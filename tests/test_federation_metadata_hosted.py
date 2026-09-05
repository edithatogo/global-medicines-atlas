"""Hosted metadata publication preserves CAS and durable evidence ordering."""

# Transport signatures mirror the protocol even when a mock ignores arguments.
# ruff: file-ignore[unused-method-argument]

import json
import runpy
import subprocess  # ruff: ignore[suspicious-subprocess-import] - mock only
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from global_medicines_atlas.federation_metadata_append import (
    ObjectDigest,
    prepare_metadata_append,
)
from global_medicines_atlas.federation_metadata_hosted import (
    PublicSnapshot,
    execute_metadata_append,
)


class FakeHub:
    def __init__(self, document):
        self.document = document
        provenance = document["provenance"]
        self.objects = (
            *(
                ObjectDigest(item["path"], 1, item["sha256"])
                for item in provenance["payloads"]
            ),
            ObjectDigest(
                provenance["receipt"], 1, provenance["receipt_sha256"]
            ),
        )
        self.plan = None
        self.calls = []
        self.drift = False
        self.tamper = False

    def snapshot(self, dataset, revision):
        self.calls.append("snapshot")
        objects = self.objects
        if self.plan:
            objects += (self.plan.addition,)
        if self.tamper and self.plan:
            objects = objects[1:]
        return PublicSnapshot(
            revision=revision, private=False, gated=False, objects=objects
        )

    def head(self, dataset):
        self.calls.append("head")
        return "a" * 40 if self.drift else self.document["revision"]

    def append(self, plan):
        self.calls.append("append")
        self.plan = plan
        return "f" * 40

    def metadata(self, dataset, revision, path):
        return self.plan.payload


@pytest.fixture
def setup(monkeypatch):
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "123",
    }.items():
        monkeypatch.setenv(key, value)
    document = json.loads(
        (
            Path(__file__).parent
            / "fixtures"
            / "federation_source_metadata/valid-pbs.json"
        ).read_text()
    )
    return document, FakeHub(document)


def test_intent_before_append_and_verification_after(setup):
    document, hub = setup
    records = []

    def persist(receipt):
        hub.calls.append(receipt["status"])
        records.append(receipt)
        return "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-1"

    result = execute_metadata_append(
        document, exact_commit="a" * 40, hub=hub, persist=persist
    )
    assert hub.calls == [
        "snapshot",
        "head",
        "intent",
        "head",
        "append",
        "snapshot",
        "anonymously_verified",
    ]
    assert result["revision"] == "f" * 40
    assert records[0]["addition"] == records[1]["addition"]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("GITHUB_ACTIONS", "false"),
        ("GITHUB_REF", "refs/pull/1/merge"),
        ("GITHUB_SHA", "b" * 40),
    ],
)
def test_local_or_unbound_execution_cannot_touch_transport(
    setup, monkeypatch, key, value
):
    document, hub = setup
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="requires"):
        execute_metadata_append(
            document, exact_commit="a" * 40, hub=hub, persist=lambda _: ""
        )
    assert hub.calls == []


def test_failed_intent_prevents_write(setup):
    document, hub = setup
    with pytest.raises(ValueError, match="intent URL"):
        execute_metadata_append(
            document, exact_commit="a" * 40, hub=hub, persist=lambda _: ""
        )
    assert "append" not in hub.calls


def test_head_drift_after_intent_prevents_write(setup):
    document, hub = setup

    def persist(_):
        hub.drift = True
        return "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-1"

    with pytest.raises(ValueError, match="drifted"):
        execute_metadata_append(
            document, exact_commit="a" * 40, hub=hub, persist=persist
        )
    assert "append" not in hub.calls


def test_changed_sibling_cannot_emit_success(setup):
    document, hub = setup
    hub.tamper = True
    records = []

    def persist(receipt):
        records.append(receipt)
        return "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-1"

    with pytest.raises(ValueError, match="sibling inventory"):
        execute_metadata_append(
            document, exact_commit="a" * 40, hub=hub, persist=persist
        )
    assert [item["status"] for item in records] == ["intent"]


def test_receipt_size_rejected_before_external_write(setup):
    document, hub = setup
    hub.objects += tuple(
        ObjectDigest(f"extra/{i}", 0, "a" * 64) for i in range(1000)
    )
    with pytest.raises(ValueError, match="receipt exceeds"):
        execute_metadata_append(
            document, exact_commit="a" * 40, hub=hub, persist=lambda _: ""
        )
    assert "append" not in hub.calls


def transport_class():
    return runpy.run_path(
        str(Path(__file__).parents[1] / "scripts/publish_source_metadata.py")
    )["HubTransport"]


def test_actual_sdk_commit_has_one_add_and_server_cas(
    setup, monkeypatch, tmp_path
):
    document, hub = setup
    calls = []

    class API:
        def __init__(self, *, token):
            calls.append(token)

        def create_commit(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(oid="f" * 40)

    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(HfApi=API, CommitOperationAdd=lambda **kwargs: kwargs),
    )
    monkeypatch.setenv("HF_TOKEN", "synthetic-test-token")
    transport = transport_class()(tmp_path)
    plan = prepare_metadata_append(document, hub.objects)
    assert transport.append(plan) == "f" * 40
    assert calls[0] is False
    assert calls[1] == "synthetic-test-token"
    assert calls[2]["parent_commit"] == plan.parent_revision
    assert calls[2]["operations"] == [
        {"path_in_repo": plan.addition.path, "path_or_fileobj": plan.payload}
    ]
    assert "delete_patterns" not in calls[2]


def test_download_overrun_is_not_written(tmp_path):
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"1234"
            yield b"5678"

    target = tmp_path / "bounded"
    response = httpx.Response(200, stream=Stream())
    with pytest.raises(ValueError, match="byte/time bound"):
        transport_class()._save_response(
            response, target, 4, time.monotonic() + 30
        )
    assert target.read_bytes() == b"1234"


def test_download_expired_deadline_writes_no_source_bytes(tmp_path):
    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"1234"

    target = tmp_path / "expired"
    with pytest.raises(ValueError, match="byte/time bound"):
        transport_class()._save_response(
            httpx.Response(200, stream=Stream()),
            target,
            4,
            time.monotonic() - 1,
        )
    assert target.read_bytes() == b""


def test_absolute_deadline_kills_worker_even_if_next_read_stalls(
    monkeypatch, tmp_path
):
    transport = object.__new__(transport_class())
    transport.cache = tmp_path
    seen = []

    def stalled(command, **kwargs):
        seen.append(kwargs)
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", stalled)
    monkeypatch.setenv("HF_TOKEN", "synthetic-secret")
    with pytest.raises(ValueError, match="exceeded deadline"):
        transport._download("owner/dataset", "a" * 40, "raw/file", 5)
    assert seen[0]["timeout"] == 60
    assert "HF_TOKEN" not in seen[0]["env"]
