from __future__ import annotations

import json
import sys
from operator import itemgetter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import scripts.append_australian_mbs_root_manifest as manifest_publisher
from jsonschema import Draft202012Validator
from scripts.append_australian_mbs_root_manifest import (
    CONTRACT,
    ROOT,
    build_updated_manifest,
    publish,
    read_json,
    verify_static_authority,
)


def _contract() -> dict[str, Any]:
    return read_json(ROOT / CONTRACT)


def _manifest(contract: dict[str, Any]) -> dict[str, Any]:
    obj = contract["object"]
    return {
        "schema_id": "global-medicines-atlas.harvest-manifest",
        "schema_version": 1,
        "dataset": contract["dataset"],
        "generated_at": "2026-10-04T00:07:34Z",
        "file_count": 2,
        "files": [
            {
                "path": "raw/mbs/releases/Downloads-20260801/MBS-XML-20260801.XML",
                "bytes": obj["bytes"],
                "sha256": obj["sha256"],
                "kind": "raw_payload",
                "source_id": "au-mbs",
                "category": "monthly_schedule_xml",
            },
            {
                "path": "raw/mbs/releases/Downloads-20260701/MBS-XML-20260701.XML",
                "bytes": 8291891,
                "sha256": "5" * 64,
                "kind": "raw_payload",
                "source_id": "au-mbs",
                "category": "monthly_schedule_xml",
            },
        ],
        "latest_run_coverage": {"status": "partial", "failed_resources": []},
    }


def test_contract_schema_and_pinned_rights_evidence_pass() -> None:
    schema = json.loads(
        (
            ROOT
            / "schemas/australian-m112-root-manifest-append-contract-v1.json"
        ).read_text(encoding="utf-8")
    )
    contract = _contract()
    cast("Any", Draft202012Validator(schema)).validate(contract)
    verify_static_authority(contract)


def test_append_adds_one_exact_row_and_preserves_all_existing_metadata() -> (
    None
):
    contract = _contract()
    original = _manifest(contract)

    updated, changed = build_updated_manifest(
        original, contract, generated_at="2026-10-17T12:00:00Z"
    )

    assert changed is True
    assert updated["file_count"] == original["file_count"] + 1
    assert updated["generated_at"] == "2026-10-17T12:00:00Z"
    assert updated["latest_run_coverage"] == original["latest_run_coverage"]
    assert updated["files"] == sorted(updated["files"], key=itemgetter("path"))
    assert all(row in updated["files"] for row in original["files"])
    assert next(
        row
        for row in updated["files"]
        if row["path"] == contract["object"]["path"]
    ) == {
        "path": contract["object"]["path"],
        "bytes": contract["object"]["bytes"],
        "sha256": contract["object"]["sha256"],
        "kind": "raw_payload",
        "source_id": "au-mbs",
        "category": "monthly_schedule_xml",
    }
    assert any(
        row["path"] == contract["object"]["preserved_alias_path"]
        for row in updated["files"]
    )


def test_append_is_idempotent_after_an_ambiguous_success() -> None:
    contract = _contract()
    once, _ = build_updated_manifest(
        _manifest(contract), contract, generated_at="2026-10-17T12:00:00Z"
    )

    twice, changed = build_updated_manifest(
        once, contract, generated_at="2026-10-18T00:00:00Z"
    )

    assert changed is False
    assert twice == once


def test_append_fails_closed_on_conflicting_target_or_alias_identity() -> None:
    contract = _contract()
    conflicting = _manifest(contract)
    conflicting["files"].append({
        "path": contract["object"]["path"],
        "bytes": contract["object"]["bytes"],
        "sha256": "0" * 64,
        "kind": "raw_payload",
        "source_id": "au-mbs",
        "category": "monthly_schedule_xml",
    })
    conflicting["file_count"] += 1
    with pytest.raises(ValueError, match="conflicting object row"):
        build_updated_manifest(
            conflicting, contract, generated_at="2026-10-17T12:00:00Z"
        )

    wrong_alias = _manifest(contract)
    wrong_alias["files"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="historical alias"):
        build_updated_manifest(
            wrong_alias, contract, generated_at="2026-10-17T12:00:00Z"
        )


