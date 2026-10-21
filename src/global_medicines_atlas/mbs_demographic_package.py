"""Transactional, deterministic candidate outputs over frozen demographic bytes.

This writes a local rebuildable derivative. It does not upload, authorize
release, qualify source meanings or admit any output. Native source payloads
remain the evidentiary truth; package inventories fingerprint every ZIP member.
"""

from __future__ import annotations

import json
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
    AncillaryCell,
    WorkbookMember,
    iter_demographic_records,
)
from .mbs_demographic_silver import (
    MAX_BATCH_BYTES,
    DemographicRow,
    DemographicSource,
    demographic_silver_schema,
    iter_demographic_silver_batches,
    summarize_demographic_batches,
)

BATCH_ROWS = 1024
PACKAGE_FILES = ("primary.parquet", "ancillary.parquet", "inventory.json")


def canonical_package_json(value: Any) -> bytes:
    """Serialize candidate metadata deterministically, rejecting non-finite values."""
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode()


def ancillary_schema() -> pa.Schema:
    """Source-bound cells outside the primary body, with native properties."""
    names = (
        "source_object_id",
        "source_sha256",
        "source_revision",
        "source_path",
        "part_path",
        "coordinate",
        "native_name",
        "state",
        "native_properties_json",
    )
    return pa.schema(
        [
            *(pa.field(name, pa.string(), nullable=False) for name in names),
            pa.field("sheet_name", pa.string()),
            pa.field("row_index", pa.int64(), nullable=False),
            pa.field("column_index", pa.int64(), nullable=False),
            pa.field("native_value", pa.string()),
        ],
        metadata={
            "schema_name": "global-medicines-atlas.mbs-demographic-silver.ancillary-cells",
            "schema_version": "1.0",
            "layer": "silver",
            "qualification": "candidate_only",
        },
    )


def _ancillary(
    cell: AncillaryCell, source: DemographicSource
) -> dict[str, Any]:
    return {
        "source_object_id": source.object_id,
        "source_sha256": source.source_sha256,
        "source_revision": source.source_revision,
        "source_path": source.source_path,
        "part_path": cell.part_path,
        "sheet_name": cell.sheet_name,
        "row_index": cell.row_index,
        "column_index": cell.column_index,
        "coordinate": cell.coordinate,
        "native_name": cell.cell.name,
        "state": cell.cell.state,
        "native_value": cell.cell.value,
        "native_properties_json": canonical_package_json(
            cell.cell.native_properties
        )
        .decode()
        .rstrip("\n"),
    }


def candidate_parquet_writer(path: Path, schema: pa.Schema) -> pq.ParquetWriter:
    """Create the governed deterministic candidate Parquet writer."""
    return pq.ParquetWriter(
        path,
        schema,
        version="2.6",
        compression="zstd",
        compression_level=9,
        use_dictionary=False,
        write_statistics=True,
        data_page_version="2.0",
    )


def file_fingerprint(path: Path) -> dict[str, Any]:
    """Stream the exact file digest and byte count without retaining its content."""
    digest = sha256()
    size = 0
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
            size += len(block)
    return {"sha256": digest.hexdigest(), "bytes": size}


