"""Fail-closed boundaries for bulk archive publication."""

from __future__ import annotations

import hashlib
import io
import json
import sys
import types
import zipfile
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import httpx
import pytest
from scripts import publish_bulk_archive as publisher
from scripts import publish_fresh_openfda as fresh
from scripts import publish_october_openfda_hosted as october

from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main as real_require_hosted_main,
)
from global_medicines_atlas.publication_transport import (
    ArtifactBinding,
    ArtifactVerification,
    PublicationDestination,
    PublicationPlan,
    PublicationTarget,
)

COMMIT = "a" * 40
SYNTHETIC_HF_TOKEN = "synthetic-token"  # ruff: ignore[hardcoded-password-string] -- synthetic fixture, not a credential.


def test_october_hosted_resume_uses_verified_batches() -> None:
    files = {
        "first.zip": b"first",
        "second.zip": b"second",
        "third.zip": b"third",
    }
    artifacts = tuple(
        ArtifactBinding(
            relative_path=path,
            size=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
        )
        for path, body in files.items()
    )
    plan = PublicationPlan(
        release_version=october.BATCH,
        target=PublicationTarget(
            destination=PublicationDestination.HUGGING_FACE,
            repository=october.REPOSITORY,
            revision="main",
            public_base_url=f"https://huggingface.co/datasets/{october.REPOSITORY}",
        ),
        artifacts=artifacts,
    )
    api = Mock()
    api.repo_info.return_value = types.SimpleNamespace(
        sha=COMMIT, private=False
    )
    first = artifacts[0]
    remote = types.SimpleNamespace(
        path=first.relative_path,
        size=first.size,
        lfs=types.SimpleNamespace(sha256=first.sha256, size=first.size),
    )
    api.list_repo_tree.return_value = [remote]
    api.list_repo_files.return_value = [".gitattributes", *files]
    committed = "b" * 40
    scratch_files = []

    def commit(_repo, *, parent_commit, operations, **_kw):
        assert parent_commit == COMMIT
        assert [operation.path_in_repo for operation in operations] == [
            "second.zip",
            "third.zip",
        ]
        for operation in operations:
            scratch_files.append(operation.path_or_fileobj)
            assert (
                operation.path_or_fileobj.read_bytes()
                == files[operation.path_in_repo]
            )
        return types.SimpleNamespace(oid=committed)

    api.create_commit.side_effect = commit
    hub = types.SimpleNamespace(
        RepoFile=types.SimpleNamespace, CommitOperationAdd=types.SimpleNamespace
    )
    requests = []

    def serve(request):
        path = request.url.path.removeprefix("/")
        requests.append(path)
        return httpx.Response(200, stream=httpx.ByteStream(files[path]))

    with httpx.Client(
        base_url=october.source_origin("http://100.64.1.2:18043/"),
        transport=httpx.MockTransport(serve),
    ) as client:
        assert october.publish_batches(api, hub, client, plan) == committed
    assert sorted(requests) == ["second.zip", "third.zip"]
    assert scratch_files
    assert all(not path.exists() for path in scratch_files)
    remote.lfs.sha256 = "0" * 64
    with pytest.raises(ValueError, match="destination checksum differs"):
        october.remaining_artifacts(api, hub, plan)


def test_october_hosted_download_checks_each_source_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parts = {"0-3": b"abcd", "4-7": b"efgh", "8-9": b"ij"}
    body = b"".join(parts.values())
    artifact = ArtifactBinding(
        relative_path="archive.zip",
        size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
    )
    output = tmp_path / artifact.relative_path
    monkeypatch.setattr(october, "SOURCE_REQUEST_BYTES", 4)
    ranges_seen = []
    corrupt_range = False

    def serve(request):
        requested = request.headers["Range"].removeprefix("bytes=")
        ranges_seen.append(requested)
        returned = "0-3" if corrupt_range and requested == "4-7" else requested
        return httpx.Response(
            206,
            headers={"Content-Range": f"bytes {returned}/{len(body)}"},
            stream=httpx.ByteStream(parts[requested]),
        )

    with httpx.Client(
        base_url="http://100.64.1.2:18043/",
        transport=httpx.MockTransport(serve),
    ) as client:
        october.download_artifact(client, artifact, output)
        assert output.read_bytes() == body
        assert ranges_seen == list(parts)
        corrupt_range = True
        with pytest.raises(ValueError, match="source range differs"):
            october.download_artifact(client, artifact, output)


