"""Completeness and policy tests for the NZ asset disposition inventory."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = (
    PROJECT_ROOT
    / "conductor/tracks/nzmedicines_migration_20260727/nz-asset-inventory.json"
)
UPSTREAM_ROOT = PROJECT_ROOT / "vendor/nzmedicines"
ALLOWED_DISPOSITIONS = {"adopted", "adapted", "superseded", "fixture", "excluded"}


def load_inventory() -> dict[str, object]:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def test_every_upstream_file_has_exactly_one_disposition_and_digest() -> None:
    inventory = load_inventory()
    rows = [
        row
        for row in inventory["assets"]
        if isinstance(row, dict) and row["scope"] == "upstream"
    ]
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
    assert all(len(row["sha256"]) == 64 for row in rows)
    assert all(
        row["upstream_commit"] == "6a8ecfae67f15d635750d11d5f446b93d76c1865"
        for row in rows
    )


def test_every_inventory_row_has_a_reviewable_rationale_and_boundary() -> None:
    inventory = load_inventory()
    rows = inventory["assets"]

    assert inventory["schema_version"] == 1
    assert inventory["asset_count"] == len(rows)
    assert len({row["path"] for row in rows}) == len(rows)
    assert all(row["disposition"] in ALLOWED_DISPOSITIONS for row in rows)
    assert all(row["family"] for row in rows)
    assert all(row["rights_boundary"] for row in rows)
    assert all(row["rationale"] for row in rows)
    assert all(row["conflict"] for row in rows)
    assert all(row["local_enhancement"] for row in rows)


def test_source_payloads_are_not_classified_for_unreviewed_publication() -> None:
    inventory = load_inventory()
    payload_rows = [
        row
        for row in inventory["assets"]
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
        row["rights_boundary"] == "local-only-review-required" for row in payload_rows
    )
