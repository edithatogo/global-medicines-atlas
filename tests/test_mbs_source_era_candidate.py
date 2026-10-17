import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyUrl
from scripts import qualify_mbs_source_era_candidate as command
from scripts.qualify_mbs_source_era_candidate import (
    field_presence_diagnostics,
    qualify_candidate,
)

from global_medicines_atlas.mbs_silver_qualification import (
    MbsSilverQualification,
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

_URI = (
    "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/"
    "650f3eec0dfb990fca25692100069854/"
    "81efb2067580a870ca258e28007f588c/"
    "$FILE/MBS-XML-20260801.XML"
)
_RECORDED_PROFILE = (
    Path(__file__).resolve().parents[1]
    / "quality/qualifications/mbs-source-era-candidate-2026-08-01.json"
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
    assert report["source_presence_projection_alignment"] == "matched"
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


def test_field_presence_diagnostics_distinguish_missing_from_parser_loss() -> (
    None
):
    payload = b"""<MBS_XML><Data><ItemNum>00123</ItemNum>
      <ItemStartDate>01.08.2026</ItemStartDate></Data></MBS_XML>"""
    receipt = _receipt(payload)
    diagnostics = {
        item["native_field"]: item
        for item in field_presence_diagnostics(payload, receipt)
    }

    assert diagnostics["ItemNum"]["source_present"] == 1
    assert diagnostics["ItemNum"]["projected_states"] == {"value": 1}
    assert diagnostics["ItemNum"]["conversion_status_counts"] == {
        "preserved": 1
    }
    assert diagnostics["ItemNum"]["presence_state_mismatches"] == 0
    assert diagnostics["ItemStartDate"]["source_present"] == 1
    assert diagnostics["ItemStartDate"]["projected_states"] == {"value": 1}
    assert diagnostics["ItemStartDate"]["conversion_status_counts"] == {
        "unsupported_format": 1
    }
    assert diagnostics["ItemStartDate"]["presence_state_mismatches"] == 0
    assert diagnostics["Benefit75"]["source_present"] == 0
    assert diagnostics["Benefit75"]["projected_states"] == {"missing_field": 1}
    assert diagnostics["Benefit75"]["presence_state_mismatches"] == 0
    assert diagnostics["Benefit75"]["requiredness_accepted"] is False


def test_committed_august_candidate_profile_is_pinned_and_value_free() -> None:
    report_bytes = _RECORDED_PROFILE.read_bytes()
    report = json.loads(report_bytes)
    qualification = MbsSilverQualification.model_validate(
        report["qualification"]
    )
    core = {
        key: value
        for key, value in report.items()
        if key not in {"candidate_sha256", "candidate_byte_count"}
    }
    canonical = json.dumps(core, sort_keys=True, separators=(",", ":")).encode()

    assert report["exact_commit"] == "b566e9980fd14d9d94caa7235002af94f6f53533"
    assert report["official_release_match"] is True
    assert report["candidate_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert report["candidate_byte_count"] == len(canonical)
    assert hashlib.sha256(report_bytes).hexdigest() == (
        "f6703c0bbc17ed529dbb7e32b696b9551fc6b6ad7500acb8318935bca02b5d39"
    )
    assert qualification.source_record_count == 6046
    assert sum(table.field_count for table in qualification.tables) == 40
    assert (
        sum(table.field_occurrence_count for table in qualification.tables)
        == 241840
    )
    assert qualification.blockers == (
        "public_v4_identity_unverified",
        "quality_findings_present",
    )
    assert report["field_semantics_accepted"] is False
    assert report["m109_accepted"] is False