def fresh_openfda_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    first, second = "drug/event/first.json.zip", "drug/event/second.json.zip"
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("data.json", "{}")
        payload = buffer.getvalue()
    index = fresh.json_bytes({
        "meta": {"last_updated": "2026-11-20"},
        "results": {
            "drug": {
                "event": {
                    "partitions": [
                        {"file": fresh.ZIP_ROOT + path}
                        for path in (first, second)
                    ]
                }
            },
            "device": {
                "udi": {
                    "partitions": [
                        {
                            "file": fresh.ZIP_ROOT
                            + "device/udi/excluded.json.zip"
                        }
                    ]
                }
            },
        },
    })
    contract = {
        "source_index_sha256": hashlib.sha256(index).hexdigest(),
        "source_index_date": "2026-11-20",
        "indexed_endpoints": 2,
        "indexed_payload_count": 3,
        "expected_endpoints": 1,
        "expected_payload_count": 2,
        "excluded_endpoint": "device/udi",
        "excluded_payload_count": 1,
        "source_url": fresh.INDEX_URL,
        "repository": fresh.REPOSITORY,
        "publication_approved": True,
        "rights": {},
    }
    contract_path = tmp_path / "contract.json"
    contract_path.write_bytes(fresh.json_bytes(contract))
    monkeypatch.setattr(fresh, "CONTRACT", contract_path)
    monkeypatch.setattr(fresh, "BATCH_SIZE", 1)
    return first, second, index, payload, contract


def test_fresh_openfda_publishes_and_verifies_bounded_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second, index, payload, _ = fresh_openfda_fixture(
        tmp_path, monkeypatch
    )
    for name, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": COMMIT,
        "GITHUB_RUN_ID": "12345",
        "GMA_MAINTAINER_PUBLICATION_APPROVED": "yes-i-approve-publication",
        "GMA_PUBLICATION_ENVIRONMENT": "production",
        "HF_TOKEN": SYNTHETIC_HF_TOKEN,
    }.items():
        monkeypatch.setenv(name, value)
    requests = []

    def serve(request):
        url = str(request.url)
        if url == fresh.INDEX_URL:
            return httpx.Response(200, content=index)
        requests.append(url)
        if len(requests) == 1:
            return httpx.Response(503)
        return httpx.Response(
            200,
            headers={"Content-Length": str(len(payload)), "ETag": '"source"'},
            stream=httpx.ByteStream(payload),
        )

    monkeypatch.setattr(
        fresh,
        "BoundIPAddressTransport",
        lambda **_kw: httpx.MockTransport(serve),
    )
    monkeypatch.setattr(fresh.time, "sleep", lambda _delay: None)
    api = Mock()
    api.repo_info.return_value = types.SimpleNamespace(
        private=False, sha=COMMIT
    )
    api.list_repo_files.return_value = [".gitattributes"]
    published = {}
    scratch_files = []
    revision = "b" * 40

    def preupload(_repo, *, additions, repo_type):
        assert repo_type == "dataset"
        (operation,) = additions
        path = Path(operation.path_or_fileobj)
        scratch_files.append(path)
        if operation.path_in_repo == first:
            published[first] = path.read_bytes()
            operation.path_or_fileobj = b""

    def commit(_repo, *, operations, parent_commit, **_kw):
        assert parent_commit == COMMIT
        assert all(not path.exists() for path in scratch_files)
        for operation in operations:
            if operation.path_or_fileobj != b"":
                published[operation.path_in_repo] = operation.path_or_fileobj
        return types.SimpleNamespace(oid=revision)

    api.preupload_lfs_files.side_effect = preupload
    api.create_commit.side_effect = commit
    hub = types.SimpleNamespace(
        HfApi=lambda **_kw: api,
        CommitOperationAdd=types.SimpleNamespace,
    )
    monkeypatch.setattr(fresh, "import_module", lambda _name: hub)

    def readback(*, target, revision, artifact):
        body = published[artifact.relative_path]
        return ArtifactVerification(
            relative_path=artifact.relative_path,
            sha256=hashlib.sha256(body).hexdigest(),
            size=len(body),
            verification_uri=f"{target.public_base_url}/resolve/{revision}/{artifact.relative_path}",
        )

    monkeypatch.setattr(
        fresh,
        "HuggingFaceAnonymousArtifactVerifier",
        lambda **_kw: types.SimpleNamespace(verify_artifact=readback),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "publisher",
            "publish",
            "--output",
            str(tmp_path),
            "--exact-commit",
            COMMIT,
        ],
    )
    assert fresh.main() == 0
    sys.argv[1] = "verify"
    assert fresh.main() == 0
    assert requests == [fresh.ZIP_ROOT + first] * 2 + [fresh.ZIP_ROOT + second]
    assert published[first] == published[second] == payload
    assert (
        json.loads((tmp_path / "verified.json").read_bytes())["state"]
        == "public"
    )
    manifest = json.loads(published["ARTIFACT-MANIFEST.json"])
    receipts = {record["path"]: record for record in manifest["artifacts"]}
    assert receipts[first]["source_etag"] == '"source"'
    assert manifest["excluded_payload_count"] == 1
    monkeypatch.setenv("GITHUB_RUN_ID", "54321")
    with pytest.raises(ValueError, match="receipts do not match"):
        fresh.verify(tmp_path, COMMIT)


