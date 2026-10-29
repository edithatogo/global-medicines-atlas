"""Deterministic group CSV candidate packages with independent native parity.

Only metadata is returned. Construction and restore establish neither source
meaning nor rights, admission, federation acceptance or publication authority.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.parquet as pq

from .mbs_demographic_package import (
    candidate_parquet_writer,
    canonical_package_json,
    file_fingerprint,
)
from .mbs_group_silver import (
    DIMENSIONS,
    GROUP_HEADERS,
    MbsGroupSource,
    group_silver_schema,
    iter_group_silver_batches,
)

PARQUET = "group.parquet"
MANIFEST = "qualification.json"
BATCH_ROWS = 1024


def _independent_values(payload: bytes) -> Iterator[tuple[str, ...]]:
    reader = pcsv.open_csv(
        BytesIO(payload),
        read_options=pcsv.ReadOptions(
            use_threads=False, block_size=8 * 1024 * 1024
        ),
        parse_options=pcsv.ParseOptions(newlines_in_values=True),
        convert_options=pcsv.ConvertOptions(
            column_types=dict.fromkeys(GROUP_HEADERS, pa.string()),
            strings_can_be_null=False,
        ),
    )
    if tuple(reader.schema.names) != GROUP_HEADERS:
        raise ValueError("independent group CSV header differs")
    yield GROUP_HEADERS
    for batch in reader:
        for row in batch.to_pylist():
            yield tuple(row[name] for name in GROUP_HEADERS)


def _typed_values_match(row: dict[str, Any], native: tuple[str, ...]) -> bool:
    if row["record_kind"] == "header":
        return (
            row["services_count"] is None
            and row["benefit_decimal"] is None
            and row["services_conversion_status"] == "header"
            and row["benefit_conversion_status"] == "header"
            and all(row[name] is None for name in DIMENSIONS)
        )
    if tuple(row[name] for name in DIMENSIONS) != native[: len(DIMENSIONS)]:
        return False
    for value_name, status_name, index in (
        ("services_count", "services_conversion_status", 6),
        ("benefit_decimal", "benefit_conversion_status", 7),
    ):
        if row[status_name] == "converted":
            try:
                original = Decimal(native[index])
            except InvalidOperation:
                return False
            if not original.is_finite() or original != row[value_name]:
                return False
        elif row[value_name] is not None:
            return False
    return True


def verify_group_package(output: Path, payload: bytes) -> dict[str, Any]:
    """Restore exact files and compare every native slot with Arrow CSV.

    The manifest must be externally digest-bound for admission. This verifier
    detects corruption and inconsistent source binding; it does not authorize
    an untrusted manifest or qualify the meaning of retained native values.
    """
    output = Path(output)
    if {path.name for path in output.iterdir()} != {PARQUET, MANIFEST}:
        raise ValueError("group package file inventory differs")
    report: dict[str, Any] = json.loads((output / MANIFEST).read_bytes())
    if report["parquet"] != file_fingerprint(output / PARQUET):
        raise ValueError("group candidate digest or byte count differs")
    source = MbsGroupSource.model_validate(report["source"])
    # Exhaust the guarded producer as a separate input preflight, without
    # retaining its batches. It binds payload identity and complete CSV shape.
    for _ in iter_group_silver_batches(payload, source):
        pass
    parquet = pq.ParquetFile(output / PARQUET)
    if not parquet.schema_arrow.equals(
        group_silver_schema(), check_metadata=True
    ):
        raise ValueError("group candidate schema differs")
    expected = iter(_independent_values(payload))
    coordinates = csv.reader(
        StringIO(payload.decode("utf-8-sig"), newline=""), strict=True
    )
    count = 0
    binding = {
        "dataset": source.dataset,
        "evidence_class": source.acquisition.evidence_class.value
        if source.acquisition.evidence_class
        else "unknown",
        "source_format": "csv",
        "source_id": source.acquisition.source_id,
        "source_sha256": source.source_sha256,
        "source_revision": source.source_revision,
        "source_path": source.source_path,
        "source_measure_id": source.source_measure_id,
        "acquisition_id": source.acquisition.acquisition_id,
        "acquisition_sha256": source.acquisition.digest(),
        "b2_manifest_sha256": source.raw_manifest.manifest_sha256,
    }
    services: Counter[str] = Counter()
    benefits: Counter[str] = Counter()
    for batch in parquet.iter_batches(batch_size=BATCH_ROWS):  # pyright: ignore[reportUnknownMemberType] -- optional Arrow selectors unused
        for row in batch.to_pylist():
            count += 1
            native = tuple(cell["value"] for cell in row["native_cells"])
            original = next(coordinates, None)
            if (
                tuple(cell["name"] for cell in row["native_cells"])  # ruff: ignore[too-many-boolean-expressions] -- all restored source bindings must agree
                != GROUP_HEADERS
                or native != next(expected, None)
                or original is None
                or tuple(original) != native
                or row["physical_line_end"] != coordinates.line_num
                or not _typed_values_match(row, native)
                or any(cell["state"] != "value" for cell in row["native_cells"])
                or any(row[key] != value for key, value in binding.items())
                or row["source_row_id"] != f"{source.object_id}:{count}"
                or row["source_object_id"] != source.object_id
                or row["native_record_index"] != count
                or row["record_kind"] != ("header" if count == 1 else "data")
                or row["benefit_interpretation_state"] != "native_unresolved"
                or row["patient_rate_state"] != "unavailable"
            ):
                raise ValueError("group restored source-field parity differs")
            if count > 1:
                services[row["services_conversion_status"]] += 1
                benefits[row["benefit_conversion_status"]] += 1
    coverage = {
        "header_records": 1,
        "data_records": count - 1,
        "native_field_slots": count * len(GROUP_HEADERS),
        "services_conversion_statuses": dict(sorted(services.items())),
        "benefit_conversion_statuses": dict(sorted(benefits.items())),
    }
    if next(expected, None) is not None or coverage != report["coverage"]:
        raise ValueError("group restored coverage differs")
    if (
        report["candidate_only"] is not True
        or report["source_object_id"] != source.object_id
        or report["benefit_semantics"]
        != source.benefit_semantics.model_dump(mode="json")
        or report["boundaries"]
        != {"rights_qualified": False, "admitted": False, "published": False}
    ):
        raise ValueError("group candidate qualification binding differs")
    return report


def build_group_package(
    payload: bytes, source: MbsGroupSource, output: Path
) -> dict[str, Any]:
    """Finalize only after all records and independent restore checks pass."""
    source = MbsGroupSource.model_validate(source.model_dump())
    output = Path(output)
    if output.exists():
        raise FileExistsError("group candidate output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=".group-candidate-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "package"
        staged.mkdir()
        records = 0
        services: Counter[str] = Counter()
        benefits: Counter[str] = Counter()
        with candidate_parquet_writer(
            staged / PARQUET, group_silver_schema()
        ) as writer:
            for batch in iter_group_silver_batches(payload, source):
                writer.write_batch(batch)
                for row in batch.to_pylist():
                    records += 1
                    if row["record_kind"] == "data":
                        services[row["services_conversion_status"]] += 1
                        benefits[row["benefit_conversion_status"]] += 1
        report = {
            "schema_version": "1.0",
            "candidate_only": True,
            "source": source.model_dump(mode="json"),
            "source_object_id": source.object_id,
            "benefit_semantics": source.benefit_semantics.model_dump(
                mode="json"
            ),
            "parquet": file_fingerprint(staged / PARQUET),
            "coverage": {
                "header_records": 1,
                "data_records": records - 1,
                "native_field_slots": records * len(GROUP_HEADERS),
                "services_conversion_statuses": dict(sorted(services.items())),
                "benefit_conversion_statuses": dict(sorted(benefits.items())),
            },
            "boundaries": {
                "rights_qualified": False,
                "admitted": False,
                "published": False,
            },
        }
        (staged / MANIFEST).write_bytes(canonical_package_json(report))
        verify_group_package(staged, payload)
        staged.rename(output)
    return report
