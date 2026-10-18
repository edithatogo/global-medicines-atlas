"""Bounded MBS official-page chronology evidence checks."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    import pytest

from scripts import qualify_mbs_current_release_page_chronology as chronology

REPORT = Path(
    "quality/qualifications/australian-mbs-current-release-page-chronology-20261018.json"
)
REGISTER = Path("docs/qualification/australian-m109-source-era-register.md")


def _report() -> dict[str, Any]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_date_mentions_preserve_text_without_assigning_unstated_semantics() -> (
    None
):
    mentions = chronology.extract_date_mentions(
        "The change was made from 1 July 2020. File updated on 7 August 2020."
    )

    assert mentions == [
        {"cue": "unclassified", "date_text": "1 July 2020"},
        {"cue": "File updated on", "date_text": "7 August 2020"},
    ]


def test_matching_rows_requires_exact_source_url_and_keeps_no_row_text() -> (
    None
):
    page_url = "https://www.mbsonline.gov.au/Downloads-test"
    source_url = "https://www.mbsonline.gov.au/file/MBS-XML-20260701.XML"
    html = f"""<table><tr><td>XML</td><td><a href="{source_url}">
    MBS XML 20260701</a></td><td>File released on 28 May 2026</td>
    </tr></table>""".encode()

    matches = chronology.match_official_rows(html, page_url, [source_url])

    assert len(matches[source_url]) == 1
    row = matches[source_url][0]
    assert row["link_label"] == "MBS XML 20260701"
    assert row["date_mentions"] == [
        {"cue": "File released on", "date_text": "28 May 2026"}
    ]
    assert "row_text" not in row


def test_limited_stream_stops_after_first_oversize_chunk() -> None:
    def chunks():
        yield b"1234"
        yield b"56"
        raise AssertionError("stream must stop after exceeding the limit")

    body, observed, complete = chronology.collect_limited(chunks(), 4)

    assert body == b"1234"
    assert observed == 6
    assert complete is False


def test_unavailable_page_preserves_expected_source_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_read(_url: str, _max_bytes: int) -> chronology.BoundedHTTPResponse:
        raise chronology.httpx.ConnectError("offline")

    monkeypatch.setattr(chronology, "_bounded_get", fail_read)
    page = {
        "page_id": "Downloads-test",
        "url": "https://www.mbsonline.gov.au/Downloads-test",
        "resources": [
            {
                "source_url": "https://www.mbsonline.gov.au/MBS-test.XML",
                "filename": "MBS-test.XML",
                "matching_archive_receipts": [
                    {
                        "receipt_path": "receipts/test.json",
                        "archive_path": "raw/test.XML",
                        "payload_sha256": "a" * 64,
                    }
                ],
            }
        ],
    }

    result = chronology.read_page(
        page, ["https://www.mbsonline.gov.au/MBS-test.XML"]
    )

    assert result["status"] == "unavailable"
    assert result["resources"][0]["source_url"].endswith("MBS-test.XML")
    assert result["resources"][0]["page_observation_status"] == "unavailable"
    assert result["resources"][0]["archive_receipts"][0]["receipt_path"] == (
        "receipts/test.json"
    )


def test_report_digest_is_valid() -> None:
    report = _report()
    digest = cast("dict[str, str]", report["digest"])
    expected_digest = digest.pop("value")
    canonical = json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == expected_digest


def test_report_reconciles_current_index_and_receipt_only_links() -> None:
    report = _report()
    scope = cast("dict[str, Any]", report["scope"])
    assert report["status"] == (
        "current_index_links_bound_to_official_rows_and_current_receipts_history_incomplete"
    )
    assert scope["official_pages_observed"] == scope["official_pages_expected"]
    assert scope["current_index_xml_links"] == 82
    assert scope["archive_receipt_only_links"] == 5
    assert scope["official_page_link_rows_observed"] == 87
    assert scope["archive_receipt_sources_without_unique_official_row"] == 0
    assert scope["exactly_one_official_row_matched"] == 87
    assert scope["unresolved_or_ambiguous_rows"] == 0
    assert len(scope["archive_revision"]) == 40
    assert scope["current_receipt_sidecars_verified"] == 87
    assert scope["current_receipt_sidecars_unresolved"] == 0
    assert scope["resource_receipt_bindings_expected"] == 87
    assert scope["resource_receipt_bindings_verified"] == 87
    assert scope["resource_receipt_bindings_unresolved"] == 0
    assert scope["expected_historical_denominator_complete"] is False
    assert scope["m109_accepted"] is False
    assert scope["source_payloads_requested"] is False
    assert scope["source_payloads_read"] is False
    assert scope["html_bodies_retained"] is False

    archive = cast("dict[str, Any]", report["archive_readback"])
    assert archive["dataset"] == "edithatogo/australian-mbs-source-archive"
    assert archive["status"] == "exact_current_revision_receipts_verified"
    assert archive["anonymous"] is True
    assert archive["private"] is False
    assert archive["gated"] is False
    assert archive["receipt_sidecars_expected"] == 87
    assert archive["receipt_sidecars_verified"] == 87
    assert archive["receipt_sidecars_unresolved"] == 0
    assert all(
        receipt["status"] == "exact_current_receipt"
        for receipt in archive["receipt_sidecars"]
    )


def test_page_inputs_reconciles_receipt_only_urls_outside_current_index() -> (
    None
):
    pages, expected_urls, unresolved = chronology._page_inputs(_index())
    resources = [
        resource for page in pages.values() for resource in page["resources"]
    ]
    current_index = [
        resource
        for resource in resources
        if resource["source_scope"] == "current_index_xml"
    ]
    receipt_only = [
        resource
        for resource in resources
        if resource["source_scope"]
        == "archive_receipt_only_not_selected_current_xml_index"
    ]

    assert len(current_index) == 82
    assert len(receipt_only) == 5
    assert len({resource["source_url"] for resource in resources}) == 87
    assert len(unresolved) == 0
    assert sum(len(urls) for urls in expected_urls.values()) == 87
    assert {resource["page_id"] for resource in receipt_only} == {
        "Downloads-210701",
        "Downloads-211101",
        "Downloads-220101",
        "Downloads-220301",
        "Downloads-220401",
    }
    assert all(
        len(resource["matching_archive_receipts"]) == 1
        for resource in receipt_only
    )


def test_page_inputs_preserves_unmapped_receipt_source_as_unresolved() -> None:
    index = deepcopy(_index())
    omitted_url = next(
        receipt["source_url"]
        for receipt in index["current_public_archive"]["receipts"]
        if receipt["source_url"]
        not in {
            resource["source_url"]
            for resource in index["monthly_schedule_xml_index_reconciliation"][
                "resources"
            ]
        }
    )
    for page in index["downloads_index"]["pages"]:
        page["resources"] = [
            resource
            for resource in page["resources"]
            if resource["url"] != omitted_url
        ]

    _pages, _expected_urls, unresolved = chronology._page_inputs(index)

    assert len(unresolved) == 1
    assert unresolved[0]["source_url"] == omitted_url
    assert (
        unresolved[0]["unresolved_reason"] == "no_official_downloads_index_row"
    )
    assert len(unresolved[0]["matching_archive_receipts"]) == 1


def test_public_archive_failure_is_recorded_as_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_metadata_read(_url: str) -> dict[str, Any]:
        raise ValueError("malformed public metadata")

    monkeypatch.setattr(chronology, "_read_json_metadata", fail_metadata_read)
    result = chronology.read_current_archive_receipts({
        "current_public_archive": {"receipts": [{"receipt_path": "a"}]}
    })

    assert result["status"] == "unavailable_or_invalid"
    assert result["failure_class"] == "ValueError"
    assert result["receipt_sidecars_expected"] == 1
    assert result["receipt_sidecars_verified"] == 0
    assert result["receipt_sidecars_unresolved"] == 1


def test_missing_resource_receipt_fails_the_per_resource_binding() -> None:
    resources: list[dict[str, Any]] = [
        {
            "source_url": "https://www.mbsonline.gov.au/MBS-test.XML",
            "archive_receipts": [{"receipt_path": "receipts/missing.json"}],
        },
        {
            "source_url": "https://www.mbsonline.gov.au/MBS-empty.XML",
            "archive_receipts": [],
        },
        {
            "source_url": "https://www.mbsonline.gov.au/MBS-mismatch.XML",
            "archive_receipts": [
                {
                    "receipt_path": "receipts/mismatch.json",
                    "archive_path": "raw/mismatch.XML",
                    "payload_sha256": "a" * 64,
                }
            ],
        },
    ]

    result = chronology.bind_current_receipts(
        resources,
        {
            "revision": "b" * 40,
            "receipt_sidecars": [
                {
                    "receipt_path": "receipts/mismatch.json",
                    "status": "exact_current_receipt",
                    "source_url": "https://www.mbsonline.gov.au/OTHER.XML",
                    "archive_path": "raw/mismatch.XML",
                    "payload_sha256": "a" * 64,
                    "receipt": {"sha256": "c" * 64},
                }
            ],
        },
    )

    assert result == {"expected": 3, "verified": 0, "unresolved": 3}
    assert resources[0]["current_receipt_binding_status"] == (
        "current_receipts_unresolved"
    )
    assert resources[1]["current_receipt_binding_status"] == (
        "invalid_receipt_mapping"
    )
    assert resources[2]["current_receipt_binding_status"] == (
        "current_receipts_unresolved"
    )
    assert (
        chronology.qualification_status(
            0,
            0,
            0,
            result["unresolved"],
            "exact_current_revision_receipts_verified",
        )
        == "incomplete_official_page_observation"
    )


def _index() -> dict[str, Any]:
    path = Path(
        "quality/qualifications/australian-mbs-official-index-reconciliation-20261017.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_page_receipts_match_the_bound_official_index() -> None:
    report = _report()
    index = _index()
    pages = cast("list[dict[str, Any]]", report["pages"])
    index_path = Path(
        "quality/qualifications/australian-mbs-official-index-reconciliation-20261017.json"
    )
    input_record = cast("dict[str, str]", report["inputs"][0])
    expected_pages = {
        page["page_id"]: page for page in index["downloads_index"]["pages"]
    }

    assert input_record["path"] == index_path.as_posix()
    assert (
        input_record["sha256"]
        == hashlib.sha256(index_path.read_bytes()).hexdigest()
    )
    assert len(pages) == 41
    for page in pages:
        expected = expected_pages[page["page_id"]]
        assert page["page_url"] == expected["url"]
        assert page["page_label"] == expected["label"]
        assert page["status"] == "observed"
        receipt = page["page_receipt"]
        assert receipt["http_status"] == 200
        assert receipt["content_type"].startswith("text/html")
        assert receipt["body_retained"] is False
        assert receipt["observed_bytes"] <= 2_000_000
        assert len(receipt["sha256"]) == 64
        started = datetime.fromisoformat(receipt["client_request_started_at"])
        completed = datetime.fromisoformat(
            receipt["client_response_received_at"]
        )
        assert started <= completed


def test_source_rows_bind_to_current_receipts_without_source_values() -> None:
    report = _report()
    index = _index()
    pages = cast("list[dict[str, Any]]", report["pages"])
    resources = [
        resource
        for page in pages
        for resource in cast("list[dict[str, Any]]", page["resources"])
    ]
    archive = cast("dict[str, Any]", report["archive_readback"])
    expected_resources = {
        resource["source_url"]: resource
        for resource in index["monthly_schedule_xml_index_reconciliation"][
            "resources"
        ]
    }
    expected_receipts = {
        receipt["receipt_path"]: receipt
        for receipt in index["current_public_archive"]["receipts"]
    }

    assert len(resources) == 87
    assert len({resource["source_url"] for resource in resources}) == 87
    for resource in resources:
        assert resource["source_url"].startswith(
            "https://www.mbsonline.gov.au/"
        )
        if resource["source_scope"] == "current_index_xml":
            expected = expected_resources[resource["source_url"]]
            assert resource["filename"] == expected["filename"]
            expected_for_source = expected["matching_archive_receipts"]
        else:
            assert resource["source_scope"] == (
                "archive_receipt_only_not_selected_current_xml_index"
            )
            expected_for_source = [
                {
                    "receipt_path": receipt["receipt_path"],
                    "archive_path": receipt["archive_path"],
                    "payload_sha256": receipt["payload_sha256"],
                }
                for receipt in index["current_public_archive"]["receipts"]
                if receipt["source_url"] == resource["source_url"]
            ]
            page_id = next(
                page_result["page_id"]
                for page_result in pages
                if any(
                    observed["source_url"] == resource["source_url"]
                    for observed in cast(
                        "list[dict[str, Any]]", page_result["resources"]
                    )
                )
            )
            page = next(
                page
                for page in index["downloads_index"]["pages"]
                if page["page_id"] == page_id
            )
            assert resource["filename"] == next(
                link["filename"]
                for link in page["resources"]
                if link["url"] == resource["source_url"]
            )
        assert resource["current_receipt_binding_status"] == (
            "exact_current_receipts_verified"
        )
        actual_for_source = resource["archive_receipts"]
        assert len(actual_for_source) == len(expected_for_source) == 1
        for actual, source_receipt in zip(
            actual_for_source, expected_for_source, strict=True
        ):
            indexed = expected_receipts[source_receipt["receipt_path"]]
            assert actual["receipt_path"] == indexed["receipt_path"]
            assert actual["archive_path"] == indexed["archive_path"]
            assert actual["current_revision"] == archive["revision"]
            assert actual["current_receipt_sha256"] == indexed["receipt_sha256"]
            assert actual["current_payload_sha256"] == indexed["payload_sha256"]

        matches = resource["matching_official_rows"]
        assert len(matches) == 1
        assert len(matches[0]["row_sha256"]) == 64
        assert "row_text" not in matches[0]
        assert all(
            mention["cue"] and mention["date_text"]
            for mention in matches[0]["date_mentions"]
        )


def test_register_documents_the_remaining_m109_boundary() -> None:
    register = REGISTER.read_text(encoding="utf-8")
    assert REPORT.name in register
    assert "full historical denominator" in register
