"""Public-only digest boundary and deterministic native MBS preservation."""

import base64
import hashlib
import io
import json
import lzma
import zipfile
from types import SimpleNamespace
from typing import Any, cast

import pytest
from scripts import publish_mbs_public_exports as subject


def fixture_pack():
    payload = b"<html><title>synthetic public report</title>\xff</html>"
    digest = hashlib.sha256(payload).hexdigest()
    document = {
        "objects": {digest: payload.decode("latin1")},
        "members": [
            {
                "cohort": "public-report",
                "name": "report.html",
                "sha256": digest,
                "bytes": len(payload),
            }
        ],
    }
    raw = subject.canonical(document)
    archive = subject.make_pack(document)
    expected = {
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "sha256": hashlib.sha256(archive).hexdigest(),
        "bytes": len(archive),
        "members": 1,
    }
    encoded = base64.b64encode(lzma.compress(raw)).decode()
    return document, expected, encoded, archive


def test_original_bytes_and_deterministic_index():
    document, expected, encoded, archive = fixture_pack()
    assert subject.decode_pack(encoded, expected) == archive
    assert subject.make_pack(document) == archive
    with zipfile.ZipFile(io.BytesIO(archive)) as handle:
        digest = next(iter(document["objects"]))
        assert handle.read(f"objects/{digest}.html").endswith(b"\xff</html>")
        assert (
            json.loads(handle.read("members.json"))["members"]
            == document["members"]
        )


@pytest.mark.parametrize(
    "mutation", ["alias", "duplicate", "digest", "length", "orphan"]
)
def test_unsafe_native_pack_rejected(mutation):
    document, _, _, _ = fixture_pack()
    member = document["members"][0]
    if mutation == "alias":
        member["name"] = "../participant.csv"
    elif mutation == "duplicate":
        document["members"].append(dict(member))
    elif mutation == "digest":
        document["objects"][member["sha256"]] += "changed"
    elif mutation == "length":
        member["bytes"] += 1
    else:
        document["members"] = []
    with pytest.raises(ValueError, match="MBS"):
        subject.make_pack(document)


@pytest.mark.parametrize(
    "field", ["input_sha256", "sha256", "bytes", "members"]
)
def test_exact_frozen_public_cohort_required(field):
    _, expected, encoded, _ = fixture_pack()
    expected[field] = 0 if isinstance(expected[field], int) else "0" * 64
    with pytest.raises(ValueError, match="MBS"):
        subject.decode_pack(encoded, expected)


def test_bounded_expansion_and_trailing_stream(monkeypatch):
    _, expected, encoded, _ = fixture_pack()
    monkeypatch.setattr(subject, "MAX_EXPANDED", 10)
    with pytest.raises(ValueError, match="MBS expansion"):
        subject.decode_pack(encoded, expected)
    monkeypatch.setattr(subject, "MAX_EXPANDED", 10000)
    trailing = base64.b64encode(base64.b64decode(encoded) + b"extra").decode()
    with pytest.raises(ValueError, match="MBS expansion"):
        subject.decode_pack(trailing, expected)


