"""Update the checksum-bound Gitleaks contract after a governed version bump."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any, cast

from contract_update import replace_files_atomically

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "quality" / "tool-versions.json"
WORKFLOW = ROOT / ".github" / "workflows" / "security-context.yml"
CHECKSUM_FIELDS = 2
SHA256_HEX_LENGTH = 64


def download(url: str) -> bytes:
    """Download release metadata or bytes over the platform TLS transport."""
    chunks: list[bytes] = []
    with urllib.request.urlopen(  # ruff: ignore[suspicious-url-open-usage]
        url, timeout=60
    ) as response:
        while chunk := response.read(1024 * 1024):
            chunks.append(chunk)
    return b"".join(chunks)


def publisher_digest(version: str, asset: str) -> str:
    """Read the asset digest from Gitleaks' publisher checksum manifest."""
    base = f"https://github.com/gitleaks/gitleaks/releases/download/v{version}"
    manifest = download(f"{base}/gitleaks_{version}_checksums.txt").decode(
        "utf-8"
    )
    matches = [
        line.split()[0]
        for line in manifest.splitlines()
        if len(line.split()) >= CHECKSUM_FIELDS
        and line.split()[-1].lstrip("*") == asset
    ]
    if len(matches) != 1 or len(matches[0]) != SHA256_HEX_LENGTH:
        raise ValueError(f"publisher checksum missing or ambiguous for {asset}")
    return matches[0].lower()


def verified_asset_digest(version: str, asset: str) -> str:
    """Verify downloaded release bytes against the publisher manifest."""
    base = f"https://github.com/gitleaks/gitleaks/releases/download/v{version}"
    expected = publisher_digest(version, asset)
    archive = download(f"{base}/{asset}")
    digest = hashlib.sha256()
    digest.update(archive)
    actual = digest.hexdigest()
    if actual != expected:
        raise ValueError(
            f"publisher checksum mismatch for {asset}: "
            f"expected {expected}, got {actual}"
        )
    return expected


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
    digest = verified_asset_digest(version, asset)
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
    replace_files_atomically({
        MANIFEST: (json.dumps(payload, indent=2) + "\n").encode(),
        WORKFLOW: workflow.encode(),
    })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    update(parser.parse_args().version)


if __name__ == "__main__":
    main()
