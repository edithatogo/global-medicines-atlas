"""Authorization and corpus contracts for bounded live U.S. acquisition."""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

import global_medicines_atlas.us_live_bronze as live_mod
from global_medicines_atlas.reuse_gate import acquire_new_decision
from global_medicines_atlas.source_catalog import load_source_catalog
from global_medicines_atlas.us_live_bronze import (
    PRIVATE_ARCHIVE_FILENAME,
    PRIVATE_MANIFEST_FILENAME,
    USLiveAcquisitionAuthorization,
    exercise_us_live_bronze_corpus,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT / "quality/qualifications/us-live-acquisition-authorization.json"
)
QUALIFICATION = (
    ROOT / "quality/qualifications/us-live-bronze-corpus-20260820.json"
)
RECORD_QUALIFICATION = (
    ROOT / "quality/qualifications/us-live-bronze-records-20260820.json"
)
NOW = datetime(2026, 8, 20, 8, 0, tzinfo=UTC)


def _zip_payload(source_id: str) -> bytes:
    members = {
        "us-drugsfda": {
            "ActionTypes_Lookup.txt": "ActionType\tDescription\nA\tApproval\n",
            "ApplicationDocs.txt": "ApplicationDocsID\tApplication_No\n1\t1\n",
            "Applications.txt": "ApplNo\tSponsorName\n1\tSponsor\n",
            "ApplicationsDocsType_Lookup.txt": "ApplicationDocsTypeID\tDescription\n1\tLabel\n",
            "Join_Submission_ActionTypes_Lookup.txt": "SubmissionID\tActionType\n1\tA\n",
            "MarketingStatus.txt": "ApplNo\tProductNo\n1\t1\n",
            "MarketingStatus_Lookup.txt": "MarketingStatusID\tDescription\n1\tPrescription\n",
            "Products.txt": "ApplNo\tProductNo\tDrugName\n1\t1\tNative\n",
            "SubmissionClass_Lookup.txt": "SubmissionClassCodeID\tDescription\n1\tClass\n",
            "SubmissionPropertyType.txt": "SubmissionPropertyTypeID\tDescription\n1\tType\n",
            "Submissions.txt": "ApplNo\tSubmissionID\n1\t1\n",
            "TE.txt": "ApplNo\tProductNo\tTECode\n1\t1\tAB\n",
        },
        "us-fda-orange-book": {
            "patent.txt": "Appl_No~Patent_No\n1~P1\n",
            "products.txt": "Appl_No~Product_No~Ingredient\n1~1~Native\n",
            "exclusivity.txt": "Appl_No~Exclusivity_Code\n1~NCE\n",
        },
        "us-fda-nsde": {
            "Comprehensive_NDC_SPL_Data_Elements_File.csv": (
                "PRODUCTNDC,NDCPACKAGECODE,PROPRIETARYNAME\n"
                "0001-0001,0001-0001-01,Native\n"
            )
        },
    }[source_id]
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return output.getvalue()


def test_authorization_is_bounded_internal_only_and_exhaustive() -> None:
    authorization = USLiveAcquisitionAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )

    assert authorization.internal_retention_authorized is True
    assert authorization.public_release_authorized is False
    assert authorization.external_publication_authorized is False
    assert authorization.coverage_complete is False
    assert len(authorization.authorized_sources) == 13
    assert {item.source_id for item in authorization.authorized_sources} == {
        "us-openfda-drugsfda",
        "us-openfda-enforcement",
        "us-openfda-faers",
        "us-openfda-ndc",
        "us-openfda-nsde",
        "us-drugsfda",
        "us-fda-drug-shortages",
        "us-fda-faers",
        "us-fda-ndc-directory",
        "us-fda-nsde",
        "us-fda-orange-book",
        "us-fda-recalls-notices",
        "us-fda-rems",
    }
    assert set(authorization.catalogue_only_sources) == {
        "us-cms-mdrp",
        "us-cms-nadac",
        "us-cms-partd-formulary",
        "us-cms-partd-spending",
        "us-dailymed-spl",
        "us-gsrs-unii",
        "us-rxnorm-api",
    }
    assert "gmdn" in " ".join(authorization.field_exclusions).casefold()


def test_live_qualification_records_real_private_corpus_without_overclaim() -> (
    None
):
    qualification = json.loads(QUALIFICATION.read_bytes())

    assert qualification["source_count"] == 13
    assert qualification["acquisition_succeeded_count"] == 13
    assert qualification["accepted_admission_count"] == 8
    assert qualification["quarantined_admission_count"] == 5
    assert qualification["recovered_acquisition_count"] == 8
    assert qualification["coverage_complete"] is False
    assert qualification["external_publication_performed"] is False
    assert qualification["public_release_authorized"] is False
    assert qualification["private_archive"]["entry_count"] == 441
    assert len(qualification["authorized_source_results"]) == 13
    assert len(qualification["catalogue_only_sources"]) == 7