def test_append_fails_closed_when_manifest_count_or_rows_are_ambiguous() -> (
    None
):
    contract = _contract()
    wrong_count = _manifest(contract)
    wrong_count["file_count"] = 99
    with pytest.raises(ValueError, match="unsupported shape"):
        build_updated_manifest(
            wrong_count, contract, generated_at="2026-10-17T12:00:00Z"
        )

    duplicate = _manifest(contract)
    duplicate["files"].append(dict(duplicate["files"][0]))
    duplicate["file_count"] += 1
    with pytest.raises(ValueError, match="duplicate paths"):
        build_updated_manifest(
            duplicate, contract, generated_at="2026-10-17T12:00:00Z"
        )


def test_static_authority_detects_changed_approval_evidence(
    tmp_path: Path,
) -> None:
    contract = _contract()
    for reference in contract["evidence_inputs"].values():
        source = ROOT / reference["path"]
        target = tmp_path / reference["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    authorization_path = (
        tmp_path
        / contract["evidence_inputs"]["publication_authorization"]["path"]
    )
    authorization_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="evidence changed"):
        verify_static_authority(contract, root=tmp_path)


def test_publish_rejects_stale_parent_before_any_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = _contract()
    obj = contract["object"]
    base_manifest = _manifest(contract)
    base_bytes = (
        json.dumps(base_manifest, indent=2, sort_keys=True) + "\n"
    ).encode()
    contract["expected_parent_revision"] = "a" * 40
    state: dict[str, Any] = {
        "revision": "d" * 40,
        "commits": 0,
    }

    class FakeApi:
        def dataset_info(
            self,
            _dataset: str,
            *,
            revision: str | None = None,
            **_kwargs: Any,
        ) -> Any:
            return SimpleNamespace(
                private=False,
                gated=False,
                sha=revision or state["revision"],
                siblings=[
                    SimpleNamespace(
                        rfilename=path,
                        size=obj["bytes"],
                        blob_id=obj["expected_blob_id"],
                    )
                    for path in (obj["path"], obj["preserved_alias_path"])
                ],
            )

        def create_commit(self, **_kwargs: Any) -> Any:
            state["commits"] += 1
            raise AssertionError("stale manifest must never be committed")

    def fake_download(
        *,
        repo_id: str,
        repo_type: str,
        filename: str,
        revision: str,
        token: bool,
        cache_dir: Path,
    ) -> str:
        assert repo_id == contract["dataset"]
        assert repo_type == "dataset"
        assert filename == "manifest.json"
        assert revision == state["revision"]
        assert token is False
        target = cache_dir / revision / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base_bytes)
        return str(target)

    def fake_read_json(_path: Path) -> dict[str, Any]:
        return contract

    def fake_verify_static_authority(_contract: dict[str, Any]) -> None:
        return None

    def fake_require_hosted_main(_commit: str) -> None:
        return None

    def fake_api_factory(**_kwargs: Any) -> FakeApi:
        return FakeApi()

    def fake_commit_operation(**_kwargs: Any) -> None:
        return None

    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setattr(manifest_publisher, "ROOT", tmp_path)
    monkeypatch.setattr(manifest_publisher, "read_json", fake_read_json)
    monkeypatch.setattr(
        manifest_publisher,
        "verify_static_authority",
        fake_verify_static_authority,
    )
    monkeypatch.setattr(
        manifest_publisher, "_require_hosted_main", fake_require_hosted_main
    )
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(
            CommitOperationAdd=fake_commit_operation,
            HfApi=fake_api_factory,
            hf_hub_download=fake_download,
        ),
    )

    receipt_path = tmp_path / "build/receipt.json"
    with pytest.raises(ValueError, match="manifest changed"):
        publish("c" * 40, receipt_path)

    assert state["commits"] == 0
    assert not receipt_path.exists()


