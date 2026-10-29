"""Native MBS group utilisation candidates, independent of demographic rows.

The shared source context supplies B1/B2 identity validation only. Group,
subgroup, item and state remain native dimensions; no age, hierarchy mapping,
patient denominator, currency meaning or cross-source equivalence is inferred.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterator
from decimal import Decimal
from hashlib import sha256
from typing import Any, ClassVar

import pyarrow as pa
from pydantic import ConfigDict, model_validator

from .mbs_demographic_silver import (
    DECIMAL_TYPE,
    MAX_BATCH_BYTES,
    MAX_BATCH_ROWS,
    MAX_CELL_CHARS,
    DemographicSource,
)
from .mbs_utilisation_numeric_policy import (
    ExactNumericPolicy,
    NumericTokenError,
    parse_exact_numeric_token,
)

GROUP_HEADERS = (
    "Year",
    "Month of Processing",
    "Group",
    "Sub-Group",
    "Item Number",
    "State",
    "Services",
    "Benefit",
)
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_RECORDS = 10_000_000
DIMENSIONS = (
    "year_native",
    "processing_month_native",
    "group_native",
    "subgroup_native",
    "item_number_native",
    "state_native",
)


class MbsGroupSource(DemographicSource):
    """Exact group CSV source, reusing only the common B1/B2 binding rules."""

    SOURCE_FAMILY: ClassVar[str] = "au-data-gov-mbs-group"
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [{"properties": {"source_format": {"const": "csv"}}}]
        }
    )

    @model_validator(mode="after")
    def group_is_csv(self) -> MbsGroupSource:
        if self.source_format != "csv":
            raise ValueError("group candidate requires the CSV source format")
        return self

    @property
    def headers(self) -> tuple[str, ...]:
        """Return the independently observed group header, without age fields."""
        return GROUP_HEADERS


def group_silver_schema() -> pa.Schema:
    """Retain native source records and independent source-reported measures."""
    strings = (
        "dataset",
        "source_format",
        "evidence_class",
        "source_id",
        "source_sha256",
        "source_revision",
        "source_path",
        "source_object_id",
        "source_measure_id",
        "acquisition_id",
        "acquisition_sha256",
        "b2_manifest_sha256",
        "source_row_id",
        "record_kind",
        "benefit_interpretation_state",
        "benefit_conversion_status",
        "services_conversion_status",
        "patient_rate_state",
    )
    cell = pa.struct([
        pa.field("name", pa.string(), nullable=False),
        pa.field("state", pa.string(), nullable=False),
        pa.field("value", pa.string(), nullable=False),
    ])
    return pa.schema(
        [
            *(pa.field(name, pa.string(), nullable=False) for name in strings),
            *(pa.field(name, pa.string()) for name in DIMENSIONS),
            pa.field("native_record_index", pa.int64(), nullable=False),
            pa.field("physical_line_end", pa.int64(), nullable=False),
            pa.field(
                "native_cells",
                pa.list_(pa.field("element", cell, nullable=False)),
                nullable=False,
            ),
            pa.field("services_count", pa.int64()),
            pa.field("benefit_decimal", DECIMAL_TYPE),
        ],
        metadata={
            "schema_name": "global-medicines-atlas.mbs-group-silver.native-records",
            "schema_version": "1.0",
            "layer": "silver",
            "qualification": "candidate_only",
            "age_dimension": "not_in_source",
            "currency_interpretation": "unresolved",
            "hierarchy_equivalence": "unestablished",
            "patient_rate": "unavailable",
            "header_record": "retained",
            "cross_source_benefit_equivalence": "unestablished",
        },
    )


def _records_unchecked(
    payload: bytes,
) -> Iterator[tuple[int, int, tuple[str, ...]]]:
    with io.TextIOWrapper(
        io.BytesIO(payload), encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.reader(stream, strict=True)
        for index, values in enumerate(reader, 1):
            if index > MAX_RECORDS or len(values) != len(GROUP_HEADERS):
                raise ValueError(
                    "group CSV record shape or resource bound differs"
                )
            if any(len(value) > MAX_CELL_CHARS for value in values):
                raise ValueError("group CSV field exceeds source text bound")
            if index == 1 and tuple(values) != GROUP_HEADERS:
                raise ValueError("group CSV header differs from observed shape")
            yield index, reader.line_num, tuple(values)


def _records(payload: bytes) -> Iterator[tuple[int, int, tuple[str, ...]]]:
    try:
        yield from _records_unchecked(payload)
    except (UnicodeError, csv.Error) as error:
        raise ValueError("group CSV encoding or grammar differs") from error


def _numeric(token: str, *, count: bool) -> tuple[Decimal | int | None, str]:  # ruff: ignore[too-many-return-statements] -- distinct lossless conversion outcomes
    if not token:
        return None, "blank"
    try:
        value = parse_exact_numeric_token(token, policy=ExactNumericPolicy())
    except NumericTokenError:
        return None, "invalid"
    if count:
        if value != value.to_integral_value():
            return None, "non_integral"
        if not -(2**63) <= value < 2**63:
            return None, "unrepresentable"
        return int(value), "converted"
    try:
        pa.scalar(value, type=DECIMAL_TYPE)
    except pa.ArrowInvalid:
        return None, "unrepresentable"
    return value, "converted"


def _row(
    index: int, line: int, values: tuple[str, ...], source: MbsGroupSource
) -> dict[str, Any]:
    header = index == 1
    services, services_status = (
        (None, "header") if header else _numeric(values[6], count=True)
    )
    benefit, benefit_status = (
        (None, "header") if header else _numeric(values[7], count=False)
    )
    return {
        "dataset": source.dataset,
        "source_format": source.source_format,
        "evidence_class": source.acquisition.evidence_class.value
        if source.acquisition.evidence_class
        else "unknown",
        "source_id": source.acquisition.source_id,
        "source_sha256": source.source_sha256,
        "source_revision": source.source_revision,
        "source_path": source.source_path,
        "source_object_id": source.object_id,
        "source_measure_id": source.source_measure_id,
        "acquisition_id": source.acquisition.acquisition_id,
        "acquisition_sha256": source.acquisition.digest(),
        "b2_manifest_sha256": source.raw_manifest.manifest_sha256,
        "source_row_id": f"{source.object_id}:{index}",
        "native_record_index": index,
        "physical_line_end": line,
        "record_kind": "header" if header else "data",
        "native_cells": [
            {"name": name, "state": "value", "value": value}
            for name, value in zip(GROUP_HEADERS, values, strict=True)
        ],
        **{
            name: None if header else values[position]
            for position, name in enumerate(DIMENSIONS)
        },
        "services_count": services,
        "services_conversion_status": services_status,
        "benefit_decimal": benefit,
        "benefit_conversion_status": benefit_status,
        "benefit_interpretation_state": "native_unresolved",
        "patient_rate_state": "unavailable",
    }


def iter_group_silver_batches(
    payload: bytes, source: MbsGroupSource, *, rows_per_batch: int = 1024
) -> Iterator[pa.RecordBatch]:
    """Preflight all CSV structure before yielding bounded native candidates.

    The header is retained as an explicit record. Native text, including blank
    fields and precision exceptions, is never replaced by converted values.
    """
    source = MbsGroupSource.model_validate(source.model_dump())
    if (
        type(rows_per_batch) is not int
        or not 1 <= rows_per_batch <= MAX_BATCH_ROWS
    ):
        raise ValueError("group output batch bound differs")
    if (
        not 0 < len(payload) <= MAX_SOURCE_BYTES
        or sha256(payload).hexdigest() != source.source_sha256
    ):
        raise ValueError("group CSV payload identity or resource bound differs")
    record_count = 0
    for _ in _records(payload):
        record_count += 1
    if not record_count:
        raise ValueError("group CSV header is unavailable")
    schema = group_silver_schema()
    buffer: list[dict[str, Any]] = []
    size = 0
    for index, line, values in _records(payload):
        projected = _row(index, line, values, source)
        encoded = len(
            json.dumps(projected, separators=(",", ":"), default=str).encode()
        )
        if encoded > MAX_BATCH_BYTES:
            raise ValueError("group native record exceeds output byte bound")
        if buffer and (
            len(buffer) == rows_per_batch or size + encoded > MAX_BATCH_BYTES
        ):
            yield pa.RecordBatch.from_pylist(buffer, schema=schema)
            buffer, size = [], 0
        buffer.append(projected)
        size += encoded
    if buffer:
        yield pa.RecordBatch.from_pylist(buffer, schema=schema)