def test_record_qualification_captures_real_projection_and_recovery() -> None:
    qualification = json.loads(RECORD_QUALIFICATION.read_bytes())

    assert qualification["source_count"] == 13
    assert qualification["source_record_projection_count"] == 8
    assert qualification["source_record_count"] == 1_701_269
    assert qualification["recovered_source_record_projection_count"] == 8
    assert qualification["source_record_parquet_pairs_byte_identical"] == 8
    assert qualification["private_archive"]["entry_count"] == 489
    assert qualification["coverage_complete"] is False
    assert qualification["external_publication_performed"] is False
    assert len(qualification["record_products"]) == 8
    assert qualification["prompt_audit_qualified_source_ids"] == [
        "us-fda-nsde"
    ]
    assert qualification["prompt_audit_qualification_basis"]["prompt_id"] == 19


@pytest.mark.integration
def test_live_corpus_runner_acquires_lands_recovers_and_archives(
    tmp_path: Path,
) -> None:
    authorization = USLiveAcquisitionAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )
    by_path = {
        str(item.endpoint): item for item in authorization.authorized_sources
    }

    def handler(request: httpx.Request) -> httpx.Response:
        item = by_path[str(request.url)]
        if item.media_hint == "zip":
            return httpx.Response(
                200,
                headers={"content-type": "application/zip"},
                content=_zip_payload(item.source_id),
            )
        if item.media_hint == "html":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"<!doctype html><html><body>FDA source</body></html>",
            )
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=json.dumps({
                "meta": {},
                "results": [
                    {
                        "application_number": "NDA001",
                        "recall_number": "R-001",
                        "event_id": "E-001",
                        "safetyreportid": "100",
                        "safetyreportversion": "1",
                        "product_ndc": "0001-0001",
                        "package_ndc": "0001-0001",
                        "package_ndc11": "00001000101",
                    }
                ],
            }).encode(),
        )

    output = tmp_path / "build" / "us-live"
    manifest = exercise_us_live_bronze_corpus(
        repository_root=tmp_path,
        output_dir=output,
        authorization_path=AUTHORIZATION,
        catalog=load_source_catalog(),
        transport=httpx.MockTransport(handler),
        reuse_searcher=acquire_new_decision,
        clock=lambda: NOW,
    )

    assert manifest.source_count == 13
    assert manifest.acquisition_succeeded_count == 13
    assert manifest.acquisition_failed_count == 0
    assert manifest.accepted_admission_count == 8
    assert manifest.quarantined_admission_count == 5
    assert manifest.recovered_acquisition_count == 8
    assert manifest.source_record_projection_count == 8
    assert manifest.recovered_source_record_projection_count == 8
    assert manifest.external_publication_performed is False
    assert manifest.coverage_complete is False
    assert len(manifest.items) == 13
    assert all(item.payload_sha256 for item in manifest.items)
    assert sum(item.source_record_count or 0 for item in manifest.items) == 21
    assert all(
        item.reuse_disposition == "acquire-new" for item in manifest.items
    )
    archive_path = output / PRIVATE_ARCHIVE_FILENAME
    assert archive_path.is_file()
    assert manifest.archive_sha256
    persisted = json.loads((output / PRIVATE_MANIFEST_FILENAME).read_bytes())
    assert persisted["archive_sha256"] == manifest.archive_sha256
    with tarfile.open(archive_path) as archive:
        names = archive.getnames()
    assert any(name.startswith("corpus/bronze/payloads/") for name in names)
    assert any(
        name.startswith("corpus/clean-room/catalogue/") for name in names
    )
    assert sum(name.endswith("source_records.parquet") for name in names) == 16


def test_runner_refuses_public_or_partial_authorization(tmp_path: Path) -> None:
    raw = json.loads(AUTHORIZATION.read_bytes())
    raw["public_release_authorized"] = True
    unsafe = tmp_path / "unsafe.json"
    unsafe.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="internal-only"):
        exercise_us_live_bronze_corpus(
            repository_root=tmp_path,
            output_dir=tmp_path / "build" / "unsafe",
            authorization_path=unsafe,
            catalog=load_source_catalog(),
            reuse_searcher=acquire_new_decision,
        )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda raw: raw.update(internal_retention_authorized=False),
            "internal retention",
        ),
        (
            lambda raw: raw.update(coverage_complete=True),
            "complete coverage",
        ),
        (
            lambda raw: raw["authorized_sources"].append(
                raw["authorized_sources"][0]
            ),
            "must be unique",
        ),
        (
            lambda raw: raw["authorized_sources"].pop(),
            "approved 13 sources",
        ),
        (
            lambda raw: raw["catalogue_only_sources"].pop(),
            "seven terms gaps",
        ),
        (
            lambda raw: raw.update(field_exclusions=["third-party only"]),
            "GMDN material",
        ),
    ],
)
def test_authorization_rejects_scope_drift(mutate, message: str) -> None:
    raw = json.loads(AUTHORIZATION.read_bytes())
    mutate(raw)

    with pytest.raises(ValueError, match=message):
        USLiveAcquisitionAuthorization.model_validate(raw)


