"""Contracts for synthetic Canada, EU, UK, and Japan adapters."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from global_medicines_atlas.adapters.canada import project_canada_fixture
from global_medicines_atlas.adapters.european_union import project_eu_fixture
from global_medicines_atlas.adapters.fixture_contracts import FixtureProjection
from global_medicines_atlas.adapters.japan import project_japan_fixture
from global_medicines_atlas.adapters.united_kingdom import project_uk_fixture
from global_medicines_atlas.models import AssertionKind, EvidenceStatus
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    EvidenceClass,
    RightsState,
)

FIXTURES = Path(__file__).parent / "fixtures" / "global_adapters"
RETRIEVED_AT = datetime(2026, 7, 29, tzinfo=UTC)
Projector = Callable[..., FixtureProjection]


@pytest.mark.integration
@pytest.mark.parametrize(
    ("fixture_name", "projector", "jurisdiction", "expected_kinds"),
    [
        (
            "canada.json",
            project_canada_fixture,
            "CAN",
            {AssertionKind.REGULATORY},
        ),
        (
            "european_union.json",
            project_eu_fixture,
            "EU",
            {AssertionKind.REGULATORY},
        ),
        (
            "united_kingdom.json",
            project_uk_fixture,
            "GBR",
            {AssertionKind.REGULATORY, AssertionKind.FUNDING},
        ),
        (
            "japan.json",
            project_japan_fixture,
            "JPN",
            {AssertionKind.REGULATORY, AssertionKind.FUNDING},
        ),
    ],
)
def test_fixture_adapters_preserve_status_dimensions(
    fixture_name: str,
    projector: Projector,
    jurisdiction: str,
    expected_kinds: set[AssertionKind],
) -> None:
    payload = (FIXTURES / fixture_name).read_bytes()

    projection = projector(payload, retrieved_at=RETRIEVED_AT)

    assert len(projection.records) == 1
    record = projection.records[0]
    assert record.concept.jurisdiction == jurisdiction
    assert {assertion.kind for assertion in record.assertions} == expected_kinds
    assert all(
        assertion.kind is not AssertionKind.FORMULARY
        for assertion in record.assertions
    )
    assert all(
        assertion.provenance.source_uri.startswith("fixture://")
        for assertion in record.assertions
    )
    assert all(
        assertion.evidence_status is EvidenceStatus.UNKNOWN
        for assertion in record.assertions
    )
    assert all(
        assertion.evidence_status is not EvidenceStatus.CONFIRMED
        for assertion in record.assertions
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("fixture_name", "projector"),
    [
        ("canada.json", project_canada_fixture),
        ("european_union.json", project_eu_fixture),
        ("united_kingdom.json", project_uk_fixture),
        ("japan.json", project_japan_fixture),
    ],
)
def test_fixture_receipts_are_synthetic_and_do_not_claim_live_access(
    fixture_name: str,
    projector: Projector,
) -> None:
    payload = (FIXTURES / fixture_name).read_bytes()

    projection = projector(payload, retrieved_at=RETRIEVED_AT)

    assert projection.receipts
    assert all(
        receipt.evidence_class is EvidenceClass.SYNTHETIC
        for receipt in projection.receipts
    )
    assert all(
        receipt.retrieval.acquisition_method is AcquisitionMethod.LOCAL_FIXTURE
        for receipt in projection.receipts
    )
    assert all(
        receipt.rights_state is RightsState.PERMITTED
        for receipt in projection.receipts
    )
    assert all(
        not receipt.satisfies_live_gate for receipt in projection.receipts
    )
    assert all(
        limit.access == "synthetic-fixture"
        for limit in projection.access_limits
        if limit.payload_included
    )
    assert all(
        "Live source not accessed" in limit.evidence_limit
        for limit in projection.access_limits
        if limit.payload_included
    )
    assert all(
        assertion.evidence_status is EvidenceStatus.UNKNOWN
        for record in projection.records
        for assertion in record.assertions
    )


@pytest.mark.unit
def test_uk_dmd_is_a_restricted_declaration_without_payload_or_assertions() -> (
    None
):
    payload = (FIXTURES / "united_kingdom.json").read_bytes()

    projection = project_uk_fixture(payload, retrieved_at=RETRIEVED_AT)

    declaration = next(
        limit
        for limit in projection.access_limits
        if limit.source_id == "uk-dmd"
    )
    assert declaration.access == "licensed-declaration-only"
    assert declaration.rights_state is RightsState.RESTRICTED
    assert not declaration.payload_included
    assert all(
        receipt.source.source_id != "uk-dmd" for receipt in projection.receipts
    )
    assert all(
        assertion.provenance.source_id != "uk-dmd"
        for record in projection.records
        for assertion in record.assertions
    )


@pytest.mark.edge
def test_fixture_rejects_undeclared_source() -> None:
    payload = (
        (FIXTURES / "canada.json")
        .read_bytes()
        .replace(
            b'"ca-noc"',
            b'"ca-unknown"',
            1,
        )
    )

    with pytest.raises(ValueError, match="sources do not match"):
        project_canada_fixture(payload, retrieved_at=RETRIEVED_AT)
