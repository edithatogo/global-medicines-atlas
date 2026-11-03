"""Build a complete, credential-free GitHub dependency snapshot from uv.lock."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tomllib
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "edithatogo/global-medicines-atlas"


def require_trusted_main(env: Mapping[str, str], checkout_sha: str) -> None:
    """Reject local, PR, other-repository and mismatched-checkout submissions."""
    expected = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": checkout_sha,
    }
    if (
        any(env.get(key) != value for key, value in expected.items())
        or env.get("GITHUB_EVENT_NAME") not in {"push", "workflow_dispatch"}
        or not re.fullmatch(r"[0-9a-f]{40}", checkout_sha)
    ):
        raise ValueError("dependency submission requires exact trusted main")


def references(package: dict[str, Any]) -> list[dict[str, Any]]:
    """Include every locked optional edge as well as ordinary dependencies."""
    result = list(package.get("dependencies", []))
    for entries in package.get("optional-dependencies", {}).values():
        result.extend(entries)
    return result


def registry_packages(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Refuse unsupported/private sources rather than silently omit packages."""
    result: list[dict[str, Any]] = []
    for package in document["package"]:
        source = package["source"]
        if source == {"editable": "."}:
            continue
        if source != {"registry": "https://pypi.org/simple"}:
            raise ValueError("unsupported locked dependency source")
        result.append(package)
    if not result:
        raise ValueError("empty locked dependency inventory")
    return result


def package_url(package: dict[str, Any]) -> str:
    """Use canonical PyPI names and explicit versions as unique identities."""
    name = re.sub(r"[-_.]+", "-", package["name"]).lower()
    version = package.get("version")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) or (
        not isinstance(version, str) or not version
    ):
        raise ValueError("invalid locked dependency identity")
    return f"pkg:pypi/{name}@{quote(version, safe='')}"


def reachable(roots: set[str], edges: dict[str, list[str]]) -> set[str]:
    """Compute group coverage without interpreting away platform markers."""
    visited: set[str] = set()
    pending = list(roots)
    while pending:
        current = pending.pop()
        if current not in visited:
            visited.add(current)
            pending.extend(edges[current])
    return visited


def resolved_inventory(document: dict[str, Any]) -> dict[str, Any]:
    """Preserve all versions and reject ambiguous name-only references."""
    packages = registry_packages(document)
    identities = {package_url(p): p for p in packages}
    if len(identities) != len(packages):
        raise ValueError("duplicate locked dependency identity")

    def resolve(dependency: dict[str, Any]) -> str:
        matches = [
            identity
            for identity, package in identities.items()
            if package["name"] == dependency["name"]
            and (
                "version" not in dependency
                or package["version"] == dependency["version"]
            )
        ]
        if len(matches) != 1:
            raise ValueError("ambiguous or missing locked dependency reference")
        return matches[0]

    edges = {
        identity: sorted({resolve(d) for d in references(p)})
        for identity, p in identities.items()
    }
    projects = [
        p for p in document["package"] if p["source"] == {"editable": "."}
    ]
    if len(projects) != 1:
        raise ValueError("exactly one local project is required")
    runtime_roots = {resolve(d) for d in references(projects[0])}
    dev_roots = {
        resolve(d)
        for entries in projects[0].get("dev-dependencies", {}).values()
        for d in entries
    }
    runtime = reachable(runtime_roots, edges)
    development = reachable(dev_roots, edges)
    result: dict[str, Any] = {}
    for identity in sorted(identities):
        row: dict[str, Any] = {
            "package_url": identity,
            "relationship": "direct"
            if identity in runtime_roots | dev_roots
            else "indirect",
            "dependencies": edges[identity],
        }
        if identity in runtime | development:
            row["scope"] = "runtime" if identity in runtime else "development"
        result[identity] = row
    return result


def build_snapshot(
    raw: bytes, sha: str, run_id: str, scanned: str
) -> dict[str, Any]:
    """Return a deterministic all-platform/all-extra/all-group lock snapshot."""
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not run_id.isdecimal():
        raise ValueError("snapshot requires an exact commit and run identity")
    if datetime.fromisoformat(scanned).utcoffset() is None:
        raise ValueError("snapshot scan time requires a timezone")
    resolved = resolved_inventory(tomllib.loads(raw.decode("utf-8")))
    return {
        "version": 0,
        "sha": sha,
        "ref": "refs/heads/main",
        "scanned": scanned,
        "job": {
            "id": run_id,
            "correlator": "gma-uv-lock-main",
            "html_url": f"https://github.com/{REPOSITORY}/actions/runs/{run_id}",
        },
        "detector": {
            "name": "gma-uv-lock",
            "version": "1.0.0",
            "url": f"https://github.com/{REPOSITORY}/blob/main/scripts/build_dependency_snapshot.py",
        },
        "metadata": {
            "uv_lock_sha256": hashlib.sha256(raw).hexdigest(),
            "package_count": len(resolved),
            "coverage": "all_locked_platforms_extras_groups",
        },
        "manifests": {
            "uv.lock": {
                "name": "uv.lock",
                "file": {"source_location": "uv.lock"},
                "resolved": resolved,
            }
        },
    }


def main() -> None:
    """Prepare snapshot JSON; the workflow owns the sole external POST."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scanned", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trusted-main", action="store_true")
    parser.add_argument("--checkout-sha", default="")
    args = parser.parse_args()
    if args.trusted_main:
        require_trusted_main(os.environ, args.checkout_sha)
        if args.sha != args.checkout_sha:
            raise ValueError("snapshot commit differs from trusted checkout")
    snapshot = build_snapshot(
        (ROOT / "uv.lock").read_bytes(), args.sha, args.run_id, args.scanned
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
