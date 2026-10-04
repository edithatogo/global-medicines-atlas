"""The real rights publisher fails closed locally and cleans only verified caches."""

import hashlib
import importlib
import io
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from global_medicines_atlas.mbs_utilisation_validation import (
    PREFLIGHT_PATH,
    load_validation_cohort,
    validate_staged_payload,
)

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


def test_payload_validation_runner_refuses_local_before_io(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    runner = importlib.import_module("validate_mbs_utilisation_payloads")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr("sys.argv", ["runner", "--exact-commit", "a" * 40])
    with pytest.raises(ValueError, match="Actions"):
        runner.main()


def _validation_reference(path, payload):

    return {
        "path": path.name,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
    }


def test_streaming_csv_validation_returns_only_counts(tmp_path):

    payload = b'\xef\xbb\xbfa,b\n"line\none",2\n3,4\n'
    path = tmp_path / "source.csv"
    path.write_bytes(payload)
    result = validate_staged_payload(path, _validation_reference(path, payload))
    assert result == {
        "format": "csv",
        "row_count": 2,
        "column_count": 2,
        "check_profile": "utf8-bom-rectangular-csv",
    }
    assert "line" not in json.dumps(result)


@pytest.mark.parametrize(
    "payload", [b"", b"a,b\n", b"a,b\n1\n", b"\xff\n1\n", b"\n1\n"]
)
def test_streaming_csv_validation_rejects_incomplete_or_invalid_input(
    tmp_path, payload
):

    path = tmp_path / "source.csv"
    path.write_bytes(payload)
    with pytest.raises((ValueError, UnicodeError)):
        validate_staged_payload(path, _validation_reference(path, payload))


@pytest.mark.parametrize(
    "change", ["digest", "short", "long", "limit", "type", "format"]
)
def test_payload_identity_and_format_are_fail_closed(tmp_path, change):

    payload = b"a\n1\n"
    path = tmp_path / ("source.bin" if change == "format" else "source.csv")
    path.write_bytes(payload)
    reference = _validation_reference(path, payload)
    if change == "digest":
        reference["sha256"] = "0" * 64
    if change in {"short", "long", "limit", "type"}:
        reference["byte_count"] = {
            "short": 3,
            "long": 5,
            "limit": 33 * 1024 * 1024,
            "type": True,
        }[change]
    with pytest.raises(ValueError, match="payload"):
        validate_staged_payload(path, reference)


@pytest.mark.parametrize("suffix", ["zip", "xlsx"])
def test_archive_validation_receipt_contains_no_values_or_member_names(
    tmp_path, suffix
):

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        archive.writestr(
            "xl/workbook.xml",
            b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>',
        )
        archive.writestr("xl/worksheets/sheet1.xml", b"<worksheet/>")
    payload = stream.getvalue()
    path = tmp_path / f"source.{suffix}"
    path.write_bytes(payload)
    result = validate_staged_payload(path, _validation_reference(path, payload))
    assert result["member_count"] == 3
    assert len(result["member_inventory_sha256"]) == 64
    assert "worksheet" not in json.dumps(result)


def test_reviewed_validation_cohort_is_exact_and_evidence_bound(tmp_path):

    rows = load_validation_cohort(ROOT)
    assert len(rows) == 14
    assert sum(row["validation_dispatch_eligible"] for row in rows) == 12
    for binding in json.loads((ROOT / PREFLIGHT_PATH).read_text())[
        "inputs"
    ].values():
        target = tmp_path / binding["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / binding["path"]).read_bytes())
    target = tmp_path / PREFLIGHT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((ROOT / PREFLIGHT_PATH).read_bytes())
    assert load_validation_cohort(tmp_path) == rows
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError, match="preflight differs"):
        load_validation_cohort(tmp_path)
    target.write_bytes((ROOT / PREFLIGHT_PATH).read_bytes())
    binding = json.loads(target.read_text())["inputs"]["event_import"]
    (tmp_path / binding["path"]).write_bytes(b"{}")
    with pytest.raises(ValueError, match="input binding differs"):
        load_validation_cohort(tmp_path)


@pytest.fixture
def validation_runner(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    runner = importlib.import_module("validate_mbs_utilisation_payloads")
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "123",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr("sys.argv", ["runner", "--exact-commit", "a" * 40])
    monkeypatch.setattr(runner, "current_main", lambda: "a" * 40)
    return runner


def test_validation_failures_do_not_block_other_sources_or_bypass_receipts(
    validation_runner, tmp_path, monkeypatch
):
    runner = validation_runner
    cohort = runner.load_validation_cohort(ROOT)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "load_validation_cohort", lambda _: cohort)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(runner.tempfile, "mkdtemp", lambda **_: str(cache))
    downloads = []

    class Hub:
        def head(self, _dataset):
            return "b" * 40

        def download_object(self, _dataset, _revision, path, _limit):
            downloads.append(path)
            if len(downloads) == 1:
                raise ValueError("source unavailable")
            target = cache / str(len(downloads))
            target.write_bytes(b"synthetic")
            return target

    monkeypatch.setattr(runner, "HubTransport", lambda _: Hub())
    monkeypatch.setattr(
        runner,
        "run_worker",
        lambda *_: {
            "status": "structure_verified",
            "anonymous_digest_verified": True,
            "checks": {"format": "synthetic"},
        },
    )
    documents = []

    def persist(document, _directory):
        # Verified caches must still exist when their evidence is persisted.
        if document["status"] == "structure_verified":
            assert len(list(cache.iterdir())) == 1
        documents.append(document)
        return f"https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-{len(documents)}"

    monkeypatch.setattr(runner, "persist_receipt", persist)
    runner.main()
    assert len(downloads) == 12
    assert len(documents) == 15
    assert documents[0]["status"] == "download_failed"
    assert sum(doc["status"] == "resource_hold" for doc in documents) == 2
    assert list(cache.iterdir()) == []
    assert len(documents[-1]["records"]) == 14
    assert (
        sum(record["cache_removed"] for record in documents[-1]["records"])
        == 11
    )
    assert all(doc["processing_admitted"] is False for doc in documents)


def test_validation_worker_timeout_strips_credentials(
    validation_runner, tmp_path, monkeypatch
):

    runner = validation_runner
    monkeypatch.setenv("HF_TOKEN", "synthetic-hf")
    monkeypatch.setenv("GH_TOKEN", "synthetic-gh")

    def run(args, **kwargs):
        assert kwargs["timeout"] == 120
        assert "HF_TOKEN" not in kwargs["env"]
        assert "GH_TOKEN" not in kwargs["env"]
        assert "--worker" in args
        raise subprocess.TimeoutExpired(args, 120)

    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.run_worker(0, tmp_path / "source") == {
        "status": "worker_failed_or_timed_out",
        "anonymous_digest_verified": False,
    }


def test_validation_workflow_is_protected_and_has_no_hub_write_token():
    workflow = yaml.safe_load(
        (
            ROOT / ".github/workflows/australian-mbs-utilisation-validation.yml"
        ).read_text()
    )
    assert set(workflow.get("on", workflow.get(True))) == {"workflow_dispatch"}
    job = workflow["jobs"]["validate"]
    assert job["environment"] == "australian-hf-publication"
    assert (
        workflow["concurrency"]["group"] == "australian-mbs-utilisation-harvest"
    )
    step = next(step for step in job["steps"] if "run" in step)
    assert "HF_TOKEN" not in step["env"]
    assert '--exact-commit "$REQUESTED_COMMIT"' in step["run"]


@pytest.mark.parametrize(
    "case", ["good", "identity", "structure", "held", "platform"]
)
def test_parser_worker_returns_bounded_independent_outcomes(
    validation_runner, tmp_path, monkeypatch, case
):
    runner = validation_runner
    payload = b"a,b\n1,2\n" if case != "structure" else b"a,b\n1\n"
    path = tmp_path / "source.csv"
    path.write_bytes(payload)
    reference = _validation_reference(path, payload)
    if case == "identity":
        reference["sha256"] = "0" * 64
    monkeypatch.setattr(
        runner,
        "load_validation_cohort",
        lambda _: [
            {
                "raw_reference": reference,
                "validation_dispatch_eligible": case != "held",
            }
        ],
    )
    monkeypatch.setattr(
        runner.sys, "platform", "darwin" if case == "platform" else "linux"
    )
    bounds = []
    original_import = importlib.import_module
    monkeypatch.setattr(
        runner.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(
                RLIMIT_AS=1,
                setrlimit=lambda kind, limit: bounds.append((kind, limit)),
            )
            if name == "resource"
            else original_import(name)
        ),
    )
    if case in {"held", "platform"}:
        with pytest.raises(ValueError, match=r"resource-held|Linux"):
            runner.worker(0, path)
        return
    outcome = runner.worker(0, path)
    assert bounds == [(1, (2 * 1024**3, 2 * 1024**3))]
    assert (
        outcome["status"]
        == {
            "good": "structure_verified",
            "identity": "identity_failed",
            "structure": "structure_failed",
        }[case]
    )
    assert outcome["anonymous_digest_verified"] == (case != "identity")
    assert "a,b" not in json.dumps(outcome)


