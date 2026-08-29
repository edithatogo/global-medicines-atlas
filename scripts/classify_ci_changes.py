"""Classify whether a pull-request diff requires heavyweight CI lanes."""

from __future__ import annotations

import argparse
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from collections.abc import Sequence

_HEAVY_PREFIXES = (
    ".context/",
    ".github/",
    "contracts/",
    "quality/",
    "schemas/",
    "scripts/",
    "sources/",
    "src/",
    "tests/",
)
_HEAVY_FILES = {
    ".gitattributes",
    ".python-version",
    "AGENTS.md",
    "codecov.yml",
    "pixi.lock",
    "pixi.toml",
    "pylock.toml",
    "pyproject.toml",
    "renovate.json",
    "uv.lock",
}


def requires_heavy_ci(paths: Sequence[str]) -> bool:
    """Return whether changed paths can affect governed runtime evidence."""
    return any(
        path in _HEAVY_FILES or path.startswith(_HEAVY_PREFIXES)
        for path in paths
    )


def changed_paths(base: str, head: str) -> tuple[str, ...]:
    """Return repository-relative paths changed between exact Git revisions."""
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to classify CI changes")
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [git, "diff", "--name-only", "--diff-filter=ACDMRTUXB", base, head],
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(path for path in result.stdout.splitlines() if path)


def main() -> int:
    """Emit a GitHub Actions output, failing open outside pull requests."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    heavy = args.event != "pull_request"
    if not heavy:
        heavy = requires_heavy_ci(changed_paths(args.base, args.head))
    print(f"heavy={'true' if heavy else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
