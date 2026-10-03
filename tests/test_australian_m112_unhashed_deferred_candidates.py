"""Contract tests for the path-level M-112 future-source digest register."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTER = (
    ROOT
    / "quality/qualifications/"
    / "australian-m112-unhashed-deferred-candidates-20261004.json"
)


def _read(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_unhashed_future_source_register_is_exact_and_fail_closed() -> None:
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    inventory_ref = register["candidate_inventory"]
    inventory_path = ROOT / inventory_ref["path"]
    inventory_bytes = inventory_path.read_bytes()
    assert (
        hashlib.sha256(inventory_bytes).hexdigest() == inventory_ref["sha256"]
    )
    inventory = json.loads(inventory_bytes)

    deferred = _read(
        "quality/qualifications/australian-m112-deferred-source-candidates-20261004.json"
    )
    source = deferred["deferred_sources"][0]
    assert register["scope"] == {
        "approved_candidate_denominator": 1_759,
        "paths_without_direct_sha256_metadata": 104,
        "raw_source_payloads": 92,
        "existing_data_projections": 12,
        "denominator_changed": False,
        "admission_status": "deferred_not_admitted",
    }
    assert register["source_dataset"] == source["dataset"]
    assert register["source_revision"] == source["current_revision"]
    assert source["rights_status"] == source["lineage_status"] == "unresolved"
    assert register["reentry_trigger"] == source["reentry_trigger"]

    expected = [
        row
        for row in inventory["observations"]
        if row["dataset"] == source["dataset"]
        and row["revision"] == source["current_revision"]
        and not row["has_lfs_sha256"]
    ]
    candidates = register["deferred_candidates"]
    assert len(expected) == len(candidates) == 104
    assert {row["path"] for row in candidates} == {
        row["path"] for row in expected
    }
    assert len({row["path"] for row in candidates}) == 104
    for row in candidates:
        observed = next(
            item for item in expected if item["path"] == row["path"]
        )
        assert row == {
            "path": observed["path"],
            "candidate_class": observed["candidate_class"],
            "revision": observed["revision"],
            "git_blob_oid": observed["observed_git_blob_oid"],
            "byte_count": observed["observed_bytes"],
            "direct_sha256_metadata": None,
            "admission_status": "deferred_not_admitted",
        }
        assert row["direct_sha256_metadata"] is None

    assert (
        sum(
            row["candidate_class"] == "raw_source_payload" for row in candidates
        )
        == 92
    )
    assert (
        sum(
            row["candidate_class"] == "existing_data_projection"
            for row in candidates
        )
        == 12
    )
    assert register["boundaries"] == {
        "payload_bytes_read": False,
        "payload_values_read": False,
        "new_rights_or_licensing_conclusion": False,
        "approved_denominator_changed": False,
        "v4_admission_performed": False,
        "consumer_canaries_performed": False,
        "m112_federation_accepted": False,
    }
