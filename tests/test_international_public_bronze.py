"""Qualification tests for the approved international public archive."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest
from scripts.qualify_international_public_bronze import (
    qualification_summary,
    qualify,
)

from global_medicines_atlas.international_public_archive import SOURCE_RIGHTS


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _archive(root: Path) -> tuple[Path, Path]:
    files: list[dict[str, object]] = []
    for source_id, rights in sorted(SOURCE_RIGHTS.items()):
        if source_id in {"global-rxnorm", "us-rxnorm-api"}:
            name = "rxcui-identifiers.json"
            payload = b'["1", "2"]\n'
        elif source_id == "eu-union-register":
            name = "ods_products.json"
            payload = b'{"data":[{"URI":"urn:example:1","name":"one"}]}\n'
        elif source_id == "fr-bdpm":
            name = "source.txt"
            payload = b"label;value\ncaf\xe9;1\n"
        else:
            name = "source.bin"
            payload = f"{source_id}\n".encode()
        path = root / "data" / source_id / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        files.append({
            "source_id": source_id,
            "path": path.relative_to(root).as_posix(),
            "sha256": _digest(path),
            "byte_count": len(payload),
            "rights": rights,
        })
    manifest = {
        "schema_id": "global-medicines-atlas.international-public-archive",
        "schema_version": 1,
        "archived_source_count": 10,
        "files": files,
        "pending_sources": {
            "fr-open-medic": "published separately",
            "gb-nice-medicines-utilisation": "not included",
            "nl-gipdatabank": "not included",
        },
        "rxnorm_input_sha256": "4" * 64,
        "coverage_complete": False,
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    publication = {
        "dataset": (
            "edithatogo/"
            "global-medicines-atlas-international-permissive-20260821"
        ),
        "immutable_revision": ("e6aa97ffe46eb32a41d7c73550fbd52811a9701b"),
        "manifest_sha256": _digest(manifest_path),
        "archived_source_count": 10,
        "source_ids": sorted(SOURCE_RIGHTS),
        "file_count": len(files),
        "repository_private": False,
        "repository_gated": False,
    }
    publication_path = root / "publication.json"
    publication_path.write_text(json.dumps(publication), encoding="utf-8")
    return root, publication_path


def test_qualifies_source_native_files_and_excludes_derived_rxnorm(
    tmp_path: Path,
) -> None:
    archive, publication = _archive(tmp_path / "archive")
    result = qualify(
        archive,
        tmp_path / "qualification",
        publication_receipt_path=publication,
    )

    assert result["public_manifest_files_verified"] == 10
    assert result["source_native_file_count"] == 8
    assert result["accepted_admission_count"] == 7
    assert result["quarantined_admission_count"] == 1
    assert result["recovered_acquisition_count"] == 7
    assert result["incomplete_quarantined_recovery_count"] == 1
    assert result["partially_quarantined_source_ids"] == ["fr-bdpm"]
    assert len(result["fully_accepted_source_ids"]) == 7
    assert result["source_record_projection_count"] == 1
    assert result["source_record_parquet_pairs_byte_identical"] == 1
    assert result["derived_only_source_ids"] == [
        "global-rxnorm",
        "us-rxnorm-api",
    ]
    assert result["derived_only_files_landed_as_live"] == 0
    assert any(
        item["path"].endswith("source.txt")
        and item["landing_media_hint"] == "bin"
        and item["admission"] == "quarantined"
        and item["document_manifest"] is None
        for item in result["items"]
    )
    assert result["coverage_complete"] is False
    assert result["external_publication_performed"] is False
    assert result["reuse_revision"] == (
        "e6aa97ffe46eb32a41d7c73550fbd52811a9701b"
    )
    summary = qualification_summary(result)
    assert "items" not in summary
    assert "derived_items" not in summary
    assert summary["source_native_payload_byte_count"] > 0


def test_rejects_public_manifest_tampering(tmp_path: Path) -> None:
    archive, publication = _archive(tmp_path / "archive")
    payload = next((archive / "data").rglob("source.bin"))
    payload.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="archive file drifted"):
        qualify(
            archive,
            tmp_path / "qualification",
            publication_receipt_path=publication,
        )


def test_rejects_publication_identity_drift(tmp_path: Path) -> None:
    archive, publication = _archive(tmp_path / "archive")
    document = json.loads(publication.read_text())
    document["immutable_revision"] = "0" * 40
    publication.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="publication identity drifted"):
        qualify(
            archive,
            tmp_path / "qualification",
            publication_receipt_path=publication,
        )