@pytest.mark.parametrize(
    "result",
    [
        [],
        {"status": "invalid"},
        {"status": "identity_failed", "anonymous_digest_verified": True},
    ],
)
def test_parent_rejects_invalid_worker_claims(
    validation_runner, tmp_path, monkeypatch, result
):
    runner = validation_runner
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=json.dumps(result)),
    )
    with pytest.raises((ValueError, TypeError), match="validation worker"):
        runner.run_worker(0, tmp_path / "source")


def test_parent_accepts_valid_worker_count_receipt(
    validation_runner, tmp_path, monkeypatch
):
    runner = validation_runner
    result = {
        "status": "structure_verified",
        "anonymous_digest_verified": True,
        "checks": {"format": "csv", "row_count": 1, "column_count": 1},
    }
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=json.dumps(result)),
    )
    assert runner.run_worker(0, tmp_path / "source") == result


def test_hosted_runner_refuses_stale_main_before_transport(
    validation_runner, monkeypatch
):
    runner = validation_runner
    monkeypatch.setattr(runner, "current_main", lambda: "b" * 40)
    monkeypatch.setattr(
        runner,
        "HubTransport",
        lambda _: pytest.fail("transport before exact-main check"),
    )
    with pytest.raises(ValueError, match="main has advanced"):
        runner.main()