def test_private_archive_and_excluded_content_fail_closed(
    tmp_path: Path,
) -> None:
    authorization = USLiveAcquisitionAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )
    openfda = authorization.authorized_sources[0]
    with pytest.raises(ValueError, match="excluded GMDN"):
        live_mod._reject_excluded_openfda_material(
            openfda,
            b'{"gmdn_term": "excluded"}',
        )

    empty = tmp_path / "empty"
    live_mod._copy_evidentiary_truth(empty, tmp_path / "copy")
    assert not (tmp_path / "copy").exists()

    corpus = tmp_path / "corpus"
    corpus.mkdir()
    target = corpus / "target"
    target.write_text("private", encoding="utf-8")
    (corpus / "link").symlink_to(target)
    with pytest.raises(ValueError, match="cannot contain symlinks"):
        live_mod._write_private_archive(corpus, tmp_path / "unsafe.tar")


def test_runner_rejects_nonempty_output_and_naive_clock(tmp_path: Path) -> None:
    occupied = tmp_path / "build" / "occupied"
    occupied.mkdir(parents=True)
    (occupied / "existing").write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError, match="must be empty"):
        exercise_us_live_bronze_corpus(
            repository_root=tmp_path,
            output_dir=occupied,
            authorization_path=AUTHORIZATION,
            catalog=load_source_catalog(),
            reuse_searcher=acquire_new_decision,
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        exercise_us_live_bronze_corpus(
            repository_root=tmp_path,
            output_dir=tmp_path / "build" / "naive",
            authorization_path=AUTHORIZATION,
            catalog=load_source_catalog(),
            reuse_searcher=acquire_new_decision,
            clock=lambda: datetime.fromisoformat("2026-08-20T08:00:00"),
        )


@pytest.mark.integration
def test_runner_fault_isolates_an_endpoint_failure(tmp_path: Path) -> None:
    authorization = USLiveAcquisitionAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )
    by_path = {
        str(item.endpoint): item for item in authorization.authorized_sources
    }
    failed_source = authorization.authorized_sources[0].source_id

    def handler(request: httpx.Request) -> httpx.Response:
        item = by_path[str(request.url)]
        if item.source_id == failed_source:
            return httpx.Response(503, request=request)
        if item.media_hint == "zip":
            return httpx.Response(
                200,
                headers={"content-type": "application/zip"},
                content=_zip_payload(item.source_id),
            )
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b'{"results": []}',
        )

    manifest = exercise_us_live_bronze_corpus(
        repository_root=tmp_path,
        output_dir=tmp_path / "build" / "fault-isolated",
        authorization_path=AUTHORIZATION,
        catalog=load_source_catalog(),
        transport=httpx.MockTransport(handler),
        reuse_searcher=acquire_new_decision,
        clock=lambda: NOW,
    )

    assert manifest.acquisition_succeeded_count == 12
    assert manifest.acquisition_failed_count == 1
    failed = next(item for item in manifest.items if item.status == "failed")
    assert failed.source_id == failed_source
    assert failed.failure_code == "http_status"


@pytest.mark.integration
def test_runner_fault_isolates_a_source_record_projection_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authorization = USLiveAcquisitionAuthorization.model_validate_json(
        AUTHORIZATION.read_bytes()
    )
    by_path = {
        str(item.endpoint): item for item in authorization.authorized_sources
    }
    failed_source = "us-openfda-faers"
    real_projector = live_mod.us_source_record_batch

    def projector(source_id: str, payload: bytes, media_hint: str):
        if source_id == failed_source:
            raise ValueError("redacted source schema failure")
        return real_projector(source_id, payload, media_hint)

    def handler(request: httpx.Request) -> httpx.Response:
        item = by_path[str(request.url)]
        if item.media_hint == "zip":
            return httpx.Response(
                200,
                headers={"content-type": "application/zip"},
                content=_zip_payload(item.source_id),
            )
        if item.media_hint == "html":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"<!doctype html><html><body>FDA source</body></html>",
            )
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b'{"results": []}',
        )

    monkeypatch.setattr(live_mod, "us_source_record_batch", projector)
    manifest = exercise_us_live_bronze_corpus(
        repository_root=tmp_path,
        output_dir=tmp_path / "build" / "projection-fault",
        authorization_path=AUTHORIZATION,
        catalog=load_source_catalog(),
        transport=httpx.MockTransport(handler),
        reuse_searcher=acquire_new_decision,
        clock=lambda: NOW,
    )

    failed = next(
        item for item in manifest.items if item.source_id == failed_source
    )
    assert failed.status == "succeeded"
    assert failed.parquet_projected is True
    assert failed.source_records_projected is False
    assert (
        failed.source_record_failure_code == "source_record_projection_failed"
    )
    assert manifest.acquisition_succeeded_count == 13
    assert manifest.source_record_projection_count == 7
