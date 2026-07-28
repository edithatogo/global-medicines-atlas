"""Fail-closed publication qualification for country comparisons."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import AwareDatetime, Field, model_validator

from .coverage import CoverageObservation
from .models import AssertionKind, EvidenceConflict, FrozenModel
from .receipts import SourceReceipt
from .source_census import CensusCoverage


class PublicationStatus(StrEnum):
    """Observable result of publication qualification."""

    BLOCKED = "blocked"
    QUALIFIED = "qualified"


class PublicationThresholds(FrozenModel):
    """Declared minimum evidence coverage for a publication."""

    minimum_regulatory_jurisdiction_ratio: float = Field(ge=0, le=1)
    minimum_funding_jurisdiction_ratio: float = Field(ge=0, le=1)
    minimum_live_receipt_jurisdiction_ratio: float = Field(ge=0, le=1)
    minimum_record_coverage_ratio: float = Field(ge=0, le=1)
    maximum_receipt_age_days: int = Field(gt=0)


class ExclusionDeclaration(FrozenModel):
    """An explicit declaration, including when no exclusions apply."""

    scope: str = Field(min_length=1)
    reasons: tuple[str, ...]

    @model_validator(mode="after")
    def reasons_are_explicit(self) -> ExclusionDeclaration:
        if any(not reason.strip() for reason in self.reasons):
            raise ValueError("exclusion reasons must not be blank")
        if len(self.reasons) != len(set(self.reasons)):
            raise ValueError("exclusion reasons must be unique")
        return self


class PublicationGateInput(FrozenModel):
    """Evidence bundle evaluated without discovery or fixture shortcuts."""

    evaluated_at: AwareDatetime
    census: CensusCoverage
    thresholds: PublicationThresholds
    receipts: tuple[SourceReceipt, ...]
    coverage: tuple[CoverageObservation, ...]
    conflicts: tuple[EvidenceConflict, ...]
    exclusions: ExclusionDeclaration


class PublicationGateDecision(FrozenModel):
    """Deterministic qualification result and blocking reasons."""

    status: PublicationStatus
    blocking_reasons: tuple[str, ...]
    qualifying_receipt_ids: tuple[str, ...]
    qualifying_jurisdictions: tuple[str, ...]

    @property
    def publishable(self) -> bool:
        return self.status is PublicationStatus.QUALIFIED


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _receipt_is_current(
    receipt: SourceReceipt,
    evaluated_at: datetime,
    maximum_age: timedelta,
) -> bool:
    retrieved_at = receipt.retrieval.retrieved_at
    if not receipt.satisfies_live_gate or retrieved_at > evaluated_at:
        return False
    if evaluated_at - retrieved_at > maximum_age:
        return False
    if (
        receipt.effective_from is not None
        and evaluated_at < receipt.effective_from
    ):
        return False
    return receipt.effective_to is None or evaluated_at < receipt.effective_to


def _check_census(
    census: CensusCoverage,
    thresholds: PublicationThresholds,
) -> set[str]:
    reasons: set[str] = set()
    if census.denominator <= 0:
        return {"discovery denominator is not declared"}
    if (
        _ratio(census.regulatory_source, census.denominator)
        < thresholds.minimum_regulatory_jurisdiction_ratio
    ):
        reasons.add("regulatory jurisdiction coverage is below threshold")
    if (
        _ratio(census.funding_source, census.denominator)
        < thresholds.minimum_funding_jurisdiction_ratio
    ):
        reasons.add("funding jurisdiction coverage is below threshold")
    return reasons


def _check_coverage(
    observations: tuple[CoverageObservation, ...],
    qualifying_receipts: dict[str, SourceReceipt],
    minimum_ratio: float,
    *,
    jurisdiction_denominator: int,
    minimum_regulatory_jurisdiction_ratio: float,
    minimum_funding_jurisdiction_ratio: float,
) -> set[str]:
    if not observations:
        return {"coverage observations are required"}
    reasons: set[str] = set()
    regulatory_jurisdictions: set[str] = set()
    funding_jurisdictions: set[str] = set()
    for observation in observations:
        receipt = qualifying_receipts.get(observation.receipt_id)
        if receipt is None:
            reasons.add("coverage is not bound to a qualifying receipt")
        elif observation.source_id != receipt.source.source_id:
            reasons.add("coverage source does not match receipt")
        elif observation.jurisdiction != receipt.source.jurisdiction:
            reasons.add("coverage jurisdiction does not match receipt")
        elif observation.dimension is AssertionKind.REGULATORY:
            regulatory_jurisdictions.add(observation.jurisdiction)
        elif observation.dimension in {
            AssertionKind.FUNDING,
            AssertionKind.FORMULARY,
        }:
            funding_jurisdictions.add(observation.jurisdiction)
        if observation.eligible_denominator is None:
            reasons.add("record coverage denominator is not declared")
        elif (
            _ratio(
                observation.concept_numerator,
                observation.eligible_denominator,
            )
            < minimum_ratio
        ):
            reasons.add("record coverage is below threshold")
        if observation.exclusion_count != len(
            set(observation.exclusion_reasons)
        ):
            reasons.add("coverage exclusions are not explicitly reconciled")
        if observation.conflicting_assertion_count:
            reasons.add("coverage contains unresolved blocking conflicts")
    reasons.update(
        _check_dimension_coverage(
            regulatory_jurisdictions,
            funding_jurisdictions,
            jurisdiction_denominator,
            minimum_regulatory_jurisdiction_ratio,
            minimum_funding_jurisdiction_ratio,
        )
    )
    return reasons


def _check_dimension_coverage(
    regulatory_jurisdictions: set[str],
    funding_jurisdictions: set[str],
    denominator: int,
    minimum_regulatory_ratio: float,
    minimum_funding_ratio: float,
) -> set[str]:
    reasons: set[str] = set()
    if minimum_regulatory_ratio > 0 and (
        _ratio(len(regulatory_jurisdictions), denominator)
        < minimum_regulatory_ratio
    ):
        reasons.add("qualifying regulatory coverage is below threshold")
    if minimum_funding_ratio > 0 and (
        _ratio(len(funding_jurisdictions), denominator) < minimum_funding_ratio
    ):
        reasons.add(
            "qualifying funding or formulary coverage is below threshold"
        )
    return reasons


def evaluate_publication_gate(
    evidence: PublicationGateInput,
) -> PublicationGateDecision:
    """Qualify only current, permitted, live, denominator-backed evidence."""

    reasons: set[str] = set()
    denominator = evidence.census.denominator
    thresholds = evidence.thresholds
    reasons.update(_check_census(evidence.census, thresholds))

    maximum_age = timedelta(days=thresholds.maximum_receipt_age_days)
    qualifying_receipts = tuple(
        receipt
        for receipt in evidence.receipts
        if _receipt_is_current(
            receipt,
            evidence.evaluated_at,
            maximum_age,
        )
    )
    qualifying_by_id = {
        receipt.receipt_id: receipt for receipt in qualifying_receipts
    }
    qualifying_ids = set(qualifying_by_id)
    qualifying_jurisdictions = {
        receipt.source.jurisdiction for receipt in qualifying_receipts
    }
    if len(qualifying_receipts) != len(evidence.receipts):
        reasons.add("all receipts must be current, permitted, and live")
    if not qualifying_receipts:
        reasons.add("no qualifying current live receipts")
    if (
        denominator > 0
        and _ratio(len(qualifying_jurisdictions), denominator)
        < thresholds.minimum_live_receipt_jurisdiction_ratio
    ):
        reasons.add("live receipt jurisdiction coverage is below threshold")

    reasons.update(
        _check_coverage(
            evidence.coverage,
            qualifying_by_id,
            thresholds.minimum_record_coverage_ratio,
            jurisdiction_denominator=denominator,
            minimum_regulatory_jurisdiction_ratio=(
                thresholds.minimum_regulatory_jurisdiction_ratio
            ),
            minimum_funding_jurisdiction_ratio=(
                thresholds.minimum_funding_jurisdiction_ratio
            ),
        )
    )

    if any(
        conflict.resolution_status.casefold() != "resolved"
        for conflict in evidence.conflicts
    ):
        reasons.add("unresolved blocking conflicts remain")

    ordered_reasons = tuple(sorted(reasons))
    status = (
        PublicationStatus.QUALIFIED
        if not ordered_reasons
        else PublicationStatus.BLOCKED
    )
    return PublicationGateDecision(
        status=status,
        blocking_reasons=ordered_reasons,
        qualifying_receipt_ids=tuple(sorted(qualifying_ids)),
        qualifying_jurisdictions=tuple(sorted(qualifying_jurisdictions)),
    )
