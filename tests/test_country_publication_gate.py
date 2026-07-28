"""Fail-closed publication qualification for country comparisons."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import AnyUrl, ValidationError

from global_medicines_atlas.coverage import CoverageObservation
from global_medicines_atlas.models import (
    AssertionKind,
    EvidenceConflict,
    TimeInterval,
)
from global_medicines_atlas.publication_gate import (
    ExclusionDeclaration,
    PublicationGateInput,
    PublicationStatus,
    PublicationThresholds,
    evaluate_publication_gate,
)
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)
from global_medicines_atlas.source_census import CensusCoverage

NOW = datetime(2026, 7, 29, tzinfo=UTC)


def _receipt(
    *,
    receipt_id: str = "receipt-nzl-live",
    source_id: str = "nz-medsafe",
    authority: str = "Medsafe",
    evidence_class: EvidenceClass = EvidenceClass.LIVE,
    rights_state: RightsState = RightsState.PERMITTED,
    retrieved_at: datetime = NOW - timedelta(days=1),
) -> SourceReceipt:
    return SourceReceipt(
        receipt_id=receipt_id,
        source=SourceIdentity(
            catalog_id="catalog",
            source_id=source_id,
            jurisdiction="NZL",
            authority=authority,
            dataset_title="Product register",
            catalog_version="1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("https://example.test/register.csv"),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=PayloadEvidence(sha256="a" * 64, byte_count=1),
        effective_from=NOW - timedelta(days=2),
        rights_state=rights_state,
        rights_reference=(
            AnyUrl("https://example.test/rights")
            if rights_state is RightsState.PERMITTED
            else None
        ),
        evidence_class=evidence_class,
        transformation=TransformationEvidence(
            transformation_id="project-v1",
            transformation_sha256="b" * 64,
            output_sha256="c" * 64,
            output_byte_count=1,
        ),
    )


def _census(*, denominator: int = 1) -> CensusCoverage:
    return CensusCoverage(
        denominator=denominator,
        regulatory_source=1 if denominator else 0,
        funding_source=1 if denominator else 0,
        api=0,
        bulk=1 if denominator else 0,
        implemented_ingestion=1 if denominator else 0,
        current_receipt=1 if denominator else 0,
        source_health_scheduled=1 if denominator else 0,
        schema_drift_scheduled=1 if denominator else 0,
    )


def _coverage(
    *,
    receipt_id: str = "receipt-nzl-live",
    source_id: str = "nz-medsafe",
    jurisdiction: str = "NZL",
    dimension: AssertionKind = AssertionKind.REGULATORY,
    denominator: int | None = 10,
    numerator: int = 10,
    conflicts: int = 0,
) -> CoverageObservation:
    interval = TimeInterval(
        start=NOW - timedelta(days=2),
        end=NOW + timedelta(days=1),
    )
    return CoverageObservation(
        jurisdiction=jurisdiction,
        source_id=source_id,
        receipt_id=receipt_id,
        observation_id="coverage-1",
        population_partition_id="all-products",
        dimension=dimension,
        assertion_type="registration",
        assertion_status="active",
        concept_population="aggregate:registered-products",
        valid_time=interval,
        observed_time=interval,
        assertion_count=numerator,
        concept_numerator=numerator,
        eligible_denominator=denominator,
        exclusion_count=1,
        exclusion_reasons=("veterinary products",),
        conflicting_assertion_count=conflicts,
    )


def _input(
    *,
    receipt: SourceReceipt | None = None,
    census: CensusCoverage | None = None,
    coverage: CoverageObservation | None = None,
    receipts: tuple[SourceReceipt, ...] | None = None,
    coverage_observations: tuple[CoverageObservation, ...] | None = None,
    conflicts: tuple[EvidenceConflict, ...] = (),
) -> PublicationGateInput:
    return PublicationGateInput(
        evaluated_at=NOW,
        census=_census() if census is None else census,
        thresholds=PublicationThresholds(
            minimum_regulatory_jurisdiction_ratio=1,
            minimum_funding_jurisdiction_ratio=1,
            minimum_live_receipt_jurisdiction_ratio=1,
            minimum_record_coverage_ratio=0.9,
            maximum_receipt_age_days=30,
        ),
        receipts=(
            receipts
            if receipts is not None
            else (_receipt() if receipt is None else receipt,)
        ),
        coverage=(
            coverage_observations
            if coverage_observations is not None
            else (
                _coverage() if coverage is None else coverage,
                _coverage(
                    receipt_id="receipt-nzl-funding",
                    source_id="nz-pharmac",
                    dimension=AssertionKind.FUNDING,
                ),
            )
        ),
        conflicts=conflicts,
        exclusions=ExclusionDeclaration(
            scope="country comparison",
            reasons=("veterinary products",),
        ),
    )


def test_complete_live_evidence_qualifies() -> None:
    decision = evaluate_publication_gate(
        _input(
            receipts=(
                _receipt(),
                _receipt(
                    receipt_id="receipt-nzl-funding",
                    source_id="nz-pharmac",
                    authority="Pharmac",
                ),
            )
        )
    )

    assert decision.status is PublicationStatus.QUALIFIED
    assert decision.publishable
    assert decision.blocking_reasons == ()
    assert decision.qualifying_jurisdictions == ("NZL",)


@pytest.mark.parametrize(
    ("receipt", "reason"),
    [
        (
            _receipt(evidence_class=EvidenceClass.FIXTURE),
            "all receipts must be current, permitted, and live",
        ),
        (
            _receipt(rights_state=RightsState.UNKNOWN),
            "all receipts must be current, permitted, and live",
        ),
        (
            _receipt(retrieved_at=NOW - timedelta(days=31)),
            "all receipts must be current, permitted, and live",
        ),
    ],
)
def test_fixture_discovery_or_stale_receipts_fail_closed(
    receipt: SourceReceipt,
    reason: str,
) -> None:
    decision = evaluate_publication_gate(_input(receipt=receipt))

    assert not decision.publishable
    assert reason in decision.blocking_reasons
    assert decision.qualifying_receipt_ids == ()


def test_declared_denominators_and_thresholds_are_required() -> None:
    decision = evaluate_publication_gate(
        _input(
            census=_census(denominator=0), coverage=_coverage(denominator=None)
        )
    )

    assert not decision.publishable
    assert "discovery denominator is not declared" in decision.blocking_reasons
    assert (
        "record coverage denominator is not declared"
        in decision.blocking_reasons
    )


def test_coverage_must_be_receipt_bound_and_above_threshold() -> None:
    decision = evaluate_publication_gate(
        _input(
            coverage=_coverage(
                receipt_id="fixture-only",
                denominator=10,
                numerator=8,
            )
        )
    )

    assert "coverage is not bound to a qualifying receipt" in (
        decision.blocking_reasons
    )
    assert "record coverage is below threshold" in decision.blocking_reasons


@pytest.mark.parametrize(
    ("coverage", "reason"),
    [
        (
            _coverage(source_id="wrong-source"),
            "coverage source does not match receipt",
        ),
        (
            _coverage(jurisdiction="AUS"),
            "coverage jurisdiction does not match receipt",
        ),
    ],
)
def test_coverage_identity_must_match_receipt(
    coverage: CoverageObservation,
    reason: str,
) -> None:
    decision = evaluate_publication_gate(
        _input(
            coverage_observations=(coverage,),
        )
    )

    assert not decision.publishable
    assert reason in decision.blocking_reasons


def test_one_dimension_only_fails_closed() -> None:
    decision = evaluate_publication_gate(
        _input(coverage_observations=(_coverage(),))
    )

    assert not decision.publishable
    assert (
        "qualifying funding or formulary coverage is below threshold"
        in decision.blocking_reasons
    )


def test_unresolved_conflicts_block_publication() -> None:
    conflict = EvidenceConflict(
        conflict_id="conflict-1",
        concept_id="medicine-1",
        kind=AssertionKind.REGULATORY,
        assertion_ids=("assertion-1", "assertion-2"),
        reason="sources disagree",
    )

    decision = evaluate_publication_gate(
        _input(coverage=_coverage(conflicts=1), conflicts=(conflict,))
    )

    assert "unresolved blocking conflicts remain" in decision.blocking_reasons
    assert (
        "coverage contains unresolved blocking conflicts"
        in decision.blocking_reasons
    )


def test_exclusion_declaration_rejects_implicit_or_duplicate_reasons() -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        ExclusionDeclaration(scope="comparison", reasons=(" ",))

    with pytest.raises(ValidationError, match="must be unique"):
        ExclusionDeclaration(scope="comparison", reasons=("known gap",) * 2)
