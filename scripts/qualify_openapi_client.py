"""Snapshot, diff, and generate the public read-only OpenAPI client."""

# ruff: file-ignore[suspicious-subprocess-import, subprocess-without-shell-equals-true]

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.api import create_app
from global_medicines_atlas.openapi_client_generator import generate_client
from global_medicines_atlas.openapi_semantic import (
    assert_semantically_compatible,
    semantic_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "contracts/openapi-readonly-v1.json"
CLIENT = ROOT / "src/global_medicines_atlas/generated/openapi_client.py"
SNAPSHOT_RELATIVE = SNAPSHOT.relative_to(ROOT).as_posix()
_GIT_SHA1_LENGTH = 40


class HistoricalBaselineError(RuntimeError):
    """The immutable OpenAPI baseline cannot be loaded from Git history."""


def _document() -> dict[str, Any]:
    return create_app(cast("Any", object())).openapi()


def _render_snapshot(document: dict[str, Any]) -> str:
    return (
        json.dumps(semantic_snapshot(document), indent=2, sort_keys=True) + "\n"
    )


def _git(
    *arguments: str,
    root: Path = ROOT,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("git")
    if executable is None:
        raise HistoricalBaselineError(
            "git is required for immutable OpenAPI baseline comparison"
        )
    completed = subprocess.run(
        [executable, *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise HistoricalBaselineError(
            f"git {' '.join(arguments)} failed: {detail}"
        )
    return completed


def _resolve_commit(reference: str, *, root: Path = ROOT) -> str:
    if not reference.strip():
        raise HistoricalBaselineError("the OpenAPI baseline ref is empty")
    completed = _git(
        "rev-parse",
        "--verify",
        f"{reference}^{{commit}}",
        root=root,
    )
    commit = completed.stdout.strip()
    if len(commit) != _GIT_SHA1_LENGTH or any(
        character not in "0123456789abcdef" for character in commit.lower()
    ):
        raise HistoricalBaselineError(
            f"the OpenAPI baseline ref did not resolve to a commit: {reference}"
        )
    ancestor = _git(
        "merge-base",
        "--is-ancestor",
        commit,
        "HEAD",
        root=root,
        check=False,
    )
    if ancestor.returncode != 0:
        raise HistoricalBaselineError(
            f"the OpenAPI baseline is not an ancestor of HEAD: {commit}"
        )
    return commit


def _default_baseline_ref() -> str:
    configured = os.environ.get("GMA_OPENAPI_BASE_REF", "").strip()
    if configured and set(configured) != {"0"}:
        return configured
    for candidate in ("origin/main", "HEAD^"):
        if (
            _git("rev-parse", "--verify", candidate, check=False).returncode
            == 0
        ):
            return candidate
    raise HistoricalBaselineError(
        "no immutable OpenAPI baseline ref is available; pass --baseline-ref"
    )


def load_historical_snapshot(
    reference: str,
    *,
    root: Path = ROOT,
    snapshot_relative: str = SNAPSHOT_RELATIVE,
) -> dict[str, Any]:
    """Load the baseline snapshot from an ancestor commit, never the worktree."""
    commit = _resolve_commit(reference, root=root)
    completed = _git(
        "show",
        f"{commit}:{snapshot_relative}",
        root=root,
    )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise HistoricalBaselineError(
            f"the historical OpenAPI snapshot is invalid JSON at {commit}"
        ) from error
    if not isinstance(value, dict):
        raise HistoricalBaselineError(
            f"the historical OpenAPI snapshot is not an object at {commit}"
        )
    return cast("dict[str, Any]", value)


def main() -> int:
    """Check committed artifacts or regenerate them deterministically."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--baseline-ref",
        help=(
            "ancestor Git ref containing the immutable compatibility baseline; "
            "defaults to GMA_OPENAPI_BASE_REF, origin/main, then HEAD^"
        ),
    )
    arguments = parser.parse_args()
    document = _document()
    rendered_snapshot = _render_snapshot(document)
    snapshot = json.loads(rendered_snapshot)
    rendered_client = generate_client(snapshot)
    baseline_ref = arguments.baseline_ref or _default_baseline_ref()
    historical = load_historical_snapshot(baseline_ref)
    assert_semantically_compatible(historical, document)
    if arguments.write:
        SNAPSHOT.write_text(rendered_snapshot, encoding="utf-8", newline="\n")
        CLIENT.parent.mkdir(parents=True, exist_ok=True)
        CLIENT.write_text(rendered_client, encoding="utf-8", newline="\n")
        return 0
    if SNAPSHOT.read_text(encoding="utf-8") != rendered_snapshot:
        raise SystemExit("OpenAPI snapshot is stale; run with --write")
    if CLIENT.read_text(encoding="utf-8") != rendered_client:
        raise SystemExit("generated OpenAPI client is stale; run with --write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "HistoricalBaselineError",
    "load_historical_snapshot",
    "main",
]
