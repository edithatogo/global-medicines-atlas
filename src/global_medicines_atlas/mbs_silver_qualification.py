"""Deterministic denominator evidence for candidate MBS Silver tables.

The report qualifies only a receipt-bound projection. It does not establish a
real-source schema era, a public v4 object, or permission to promote data.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Literal

from pydantic import Field, model_validator

from .australian_source_contracts import TargetTable, mbs_field_contracts
from .mbs_silver import iter_mbs_silver_batches
from .models import FrozenModel
from .receipts import SourceReceipt

_TABLES: tuple[TargetTable, ...] = (
    "services",
    "hierarchy",
    "descriptions",
    "fees",
    "benefits",
    "caps",
)
_QUALITY_STATUSES = frozenset({
    "blank",
    "invalid",
    "unrepresentable",
    "unsupported_format",
})
Blocker = Literal[
    "public_v4_identity_unverified",
    "real_source_era_unqualified",
    "quality_findings_present",
]


class MbsSilverTableQualification(FrozenModel):
    """Exact row, field, state, conversion, and lineage denominator."""

    table: TargetTable
    row_count: int = Field(strict=True, ge=1)
    field_count: int = Field(strict=True, ge=1)
    field_occurrence_count: int = Field(strict=True, ge=1)
    lineage_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class MbsSilverQualityCount(FrozenModel):
    """Count one source-state or conversion outcome without source values."""

    status: str = Field(min_length=1)
    count: int = Field(strict=True, ge=1)


class MbsSilverQualification(FrozenModel):
    """Aggregate candidate qualification over all six MBS Silver tables."""

    schema_version: Literal[1] = 1
    source_id: Literal["au-mbs"] = "au-mbs"
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_era: str = Field(min_length=1)
    date_format: Literal["iso", "mbs-dmy"] | None
    source_record_count: int = Field(strict=True, ge=1)
    tables: tuple[MbsSilverTableQualification, ...]
    quality: tuple[MbsSilverQualityCount, ...]
    promotion_status: Literal["candidate_only"] = "candidate_only"
    blockers: tuple[Blocker, ...]
    qualification_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @property
    def field_count(self) -> int:
        """Return the complete distinct native-field denominator."""
        return sum(table.field_count for table in self.tables)

    @property
    def field_occurrence_count(self) -> int:
        """Return expected native slots across all source rows."""
        return sum(table.field_occurrence_count for table in self.tables)

    @property
    def quality_counts(self) -> dict[str, int]:
        """Return outcome counts as a read-only serialized projection."""
        return {item.status: item.count for item in self.quality}

    @model_validator(mode="after")
    def denominators_and_digest_match(self) -> MbsSilverQualification:
        """Reject relabelled, incomplete, or promoted serialized reports."""
        if tuple(table.table for table in self.tables) != _TABLES:
            raise ValueError("MBS Silver table denominator differs")
        if any(
            table.row_count != self.source_record_count
            or table.field_occurrence_count
            != table.row_count * table.field_count
            for table in self.tables
        ):
            raise ValueError("MBS Silver row denominator differs")
        if self.field_count != len(mbs_field_contracts()):
            raise ValueError("MBS Silver field denominator differs")
        if tuple(item.status for item in self.quality) != tuple(
            sorted({item.status for item in self.quality})
        ):
            raise ValueError("quality outcomes must be sorted and unique")
        expected_blockers = (
            "public_v4_identity_unverified",
            "real_source_era_unqualified",
            *(
                ("quality_findings_present",)
                if any(
                    item.status in _QUALITY_STATUSES for item in self.quality
                )
                else ()
            ),
        )
        if self.blockers != expected_blockers:
            raise ValueError("candidate blockers differ from evidence")
        if self.qualification_sha256 != _report_digest(self):
            raise ValueError("qualification digest differs from report")
        return self


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()


def _report_digest(report: MbsSilverQualification) -> str:
    values = report.model_dump(
        exclude={"qualification_sha256"}, exclude_computed_fields=True
    )
    return hashlib.sha256(_canonical(values)).hexdigest()


def qualify_mbs_silver(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    date_format: Literal["iso", "mbs-dmy"] | None = None,
    rows_per_batch: int = 1024,
) -> MbsSilverQualification:
    """Account for every candidate table row and mapped native field.

    Values contribute to per-table lineage digests but are not copied into the
    aggregate report. The projection remains candidate-only until independent
    real-source-era and public-v4 evidence exists.
    """
    receipt = SourceReceipt.model_validate(receipt.model_dump())
    table_reports: list[MbsSilverTableQualification] = []
    outcomes: Counter[str] = Counter()
    source_record_count: int | None = None
    for table in _TABLES:
        field_names = tuple(
            field.native_name
            for field in mbs_field_contracts()
            if field.target_table == table
        )
        digest = hashlib.sha256()
        row_count = 0
        for batch in iter_mbs_silver_batches(
            payload,
            receipt,
            table=table,
            date_format=date_format,
            rows_per_batch=rows_per_batch,
        ):
            for row in batch.to_pylist():
                row_count += 1
                for name in field_names:
                    value = row[name]
                    outcomes[value["conversion_status"]] += 1
                    digest.update(
                        _canonical({
                            "source_record_id": row["source_record_id"],
                            "source_ordinal": row["source_ordinal"],
                            "field": name,
                            **value,
                        })
                    )
                    digest.update(b"\n")
        if source_record_count is None:
            source_record_count = row_count
        elif row_count != source_record_count:
            raise ValueError("MBS Silver table row denominators differ")
        table_reports.append(
            MbsSilverTableQualification(
                table=table,
                row_count=row_count,
                field_count=len(field_names),
                field_occurrence_count=row_count * len(field_names),
                lineage_sha256=digest.hexdigest(),
            )
        )
    if source_record_count is None or source_record_count == 0:
        raise ValueError("MBS Silver source denominator is empty")
    quality = tuple(
        MbsSilverQualityCount(status=status, count=count)
        for status, count in sorted(outcomes.items())
        if count
    )
    blockers: tuple[Blocker, ...] = (
        "public_v4_identity_unverified",
        "real_source_era_unqualified",
        *(
            ("quality_findings_present",)
            if any(item.status in _QUALITY_STATUSES for item in quality)
            else ()
        ),
    )
    provisional = MbsSilverQualification.model_construct(
        source_sha256=receipt.payload.sha256,
        receipt_sha256=receipt.digest(),
        schema_era=receipt.source.catalog_version,
        date_format=date_format,
        source_record_count=source_record_count,
        tables=tuple(table_reports),
        quality=quality,
        blockers=blockers,
        qualification_sha256="0" * 64,
    )
    return MbsSilverQualification(
        source_sha256=receipt.payload.sha256,
        receipt_sha256=receipt.digest(),
        schema_era=receipt.source.catalog_version,
        date_format=date_format,
        source_record_count=source_record_count,
        tables=tuple(table_reports),
        quality=quality,
        blockers=blockers,
        qualification_sha256=_report_digest(provisional),
    )
