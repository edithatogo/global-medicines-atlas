"""Contracts for no-credential data-layer archival."""

from __future__ import annotations

import json
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError

from global_medicines_atlas import data_layer_archive as archive_mod
from global_medicines_atlas.data_layer_archive import (
    CATALOGUE_REPOSITORY,
    FIXTURE_PROVENANCE_NOTE,
    HF_TOKEN_SECRET_NAME,
    MAX_ARCHIVAL_FILE_BYTES,
    RESTRICTED_PATH_PREFIXES,
    AccessClass,
    ArchivalDisposition,
    HuggingFaceAuthError,
    HuggingFaceCliUploader,
    assert_no_restricted_artifacts,
    build_data_layer_archive,
    classify_source_access,
    inventory_data_layer,
    resolve_huggingface_identity,
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
from global_medicines_atlas.source_catalog import load_source_catalog
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
