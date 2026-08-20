"""Contracts for authorized current FDA NDC Directory acquisition."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from global_medicines_atlas.ndc_directory_acquisition import (
    NDCDirectoryAuthorization,
    exercise_ndc_directory,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT / "quality/qualifications/ndc-directory-live-authorization.json"
)
QUALIFICATION = (
    ROOT / "quality/qualifications/ndc-directory-live-corpus-20260821.json"
)


def _authorization() -> dict[str, object]:
    return json.loads(AUTHORIZATION.read_text(encoding="utf-8"))


def _zip(name: str, payload: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(name, payload)
    return output.getvalue()


def test_authorization_is_exact_bounded_and_internal_only() -> None:
    authorization = NDCDirectoryAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )

    assert authorization.internal_retention_authorized is True
    assert authorization.public_release_authorized is False
    assert authorization.external_publication_authorized is False
    assert authorization.coverage_complete is False
    assert len(authorization.releases) == 5


def test_qualification_binds_complete_current_records_to_verified_archive() -> (
    None
):
    qualification = json.loads(QUALIFICATION.read_text(encoding="utf-8"))

    assert qualification["current_bulk_surface_complete"] is True
    assert qualification["historical_snapshot_coverage_claimed"] is False
    assert qualification["external_publication_performed"] is False
    assert qualification["release_count"] == 5
    assert qualification["acquisition_succeeded_count"] == 5
    assert qualification["source_record_projection_count"] == 5
    assert qualification["recovered_source_record_projection_count"] == 5
    assert qualification["source_record_rows"] == 1122796
    assert qualification["archive_checksum_verified"] is True


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda value: value.update(internal_retention_authorized=False),
            "internal retention",
        ),
        (
            lambda value: value.update(public_release_authorized=True),
            "internal-only",
        ),
        (
            lambda value: value.update(external_publication_authorized=True),
            "internal-only",
        ),
        (
            lambda value: value.update(coverage_complete=True),
            "cannot claim",
        ),
        (
            lambda value: value["releases"].pop(),
            "five official",
        ),
    ],
)
def test_authorization_fails_closed_on_scope_drift(
    mutate, message: str
) -> None:
    value = _authorization()
    mutate(value)
    with pytest.raises(ValidationError, match=message):
        NDCDirectoryAuthorization.model_validate(value)


def test_runner_lands_projects_recovers_and_archives_current_family(
    tmp_path: Path,
) -> None:
    direct = _zip(
        "product.txt",
        "PRODUCTNDC\tNDCPACKAGECODE\tLABELERNAME\n0001-0001\t0001-0001-01\tLabeler\n",
    )
    openfda = _zip(
        "drug-ndc-0001-of-0001.json",
        json.dumps({"results": [{"product_ndc": "0001-0001"}]}),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        payload = (
            openfda if request.url.host == "download.open.fda.gov" else direct
        )
        return httpx.Response(
            200,
            content=payload,
            headers={"content-type": "application/zip"},
        )

    output = tmp_path / "output"
    manifest = exercise_ndc_directory(
        repository_root=ROOT,
        output_dir=output,
        authorization_path=AUTHORIZATION,
        transport=httpx.MockTransport(handler),
        observed_at=datetime(2026, 8, 21, tzinfo=UTC),
    )

    assert manifest.release_count == 5
    assert manifest.succeeded_count == 5
    assert manifest.failed_count == 0
    assert manifest.accepted_count == 5
    assert manifest.recovered_count == 5
    assert manifest.source_record_projection_count == 5
    assert manifest.recovered_source_record_projection_count == 5
    assert manifest.source_record_rows == 5
    assert manifest.external_publication_performed is False
    assert manifest.coverage_complete is False
    assert (output / "ndc-directory-live.private.tar").is_file()
    assert (
        (output / "SHA256SUMS").read_text().startswith(manifest.archive_sha256)
    )
    with pytest.raises(FileExistsError, match="must be empty"):
        exercise_ndc_directory(
            repository_root=ROOT,
            output_dir=output,
            authorization_path=AUTHORIZATION,
            transport=httpx.MockTransport(handler),
        )
