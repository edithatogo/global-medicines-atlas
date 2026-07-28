"""Explainable evidence for cross-jurisdiction matching candidates."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import AwareDatetime, Field, model_validator

from .matching_models import MappingLevel
from .models import FrozenModel


class FeatureKind(StrEnum):
    IDENTIFIER = "identifier"
    INGREDIENT = "ingredient"
    STRENGTH = "strength"
    UNIT = "unit"
    FORM = "form"
    ROUTE = "route"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    RXNORM = "rxnorm"
    TEMPORAL = "temporal"


class FeatureDisposition(StrEnum):
    AGREEMENT = "agreement"
    CONFLICT = "conflict"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


class FeatureEvidence(FrozenModel):
    kind: FeatureKind
    disposition: FeatureDisposition
    contribution: float = Field(ge=-1, le=1)
    explanation: str = Field(min_length=1)
    source_value: str | None = None
    target_value: str | None = None
    provenance_ids: tuple[str, ...] = ()


class MatchFeatures(FrozenModel):
    mapping_level: MappingLevel
    identifiers: FeatureEvidence
    ingredients: FeatureEvidence
    strength: FeatureEvidence
    unit: FeatureEvidence
    form: FeatureEvidence
    route: FeatureEvidence
    lexical: FeatureEvidence
    semantic: FeatureEvidence
    rxnorm: FeatureEvidence
    temporal: FeatureEvidence
    penalties: tuple[FeatureEvidence, ...] = ()
    feature_version: str = Field(min_length=1)
    evaluated_at: AwareDatetime

    @model_validator(mode="after")
    def feature_slots_match_kinds(self) -> MatchFeatures:
        slots = {
            "identifiers": FeatureKind.IDENTIFIER,
            "ingredients": FeatureKind.INGREDIENT,
            "strength": FeatureKind.STRENGTH,
            "unit": FeatureKind.UNIT,
            "form": FeatureKind.FORM,
            "route": FeatureKind.ROUTE,
            "lexical": FeatureKind.LEXICAL,
            "semantic": FeatureKind.SEMANTIC,
            "rxnorm": FeatureKind.RXNORM,
            "temporal": FeatureKind.TEMPORAL,
        }
        for name, expected in slots.items():
            if getattr(self, name).kind is not expected:
                raise ValueError(
                    f"{name} must contain {expected.value} evidence"
                )
        if any(item.contribution > 0 for item in self.penalties):
            raise ValueError("Penalty contributions must be non-positive")
        return self

    @property
    def ordered_evidence(self) -> tuple[FeatureEvidence, ...]:
        return (
            self.identifiers,
            self.ingredients,
            self.strength,
            self.unit,
            self.form,
            self.route,
            self.lexical,
            self.semantic,
            self.rxnorm,
            self.temporal,
            *self.penalties,
        )

    @property
    def raw_score(self) -> float:
        score = sum(item.contribution for item in self.ordered_evidence)
        return max(0.0, min(1.0, score))

    @property
    def conflicts(self) -> tuple[FeatureKind, ...]:
        return tuple(
            item.kind
            for item in self.ordered_evidence
            if item.disposition is FeatureDisposition.CONFLICT
        )

    @property
    def missing(self) -> tuple[FeatureKind, ...]:
        return tuple(
            item.kind
            for item in self.ordered_evidence
            if item.disposition is FeatureDisposition.MISSING
        )


def feature(
    kind: FeatureKind,
    disposition: FeatureDisposition,
    contribution: float,
    explanation: str,
    *,
    source_value: str | None = None,
    target_value: str | None = None,
    provenance_ids: tuple[str, ...] = (),
) -> FeatureEvidence:
    """Construct explicit feature evidence without hiding its inputs."""
    return FeatureEvidence(
        kind=kind,
        disposition=disposition,
        contribution=contribution,
        explanation=explanation,
        source_value=source_value,
        target_value=target_value,
        provenance_ids=provenance_ids,
    )


def utc_now() -> datetime:
    """Clock seam for callers that do not need a reproducible timestamp."""
    return datetime.now().astimezone()
