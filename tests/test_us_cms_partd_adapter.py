"""Fixture contracts for plan-level CMS Part D evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from global_medicines_atlas.adapters.us_cms_partd import project_cms_partd_csv
from global_medicines_atlas.models import AssertionKind, EvidenceStatus
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

FIXTURE = Path(__file__).parent / "fixtures" / "us" / "cms_partd_formulary.csv"


def receipt(
    payload: str,
    *,
    source_id: str = "us-cms-partd-formulary",
    jurisdiction: str = "USA",
    method: AcquisitionMethod = AcquisitionMethod.DOWNLOAD,
    live: bool = False,
) -> SourceReceipt:
    payload_bytes = payload.encode()
    digest = sha256(payload_bytes).hexdigest()
    return SourceReceipt(
        receipt_id="cms-partd-fixture",
        source=SourceIdentity(
            catalog_id=source_id,
            source_id=source_id,
            jurisdiction=jurisdiction,
            authority="Centers for Medicare & Medicaid Services",
            dataset_title="CMS Part D formulary fixture",
            catalog_version="1",
        ),
        retrieval=RetrievalEvidence(
            uri="https://example.test/cms-partd.csv",
            retrieved_at=datetime(2026, 7, 29, tzinfo=UTC),
            acquisition_method=method,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=PayloadEvidence.from_bytes(payload_bytes),
        rights_state=RightsState.PERMITTED if live else RightsState.UNKNOWN,
        rights_reference=("https://rights.example/cms-partd" if live else None),
        evidence_class=EvidenceClass.LIVE if live else EvidenceClass.FIXTURE,
        transformation=TransformationEvidence(
            transformation_id="cms-partd-raw-v1",
            transformation_sha256="a" * 64,
            output_sha256=digest,
            output_byte_count=len(payload_bytes),
        ),
    )


@pytest.mark.integration
def test_cms_partd_projects_plan_level_formulary_and_pricing() -> None:
    payload = FIXTURE.read_text(encoding="utf-8")
    projection = project_cms_partd_csv(
        payload,
        receipt=receipt(payload),
    )

    assert len(projection.records) == 2
    assert {record.concept.level for record in projection.records} == {
        "payer-plan-product"
    }
    first = projection.records[0]
    assert first.assertions[0].kind is AssertionKind.FORMULARY
    assert first.assertions[0].evidence_status is EvidenceStatus.UNKNOWN
    assert "plan=S1234:001" in first.assertions[0].restrictions
    assert "tier=2" in first.assertions[0].restrictions
    assert "retail_price_usd=12.34" in first.assertions[0].restrictions
    assert "scope=medicare-part-d-plan-not-national" in (
        first.assertions[0].restrictions
    )


@pytest.mark.unit
def test_cms_partd_confirms_only_qualifying_live_receipt() -> None:
    payload = FIXTURE.read_text(encoding="utf-8")
    projection = project_cms_partd_csv(
        payload,
        receipt=receipt(payload, live=True),
    )

    assert (
        projection.records[0].assertions[0].evidence_status
        is EvidenceStatus.CONFIRMED
    )


@pytest.mark.unit
def test_us_funding_context_explicitly_denies_a_single_national_list() -> None:
    payload = FIXTURE.read_text(encoding="utf-8")
    projection = project_cms_partd_csv(
        payload,
        receipt=receipt(payload),
    )

    assert not projection.funding_context.national_medicines_funding_list_exists
    assert projection.funding_context.coverage_unit == "payer-plan"
    assert "no single national medicines funding list" in (
        projection.funding_context.explanation
    )
    assert all(
        assertion.kind is not AssertionKind.FUNDING
        for record in projection.records
        for assertion in record.assertions
    )


@pytest.mark.edge
def test_missing_plan_identity_is_not_projected_as_negative_evidence() -> None:
    payload = (
        "contract_id,plan_id,ndc,drug_name,formulary_status,tier,"
        "retail_price_usd,prior_authorization,step_therapy\n"
        ",001,00011-1111-11,Example Drug,covered,2,12.34,false,false\n"
    )
    projection = project_cms_partd_csv(
        payload,
        receipt=receipt(payload),
    )

    assert projection.records == ()


@pytest.mark.edge
def test_cms_partd_rejects_tampered_payload() -> None:
    payload = FIXTURE.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="does not match receipt"):
        project_cms_partd_csv(payload + "\n", receipt=receipt(payload))


@pytest.mark.edge
@pytest.mark.parametrize(
    "bad_receipt",
    [
        receipt("payload", source_id="us-drugsfda"),
        receipt("payload", jurisdiction="NZL"),
        receipt("payload", method=AcquisitionMethod.LOCAL_FIXTURE),
    ],
)
def test_cms_partd_rejects_mismatched_receipt(
    bad_receipt: SourceReceipt,
) -> None:
    with pytest.raises(ValueError, match=r"receipt|acquisition"):
        project_cms_partd_csv("payload", receipt=bad_receipt)
