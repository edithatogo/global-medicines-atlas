"""The real rights publisher fails closed locally and cleans only verified caches."""

import importlib
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def publisher(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("publish_mbs_utilisation_rights")


def test_local_cli_refuses_before_transport(publisher, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr("sys.argv", ["publisher", "--exact-commit", "a" * 40])
    with pytest.raises(ValueError, match="Actions"):
        publisher.main()


def test_workflow_dispatch_is_exact_and_protected():
    workflow = yaml.safe_load(
        (
            ROOT / ".github/workflows/australian-mbs-utilisation-rights.yml"
        ).read_text()
    )
    events = workflow.get("on", workflow.get(True))
    assert set(events) == {"workflow_dispatch"}
    assert events["workflow_dispatch"]["inputs"]["exact_contract_commit"][
        "required"
    ]
    job = workflow["jobs"]["append"]
    assert job["environment"] == "australian-hf-publication"
    assert (
        workflow["concurrency"]["group"] == "australian-mbs-utilisation-harvest"
    )
    assert workflow["concurrency"]["cancel-in-progress"] is False
    command = next(step for step in job["steps"] if "run" in step)["run"]
    assert '"$REQUESTED_COMMIT"' in command
    assert "publish_mbs_utilisation_rights.py" in command
    assert "--exact-commit" in command
    assert "--with huggingface-hub==1.14.0" in command


@pytest.fixture
def hosted(publisher, monkeypatch, tmp_path):
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "123",
    }.items():
        monkeypatch.setenv(key, value)
    for relative in (
        publisher.CONTRACT_PATH,
        publisher.PAYLOAD_PATH,
        publisher.DECISION_PATH,
        publisher.JOIN_PATH,
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    monkeypatch.setattr(publisher, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["publisher", "--exact-commit", "a" * 40])
    monkeypatch.setattr(publisher, "current_main", lambda: "a" * 40)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(
        publisher.tempfile, "mkdtemp", lambda **_kwargs: str(cache)
    )
    calls = []
    monkeypatch.setattr(
        publisher, "HubTransport", lambda _directory: calls.append("transport")
    )
    return cache, calls


def test_verified_success_cleans_and_records(publisher, hosted, monkeypatch):
    cache, calls = hosted
    url = "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-1"

    def execute(*_args, **kwargs):
        calls.append("execute")
        assert kwargs["current_main"]() == "a" * 40
        assert kwargs["exact_commit"] == "a" * 40
        return {"status": "anonymously_verified", "receipt_url": url}

    records = []
    monkeypatch.setattr(publisher, "execute_rights_append", execute)
    monkeypatch.setattr(
        publisher,
        "persist_receipt",
        lambda document, _directory: records.append(document) or url,
    )
    publisher.main()
    assert calls == ["transport", "execute"]
    assert not cache.exists()
    assert records[0]["status"] == "cleanup_completed"
    assert records[0]["temporary_cache_removed"] is True
    result = json.loads(
        (
            publisher.ROOT / "build/mbs-utilisation-rights-receipts/result.json"
        ).read_bytes()
    )
    assert result["cleanup_receipt_url"] == url


def test_failed_append_retains_hosted_cache(publisher, hosted, monkeypatch):
    cache, calls = hosted

    def fail(*_args, **_kwargs):
        raise RuntimeError("anonymous verification failed")

    monkeypatch.setattr(publisher, "execute_rights_append", fail)
    with pytest.raises(RuntimeError, match="verification failed"):
        publisher.main()
    assert cache.exists()
    assert calls == ["transport"]


@pytest.mark.parametrize(
    "result",
    [
        {"status": "cas_acknowledged", "receipt_url": "url"},
        {"status": "anonymously_verified"},
    ],
)
def test_cleanup_refuses_unverified_result(publisher, tmp_path, result):
    cache = tmp_path / "cache"
    cache.mkdir()
    with pytest.raises(ValueError, match="durable anonymous verification"):
        publisher.finalize(result, cache, tmp_path)
    assert cache.exists()


def test_advanced_main_refuses_before_transport(publisher, hosted, monkeypatch):
    _cache, calls = hosted
    monkeypatch.setattr(publisher, "current_main", lambda: "b" * 40)
    with pytest.raises(ValueError, match="main has advanced"):
        publisher.main()
    assert calls == []


def test_current_main_is_bounded_fixed_argv(publisher, monkeypatch):
    def check(argv, **kwargs):
        assert argv == [
            "gh",
            "api",
            "repos/edithatogo/global-medicines-atlas/commits/main",
            "--jq",
            ".sha",
        ]
        assert kwargs["timeout"] == 30
        return "a" * 40 + "\n"

    monkeypatch.setattr(publisher.subprocess, "check_output", check)
    assert publisher.current_main() == "a" * 40


def test_lifecycle_runner_refuses_local_execution(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    lifecycle = importlib.import_module("publish_mbs_utilisation_lifecycle")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr("sys.argv", ["publisher", "--exact-commit", "a" * 40])
    with pytest.raises(ValueError, match="Actions"):
        lifecycle.main()


def test_lifecycle_workflow_is_protected_and_shares_writer_lock():
    workflow = yaml.safe_load(
        (
            ROOT / ".github/workflows/australian-mbs-utilisation-lifecycle.yml"
        ).read_text()
    )
    assert set(workflow.get("on", workflow.get(True))) == {"workflow_dispatch"}
    assert (
        workflow["jobs"]["append"]["environment"] == "australian-hf-publication"
    )
    assert (
        workflow["concurrency"]["group"] == "australian-mbs-utilisation-harvest"
    )
    assert workflow["concurrency"]["cancel-in-progress"] is False
    command = next(
        s["run"] for s in workflow["jobs"]["append"]["steps"] if "run" in s
    )
    assert "publish_mbs_utilisation_lifecycle.py" in command
    assert '"$REQUESTED_COMMIT"' in command


@pytest.mark.parametrize(
    "outcome", ["verified", "failed", "drift", "unreviewed"]
)
def test_lifecycle_runner_order_and_cache_retention(
    publisher, hosted, monkeypatch, outcome
):
    cache, calls = hosted
    lifecycle = importlib.import_module("publish_mbs_utilisation_lifecycle")
    for relative in (
        lifecycle.CONTRACT_PATH,
        lifecycle.PAYLOAD_PATH,
        lifecycle.BASELINE_PATH,
    ):
        destination = publisher.ROOT / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    monkeypatch.setattr(lifecycle, "ROOT", publisher.ROOT)
    monkeypatch.setattr(
        lifecycle,
        "current_main",
        lambda: "b" * 40 if outcome == "drift" else "a" * 40,
    )
    monkeypatch.setattr(
        lifecycle, "HubTransport", lambda _directory: calls.append("transport")
    )
    url = "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-1"
    records = []
    monkeypatch.setattr(
        publisher,
        "persist_receipt",
        lambda document, _directory: records.append(document) or url,
    )

    def execute(*_args, **_kwargs):
        calls.append("execute")
        if outcome == "failed":
            raise RuntimeError("readback failed")
        return {"status": "anonymously_verified", "receipt_url": url}

    monkeypatch.setattr(lifecycle, "execute_lifecycle_append", execute)
    if outcome == "unreviewed":
        path = lifecycle.ROOT / lifecycle.PAYLOAD_PATH
        path.write_bytes(path.read_bytes() + b" ")
    if outcome == "verified":
        lifecycle.main()
        assert calls == ["transport", "execute"]
        assert not cache.exists()
        assert records[0]["status"] == "cleanup_completed"
        assert (
            lifecycle.ROOT
            / "build/mbs-utilisation-lifecycle-receipts/result.json"
        ).exists()
    else:
        with pytest.raises(
            (ValueError, RuntimeError), match=r"advanced|reviewed|readback"
        ):
            lifecycle.main()
        assert cache.exists()
        assert records == []
        assert calls == (
            ["transport", "execute"] if outcome == "failed" else []
        )
