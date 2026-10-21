"""Archive runner stops locally and accepts only the bounded frozen cohort."""

import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import yaml
from scripts import profile_frozen_mbs_archives as module
from test_mbs_archive_members import fixture

SHA = "a" * 40


def test_local_context_stops_before_archive_transport(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    def refuse(_):
        raise AssertionError("real source transport forbidden locally")

    with pytest.raises(ValueError, match="exact main Actions"):
        module.qualify(SHA, 0, transport=httpx.MockTransport(refuse))


@pytest.mark.parametrize("index", [-1, 6, True])
def test_archive_index_is_bounded_before_source_selection(monkeypatch, index):
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": SHA,
    }.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="index"):
        module.qualify(SHA, index)


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": SHA,
    }.items():
        monkeypatch.setenv(key, value)
    path, source = fixture(tmp_path)
    source = replace(source, dataset=module.DATASET, revision=module.REVISION)
    monkeypatch.setattr(module, "load_archives", lambda _: (source,) * 6)
    url = f"https://huggingface.co/datasets/{module.DATASET}/resolve/{module.REVISION}/{source.source_path}?download=true"
    responses = {
        module.INFO_URL: json.dumps({
            "id": module.DATASET,
            "sha": module.REVISION,
            "private": False,
            "gated": False,
        }).encode(),
        url: path.read_bytes(),
    }
    calls = []

    def handle(request):
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        calls.append(str(request.url))
        return httpx.Response(200, content=responses[str(request.url)])

    return source, responses, calls, httpx.MockTransport(handle), url


def test_streamed_source_is_verified_inventoried_and_removed(
    synthetic, monkeypatch
):
    observed = []
    original = module.profile_archive_members

    def profile(path, source):
        assert path.is_file()
        observed.append(path)
        return original(path, source)

    monkeypatch.setattr(module, "profile_archive_members", profile)
    report = module.qualify(SHA, 0, transport=synthetic[3])
    assert report["status"] == "passed"
    assert report["result"]["member_count"] == 3
    assert report["temporary_source_removed"] is True
    assert len(synthetic[2]) == 3
    assert observed
    assert not observed[0].exists()
    assert "SYNTHETIC" not in json.dumps(report)


def test_oversized_stream_rejects_before_member_parse(synthetic):
    source, responses, _, transport, url = synthetic
    responses[url] += b"changed"
    with pytest.raises(ValueError, match="streamed byte bound"):
        module.qualify(SHA, 0, transport=transport)
    assert source.source_bytes > 0


def test_private_source_rejected_before_archive_download(synthetic):
    _, responses, calls, transport, _ = synthetic
    responses[module.INFO_URL] = json.dumps({"private": True}).encode()
    with pytest.raises(ValueError, match="public revision"):
        module.qualify(SHA, 0, transport=transport)
    assert calls == [module.INFO_URL]


def test_cli_existing_evidence_is_preserved(tmp_path):
    output = tmp_path / "receipt.json"
    output.write_text("human evidence")
    with pytest.raises(SystemExit):
        module.main([
            "--exact-commit",
            SHA,
            "--archive-index",
            "0",
            "--output",
            str(output),
        ])
    assert output.read_text() == "human evidence"


def test_cli_source_exception_text_is_withheld(tmp_path, monkeypatch):
    def fail(*_):
        raise ValueError("SYNTHETIC SECRET")

    monkeypatch.setattr(module, "qualify", fail)
    output = tmp_path / "receipt.json"
    assert (
        module.main([
            "--exact-commit",
            SHA,
            "--archive-index",
            "0",
            "--output",
            str(output),
        ])
        == 1
    )
    assert "SYNTHETIC SECRET" not in output.read_text()
    assert json.loads(output.read_bytes())["status"] == "failed"


def test_workflow_runs_all_six_read_only_bounded_jobs():
    root = Path(__file__).resolve().parents[1]
    document = yaml.load(
        (
            root / ".github/workflows/mbs-q1-source-meaning-diagnostics.yml"
        ).read_text(),
        Loader=yaml.BaseLoader,
    )
    job = document["jobs"]["archive-members"]
    assert job["strategy"]["matrix"]["archive"] == [
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
    ]
    assert job["strategy"]["fail-fast"] == "false"
    assert job["strategy"]["max-parallel"] == "2"
    assert job["permissions"] == {"contents": "read"}
    assert job["timeout-minutes"] == "30"
    step = next(step for step in job["steps"] if "run" in step)
    assert '--archive-index "$ARCHIVE_INDEX"' in step["run"]
    assert 'test "${GITHUB_SHA}" = "${REQUESTED_COMMIT}"' in step["run"]
    assert job["steps"][-1]["if"] == "always()"
    assert job["steps"][-1]["with"]["path"] == "archive-members.json"
