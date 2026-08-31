"""Metadata diagnostics must never enter raw acquisition or qualification."""

import json
import socket
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from scripts import qualify_historical_pbs_public as cli
from test_pbs_hosted_qualification import SHA

from global_medicines_atlas import pbs_hosted_qualification as hosted

pytest_plugins = ["test_pbs_hosted_qualification"]


def test_probe_stops_after_exact_public_metadata(synthetic, monkeypatch):
    _, calls, transport = synthetic

    def forbidden(*_args, **_kwargs):
        raise AssertionError("raw or projection route reached")

    for name in (
        "_file",
        "read_pbs_v3_member",
        "qualify_pbs_historical_projections",
    ):
        monkeypatch.setattr(hosted, name, forbidden)
    checkpoints = []
    report = hosted.run_hosted_metadata_probe(
        SHA, transport=transport, progress=checkpoints.append
    )
    assert calls == [hosted.INFO_URL]
    assert report["status"] == "metadata_verified"
    assert report["operation"] == "pbs-public-metadata-diagnostic"
    assert report["corpus_qualified"] is False
    assert report["source_files_read"] is False
    assert "qualification" not in report
    assert all(item["corpus_qualified"] is False for item in checkpoints)


def test_metadata_failure_only_receipt_is_scoped(tmp_path):
    output = tmp_path / "receipt.json"
    assert (
        cli.main([
            "--exact-commit",
            SHA,
            "--output",
            str(output),
            "--metadata-only",
            "--failure-only",
        ])
        == 0
    )
    report = json.loads(output.read_text())["report"]
    assert report["status"] == "failed"
    assert report["operation"] == "pbs-public-metadata-diagnostic"
    assert report["corpus_qualified"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("private", True),
        ("gated", "auto"),
        ("sha", "main"),
        ("id", "other/repository"),
    ],
)
def test_probe_retains_exact_public_guards(synthetic, field, value):
    responses, calls, transport = synthetic
    info = json.loads(responses[hosted.INFO_URL])
    info[field] = value
    responses[hosted.INFO_URL] = json.dumps(info).encode()
    with pytest.raises(
        hosted.QualificationError, match="public-before/validation"
    ):
        hosted.run_hosted_metadata_probe(SHA, transport=transport)
    assert calls == [hosted.INFO_URL]


@pytest.mark.parametrize(
    "key", ["GITHUB_ACTIONS", "GITHUB_SHA", "GITHUB_REF", "GITHUB_REPOSITORY"]
)
def test_probe_rejects_context_before_transport(synthetic, monkeypatch, key):
    _, calls, transport = synthetic
    monkeypatch.setenv(key, "invalid")
    with pytest.raises(hosted.QualificationError, match="context/validation"):
        hosted.run_hosted_metadata_probe(SHA, transport=transport)
    assert not calls


@pytest.mark.parametrize(
    "target",
    [
        "https://us.aws.cdn.hf.co/raw-source.zip",
        "https://huggingface.co/datasets/other/data/resolve/main/payload",
        "https://127.0.0.1/metadata",
    ],
)
def test_probe_rejects_nonmetadata_redirect_before_request(synthetic, target):
    responses, calls, transport = synthetic
    responses[hosted.INFO_URL] = httpx.Response(
        302, headers={"location": target}
    )
    with pytest.raises(hosted.QualificationError):
        hosted.run_hosted_metadata_probe(SHA, transport=transport)
    assert calls == [hosted.INFO_URL]


def test_probe_retry_retains_first_and_terminal_causes(synthetic, monkeypatch):
    _, _, _transport = synthetic
    calls = []
    monkeypatch.setattr(hosted.time, "sleep", lambda _: None)

    def handler(request):
        calls.append(str(request.url))
        raise httpx.ConnectError("hidden") from socket.gaierror(-2, "hidden")

    with pytest.raises(hosted.QualificationError) as caught:
        hosted.run_hosted_metadata_probe(
            SHA, transport=httpx.MockTransport(handler)
        )
    report = hosted.metadata_probe_report(hosted.failure_report(caught.value))
    assert calls == [hosted.INFO_URL, hosted.INFO_URL]
    assert report["transport_diagnostics"] == {
        "retry_cause": "dns",
        "terminal_cause": "dns",
    }
    assert "hidden" not in json.dumps(report)


def test_probe_runtime_uses_guarded_transport(synthetic, monkeypatch):
    _, calls, transport = synthetic
    policies = []

    def factory(*, policy):
        policies.append(policy)
        return transport

    monkeypatch.setattr(hosted, "BoundIPAddressTransport", factory)
    assert (
        hosted.run_hosted_metadata_probe(SHA)["status"] == "metadata_verified"
    )
    assert calls == [hosted.INFO_URL]
    assert policies[0].allowed_hosts == hosted.HOSTS
    assert policies[0].timeout_seconds == 30