def test_local_mutation_rejected_before_credentials(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(PermissionError, match="Actions main"):
        subject.main()
    with pytest.raises(PermissionError, match="Actions main"):
        subject.commit_pack(None, cast("Any", None), "", {})


def test_segment_digest_and_size_checked_before_retention(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    payload = b"synthetic approved compressed public segment"
    contract = {
        "segments": {
            "stage-0000": {
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        }
    }
    monkeypatch.setenv("MBS_PUBLIC_BUNDLE", base64.b64encode(payload).decode())
    subject.stage_segment("stage-0000", contract)
    assert (
        tmp_path / "build/mbs-public-segment/segment.bin"
    ).read_bytes() == payload
    monkeypatch.setenv(
        "MBS_PUBLIC_BUNDLE", base64.b64encode(payload + b"x").decode()
    )
    with pytest.raises(ValueError, match="reviewed public transport"):
        subject.stage_segment("stage-0000", contract)


def test_final_audit_requires_all_approved_objects():
    contract = {
        "batches": {"public-reports": {"path": "raw/report.zip", "sha256": "a"}}
    }
    with pytest.raises(RuntimeError, match="missing before final audit"):
        subject.audit_manifest({"files": []}, contract)
    subject.audit_manifest(
        {"files": [{"path": "raw/report.zip", "sha256": "a"}]}, contract
    )


def test_original_parent_objects_cannot_disappear(monkeypatch):
    baseline = {"path": "raw/old", "sha256": "original"}

    sdk = SimpleNamespace(HfApi=lambda **_kwargs: None)
    monkeypatch.setattr(
        subject,
        "fetch_existing_harvest_manifest",
        lambda *_args: ("parent", {"dataset": subject.DATASET, "files": []}),
    )
    with pytest.raises(RuntimeError, match="original archive"):
        subject.snapshot(sdk, {"baseline_files": [baseline]})


def test_existing_pack_reuses_original_receipt_without_mutation(monkeypatch):
    raw = "raw/report.zip"
    original = {
        "path": raw.replace("raw/", "bronze/") + ".receipt.json",
        "sha256": "original-b1",
    }
    existing = {"files": [{"path": raw, "sha256": "approved"}, original]}
    stage = SimpleNamespace(
        resource=SimpleNamespace(archive_path=raw),
        receipt=SimpleNamespace(sha256="approved"),
    )
    monkeypatch.setattr(
        subject,
        "commit_pack",
        lambda *_args: pytest.fail("unexpected mutation"),
    )
    revision, full, verification, present = subject.append_pack(
        None, cast("Any", stage), "exact-parent", existing
    )
    assert (revision, full, present) == ("exact-parent", existing, True)
    assert original in verification["files"]
    stage.receipt.sha256 = "changed"
    with pytest.raises(RuntimeError, match="immutable path collision"):
        subject.append_pack(None, cast("Any", stage), "exact-parent", existing)


def test_segments_require_complete_reviewed_run_inventory(monkeypatch):
    monkeypatch.setenv("MBS_PUBLIC_RUNS", "{}")
    with pytest.raises(ValueError, match="run inventory mismatch"):
        subject.collect_segments({"segments": {"stage-0000": {}}})


def test_staged_artifact_read_checks_head_and_does_not_forward_bearer(
    monkeypatch,
):
    payload = b"synthetic public segment"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("segment.bin", payload)
    contract = {
        "segments": {
            "stage-0000": {
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        }
    }
    calls = []

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, url, **kwargs):
            url = str(url)
            calls.append((url, kwargs))
            status = 200
            headers = {}
            if url.endswith("/runs/42"):
                body = json.dumps({
                    "head_sha": "reviewed-head",
                    "conclusion": "success",
                    "event": "workflow_dispatch",
                    "path": ".github/workflows/australian-mbs-utilisation-harvest.yml",
                }).encode()
            elif url.endswith("/runs/42/artifacts"):
                body = json.dumps({
                    "artifacts": [
                        {
                            "name": "mbs-public-stage-0000",
                            "id": 7,
                            "expired": False,
                        }
                    ]
                }).encode()
            elif url.endswith("/artifacts/7/zip"):
                status = 302
                headers = {
                    "location": "https://synthetic.blob.core.windows.net/signed"
                }
                body = b""
            else:
                body = output.getvalue()
            return SimpleNamespace(
                status_code=status,
                headers=headers,
                content=body,
                raise_for_status=lambda: None,
            )

    monkeypatch.setattr(subject.httpx, "Client", Client)
    monkeypatch.setenv("MBS_PUBLIC_RUNS", '{"stage-0000":42}')
    monkeypatch.setenv("GITHUB_SHA", "reviewed-head")
    monkeypatch.setenv("GH_TOKEN", "synthetic-test-token")
    assert base64.b64decode(subject.collect_segments(contract)) == payload
    assert calls[-1][1] == {}
    assert (
        calls[0][1]["headers"]["Authorization"] == "Bearer synthetic-test-token"
    )
    monkeypatch.setenv("GITHUB_SHA", "changed-head")
    with pytest.raises(ValueError, match="successful exact-head"):
        subject.collect_segments(contract)


def test_anonymous_verification_failure_never_writes_passed_receipt(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"dataset": subject.DATASET, "batches": {}}))
    monkeypatch.setattr(subject, "CONTRACT", contract)
    monkeypatch.setattr(subject, "require_hosted", lambda: None)
    monkeypatch.setattr(subject.importlib, "import_module", lambda _name: None)
    monkeypatch.setattr(
        subject,
        "snapshot",
        lambda *_args: ("exact-revision", {"files": [], "file_count": 0}),
    )

    def failed_restore(*_args, **_kwargs):
        raise ValueError("anonymous digest mismatch")

    monkeypatch.setattr(subject, "verify_anonymous_restore", failed_restore)
    monkeypatch.setenv("MBS_PUBLIC_BATCH", "verify-all")
    monkeypatch.delenv("MBS_PUBLIC_BUNDLE", raising=False)
    with pytest.raises(ValueError, match="anonymous digest mismatch"):
        subject.main()
    assert not (
        tmp_path / "build/mbs-utilisation-harvest-receipt.json"
    ).exists()
