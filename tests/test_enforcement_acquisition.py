"""Contracts for current FDA enforcement and recall-notice acquisition."""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from global_medicines_atlas.enforcement_acquisition import (
    FDAEnforcementAuthorization,
    exercise_fda_enforcement,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT / "quality/qualifications/fda-enforcement-live-authorization.json"
)
QUALIFICATION = (
    ROOT / "quality/qualifications/fda-enforcement-live-corpus-20260821.json"
)
BULK_URL = (
    "https://download.open.fda.gov/drug/enforcement/"
    "drug-enforcement-0001-of-0001.json.zip"
)


def _authorization() -> dict[str, Any]:
    return json.loads(AUTHORIZATION.read_text(encoding="utf-8"))


def _zip(name: str, payload: bytes) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(name, payload)
    return output.getvalue()


def _inventory(*, records: int = 2, file: str = BULK_URL) -> bytes:
    return json.dumps({
        "meta": {
            "last_updated": "2026-08-20",
            "license": "https://open.fda.gov/license/",
        },
        "results": {
            "drug": {
                "enforcement": {
                    "export_date": "2026-08-19",
                    "partitions": [
                        {
                            "display_name": "/drug/enforcement data",
                            "file": file,
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
    return _zip(
        "drug-enforcement-0001-of-0001.json",
        json.dumps({
            "meta": {"last_updated": "2026-08-20"},
            "results": [
                {
                    "recall_number": "D-0001-2026",
                    "event_id": "10001",
                    "product_description": "Source-native product A",
                    "classification": "Class II",
                    "reason_for_recall": "Source-native reason A",
                    "status": "Ongoing",
                    "distribution_pattern": "Nationwide",
                    "recall_initiation_date": "20260101",
                    "report_date": "20260110",
                },
                {
                    "recall_number": "D-0002-2026",
                    "event_id": "10002",
                    "product_description": "Source-native product B",
                    "classification": "Class III",
                    "reason_for_recall": "Source-native reason B",
                    "status": "Terminated",
                    "distribution_pattern": "One state",
                    "recall_initiation_date": "20260201",
                    "report_date": "20260210",
                },
            ],
        }).encode(),
    )


def _xlsx() -> bytes:
    return _zip(
        "[Content_Types].xml",
        b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
    )


def test_authorization_is_exact_bounded_and_internal_only() -> None:
    authorization = FDAEnforcementAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )

    assert authorization.acquisition_authorized is True
    assert authorization.internal_retention_authorized is True
    assert authorization.public_release_authorized is False
    assert authorization.external_publication_authorized is False
    assert authorization.historical_notice_archive_complete is False
    assert authorization.expected_partition_count == 1


def test_live_qualification_is_bound_to_recovered_internal_evidence() -> None:
    qualification = json.loads(QUALIFICATION.read_text(encoding="utf-8"))

    assert qualification["evidence_class"] == "live_bounded_internal"
    assert qualification["prompt_audit_qualified_source_ids"] == [
        "us-openfda-enforcement"
    ]
    assert qualification["current_enforcement_bulk_complete"] is True
    assert qualification["current_notice_snapshot_acquired"] is True
    assert qualification["historical_notice_archive_complete"] is False
    assert qualification["prompt_complete"] is False
    assert qualification["public_release_authorized"] is False
    assert qualification["external_publication_performed"] is False
    assert qualification["source_record_rows"] == 17_876
    assert qualification["source_record_projection_count"] == 1
    assert qualification["recovered_source_record_projection_count"] == 1
    assert qualification["source_record_parquet_pairs_byte_identical"] == 1
    assert qualification["archive_checksum_verified"] is True
    assert qualification["overlap_contract"] == {
        "automatic_record_linkage_performed": False,
        "silent_deduplication_performed": False,
    }


_AUTHORIZATION_MUTATIONS: list[
    tuple[Callable[[dict[str, Any]], object], str]
] = [
    (
        lambda raw: raw.update(acquisition_authorized=False),
        "explicitly authorized",
    ),
    (
        lambda raw: raw.update(internal_retention_authorized=False),
        "internal retention",
    ),
    (
        lambda raw: raw.update(public_release_authorized=True),
        "internal-only",
    ),
    (
        lambda raw: raw.update(historical_notice_archive_complete=True),
        "cannot pre-authorize historical completeness",
    ),
    (
        lambda raw: raw["surfaces"].pop(),
        "four exact current surfaces",
    ),
    (
        lambda raw: raw.update(expected_partition_count=2),
        "one official bulk partition",
    ),
]


@pytest.mark.parametrize(
    ("mutate", "message"),
    _AUTHORIZATION_MUTATIONS,
)
def test_authorization_fails_closed_on_scope_drift(
    mutate: Callable[[dict[str, Any]], object], message: str
) -> None:
    raw = _authorization()
    mutate(raw)
    with pytest.raises(ValidationError, match=message):
        FDAEnforcementAuthorization.model_validate(raw)


def test_runner_preserves_distinct_surfaces_projects_bulk_and_archives(
    tmp_path: Path,
) -> None:
    bulk = _bulk()
    xlsx = _xlsx()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/download.json":
            return httpx.Response(
                200,
                content=_inventory(),
                headers={"content-type": "application/json"},
            )
        if request.url.host == "download.open.fda.gov":
            return httpx.Response(
                200,
                content=bulk,
                headers={"content-type": "application/zip"},
            )
        if request.url.path.endswith("datatables-data"):
            return httpx.Response(
                200,
                content=xlsx,
                headers={
                    "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                },
            )
        return httpx.Response(
            200,
            content=b"<html>official documentation</html>",
            headers={"content-type": "text/html"},
        )

    output = tmp_path / "output"
    manifest = exercise_fda_enforcement(
        repository_root=ROOT,
        output_dir=output,
        authorization_path=AUTHORIZATION,
        transport=httpx.MockTransport(handler),
        observed_at=datetime(2026, 8, 21, tzinfo=UTC),
    )

    assert manifest.surface_count == 5
    assert manifest.succeeded_count == 5
    assert manifest.failed_count == 0
    assert manifest.inventory_export_date.isoformat() == "2026-08-19"
    assert manifest.inventory_total_records == 2
    assert manifest.source_record_projection_count == 1
    assert manifest.source_record_rows == 2
    assert manifest.recovered_source_record_projection_count == 1
    assert manifest.source_record_parquet_pairs_byte_identical == 1
    assert manifest.current_notice_snapshot_acquired is True
    assert manifest.historical_notice_archive_complete is False
    assert manifest.prompt_complete is False
    assert manifest.external_publication_performed is False
    assert (output / "fda-enforcement-live.private.tar").is_file()
    assert (
        (output / "SHA256SUMS").read_text().startswith(manifest.archive_sha256)
    )
    assert (
        len(
            tuple(
                (output / "runs/corpus/bronze/payloads/by_content").rglob(
                    "payload.xlsx"
                )
            )
        )
        == 1
    )
    overlap = json.loads(
        (
            output
            / "runs/corpus/evidence/recall-enforcement-overlap-contract.json"
        ).read_text(encoding="utf-8")
    )
    assert overlap["automatic_record_linkage_performed"] is False
    assert overlap["silent_deduplication_performed"] is False
    assert overlap["enforcement_identity_fields"] == [
        "recall_number",
        "event_id",
    ]


@pytest.mark.parametrize(
    ("inventory", "message"),
    [
        (_inventory(file="https://example.test/wrong.zip"), "bulk URL"),
        (_inventory(records=3), "record count"),
    ],
)
def test_runner_rejects_inventory_or_payload_drift_before_archiving(
    tmp_path: Path,
    inventory: bytes,
    message: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/download.json":
            return httpx.Response(
                200,
                content=inventory,
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
            content=b"<html>official documentation</html>",
            headers={"content-type": "text/html"},
        )

    with pytest.raises(ValueError, match=message):
        exercise_fda_enforcement(
            repository_root=ROOT,
            output_dir=tmp_path / message.replace(" ", "-"),
            authorization_path=AUTHORIZATION,
            transport=httpx.MockTransport(handler),
            observed_at=datetime(2026, 8, 21, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    ("inventory", "message"),
    [
        (b'{"meta": {}}', "lacks drug enforcement"),
        (
            json.dumps({
                "meta": {"last_updated": "2026-08-20"},
                "results": {
                    "drug": {
                        "enforcement": {
                            "export_date": "2026-08-19",
                            "partitions": [],
                            "total_records": 2,
                        }
                    }
                },
            }).encode(),
            "partition count",
        ),
        (
            json.dumps({
                "meta": {"last_updated": "2026-08-20"},
                "results": {
                    "drug": {
                        "enforcement": {
                            "export_date": "2026-08-19",
                            "partitions": [
                                {
                                    "display_name": "/drug/enforcement data",
                                    "file": BULK_URL,
                                    "size_mb": "0.01",
                                    "records": 2,
                                }
                            ],
                            "total_records": 3,
                        }
                    }
                },
            }).encode(),
            "inventory record count",
        ),
    ],
)
def test_runner_rejects_inventory_shape_drift(
    tmp_path: Path,
    inventory: bytes,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        exercise_fda_enforcement(
            repository_root=ROOT,
            output_dir=tmp_path / message.replace(" ", "-"),
            authorization_path=AUTHORIZATION,
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    content=inventory,
                    headers={"content-type": "application/json"},
                )
            ),
            observed_at=datetime(2026, 8, 21, tzinfo=UTC),
        )


def test_runner_rejects_nonempty_output_naive_time_and_failed_inventory(
    tmp_path: Path,
) -> None:
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "preserve.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError, match="must be empty"):
        exercise_fda_enforcement(
            repository_root=ROOT,
            output_dir=nonempty,
            authorization_path=AUTHORIZATION,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        exercise_fda_enforcement(
            repository_root=ROOT,
            output_dir=tmp_path / "naive",
            authorization_path=AUTHORIZATION,
            observed_at=datetime(2026, 8, 21, tzinfo=UTC).replace(tzinfo=None),
        )
    with pytest.raises(TypeError, match="inventory acquisition failed"):
        exercise_fda_enforcement(
            repository_root=ROOT,
            output_dir=tmp_path / "failed-inventory",
            authorization_path=AUTHORIZATION,
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(503, content=b"unavailable")
            ),
            observed_at=datetime(2026, 8, 21, tzinfo=UTC),
        )


def test_runner_records_fault_isolated_bulk_and_surface_failures(
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/download.json":
            return httpx.Response(
                200,
                content=_inventory(),
                headers={"content-type": "application/json"},
            )
        return httpx.Response(503, content=b"unavailable")

    manifest = exercise_fda_enforcement(
        repository_root=ROOT,
        output_dir=tmp_path / "output",
        authorization_path=AUTHORIZATION,
        transport=httpx.MockTransport(handler),
        observed_at=datetime(2026, 8, 21, tzinfo=UTC),
    )

    assert manifest.succeeded_count == 1
    assert manifest.failed_count == 4
    assert manifest.source_record_projection_count == 0
    assert manifest.current_notice_snapshot_acquired is False


def test_runner_rejects_unprojectable_bulk_and_exhausted_budget(
    tmp_path: Path,
) -> None:
    invalid_bulk = _zip(
        "drug-enforcement-0001-of-0001.json",
        b'{"results": {}}',
    )

    def unprojectable(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/download.json":
            return httpx.Response(
                200,
                content=_inventory(),
                headers={"content-type": "application/json"},
            )
        return httpx.Response(
            200,
            content=invalid_bulk,
            headers={"content-type": "application/zip"},
        )

    with pytest.raises(ValueError, match="lacks source records"):
        exercise_fda_enforcement(
            repository_root=ROOT,
            output_dir=tmp_path / "unprojectable",
            authorization_path=AUTHORIZATION,
            transport=httpx.MockTransport(unprojectable),
            observed_at=datetime(2026, 8, 21, tzinfo=UTC),
        )

    inventory = _inventory()
    bulk = _bulk()
    authorization_raw = _authorization()
    authorization_raw["max_total_bytes"] = len(inventory) + len(bulk)
    authorization = tmp_path / "bounded-authorization.json"
    authorization.write_text(json.dumps(authorization_raw), encoding="utf-8")

    def bounded(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/download.json":
            return httpx.Response(
                200,
                content=inventory,
                headers={"content-type": "application/json"},
            )
        return httpx.Response(
            200,
            content=bulk,
            headers={"content-type": "application/zip"},
        )

    with pytest.raises(ValueError, match="exceeded total byte budget"):
        exercise_fda_enforcement(
            repository_root=ROOT,
            output_dir=tmp_path / "bounded",
            authorization_path=authorization,
            transport=httpx.MockTransport(bounded),
            observed_at=datetime(2026, 8, 21, tzinfo=UTC),
        )
