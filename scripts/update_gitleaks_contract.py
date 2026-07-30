"""Update the checksum-bound Gitleaks contract after a governed version bump."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "quality" / "tool-versions.json"
WORKFLOW = ROOT / ".github" / "workflows" / "security-context.yml"


def download_digest(version: str, asset: str) -> str:
    """Download the official release asset and return its SHA-256 digest."""
    url = (
        "https://github.com/gitleaks/gitleaks/releases/download/"
        f"v{version}/{asset}"
    )
    digest = hashlib.sha256()
    with urllib.request.urlopen(  # ruff: ignore[suspicious-url-open-usage]
        url, timeout=60
    ) as response:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def replace_exact(text: str, old: str, new: str) -> str:
    """Replace one governed literal and reject ambiguous source state."""
    if text.count(old) != 1:
        raise ValueError(f"expected exactly one governed literal: {old}")
    return text.replace(old, new)


def update(version: str) -> None:
    """Update manifest and workflow as one checksum-verified contract."""
    payload = cast(
        "dict[str, Any]", json.loads(MANIFEST.read_text(encoding="utf-8"))
    )
    versions = cast("dict[str, str]", payload["versions"])
    checksums = cast("dict[str, str]", payload["checksums"])
    old_version = versions["gitleaks"]
    old_asset = checksums["gitleaks_asset"]
    asset = f"gitleaks_{version}_linux_x64.tar.gz"
    digest = download_digest(version, asset)
    workflow = WORKFLOW.read_text(encoding="utf-8")
    workflow = replace_exact(
        workflow,
        f"GITLEAKS_ASSET: {old_asset}",
        f"GITLEAKS_ASSET: {asset}",
    )
    workflow = replace_exact(
        workflow,
        f"GITLEAKS_SHA256: {checksums['gitleaks_linux_x64']}",
        f"GITLEAKS_SHA256: {digest}",
    )
    workflow = replace_exact(
        workflow,
        f"GITLEAKS_VERSION: {old_version}",
        f"GITLEAKS_VERSION: {version}",
    )
    versions["gitleaks"] = version
    checksums["gitleaks_asset"] = asset
    checksums["gitleaks_linux_x64"] = digest
    MANIFEST.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    WORKFLOW.write_text(workflow, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    update(parser.parse_args().version)


if __name__ == "__main__":
    main()
