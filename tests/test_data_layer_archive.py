"""Contracts for no-credential data-layer archival."""

from __future__ import annotations

import hashlib
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from global_medicines_atlas import data_layer_archive as archive_mod
from global_medicines_atlas.data_layer_archive import (
    ARCHIVE_WORKFLOW_RELATIVE,
    CATALOGUE_REPOSITORY,
    FIXTURE_PROVENANCE_NOTE,
    HF_TOKEN_SECRET_NAME,
    HUGGINGFACE_HUB_PIN,
    MAX_ARCHIVAL_FILE_BYTES,
    RESTRICTED_PATH_PREFIXES,
    SCOPED_AUTHORITY_GROUPS,
    AccessClass,
    ArchivalDisposition,
    AuthorityGroup,
    HttpPayloadRetriever,
    HuggingFaceAuthError,
    HuggingFaceCliUploader,
    PayloadKind,
    RetrievedPayload,
    assert_no_restricted_artifacts,
    build_data_layer_archive,
    classify_authority_group,
    classify_source_access,
    inventory_data_layer,
    parse_authority_groups,
    resolve_huggingface_identity,
    retrieval_uris_for_source,
)
from global_medicines_atlas.publication_transport import (
    APPROVAL_VALUE,
    PRODUCTION_ENVIRONMENT,
    PublicationAuthorization,
    PublicationDestination,
    PublicationTarget,
    PublicationTransportState,
    assert_external_write_authorized,
    execute_publication,
    prepare_publication,
)
from global_medicines_atlas.source_catalog import (
    MedicineDataSource,
    load_source_catalog,
)
from global_medicines_atlas.source_profiles import AuthenticationMode

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 19, 12, tzinfo=UTC)


class _FakeUploader:
    def __init__(self, revision: str = "abc123def456") -> None:
        self.revision = revision
        self.calls: list[tuple[str, Path, str]] = []

    def upload_folder(
        self,
        *,
        repository: str,
        folder: Path,
        commit_message: str,
    ) -> str:
        self.calls.append((repository, folder, commit_message))
        return self.revision


def _completed(
    _args: object, **_kwargs: object
) -> subprocess.CompletedProcess[str]:
    command = _args if isinstance(_args, tuple) else ("hf",)
    return subprocess.CompletedProcess(
        command, 0, stdout="edithatogo\n", stderr=""
    )


def _completed_empty(
    _args: object, **_kwargs: object
) -> subprocess.CompletedProcess[str]:
    command = _args if isinstance(_args, tuple) else ("hf",)
    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


def _http_revision(_url: str, **_kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"sha": "cafebabe1234"},
    )


def _http_blank_revision(_url: str, **_kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"sha": " "},
    )


def _raise_cli_error(_args: object, **_kwargs: object) -> None:
    raise subprocess.CalledProcessError(1, "hf")


def test_inventory_covers_every_catalog_source_exactly_once() -> None:
    inventory = inventory_data_layer(ROOT)
    catalog_ids = {source.source_id for source in load_source_catalog()}
    inventory_ids = {row.source_id for row in inventory.sources}
    assert len(inventory.sources) == 96
    assert inventory_ids == catalog_ids
    assert inventory.public_no_credential_count == 85
    assert inventory.credential_restricted_count == 11


