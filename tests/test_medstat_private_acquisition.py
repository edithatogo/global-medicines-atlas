"""Contracts for the hosted-only Medstat private retention path."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from scripts.acquire_medstat_private import (
    require_supported_query,
    validate_browser_download,
)

import global_medicines_atlas.medstat_private_acquisition as acquisition
from global_medicines_atlas.medstat_private_acquisition import (
    CHECKSUM,
    MANIFEST,
    PRIVATE_ARCHIVE,
    PRIVATE_DATASET,
    MedstatQuery,
    exercise_medstat_private_acquisition,
    require_authorized_medstat_query,
    require_medstat_authorization,
)
from global_medicines_atlas.reuse_gate import evaluate_reuse_gate
from global_medicines_atlas.source_catalog import load_source_catalog

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/nordic-utilisation-acquisition-authorization.json"
)


def workbook_payload() -> bytes:
    """Return a minimal structurally valid OOXML workbook fixture."""
    buffer = BytesIO()
    with ZipFile(buffer, "w") as workbook:
        workbook.writestr("[Content_Types].xml", "<Types />")
        workbook.writestr("_rels/.rels", "<Relationships />")
        workbook.writestr("xl/workbook.xml", "<workbook />")
        workbook.writestr("xl/worksheets/sheet1.xml", "<worksheet />")
    return buffer.getvalue()


def reuse_decision():
    return evaluate_reuse_gate(
        acquisition.SOURCE_ID,
        repository_root=ROOT,
        catalog=load_source_catalog(),
        github_index={},
        huggingface_index={},
    )


def test_query_binds_the_single_approved_aggregate_scope() -> None:
    query = MedstatQuery()
    assert query.source_parameters() == {
        "year": ["2025"],
        "region": ["0"],
        "gender": ["A"],
        "ageGroup": ["A"],
        "searchVariable": ["turnover"],
        "atcCode": ["X"],
        "sector": ["0", "1"],
    }
    assert query.export_url().startswith(
        "https://medstat.dk/da/viewDataTables/medicineAndMedicalGroups/"
        "exportToExcel/"
    )
    with pytest.raises(PermissionError, match="approved"):
        require_authorized_medstat_query(MedstatQuery(years=(2024,)))


def test_authorization_rejects_pending_or_public_scope(tmp_path: Path) -> None:
    document = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    denmark = document["sources"][0]
    denmark.update(
        decision_status="pending",
        decision_date=None,
        acquisition_authorized=False,
        internal_retention_authorized=False,
    )
    pending = tmp_path / "pending.json"
    pending.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PermissionError, match="pending"):
        require_medstat_authorization(pending)
    denmark.update(
        decision_status="approved_internal",
        decision_date="2026-09-13",
        acquisition_authorized=True,
        internal_retention_authorized=True,
        public_release_authorized=True,
    )
    public = tmp_path / "public.json"
    public.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="publication must remain"):
        require_medstat_authorization(public)


def test_browser_download_diagnostic_reports_only_bounded_metadata() -> None:
    with pytest.raises(RuntimeError) as caught:
        validate_browser_download(
            b"<html>synthetic-marker</html>",
            "response.xlsx",
            {"http_status": 200, "content_type": "text/html"},
        )

    message = str(caught.value)
    assert "filename_extension=.xlsx" in message
    assert "byte_count=29" in message
    assert "zip_signature_valid=False" in message
    assert "ole_signature_valid=False" in message
    assert "html_document=True" in message
    assert "html_table_count=0" in message
    assert "html_form_count=0" in message
    assert "html_input_count=0" in message
    assert "html_source_title_match=False" in message
    assert "http_status=200" in message
    assert "content_type=text/html" in message
    assert "synthetic-marker" not in message


def test_browser_download_diagnostic_classifies_html_structure_only() -> None:
    response = (
        b"<html><head><title>Medstat</title></head><body>"
        b"<form><input><select></select><button>do not report</button></form>"
        b"<table><tr><th>private heading</th></tr></table>"
        b"<iframe></iframe><script>private script</script><a href='/private'>x</a>"
        b"</body></html>"
    )
    with pytest.raises(RuntimeError) as caught:
        validate_browser_download(response, "response.xls")

    message = str(caught.value)
    assert "html_form_count=1" in message
    assert "html_input_count=1" in message
    assert "html_select_count=1" in message
    assert "html_iframe_count=1" in message
    assert "html_script_count=1" in message
    assert "html_link_count=0" in message
    assert "html_button_count=1" in message
    assert "html_source_title_match=True" in message
    assert "private heading" not in message
    assert "private script" not in message
    assert "/private" not in message


def test_browser_download_accepts_a_valid_workbook() -> None:
    payload = workbook_payload()
    assert validate_browser_download(payload, "medstat.xlsx") == payload


def test_query_preflight_requires_measure_support_in_each_sector() -> None:
    query = MedstatQuery()
    require_supported_query(
        query,
        {"0": {"turnover", "sold_volume"}, "1": {"turnover"}},
    )
    with pytest.raises(ValueError, match="sector code 2"):
        require_supported_query(
            MedstatQuery(sector=("0", "2")),
            {"0": {"turnover"}, "1": {"turnover"}, "2": {"sold_volume"}},
        )


def test_medstat_query_matches_observed_source_constraints() -> None:
    evidence = json.loads(
        (
            ROOT / "quality/qualifications/"
            "nordic-medstat-query-constraints-20260929.json"
        ).read_text(encoding="utf-8")
    )
    assert (
        MedstatQuery().source_parameters() == evidence["selected_bounded_query"]
    )
    require_supported_query(
        MedstatQuery(),
        {
            sector: set(variables)
            for sector, variables in evidence[
                "observed_search_variables"
            ].items()
        },
    )
    assert evidence["source_payload_retrieved"] is False
    assert evidence["acquisition_or_bronze_acceptance_claimed"] is False


def test_medstat_export_review_distinguishes_diagnostic_read_from_retention() -> (
    None
):
    evidence = json.loads(
        (
            ROOT / "quality/qualifications/"
            "nordic-medstat-export-format-doc-review-20260929.json"
        ).read_text(encoding="utf-8")
    )
    disposition = evidence["disposition"]
    assert (
        disposition["result_payload_bytes_read_for_bounded_diagnostic"] is True
    )
    assert disposition["result_payload_bytes_retained"] is False
    assert disposition["format_semantics_resolved"] is False

    request = (
        ROOT / "conductor/tracks/bronze_medallion_completion_20260819/"
        "medstat-export-format-request.md"
    ).read_text(encoding="utf-8")
    assert "transiently read the 4,446-byte response" in request
    assert "did not emit the response text or retain the bytes" in request
    assert (
        "We did not inspect or retain the response text or bytes" not in request
    )


def test_medstat_format_clarification_sent_receipt_is_bound_and_fail_closed() -> (
    None
):
    receipt = json.loads(
        (
            ROOT / "quality/qualifications/"
            "provider-outreach-receipts-20260929.json"
        ).read_text(encoding="utf-8")
    )
    message = next(
        item
        for item in receipt["messages"]
        if item.get("gmail_message_id") == "1a0e9ad775ff9a95"
    )
    acknowledgement = next(
        item
        for item in receipt["messages"]
        if item.get("gmail_message_id") == "1a0e9b780c580bd2"
    )
    review = json.loads(
        (
            ROOT / "quality/qualifications/"
            "nordic-medstat-export-format-doc-review-20260929.json"
        ).read_text(encoding="utf-8")
    )
    request = (
        ROOT / "conductor/tracks/bronze_medallion_completion_20260819/"
        "medstat-export-format-request.md"
    ).read_text(encoding="utf-8")

    assert message["gmail_message_id"] == "1a0e9ad775ff9a95"
    assert message["rfc_message_id"] == (
        "<CA+D7Coz0Q_6qHUQD83HqLZESurDopQw-F6JJNzzokYEDHVy7Uw@mail.gmail.com>"
    )
    assert message["recipient"] == "kontakt@sundhedsdata.dk"
    assert message["state"] == "sent_awaiting_provider_response"
    assert message["attachment_count"] == 0
    assert message["source_payloads_attached"] is False
    assert message["rights_scope_changed"] is False
    assert "acknowledgement" not in message
    assert acknowledgement["state"] == "automatic_reply_unbound"
    assert acknowledgement["rfc_message_id"] == (
        "<fb2defdacec34bf09b97d565714ad56d@VI1P189MB2515.EURP189.PROD.OUTLOOK.COM>"
    )
    assert acknowledgement["auto_submitted"] == "auto-generated"
    assert acknowledgement["substantive_guidance"] is False
    assert acknowledgement["request_correlation_verified"] is False
    assert (
        acknowledgement["in_reply_to_message_id"] != message["rfc_message_id"]
    )
    assert (
        review["disposition"]["provider_acknowledgement"]["gmail_message_id"]
        == acknowledgement["gmail_message_id"]
    )
    assert (
        review["disposition"]["provider_acknowledgement"][
            "request_correlation_verified"
        ]
        is False
    )
    evidence = [
        json.loads(line)
        for line in (
            ROOT / "conductor/tracks/bronze_medallion_completion_20260819/"
            "evidence.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    correction = next(
        item
        for item in reversed(evidence)
        if item["kind"] == "nordic_medstat_auto_reply_correlation_correction"
    )
    assert correction["request_correlation_verified"] is False
    assert (
        "nordic_medstat_provider_automatic_acknowledgement"
        in correction["supersedes_evidence_kinds"]
    )
    assert (
        correction["raw_in_reply_to_message_id"]
        == acknowledgement["in_reply_to_message_id"]
    )
    assert (
        receipt["verification"][
            "new_medstat_format_inquiry_recipient_subject_and_message_id_readback"
        ]
        is True
    )
    assert (
        receipt["verification"][
            "unbound_medstat_auto_reply_from_official_contact_observed"
        ]
        is True
    )
    assert review["disposition"]["format_semantics_resolved"] is False
    assert review["disposition"]["html_result_parser_implemented"] is False
    assert (
        review["disposition"]["provider_request"]["gmail_message_id"]
        == message["gmail_message_id"]
    )
    assert (
        review["disposition"]["provider_request"]["rfc_message_id"]
        == message["rfc_message_id"]
    )
    assert "awaiting substantive provider response" in request
    assert "No attachments or source result payloads" in request


def test_private_acquisition_lands_recovers_and_archives(
    tmp_path: Path,
) -> None:
    result = exercise_medstat_private_acquisition(
        payload=workbook_payload(),
        output_dir=tmp_path / "output",
        authorization_path=AUTHORIZATION,
        observed_at=datetime(2026, 9, 13, tzinfo=UTC),
        reuse_decision=reuse_decision(),
    )
    assert result.private_dataset == PRIVATE_DATASET
    assert result.public_release_authorized is False
    assert result.external_publication_authorized is False
    assert result.clean_room_recovered_payload_count == 1
    assert (tmp_path / "output" / PRIVATE_ARCHIVE).is_file()
    assert (tmp_path / "output" / MANIFEST).is_file()
    assert (tmp_path / "output" / CHECKSUM).is_file()


def test_private_acquisition_rejects_empty_payload_and_unsafe_output(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="empty"):
        exercise_medstat_private_acquisition(
            payload=b"",
            output_dir=tmp_path / "empty",
            authorization_path=AUTHORIZATION,
            reuse_decision=reuse_decision(),
        )
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "prior.txt").write_text("prior", encoding="utf-8")
    with pytest.raises(FileExistsError, match="empty"):
        exercise_medstat_private_acquisition(
            payload=b"payload",
            output_dir=occupied,
            authorization_path=AUTHORIZATION,
            reuse_decision=reuse_decision(),
        )


def test_private_acquisition_rejects_naive_time_and_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        exercise_medstat_private_acquisition(
            payload=workbook_payload(),
            output_dir=tmp_path / "naive",
            authorization_path=AUTHORIZATION,
            observed_at=datetime.fromisoformat("2026-09-13T00:00:00"),
            reuse_decision=reuse_decision(),
        )

    def rejected_landing(*_: object, **__: object) -> object:
        return object()

    monkeypatch.setattr(
        acquisition,
        "land_bronze_payload",
        rejected_landing,
    )
    with pytest.raises(TypeError, match="not admitted"):
        exercise_medstat_private_acquisition(
            payload=workbook_payload(),
            output_dir=tmp_path / "rejected",
            authorization_path=AUTHORIZATION,
            observed_at=datetime(2026, 9, 13, tzinfo=UTC),
            reuse_decision=reuse_decision(),
        )


def test_private_acquisition_rejects_non_workbook_and_missing_reuse_gate(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="OOXML"):
        exercise_medstat_private_acquisition(
            payload=b"synthetic Medstat Excel export",
            output_dir=tmp_path / "opaque",
            authorization_path=AUTHORIZATION,
            observed_at=datetime(2026, 9, 13, tzinfo=UTC),
            reuse_decision=reuse_decision(),
        )
    arbitrary_zip = BytesIO()
    with ZipFile(arbitrary_zip, "w") as archive:
        archive.writestr("response.html", "<html>not a workbook</html>")
    with pytest.raises(ValueError, match="required OOXML"):
        exercise_medstat_private_acquisition(
            payload=arbitrary_zip.getvalue(),
            output_dir=tmp_path / "arbitrary-zip",
            authorization_path=AUTHORIZATION,
            observed_at=datetime(2026, 9, 13, tzinfo=UTC),
            reuse_decision=reuse_decision(),
        )
    with pytest.raises(PermissionError, match="approved"):
        exercise_medstat_private_acquisition(
            payload=workbook_payload(),
            output_dir=tmp_path / "custom-query",
            authorization_path=AUTHORIZATION,
            observed_at=datetime(2026, 9, 13, tzinfo=UTC),
            query=MedstatQuery(years=(2024,)),
            reuse_decision=reuse_decision(),
        )
    with pytest.raises(ValueError, match="reuse gate required"):
        exercise_medstat_private_acquisition(
            payload=workbook_payload(),
            output_dir=tmp_path / "missing-reuse",
            authorization_path=AUTHORIZATION,
            observed_at=datetime(2026, 9, 13, tzinfo=UTC),
        )