def test_metadata_cli_success_and_failure_are_scoped(
    tmp_path, synthetic, monkeypatch
):
    _, _, transport = synthetic
    output = tmp_path / "receipt.json"
    args = ["--exact-commit", SHA, "--metadata-only", "--output", str(output)]
    monkeypatch.setattr(
        cli,
        "run_hosted_metadata_probe",
        lambda exact, progress: hosted.run_hosted_metadata_probe(
            exact, transport=transport, progress=progress
        ),
    )
    assert cli.main(args) == 0
    assert (
        json.loads(output.read_text())["report"]["status"]
        == "metadata_verified"
    )

    def fail(_exact, *, progress):
        progress(
            hosted.metadata_probe_report({
                "status": "incomplete",
                "progress": {"stage": "public-before"},
            })
        )
        raise hosted.QualificationError("public-before", "transport-connect")

    monkeypatch.setattr(cli, "run_hosted_metadata_probe", fail)
    assert cli.main(args) == 1
    report = json.loads(output.read_text())["report"]
    assert report["corpus_qualified"] is False
    assert report["progress"]["stage"] == "public-before"


def test_metadata_interruption_retains_scoped_atomic_checkpoint(
    tmp_path, monkeypatch
):
    output = tmp_path / "receipt.json"

    def interrupt(_exact, *, progress):
        progress(hosted.metadata_probe_report({"status": "incomplete"}))
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_hosted_metadata_probe", interrupt)
    with pytest.raises(KeyboardInterrupt):
        cli.main([
            "--exact-commit",
            SHA,
            "--metadata-only",
            "--output",
            str(output),
        ])
    report = json.loads(output.read_text())["report"]
    assert report["status"] == "incomplete"
    assert report["operation"] == "pbs-public-metadata-diagnostic"
    assert report["corpus_qualified"] is False


def test_oversize_fallback_does_not_lose_metadata_scope(tmp_path):
    report = hosted.metadata_probe_report({"status": "passed"})
    report["oversize"] = "x" * hosted.MAX_REPORT_BYTES
    written = cli._write(tmp_path / "receipt.json", report)
    assert written["status"] == "failed"
    assert written["operation"] == "pbs-public-metadata-diagnostic"
    assert written["corpus_qualified"] is False


@pytest.mark.parametrize("status", [[], "unexpected", "metadata_verified"])
def test_scope_drops_corpus_fields_and_handles_unknown_status(status):
    result = hosted.metadata_probe_report({
        "status": status,
        "qualification": {"secret": "hidden"},
    })
    assert "qualification" not in result
    assert result["status"] in {"failed", "metadata_verified"}


def test_diagnostic_workflow_has_only_scoped_read_and_receipt_paths():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/pbs-public-metadata-diagnostic.yml"
    ).read_text()
    assert workflow.count("--metadata-only") == 2
    assert "--metadata-only --failure-only" in workflow
    assert "HF_TOKEN" not in workflow
    assert "schedule:" not in workflow
    assert "timeout-minutes: 6" in workflow
    assert "gh issue comment 341" in workflow
    assert "path: pbs-metadata-diagnostic-receipt.json" in workflow


def test_metadata_body_cap_is_preserved(synthetic):
    responses, calls, transport = synthetic
    responses[hosted.INFO_URL] = b"x" * (1024 * 1024 + 1)
    with pytest.raises(hosted.QualificationError):
        hosted.run_hosted_metadata_probe(SHA, transport=transport)
    assert calls == [hosted.INFO_URL]


def test_metadata_identical_redirect_loop_remains_bounded(synthetic):
    responses, calls, transport = synthetic
    responses[hosted.INFO_URL] = httpx.Response(
        302, headers={"location": hosted.INFO_URL}
    )
    with pytest.raises(hosted.QualificationError, match="redirect"):
        hosted.run_hosted_metadata_probe(SHA, transport=transport)
    assert calls == [hosted.INFO_URL] * 4


def test_diagnostic_request_hook_rejects_non_get():
    with pytest.raises(ValueError, match="destination-policy"):
        hosted._metadata_request(httpx.Request("POST", hosted.INFO_URL))


def test_corpus_success_cannot_be_relabelled_metadata_success():
    report = hosted.metadata_probe_report({
        "status": "passed",
        "qualification": {"rows": 100},
        "member_retrieval": "extracted-from-verified-archive",
    })
    assert report["status"] == "failed"
    assert "qualification" not in report


@pytest.mark.usefixtures("synthetic")
def test_metadata_stream_deadline_is_terminal(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(
        hosted,
        "time",
        SimpleNamespace(monotonic=lambda: now[0], sleep=lambda _: None),
    )
    calls = []

    class DelayedMetadata(httpx.SyncByteStream):
        def __iter__(self):
            now[0] = 301.0
            yield b"{}"

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, stream=DelayedMetadata())

    with pytest.raises(hosted.QualificationError, match="timeout") as caught:
        hosted.run_hosted_metadata_probe(
            SHA, transport=httpx.MockTransport(handler)
        )
    assert calls == [hosted.INFO_URL]
    assert hosted.failure_report(caught.value)["transport_retry"] is None