def test_credential_sources_are_classified_without_payload_archival() -> None:
    inventory = inventory_data_layer(ROOT)
    restricted = {
        row.source_id: row
        for row in inventory.sources
        if row.access_class is AccessClass.CREDENTIAL_RESTRICTED
    }
    assert set(restricted) == {
        "au-amt-rf2",
        "au-pbs-embargo",
        "eu-ema-pms-fhir",
        "eu-spor-rms-oms",
        "gb-nhs-dmd",
        "gb-trud-api",
        "kr-hira-reimbursement",
        "kr-mfds-nedrug",
        "nz-nzhts-fhir",
        "nz-nzulm-bulk",
        "sa-sfda-drug-list",
    }
    assert all(
        row.archival_disposition is ArchivalDisposition.CATALOG_METADATA_ONLY
        for row in restricted.values()
    )
    nzulm = restricted["nz-nzulm-bulk"]
    assert nzulm.skip_reason == "credentials_and_restricted_bytes"
    assert "vendor/nzmedicines" not in nzulm.fixture_paths


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (AuthenticationMode.NONE, AccessClass.PUBLIC_NO_CREDENTIAL),
        (AuthenticationMode.API_KEY, AccessClass.CREDENTIAL_RESTRICTED),
        (AuthenticationMode.OAUTH, AccessClass.CREDENTIAL_RESTRICTED),
        (AuthenticationMode.ACCOUNT, AccessClass.CREDENTIAL_RESTRICTED),
        (AuthenticationMode.SUBSCRIPTION, AccessClass.CREDENTIAL_RESTRICTED),
        (AuthenticationMode.MANUAL_APPROVAL, AccessClass.CREDENTIAL_RESTRICTED),
        (AuthenticationMode.CERTIFICATE, AccessClass.CREDENTIAL_RESTRICTED),
        (AuthenticationMode.UNKNOWN, AccessClass.CREDENTIAL_RESTRICTED),
    ],
)
def test_access_class_is_fail_closed_for_credentials(
    mode: AuthenticationMode, expected: AccessClass
) -> None:
    assert classify_source_access(mode) is expected