@pytest.mark.parametrize("failure", ["persist", "url", "identity"])
def test_unverified_or_unrecorded_bytes_are_preserved(
    validation_runner, tmp_path, monkeypatch, failure
):
    runner = validation_runner
    row = load_validation_cohort(ROOT)[0]
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "load_validation_cohort", lambda _: [row])
    cache = tmp_path / "cache"
    cache.mkdir()
    target = cache / "source"
    target.write_bytes(b"synthetic")
    monkeypatch.setattr(runner.tempfile, "mkdtemp", lambda **_: str(cache))
    monkeypatch.setattr(
        runner,
        "HubTransport",
        lambda _: SimpleNamespace(
            head=lambda _: "b" * 40, download_object=lambda *_: target
        ),
    )
    monkeypatch.setattr(
        runner,
        "run_worker",
        lambda *_: {
            "status": "identity_failed"
            if failure == "identity"
            else "structure_verified",
            "anonymous_digest_verified": failure != "identity",
        },
    )

    def persist(*_):
        if failure == "persist":
            raise ValueError("durable receipt failed")
        return (
            "invalid"
            if failure == "url"
            else "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-1"
        )

    monkeypatch.setattr(runner, "persist_receipt", persist)
    if failure in {"persist", "url"}:
        with pytest.raises(ValueError, match="durable"):
            runner.main()
    else:
        runner.main()
    assert target.read_bytes() == b"synthetic"


