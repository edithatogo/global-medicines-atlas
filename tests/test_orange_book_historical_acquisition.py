"""Contracts for authorized Orange Book historical acquisition."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from global_medicines_atlas.orange_book_historical_acquisition import (
    OrangeBookHistoricalAuthorization,
    discover_monthly_releases,
    exercise_orange_book_history,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT / "quality/qualifications/orange-book-historical-authorization.json"
)
QUALIFICATION = (
    ROOT / "quality/qualifications/orange-book-historical-corpus-20260821.json"
)


def _authorization_payload() -> dict[str, object]:
    return json.loads(AUTHORIZATION.read_text(encoding="utf-8"))


def test_committed_authorization_is_internal_only_and_bounded():
    authorization = OrangeBookHistoricalAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )

    assert authorization.acquisition_authorized is True
    assert authorization.internal_retention_authorized is True
    assert authorization.public_release_authorized is False
    assert authorization.external_publication_authorized is False
    assert authorization.max_releases == 320
    assert len(authorization.seeds) == 5


def test_committed_live_qualification_is_partial_internal_evidence():
    qualification = json.loads(QUALIFICATION.read_text(encoding="utf-8"))

    assert qualification["evidence_class"] == "live_internal_historical"
    assert qualification["authorized"] is True
    assert qualification["internal_retention_authorized"] is True
    assert qualification["public_release_authorized"] is False
    assert qualification["external_publication_performed"] is False
    assert qualification["coverage_complete"] is False
    assert qualification["historical_inventory_complete"] is False
    assert qualification["inventoried_release_count"] == 259
    assert qualification["unique_acquisition_succeeded_count"] == 200
    assert qualification["unique_acquisition_failed_count"] == 59
    assert qualification["unique_accepted_count"] == 18
    assert qualification["unique_quarantined_count"] == 182
    assert qualification["unique_payload_byte_count"] == 59737593
    assert qualification["source_record_rows"] == 73239
    assert all(
        archive["checksum_verified"]
        for archive in qualification["private_archives"]
    )
    assert len(qualification["private_archives"]) == 6
    assert qualification["private_archive_byte_count"] == 714455040
    assert qualification["private_archives"][-1] == {
        "attempt": "sixth-full-inventory-availability-observation",
        "release_count": 259,
        "succeeded_count": 156,
        "failed_count": 103,
        "accepted_count": 6,
        "quarantined_count": 150,
        "recovered_count": 6,
        "source_record_projection_count": 1,
        "archive_byte_count": 174325760,
        "archive_sha256": (
            "a8bf3b7ed1ec12c8fa7051559f8120d9f26d884837f2893cec8e160deddc2333"
        ),
        "checksum_verified": True,
    }
    assert qualification["failure_scope"] == {
        "host": "wayback.archive-it.org",
        "failure_code": "http_status",
        "failed_release_count": 59,
        "observed_rate_limit_status": 429,
        "latest_full_inventory_failed_count": 103,
        "bounded_correction_passes": 6,
        "retry_required": False,
        "disposition": (
            "explicitly_unavailable_without_complete_official_denominator"
        ),
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("acquisition_authorized", False, "explicitly authorized"),
        ("internal_retention_authorized", False, "retention"),
        ("public_release_authorized", True, "internal-only"),
        ("external_publication_authorized", True, "internal-only"),
    ],
)
def test_authorization_fails_closed(field: str, value: object, message: str):
    payload = _authorization_payload()
    payload[field] = value

    with pytest.raises(ValidationError, match=message):
        OrangeBookHistoricalAuthorization.model_validate(payload)


def test_authorization_rejects_host_duplicates_and_missing_discovery():
    payload = _authorization_payload()
    seeds = payload["seeds"]
    assert isinstance(seeds, list)
    seeds[0]["url"] = "https://example.com/data"  # type: ignore[index]
    with pytest.raises(ValidationError, match="official FDA"):
        OrangeBookHistoricalAuthorization.model_validate(payload)

    payload = _authorization_payload()
    seeds = payload["seeds"]
    assert isinstance(seeds, list)
    seeds[1]["release_id"] = seeds[0]["release_id"]  # type: ignore[index]
    with pytest.raises(ValidationError, match="must be unique"):
        OrangeBookHistoricalAuthorization.model_validate(payload)

    payload = _authorization_payload()
    seeds = payload["seeds"]
    assert isinstance(seeds, list)
    for seed in seeds:
        seed["discover_links"] = False  # type: ignore[index]
    with pytest.raises(ValidationError, match="discovery seed"):
        OrangeBookHistoricalAuthorization.model_validate(payload)


def test_discovery_keeps_only_deduplicated_official_month_links():
    payload = b"""
    <a href='/history/january-2020'> January 2020 </a>
    <a href='/history/january-2020#top'>January 2020 duplicate</a>
    <a href='https://example.com/february-2020'>February 2020</a>
    <a href='/not-a-release'>Documentation</a>
    """

    releases = discover_monthly_releases(payload, "https://www.fda.gov/index")

    assert len(releases) == 1
    assert releases[0].title == "January 2020 duplicate"
    assert str(releases[0].url) == "https://www.fda.gov/history/january-2020"
    assert releases[0].media_hint == "html"


def test_discovery_classifies_pdf_and_zip_release_links():
    payload = b"""
    <a href='/media/january-2020/download'>January 2020</a>
    <a href='/history/february-2020.zip'>February 2020</a>
    """

    releases = discover_monthly_releases(payload, "https://www.fda.gov/index")

    assert [release.media_hint for release in releases] == ["zip", "pdf"]


def test_runner_fault_isolates_failed_seed_and_rejects_reused_output(
    tmp_path: Path,
):
    payload = _authorization_payload()
    payload["max_releases"] = 1
    payload["archive_request_interval_seconds"] = 0
    payload["seeds"] = [
        {
            "release_id": "index",
            "url": "https://www.fda.gov/index",
            "media_hint": "html",
            "discover_links": True,
        }
    ]
    authorization = tmp_path / "authorization.json"
    authorization.write_text(json.dumps(payload), encoding="utf-8")
    transport = httpx.MockTransport(lambda _: httpx.Response(404))
    output = tmp_path / "output"

    manifest = exercise_orange_book_history(
        repository_root=ROOT,
        output_dir=output,
        authorization_path=authorization,
        transport=transport,
        observed_at=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
    )

    assert manifest.succeeded_count == 0
    assert manifest.failed_count == 1
    assert manifest.items[0].failure_code == "http_status"
    with pytest.raises(FileExistsError, match="must be empty"):
        exercise_orange_book_history(
            repository_root=ROOT,
            output_dir=output,
            authorization_path=authorization,
            transport=transport,
        )


def test_live_runner_discovers_lands_recovers_and_archives(tmp_path: Path):
    payload = _authorization_payload()
    payload["max_releases"] = 4
    payload["seeds"] = [
        {
            "release_id": "index",
            "url": "https://www.fda.gov/index",
            "media_hint": "html",
            "discover_links": True,
        },
        {
            "release_id": "document",
            "url": "https://www.fda.gov/media/document.pdf",
            "media_hint": "pdf",
            "discover_links": False,
        },
    ]
    authorization = tmp_path / "authorization.json"
    authorization.write_text(json.dumps(payload), encoding="utf-8")
    html = b"<html><a href='/history/january-2020'>January 2020</a></html>"
    pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/index":
            return httpx.Response(
                200, content=html, headers={"content-type": "text/html"}
            )
        return httpx.Response(
            200, content=pdf, headers={"content-type": "application/pdf"}
        )

    manifest = exercise_orange_book_history(
        repository_root=ROOT,
        output_dir=tmp_path / "output",
        authorization_path=authorization,
        transport=httpx.MockTransport(handler),
        observed_at=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
    )

    assert manifest.release_count == 3
    assert manifest.succeeded_count == 3
    assert manifest.failed_count == 0
    assert manifest.external_publication_performed is False
    assert manifest.archive_byte_count > 0
    assert (tmp_path / "output/orange-book-history.private.tar").is_file()
    assert (
        (tmp_path / "output/SHA256SUMS")
        .read_text()
        .startswith(manifest.archive_sha256)
    )