def test_archive_includes_catalog_schema_and_governed_fixtures(
    tmp_path: Path,
) -> None:
    package = build_data_layer_archive(ROOT, tmp_path / "archive")
    relative = {item.relative_path for item in package.files}
    assert "README.md" in relative
    assert "medicine_source_catalog.json" in relative
    assert "international-resource-v5.json" in relative
    assert "inventory/source-inventory.parquet" in relative
    assert "inventory/source-inventory.json" in relative
    assert "inventory/archival-manifest.json" in relative
    assert "metadata/publication-identities.json" in relative
    assert "SHA256SUMS" in relative
    assert "fixtures/au-artg/au_artg.csv" in relative
    assert "fixtures/global-rxnorm/rxnorm_bootstrap.json" in relative
    assert "fixtures/synthetic/canada.json" in relative
    assert all(
        "vendor/nzmedicines" not in path and "nzulm" not in path
        for path in relative
    )
    manifest = json.loads(
        package.file("inventory/archival-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["fixture_provenance"] == FIXTURE_PROVENANCE_NOTE
    assert manifest["live_source_dump_downloaded"] is False
    assert "nz-nzulm-bulk" in manifest["skipped_source_ids"]
    table = pq.read_table(
        tmp_path / "archive" / "inventory" / "source-inventory.parquet"
    )
    assert table.num_rows == 96
    access = table.column("access_class").to_pylist()
    assert access.count("public_no_credential") == 85
    assert access.count("credential_restricted") == 11


def test_restricted_paths_and_oversize_files_fail_closed(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="restricted"):
        assert_no_restricted_artifacts(("vendor/nzmedicines/secret.json",))
    huge = tmp_path / "huge.csv"
    huge.write_bytes(b"x" * (MAX_ARCHIVAL_FILE_BYTES + 1))
    with pytest.raises(ValueError, match="exceeds"):
        assert_no_restricted_artifacts(
            (huge.relative_to(tmp_path).as_posix(),),
            root=tmp_path,
        )
    assert any(
        prefix.startswith("vendor/") for prefix in RESTRICTED_PATH_PREFIXES
    )


def test_prepared_archive_upload_requires_dual_authorization(
    tmp_path: Path,
) -> None:
    package = build_data_layer_archive(ROOT, tmp_path / "archive")
    paths = tuple(item.relative_path for item in package.files)
    plan, receipt = prepare_publication(
        root=tmp_path / "archive",
        release_version="data-layer-archive-v1",
        target=package.target,
        relative_paths=paths,
        recorded_at=NOW,
    )
    assert receipt.state is PublicationTransportState.PREPARED
    assert plan.target.repository == CATALOGUE_REPOSITORY
    assert plan.target.destination is PublicationDestination.HUGGING_FACE
    with pytest.raises(PermissionError, match="maintainer approval"):
        execute_publication(
            plan=plan,
            authorization=PublicationAuthorization(
                environment="unset",
                maintainer_approval="unset",
            ),
            root=tmp_path / "archive",
            uploader=_FakeUploader(),
            recorded_at=NOW,
        )


def test_authorized_upload_records_public_receipt_without_secrets(
    tmp_path: Path,
) -> None:
    package = build_data_layer_archive(ROOT, tmp_path / "archive")
    paths = tuple(item.relative_path for item in package.files)
    plan, _prepared = prepare_publication(
        root=tmp_path / "archive",
        release_version="data-layer-archive-v1",
        target=package.target,
        relative_paths=paths,
        recorded_at=NOW,
    )
    uploader = _FakeUploader("deadbeefcafebabe")
    receipt = execute_publication(
        plan=plan,
        authorization=PublicationAuthorization(
            environment=PRODUCTION_ENVIRONMENT,
            maintainer_approval=APPROVAL_VALUE,
        ),
        root=tmp_path / "archive",
        uploader=uploader,
        recorded_at=NOW,
    )
    assert receipt.state is PublicationTransportState.PUBLIC
    assert receipt.remote_revision == "deadbeefcafebabe"
    assert receipt.verification_uri == (
        "https://huggingface.co/datasets/"
        "edithatogo/global-medicines-atlas-catalogue/tree/deadbeefcafebabe"
    )
    dumped = receipt.model_dump_json()
    assert "token" not in dumped.casefold()
    assert "deadbeefcafebabe" in dumped
    assert uploader.calls[0][0] == CATALOGUE_REPOSITORY


def test_identity_probe_names_missing_hf_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(
        "global_medicines_atlas.data_layer_archive.shutil.which",
        lambda _name: None,
    )
    with pytest.raises(HuggingFaceAuthError, match="HF_TOKEN") as error:
        resolve_huggingface_identity(environment={})
    assert error.value.missing_secret == HF_TOKEN_SECRET_NAME


def test_external_gate_records_secret_name_without_logging_exception_secret(
    tmp_path: Path,
) -> None:
    record_path = archive_mod.write_huggingface_external_gate(tmp_path)
    recorded = json.loads(record_path.read_text(encoding="utf-8"))
    assert recorded["state"] == "blocked"
    assert recorded["missing_secret_name"] == HF_TOKEN_SECRET_NAME
    stdout_payload = archive_mod.huggingface_external_gate_stdout(
        record_path.name
    )
    dumped = json.dumps(stdout_payload)
    assert stdout_payload["state"] == "blocked"
    assert "missing_secret" not in dumped
    assert HF_TOKEN_SECRET_NAME not in dumped


def test_authorization_helper_stays_fail_closed() -> None:
    with pytest.raises(PermissionError):
        assert_external_write_authorized(
            PublicationAuthorization(
                environment="staging",
                maintainer_approval=APPROVAL_VALUE,
            )
        )


def test_target_rejects_non_catalogue_host() -> None:
    with pytest.raises(ValidationError):
        PublicationTarget(
            destination=PublicationDestination.HUGGING_FACE,
            repository=CATALOGUE_REPOSITORY,
            revision="main",
            public_base_url="https://example.org/datasets/secret",
        )


def test_package_file_lookup_and_unsafe_paths_fail_closed(
    tmp_path: Path,
) -> None:
    package = build_data_layer_archive(ROOT, tmp_path / "archive")
    with pytest.raises(KeyError):
        package.file("missing.bin")
    with pytest.raises(ValueError, match="unsafe"):
        assert_no_restricted_artifacts(("../secret.json",))


def test_oversize_fixture_copy_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(archive_mod, "MAX_ARCHIVAL_FILE_BYTES", 10)
    with pytest.raises(ValueError, match="exceeds"):
        build_data_layer_archive(ROOT, tmp_path / "archive")


def test_identity_probe_accepts_cli_or_env_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        archive_mod.shutil,
        "which",
        lambda name: "/bin/hf" if name == "hf" else None,
    )
    monkeypatch.setattr(archive_mod.subprocess, "run", _completed)
    assert resolve_huggingface_identity(environment={}) == "edithatogo"

    monkeypatch.setattr(archive_mod.shutil, "which", lambda _name: None)
    assert (
        resolve_huggingface_identity(
            environment={HF_TOKEN_SECRET_NAME: "present"}
        )
        == "env-token-present"
    )
    monkeypatch.setattr(archive_mod.shutil, "which", lambda _name: "/bin/hf")
    monkeypatch.setattr(archive_mod.subprocess, "run", _completed_empty)
    assert (
        resolve_huggingface_identity(
            environment={HF_TOKEN_SECRET_NAME: "present"}
        )
        == "env-token-present"
    )
    monkeypatch.setattr(archive_mod.subprocess, "run", _raise_cli_error)
    assert (
        resolve_huggingface_identity(
            environment={HF_TOKEN_SECRET_NAME: "present"}
        )
        == "env-token-present"
    )


def test_cli_uploader_records_public_revision(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        archive_mod, "resolve_huggingface_identity", lambda: "edithatogo"
    )
    monkeypatch.setattr(
        archive_mod.shutil,
        "which",
        lambda name: "/bin/huggingface-cli" if "cli" in name else None,
    )
    monkeypatch.setattr(archive_mod.subprocess, "run", _completed_empty)
    monkeypatch.setattr(archive_mod.httpx, "get", _http_revision)
    revision = HuggingFaceCliUploader().upload_folder(
        repository=CATALOGUE_REPOSITORY,
        folder=tmp_path,
        commit_message="archive",
    )
    assert revision == "cafebabe1234"


def test_cli_uploader_and_revision_probe_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        archive_mod, "resolve_huggingface_identity", lambda: "edithatogo"
    )
    monkeypatch.setattr(archive_mod.shutil, "which", lambda _name: None)
    with pytest.raises(HuggingFaceAuthError, match="HF_TOKEN"):
        HuggingFaceCliUploader().upload_folder(
            repository=CATALOGUE_REPOSITORY,
            folder=tmp_path,
            commit_message="archive",
        )
    monkeypatch.setattr(archive_mod.httpx, "get", _http_blank_revision)
    with pytest.raises(HuggingFaceAuthError, match="not publicly observable"):
        archive_mod._public_dataset_revision(CATALOGUE_REPOSITORY)
    monkeypatch.setattr(archive_mod.shutil, "which", lambda _name: "/bin/hf")
    monkeypatch.setattr(archive_mod.subprocess, "run", _raise_cli_error)
    with pytest.raises(HuggingFaceAuthError, match="HF_TOKEN"):
        HuggingFaceCliUploader().upload_folder(
            repository=CATALOGUE_REPOSITORY,
            folder=tmp_path,
            commit_message="archive",
        )


