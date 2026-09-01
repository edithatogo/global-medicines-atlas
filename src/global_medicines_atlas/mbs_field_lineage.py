"""Field-addressed lineage for receipt-bound MBS Silver candidates.

The report maps every native XML field to its typed Silver destination and
accounts for every source occurrence without copying source values. It is not
schema-era qualification, promotion evidence, or publication authority.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Literal, cast

from pydantic import Field, model_validator

from .australian_source_contracts import (
    TargetTable,
    ValueType,
    mbs_field_contracts,
)
from .mbs_silver import iter_mbs_silver_batches
from .models import FrozenModel
from .receipts import SourceReceipt


class MbsNativeStateCount(FrozenModel):
    """One non-value-bearing native-state denominator."""

    outcome: Literal["missing_field", "null", "value"]
    count: int = Field(strict=True, ge=1)


class MbsConversionStatusCount(FrozenModel):
    """One closed-vocabulary typed-conversion denominator."""

    outcome: Literal[
        "missing_field",
        "null",
        "blank",
        "preserved",
        "converted",
        "invalid",
        "unrepresentable",
        "unsupported_format",
    ]
    count: int = Field(strict=True, ge=1)


class MbsSilverFieldLineage(FrozenModel):
    """One explicit native-path to Silver-field mapping and denominator."""

    native_name: str = Field(min_length=1)
    source_path: str = Field(pattern=r"^/MBS_XML/Data/[^/]+$")
    target_table: TargetTable
    target_field: str = Field(min_length=1)
    value_type: ValueType
    mapping_status: Literal["source_native"] = "source_native"
    source_value_overwritten: Literal[False] = False
    occurrence_count: int = Field(strict=True, ge=1)
    native_states: tuple[MbsNativeStateCount, ...]
    conversion_statuses: tuple[MbsConversionStatusCount, ...]
    lineage_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def mapping_and_denominators_match(self) -> MbsSilverFieldLineage:
        contract = next(
            (
                item
                for item in mbs_field_contracts()
                if item.native_name == self.native_name
            ),
            None,
        )
        if contract is None or (
            self.source_path,
            self.target_table,
            self.target_field,
            self.value_type,
        ) != (
            f"/MBS_XML/Data/{self.native_name}",
            contract.target_table,
            contract.native_name,
            contract.value_type,
        ):
            raise ValueError("MBS field lineage mapping differs from contract")
        for values in (self.native_states, self.conversion_statuses):
            if tuple(item.outcome for item in values) != tuple(
                sorted({item.outcome for item in values})
            ):
                raise ValueError("MBS field lineage outcomes differ")
            if sum(item.count for item in values) != self.occurrence_count:
                raise ValueError("MBS field lineage denominator differs")
        return self


class MbsSilverFieldLineageReport(FrozenModel):
    """Complete 40-field XML lineage inventory for one exact candidate."""

    schema_id: Literal["global-medicines-atlas.mbs-field-lineage"] = (
        "global-medicines-atlas.mbs-field-lineage"
    )
    schema_version: Literal[1] = 1
    qualification: Literal["candidate_only"] = "candidate_only"
    source_id: Literal["au-mbs"] = "au-mbs"
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_era: str = Field(min_length=1)
    date_format: Literal["iso", "mbs-dmy"] | None
    source_record_count: int = Field(strict=True, ge=1)
    fields: tuple[MbsSilverFieldLineage, ...]
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def complete_and_content_bound(self) -> MbsSilverFieldLineageReport:
        expected = tuple(item.native_name for item in mbs_field_contracts())
        if tuple(item.native_name for item in self.fields) != expected:
            raise ValueError("MBS field lineage denominator differs")
        if any(
            item.occurrence_count != self.source_record_count
            for item in self.fields
        ):
            raise ValueError("MBS field lineage row denominator differs")
        if self.report_sha256 != _report_digest(self):
            raise ValueError("MBS field lineage report digest differs")
        return self


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()


def _report_digest(report: MbsSilverFieldLineageReport) -> str:
    return hashlib.sha256(
        _canonical(
            report.model_dump(
                exclude={"report_sha256"}, exclude_computed_fields=True
            )
        )
    ).hexdigest()


def build_mbs_silver_field_lineage(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    date_format: Literal["iso", "mbs-dmy"] | None = None,
    rows_per_batch: int = 1024,
) -> MbsSilverFieldLineageReport:
    """Build deterministic field-addressed lineage without source values."""
    receipt = SourceReceipt.model_validate(receipt.model_dump())
    contracts = mbs_field_contracts()
    states = {item.native_name: Counter[str]() for item in contracts}
    conversions = {item.native_name: Counter[str]() for item in contracts}
    digests = {item.native_name: hashlib.sha256() for item in contracts}
    counts = {item.native_name: 0 for item in contracts}
    record_count: int | None = None
    tables: tuple[TargetTable, ...] = tuple(
        dict.fromkeys(item.target_table for item in contracts)
    )
    for table in tables:
        table_contracts = tuple(
            item for item in contracts if item.target_table == table
        )
        table_count = 0
        for batch in iter_mbs_silver_batches(
            payload,
            receipt,
            table=table,
            date_format=date_format,
            rows_per_batch=rows_per_batch,
        ):
            for row in batch.to_pylist():
                table_count += 1
                for contract in table_contracts:
                    name = contract.native_name
                    counts[name] += 1
                    value = row[name]
                    states[name][value["native_state"]] += 1
                    conversions[name][value["conversion_status"]] += 1
                    digests[name].update(
                        _canonical({
                            "source_record_id": row["source_record_id"],
                            "source_ordinal": row["source_ordinal"],
                            "native_name": name,
                            **value,
                        })
                    )
                    digests[name].update(b"\n")
        if table_count == 0:
            raise ValueError("MBS field lineage source denominator is empty")
        if record_count is None:
            record_count = table_count
        elif table_count != record_count:
            raise ValueError("MBS field lineage row denominators differ")
    output: list[MbsSilverFieldLineage] = []
    for contract in contracts:
        name = contract.native_name
        output.append(
            MbsSilverFieldLineage(
                native_name=name,
                source_path=f"/MBS_XML/Data/{name}",
                target_table=contract.target_table,
                target_field=name,
                value_type=contract.value_type,
                occurrence_count=counts[name],
                native_states=tuple(
                    MbsNativeStateCount.model_validate({
                        "outcome": outcome,
                        "count": value,
                    })
                    for outcome, value in sorted(states[name].items())
                ),
                conversion_statuses=tuple(
                    MbsConversionStatusCount.model_validate({
                        "outcome": outcome,
                        "count": value,
                    })
                    for outcome, value in sorted(conversions[name].items())
                ),
                lineage_sha256=digests[name].hexdigest(),
            )
        )
    final_record_count = cast("int", record_count)
    provisional = MbsSilverFieldLineageReport.model_construct(
        source_sha256=receipt.payload.sha256,
        receipt_sha256=receipt.digest(),
        schema_era=receipt.source.catalog_version,
        date_format=date_format,
        source_record_count=final_record_count,
        fields=tuple(output),
        report_sha256="0" * 64,
    )
    return MbsSilverFieldLineageReport(
        source_sha256=receipt.payload.sha256,
        receipt_sha256=receipt.digest(),
        schema_era=receipt.source.catalog_version,
        date_format=date_format,
        source_record_count=final_record_count,
        fields=tuple(output),
        report_sha256=_report_digest(provisional),
    )
