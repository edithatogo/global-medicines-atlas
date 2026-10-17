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

from global_medicines_atlas.adapters.au_mbs import MBS_NATIVE_FIELDS
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
_PRESENCE_BASELINE = (
    Path(__file__).resolve().parents[1]
    / "quality/qualifications/mbs-source-era-candidate-2026-08-01-presence-baseline.json"
)
_DMY_PROFILE = (
    Path(__file__).resolve().parents[1]
    / "quality/qualifications/mbs-source-era-candidate-2026-08-01-dmy-profile.json"
)
_LATEST_DIAGNOSTIC_PROFILE = (
    Path(__file__).resolve().parents[1]
    / "quality/qualifications/mbs-source-era-candidate-2026-08-01-run-39032003723.json"
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
    assert report["qualification"]["date_format"] == "mbs-dmy"
    assert report["field_semantics_accepted"] is False
    assert report["date_grammar_status"] == (
        "declared_grammar_profiled_candidate_only"
    )
    assert report["field_semantics_blockers"] == [
        "release_linked_field_semantics_version_history_unverified"
    ]
    assert report["candidate_blockers"] == [
        "release_linked_field_semantics_version_history_unverified",
        "public_v4_identity_unverified",
    ]
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
    qualified = {
        item["native_field"]: item
        for item in field_presence_diagnostics(
            payload, receipt, date_format="mbs-dmy"
        )
    }
    assert qualified["ItemStartDate"]["conversion_status_counts"] == {
        "converted": 1
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


def test_latest_exact_main_diagnostics_cover_all_fields_without_promotion() -> (
    None
):
    report_bytes = _LATEST_DIAGNOSTIC_PROFILE.read_bytes()
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
    diagnostics = report["field_presence_diagnostics"]

    assert report["exact_commit"] == "b5b4d3ce6e3400e0fdb84ab2b56854776c4878e6"
    assert report["official_release_match"] is True
    assert report["source_presence_projection_alignment"] == "matched"
    assert report["candidate_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert report["candidate_byte_count"] == len(canonical)
    assert hashlib.sha256(report_bytes).hexdigest() == (
        "35265bb883a6dde7f99e349a272c29a6592a65a160d096f05600091c455e90a2"
    )
    assert qualification.source_record_count == 6046
    assert {item["native_field"] for item in diagnostics} == set(
        MBS_NATIVE_FIELDS
    )
    assert len(diagnostics) == 40
    assert all(
        item["rows"] == 6046
        and item["presence_state_mismatches"] == 0
        and item["requiredness_accepted"] is False
        for item in diagnostics
    )
    assert report["field_semantics_accepted"] is False
    assert report["field_semantics_blockers"] == [
        "release_linked_field_semantics_version_history_unverified"
    ]
    assert report["date_grammar_status"] == (
        "declared_grammar_profiled_candidate_only"
    )
    assert report["m109_accepted"] is False
    assert report["public_v4_admission"] is False
    assert report["publication_performed"] is False
    assert report["source_bytes_retained"] is False
    assert "source_values" not in report


def test_august_presence_baseline_is_pinned_without_date_semantics() -> None:
    report_bytes = _PRESENCE_BASELINE.read_bytes()
    report = json.loads(report_bytes)
    core = {
        key: value
        for key, value in report.items()
        if key not in {"candidate_sha256", "candidate_byte_count"}
    }
    canonical = json.dumps(core, sort_keys=True, separators=(",", ":")).encode()

    assert report["exact_commit"] == "19420a008b8b33919aa4a837779e0fb6a15b4a88"
    assert report["qualification"]["date_format"] is None
    assert report["field_semantics_accepted"] is False
    assert report["source_presence_projection_alignment"] == "matched"
    assert len(report["field_presence_diagnostics"]) == 40
    assert all(
        item["presence_state_mismatches"] == 0
        for item in report["field_presence_diagnostics"]
    )
    assert report["candidate_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert report["candidate_byte_count"] == len(canonical)
    assert hashlib.sha256(report_bytes).hexdigest() == (
        "5af143a416918113ebb4dc2a625c3a14ab66015d413f7c7de92ee13a3995f181"
    )
    assert "source_values" not in report
    assert report["m109_accepted"] is False


def test_august_dmy_profile_is_historical_and_semantic_claim_is_superseded() -> (
    None
):
    report_bytes = _DMY_PROFILE.read_bytes()
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

    assert report["exact_commit"] == "a087acdfb935bb79f894ecd3f91530351f3faac8"
    assert report["official_release_match"] is True
    # Preserve the exact old hosted artifact, including its overclaim, as
    # historical evidence; the separate status record withdraws that claim.
    assert report["field_semantics_accepted"] is True
    assert (
        report["field_semantics_sha256"]
        == hashlib.sha256(
            (
                Path(__file__).resolve().parents[1]
                / "docs/qualification/mbs-xml-v3-field-semantics-2026-08.md"
            ).read_bytes()
        ).hexdigest()
    )
    assert qualification.date_format == "mbs-dmy"
    assert qualification.source_record_count == 6046
    assert sum(table.field_count for table in qualification.tables) == 40
    assert sum(
        table.field_occurrence_count for table in qualification.tables
    ) == (241840)
    assert qualification.blockers == ("public_v4_identity_unverified",)
    assert report["source_presence_projection_alignment"] == "matched"
    assert len(report["field_presence_diagnostics"]) == 40
    assert all(
        item["rows"] == 6046 and item["presence_state_mismatches"] == 0
        for item in report["field_presence_diagnostics"]
    )
    assert all(
        "unsupported_format" not in item["conversion_status_counts"]
        and "invalid" not in item["conversion_status_counts"]
        for item in report["field_presence_diagnostics"]
    )
    assert report["candidate_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert report["candidate_byte_count"] == len(canonical)
    assert hashlib.sha256(report_bytes).hexdigest() == (
        "8e8d14f88baabc10a172fd2ec3947f8a89947828d64fb0237398dc230896763e"
    )
    assert report["source_bytes_retained"] is False
    assert report["publication_performed"] is False
    assert report["m109_accepted"] is False
    status = (
        Path(__file__).resolve().parents[1]
        / "docs/qualification/mbs-xml-v3-field-semantics-status-2026-08.md"
    ).read_text(encoding="utf-8")
    assert "field_semantics_accepted` must remain\nfalse" in status
    assert "interpretation is superseded" in status


def test_august_field_semantics_bind_all_native_fields_and_date_grammar() -> (
    None
):
    document = (
        Path(__file__).resolve().parents[1]
        / "docs/qualification/mbs-xml-v3-field-semantics-2026-08.md"
    ).read_text(encoding="utf-8")

    assert all(f"`{field}`" in document for field in MBS_NATIVE_FIELDS)
    assert (
        "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565"
        in document
    )
    assert "6,046 source records" in document
    assert "241,840 field" in document
    assert "DD.MM.YYYY" in document
    assert "M-109 remains partial and blocked" in document
    status = (
        Path(__file__).resolve().parents[1]
        / "docs/qualification/mbs-xml-v3-field-semantics-status-2026-08.md"
    ).read_text(encoding="utf-8")
    assert "does not provide a release-linked" in status