def test_execute_publication_fails_when_artifacts_change(
    tmp_path: Path,
) -> None:
    package = build_data_layer_archive(ROOT, tmp_path / "archive")
    paths = tuple(item.relative_path for item in package.files)
    plan, _prepared = prepare_publication(
        root=tmp_path / "archive",
        release_version="data-layer-archive-v1",
        target=package.target,
        relative_paths=paths,
        recorded_at=NOW,
    )
    (tmp_path / "archive" / "README.md").write_text("changed", encoding="utf-8")
    receipt = execute_publication(
        plan=plan,
        authorization=PublicationAuthorization(
            environment=PRODUCTION_ENVIRONMENT,
            maintainer_approval=APPROVAL_VALUE,
        ),
        root=tmp_path / "archive",
        uploader=_FakeUploader(),
        recorded_at=NOW,
    )
    assert receipt.state is PublicationTransportState.VERIFICATION_FAILED
    assert receipt.failure_reason is not None


EXPECTED_FDA = frozenset({
    "us-drugsfda",
    "us-fda-orange-book",
    "us-gsrs-unii",
    "us-openfda-drugsfda",
    "us-openfda-ndc",
})
EXPECTED_EMA = frozenset({
    "eu-ema-article57",
    "eu-ema-json",
    "eu-ema-medicines",
    "eu-ema-pms-fhir",
    "eu-spor-rms-oms",
    "eu-union-register",
})
EXPECTED_TGA = frozenset({
    "au-artg",
    "au-tga-pi-cmi",
    "au-tga-regulatory-events",
})
EXPECTED_MEDSAFE = frozenset({
    "nz-medsafe-documents",
    "nz-medsafe-products",
})
GATED_SCOPED = frozenset({"eu-ema-pms-fhir", "eu-spor-rms-oms"})
WORKFLOW = ROOT / ARCHIVE_WORKFLOW_RELATIVE


