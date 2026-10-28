"""Reproducible historical workbook records with full native restore.

Every native extraction record is retained alongside queryable cell properties.
Decimals are lossless storage candidates; no dates, currency, payment or patient
meaning is inferred. The original archive acquisition remains the B1/B2 binding.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict
from hashlib import sha256
from itertools import zip_longest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from .mbs_demographic_package import (
    candidate_parquet_writer,
    canonical_package_json,
    file_fingerprint,
)
from .mbs_historical_csv_package import FrozenMbsMember
from .mbs_historical_workbook_native import iter_workbook_records
from .mbs_workbook_silver import (
    _number,  # pyright: ignore[reportPrivateUsage] -- shared exact numeric storage conversion
)

DATA = "records.parquet"
MANIFEST = "manifest.json"
MAX_FILE_BYTES = 4 * 1024**3
MAX_MANIFEST_BYTES = 1024 * 1024
BATCH_ROWS = 1024
MAX_BATCH_BYTES = 8 * 1024 * 1024
BOUNDARIES = {
    "semantics_qualified": False,
    "rights_qualified": False,
    "admitted": False,
    "published": False,
}


def _identity(member: FrozenMbsMember) -> str:
    return sha256(canonical_package_json(asdict(member))).hexdigest()


def _schema(member: FrozenMbsMember) -> pa.Schema:
    return pa.schema(
        [
            pa.field("record_ordinal", pa.int64(), nullable=False),
            pa.field("native_record_id", pa.string(), nullable=False),
            pa.field("record_kind", pa.string(), nullable=False),
            pa.field("sheet_path", pa.string()),
            pa.field("row_index", pa.int32()),
            pa.field("column_index", pa.int32()),
            pa.field("coordinate", pa.string()),
            pa.field("native_value", pa.string()),
            pa.field("raw_value", pa.string()),
            pa.field("cell_type", pa.string()),
            pa.field("formula", pa.string()),
            pa.field("native_state", pa.string()),
            pa.field("decimal_candidate", pa.decimal128(38, 9)),
            pa.field("conversion_status", pa.string(), nullable=False),
            pa.field("native_record", pa.string(), nullable=False),
        ],
        metadata={
            "schema_name": "global-medicines-atlas.mbs-historical-workbook-native.records",
            "schema_version": "1",
            "member_binding": canonical_package_json(asdict(member)),
            "qualification": "candidate_only",
            "date_interpretation": "native_unresolved",
            "currency_interpretation": "unqualified",
            "patient_rates": "unavailable",
            "absence_interpretation": "unknown",
        },
    )


def _row(record: dict[str, Any], ordinal: int, identity: str) -> dict[str, Any]:
    cell = record.get("cell", {})
    props = cell.get("native_properties", {})
    status = "not_numeric_cell"
    decimal = None
    if record["kind"] == "cell" and props.get("cell_type") in {None, "n"}:
        raw = props.get("raw_value")
        converted = (
            _number(raw)
            if raw is not None
            else {"conversion_status": "missing_value"}
        )
        status = converted["conversion_status"]
        decimal = converted.get("decimal_value")
    return {
        "record_ordinal": ordinal,
        "native_record_id": f"{identity}:/records/{ordinal}",
        "record_kind": record["kind"],
        "sheet_path": record.get("sheet_path"),
        "row_index": record.get("row_index"),
        "column_index": record.get("column_index"),
        "coordinate": record.get("coordinate"),
        "native_value": cell.get("value"),
        "raw_value": props.get("raw_value"),
        "cell_type": props.get("cell_type"),
        "formula": props.get("formula"),
        "native_state": cell.get("state"),
        "decimal_candidate": decimal,
        "conversion_status": status,
        "native_record": canonical_package_json(record).decode(),
    }


def _rows(
    path: Path, member: FrozenMbsMember, native: str
) -> Iterator[dict[str, Any]]:
    identity = _identity(member)
    for ordinal, record in enumerate(
        iter_workbook_records(path, member, native)
    ):
        yield _row(record, ordinal, identity)


def _batches(
    path: Path, member: FrozenMbsMember, native: str
) -> Iterator[pa.RecordBatch]:
    rows: list[dict[str, Any]] = []
    size = 0
    schema = _schema(member)
    for row in _rows(path, member, native):
        encoded = len(
            json.dumps(
                row, ensure_ascii=False, separators=(",", ":"), default=str
            ).encode()
        )
        if encoded > MAX_BATCH_BYTES:
            raise ValueError("historical workbook record exceeds batch bound")
        if rows and (
            len(rows) >= BATCH_ROWS or size + encoded > MAX_BATCH_BYTES
        ):
            yield pa.RecordBatch.from_pylist(rows, schema=schema)
            rows, size = [], 0
        rows.append(row)
        size += encoded
    if rows:
        yield pa.RecordBatch.from_pylist(rows, schema=schema)


def _coverage(rows: Iterator[dict[str, Any]]) -> dict[str, Any]:
    kinds: Counter[str] = Counter()
    conversions: Counter[str] = Counter()
    states: Counter[str] = Counter()
    digest = sha256()
    for row in rows:
        kinds[row["record_kind"]] += 1
        conversions[row["conversion_status"]] += 1
        if row["native_state"] is not None:
            states[row["native_state"]] += 1
        digest.update(row["native_record"].encode())
    return {
        "records": sum(kinds.values()),
        "cells": kinds["cell"],
        "rows": kinds["row"],
        "sheets": kinds["sheet"],
        "kinds": dict(sorted(kinds.items())),
        "conversion_statuses": dict(sorted(conversions.items())),
        "native_states": dict(sorted(states.items())),
        "native_records_sha256": digest.hexdigest(),
    }


def _fingerprint(output: Path) -> dict[str, Any]:
    path = output / DATA
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > MAX_FILE_BYTES
    ):
        raise ValueError("historical workbook file byte bound differs")
    return file_fingerprint(path)


def _manifest(
    output: Path, member: FrozenMbsMember, coverage: dict[str, Any]
) -> dict[str, Any]:
    identity = {
        "schema_id": "global-medicines-atlas.mbs-historical-workbook-package",
        "schema_version": 1,
        "candidate_only": True,
        "member_binding": asdict(member),
        "coverage": coverage,
        "parquet": _fingerprint(output),
        "boundaries": dict(BOUNDARIES),
    }
    return {
        **identity,
        "output_id": sha256(canonical_package_json(identity)).hexdigest(),
    }


def verify_workbook_package(
    output: Path, path: Path, member: FrozenMbsMember, native: str
) -> dict[str, Any]:
    """Restore every original record and annotation from a separate native parse."""
    if (
        output.is_symlink()
        or {p.name for p in output.iterdir()} != {DATA, MANIFEST}
        or any(p.is_symlink() or not p.is_file() for p in output.iterdir())
    ):
        raise ValueError("historical workbook package inventory differs")
    if (output / MANIFEST).stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("historical workbook manifest byte bound differs")
    report = json.loads((output / MANIFEST).read_bytes())
    if report.get("parquet") != _fingerprint(output):
        raise ValueError("historical workbook package digest differs")
    parquet = pq.ParquetFile(output / DATA)
    if not parquet.schema_arrow.equals(_schema(member), check_metadata=True):
        raise ValueError("historical workbook schema or lineage differs")
    restored = (
        row
        for batch in parquet.iter_batches(batch_size=BATCH_ROWS)  # pyright: ignore[reportUnknownMemberType] -- unused Arrow selectors
        for row in batch.to_pylist()
    )  # pyright: ignore[reportUnknownMemberType] -- unused Arrow selector overloads

    def checked() -> Iterator[dict[str, Any]]:
        for actual, expected in zip_longest(
            restored, _rows(path, member, native)
        ):
            if actual is None or actual != expected:
                raise ValueError(
                    "historical workbook native restore or annotations differ"
                )
            yield actual

    coverage = _coverage(checked())
    if report != _manifest(output, member, coverage):
        raise ValueError(
            "historical workbook coverage or qualification differs"
        )
    return report


def build_workbook_package(
    path: Path, member: FrozenMbsMember, native: str, output: Path
) -> dict[str, Any]:
    """Finalize an atomic package only after exhaustive source-bound restore."""
    if output.exists() or output.is_symlink():
        raise FileExistsError("historical workbook package already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=".mbs-native-workbook-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "package"
        staged.mkdir()
        with candidate_parquet_writer(staged / DATA, _schema(member)) as writer:

            def written() -> Iterator[dict[str, Any]]:
                for batch in _batches(path, member, native):
                    writer.write_batch(batch)
                    if (staged / DATA).stat().st_size > MAX_FILE_BYTES:
                        raise ValueError(
                            "historical workbook file byte bound exceeded"
                        )
                    yield from batch.to_pylist()

            coverage = _coverage(written())
        report = _manifest(staged, member, coverage)
        (staged / MANIFEST).write_bytes(canonical_package_json(report))
        verify_workbook_package(staged, path, member, native)
        staged.rename(output)
    return report


def qualify_workbook_member_package(
    path: Path, member: FrozenMbsMember, native: str
) -> dict[str, Any]:
    """Qualify two independent builds, full source restore and DuckDB counts."""
    with TemporaryDirectory(
        prefix="mbs-native-workbook-qualification-"
    ) as temporary:
        root = Path(temporary)
        first = build_workbook_package(path, member, native, root / "first")
        second = build_workbook_package(path, member, native, root / "second")
        if first != second:
            raise ValueError("historical workbook independent builds differ")
        with duckdb.connect(":memory:") as connection:
            actual = connection.execute(
                "SELECT count(*), count(*) FILTER (WHERE record_kind = 'cell'), count(*) FILTER (WHERE record_kind = 'row'), count(*) FILTER (WHERE record_kind = 'sheet') FROM read_parquet(?)",
                [str(root / "first" / DATA)],
            ).fetchone()
        coverage = first["coverage"]
        expected = tuple(
            coverage[key] for key in ("records", "cells", "rows", "sheets")
        )
        if actual != expected:
            raise ValueError("historical workbook DuckDB denominators differ")
        return {
            "manifest": first,
            "two_builds_equal": True,
            "complete_native_restore_verified": True,
            "duckdb_records": expected[0],
            "duckdb_cells": expected[1],
            "duckdb_rows": expected[2],
            "duckdb_sheets": expected[3],
            "native_values_or_names_emitted": False,
        }
