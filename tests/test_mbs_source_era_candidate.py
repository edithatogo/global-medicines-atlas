from datetime import UTC, datetime

import pytest
from pydantic import AnyUrl
from scripts import qualify_mbs_source_era_candidate as command
from scripts.qualify_mbs_source_era_candidate import qualify_candidate

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

_URI = (
    "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/"
    "650f3eec0dfb990fca25692100069854/"
    "81efb2067580a870ca258e28007f588c/"
    "$FILE/MBS-XML-20260801.XML"
)


def _receipt(payload: bytes) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id="mbs-release:test-2026-08-01",
        source=SourceIdentity(
            catalog_id="au-mbs",
            source_id="au-mbs",
            jurisdiction="AUS",
            authority="Australian Government Department of Health",
            dataset_title="Medicare Benefits Schedule XML releases",
            catalog_version="2026-08-01",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(_URI),
            retrieved_at=datetime(2026, 10, 4, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl(
            "https://github.com/edithatogo/global-medicines-atlas/issues/339#issuecomment-5467052330"
        ),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="raw-acquisition-v1",
            transformation_sha256="a" * 64,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def test_candidate_binds_archive_payload_to_exact_official_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"<MBS_XML><Data><ItemNum>00123</ItemNum></Data></MBS_XML>"
    receipt = _receipt(payload)
    monkeypatch.setattr(command, "RELEASE_SHA256", receipt.payload.sha256)
    monkeypatch.setattr(command, "RELEASE_BYTE_COUNT", len(payload))
    report = qualify_candidate(
        payload=payload,
        receipt=receipt,
        official_payload=payload,
        compared_at=datetime(2026, 10, 17, tzinfo=UTC),
        exact_commit="a" * 40,
    )

    assert report["status"] == "candidate_only"
    assert report["source_era"] == "2026-08-01"
    assert report["official_release_match"] is True
    assert report["exact_commit"] == "a" * 40
    assert report["qualification"]["source_record_count"] == 1
    assert report["qualification"]["blockers"] == [
        "public_v4_identity_unverified"
    ]
    assert report["field_semantics_accepted"] is False
    assert report["m109_accepted"] is False


def test_candidate_rejects_official_payload_that_differs_from_b1_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"<MBS_XML><Data><ItemNum>00123</ItemNum></Data></MBS_XML>"
    receipt = _receipt(payload)
    monkeypatch.setattr(command, "RELEASE_SHA256", receipt.payload.sha256)
    monkeypatch.setattr(command, "RELEASE_BYTE_COUNT", len(payload))

    with pytest.raises(ValueError, match="official source differs from B1"):
        qualify_candidate(
            payload=payload,
            receipt=receipt,
            official_payload=payload + b" ",
            compared_at=datetime(2026, 10, 17, tzinfo=UTC),
            exact_commit="a" * 40,
        )
