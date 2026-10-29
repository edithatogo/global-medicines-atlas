"""Atomic group workbook candidate package with complete native-cell restore."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from contextlib import ExitStack
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .mbs_demographic_extraction import (
    MAX_SOURCE_BYTES,
    AncillaryCell,
    DemographicRow,
    WorkbookMember,
)
from .mbs_demographic_package import (
    ancillary_schema,
    candidate_parquet_writer,
    canonical_package_json,
    file_fingerprint,
    native_ancillary_record,
)
from .mbs_demographic_silver import MAX_BATCH_BYTES
from .mbs_group_workbook_silver import (
    GROUP_WORKBOOK_HEADERS,
    LAYOUT_SHA256,
    GroupWorkbookSource,
    group_workbook_schema,
    iter_group_workbook_batches,
    iter_group_workbook_records,
)

DATA_FILES = ("primary.parquet", "ancillary.parquet", "inventory.json")
BATCH_ROWS = 1024
BOUNDARIES = {"rights_qualified": False, "admitted": False, "published": False}


def _context(
    payload: bytes, source: GroupWorkbookSource
) -> GroupWorkbookSource:
    source = GroupWorkbookSource.model_validate(source.model_dump())
    if (
        not 0 < len(payload) <= MAX_SOURCE_BYTES
        or sha256(payload).hexdigest() != source.source_sha256
    ):
        raise ValueError("group workbook source payload identity differs")
    return source


def _ancillary_schema() -> pa.Schema:
    schema = ancillary_schema()
    metadata = dict(schema.metadata or {})
    metadata[b"schema_name"] = (
        b"global-medicines-atlas.mbs-group-workbook.ancillary-cells"
    )
    return schema.with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType] -- Arrow schema metadata stub


def _rows(batches: Iterator[pa.RecordBatch]) -> Iterator[dict[str, Any]]:
    for batch in batches:
        yield from batch.to_pylist()


def _coverage() -> dict[str, Any]:
    return {
        "native_primary_rows": 0,
        "native_primary_cells": 0,
        "ancillary_cells": 0,
        "services_conversion_statuses": Counter(),
        "benefit_conversion_statuses": Counter(),
    }


def _observe(row: dict[str, Any], coverage: dict[str, Any]) -> None:
    coverage["native_primary_rows"] += 1
    coverage["native_primary_cells"] += sum(
        cell["state"] != "absent" for cell in row["native_cells"]
    )
    coverage["services_conversion_statuses"][
        row["services_conversion_status"]
    ] += 1
    coverage["benefit_conversion_statuses"][
        row["benefit_conversion_status"]
    ] += 1


def _finish(
    coverage: dict[str, Any], inventory: dict[str, Any]
) -> dict[str, Any]:
    total = sum(sheet["native_cell_count"] for sheet in inventory["sheets"])
    if total != coverage["native_primary_cells"] + coverage["ancillary_cells"]:
        raise ValueError("group workbook complete cell denominator differs")
    return {
        **coverage,
        "services_conversion_statuses": dict(
            sorted(coverage["services_conversion_statuses"].items())
        ),
        "benefit_conversion_statuses": dict(
            sorted(coverage["benefit_conversion_statuses"].items())
        ),
        "native_workbook_cells": total,
        "native_field_slots": coverage["native_primary_rows"]
        * len(GROUP_WORKBOOK_HEADERS),
    }


def _manifest(
    output: Path, source: GroupWorkbookSource, coverage: dict[str, Any]
) -> dict[str, Any]:
    content = {
        "schema_id": "global-medicines-atlas.mbs-group-workbook-package",
        "schema_version": 1,
        "candidate_only": True,
        "source": source.model_dump(mode="json"),
        "source_object_id": source.object_id,
        "source_measure_id": source.source_measure_id,
        "benefit_semantics": source.benefit_semantics.model_dump(mode="json"),
        "header_profile_sha256": LAYOUT_SHA256,
        "coverage": coverage,
        "files": {name: file_fingerprint(output / name) for name in DATA_FILES},
        "boundaries": dict(BOUNDARIES),
    }
    return {
        **content,
        "output_id": sha256(canonical_package_json(content)).hexdigest(),
    }


def verify_group_workbook_package(
    output: Path, payload: bytes, source: GroupWorkbookSource
) -> dict[str, Any]:
    """Restore all typed/native rows, ancillary cells and complete inventories.

    Admission requires an external binding to the manifest digest. Internal
    integrity establishes no benefit meaning, row grain, rights or release.
    """
    source = _context(payload, source)
    output = Path(output)
    if {path.name for path in output.iterdir()} != {
        *DATA_FILES,
        "manifest.json",
    }:
        raise ValueError("group workbook package file inventory differs")
    report: dict[str, Any] = json.loads((output / "manifest.json").read_bytes())
    if report.get("files") != {
        name: file_fingerprint(output / name) for name in DATA_FILES
    }:
        raise ValueError("group workbook package file digest or size differs")
    primary = pq.ParquetFile(output / "primary.parquet")
    ancillary = pq.ParquetFile(output / "ancillary.parquet")
    if not primary.schema_arrow.equals(
        group_workbook_schema(), check_metadata=True
    ) or not ancillary.schema_arrow.equals(
        _ancillary_schema(), check_metadata=True
    ):
        raise ValueError("group workbook restored Arrow schema differs")
    actual_primary = iter(_rows(primary.iter_batches(batch_size=BATCH_ROWS)))  # pyright: ignore[reportUnknownMemberType] -- optional Arrow selectors unused
    actual_ancillary = iter(
        _rows(
            ancillary.iter_batches(batch_size=BATCH_ROWS)  # pyright: ignore[reportUnknownMemberType] -- optional Arrow selectors unused
        )
    )  # pyright: ignore[reportUnknownMemberType] -- optional Arrow selectors unused
    inventory: dict[str, Any] = {"members": [], "sheets": []}
    coverage = _coverage()

    def expected_rows() -> Iterator[DemographicRow]:
        for record in iter_group_workbook_records(payload, source):
            if isinstance(record, DemographicRow):
                yield record
            elif isinstance(record, AncillaryCell):
                if next(actual_ancillary, None) != native_ancillary_record(
                    record, source
                ):
                    raise ValueError(
                        "group workbook ancillary source parity differs"
                    )
                coverage["ancillary_cells"] += 1
            else:
                inventory[
                    "members"
                    if isinstance(record, WorkbookMember)
                    else "sheets"
                ].append(asdict(record))

    for expected in _rows(iter_group_workbook_batches(expected_rows(), source)):
        actual = next(actual_primary, None)
        if actual != expected:
            raise ValueError("group workbook primary source parity differs")
        _observe(expected, coverage)
    if (
        next(actual_primary, None) is not None
        or next(actual_ancillary, None) is not None
    ):
        raise ValueError("group workbook restored row count differs")
    if json.loads((output / "inventory.json").read_bytes()) != inventory:
        raise ValueError("group workbook native package inventory differs")
    coverage = _finish(coverage, inventory)
    if report != _manifest(output, source, coverage):
        raise ValueError("group workbook coverage or qualification differs")
    return report


def build_group_workbook_package(
    payload: bytes, source: GroupWorkbookSource, output: Path
) -> dict[str, Any]:
    """Finalize only after all native members/cells and restore checks succeed."""
    output = Path(output)
    if output.exists():
        raise FileExistsError("group workbook output already exists")
    source = _context(payload, source)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=".group-workbook-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "package"
        staged.mkdir()
        inventory: dict[str, Any] = {"members": [], "sheets": []}
        coverage = _coverage()
        with ExitStack() as stack:
            primary = stack.enter_context(
                candidate_parquet_writer(
                    staged / "primary.parquet", group_workbook_schema()
                )
            )
            ancillary = stack.enter_context(
                candidate_parquet_writer(
                    staged / "ancillary.parquet", _ancillary_schema()
                )
            )
            pending: list[dict[str, Any]] = []
            pending_bytes = 0

            def flush() -> None:
                nonlocal pending, pending_bytes
                if pending:
                    ancillary.write_batch(
                        pa.RecordBatch.from_pylist(
                            pending, schema=_ancillary_schema()
                        )
                    )
                    pending, pending_bytes = [], 0

            def rows() -> Iterator[DemographicRow]:
                nonlocal pending_bytes
                for record in iter_group_workbook_records(payload, source):
                    if isinstance(record, DemographicRow):
                        yield record
                    elif isinstance(record, AncillaryCell):
                        row = native_ancillary_record(record, source)
                        size = len(canonical_package_json(row))
                        if size > MAX_BATCH_BYTES:
                            raise ValueError(
                                "group workbook ancillary byte bound exceeded"
                            )
                        if pending and pending_bytes + size > MAX_BATCH_BYTES:
                            flush()
                        pending.append(row)
                        pending_bytes += size
                        coverage["ancillary_cells"] += 1
                        if len(pending) == BATCH_ROWS:
                            flush()
                    else:
                        inventory[
                            "members"
                            if isinstance(record, WorkbookMember)
                            else "sheets"
                        ].append(asdict(record))

            for batch in iter_group_workbook_batches(rows(), source):
                primary.write_batch(batch)
                for row in batch.to_pylist():
                    _observe(row, coverage)
            flush()
        (staged / "inventory.json").write_bytes(
            canonical_package_json(inventory)
        )
        report = _manifest(staged, source, _finish(coverage, inventory))
        (staged / "manifest.json").write_bytes(canonical_package_json(report))
        verify_group_workbook_package(staged, payload, source)
        staged.rename(output)
    return report
