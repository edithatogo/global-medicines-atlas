"""Completeness and policy tests for the NZ asset disposition inventory."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from scripts import generate_nz_asset_inventory as generator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = (
    PROJECT_ROOT
    / "conductor/archive/nzmedicines_migration_20260727/nz-asset-inventory.json"
)
UPSTREAM_ROOT = PROJECT_ROOT / "vendor/nzmedicines"
ALLOWED_DISPOSITIONS = {
    "adopted",
    "adapted",
    "superseded",
    "fixture",
    "excluded",
}


def load_inventory() -> dict[str, Any]:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def load_assets() -> list[dict[str, object]]:
    return cast(
        "list[dict[str, object]]",
        load_inventory()["assets"],
    )


def bind_test_preservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inventory: dict[str, object],
) -> None:
    manifest = generator.upstream_manifest(inventory)
    tree_digest = generator.aggregate_manifest_digest(manifest)
    preservation_path = tmp_path / "preservation.json"
    preservation_path.write_text(
        json.dumps({
            "source_commit": generator.UPSTREAM_COMMIT,
            "upstream_asset_count": len(manifest),
            "upstream_tree_sha256": tree_digest,
            "bundle_size_bytes": 1,
            "bundle_sha256": "f" * 64,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        generator,
        "PRESERVATION_MANIFEST",
        preservation_path,
    )
    monkeypatch.setattr(
        generator,
        "EXPECTED_UPSTREAM_TREE_DIGEST",
        tree_digest,
    )
    monkeypatch.setattr(
        generator,
        "EXPECTED_BUNDLE_DIGEST",
        "f" * 64,
    )


def test_every_upstream_file_has_exactly_one_disposition_and_digest() -> None:
    inventory = load_inventory()
    rows = [row for row in load_assets() if row["scope"] == "upstream"]
    expected = {
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in UPSTREAM_ROOT.rglob("*")
        if path.is_file()
    }

    assert inventory["upstream_asset_count"] == 25
    assert len(rows) == len(expected)
    assert {row["path"] for row in rows} == expected
    assert len({row["path"] for row in rows}) == len(rows)
    assert all(row["disposition"] in ALLOWED_DISPOSITIONS for row in rows)
    assert all(
        isinstance(row["sha256"], str) and len(row["sha256"]) == 64
        for row in rows
    )
    assert all(
        row["upstream_commit"] == "6a8ecfae67f15d635750d11d5f446b93d76c1865"
        for row in rows
    )


def test_every_inventory_row_has_a_reviewable_rationale_and_boundary() -> None:
    inventory = load_inventory()
    rows = load_assets()

    assert inventory["schema_version"] == 1
    assert inventory["asset_count"] == len(rows)
    assert len({row["path"] for row in rows}) == len(rows)
    assert all(row["disposition"] in ALLOWED_DISPOSITIONS for row in rows)
    assert all(row["family"] for row in rows)
    assert all(row["rights_boundary"] for row in rows)
    assert all(row["rationale"] for row in rows)
    assert all(row["conflict"] for row in rows)
    assert all(row["local_enhancement"] for row in rows)


def test_source_payloads_are_not_classified_for_unreviewed_publication() -> (
    None
):
    payload_rows = [
        row
        for row in load_assets()
        if row["family"]
        in {
            "medsafe_regulatory_source",
            "funding_formulary_source",
            "nzmt_hierarchy_source",
            "terminology_mapping_source",
            "nzmt_supporting_source",
        }
    ]

    assert payload_rows
    assert all(
        row["rights_boundary"] == "local-only-review-required"
        for row in payload_rows
    )


def test_portable_check_succeeds_without_local_only_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["generate_nz_asset_inventory.py", "--check"]
    )

    generator.main()


def test_upstream_tree_manifest_verifies_exact_snapshot() -> None:
    generator.verify_upstream_tree(load_inventory())


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "missing="),
        ("extra", "extra="),
        ("modified", "size differs"),
    ],
)
def test_upstream_tree_manifest_rejects_tree_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    upstream_root = tmp_path / "vendor/nzmedicines"
    upstream_root.mkdir(parents=True)
    fixture = upstream_root / "readme.md"
    fixture.write_text("preserved\n", encoding="utf-8")
    monkeypatch.setattr(generator, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(generator, "UPSTREAM_ROOT", upstream_root)
    inventory: dict[str, object] = {
        "upstream_asset_count": 1,
        "assets": [
            {
                "path": "vendor/nzmedicines/readme.md",
                "scope": "upstream",
                "size_bytes": fixture.stat().st_size,
                "sha256": generator.sha256(fixture),
                "upstream_commit": generator.UPSTREAM_COMMIT,
                "disposition": "adapted",
            }
        ],
    }
    bind_test_preservation(tmp_path, monkeypatch, inventory)

    if mutation == "missing":
        fixture.unlink()
    elif mutation == "extra":
        (upstream_root / "unexpected.json").write_text("{}", encoding="utf-8")
    else:
        fixture.write_text("modified content\n", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        generator.verify_upstream_tree(inventory)


def test_upstream_tree_manifest_rejects_digest_modification_with_same_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_root = tmp_path / "vendor/nzmedicines"
    upstream_root.mkdir(parents=True)
    fixture = upstream_root / "readme.md"
    fixture.write_bytes(b"original")
    monkeypatch.setattr(generator, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(generator, "UPSTREAM_ROOT", upstream_root)
    inventory: dict[str, object] = {
        "upstream_asset_count": 1,
        "assets": [
            {
                "path": "vendor/nzmedicines/readme.md",
                "scope": "upstream",
                "size_bytes": 8,
                "sha256": generator.sha256(fixture),
                "upstream_commit": generator.UPSTREAM_COMMIT,
                "disposition": "adapted",
            }
        ],
    }
    bind_test_preservation(tmp_path, monkeypatch, inventory)
    fixture.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="SHA-256 differs"):
        generator.verify_upstream_tree(inventory)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate", "Duplicate upstream manifest path"),
        ("commit", "Unexpected source commit"),
        ("disposition", "missing: disposition"),
    ],
)
def test_upstream_tree_manifest_rejects_invalid_manifest_rows(
    mutation: str,
    message: str,
) -> None:
    row = {
        "path": "vendor/nzmedicines/readme.md",
        "scope": "upstream",
        "size_bytes": 1,
        "sha256": "0" * 64,
        "upstream_commit": generator.UPSTREAM_COMMIT,
        "disposition": "adapted",
    }
    rows = [row]
    if mutation == "duplicate":
        rows.append(dict(row))
    elif mutation == "commit":
        row["upstream_commit"] = "wrong"
    else:
        row["disposition"] = ""

    with pytest.raises(ValueError, match=message):
        generator.upstream_manifest({
            "upstream_asset_count": len(rows),
            "assets": rows,
        })


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("size_bytes", True, TypeError),
        ("size_bytes", "1", TypeError),
        ("size_bytes", -1, TypeError),
        ("sha256", "not-a-digest", ValueError),
        ("sha256", "A" * 64, ValueError),
        ("upstream_asset_count", True, TypeError),
        ("upstream_asset_count", "1", TypeError),
    ],
)
def test_upstream_manifest_rejects_invalid_numeric_and_digest_types(
    field: str,
    value: object,
    error: type[Exception],
) -> None:
    row: dict[str, object] = {
        "path": "vendor/nzmedicines/readme.md",
        "scope": "upstream",
        "size_bytes": 1,
        "sha256": "0" * 64,
        "upstream_commit": generator.UPSTREAM_COMMIT,
        "disposition": "adapted",
    }
    inventory: dict[str, object] = {
        "upstream_asset_count": 1,
        "assets": [row],
    }
    target = inventory if field == "upstream_asset_count" else row
    target[field] = value

    with pytest.raises(error):
        generator.upstream_manifest(inventory)


def test_adjacent_inventory_and_vendor_tampering_cannot_reanchor_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_root = tmp_path / "vendor/nzmedicines"
    upstream_root.mkdir(parents=True)
    fixture = upstream_root / "readme.md"
    fixture.write_bytes(b"tampered")
    monkeypatch.setattr(generator, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(generator, "UPSTREAM_ROOT", upstream_root)
    inventory: dict[str, object] = {
        "upstream_asset_count": 1,
        "assets": [
            {
                "path": "vendor/nzmedicines/readme.md",
                "scope": "upstream",
                "size_bytes": fixture.stat().st_size,
                "sha256": generator.sha256(fixture),
                "upstream_commit": generator.UPSTREAM_COMMIT,
                "disposition": "adapted",
            }
        ],
    }
    preservation = json.loads(
        generator.PRESERVATION_MANIFEST.read_text(encoding="utf-8")
    )
    preservation["upstream_asset_count"] = 1
    preservation_path = tmp_path / "preservation.json"
    preservation_path.write_text(
        json.dumps(preservation),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        generator,
        "PRESERVATION_MANIFEST",
        preservation_path,
    )

    with pytest.raises(ValueError, match="aggregate tree digest differs"):
        generator.verify_upstream_tree(inventory)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("upstream_asset_count", True, TypeError),
        ("upstream_asset_count", "25", TypeError),
        ("bundle_size_bytes", True, TypeError),
        ("bundle_size_bytes", "37832", TypeError),
        ("upstream_tree_sha256", "not-a-digest", ValueError),
        ("bundle_sha256", "A" * 64, ValueError),
    ],
)
def test_preservation_manifest_rejects_invalid_types(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    error: type[Exception],
) -> None:
    inventory = load_inventory()
    manifest = generator.upstream_manifest(inventory)
    preservation = json.loads(
        generator.PRESERVATION_MANIFEST.read_text(encoding="utf-8")
    )
    preservation[field] = value
    preservation_path = tmp_path / "preservation.json"
    preservation_path.write_text(
        json.dumps(preservation),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        generator,
        "PRESERVATION_MANIFEST",
        preservation_path,
    )

    with pytest.raises(error):
        generator.verify_preservation_identity(manifest)
