"""Group workbook Silver candidates over its independently observed native header.

Every primary row remains a native row, including repeated headers or section
rows. Converted service values establish no patient denominator or row grain.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from hashlib import sha256
from pathlib import Path
from typing import Any, ClassVar, cast

import pyarrow as pa
from pydantic import ConfigDict, model_validator

from .bronze_raw_evidence import RawEvidenceManifest
from .mbs_demographic_extraction import Record, iter_native_workbook_records
from .mbs_demographic_silver import (
    MAX_BATCH_BYTES,
    MAX_BATCH_ROWS,
    MAX_PROPERTIES_BYTES,
    DemographicRow,
    DemographicSource,
    convert_native_utilisation_number,
    demographic_silver_schema,
)
from .mbs_group_silver import group_silver_schema
from .mbs_group_workbook_layout import load_reference
from .receipts import AcquisitionEvent

GROUP_WORKBOOK_HEADERS = (
    "Year",
    "Month",
    "Group",
    "Sub_Group",
    "Item_Number",
    "State",
    "Services",
    "Benefits ($)",
)
LAYOUT = (
    "quality/qualifications/mbs-group-workbook-layout-20261022-39651063652.json"
)
LAYOUT_SHA256 = (
    "3ed500ce30de26a372326fea1645d15e25911dbd60c15faae121430ce3dfc0c3"
)
DIMENSIONS = (
    "year_native",
    "month_native",
    "group_native",
    "subgroup_native",
    "item_number_native",
    "state_native",
)
HEADER_ROW = 3
FIRST_PRIMARY_ROW = 4


class GroupWorkbookSource(DemographicSource):
    """Receipt-bound group-family workbook; no CSV or age-field substitution."""

    SOURCE_FAMILY: ClassVar[str] = "au-data-gov-mbs-group"
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [{"properties": {"source_format": {"const": "workbook"}}}]
        }
    )

    @model_validator(mode="after")
    def require_workbook(self) -> GroupWorkbookSource:
        if self.source_format != "workbook":
            raise ValueError("group source requires workbook format")
        return self

    @property
    def headers(self) -> tuple[str, ...]:
        return GROUP_WORKBOOK_HEADERS


def load_group_workbook_source(root: Path) -> GroupWorkbookSource:
    """Bind exact layout readback to frozen identity and original B1/B2."""
    reference = load_reference(root)
    payload = (root / LAYOUT).read_bytes()
    if sha256(payload).hexdigest() != LAYOUT_SHA256:
        raise ValueError("group workbook layout receipt digest differs")
    layout = json.loads(payload)
    observed = layout["result"]["sheets"][0]["header_candidates"]
    headers = tuple(
        cell["value"] for cell in observed if cell["row"] == HEADER_ROW
    )
    if layout["source"] != reference or headers != GROUP_WORKBOOK_HEADERS:
        raise ValueError("group workbook layout source or header differs")
    family = GroupWorkbookSource.SOURCE_FAMILY
    acquisition = reference["acquisition_id"]
    return GroupWorkbookSource(
        acquisition=AcquisitionEvent.model_validate_json(
            (
                root
                / f"quality/bronze/imported-acquisitions/{family}/{acquisition}.json"
            ).read_bytes()
        ),
        raw_manifest=RawEvidenceManifest.model_validate_json(
            (
                root
                / f"quality/bronze/raw-evidence/{family}/{acquisition}/manifest.json"
            ).read_bytes()
        ),
        dataset=reference["dataset"],
        source_format="workbook",
        source_revision=reference["revision"],
        source_path=reference["path"],
    )


def group_workbook_schema() -> pa.Schema:
    """Keep group dimensions, physical native cells and explicit uncertainty."""
    original = group_silver_schema()
    fields: list[pa.Field[pa.DataType]] = [
        pa.field("month_native", pa.string())
        if field.name == "processing_month_native"
        else field
        for field in cast("Iterable[pa.Field[pa.DataType]]", original)
        if field.name
        not in {"native_record_index", "physical_line_end", "native_cells"}
    ]
    native_field = cast(
        "pa.Field[pa.DataType]",
        demographic_silver_schema().field("native_cells"),  # pyright: ignore[reportUnknownMemberType] -- Arrow field stub is unspecialised
    )
    fields.extend([
        pa.field("native_row_index", pa.int64(), nullable=False),
        native_field,
    ])
    metadata = cast(
        "dict[str | bytes, str | bytes]", dict(original.metadata or {})
    )
    metadata.update({
        b"schema_name": b"global-medicines-atlas.mbs-group-workbook-silver.native-rows",
        b"header_profile_sha256": LAYOUT_SHA256.encode(),
        b"primary_row_kind": b"uninterpreted_native_rows",
        b"period_alignment": b"unqualified",
        b"row_grain": b"unqualified",
        b"header_record": b"separate_ancillary_required",
        b"age_dimension": b"not_in_primary_header",
    })
    return pa.schema(fields, metadata=metadata)


def iter_group_workbook_records(
    payload: bytes, source: GroupWorkbookSource
) -> Iterator[Record]:
    """Exhaust all source members/cells under the exact group workbook profile."""
    source = GroupWorkbookSource.model_validate(source.model_dump())
    yield from iter_native_workbook_records(payload, source)


def _binding(source: GroupWorkbookSource) -> dict[str, str]:
    return {
        "dataset": source.dataset,
        "source_format": "workbook",
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
    }


def _project(
    row: DemographicRow, source: GroupWorkbookSource, binding: dict[str, str]
) -> dict[str, Any]:
    if tuple(cell.name for cell in row.cells) != source.headers:
        raise ValueError("group workbook native header profile differs")
    native: list[dict[str, Any]] = []
    for cell in row.cells:
        properties = json.dumps(cell.native_properties, sort_keys=True)
        if len(properties.encode()) > MAX_PROPERTIES_BYTES:
            raise ValueError(
                "group workbook native property byte bound exceeded"
            )
        native.append({
            "name": cell.name,
            "state": cell.state,
            "value": cell.value,
            "native_properties_json": properties,
        })
    services, services_status = convert_native_utilisation_number(
        row.cells[6], count=True, workbook=True
    )
    benefit, benefit_status = convert_native_utilisation_number(
        row.cells[7], count=False, workbook=True
    )
    return {
        **binding,
        "source_row_id": f"{source.object_id}:primary-row:{row.row_index}",
        "record_kind": "native_primary_row",
        "native_row_index": row.row_index,
        "native_cells": native,
        "services_count": services,
        "services_conversion_status": services_status,
        "benefit_decimal": benefit,
        "benefit_conversion_status": benefit_status,
        "benefit_interpretation_state": "native_unresolved",
        "patient_rate_state": "unavailable",
        **{
            name: row.cells[index].value
            for index, name in enumerate(DIMENSIONS)
        },
    }


def iter_group_workbook_batches(
    rows: Iterable[DemographicRow],
    source: GroupWorkbookSource,
    *,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Project supplied physical rows; complete-source extraction is separate."""
    if (
        type(rows_per_batch) is not int
        or not 1 <= rows_per_batch <= MAX_BATCH_ROWS
    ):
        raise ValueError("group workbook batch row bound differs")
    source = GroupWorkbookSource.model_validate(source.model_dump())
    binding = _binding(source)
    buffer: list[dict[str, Any]] = []
    previous = buffered_bytes = 0
    for original in rows:
        row = DemographicRow.model_validate(original.model_dump())
        if row.row_index < FIRST_PRIMARY_ROW or row.row_index <= previous:
            raise ValueError("group workbook source row order differs")
        previous = row.row_index
        projected = _project(row, source, binding)
        size = len(
            json.dumps(projected, default=str, separators=(",", ":")).encode()
        )
        if size > MAX_BATCH_BYTES:
            raise ValueError("group workbook row byte bound exceeded")
        if buffer and buffered_bytes + size > MAX_BATCH_BYTES:
            yield pa.RecordBatch.from_pylist(
                buffer, schema=group_workbook_schema()
            )
            buffer, buffered_bytes = [], 0
        buffer.append(projected)
        buffered_bytes += size
        if len(buffer) == rows_per_batch:
            yield pa.RecordBatch.from_pylist(
                buffer, schema=group_workbook_schema()
            )
            buffer, buffered_bytes = [], 0
    if buffer:
        yield pa.RecordBatch.from_pylist(buffer, schema=group_workbook_schema())