def _build(
    payload: bytes, source: DemographicSource, output: Path
) -> dict[str, Any]:
    inventory: dict[str, Any] = {"members": [], "sheets": []}
    ancillary_count = 0
    with ExitStack() as stack:
        primary_writer = stack.enter_context(
            candidate_parquet_writer(
                output / "primary.parquet", demographic_silver_schema()
            )
        )
        ancillary_writer = stack.enter_context(
            candidate_parquet_writer(
                output / "ancillary.parquet", ancillary_schema()
            )
        )

        def rows() -> Iterator[DemographicRow]:
            nonlocal ancillary_count
            buffer: list[dict[str, Any]] = []
            size = 0
            for record in iter_demographic_records(payload, source):
                if isinstance(record, DemographicRow):
                    yield record
                elif isinstance(record, AncillaryCell):
                    projected = _ancillary(record, source)
                    record_bytes = len(canonical_package_json(projected))
                    if record_bytes > MAX_BATCH_BYTES:
                        raise ValueError(
                            "ancillary cell exceeds output byte bound"
                        )
                    if buffer and (
                        len(buffer) == BATCH_ROWS
                        or size + record_bytes > MAX_BATCH_BYTES
                    ):
                        ancillary_writer.write_batch(
                            pa.RecordBatch.from_pylist(
                                buffer, schema=ancillary_schema()
                            )
                        )
                        buffer, size = [], 0
                    buffer.append(projected)
                    size += record_bytes
                    ancillary_count += 1
                elif isinstance(record, WorkbookMember):
                    inventory["members"].append(asdict(record))
                else:
                    inventory["sheets"].append(asdict(record))
            if buffer:
                ancillary_writer.write_batch(
                    pa.RecordBatch.from_pylist(
                        buffer, schema=ancillary_schema()
                    )
                )

        def batches() -> Iterator[pa.RecordBatch]:
            for batch in iter_demographic_silver_batches(
                rows(), source, rows_per_batch=BATCH_ROWS
            ):
                primary_writer.write_batch(batch)
                yield batch

        coverage = summarize_demographic_batches(batches())
    (output / "inventory.json").write_bytes(canonical_package_json(inventory))
    workbook_cells = sum(
        sheet["native_cell_count"] for sheet in inventory["sheets"]
    )
    primary_cells = sum(count["native_fields"] for count in coverage.values())
    if (
        source.source_format == "workbook"
        and workbook_cells != primary_cells + ancillary_count
    ):
        raise ValueError("workbook source/output cell accounting differs")
    return {
        "schema_version": "1.0",
        "candidate_only": True,
        "source": source.model_dump(mode="json"),
        "source_object_id": source.object_id,
        "benefit_semantics": source.benefit_semantics.model_dump(mode="json"),
        "coverage": coverage,
        "ancillary_cells": ancillary_count,
        "native_workbook_cells": workbook_cells,
        "files": {
            name: file_fingerprint(output / name) for name in PACKAGE_FILES
        },
        "limits": {
            "semantic_qualification": False,
            "rights_qualification": False,
            "admission": False,
            "publication": False,
        },
    }


def build_demographic_package(
    payload: bytes, source: DemographicSource, output: Path
) -> dict[str, Any]:
    """Finalize only after source exhaustion and complete cell accounting."""
    source = DemographicSource.model_validate(source.model_dump())
    output = Path(output)
    if output.exists():
        raise FileExistsError("candidate output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=".demographic-build-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "package"
        staged.mkdir()
        report = _build(payload, source, staged)
        (staged / "qualification.json").write_bytes(
            canonical_package_json(report)
        )
        verify_demographic_package(staged)
        staged.rename(output)
    return report


def verify_demographic_package(output: Path) -> dict[str, Any]:
    """Read Parquet independently and compare digests, schemas and coverage.

    This detects corruption relative to the retained candidate report. The
    report itself must be externally content-bound for admission or release.
    """
    output = Path(output)
    report: dict[str, Any] = json.loads(
        (output / "qualification.json").read_bytes()
    )
    if {path.name for path in output.iterdir()} != {
        *PACKAGE_FILES,
        "qualification.json",
    }:
        raise ValueError("candidate package file inventory differs")
    if set(report["files"]) != set(PACKAGE_FILES):
        raise ValueError("candidate manifest inventory differs")
    for name in PACKAGE_FILES:
        if file_fingerprint(output / name) != report["files"][name]:
            raise ValueError("candidate output digest or size differs")
    source = DemographicSource.model_validate(report["source"])
    if (
        report["source_object_id"] != source.object_id
        or report["candidate_only"] is not True
        or report["benefit_semantics"]
        != source.benefit_semantics.model_dump(mode="json")
        or report["limits"]
        != {
            "semantic_qualification": False,
            "rights_qualification": False,
            "admission": False,
            "publication": False,
        }
    ):
        raise ValueError("candidate source binding differs")
    primary = pq.ParquetFile(output / "primary.parquet")
    ancillary = pq.ParquetFile(output / "ancillary.parquet")
    if not primary.schema_arrow.equals(
        demographic_silver_schema(), check_metadata=True
    ) or not ancillary.schema_arrow.equals(
        ancillary_schema(), check_metadata=True
    ):
        raise ValueError("candidate output schema differs")
    coverage = summarize_demographic_batches(
        primary.iter_batches(batch_size=BATCH_ROWS)  # pyright: ignore[reportUnknownMemberType] -- Arrow optional column selectors unused
    )
    if set(coverage) - {source.object_id}:
        raise ValueError("candidate restored source object differs")
    inventory = json.loads((output / "inventory.json").read_bytes())
    native_cells = sum(
        sheet["native_cell_count"] for sheet in inventory["sheets"]
    )
    primary_cells = sum(count["native_fields"] for count in coverage.values())
    if native_cells != report["native_workbook_cells"] or (
        source.source_format == "workbook"
        and native_cells != primary_cells + ancillary.metadata.num_rows
    ):
        raise ValueError("candidate restored workbook cell accounting differs")
    if (
        coverage != report["coverage"]
        or ancillary.metadata.num_rows != report["ancillary_cells"]
    ):
        raise ValueError("candidate restored coverage differs")
    return report