def test_fresh_openfda_refuses_local_or_changed_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, index, _, contract = fresh_openfda_fixture(tmp_path, monkeypatch)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="Actions dispatch on main"):
        fresh.publish(tmp_path, COMMIT)
    with pytest.raises(ValueError, match="FDA index SHA-256"):
        fresh.index_paths(index + b" ", contract)
    foreign_index = index.replace(b"download.open.fda.gov", b"example.test")
    foreign_contract = {
        **contract,
        "source_index_sha256": hashlib.sha256(foreign_index).hexdigest(),
    }
    with pytest.raises(ValueError, match="unapproved ZIP URL"):
        fresh.index_paths(foreign_index, foreign_contract)


def write_contract(tmp_path: Path, **overrides: object) -> Path:
    """Create a contract in the committed source-batch shape."""
    batch = tmp_path / "quality/source-batches/synthetic"
    batch.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "batch_id": "synthetic",
        "repository": "owner/synthetic",
        "publication_approved": True,
        "approval_reference": "Synthetic maintainer approval.",
        "snapshot_id": "synthetic-snapshot",
        "source_authority": "Synthetic authority",
        "source_url": "https://example.gov/data",
        "retrieval_date": "2026-01-01",
        "schema_version": "synthetic/v1",
        "pretty_name": "Synthetic archive",
        "description": "Synthetic description.",
        "fields_and_transformations": "Unmodified synthetic source bytes.",
        "payload_suffix": ".bin",
        "expected_payload_count": 2,
        "expected_payload_bytes": 6,
        "rights": {
            "licence": "Synthetic public domain",
            "terms": "https://example.gov/terms",
            "attribution": "Synthetic authority, https://example.gov/data",
            "redistribution": "Permitted for unmodified source bytes.",
        },
        "not_included": ["No derived tables."],
    }
    manifest.update(overrides)
    path = batch / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def write_archive(tmp_path: Path) -> Path:
    """Create a two-payload archive matching the default contract."""
    root = tmp_path / "archive"
    (root / "group").mkdir(parents=True)
    (root / "group" / "first.bin").write_bytes(b"abc")
    (root / "second.bin").write_bytes(b"def")
    return root


@pytest.fixture(autouse=True)
def committed_batches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        publisher, "BATCHES", tmp_path / "quality/source-batches"
    )
    monkeypatch.setattr(publisher, "require_hosted_main", lambda _c: None)