def test_csv_row_and_column_bounds_are_enforced(tmp_path, monkeypatch):
    module = importlib.import_module(
        "global_medicines_atlas.mbs_utilisation_validation"
    )
    path = tmp_path / "source.csv"
    payload = b"a,b\n1,2\n3,4\n"
    path.write_bytes(payload)
    monkeypatch.setattr(module, "MAX_CSV_ROWS", 1)
    with pytest.raises(ValueError, match="row bound"):
        module.validate_staged_payload(
            path, _validation_reference(path, payload)
        )
    monkeypatch.setattr(module, "MAX_CSV_COLUMNS", 1)
    with pytest.raises(ValueError, match="header"):
        module.validate_staged_payload(
            path, _validation_reference(path, payload)
        )


def test_empty_zip_is_not_a_valid_utilisation_container(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w"):
        pass
    payload = stream.getvalue()
    path = tmp_path / "source.zip"
    path.write_bytes(payload)
    with pytest.raises(ValueError, match="no regular members"):
        validate_staged_payload(path, _validation_reference(path, payload))


def test_public_download_adapter_uses_existing_bounded_worker(
    tmp_path, monkeypatch
):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    transport = importlib.import_module("publish_source_metadata")
    hub = object.__new__(transport.HubTransport)
    target = tmp_path / "object"
    calls = []
    monkeypatch.setattr(
        hub, "_download", lambda *args: calls.append(args) or target
    )
    assert hub.download_object("dataset", "revision", "raw/path", 123) == target
    assert calls == [("dataset", "revision", "raw/path", 123)]


@pytest.mark.parametrize(
    "stage",
    [
        "identity_io",
        "identity_memory",
        "parse_io",
        "parse_memory",
        "wrapped_io",
    ],
)
def test_worker_infrastructure_failure_is_inconclusive(
    validation_runner, tmp_path, monkeypatch, stage
):
    runner = validation_runner
    path = tmp_path / "source.csv"
    payload = b"a\n1\n"
    path.write_bytes(payload)
    row = {
        "raw_reference": _validation_reference(path, payload),
        "validation_dispatch_eligible": True,
    }
    monkeypatch.setattr(runner, "load_validation_cohort", lambda _: [row])
    monkeypatch.setattr(runner.sys, "platform", "linux")
    original_import = importlib.import_module
    monkeypatch.setattr(
        runner.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(RLIMIT_AS=1, setrlimit=lambda *_: None)
            if name == "resource"
            else original_import(name)
        ),
    )

    def unavailable(*_):
        if stage == "wrapped_io":
            raise ValueError("archive wrapper") from OSError("read unavailable")
        if stage.endswith("memory"):
            raise MemoryError
        raise OSError("read unavailable")

    monkeypatch.setattr(
        runner,
        "verify_staged_identity"
        if stage.startswith("identity")
        else "validate_staged_payload",
        unavailable,
    )
    outcome = runner.worker(0, path)
    assert outcome["status"] == (
        "identity_unavailable"
        if stage.startswith("identity")
        else "validation_unavailable"
    )
    assert outcome["anonymous_digest_verified"] == (
        not stage.startswith("identity")
    )


@pytest.mark.parametrize(
    "status", ["identity_unavailable", "validation_unavailable"]
)
def test_parent_accepts_inconclusive_worker_results(
    validation_runner, tmp_path, monkeypatch, status
):
    runner = validation_runner
    result = {
        "status": status,
        "anonymous_digest_verified": status == "validation_unavailable",
    }
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=json.dumps(result)),
    )
    assert runner.run_worker(0, tmp_path / "source") == result


def test_workbook_diagnostic_selection_uses_only_recorded_failures(
    validation_runner,
):
    runner = validation_runner
    selected = runner.failed_workbook_paths(ROOT, load_validation_cohort(ROOT))
    assert selected == {
        "raw/mbs/utilisation/demographics/mbs-demographics-2016-qtr1-marchhr.xlsx",
        "raw/mbs/utilisation/demographics/mbs-demographics-2016-qtr2-junehr.xlsx",
    }