class _FakeRetriever:
    def __init__(self, *, fail_ids: frozenset[str] = frozenset()) -> None:
        self.fail_ids = fail_ids
        self.calls: list[str] = []

    def retrieve(self, source: MedicineDataSource) -> RetrievedPayload:
        source_id = source.source_id
        self.calls.append(source_id)
        uri = str(source.download_url or source.api_url or source.landing_page)
        if source_id in self.fail_ids:
            return RetrievedPayload(
                source_id=source_id,
                uri=uri,
                content=b"",
                content_type="application/octet-stream",
                retrieved_at="2026-08-19T00:00:00+00:00",
                attempts=3,
                sha256="",
                kind=PayloadKind.REPRESENTATIVE_FIXTURE,
                skip_reason="live_retrieval_failed_after_3_attempts",
            )
        payload = f"{source_id}:live\n".encode()
        return RetrievedPayload(
            source_id=source_id,
            uri=uri,
            content=payload,
            content_type="text/plain",
            retrieved_at="2026-08-19T00:00:00+00:00",
            attempts=1,
            sha256=hashlib.sha256(payload).hexdigest(),
            kind=PayloadKind.LIVE_PUBLIC,
            skip_reason="",
        )


def test_authority_groups_cover_fda_ema_tga_and_medsafe() -> None:
    catalog = load_source_catalog()
    grouped: dict[AuthorityGroup, set[str]] = {
        group: set() for group in SCOPED_AUTHORITY_GROUPS
    }
    for source in catalog:
        group = classify_authority_group(source)
        if group in grouped:
            grouped[group].add(source.source_id)
    assert grouped[AuthorityGroup.FDA] == EXPECTED_FDA
    assert grouped[AuthorityGroup.EMA] == EXPECTED_EMA
    assert grouped[AuthorityGroup.TGA] == EXPECTED_TGA
    assert grouped[AuthorityGroup.MEDSAFE] == EXPECTED_MEDSAFE
    ids = {source.source_id for source in catalog}
    assert "ph-fda-verification" in ids
    assert (
        classify_authority_group(
            next(s for s in catalog if s.source_id == "ph-fda-verification")
        )
        is AuthorityGroup.OTHER
    )
    assert (
        classify_authority_group(
            next(s for s in catalog if s.source_id == "au-pbs-api")
        )
        is AuthorityGroup.OTHER
    )
    assert (
        classify_authority_group(
            next(s for s in catalog if s.source_id == "nz-nzulm-bulk")
        )
        is AuthorityGroup.OTHER
    )


