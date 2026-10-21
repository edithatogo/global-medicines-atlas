"""Declared field interpretation and consumer guards, separate from admission.

This contract carries source-bound qualification results; constructing it does
not review evidence, establish rights, admit an output or authorize release.
Native unresolved values remain present, with derived uses gated explicitly.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from .models import FrozenModel

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
InterpretationState = Literal["interpreted", "native_unresolved", "unavailable"]


class SilverFieldSemantics(FrozenModel):
    """One source-native field and its explicitly declared semantic evidence."""

    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"state": {"const": "interpreted"}}},
                    "then": {
                        "required": ["evidence_sha256", "semantic_definition"],
                        "properties": {
                            "evidence_sha256": {"type": "string"},
                            "semantic_definition": {"type": "string"},
                        },
                    },
                }
            ],
        }
    )

    source_sha256: Digest
    source_object_id: Digest | None = None
    native_name: str = Field(min_length=1)
    value_kind: Literal["measure", "date", "category", "count"] = "measure"
    state: InterpretationState
    reason: str = Field(min_length=1)
    evidence_sha256: Digest | None = None
    semantic_definition: str | None = Field(default=None, min_length=1)
    unit: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def interpreted_has_evidence(self) -> SilverFieldSemantics:
        if self.state == "interpreted" and (
            self.evidence_sha256 is None or self.semantic_definition is None
        ):
            raise ValueError(
                "interpreted field requires evidence and definition"
            )
        return self

    @property
    def measure_identity(self) -> tuple[str, str | None, str]:
        """Identify content, optional exact object binding, and native field.

        Object-aware producers must supply source_object_id so byte-identical
        aliases remain distinct. None denotes a content-only field identity.
        """
        return self.source_sha256, self.source_object_id, self.native_name

    def require_interpreted(self) -> None:
        """Reject derived uses of unresolved or unavailable field meanings."""
        checked = SilverFieldSemantics.model_validate(self.model_dump())
        if checked.state != "interpreted":
            raise ValueError("derived operation requires interpreted evidence")


def compatible_measure_values(
    observations: Sequence[tuple[SilverFieldSemantics, Decimal]],
) -> tuple[Decimal, ...]:
    """Return lossless values only when declared definitions and units agree.

    Returning values rather than summing avoids introducing Decimal-context
    rounding. Native/source-reported displays do not require this operation.
    """
    identities: set[tuple[str | None, str | None]] = set()
    values: list[Decimal] = []
    for semantics, value in observations:
        semantics.require_interpreted()
        if semantics.value_kind not in {"measure", "count"}:
            raise ValueError("field is not a numeric measure")
        if semantics.unit is None:
            raise ValueError("measure definition and unit must be established")
        identities.add((semantics.semantic_definition, semantics.unit))
        if not value.is_finite():
            raise ValueError("measure value must be finite")
        values.append(value)
    if len(identities) > 1:
        raise ValueError("measure definition and unit differ")
    return tuple(values)


def qualified_date(
    semantics: SilverFieldSemantics, parsed_value: date | None
) -> date:
    """Require semantic evidence before temporal comparisons/current claims."""
    semantics.require_interpreted()
    if semantics.value_kind != "date":
        raise ValueError("field is not a date")
    if parsed_value is None:
        raise ValueError("qualified date value is unavailable")
    return parsed_value
