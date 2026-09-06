"""Real synthetic Git bundles and fail-closed hosted runner entry points."""

import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def publisher(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "scripts"))
    return importlib.import_module("publish_donor_history")


def test_incremental_bundle_restores_only_with_baseline(publisher, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    git = publisher.git
    git(source, "init", "--quiet")
    (source / "example.txt").write_text("synthetic baseline\n")
    git(source, "add", "example.txt")
    git(
        source,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "baseline",
    )
    baseline = git(source, "rev-parse", "HEAD")
    git(source, "update-ref", "refs/archive/pinned", baseline)
    baseline_bundle = tmp_path / "baseline.bundle"
    git(
        source,
        "bundle",
        "create",
        "--version=2",
        str(baseline_bundle),
        "refs/archive/pinned",
    )
    (source / "example.txt").write_text("synthetic extension\n")
    git(source, "add", "example.txt")
    git(
        source,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "extension",
    )
    head = git(source, "rev-parse", "HEAD")
    git(source, "update-ref", "refs/archive/extension", head)
    extension = tmp_path / "extension.bundle"
    git(
        source,
        "bundle",
        "create",
        "--version=2",
        str(extension),
        "refs/archive/extension",
        f"^{baseline}",
    )
    assert publisher.prerequisites(extension) == (baseline,)
    assert publisher.prerequisites(baseline_bundle) == ()
    restore = tmp_path / "restore"
    restore.mkdir()
    git(restore, "init", "--bare", "--quiet")
    with pytest.raises(ValueError, match="Git operation failed"):
        git(restore, "bundle", "verify", str(extension))
    git(
        restore,
        "fetch",
        str(baseline_bundle),
        "refs/archive/pinned:refs/archive/baseline",
    )
    git(restore, "bundle", "verify", str(extension))
    git(
        restore,
        "fetch",
        str(extension),
        "refs/archive/extension:refs/archive/extension",
    )
    assert git(restore, "rev-parse", "refs/archive/extension") == head
    git(restore, "merge-base", "--is-ancestor", baseline, head)
    git(restore, "fsck", "--full", "--strict")


@pytest.mark.parametrize(
    "payload",
    [
        b"bad\n",
        b"# v2 git bundle\n",
        b"# v2 git bundle\n" + b"a" * 4096,
        b"# v2 git bundle\n" + b"a\n" * 256,
    ],
)
def test_malformed_bundle_headers_fail(publisher, tmp_path, payload):
    path = tmp_path / "bad.bundle"
    path.write_bytes(payload)
    with pytest.raises(ValueError, match="bundle"):
        publisher.prerequisites(path)


def test_history_cli_refuses_local_before_network(publisher, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(
        "sys.argv", ["publish_donor_history.py", "--exact-commit", "a" * 40]
    )

    def forbidden(*_):
        pytest.fail("network or temporary workspace before authority")

    monkeypatch.setattr(publisher, "gh", forbidden)
    monkeypatch.setattr(publisher.tempfile, "mkdtemp", forbidden)
    with pytest.raises(ValueError, match="Actions dispatch"):
        publisher.main()


def test_history_cli_refuses_inert_contract_before_network(
    publisher, monkeypatch
):
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": "a" * 40,
        "GITHUB_RUN_ID": "123",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        "sys.argv", ["publish_donor_history.py", "--exact-commit", "a" * 40]
    )

    def forbidden(*_):
        pytest.fail("network before explicit authorization")

    monkeypatch.setattr(publisher, "gh", forbidden)
    with pytest.raises(ValueError, match="not authorized"):
        publisher.main()


def test_retained_local_patch_and_fixture_have_exact_digests(publisher):
    root = Path(__file__).parents[1] / "docs/migrations/scraper-local-20260906"
    inventory = json.loads((root / "inventory.json").read_text())
    patch = inventory["preserved_patch"]
    assert (
        publisher.object_info(patch["path"], root / patch["path"]).sha256
        == patch["sha256"]
    )
    fixture = next(
        item
        for item in inventory["local_entries"]
        if item["disposition"] == "retain-synthetic-legacy"
    )
    observed = publisher.object_info(
        "sample_pbs.json", root / "sample_pbs.json"
    )
    assert observed.sha256 == fixture["sha256"]
    assert observed.byte_count == fixture["bytes"]
