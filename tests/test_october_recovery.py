"""Exercise October interruptions without a live publication or real source data."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- local Git fixtures and the workflow's Bash step.
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
import yaml
from scripts import publish_october_openfda_hosted as october

from global_medicines_atlas.publication_transport import (
    ArtifactBinding,
    PublicationDestination,
    PublicationPlan,
    PublicationTarget,
)

ROOT = Path(__file__).resolve().parents[1]
HEAD = "b" * 40


def planned(files):
    return PublicationPlan(
        release_version=october.BATCH,
        target=PublicationTarget(
            destination=PublicationDestination.HUGGING_FACE,
            repository=october.REPOSITORY,
            revision="main",
            public_base_url=f"https://huggingface.co/datasets/{october.REPOSITORY}",
        ),
        artifacts=tuple(
            ArtifactBinding(
                relative_path=path,
                size=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
            )
            for path, body in files.items()
        ),
    )


def test_git_checkpoint_hashes_the_pinned_bytes(tmp_path, monkeypatch):
    repo = tmp_path / "public"
    repo.mkdir()

    def git(*args):
        executable = shutil.which("git")
        assert executable is not None
        return subprocess.check_output(  # ruff: ignore[subprocess-without-shell-equals-true] -- local synthetic Git data.
            [executable, "-C", str(repo), *args],
            text=True,
        ).strip()

    git("init", "--quiet")
    files = {"receipt.json": b"one"}
    (repo / "receipt.json").write_bytes(files["receipt.json"])
    git("add", "receipt.json")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    head = git("rev-parse", "HEAD")
    plan = planned(files)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{repo.as_uri()}.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", plan.target.public_base_url)
    monkeypatch.setattr(
        october,
        "OctoberReadback",
        Mock(side_effect=AssertionError("one Git fetch suffices")),
    )
    october.verify_git_checkpoint(plan.target, head, list(plan.artifacts))
    wrong = plan.artifacts[0].model_copy(update={"sha256": "0" * 64})
    with pytest.raises(ValueError, match="destination checksum differs"):
        october.verify_git_checkpoint(plan.target, head, [wrong])


def test_interrupted_verification_reuses_only_same_revision_readbacks(
    tmp_path, monkeypatch
):
    files = {"a.json": b"one", "b.zip": b"two"}
    plan = planned(files)
    monkeypatch.setattr(october, "PLAN_SHA256", plan.sha256())
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setattr(october.time, "sleep", lambda _wait: None)
    october.record_intent(tmp_path, plan, HEAD)
    october.record_upload(tmp_path, plan, HEAD)
    calls = []

    def serve(request):
        name = request.url.path.rsplit("/", 1)[1]
        calls.append(name)
        if name == "b.zip" and len(calls) <= 5:
            return httpx.Response(503)
        return httpx.Response(200, content=files[name])

    reader = october.OctoberReadback
    monkeypatch.setattr(
        october,
        "OctoberReadback",
        lambda **kw: reader(
            **kw, transport_factory=lambda: httpx.MockTransport(serve)
        ),
    )
    with pytest.raises(october.TransientOctoberError, match=r"b.zip: HTTP 503"):
        october.verify(tmp_path, HEAD)
    assert (
        json.loads((tmp_path / "verified.json").read_text())["state"]
        != "public"
    )
    journal = tmp_path / f"readbacks-{HEAD}.jsonl"
    assert json.loads(journal.read_text())["relative_path"] == "a.json"
    prior = tmp_path / "prior" / "openfda-october-verification-1"
    prior.mkdir(parents=True)
    journal.rename(prior / journal.name)
    (prior / ("readbacks-" + "e" * 40 + ".jsonl")).write_text("invalid\n")
    assert october.verify(tmp_path, HEAD) == 0
    receipt = json.loads((tmp_path / "verified.json").read_text())
    assert (receipt["state"], receipt["remote_revision"]) == ("public", HEAD)
    assert [a["relative_path"] for a in receipt["verified_artifacts"]] == list(
        files
    )
    assert calls == ["a.json", "b.zip", "b.zip", "b.zip", "b.zip", "b.zip"]
    stale = json.loads((prior / journal.name).read_text())
    stale["verification_uri"] = stale["verification_uri"].replace(
        HEAD, "e" * 40
    )
    (prior / journal.name).write_text(json.dumps(stale))
    assert october.verify(tmp_path, HEAD) == 1


def test_lost_commit_acknowledgement_requires_inventory_before_another_write():
    api = Mock()
    api.create_commit.side_effect = httpx.ConnectError("lost acknowledgement")
    with pytest.raises(
        october.TransientOctoberError, match="requires reconciliation"
    ):
        october.commit_artifacts(api, Mock(), HEAD, [])
    assert api.create_commit.call_count == 1
    for code in (401, 403, 404):
        error = october.AnonymousReadbackHTTPError(httpx.Response(code))
        assert october.transient_reason(error) is None
    assert (
        october.transient_reason(
            ValueError("anonymous artifact digest mismatch")
        )
        is None
    )


@pytest.mark.parametrize(
    ("failure", "expect_retry"),
    [
        ("marked", True),
        ("runner_lost", True),
        ("integrity", False),
        ("cancelled", False),
        ("in_progress", False),
        ("success", False),
        ("verify_only_second_attempt", True),
        ("expired_source", False),
    ],
)
def test_scheduled_recovery_only_reruns_eligible_jobs(
    tmp_path, failure, expect_retry
):
    """Execute the production workflow shell with an isolated GitHub CLI."""
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/recover-october-openfda.yml").read_text()
    )
    script = workflow["jobs"]["recover"]["steps"][0]["run"]
    state = "in_progress" if failure == "in_progress" else "completed"
    conclusion = failure if failure in {"success", "cancelled"} else "failure"
    attempt = 2 if failure == "verify_only_second_attempt" else 1
    (tmp_path / "latest").write_text(
        json.dumps({
            "databaseId": 12,
            "attempt": attempt,
            "status": state,
            "conclusion": conclusion,
        })
    )
    private = {
        "name": "Publish October from the private read-only source",
        "conclusion": "failure",
        "check_run_url": "https://api.github.com/check-runs/1",
        "steps": [
            {
                "name": "Eligible for automatic October retry",
                "conclusion": "success"
                if failure in {"marked", "expired_source"}
                else "skipped",
            }
        ],
    }
    (tmp_path / "first").write_text(json.dumps({"jobs": [private]}))
    if attempt == 2:
        private.update(name="Verify October archive")
        private["steps"][0]["conclusion"] = "success"
    (tmp_path / "current").write_text(json.dumps({"jobs": [private]}))
    message = (
        "The hosted runner lost communication."
        if failure == "runner_lost"
        else "Exit code 1"
    )
    (tmp_path / "annotations").write_text(json.dumps([{"message": message}]))
    gh = tmp_path / "gh"
    gh.write_text("""#!/bin/sh
case "$1 $2" in
  'run list') cat latest;;
  'run rerun') printf '%s\n' "$*" > rerun;;
  'api '*/annotations) cat annotations;;
  'api '*/attempts/1/jobs) cat first;;
  'api '*/attempts/2/jobs) cat current;;
  *) exit 1;;
esac
""")
    gh.chmod(0o700)
    date = tmp_path / "date"
    stamp = "202611290530" if failure == "expired_source" else "202611271030"
    date.write_text(f"#!/bin/sh\necho {stamp}\n")
    date.chmod(0o700)
    bash = shutil.which("bash")
    assert bash is not None
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] -- execute the checked-in workflow with the fake gh.
        [bash, "-c", script],
        cwd=tmp_path,
        check=True,
        env={
            **os.environ,
            "GITHUB_REPOSITORY": "test/repo",
            "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
            "RUNNER_ENVIRONMENT": "github-hosted",
        },
    )
    if expect_retry:
        assert (
            tmp_path / "rerun"
        ).read_text().strip() == "run rerun 12 --failed --repo test/repo"
    else:
        assert not (tmp_path / "rerun").exists()
