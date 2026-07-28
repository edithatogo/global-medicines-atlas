"""Representative native-format contracts for Japanese medicine sources."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyUrl

from global_medicines_atlas.adapters.japan import (
    MHLW_NHI_FIELD_MAPPINGS,
    PMDA_FIELD_MAPPINGS,
    TRANSLATION_REVIEW_GATE,
    project_mhlw_nhi_price_csv,
    project_pmda_approval_csv,
)
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

FIXTURES = Path(__file__).parent / "fixtures" / "native" / "jp"
SHA = "b" * 64
Projector = Callable[[bytes, SourceReceipt], tuple[object, ...]]


def _receipt(payload: bytes, *, source_id: str) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id=f"fixture:{source_id}",
        source=SourceIdentity(
            catalog_id=source_id,
            source_id=source_id,
            jurisdiction="JPN",
            authority="Synthetic Japanese source fixture",
            dataset_title=f"Synthetic {source_id} native-format fixture",
            catalog_version="fixture-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(f"https://fixtures.invalid/{source_id}"),
            retrieved_at=datetime(2026, 7, 29, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id=f"{source_id}-fixture",
            transformation_sha256=SHA,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def test_pmda_native_fixture_projects_regulatory_evidence() -> None:
    payload = (FIXTURES / "pmda_approvals.csv").read_bytes()
    records = project_pmda_approval_csv(
        payload,
        _receipt(payload, source_id="jp-pmda"),
    )

    assertion = records[0].assertions[0]
    assert records[0].concept.preferred_name == "試験薬錠10mg"
    assert assertion.kind is AssertionKind.REGULATORY
    assert assertion.status_code == "approved"
    assert assertion.evidence_status is EvidenceStatus.UNKNOWN
    assert "source-approval-category:新医薬品" in assertion.restrictions
    assert TRANSLATION_REVIEW_GATE in assertion.restrictions


def test_mhlw_native_fixture_projects_only_funding_evidence() -> None:
    payload = (FIXTURES / "mhlw_nhi_prices.csv").read_bytes()
    records = project_mhlw_nhi_price_csv(
        payload,
        _receipt(payload, source_id="jp-mhlw-nhi"),
    )

    assertion = records[0].assertions[0]
    assert records[0].concept.preferred_name == "試験薬錠10mg"
    assert assertion.kind is AssertionKind.FUNDING
    assert assertion.status_code == "nhi-listed"
    assert assertion.evidence_status is EvidenceStatus.UNKNOWN
    assert "source-listing-category:新規収載" in assertion.restrictions
    assert "listed-price-jpy:123.40" in assertion.restrictions
    assert TRANSLATION_REVIEW_GATE in assertion.restrictions


def test_reviewed_field_mappings_are_explicit() -> None:
    assert PMDA_FIELD_MAPPINGS["承認番号"] == "approval_number"
    assert MHLW_NHI_FIELD_MAPPINGS["薬価"] == "listed_price_yen"


@pytest.mark.parametrize(
    ("fixture_name", "source_id", "projector"),
    [
        ("pmda_approvals.csv", "jp-pmda", project_pmda_approval_csv),
        (
            "mhlw_nhi_prices.csv",
            "jp-mhlw-nhi",
            project_mhlw_nhi_price_csv,
        ),
    ],
)
def test_native_adapter_rejects_tampered_payload(
    fixture_name: str,
    source_id: str,
    projector: Projector,
) -> None:
    payload = (FIXTURES / fixture_name).read_bytes()
    receipt = _receipt(payload, source_id=source_id)

    with pytest.raises(ValueError, match="does not match"):
        projector(payload + b"\n", receipt)


def test_pmda_rejects_missing_native_header() -> None:
    payload = (
        (FIXTURES / "pmda_approvals.csv")
        .read_bytes()
        .replace(
            "承認区分".encode(),
            "区分".encode(),
        )
    )
    with pytest.raises(ValueError, match="missing native fields"):
        project_pmda_approval_csv(
            payload,
            _receipt(payload, source_id="jp-pmda"),
        )


def test_mhlw_rejects_negative_price() -> None:
    payload = (
        (FIXTURES / "mhlw_nhi_prices.csv")
        .read_bytes()
        .replace(
            b"123.40",
            b"-1.00",
        )
    )
    with pytest.raises(ValueError, match="must not be negative"):
        project_mhlw_nhi_price_csv(
            payload,
            _receipt(payload, source_id="jp-mhlw-nhi"),
        )


def test_pmda_rejects_blank_required_source_label() -> None:
    payload = (
        (FIXTURES / "pmda_approvals.csv")
        .read_bytes()
        .replace(
            "試験薬錠10mg".encode(),
            b"",
        )
    )
    with pytest.raises(ValueError, match="Missing required PMDA field"):
        project_pmda_approval_csv(
            payload,
            _receipt(payload, source_id="jp-pmda"),
        )


def test_pmda_rejects_invalid_approval_date() -> None:
    payload = (
        (FIXTURES / "pmda_approvals.csv")
        .read_bytes()
        .replace(
            b"2026-04-01",
            b"not-a-date",
        )
    )
    with pytest.raises(ValueError, match="expected YYYY-MM-DD"):
        project_pmda_approval_csv(
            payload,
            _receipt(payload, source_id="jp-pmda"),
        )


def test_mhlw_rejects_non_numeric_price() -> None:
    payload = (
        (FIXTURES / "mhlw_nhi_prices.csv")
        .read_bytes()
        .replace(
            b"123.40",
            b"not-a-price",
        )
    )
    with pytest.raises(ValueError, match="must be numeric"):
        project_mhlw_nhi_price_csv(
            payload,
            _receipt(payload, source_id="jp-mhlw-nhi"),
        )
