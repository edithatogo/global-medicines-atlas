"""Exact-manifest FDA public archive tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from global_medicines_atlas.fda_public_archive import (
    FDA_SOURCE_IDS,
    FdaPublicationCandidateManifest,
    build_fda_publication_candidate,
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
    manifest = build_fda_publication_candidate(
        _corpus(tmp_path / "corpus"), output
    )
    assert manifest.source_count == 13
    assert {entry.source_id for entry in manifest.entries} == FDA_SOURCE_IDS
    assert sum(entry.projection_permitted for entry in manifest.entries) == 12
    assert manifest.publication_approved is False
    assert "re-identification" in (output / "README.md").read_text()
    assert not (
        output / "evidence/us-live-acquisition-authorization.json"
    ).exists()


def test_rejects_digest_mismatch(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path / "corpus")
    next((corpus / "downloads").iterdir()).write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest mismatch"):
        build_fda_publication_candidate(corpus, tmp_path / "public")


def test_candidate_cannot_encode_publication_approval(tmp_path: Path) -> None:
    manifest = build_fda_publication_candidate(
        _corpus(tmp_path / "corpus"), tmp_path / "candidate"
    )
    with pytest.raises(ValueError, match="cannot encode publication approval"):
        FdaPublicationCandidateManifest.model_validate({
            **manifest.model_dump(),
            "publication_approved": True,
        })


def test_manifest_rejects_incomplete_or_duplicate_source_sets(
    tmp_path: Path,
) -> None:
    manifest = build_fda_publication_candidate(
        _corpus(tmp_path / "corpus"), tmp_path / "candidate"
    )
    raw = manifest.model_dump()
    with pytest.raises(ValueError, match="every proposed source"):
        FdaPublicationCandidateManifest.model_validate({
            **raw,
            "entries": raw["entries"][:-1],
        })
    with pytest.raises(ValueError, match="source IDs must be unique"):
        FdaPublicationCandidateManifest.model_validate({
            **raw,
            "entries": [*raw["entries"], raw["entries"][0]],
        })


def test_builder_rejects_incomplete_receipts_payloads_and_existing_output(
    tmp_path: Path,
) -> None:
    corpus = _corpus(tmp_path / "corpus")
    receipts_path = corpus / "evidence/redacted-acquisition-results.json"
    receipts = json.loads(receipts_path.read_text(encoding="utf-8"))
    receipts_path.write_text(json.dumps(receipts[:-1]), encoding="utf-8")
    with pytest.raises(ValueError, match="exact FDA source set"):
        build_fda_publication_candidate(corpus, tmp_path / "candidate")

    corpus = _corpus(tmp_path / "second-corpus")
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(FileExistsError):
        build_fda_publication_candidate(corpus, existing)

    next((corpus / "downloads").iterdir()).unlink()
    with pytest.raises(ValueError, match="expected one payload"):
        build_fda_publication_candidate(corpus, tmp_path / "missing")
