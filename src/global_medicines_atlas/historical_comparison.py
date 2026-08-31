"""Bounded native snapshot differences, not status or Gold promotion.

Inputs are caller-supplied observations, not acquired or independently verified
source evidence. Digests pin their declared lineage; this module does not verify
remote bytes, establish completeness, interpret dates, or authorize publication.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    ConfigDict,
    Field,
    model_validator,
)

from .models import FrozenModel

MAX_ROWS = 4096
MAX_FIELDS = 256
MAX_NATIVE_BYTES = 8 * 1024 * 1024
MAX_SNAPSHOT_FIELDS = 65536
MAX_DIFFERENCES = 65536
Name = Annotated[str, Field(min_length=1, max_length=4096)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Reason = Literal[
    "incompatible_profile", "incomplete_snapshot", "ambiguous_identity"
]


def _profile_name(value: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError("profile identity must be nonblank and unpadded")
    return value


def _native_identity(value: str) -> str:
    if not value.strip():
        raise ValueError("native identity cannot be blank")
    return value


ProfileName = Annotated[Name, AfterValidator(_profile_name)]
NativeIdentity = Annotated[Name, AfterValidator(_native_identity)]


class NativeField(FrozenModel):
    """A literal field; omitted, null and empty are different observations."""

    model_config = ConfigDict(
        revalidate_instances="always",
        json_schema_extra={
            "oneOf": [
                {
                    "properties": {
                        "state": {"const": "value"},
                        "value": {"type": "string"},
                    },
                    "required": ["value"],
                },
                {
                    "properties": {
                        "state": {"enum": ["missing", "null"]},
                        "value": {"type": "null"},
                    }
                },
            ]
        },
    )
    name: Name
    state: Literal["missing", "null", "value"]
    value: str | None = Field(default=None, max_length=16384)

    @model_validator(mode="after")
    def state_matches_value(self) -> NativeField:
        if (self.state == "value") != (self.value is not None):
            raise ValueError("native state and value disagree")
        return self


class NativeRow(FrozenModel):
    """One source occurrence with its uncoerced native identity and fields."""

    model_config = ConfigDict(revalidate_instances="always")
    native_id: NativeIdentity
    occurrence_id: Name
    fields: tuple[NativeField, ...] = Field(max_length=MAX_FIELDS)

    @model_validator(mode="after")
    def unique_fields(self) -> NativeRow:
        if len({field.name for field in self.fields}) != len(self.fields):
            raise ValueError("duplicate native field")
        return self


class NativeSnapshot(FrozenModel):
    """Bounded source-native input with explicit declared completeness."""

    model_config = ConfigDict(revalidate_instances="always")
    source_id: ProfileName
    table: ProfileName
    dimension: Literal[
        "service_benefit", "funding", "formulary", "terminology", "regulatory"
    ]
    schema_era: ProfileName
    identity_profile: ProfileName
    scope_id: ProfileName = "whole_source"
    source_revision: ProfileName
    source_path: ProfileName
    b1_sha256: Digest
    b2_sha256: Digest
    observed_at: AwareDatetime
    cohort: Literal["synthetic", "legacy", "historical", "current"]
    declared_rows: int = Field(strict=True, ge=0, le=MAX_ROWS)
    complete: bool = Field(strict=True)
    rows: tuple[NativeRow, ...] = Field(max_length=MAX_ROWS)

    @model_validator(mode="after")
    def unique_occurrences_and_bounded_bytes(self) -> NativeSnapshot:
        if len({row.occurrence_id for row in self.rows}) != len(self.rows):
            raise ValueError("duplicate occurrence identity")
        if sum(len(row.fields) for row in self.rows) > MAX_SNAPSHOT_FIELDS:
            raise ValueError("snapshot aggregate field limit exceeded")
        size = 0
        for row in self.rows:
            size += len(row.native_id.encode()) + len(
                row.occurrence_id.encode()
            )
            for field in row.fields:
                size += len(field.name.encode())
                size += len((field.value or "").encode())
            if size > MAX_NATIVE_BYTES:
                raise ValueError("snapshot native byte limit exceeded")
        return self


class NativeDifference(FrozenModel):
    """Literal observation difference, never addition or cessation status."""

    model_config = ConfigDict(revalidate_instances="always")
    native_id: NativeIdentity
    field_name: Name | None
    kind: Literal[
        "field_changed", "unchanged", "present_only_left", "present_only_right"
    ]
    left_occurrence: Name | None
    right_occurrence: Name | None
    left: NativeField | None
    right: NativeField | None


def _reasons(left: NativeSnapshot, right: NativeSnapshot) -> tuple[Reason, ...]:
    reasons: list[Reason] = []
    profile = (
        "source_id",
        "table",
        "dimension",
        "schema_era",
        "identity_profile",
        "scope_id",
    )
    if any(getattr(left, key) != getattr(right, key) for key in profile) or (
        (left.cohort == "synthetic") != (right.cohort == "synthetic")
    ):
        reasons.append("incompatible_profile")
    if any(
        not item.complete or item.declared_rows != len(item.rows)
        for item in (left, right)
    ):
        reasons.append("incomplete_snapshot")
    if any(
        len({row.native_id for row in item.rows}) != len(item.rows)
        for item in (left, right)
    ):
        reasons.append("ambiguous_identity")
    return tuple(reasons)


def _differences(
    left: NativeSnapshot, right: NativeSnapshot
) -> tuple[NativeDifference, ...]:
    output: list[NativeDifference] = []
    left_rows = {row.native_id: row for row in left.rows}
    right_rows = {row.native_id: row for row in right.rows}
    count = 0
    for identity in left_rows.keys() | right_rows.keys():
        before, after = left_rows.get(identity), right_rows.get(identity)
        count += (
            1
            if before is None or after is None
            else len(
                {field.name for field in before.fields}
                | {field.name for field in after.fields}
            )
        )
        if count > MAX_DIFFERENCES:
            raise ValueError("comparison difference limit exceeded")
    for identity in sorted(left_rows.keys() | right_rows.keys()):
        before, after = left_rows.get(identity), right_rows.get(identity)
        if before is None or after is None:
            output.append(
                NativeDifference(
                    native_id=identity,
                    field_name=None,
                    kind="present_only_right"
                    if before is None
                    else "present_only_left",
                    left_occurrence=before.occurrence_id if before else None,
                    right_occurrence=after.occurrence_id if after else None,
                    left=None,
                    right=None,
                )
            )
            continue
        before_fields = {field.name: field for field in before.fields}
        after_fields = {field.name: field for field in after.fields}
        for name in sorted(before_fields.keys() | after_fields.keys()):
            old, new = before_fields.get(name), after_fields.get(name)
            output.append(
                NativeDifference(
                    native_id=identity,
                    field_name=name,
                    kind="unchanged" if old == new else "field_changed",
                    left_occurrence=before.occurrence_id,
                    right_occurrence=after.occurrence_id,
                    left=old,
                    right=new,
                )
            )
    return tuple(output)


class NativeComparison(FrozenModel):
    """Revalidated candidate result retaining both full input denominators."""

    model_config = ConfigDict(revalidate_instances="always")
    schema_id: Literal["global-medicines-atlas.native-comparison"] = (
        "global-medicines-atlas.native-comparison"
    )
    schema_version: Literal[1] = 1
    absence_interpretation: Literal["unknown"] = "unknown"
    qualification: Literal["native_difference_candidate"] = (
        "native_difference_candidate"
    )
    left: NativeSnapshot
    right: NativeSnapshot
    outcome: Literal["compared", "abstained"]
    reasons: tuple[Reason, ...]
    differences: tuple[NativeDifference, ...] = Field(
        max_length=MAX_DIFFERENCES
    )

    @model_validator(mode="after")
    def result_matches_inputs(self) -> NativeComparison:
        NativeSnapshot.model_validate(self.left.model_dump())
        NativeSnapshot.model_validate(self.right.model_dump())
        reasons = _reasons(self.left, self.right)
        expected = () if reasons else _differences(self.left, self.right)
        outcome = "abstained" if reasons else "compared"
        if (
            self.reasons != reasons
            or self.outcome != outcome
            or self.differences != expected
        ):
            raise ValueError("comparison result does not match native inputs")
        return self


def compare_native_snapshots(
    left: NativeSnapshot, right: NativeSnapshot
) -> NativeComparison:
    """Compare literal profiles or abstain; never infer missing-source status."""
    # Revalidate even caller-mutated/model_construct inputs before comparison.
    left = NativeSnapshot.model_validate(left.model_dump())
    right = NativeSnapshot.model_validate(right.model_dump())
    reasons = _reasons(left, right)
    return NativeComparison(
        left=left,
        right=right,
        outcome="abstained" if reasons else "compared",
        reasons=reasons,
        differences=() if reasons else _differences(left, right),
    )
