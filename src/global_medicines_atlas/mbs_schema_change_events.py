"""Explicit schema-era mappings and observed MBS change-event candidates.

The producer compares complete, receipt-bound native cohorts only after an
explicit mapping covers every field in the selected Silver table. Events
preserve source-native values and distinguish observation from status: absence
never means addition, cessation, or supersession. No acquisition, promotion,
or publication occurs here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from .australian_source_contracts import TargetTable, mbs_field_contracts
from .historical_comparison import MAX_DIFFERENCES, NativeField, NativeSnapshot
from .mbs_historical_comparison import MbsComparisonCohort
from .models import FrozenModel


class MbsSchemaFieldMapping(FrozenModel):
    """One explicit source-native field mapping between declared eras."""

    historical_native_name: str = Field(min_length=1)
    current_native_name: str = Field(min_length=1)
    silver_target_field: str = Field(min_length=1)
    mapping_method: Literal["source_native_exact"] = "source_native_exact"
    source_value_overwritten: Literal[False] = False


class MbsSchemaEraMapping(FrozenModel):
    """Complete table mapping between two caller-declared MBS XML eras."""

    schema_id: Literal["global-medicines-atlas.mbs-schema-era-mapping"] = (
        "global-medicines-atlas.mbs-schema-era-mapping"
    )
    schema_version: Literal[1] = 1
    source_id: Literal["au-mbs"] = "au-mbs"
    table: TargetTable
    historical_schema_era: str = Field(min_length=1)
    current_schema_era: str = Field(min_length=1)
    identity_profile: Literal["mbs-item-subitem-literal-v1"] = (
        "mbs-item-subitem-literal-v1"
    )
    fields: tuple[MbsSchemaFieldMapping, ...]
    mapping_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def complete_and_content_bound(self) -> MbsSchemaEraMapping:
        for era in (self.historical_schema_era, self.current_schema_era):
            if not era.strip() or era != era.strip():
                raise ValueError("MBS schema era must be nonblank and unpadded")
        if self.historical_schema_era == self.current_schema_era:
            raise ValueError("MBS schema-era mapping requires distinct eras")
        names = tuple(
            item.native_name
            for item in mbs_field_contracts()
            if item.target_table == self.table
        )
        targets = tuple(item.silver_target_field for item in self.fields)
        historical_names = tuple(
            item.historical_native_name for item in self.fields
        )
        current_names = tuple(item.current_native_name for item in self.fields)
        if not names or targets != names:
            raise ValueError("MBS schema-era field mapping differs")
        if any(
            not value.strip() or value != value.strip()
            for value in (*historical_names, *current_names)
        ):
            raise ValueError("MBS schema-era native field name is invalid")
        if len(set(historical_names)) != len(historical_names) or len(
            set(current_names)
        ) != len(current_names):
            raise ValueError("MBS schema-era native field mapping is ambiguous")
        if self.mapping_sha256 != _mapping_digest(self):
            raise ValueError("MBS schema-era mapping digest differs")
        return self


class MbsObservedChangeEvent(FrozenModel):
    """Literal before/after observation, never inferred programme status."""

    model_config = ConfigDict(revalidate_instances="always")
    event_id: str = Field(pattern=r"^mbs-event:[0-9a-f]{64}$")
    native_id: str = Field(min_length=1)
    silver_target_field: str | None
    kind: Literal[
        "field_changed",
        "unchanged",
        "observed_only_historical",
        "observed_only_current",
    ]
    historical_occurrence: str | None
    current_occurrence: str | None
    historical: NativeField | None
    current: NativeField | None


class MbsSchemaChangeReport(FrozenModel):
    """Deterministic event evidence over complete explicitly mapped cohorts."""

    model_config = ConfigDict(revalidate_instances="always")
    schema_id: Literal["global-medicines-atlas.mbs-schema-change-report"] = (
        "global-medicines-atlas.mbs-schema-change-report"
    )
    schema_version: Literal[1] = 1
    qualification: Literal["observed_change_candidate"] = (
        "observed_change_candidate"
    )
    absence_interpretation: Literal["unknown"] = "unknown"
    historical: MbsComparisonCohort
    current: MbsComparisonCohort
    mapping: MbsSchemaEraMapping
    events: tuple[MbsObservedChangeEvent, ...] = Field(
        max_length=MAX_DIFFERENCES
    )
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def inputs_events_and_digest_match(self) -> MbsSchemaChangeReport:
        _validate_inputs(
            self.historical.snapshot, self.current.snapshot, self.mapping
        )
        if self.events != _events(
            self.historical.snapshot, self.current.snapshot, self.mapping
        ):
            raise ValueError("MBS schema change events differ from inputs")
        if self.report_sha256 != _report_digest(self):
            raise ValueError("MBS schema change report digest differs")
        return self


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()


def _mapping_digest(mapping: MbsSchemaEraMapping) -> str:
    return hashlib.sha256(
        _canonical(mapping.model_dump(exclude={"mapping_sha256"}))
    ).hexdigest()


def _report_digest(report: MbsSchemaChangeReport) -> str:
    return hashlib.sha256(
        _canonical(
            report.model_dump(
                exclude={"report_sha256"}, exclude_computed_fields=True
            )
        )
    ).hexdigest()


def declare_mbs_xml_schema_era_mapping(
    *,
    table: TargetTable,
    historical_schema_era: str,
    current_schema_era: str,
    fields: tuple[MbsSchemaFieldMapping, ...] | None = None,
) -> MbsSchemaEraMapping:
    """Declare a complete explicit XML mapping without qualifying either era."""
    if fields is None:
        fields = tuple(
            MbsSchemaFieldMapping(
                historical_native_name=item.native_name,
                current_native_name=item.native_name,
                silver_target_field=item.native_name,
            )
            for item in mbs_field_contracts()
            if item.target_table == table
        )
    provisional = MbsSchemaEraMapping.model_construct(
        table=table,
        historical_schema_era=historical_schema_era,
        current_schema_era=current_schema_era,
        fields=fields,
        mapping_sha256="0" * 64,
    )
    return MbsSchemaEraMapping(
        table=table,
        historical_schema_era=historical_schema_era,
        current_schema_era=current_schema_era,
        fields=fields,
        mapping_sha256=_mapping_digest(provisional),
    )


def _validate_inputs(
    historical: NativeSnapshot,
    current: NativeSnapshot,
    mapping: MbsSchemaEraMapping,
) -> None:
    for snapshot in (historical, current):
        NativeSnapshot.model_validate(snapshot.model_dump())
        if not snapshot.complete or snapshot.declared_rows != len(
            snapshot.rows
        ):
            raise ValueError("MBS schema comparison requires complete cohorts")
        if len({row.native_id for row in snapshot.rows}) != len(snapshot.rows):
            raise ValueError("MBS schema comparison identity is ambiguous")
    invariant = (
        "source_id",
        "table",
        "dimension",
        "identity_profile",
        "scope_id",
    )
    if any(
        getattr(historical, name) != getattr(current, name)
        for name in invariant
    ) or (
        historical.source_id,
        historical.table,
        historical.dimension,
        historical.identity_profile,
    ) != (
        mapping.source_id,
        mapping.table,
        "service_benefit",
        mapping.identity_profile,
    ):
        raise ValueError("MBS schema comparison profile differs")
    if (
        historical.schema_era,
        current.schema_era,
    ) != (
        mapping.historical_schema_era,
        mapping.current_schema_era,
    ):
        raise ValueError("MBS schema comparison eras differ from mapping")
    if (historical.cohort, current.cohort) not in {
        ("synthetic", "synthetic"),
        ("legacy", "current"),
        ("historical", "current"),
    }:
        raise ValueError("MBS schema comparison cohort roles differ")


def _event(
    values: dict[str, object], comparison_identity: Mapping[str, object]
) -> MbsObservedChangeEvent:
    canonical_values = {
        key: value.model_dump() if isinstance(value, NativeField) else value
        for key, value in values.items()
    }
    event_id = (
        "mbs-event:"
        + hashlib.sha256(
            _canonical({
                "comparison": comparison_identity,
                "event": canonical_values,
            })
        ).hexdigest()
    )
    return MbsObservedChangeEvent.model_validate({
        "event_id": event_id,
        **canonical_values,
    })


def _events(
    historical: NativeSnapshot,
    current: NativeSnapshot,
    mapping: MbsSchemaEraMapping,
) -> tuple[MbsObservedChangeEvent, ...]:
    before = {row.native_id: row for row in historical.rows}
    after = {row.native_id: row for row in current.rows}
    output: list[MbsObservedChangeEvent] = []
    comparison_identity = {
        "mapping_sha256": mapping.mapping_sha256,
        "historical_schema_era": historical.schema_era,
        "current_schema_era": current.schema_era,
        "historical_source_revision": historical.source_revision,
        "current_source_revision": current.source_revision,
        "historical_b1_sha256": historical.b1_sha256,
        "current_b1_sha256": current.b1_sha256,
        "historical_b2_sha256": historical.b2_sha256,
        "current_b2_sha256": current.b2_sha256,
        "scope_id": historical.scope_id,
    }
    count = 0
    for native_id in sorted(before.keys() | after.keys()):
        old_row, new_row = before.get(native_id), after.get(native_id)
        if old_row is None or new_row is None:
            count += 1
            if count > MAX_DIFFERENCES:
                raise ValueError("MBS schema change event limit exceeded")
            output.append(
                _event(
                    {
                        "native_id": native_id,
                        "silver_target_field": None,
                        "kind": "observed_only_current"
                        if old_row is None
                        else "observed_only_historical",
                        "historical_occurrence": old_row.occurrence_id
                        if old_row
                        else None,
                        "current_occurrence": new_row.occurrence_id
                        if new_row
                        else None,
                        "historical": None,
                        "current": None,
                    },
                    comparison_identity,
                )
            )
            continue
        old_fields = {item.name: item for item in old_row.fields}
        new_fields = {item.name: item for item in new_row.fields}
        for field in mapping.fields:
            count += 1
            if count > MAX_DIFFERENCES:
                raise ValueError("MBS schema change event limit exceeded")
            old = old_fields.get(field.historical_native_name)
            new = new_fields.get(field.current_native_name)
            output.append(
                _event(
                    {
                        "native_id": native_id,
                        "silver_target_field": field.silver_target_field,
                        "kind": "unchanged" if old == new else "field_changed",
                        "historical_occurrence": old_row.occurrence_id,
                        "current_occurrence": new_row.occurrence_id,
                        "historical": old,
                        "current": new,
                    },
                    comparison_identity,
                )
            )
    return tuple(output)


def build_mbs_schema_change_report(
    historical: MbsComparisonCohort,
    current: MbsComparisonCohort,
    mapping: MbsSchemaEraMapping,
) -> MbsSchemaChangeReport:
    """Compare complete candidate cohorts under an exact explicit mapping."""
    historical = MbsComparisonCohort.model_validate(historical.model_dump())
    current = MbsComparisonCohort.model_validate(current.model_dump())
    mapping = MbsSchemaEraMapping.model_validate(mapping.model_dump())
    _validate_inputs(historical.snapshot, current.snapshot, mapping)
    events = _events(historical.snapshot, current.snapshot, mapping)
    provisional = MbsSchemaChangeReport.model_construct(
        historical=historical,
        current=current,
        mapping=mapping,
        events=events,
        report_sha256="0" * 64,
    )
    return MbsSchemaChangeReport(
        historical=historical,
        current=current,
        mapping=mapping,
        events=events,
        report_sha256=_report_digest(provisional),
    )
