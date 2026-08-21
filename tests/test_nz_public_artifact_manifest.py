"""Tests for the approved fail-closed NZ public artifact manifest."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.build_nz_public_artifact_manifest import build_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ROOT / "quality/qualifications/nz-public-artifact-manifest-20260821.json"
)


@pytest.mark.unit
def test_nz_public_manifest_regenerates_exactly() -> None:
    assert json.loads(MANIFEST.read_text(encoding="utf-8")) == build_manifest()


@pytest.mark.unit
def test_nz_public_manifest_excludes_restricted_families() -> None:
    manifest = build_manifest()
    paths = {item["path"] for item in manifest["approved_files"]}

    assert paths
    assert not any(path.startswith("vendor/nzmedicines/") for path in paths)
    assert manifest["restricted_source_bytes_included"] is False
    assert manifest["derived_restricted_fields_included"] is False
    assert manifest["preserved_bundle"]["included"] is False
    assert manifest["coverage_complete"] is False
    assert manifest["clinical_inference_permitted"] is False


@pytest.mark.unit
def test_nz_public_manifest_is_exact_and_hash_bound() -> None:
    manifest = build_manifest()
    files = manifest["approved_files"]

    assert manifest["approved_file_count"] == len(files) == 15
    assert all(len(item["sha256"]) == 64 for item in files)
    assert all(item["size_bytes"] > 0 for item in files)
    assert len({item["path"] for item in files}) == len(files)
