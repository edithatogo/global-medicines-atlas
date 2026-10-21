"""Bounded primary-table demographic candidates, retaining native evidence.

Rows must come from a separately verified source-native parser. This producer
binds supplied rows to B1/B2 references; it does not prove extraction parity,
qualify a whole workbook, establish meanings, admit outputs or publish them.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Iterator
from decimal import Decimal
from hashlib import sha256
from typing import Any, ClassVar, Literal
from urllib.parse import unquote, urlsplit

import pyarrow as pa
from pydantic import ConfigDict, Field, JsonValue, model_validator

from .bronze_raw_evidence import (
    RawEvidenceKind,
    RawEvidenceManifest,
    RawEvidenceState,
)
from .mbs_utilisation_numeric_policy import (
    ExactNumericPolicy,
    NumericTokenError,
    parse_exact_numeric_token,
    parse_ooxml_numeric_token,
)
from .models import FrozenModel
from .receipts import AcquisitionEvent, AcquisitionStatus
from .silver_field_semantics import SilverFieldSemantics

WIDTH = 8
MAX_BATCH_ROWS = 4096
MAX_PROPERTIES_BYTES = 65_536
MAX_CELL_CHARS = 65_536
MAX_BATCH_BYTES = 8 * 1024 * 1024
DECIMAL_TYPE = pa.decimal128(38, 9)
MIN_DECIMAL_ADJUSTED = -DECIMAL_TYPE.scale
MAX_DECIMAL_ADJUSTED = DECIMAL_TYPE.precision - DECIMAL_TYPE.scale - 1
CSV_HEADERS = (
    "Year",
    "Month of Processing",
    "Item Number",
    "State",
    "Age Range",
    "Gender",
    "Services",
    "Benefit",
)
WORKBOOK_HEADERS = (
    "Year",
    "Month",
    "Item_Number",
    "State",
    "Age_Range",
    "Gender",
    "Services",
    "Benefits ($)",
)


class DemographicCell(FrozenModel):
    """A native field value, explicit presence, and retained parser properties."""

    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "state": {"enum": ["value", "source_error"]}
                        }
                    },
                    "then": {"properties": {"value": {"type": "string"}}},
                    "else": {"properties": {"value": {"type": "null"}}},
                }
            ],
        }
    )

    name: str = Field(min_length=1)
    state: Literal["absent", "null", "value", "source_error"]
    value: str | None = Field(max_length=MAX_CELL_CHARS)
    native_properties: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent_presence(self) -> DemographicCell:
        if (self.state in {"value", "source_error"}) != (
            self.value is not None
        ):
            raise ValueError("native cell state and value disagree")
        return self


class DemographicRow(FrozenModel):
    """One logical CSV record or physical workbook primary-table row."""

    row_index: int = Field(strict=True, ge=1)
    cells: tuple[DemographicCell, ...] = Field(
        min_length=WIDTH, max_length=WIDTH
    )


class DemographicSource(FrozenModel):
    """One exact B1/B2 source reference and its reviewed native header shape."""

    SOURCE_FAMILY: ClassVar[str] = "au-data-gov-mbs-demographics"

    acquisition: AcquisitionEvent
    raw_manifest: RawEvidenceManifest
    dataset: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$"
    )
    source_format: Literal["csv", "workbook"]
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_path: str = Field(min_length=1)

    @model_validator(mode="after")
    def bind_source(self) -> DemographicSource:
        event = AcquisitionEvent.model_validate(self.acquisition.model_dump())
        manifest = RawEvidenceManifest.model_validate(
            self.raw_manifest.model_dump()
        )
        if event.source_id != self.SOURCE_FAMILY:
            raise ValueError("demographic source family differs")
        if manifest.row_count != 1:
            raise ValueError(
                "demographic source requires one exact B2 reference"
            )
        raw = manifest.rows[0]
        if (
            raw.source_id != event.source_id
            or raw.acquisition_id != event.acquisition_id
            or raw.content_id != event.content_id
        ):
            raise ValueError("demographic B1/B2 source identity differs")
        if (
            event.retrieval is None
            or event.retrieval.status is not AcquisitionStatus.SUCCEEDED
            or raw.kind is not RawEvidenceKind.PAYLOAD
            or raw.state is not RawEvidenceState.EXTERNAL_REFERENCE_ONLY
        ):
            raise ValueError(
                "demographic source requires a succeeded payload reference"
            )
        suffix = ".csv" if self.source_format == "csv" else ".xlsx"
        if (
            self.source_path.startswith("/")
            or ".." in self.source_path.split("/")
            or not self.source_path.endswith(suffix)
        ):
            raise ValueError("demographic source path/format differs")
        reference_path = unquote(urlsplit(raw.external_reference or "").path)
        if not reference_path.endswith(
            f"/datasets/{self.dataset}/resolve/{self.source_revision}/{self.source_path}"
        ):
            raise ValueError(
                "demographic revision/path does not match B2 reference"
            )
        return self

    @property
    def source_sha256(self) -> str:
        """Return immutable source identity, independently of acquisition."""
        return self.acquisition.payload_sha256

    @property
    def object_id(self) -> str:
        """Keep retained dataset/revision/path identities distinct for aliases."""
        binding = [
            self.dataset,
            self.source_revision,
            self.source_path,
            self.source_sha256,
        ]
        return sha256(
            json.dumps(binding, separators=(",", ":")).encode()
        ).hexdigest()

    @property
    def source_measure_id(self) -> str:
        """Identify the native benefit measure within this exact object."""
        return f"{self.object_id}:{self.headers[7]}"

    @property
    def headers(self) -> tuple[str, ...]:
        """Return native column names without renaming one era into another."""
        return CSV_HEADERS if self.source_format == "csv" else WORKBOOK_HEADERS

    @property
    def benefit_semantics(self) -> SilverFieldSemantics:
        """Like-named benefit columns remain separate unresolved measures."""
        return SilverFieldSemantics(
            source_sha256=self.source_sha256,
            source_object_id=self.object_id,
            native_name=self.headers[7],
            state="native_unresolved",
            reason="Source-reported benefit calculation is unresolved",
        )


def demographic_silver_schema() -> pa.Schema:
    """Return the candidate primary-table schema with per-row provenance."""
    cell = pa.struct([
        pa.field("name", pa.string(), nullable=False),
        pa.field("state", pa.string(), nullable=False),
        pa.field("value", pa.string()),
        pa.field("native_properties_json", pa.string(), nullable=False),
    ])
    strings = (
        "dataset",
        "source_object_id",
        "source_measure_id",
        "source_id",
        "source_sha256",
        "source_revision",
        "source_path",
        "source_format",
        "acquisition_id",
        "acquisition_sha256",
        "b2_manifest_sha256",
        "evidence_class",
        "source_row_id",
        "benefit_native_name",
        "benefit_interpretation_state",
        "benefit_conversion_status",
        "services_conversion_status",
        "age_suppression_relationship",
        "patient_rate_state",
    )
    return pa.schema(
        [
            *(pa.field(name, pa.string(), nullable=False) for name in strings),
            pa.field("native_row_index", pa.int64(), nullable=False),
            pa.field(
                "native_cells",
                pa.list_(pa.field("element", cell, nullable=False)),
                nullable=False,
            ),
            pa.field("age_native", pa.string()),
            pa.field("age_lower_bound", pa.int64()),
            pa.field("age_upper_bound", pa.int64()),
            pa.field("benefit_decimal", DECIMAL_TYPE),
            pa.field("services_count", pa.int64()),
        ],
        metadata={
            "schema_name": "global-medicines-atlas.mbs-demographic-silver.primary-rows",
            "schema_version": "1.0",
            "layer": "silver",
            "currency_interpretation": "unresolved",
            "qualification": "candidate_only",
            "projection_scope": "primary_table_only",
            "dimension": "service_benefit",
            "provenance_scope": "per_row",
            "acquisition_digest_basis": "canonical_B1_event",
            "b2_manifest_digest_basis": "canonical_manifest_rows",
            "absence_interpretation": "unknown",
            "byte_budget_measure": "utf8_compact_json_not_python_resident_memory",
            "cross_source_benefit_equivalence": "unestablished",
        },
    )


def _numeric(
    cell: DemographicCell, *, count: bool, workbook: bool
) -> tuple[Decimal | int | None, str]:
    if cell.state != "value":
        return None, cell.state
    storage = cell.native_properties.get("cell_type")
    if storage is not None and (
        not isinstance(storage, str)
        or storage not in {"n", "s", "str", "inlineStr"}
    ):
        return None, "unsupported_storage_type"
    if not cell.value:
        return None, "blank"
    try:
        value = (
            parse_ooxml_numeric_token(cell.value or "")
            if workbook
            and "cell_type" in cell.native_properties
            and storage in {None, "n"}
            else parse_exact_numeric_token(
                cell.value or "", policy=ExactNumericPolicy()
            )
        )
    except NumericTokenError:
        return None, "invalid"
    return _representable_numeric(value, count=count)


def _representable_numeric(
    value: Decimal, *, count: bool
) -> tuple[Decimal | int | None, str]:
    if count:
        if value != value.to_integral_value():
            return None, "non_integral"
        if not -(2**63) <= value < 2**63:
            return None, "unrepresentable"
        return int(value), "converted"
    if value.is_zero():
        value = Decimal(0)
    elif not MIN_DECIMAL_ADJUSTED <= value.adjusted() <= MAX_DECIMAL_ADJUSTED:
        return None, "unrepresentable"
    try:
        pa.scalar(value, type=DECIMAL_TYPE)
    except pa.ArrowInvalid:
        return None, "unrepresentable"
    return value, "converted"


def _project(
    row: DemographicRow, source: DemographicSource, binding: dict[str, str]
) -> dict[str, Any]:
    if tuple(cell.name for cell in row.cells) != source.headers:
        raise ValueError(
            "native demographic headers differ from reviewed shape"
        )
    native: list[dict[str, Any]] = []
    for cell in row.cells:
        properties = json.dumps(
            cell.native_properties,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        if len(properties.encode()) > MAX_PROPERTIES_BYTES:
            raise ValueError("native demographic properties exceed cell bound")
        native.append({
            "name": cell.name,
            "value": cell.value,
            "state": cell.state,
            "native_properties_json": properties,
        })
    benefit, benefit_status = _numeric(
        row.cells[7], count=False, workbook=source.source_format == "workbook"
    )
    services, services_status = _numeric(
        row.cells[6], count=True, workbook=source.source_format == "workbook"
    )
    return {
        **binding,
        "source_row_id": f"{binding['source_object_id']}:primary-row:{row.row_index}",
        "native_row_index": row.row_index,
        "native_cells": native,
        "benefit_native_name": source.headers[7],
        "benefit_decimal": benefit,
        "benefit_interpretation_state": "native_unresolved",
        "benefit_conversion_status": benefit_status,
        "services_count": services,
        "services_conversion_status": services_status,
        "age_native": row.cells[4].value,
        "age_lower_bound": None,
        "age_upper_bound": None,
        "age_suppression_relationship": "unresolved",
        "patient_rate_state": "unavailable",
    }


def iter_demographic_silver_batches(
    rows: Iterable[DemographicRow],
    source: DemographicSource,
    *,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Preserve every supplied primary-table row in bounded output batches."""
    if (
        type(rows_per_batch) is not int
        or not 1 <= rows_per_batch <= MAX_BATCH_ROWS
    ):
        raise ValueError("demographic batch size is outside its bound")
    source = DemographicSource.model_validate(source.model_dump())
    binding = {
        "dataset": source.dataset,
        "source_object_id": source.object_id,
        "source_measure_id": source.source_measure_id,
        "source_id": source.acquisition.source_id,
        "source_sha256": source.source_sha256,
        "source_revision": source.source_revision,
        "source_path": source.source_path,
        "source_format": source.source_format,
        "acquisition_id": source.acquisition.acquisition_id,
        "acquisition_sha256": source.acquisition.digest(),
        "b2_manifest_sha256": source.raw_manifest.manifest_sha256,
        "evidence_class": source.acquisition.evidence_class.value
        if source.acquisition.evidence_class
        else "unknown",
    }
    schema = demographic_silver_schema()
    buffer: list[dict[str, Any]] = []
    previous = 0
    buffered_bytes = 0
    minimum = 2 if source.source_format == "csv" else 4
    for observation in rows:
        row = DemographicRow.model_validate(observation.model_dump())
        if row.row_index <= previous or row.row_index < minimum:
            raise ValueError("native demographic row order or start differs")
        previous = row.row_index
        projected = _project(row, source, binding)
        encoded_bytes = len(
            json.dumps(projected, separators=(",", ":"), default=str).encode()
        )
        if encoded_bytes > MAX_BATCH_BYTES:
            raise ValueError("native demographic row exceeds byte bound")
        if buffer and buffered_bytes + encoded_bytes > MAX_BATCH_BYTES:
            yield pa.RecordBatch.from_pylist(buffer, schema=schema)
            buffer = []
            buffered_bytes = 0
        buffer.append(projected)
        buffered_bytes += encoded_bytes
        if len(buffer) == rows_per_batch:
            yield pa.RecordBatch.from_pylist(buffer, schema=schema)
            buffer = []
            buffered_bytes = 0
    if buffer:
        yield pa.RecordBatch.from_pylist(buffer, schema=schema)


