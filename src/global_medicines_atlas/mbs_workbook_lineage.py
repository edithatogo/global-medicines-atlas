"""Value-free column lineage over existing receipt-bound workbook candidates.

Ordered digests bind all native and converted cell fields, not just values.
The report is rebuildable metadata, not authenticated source qualification.
Missing cells are not synthesized from the declared worksheet rectangle.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, model_validator

from .mbs_workbook_domain import LEGACY_SHEET_PROFILES, workbook_header_mapping
from .mbs_workbook_values import iter_workbook_value_batches
from .models import FrozenModel
from .receipts import SourceReceipt

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Count = Annotated[int, Field(strict=True, ge=0)]
MAX_COLUMNS = 4096
Status = Literal[
    "header",
    "unmapped",
    "missing_value",
    "null",
    "source_error",
    "preserved",
    "converted",
    "invalid",
    "unrepresentable",
    "blank",
    "unsupported_format",
    "unsupported_storage_type",
    "unsupported_serial_date",
]


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


class WorkbookFieldLineage(FrozenModel):
    """One native column, including header and unlabelled-cell occurrences."""

    model_config = ConfigDict(revalidate_instances="always")
    sheet_name: str
    sheet_path: str
    column: str = Field(pattern=r"^[A-Z]{1,3}$")
    native_header: str | None
    mapping_target: str
    mapping_field: str | None
    cell_count: Count
    header_count: Count
    formula_count: Count
    error_count: Count
    statuses: tuple[
        tuple[Status, Annotated[int, Field(strict=True, ge=1)]], ...
    ]
    lineage_sha256: Digest

    @model_validator(mode="after")
    def valid_mapping(self) -> WorkbookFieldLineage:
        profiles = {
            name: dict(headers) for name, _, headers in LEGACY_SHEET_PROFILES
        }
        if self.sheet_name not in profiles:
            raise ValueError("unknown workbook lineage sheet")
        if self.native_header != profiles[self.sheet_name].get(self.column):
            raise ValueError("workbook lineage header differs")
        if (self.mapping_target, self.mapping_field) != workbook_header_mapping(
            self.native_header
        ):
            raise ValueError("workbook lineage mapping differs")
        if self.cell_count < 1 or any(
            count > self.cell_count
            for count in (
                self.header_count,
                self.formula_count,
                self.error_count,
            )
        ):
            raise ValueError("workbook lineage cell denominator differs")
        if tuple(status for status, _ in self.statuses) != tuple(
            sorted({status for status, _ in self.statuses})
        ):
            raise ValueError("workbook lineage status denominator differs")
        if (
            sum(count for _, count in self.statuses) != self.cell_count
            or dict(self.statuses).get("header", 0) != self.header_count
        ):
            raise ValueError("workbook lineage status counts differ")
        return self


class WorkbookSheetLineage(FrozenModel):
    """Native sheet identity and observed, not rectangular, denominator."""

    model_config = ConfigDict(revalidate_instances="always")
    name: str
    path: str
    relationship_id: str
    dimension: str
    cell_count: Count


class WorkbookFieldLineageReport(FrozenModel):
    """Complete candidate column lineage for the existing P7 header profile."""

    model_config = ConfigDict(revalidate_instances="always")
    schema_id: Literal["global-medicines-atlas.mbs-workbook-field-lineage"] = (
        "global-medicines-atlas.mbs-workbook-field-lineage"
    )
    schema_version: Literal[1] = 1
    qualification: Literal["candidate_only"] = "candidate_only"
    source_id: Literal["au-mbs-p7-legacy-workbook"] = (
        "au-mbs-p7-legacy-workbook"
    )
    dimension: Literal["service_benefit"] = "service_benefit"
    absence_interpretation: Literal["unknown"] = "unknown"
    mapping_profile: Literal["mbs-p7-2024-07-headers-v1"] = (
        "mbs-p7-2024-07-headers-v1"
    )
    source_sha256: Digest
    receipt_sha256: Digest
    source_revision: str
    date_profile: Literal["iso", "mbs-dmy"] | None = None
    cell_count: Count
    sheets: tuple[WorkbookSheetLineage, ...] = Field(min_length=4, max_length=4)
    fields: tuple[WorkbookFieldLineage, ...] = Field(max_length=MAX_COLUMNS)
    report_sha256: Digest

    @model_validator(mode="after")
    def complete(self) -> WorkbookFieldLineageReport:
        if tuple(
            (sheet.name, sheet.dimension) for sheet in self.sheets
        ) != tuple(
            (name, dimension) for name, dimension, _ in LEGACY_SHEET_PROFILES
        ):
            raise ValueError("workbook lineage sheet denominator differs")
        if len({sheet.path for sheet in self.sheets}) != len(self.sheets):
            raise ValueError("workbook lineage sheet paths differ")
        keys = tuple((field.sheet_name, field.column) for field in self.fields)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("workbook lineage columns duplicated or unordered")
        for sheet in self.sheets:
            fields = tuple(
                field for field in self.fields if field.sheet_name == sheet.name
            )
            if sum(
                field.cell_count for field in fields
            ) != sheet.cell_count or any(
                field.sheet_path != sheet.path for field in fields
            ):
                raise ValueError("workbook lineage sheet cells differ")
            headers = dict(
                next(
                    headers
                    for name, _, headers in LEGACY_SHEET_PROFILES
                    if name == sheet.name
                )
            )
            if {
                field.column for field in fields if field.header_count == 1
            } != set(headers) or any(
                field.header_count > 1 for field in fields
            ):
                raise ValueError("workbook lineage header denominator differs")
        if sum(sheet.cell_count for sheet in self.sheets) != self.cell_count:
            raise ValueError("workbook lineage total differs")
        if (
            self.report_sha256
            != hashlib.sha256(
                _canonical(self.model_dump(exclude={"report_sha256"}))
            ).hexdigest()
        ):
            raise ValueError("workbook lineage report digest differs")
        return self


def build_workbook_field_lineage(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    date_profile: Literal["iso", "mbs-dmy"] | None = None,
    rows_per_batch: int = 1024,
    max_columns: int = 1024,
) -> WorkbookFieldLineageReport:
    """Hash bounded native/value batches while retaining only column counters.

    Input parsing retains the existing bounded workbook parser. A separate
    column ceiling bounds the report accumulator; no source bytes are stored.
    Date profiles are explicit caller choices, never qualified by this report.
    """
    if type(max_columns) is not int or not 1 <= max_columns <= MAX_COLUMNS:
        raise ValueError("workbook lineage column limit must be 1 to 4096")
    receipt = SourceReceipt.model_validate(receipt.model_dump())
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    sheet_manifest: list[dict[str, Any]] | None = None
    for batch in iter_workbook_value_batches(
        payload,
        receipt,
        date_format=date_profile,
        rows_per_batch=rows_per_batch,
    ):
        manifest = json.loads((batch.schema.metadata or {})[b"workbook_sheets"])
        if sheet_manifest is None:
            sheet_manifest = manifest
        elif manifest != sheet_manifest:
            raise ValueError("workbook lineage sheet metadata drift")
        for row in batch.to_pylist():
            column = row["header_coordinate"][:-1]
            key = (row["sheet_name"], column)
            if key not in groups:
                if len(groups) >= max_columns:
                    raise ValueError("workbook lineage column limit exceeded")
                target, field = workbook_header_mapping(row["native_header"])
                groups[key] = {
                    "sheet_name": key[0],
                    "sheet_path": row["sheet_path"],
                    "column": column,
                    "native_header": row["native_header"],
                    "mapping_target": target,
                    "mapping_field": field,
                    "cell_count": 0,
                    "header_count": 0,
                    "formula_count": 0,
                    "error_count": 0,
                    "statuses": Counter(),
                    "digest": hashlib.sha256(),
                }
            group = groups[key]
            group["cell_count"] += 1
            group["header_count"] += row["row_kind"] == "header"
            group["formula_count"] += row["value_origin"] == "formula_cache"
            group["error_count"] += row["error_code"] is not None
            group["statuses"][row["domain_status"]] += 1
            group["digest"].update(_canonical(row) + b"\n")
    if sheet_manifest is None:
        raise ValueError("workbook lineage producer emitted no manifest")
    fields: list[WorkbookFieldLineage] = []
    for key in sorted(groups):
        group = groups[key]
        digest = group.pop("digest")
        group["statuses"] = tuple(sorted(group["statuses"].items()))
        fields.append(
            WorkbookFieldLineage(**group, lineage_sha256=digest.hexdigest())
        )
    document: dict[str, Any] = {
        "source_sha256": receipt.payload.sha256,
        "receipt_sha256": receipt.digest(),
        "source_revision": receipt.source.catalog_version,
        "date_profile": date_profile,
        "cell_count": sum(field.cell_count for field in fields),
        "sheets": tuple(
            WorkbookSheetLineage(**{
                key: sheet[key]
                for key in (
                    "name",
                    "path",
                    "relationship_id",
                    "dimension",
                    "cell_count",
                )
            })
            for sheet in sheet_manifest
        ),
        "fields": tuple(fields),
    }
    provisional = WorkbookFieldLineageReport.model_construct(
        **document, report_sha256="0" * 64
    )
    return WorkbookFieldLineageReport.model_validate({
        **provisional.model_dump(),
        "report_sha256": hashlib.sha256(
            _canonical(provisional.model_dump(exclude={"report_sha256"}))
        ).hexdigest(),
    })
