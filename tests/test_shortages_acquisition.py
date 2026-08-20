"""Contracts for current and historical FDA drug-shortage acquisition."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from global_medicines_atlas.shortages_acquisition import (
    FDAShortagesAuthorization,
    exercise_fda_shortages,
    parse_cdx_inventory,
    parse_download_inventory,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT / "quality/qualifications/fda-shortages-live-authorization.json"
)
QUALIFICATION = (
    ROOT / "quality/qualifications/fda-shortages-live-corpus-20260821.json"
)
BULK_URL = (
    "https://download.open.fda.gov/drug/shortages/"
    "drug-shortages-0001-of-0001.json.zip"
)
CAPTURES = (
    (
        "20140622235409",
        "http://www.accessdata.fda.gov:80/scripts/drugshortages/default.cfm",
        "DIGEST-A",
    ),
    (
        "20140715235959",
        "https://www.accessdata.fda.gov/scripts/drugshortages/default.cfm",
        "DIGEST-B",
    ),
)


def _authorization(tmp_path: Path) -> Path:
    raw = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    raw["expected_historical_capture_count"] = 2
    raw["expected_first_capture"] = CAPTURES[0][0]
    raw["expected_last_capture"] = CAPTURES[-1][0]
    raw["capture_replay_overrides"] = {}
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def _cdx() -> bytes:
    return json.dumps([
        ["timestamp", "original", "statuscode", "mimetype", "digest"],
        *[
            [timestamp, original, "200", "text/html", digest]
            for timestamp, original, digest in CAPTURES
        ],
    ]).encode()


def _index(records: int = 2) -> bytes:
    return json.dumps({
        "meta": {"last_updated": "2026-08-20"},
        "results": {
            "drug": {
                "shortages": {
                    "export_date": "2026-08-20",
                    "partitions": [
                        {
                            "display_name": "/drug/shortages data",
                            "file": BULK_URL,
                            "size_mb": "0.01",
                            "records": records,
                        }
                    ],
                    "total_records": records,
                }
            }
        },
    }).encode()


def _bulk() -> bytes:
    records: list[dict[str, Any]] = [
        {
            "package_ndc": "0001-0001-01",
            "generic_name": "Source native A",
            "presentation": "Presentation A",
            "status": "Current",
            "shortage_reason": "Reason A",
            "initial_posting_date": "01/01/2026",
            "update_date": "08/20/2026",
            "company_name": "Company A",
        },
        {
            "package_ndc": "0002-0002-02",
            "generic_name": "Source native B",
            "presentation": "Presentation B",
            "status": "Resolved",
            "shortage_reason": "Reason B",
            "initial_posting_date": "02/01/2026",
            "update_date": "08/20/2026",
            "company_name": "Company B",
        },
    ]
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "drug-shortages-0001-of-0001.json",
            json.dumps({"results": records}),
        )
    return output.getvalue()


def test_authorization_is_bounded_and_internal_only() -> None:
    authorization = FDAShortagesAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )
    assert authorization.acquisition_authorized is True
    assert authorization.internal_retention_authorized is True
    assert authorization.public_release_authorized is False
    assert authorization.external_publication_authorized is False
    assert authorization.expected_historical_capture_count == 129


def test_live_qualification_preserves_partial_historical_boundary() -> None:
    qualification = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    assert qualification["evidence_class"] == "live_internal_historical"
    assert qualification["prompt_audit_qualified_source_ids"] == []
    assert qualification["current_bulk_export_complete"] is True
    assert qualification["historical_list_snapshot_inventory_complete"] is True
    assert qualification["unique_historical_list_snapshots_archived"] == 129
    assert (
        qualification["historical_detail_snapshot_coverage_complete"] is False
    )
    assert qualification["prompt_complete"] is False
    assert qualification["current_source_record_rows"] == 1_628
    assert (
        qualification["current_source_record_parquet_pairs_byte_identical"] == 1
    )
    assert qualification["archive_checksums_verified"] == 5
    assert qualification["public_release_authorized"] is False
    assert qualification["external_publication_performed"] is False


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("acquisition_authorized", False, "explicitly authorized"),
        ("internal_retention_authorized", False, "internal retention"),
        ("public_release_authorized", True, "internal-only"),
        ("cdx_url", "https://example.test/cdx", "Internet Archive"),
        (
            "download_index_url",
            "https://example.test/download.json",
            "official openFDA",
        ),
        (
            "expected_bulk_url",
            "https://example.test/bulk.zip",
            "official openFDA download",
        ),
        (
            "documentation_url",
            "https://example.test/shortages",
            "official FDA",
        ),
        ("expected_first_capture", "bad", "14-digit"),
    ],
)
def test_authorization_fails_closed_on_scope_drift(
    field: str, value: object, message: str
) -> None:
    raw = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    raw[field] = value
    with pytest.raises(ValidationError, match=message):
        FDAShortagesAuthorization.model_validate(raw)


def test_cdx_inventory_rejects_nonofficial_or_duplicate_captures() -> None:
    assert len(parse_cdx_inventory(_cdx())) == 2
    wrong = json.loads(_cdx())
    wrong[1][1] = "https://example.test/default.cfm"
    with pytest.raises(ValueError, match="outside official scope"):
        parse_cdx_inventory(json.dumps(wrong).encode())
    duplicate = json.loads(_cdx())
    duplicate[2][0] = "20140630235959"
    with pytest.raises(ValueError, match="duplicate monthly"):
        parse_cdx_inventory(json.dumps(duplicate).encode())


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"{}", "lacks drug shortages"),
        (
            json.dumps({
                "meta": {"last_updated": "2026-08-20"},
                "results": {
                    "drug": {
                        "shortages": {
                            "export_date": "2026-08-20",
                            "partitions": [],
                            "total_records": 2,
                        }
                    }
                },
            }).encode(),
            "partition count",
        ),
        (
            _index(records=3).replace(
                b'"total_records": 3', b'"total_records": 2'
            ),
            "record count",
        ),
    ],
)
def test_download_inventory_fails_closed_on_shape_drift(
    payload: bytes, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_download_inventory(payload)


def test_runner_archives_current_and_historical_surfaces(
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/cdx/search/cdx"):
            return httpx.Response(
                200,
                content=_cdx(),
                headers={"content-type": "application/json"},
            )
        if request.url.path == "/download.json":
            return httpx.Response(
                200,
                content=_index(),
                headers={"content-type": "application/json"},
            )
        if request.url.host == "download.open.fda.gov":
            return httpx.Response(
                200,
                content=_bulk(),
                headers={"content-type": "application/zip"},
            )
        return httpx.Response(
            200,
            content=b"<html>source-native FDA shortage surface</html>",
            headers={"content-type": "text/html"},
        )

    output = tmp_path / "output"
    manifest = exercise_fda_shortages(
        repository_root=ROOT,
        output_dir=output,
        authorization_path=_authorization(tmp_path),
        transport=httpx.MockTransport(handler),
        observed_at=datetime(2026, 8, 21, tzinfo=UTC),
    )

    assert manifest.current_record_count == 2
    assert manifest.historical_capture_inventory_count == 2
    assert manifest.historical_capture_inventory_complete is True
    assert manifest.historical_capture_succeeded_count == 2
    assert manifest.historical_capture_failed_count == 0
    assert manifest.surface_count == 6
    assert manifest.succeeded_count == 6
    assert manifest.failed_count == 0
    assert manifest.accepted_count == 5
    assert manifest.quarantined_count == 1
    assert manifest.recovered_count == 5
    assert manifest.source_record_projection_count == 1
    assert manifest.source_record_rows == 2
    assert manifest.recovered_source_record_projection_count == 1
    assert manifest.source_record_parquet_pairs_byte_identical == 1
    assert manifest.historical_detail_snapshot_coverage_complete is False
    assert manifest.prompt_complete is False
    assert manifest.external_publication_performed is False
    assert (output / "fda-shortages-live.private.tar").is_file()
    assert (
        (output / "SHA256SUMS").read_text().startswith(manifest.archive_sha256)
    )


def test_runner_can_retry_an_exact_inventory_subset(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/cdx/search/cdx"):
            return httpx.Response(
                200,
                content=_cdx(),
                headers={"content-type": "application/json"},
            )
        if request.url.path == "/download.json":
            return httpx.Response(
                200,
                content=_index(),
                headers={"content-type": "application/json"},
            )
        if request.url.host == "download.open.fda.gov":
            return httpx.Response(
                200,
                content=_bulk(),
                headers={"content-type": "application/zip"},
            )
        return httpx.Response(
            200,
            content=b"<html>snapshot</html>",
            headers={"content-type": "text/html"},
        )

    manifest = exercise_fda_shortages(
        repository_root=ROOT,
        output_dir=tmp_path / "retry",
        authorization_path=_authorization(tmp_path),
        transport=httpx.MockTransport(handler),
        observed_at=datetime(2026, 8, 21, tzinfo=UTC),
        capture_timestamps=frozenset({CAPTURES[-1][0]}),
    )
    assert manifest.historical_capture_inventory_count == 2
    assert manifest.historical_capture_succeeded_count == 1
    assert manifest.surface_count == 5

    with pytest.raises(ValueError, match="retry scope"):
        exercise_fda_shortages(
            repository_root=ROOT,
            output_dir=tmp_path / "unsafe-retry",
            authorization_path=_authorization(tmp_path),
            transport=httpx.MockTransport(handler),
            observed_at=datetime(2026, 8, 21, tzinfo=UTC),
            capture_timestamps=frozenset({"20000101000000"}),
        )


def test_runner_rejects_inventory_drift_and_nonempty_output(
    tmp_path: Path,
) -> None:
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "preserve.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError, match="must be empty"):
        exercise_fda_shortages(
            repository_root=ROOT,
            output_dir=nonempty,
            authorization_path=_authorization(tmp_path),
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        exercise_fda_shortages(
            repository_root=ROOT,
            output_dir=tmp_path / "naive",
            authorization_path=_authorization(tmp_path),
            observed_at=datetime(2026, 8, 21, tzinfo=UTC).replace(tzinfo=None),
        )

    with pytest.raises(ValueError, match="inventory drifted"):
        exercise_fda_shortages(
            repository_root=ROOT,
            output_dir=tmp_path / "drift",
            authorization_path=_authorization(tmp_path),
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    content=json.dumps([
                        [
                            "timestamp",
                            "original",
                            "statuscode",
                            "mimetype",
                            "digest",
                        ],
                        [*CAPTURES[0][:2], "200", "text/html", CAPTURES[0][2]],
                    ]).encode(),
                    headers={"content-type": "application/json"},
                )
            ),
            observed_at=datetime(2026, 8, 21, tzinfo=UTC),
        )
