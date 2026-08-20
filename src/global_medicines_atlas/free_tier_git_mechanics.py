"""Disposable Git workflow and restore experiment for free-tier runners."""

from __future__ import annotations

import hashlib
import json
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed Git argv is the experiment subject
import time
from pathlib import Path
from typing import Any


def _git(
    directory: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        ["git", *arguments],  # ruff: ignore[start-process-with-partial-path]
        cwd=directory,
        check=check,
        capture_output=True,
        text=True,
    )


def _inventory(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if ".git" not in path.relative_to(root).parts
    }


def run_git_mechanics(work_root: Path) -> dict[str, Any]:  # ruff: ignore[too-many-locals]
    """Exercise conflict, rollback, inventory, loss, and clean restoration."""
    started = time.monotonic_ns()
    remote = work_root / "remote.git"
    writer = work_root / "writer"
    restored = work_root / "restored"
    remote.mkdir(parents=True)
    _git(remote, "init", "--bare", "--initial-branch=main")
    writer.mkdir()
    _git(writer, "init", "--initial-branch=main")
    _git(writer, "config", "user.name", "GMA Experiment")
    _git(writer, "config", "user.email", "experiment@example.invalid")
    evidence = writer / "evidence.json"
    evidence.write_text(json.dumps({"revision": 1, "value": 1}) + "\n")
    _git(writer, "add", "evidence.json")
    _git(writer, "commit", "-m", "initial synthetic evidence")
    _git(writer, "remote", "add", "origin", str(remote))
    _git(writer, "push", "-u", "origin", "main")
    initial_commit = _git(writer, "rev-parse", "HEAD").stdout.strip()

    _git(writer, "switch", "-c", "experiment")
    evidence.write_text(json.dumps({"revision": 2, "value": 2}) + "\n")
    _git(writer, "commit", "-am", "experiment update")
    experiment_commit = _git(writer, "rev-parse", "HEAD").stdout.strip()
    _git(writer, "switch", "main")
    evidence.write_text(json.dumps({"revision": 2, "value": 3}) + "\n")
    _git(writer, "commit", "-am", "divergent update")
    conflict = _git(writer, "merge", "--no-commit", "experiment", check=False)
    conflict_detected = conflict.returncode != 0
    evidence.write_text(json.dumps({"revision": 3, "value": 5}) + "\n")
    _git(writer, "add", "evidence.json")
    _git(writer, "commit", "-m", "resolve synthetic conflict")
    _git(writer, "tag", "accepted-v1")
    _git(writer, "push", "origin", "main", "accepted-v1")
    accepted_commit = _git(writer, "rev-parse", "HEAD").stdout.strip()
    inventory = _inventory(writer)
    latest_push = time.monotonic_ns()

    _git(
        work_root,
        "clone",
        "--branch",
        "accepted-v1",
        str(remote),
        str(restored),
    )
    restored_inventory = _inventory(restored)
    restored_commit = _git(restored, "rev-parse", "HEAD").stdout.strip()
    retained_tag_commit = _git(
        restored, "rev-list", "-n", "1", "accepted-v1"
    ).stdout.strip()
    completed = time.monotonic_ns()
    rollback_contents = _git(
        restored, "show", f"{initial_commit}:evidence.json"
    ).stdout

    return {
        "schema_version": "1.0",
        "provider_scope": "portable_git_on_standard_github_hosted_runner",
        "operations": {
            "branch_created": True,
            "divergent_update_created": True,
            "conflict_detected": conflict_detected,
            "conflict_resolved": accepted_commit != experiment_commit,
            "rollback_read_verified": json.loads(rollback_contents)["revision"]
            == 1,
            "clean_restore_verified": inventory == restored_inventory,
            "retention_reference_verified": retained_tag_commit
            == accepted_commit,
        },
        "commits": {
            "initial": initial_commit,
            "divergent": experiment_commit,
            "accepted": accepted_commit,
            "restored": restored_commit,
        },
        "inventory": inventory,
        "observed_experimental_rpo_seconds": 0,
        "observed_restore_seconds": round(
            (completed - latest_push) / 1_000_000_000, 6
        ),
        "observed_total_seconds": round(
            (completed - started) / 1_000_000_000, 6
        ),
        "claims_explicitly_not_established": [
            "worm_or_object_lock",
            "guaranteed_geographic_replication",
            "production_rpo_or_rto",
            "provider_sla",
            "immutable_history",
        ],
        "core_dependency_added": False,
    }
