"""Bounded, evidence-preserving historical change observations.

This is a product candidate over already supplied snapshots.  It deliberately
does not turn absence into a cessation or a missing period into a negative
finding; consumers must inspect the explicit availability and completeness
states.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from .historical_comparison import (
    NativeDifference,
    NativeSnapshot,
    compare_native_snapshots,
)
from .models import FrozenModel

MAX_HISTORICAL_CHANGE_PAGE_SIZE = 1000


class ChangeObservation(FrozenModel):
    """One literal key/field change with an explicit interpretation."""

    model_config = ConfigDict(revalidate_instances="always")
    native_id: str = Field(min_length=1, max_length=4096)
    field_name: str | None = Field(default=None, max_length=4096)
    kind: Literal[
        "added_observation", "removed_observation", "field_changed", "unchanged"
    ]
    interpretation: Literal["observed_change", "observed_stability"]
    difference: NativeDifference | None = None

    @model_validator(mode="after")
    def consistent(self) -> ChangeObservation:
        if self.kind in {"added_observation", "removed_observation"}:
            if self.field_name is not None or self.difference is None:
                raise ValueError("row changes require a row-level difference")
        elif self.difference is None or self.field_name is None:
            raise ValueError("field changes require a field-level difference")
        expected = (
            "observed_stability"
            if self.kind == "unchanged"
            else "observed_change"
        )
        if self.interpretation != expected:
            raise ValueError("change interpretation does not match kind")
        return self


class HistoricalChange(FrozenModel):
    """Comparison envelope retaining coverage and source-outage semantics."""

    model_config = ConfigDict(revalidate_instances="always")
    schema_id: Literal["global-medicines-atlas.historical-change"] = (
        "global-medicines-atlas.historical-change"
    )
    schema_version: Literal[1] = 1
    left: NativeSnapshot | None
    right: NativeSnapshot | None
    availability: Literal[
        "both_present", "left_missing", "right_missing", "both_missing"
    ]
    comparison_state: Literal[
        "compared",
        "missing_period",
        "source_outage",
        "schema_drift",
        "incompatible",
    ]
    absence_interpretation: Literal["unknown"] = "unknown"
    changes: tuple[ChangeObservation, ...] = Field(max_length=65536)

    @model_validator(mode="after")
    def matches_inputs(self) -> HistoricalChange:
        if self.left is None and self.right is None:
            expected = "both_missing"
            state = "source_outage"
        elif self.left is None:
            expected = "left_missing"
            state = "missing_period"
        elif self.right is None:
            expected = "right_missing"
            state = "missing_period"
        else:
            expected = "both_present"
            candidate = compare_native_snapshots(self.left, self.right)
            if "incomplete_snapshot" in candidate.reasons:
                state = "source_outage"
            elif "incompatible_profile" in candidate.reasons:
                state = (
                    "schema_drift"
                    if (
                        self.left.schema_era != self.right.schema_era
                        or self.left.identity_profile
                        != self.right.identity_profile
                    )
                    else "incompatible"
                )
            elif "ambiguous_identity" in candidate.reasons:
                state = "incompatible"
            else:
                state = "compared"
            expected_changes = tuple(
                _observation(item) for item in candidate.differences
            )
            if self.changes != expected_changes:
                raise ValueError("historical changes do not match snapshots")
        if self.availability != expected or self.comparison_state != state:
            raise ValueError(
                "historical state does not match snapshot availability"
            )
        if (self.left is None or self.right is None) and self.changes:
            raise ValueError("missing snapshots cannot have inferred changes")
        return self


class HistoricalChangePage(FrozenModel):
    """A bounded page of already-computed historical change envelopes."""

    items: tuple[HistoricalChange, ...]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=MAX_HISTORICAL_CHANGE_PAGE_SIZE)
    total: int = Field(ge=0)
    next_offset: int | None = Field(default=None, ge=0)


class HistoricalChangeService:
    """Read-only paging over an injected, immutable historical result set.

    The service does not acquire snapshots or infer changes.  Callers provide
    the already-qualified envelopes, and paging only selects a deterministic
    bounded window for a route or other transport adapter.
    """

    def __init__(self, changes: Sequence[HistoricalChange]) -> None:
        self._changes = tuple(changes)

    def page(
        self, *, offset: int = 0, limit: int = 100
    ) -> HistoricalChangePage:
        if offset < 0 or limit < 1 or limit > MAX_HISTORICAL_CHANGE_PAGE_SIZE:
            raise ValueError("historical change paging bounds are invalid")
        total = len(self._changes)
        items = self._changes[offset : offset + limit]
        end = offset + len(items)
        return HistoricalChangePage(
            items=items,
            offset=offset,
            limit=limit,
            total=total,
            next_offset=end if end < total else None,
        )


def _observation(item: NativeDifference) -> ChangeObservation:
    if item.kind == "present_only_left":
        kind = "removed_observation"
    elif item.kind == "present_only_right":
        kind = "added_observation"
    elif item.kind == "field_changed":
        kind = "field_changed"
    else:
        kind = "unchanged"
    return ChangeObservation(
        native_id=item.native_id,
        field_name=item.field_name,
        kind=kind,
        interpretation=(
            "observed_stability" if kind == "unchanged" else "observed_change"
        ),
        difference=item,
    )


def compare_historical_snapshots(
    left: NativeSnapshot | None, right: NativeSnapshot | None
) -> HistoricalChange:
    """Produce a bounded change envelope without inferring status."""
    if left is None or right is None:
        return HistoricalChange(
            left=left,
            right=right,
            availability=(
                "both_missing"
                if left is None and right is None
                else "left_missing"
                if left is None
                else "right_missing"
            ),
            comparison_state=(
                "source_outage"
                if left is None and right is None
                else "missing_period"
            ),
            changes=(),
        )
    candidate = compare_native_snapshots(left, right)
    state = (
        "source_outage"
        if "incomplete_snapshot" in candidate.reasons
        else (
            "schema_drift"
            if "incompatible_profile" in candidate.reasons
            and (
                left.schema_era != right.schema_era
                or left.identity_profile != right.identity_profile
            )
            else "incompatible"
            if candidate.reasons
            else "compared"
        )
    )
    return HistoricalChange(
        left=left,
        right=right,
        availability="both_present",
        comparison_state=state,
        changes=tuple(_observation(item) for item in candidate.differences),
    )
