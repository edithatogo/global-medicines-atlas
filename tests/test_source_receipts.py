from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    FailureReceipt,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)

NOW = datetime(2026, 7, 29, 1, 2, 3, tzinfo=UTC)
SHA_A = "a" * 64
SHA_B = "b" * 64


def source_identity() -> SourceIdentity:
    return SourceIdentity(
        catalog_id="nz-medsafe-products",
        source_id="medsafe-product-register",
        jurisdiction="NZ",
        authority="Medsafe",
        dataset_title="Product/Application Search",
        catalog_version="2026-07-29",
    )


def retrieval(
    *,
    status: AcquisitionStatus = AcquisitionStatus.SUCCEEDED,
) -> RetrievalEvidence:
    return RetrievalEvidence(
        uri="https://www.medsafe.govt.nz/regulatory/dbsearch.asp",
        retrieved_at=NOW,
        acquisition_method=AcquisitionMethod.DOWNLOAD,
        status=status,
    )


def payload() -> PayloadEvidence:
    return PayloadEvidence(sha256=SHA_A, byte_count=128)


def transformation() -> TransformationEvidence:
    return TransformationEvidence(
        transformation_id="medsafe-products-v1",
        transformation_sha256=SHA_B,
        output_sha256="c" * 64,
        output_byte_count=96,
    )


def source_receipt(
    *,
    evidence_class: EvidenceClass = EvidenceClass.LIVE,
) -> SourceReceipt:
    return SourceReceipt(
        receipt_id="receipt-nz-medsafe-20260729",
        source=source_identity(),
        retrieval=retrieval(),
        payload=payload(),
        effective_from=NOW - timedelta(days=1),
        effective_to=None,
        rights_state=RightsState.PERMITTED,
        rights_reference="https://www.medsafe.govt.nz/other/copyright.asp",
        evidence_class=evidence_class,
        transformation=transformation(),
    )


@pytest.mark.unit
def test_success_receipt_preserves_governed_evidence() -> None:
    receipt = source_receipt()

    assert receipt.source.jurisdiction == "NZ"
    assert receipt.payload.byte_count == 128
    assert receipt.transformation.output_sha256 == "c" * 64
    assert receipt.satisfies_live_gate


@pytest.mark.unit
@pytest.mark.parametrize(
    "evidence_class",
    [
        EvidenceClass.FIXTURE,
        EvidenceClass.SYNTHETIC,
        EvidenceClass.DRY_RUN,
        EvidenceClass.UNAVAILABLE,
    ],
)
def test_non_live_evidence_never_satisfies_live_gate(
    evidence_class: EvidenceClass,
) -> None:
    assert not source_receipt(evidence_class=evidence_class).satisfies_live_gate


@pytest.mark.unit
def test_receipts_are_deeply_immutable() -> None:
    receipt = source_receipt()

    with pytest.raises(ValidationError):
        receipt.rights_state = RightsState.UNKNOWN
    with pytest.raises(ValidationError):
        receipt.source.authority = "Changed"


@pytest.mark.unit
def test_canonical_json_and_digest_are_order_independent() -> None:
    receipt = source_receipt()
    rebuilt = SourceReceipt.model_validate(
        dict(reversed(list(receipt.model_dump(mode="json").items())))
    )

    assert receipt.canonical_json() == rebuilt.canonical_json()
    assert receipt.digest() == rebuilt.digest()
    assert receipt.digest() == receipt.digest()


@pytest.mark.edge
@pytest.mark.parametrize("digest", ["A" * 64, "a" * 63, "g" * 64, ""])
def test_payload_rejects_noncanonical_sha256(digest: str) -> None:
    with pytest.raises(ValidationError):
        PayloadEvidence(sha256=digest, byte_count=1)


@pytest.mark.edge
def test_receipt_rejects_naive_retrieval_clock() -> None:
    values = retrieval().model_dump()
    # ruff: ignore[call-datetime-without-tzinfo]
    values["retrieved_at"] = datetime(2026, 7, 29)

    with pytest.raises(ValidationError):
        RetrievalEvidence.model_validate(values)


@pytest.mark.edge
def test_receipt_rejects_inverted_effective_interval() -> None:
    with pytest.raises(ValidationError):
        SourceReceipt(
            receipt_id="invalid-time",
            source=source_identity(),
            retrieval=retrieval(),
            payload=payload(),
            effective_from=NOW,
            effective_to=NOW - timedelta(seconds=1),
            rights_state=RightsState.UNKNOWN,
            evidence_class=EvidenceClass.LIVE,
            transformation=transformation(),
        )


@pytest.mark.edge
def test_success_receipt_requires_payload_and_transformation() -> None:
    common = {
        "receipt_id": "missing-evidence",
        "source": source_identity(),
        "retrieval": retrieval(),
        "effective_from": NOW,
        "rights_state": RightsState.UNKNOWN,
        "evidence_class": EvidenceClass.LIVE,
    }

    with pytest.raises(ValidationError):
        SourceReceipt(**common)


@pytest.mark.unit
def test_failure_receipt_is_explicit_and_cannot_pass_live_gate() -> None:
    receipt = FailureReceipt(
        receipt_id="failure-nz-medsafe-20260729",
        source=source_identity(),
        retrieval=retrieval(status=AcquisitionStatus.FAILED),
        evidence_class=EvidenceClass.UNAVAILABLE,
        rights_state=RightsState.UNKNOWN,
        failure_code="timeout",
        failure_message="The source did not respond before the deadline.",
        retryable=True,
    )

    assert not receipt.satisfies_live_gate
    assert receipt.failure_code == "timeout"
    assert receipt.digest() == receipt.digest()


@pytest.mark.edge
def test_failure_receipt_rejects_success_status_and_live_class() -> None:
    with pytest.raises(ValidationError):
        FailureReceipt(
            receipt_id="invalid-failure",
            source=source_identity(),
            retrieval=retrieval(),
            evidence_class=EvidenceClass.LIVE,
            rights_state=RightsState.UNKNOWN,
            failure_code="none",
            failure_message="Not actually a failure.",
        )


@pytest.mark.property
@given(st.binary(max_size=4096))
def test_payload_digest_contract_accepts_any_payload_bytes(data: bytes) -> None:
    evidence = PayloadEvidence.from_bytes(data)

    assert evidence.byte_count == len(data)
    assert len(evidence.sha256) == 64
    assert evidence.matches(data)
    assert not evidence.matches(data + b"x")


@pytest.mark.property
@given(
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cc", "Cs"),
            blacklist_characters=("\x00",),
        ),
        min_size=1,
        max_size=40,
    )
)
def test_receipt_digest_changes_when_identity_changes(source_id: str) -> None:
    baseline = source_receipt()
    changed = baseline.model_copy(
        update={"source": baseline.source.model_copy(update={"source_id": source_id})}
    )

    if source_id != baseline.source.source_id:
        assert changed.digest() != baseline.digest()