def test_hosted_publish_commits_only_manifest_and_verifies_exact_readback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    publisher = manifest_publisher
    contract = _contract()
    obj = contract["object"]
    base_manifest = _manifest(contract)
    base_bytes = (
        json.dumps(base_manifest, indent=2, sort_keys=True) + "\n"
    ).encode()
    contract["expected_parent_revision"] = "a" * 40
    contract["expected_parent_manifest_sha256"] = publisher.sha256_bytes(
        base_bytes
    )
    contract["expected_parent_file_count"] = len(base_manifest["files"])
    state: dict[str, Any] = {
        "revision": contract["expected_parent_revision"],
        "manifests": {contract["expected_parent_revision"]: base_bytes},
        "operations": None,
    }

    class FakeApi:
        def __init__(self, credential: Any = None) -> None:
            self.credential = credential

        def dataset_info(
            self,
            _dataset: str,
            *,
            revision: str | None = None,
            **_kwargs: Any,
        ) -> Any:
            selected = revision or state["revision"]
            return SimpleNamespace(
                private=False,
                gated=False,
                sha=selected,
                siblings=[
                    SimpleNamespace(
                        rfilename=path,
                        size=obj["bytes"],
                        blob_id=obj["expected_blob_id"],
                    )
                    for path in (obj["path"], obj["preserved_alias_path"])
                ],
            )

        def create_commit(
            self,
            *,
            repo_id: str,
            repo_type: str,
            parent_commit: str,
            commit_message: str,
            operations: list[Any],
        ) -> Any:
            assert self.credential == "test-token"
            assert repo_id == contract["dataset"]
            assert repo_type == "dataset"
            assert parent_commit == contract["expected_parent_revision"]
            assert commit_message
            state["operations"] = operations
            assert len(operations) == 1
            operation = operations[0]
            assert operation.path_in_repo == "manifest.json"
            new_bytes = operation.path_or_fileobj.getvalue()
            new_revision = "b" * 40
            state["revision"] = new_revision
            state["manifests"][new_revision] = new_bytes
            return SimpleNamespace(oid=new_revision)

    def fake_download(
        *,
        repo_id: str,
        repo_type: str,
        filename: str,
        revision: str,
        token: bool,
        cache_dir: Path,
    ) -> str:
        assert repo_id == contract["dataset"]
        assert repo_type == "dataset"
        assert filename == "manifest.json"
        assert token is False
        target = cache_dir / revision / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(state["manifests"][revision])
        return str(target)

    def fake_api_factory(**kwargs: Any) -> FakeApi:
        return FakeApi(credential=kwargs.get("token"))

    def fake_read_json(_path: Path) -> dict[str, Any]:
        return contract

    def fake_verify_static_authority(_contract: dict[str, Any]) -> None:
        return None

    def fake_require_hosted_main(_commit: str) -> None:
        return None

    def fake_commit_operation(
        *, path_in_repo: str, path_or_fileobj: Any
    ) -> Any:
        return SimpleNamespace(
            path_in_repo=path_in_repo,
            path_or_fileobj=path_or_fileobj,
        )

    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setattr(publisher, "ROOT", tmp_path)
    monkeypatch.setattr(publisher, "read_json", fake_read_json)
    monkeypatch.setattr(
        publisher,
        "verify_static_authority",
        fake_verify_static_authority,
    )
    monkeypatch.setattr(
        publisher,
        "_require_hosted_main",
        fake_require_hosted_main,
    )
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(
            CommitOperationAdd=fake_commit_operation,
            HfApi=fake_api_factory,
            hf_hub_download=fake_download,
        ),
    )

    result_path = tmp_path / "build/result.json"
    receipt = publish("c" * 40, result_path)

    assert receipt["status"] == "appended_and_verified"
    assert receipt["before_revision"] == "a" * 40
    assert receipt["after_revision"] == "b" * 40
    assert receipt["source_payload_bytes_read"] is False
    assert receipt["file_count_before"] == len(base_manifest["files"])
    assert receipt["file_count_after"] == len(base_manifest["files"]) + 1
    assert [operation.path_in_repo for operation in state["operations"]] == [
        "manifest.json"
    ]
    assert json.loads(result_path.read_text(encoding="utf-8")) == receipt

    retry_path = tmp_path / "build/retry-receipt.json"
    retry_receipt = publish("c" * 40, retry_path)
    assert retry_receipt["status"] == "already_present_and_verified"
    assert retry_receipt["before_revision"] == "b" * 40
    assert retry_receipt["after_revision"] == "b" * 40
    assert [operation.path_in_repo for operation in state["operations"]] == [
        "manifest.json"
    ]
    assert json.loads(retry_path.read_text(encoding="utf-8")) == retry_receipt