def summarize_demographic_batches(
    batches: Iterable[pa.RecordBatch],
) -> dict[str, dict[str, Any]]:
    """Count rows and fields per object, including native Unknown-age rows.

    Counts describe source observations. No benefit totals or patient rates are
    derived; source objects are never pooled into one measure population.
    """
    counts: dict[str, Counter[str]] = {}
    age_groups: dict[str, Counter[tuple[str, str | None]]] = {}
    for batch in batches:
        for row in batch.to_pylist():
            counter = counts.setdefault(row["source_object_id"], Counter())
            counter["native_rows"] += 1
            counter["native_field_slots"] += len(row["native_cells"])
            counter["native_fields"] += sum(
                cell["state"] != "absent" for cell in row["native_cells"]
            )
            age = row["native_cells"][4]
            age_groups.setdefault(row["source_object_id"], Counter())[
                age["state"], age["value"]
            ] += 1
            counter["literal_unknown_age_rows"] += (
                age["state"] == "value" and age["value"] == "Unknown"
            )
            counter["benefit_" + row["benefit_conversion_status"]] += 1
            counter["services_" + row["services_conversion_status"]] += 1
    return {
        key: {
            **dict(sorted(value.items())),
            "native_age_groups": [
                {"state": state, "label": label, "rows": number}
                for (state, label), number in sorted(
                    age_groups[key].items(),
                    key=lambda item: (item[0][0], item[0][1] or ""),
                )
            ],
        }
        for key, value in sorted(counts.items())
    }


# Shared lossless conversion; callers retain their own dimension/header contracts.
convert_native_utilisation_number = _numeric
