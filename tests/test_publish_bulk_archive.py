"""Fail-closed boundaries for bulk archive publication."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts import publish_bulk_archive as publisher

from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main as real_require_hosted_main,
)

COMMIT = "a" * 40


def write_contract(tmp_path: Path, **overrides: object) -> Path:
    """Create a contract in the committed source-batch shape."""
    batch = tmp_path / "quality/source-batches/synthetic"
    batch.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "batch_id": "synthetic",
        "repository": "owner/synthetic",
        "publication_approved": True,
        "approval_reference": "Synthetic maintainer approval.",
        "snapshot_id": "synthetic-snapshot",
        "source_authority": "Synthetic authority",
        "source_url": "https://example.gov/data",
        "retrieval_date": "2026-01-01",
        "schema_version": "synthetic/v1",
        "pretty_name": "Synthetic archive",
        "description": "Synthetic description.",
        "fields_and_transformations": "Unmodified synthetic source bytes.",
        "payload_suffix": ".bin",
        "expected_payload_count": 2,
        "expected_payload_bytes": 6,
        "rights": {
            "licence": "Synthetic public domain",
            "terms": "https://example.gov/terms",
            "attribution": "Synthetic authority, https://example.gov/data",
            "redistribution": "Permitted for unmodified source bytes.",
        },
        "not_included": ["No derived tables."],
    }
    manifest.update(overrides)
    path = batch / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def write_archive(tmp_path: Path) -> Path:
    """Create a two-payload archive matching the default contract."""
    root = tmp_path / "archive"
    (root / "group").mkdir(parents=True)
    (root / "group" / "first.bin").write_bytes(b"abc")
    (root / "second.bin").write_bytes(b"def")
    return root


@pytest.fixture(autouse=True)
def committed_batches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        publisher, "BATCHES", tmp_path / "quality/source-batches"
    )
    monkeypatch.setattr(publisher, "require_hosted_main", lambda _c: None)


def test_local_invocation_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        publisher, "require_hosted_main", real_require_hosted_main
    )
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    manifest = write_contract(tmp_path)
    with pytest.raises(ValueError, match="Actions dispatch on main"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_unapproved_contract_is_refused(tmp_path: Path) -> None:
    manifest = write_contract(tmp_path, publication_approved=False)
    with pytest.raises(ValueError, match="not approved"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_manifest_outside_source_batches_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    manifest = outside / "manifest.json"
    manifest.write_text(json.dumps({"publication_approved": True}))
    with pytest.raises(ValueError, match="committed source-batch"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_payload_count_drift_is_refused(tmp_path: Path) -> None:
    manifest = write_contract(tmp_path, expected_payload_count=3)
    with pytest.raises(ValueError, match="payload count differs"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_payload_byte_drift_is_refused(tmp_path: Path) -> None:
    manifest = write_contract(tmp_path, expected_payload_bytes=7)
    with pytest.raises(ValueError, match="payload bytes differ"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_recorded_digest_mismatch_is_refused(tmp_path: Path) -> None:
    manifest = write_contract(
        tmp_path,
        recorded_payload_digests={"second.bin": "0" * 64},
    )
    with pytest.raises(ValueError, match="recorded payload digest differs"):
        publisher.publish_bulk_archive(
            manifest, write_archive(tmp_path), tmp_path / "out", COMMIT
        )


def test_prepare_binds_every_file_without_upload(tmp_path: Path) -> None:
    archive = write_archive(tmp_path)
    output = tmp_path / "out"
    assert (
        publisher.publish_bulk_archive(
            write_contract(tmp_path), archive, output, COMMIT
        )
        == 0
    )
    plan = json.loads(
        (output / "publication-receipts" / "plan.json").read_text()
    )
    bound = [item["relative_path"] for item in plan["artifacts"]]
    assert bound == sorted(
        str(path.relative_to(archive))
        for path in archive.rglob("*")
        if path.is_file()
    )
    assert plan["target"]["repository"] == "owner/synthetic"
    assert "ARTIFACT-MANIFEST.json" in bound


def test_card_records_rights_and_scope(tmp_path: Path) -> None:
    archive = write_archive(tmp_path)
    publisher.publish_bulk_archive(
        write_contract(tmp_path), archive, tmp_path / "out", COMMIT
    )
    card = (archive / "README.md").read_text()
    assert "Synthetic authority" in card
    assert "Permitted for unmodified source bytes." in card
    assert "## What this archive is not" in card
    assert "- No derived tables." in card


def test_publish_refuses_without_external_write_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GMA_PUBLICATION_ENVIRONMENT", raising=False)
    monkeypatch.delenv("GMA_MAINTAINER_PUBLICATION_APPROVED", raising=False)
    with pytest.raises(PermissionError, match="explicit maintainer approval"):
        publisher.publish_bulk_archive(
            write_contract(tmp_path),
            write_archive(tmp_path),
            tmp_path / "out",
            COMMIT,
            publish=True,
        )