def test_diagnostic_selection_rejects_tampered_receipt_and_source(
    validation_runner, tmp_path
):
    runner = validation_runner
    target = tmp_path / runner.DIAGNOSTIC_RECEIPT_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes(b"{}")
    with pytest.raises(ValueError, match="receipt differs"):
        runner.failed_workbook_paths(tmp_path, load_validation_cohort(ROOT))
    cohort = json.loads(json.dumps(load_validation_cohort(ROOT)))
    cohort[3]["validation_dispatch_eligible"] = False
    with pytest.raises(ValueError, match="source identity differs"):
        runner.failed_workbook_paths(ROOT, cohort)


@pytest.mark.parametrize(
    ("message", "code"),
    [
        (
            "archive total uncompressed bytes limit exceeded",
            "archive_expanded_byte_limit",
        ),
        (
            "private source value must never be logged",
            "structural_profile_failure_unclassified",
        ),
    ],
)
def test_diagnostic_failure_codes_do_not_expose_exception_text(
    validation_runner, tmp_path, monkeypatch, message, code
):
    runner = validation_runner
    path = tmp_path / "source.csv"
    payload = b"a\n1\n"
    path.write_bytes(payload)
    monkeypatch.setattr(
        runner,
        "load_validation_cohort",
        lambda _: [
            {
                "raw_reference": _validation_reference(path, payload),
                "validation_dispatch_eligible": True,
            }
        ],
    )
    monkeypatch.setattr(runner.sys, "platform", "linux")
    original_import = importlib.import_module
    monkeypatch.setattr(
        runner.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(RLIMIT_AS=1, setrlimit=lambda *_: None)
            if name == "resource"
            else original_import(name)
        ),
    )

    def fail(*_):
        raise ValueError(message)

    monkeypatch.setattr(runner, "validate_staged_payload", fail)
    result = runner.worker(0, path)
    assert result["failure_code"] == code
    assert message not in json.dumps(result)


def test_diagnostic_mode_downloads_only_two_recorded_workbooks(
    validation_runner, tmp_path, monkeypatch
):
    runner = validation_runner
    cohort = load_validation_cohort(ROOT)
    selected = runner.failed_workbook_paths(ROOT, cohort)
    monkeypatch.setattr(
        "sys.argv",
        ["runner", "--exact-commit", "a" * 40, "--failed-workbooks-only"],
    )
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "load_validation_cohort", lambda _: cohort)
    monkeypatch.setattr(runner, "failed_workbook_paths", lambda *_: selected)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(runner.tempfile, "mkdtemp", lambda **_: str(cache))
    downloads = []

    def download(_dataset, _revision, path, _limit):
        downloads.append(path)
        target = cache / str(len(downloads))
        target.write_bytes(b"synthetic")
        return target

    monkeypatch.setattr(
        runner,
        "HubTransport",
        lambda _: SimpleNamespace(
            head=lambda _: "b" * 40, download_object=download
        ),
    )
    monkeypatch.setattr(
        runner,
        "run_worker",
        lambda *_: {
            "status": "structure_failed",
            "anonymous_digest_verified": True,
            "failure_code": "archive_expanded_byte_limit",
        },
    )
    documents = []

    def persist(document, _directory):
        documents.append(document)
        return f"https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-{len(documents)}"

    monkeypatch.setattr(runner, "persist_receipt", persist)
    runner.main()
    assert set(downloads) == selected
    assert len(documents) == 3
    assert all(
        document["validation_mode"] == "failed_workbooks_only"
        for document in documents
    )
    assert len(documents[-1]["records"]) == 2
    assert all(record["cache_removed"] for record in documents[-1]["records"])


def test_workbook_diagnostic_workflow_is_exact_protected_and_read_only():
    workflow = yaml.safe_load(
        (
            ROOT / ".github/workflows/australian-mbs-workbook-diagnostics.yml"
        ).read_text()
    )
    job = workflow["jobs"]["validate"]
    assert job["environment"] == "australian-hf-publication"
    assert (
        workflow["concurrency"]["group"] == "australian-mbs-utilisation-harvest"
    )
    step = next(step for step in job["steps"] if "run" in step)
    assert "--failed-workbooks-only" in step["run"]
    assert "HF_TOKEN" not in step["env"]