def test_scoped_public_sources_archive_payloads_and_metadata(
    tmp_path: Path,
) -> None:
    retriever = _FakeRetriever()
    package = build_data_layer_archive(
        ROOT,
        tmp_path / "archive",
        retriever=retriever,
    )
    relative = {item.relative_path for item in package.files}
    by_id = {row.source_id: row for row in package.inventory.sources}
    scoped = EXPECTED_FDA | EXPECTED_EMA | EXPECTED_TGA | EXPECTED_MEDSAFE
    assert scoped >= GATED_SCOPED
    assert set(retriever.calls) == scoped - GATED_SCOPED
    assert "nz-nzulm-bulk" not in retriever.calls
    assert "eu-ema-pms-fhir" not in retriever.calls
    for source_id in scoped:
        row = by_id[source_id]
        meta_path = f"metadata/sources/{source_id}.json"
        assert meta_path in relative
        metadata = json.loads(
            package.file(meta_path).read_text(encoding="utf-8")
        )
        assert metadata["source_id"] == source_id
        assert metadata["authority"] == row.authority
        assert metadata["dimension"] == row.dimension
        assert metadata["rights_status"]
        assert metadata["landing_page"]
        assert "native_identifier" in metadata
        if source_id in GATED_SCOPED:
            assert row.access_class is AccessClass.CREDENTIAL_RESTRICTED
            assert row.archival_disposition is (
                ArchivalDisposition.CATALOG_METADATA_ONLY
            )
            assert row.payload_kind is PayloadKind.METADATA_ONLY
            assert not any(
                path.startswith(f"payloads/{source_id}/") for path in relative
            )
            continue
        assert row.access_class is AccessClass.PUBLIC_NO_CREDENTIAL
        assert row.payload_kind is PayloadKind.LIVE_PUBLIC
        assert row.archival_disposition is (
            ArchivalDisposition.CATALOG_AND_LIVE_PAYLOAD
        )
        assert row.payload_sha256
        assert any(
            path.startswith(f"payloads/{source_id}/") for path in relative
        )
        assert metadata["payload_sha256"] == row.payload_sha256
        assert metadata["retrieval_uri"]
    manifest = json.loads(
        package.file("inventory/archival-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["live_source_dump_downloaded"] is True
    assert set(manifest["authority_groups"]) == {
        "fda",
        "ema",
        "tga",
        "medsafe",
    }
    assert manifest["publisher"] == "github-actions"
    assert manifest["workflow"] == ARCHIVE_WORKFLOW_RELATIVE
    assert "nz-nzulm-bulk" in manifest["skipped_source_ids"]
    assert "eu-ema-pms-fhir" in manifest["skipped_source_ids"]
    assert all(
        "vendor/nzmedicines" not in path and "nzulm" not in path
        for path in relative
    )


def test_failed_live_retrieval_is_labelled_fixture_not_completion(
    tmp_path: Path,
) -> None:
    retriever = _FakeRetriever(fail_ids=frozenset({"us-fda-orange-book"}))
    package = build_data_layer_archive(
        ROOT,
        tmp_path / "archive",
        retriever=retriever,
    )
    row = next(
        item
        for item in package.inventory.sources
        if item.source_id == "us-fda-orange-book"
    )
    assert row.payload_kind is PayloadKind.REPRESENTATIVE_FIXTURE
    assert row.skip_reason == "live_retrieval_failed_after_3_attempts"
    metadata = json.loads(
        package.file("metadata/sources/us-fda-orange-book.json").read_text(
            encoding="utf-8"
        )
    )
    assert metadata["skip_reason"] == row.skip_reason
    assert metadata["live_attempts"] == 3


def test_http_retriever_caps_size_and_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "too-large" in str(request.url):
            return httpx.Response(200, content=b"x" * 64)
        return httpx.Response(503, content=b"retry")

    retriever = HttpPayloadRetriever(
        transport=httpx.MockTransport(handler),
        max_bytes=32,
        max_attempts=3,
    )
    catalog = load_source_catalog()
    orange = next(
        source for source in catalog if source.source_id == "us-fda-orange-book"
    )
    failed = retriever.retrieve(orange)
    assert failed.kind is PayloadKind.REPRESENTATIVE_FIXTURE
    assert failed.attempts == 3
    huge = orange.model_copy(
        update={
            "download_url": "https://www.fda.gov/too-large",
            "landing_page": "https://www.fda.gov/too-large",
        }
    )
    oversize = HttpPayloadRetriever(
        transport=httpx.MockTransport(handler),
        max_bytes=32,
    ).retrieve(huge)
    assert oversize.kind is PayloadKind.REPRESENTATIVE_FIXTURE
    assert oversize.skip_reason == "live_file_too_large"


def test_drugsfda_retrieval_uses_governed_bulk_url() -> None:
    source = next(
        item
        for item in load_source_catalog()
        if item.source_id == "us-drugsfda"
    )
    uris = retrieval_uris_for_source(source)
    assert any("media/89850" in uri for uri in uris)


def test_parse_authority_groups_defaults_and_rejects_unknown() -> None:
    assert parse_authority_groups("") == SCOPED_AUTHORITY_GROUPS
    assert parse_authority_groups(" fda , tga ") == frozenset({
        AuthorityGroup.FDA,
        AuthorityGroup.TGA,
    })
    with pytest.raises(ValueError, match="unsupported archival authority"):
        parse_authority_groups("fda,other")
    with pytest.raises(ValueError, match="is not a valid AuthorityGroup"):
        parse_authority_groups("nope")


def test_authority_group_uses_source_id_prefix_when_authority_text_differs() -> (
    None
):
    source = next(
        item
        for item in load_source_catalog()
        if item.source_id == "us-gsrs-unii"
    )
    renamed = source.model_copy(update={"authority": "NIH NCATS"})
    assert classify_authority_group(renamed) is AuthorityGroup.FDA


def test_http_retriever_archives_live_public_bytes() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'{"ok": true}',
            headers={"content-type": "application/json"},
        )

    source = next(
        item
        for item in load_source_catalog()
        if item.source_id == "us-openfda-drugsfda"
    )
    retriever = HttpPayloadRetriever(
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    )
    retrieved = retriever.retrieve(source)
    assert retrieved.kind is PayloadKind.LIVE_PUBLIC
    assert retrieved.content == b'{"ok": true}'
    assert retrieved.filename == "drugsfda.json"
    assert retrieved.attempts == 1
    orange = next(
        item
        for item in load_source_catalog()
        if item.source_id == "us-fda-orange-book"
    )
    extensionless = retriever.retrieve(orange)
    assert extensionless.filename == "public-artefact.bin"


def test_http_retriever_labels_disallowed_hosts_and_http_errors() -> None:
    source = next(
        item
        for item in load_source_catalog()
        if item.source_id == "us-fda-orange-book"
    )
    blocked = source.model_copy(
        update={
            "landing_page": "http://www.fda.gov/orange-book",
            "download_url": "http://www.fda.gov/orange-book.zip",
            "api_url": None,
        }
    )
    labelled = HttpPayloadRetriever(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200)),
        max_attempts=3,
    ).retrieve(blocked)
    assert labelled.kind is PayloadKind.REPRESENTATIVE_FIXTURE
    assert labelled.skip_reason == "host_not_in_catalog"

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable")

    failed = HttpPayloadRetriever(
        transport=httpx.MockTransport(handler),
        max_attempts=3,
    ).retrieve(source)
    assert failed.kind is PayloadKind.REPRESENTATIVE_FIXTURE
    assert failed.attempts == 3
    assert failed.skip_reason == "live_retrieval_failed_after_3_attempts"