def test_local_invocation_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        publisher, "require_hosted_main", real_require_hosted_main
    )
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    manifest = write_contract(tmp_path)
    with pytest.raises(ValueError, match="Actions dispatch on main"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_unapproved_contract_is_refused(tmp_path: Path) -> None:
    manifest = write_contract(tmp_path, publication_approved=False)
    with pytest.raises(ValueError, match="not approved"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_manifest_outside_source_batches_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    manifest = outside / "manifest.json"
    manifest.write_text(json.dumps({"publication_approved": True}))
    with pytest.raises(ValueError, match="committed source-batch"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_payload_count_drift_is_refused(tmp_path: Path) -> None:
    manifest = write_contract(tmp_path, expected_payload_count=3)
    with pytest.raises(ValueError, match="payload count differs"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_payload_byte_drift_is_refused(tmp_path: Path) -> None:
    manifest = write_contract(tmp_path, expected_payload_bytes=7)
    with pytest.raises(ValueError, match="payload bytes differ"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_recorded_digest_mismatch_is_refused(tmp_path: Path) -> None:
    manifest = write_contract(
        tmp_path,
        recorded_payload_digests={"second.bin": "0" * 64},
    )
    with pytest.raises(ValueError, match="recorded payload digest differs"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_prepare_binds_every_file_without_upload(tmp_path: Path) -> None:
    archive = write_archive(tmp_path)
    output = tmp_path / "out"
    assert (
        publisher.publish_bulk_archive(
            write_contract(tmp_path), archive, output, COMMIT
        )
        == 0
    )
    plan = json.loads(
        (output / "publication-receipts" / "plan.json").read_text()
    )
    bound = [item["relative_path"] for item in plan["artifacts"]]
    assert bound == sorted(
        str(path.relative_to(archive))
        for path in archive.rglob("*")
        if path.is_file()
    )
    assert plan["target"]["repository"] == "owner/synthetic"
    assert "ARTIFACT-MANIFEST.json" in bound
    assert "allow_identical_content" not in plan


def test_prepared_bulk_archive_keeps_identical_files_at_distinct_paths(
    tmp_path: Path,
) -> None:
    archive = write_archive(tmp_path)
    (archive / "second.bin").write_bytes(b"abc")
    output = tmp_path / "out"
    manifest = write_contract(tmp_path, allow_identical_content=True)

    assert (
        publisher.publish_bulk_archive(manifest, archive, output, COMMIT) == 0
    )

    report = output / "publication-receipts" / "plan.json"
    plan = json.loads(report.read_text())
    assert plan["allow_identical_content"] is True
    payloads = [
        item
        for item in plan["artifacts"]
        if item["relative_path"].endswith(".bin")
    ]
    assert [item["relative_path"] for item in payloads] == [
        "group/first.bin",
        "second.bin",
    ]
    assert payloads[0]["sha256"] == payloads[1]["sha256"]


def test_card_records_rights_and_scope(tmp_path: Path) -> None:
    archive = write_archive(tmp_path)
    publisher.publish_bulk_archive(
        write_contract(tmp_path), archive, tmp_path / "out", COMMIT
    )
    card = (archive / "README.md").read_text()
    assert "Synthetic authority" in card
    assert "Permitted for unmodified source bytes." in card
    assert "## What this archive is not" in card
    assert "- No derived tables." in card


def test_publish_refuses_without_external_write_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GMA_PUBLICATION_ENVIRONMENT", raising=False)
    monkeypatch.delenv("GMA_MAINTAINER_PUBLICATION_APPROVED", raising=False)
    with pytest.raises(PermissionError, match="explicit maintainer approval"):
        publisher.publish_bulk_archive(
            write_contract(tmp_path),
            write_archive(tmp_path),
            tmp_path / "out",
            COMMIT,
            publish=True,
        )


class _CommitInfo:
    oid = "b" * 40


class _RecordingApi:
    """Record exactly how the hub is called by the uploader."""

    def __init__(self) -> None:
        self.token = ""
        self.created: list[dict[str, object]] = []
        self.uploaded: list[dict[str, object]] = []

    def create_repo(self, **kwargs: object) -> None:
        self.created.append(kwargs)

    def upload_folder(self, **kwargs: object) -> _CommitInfo:
        self.uploaded.append(kwargs)
        return _CommitInfo()


class _HfApiFactory:
    """Stand in for ``HfApi`` and hand every instance to the recorder."""

    def __init__(self, api: _RecordingApi) -> None:
        self._api = api

    def __call__(self, *, token: str) -> _RecordingApi:
        self._api.token = token
        return self._api


def test_uploader_calls_only_supported_hub_keywords(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guard the hub call shape: an unsupported keyword fails only at runtime."""

    api = _RecordingApi()
    module = types.ModuleType("huggingface_hub")
    cast("Any", module).HfApi = _HfApiFactory(api)
    monkeypatch.setitem(sys.modules, "huggingface_hub", module)
    monkeypatch.setenv("HF_TOKEN", SYNTHETIC_HF_TOKEN)
    folder = write_archive(tmp_path)

    revision = publisher.HuggingFaceFolderUploader(
        repository="owner/synthetic"
    ).upload_folder(
        repository="owner/synthetic",
        folder=folder,
        commit_message="Archive synthetic",
    )

    assert revision == "b" * 40
    assert api.token == SYNTHETIC_HF_TOKEN
    assert api.created == [
        {
            "repo_id": "owner/synthetic",
            "repo_type": "dataset",
            "private": False,
            "exist_ok": True,
        }
    ]
    assert api.uploaded == [
        {
            "repo_id": "owner/synthetic",
            "repo_type": "dataset",
            "folder_path": folder,
            "commit_message": "Archive synthetic",
        }
    ]


def test_uploader_refuses_a_different_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HF_TOKEN", SYNTHETIC_HF_TOKEN)
    with pytest.raises(ValueError, match="target differs"):
        publisher.HuggingFaceFolderUploader(
            repository="owner/synthetic"
        ).upload_folder(
            repository="owner/other",
            folder=write_archive(tmp_path),
            commit_message="Archive other",
        )
