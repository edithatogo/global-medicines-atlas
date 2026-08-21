"""Exact-manifest FDA public archive tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from global_medicines_atlas.fda_public_archive import (
    FDA_SOURCE_IDS,
    build_fda_public_archive,
)


def _corpus(root: Path) -> Path:
    downloads = root / "downloads"
    evidence = root / "evidence"
    downloads.mkdir(parents=True)
    evidence.mkdir()
    receipts: list[dict[str, str]] = []
    for index, source_id in enumerate(sorted(FDA_SOURCE_IDS)):
        payload = f"official-{source_id}".encode()
        (downloads / f"{source_id}.json").write_bytes(payload)
        receipts.append({
            "source_id": source_id,
            "payload_sha256": hashlib.sha256(payload).hexdigest(),
            "admission_state": "quarantined" if index == 0 else "accepted",
        })
    (evidence / "redacted-acquisition-results.json").write_text(
        json.dumps(receipts), encoding="utf-8"
    )
    return root


def test_builds_exact_receipt_bound_archive(tmp_path: Path) -> None:
    output = tmp_path / "public"
    manifest = build_fda_public_archive(_corpus(tmp_path / "corpus"), output)
    assert manifest.source_count == 13
    assert {entry.source_id for entry in manifest.entries} == FDA_SOURCE_IDS
    assert sum(entry.projection_permitted for entry in manifest.entries) == 12
    assert "re-identification" in (output / "README.md").read_text()
    assert not (
        output / "evidence/us-live-acquisition-authorization.json"
    ).exists()


def test_rejects_digest_mismatch(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path / "corpus")
    next((corpus / "downloads").iterdir()).write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest mismatch"):
        build_fda_public_archive(corpus, tmp_path / "public")