def test_http_retriever_caps_chunked_payloads_without_content_length() -> None:
    def body() -> object:
        yield b"x" * 20
        yield b"x" * 20

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body())

    source = next(
        item
        for item in load_source_catalog()
        if item.source_id == "au-tga-pi-cmi"
    )
    oversize = HttpPayloadRetriever(
        transport=httpx.MockTransport(handler),
        max_bytes=24,
    ).retrieve(source)
    assert oversize.kind is PayloadKind.REPRESENTATIVE_FIXTURE
    assert oversize.skip_reason == "live_file_too_large"


def test_uri_allowlist_includes_api_host_when_download_url_is_absent() -> None:
    source = next(
        item
        for item in load_source_catalog()
        if item.source_id == "us-openfda-drugsfda"
    )
    api_only = source.model_copy(update={"download_url": None})
    assert archive_mod._uri_is_allowed(str(api_only.api_url), api_only)
    assert not archive_mod._uri_is_allowed("https://example.test/x", api_only)


def test_archive_workflow_is_sha_pinned_and_covers_four_authorities() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert WORKFLOW.is_file()
    assert "workflow_dispatch:" in workflow
    assert "pull_request:" in workflow
    assert "scripts/archive_data_layer.py" in workflow
    assert "--retrieve" in workflow
    assert "fda,ema,tga,medsafe" in workflow
    assert HF_TOKEN_SECRET_NAME in workflow
    assert "secrets.HF_TOKEN" in workflow
    assert "--upload" in workflow
    assert (
        "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803" in workflow
    )
    assert (
        "astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b"
        in workflow
    )
    assert (
        "actions/upload-artifact@"
        "b7c566a772e6b6bfb58ed0dc250532a479d7789f" in workflow
    )
    assert "persist-credentials: false" in workflow
    assert "permissions:" in workflow
    assert "contents: read" in workflow
    assert HUGGINGFACE_HUB_PIN in workflow
    publish_at = workflow.index("Publish to Hugging Face")
    assert "--upload" in workflow[publish_at:]
    package_block = workflow[:publish_at]
    assert "--upload" not in package_block
    assert "vendor/nzmedicines" not in workflow
    assert "nz-nzulm-bulk" not in workflow or "skip" in workflow.casefold()
