"""Verify the exact M-112 raw-object joins recovered from retained evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from scripts.reconcile_m112_retained_evidence_joins import (
    OUTPUT,
    ROOT,
    build_report,
)


def test_retained_evidence_adds_four_exact_current_revision_joins() -> None:
    report = build_report()
    increment = report["retained_evidence_join_increment"]

    assert report["scope"]["approved_denominator"] == 1759
    assert report["scope"]["approved_raw_paths"] == 1736
    assert report["scope"]["approved_projection_paths"] == 23
    assert increment["prior_raw_digest_path_joins"] == 22
    assert increment["new_exact_raw_digest_path_matches"] == 4
    assert increment["new_exact_b1_b2_receipt_joins"] == 4
    assert increment["cumulative_exact_raw_digest_path_joins"] == 26
    assert increment["raw_paths_outside_digest_join_subset"] == 1710
    assert increment["prior_complete_b1_b2_lineage_paths"] == 2
    assert increment["new_complete_b1_b2_lineage_paths"] == 4
    assert increment["cumulative_complete_b1_b2_lineage_paths"] == 6
    assert increment["existing_same_content_alias_path_bindings"] == 1
    assert increment["cumulative_raw_path_identity_bindings"] == 27
    assert increment["candidate_path_disposition"] == {
        "verified_new_join": 4,
        "already_joined_canonical": 1,
        "same_content_alias_already_bound": 1,
        "unmatched": 0,
        "incompatible_role": 0,
    }
    assert [row["status"] for row in increment["candidate_path_results"]].count(
        "verified_new_b1_b2_receipt_join"
    ) == 4
    assert [row["status"] for row in increment["candidate_path_results"]].count(
        "preexisting_same_content_alias"
    ) == 1
    assert increment["unmatched_records"] == []
    assert increment["incompatible_role_records"] == []

    joins = increment["new_joins"]
    assert len(joins) == 4
    assert {join["dataset_revision"] for join in joins} == {
        "40891976f77ee5e7688edceed25c9ac98a77547e"
    }
    assert all(join["same_path_byte_count_and_sha256"] for join in joins)
    assert all(join["all_b1_b2_roles_match"] for join in joins)
    assert all(join["preserved_denominator_member"] for join in joins)
    july_rows = [
        row
        for row in report["objects"]
        if row["path"].startswith("raw/mbs/")
        and "Downloads-20260701" in row["path"]
    ]
    assert len(july_rows) == 4
    assert all(
        "exact per-object authorization and reuse disposition remain unresolved"
        in row["rights"]["state"]
        and "B1 binding incomplete" not in row["rights"]["state"]
        for row in july_rows
    )


def test_join_increment_preserves_inventory_ids_and_separate_gates() -> None:
    report = build_report()
    increment = report["retained_evidence_join_increment"]
    gates = report["updated_gate_totals"]
    baseline = json.loads(
        (
            ROOT
            / "quality/qualifications/australian-m112-per-object-gate-reconciliation-20261018.json"
        ).read_text(encoding="utf-8")
    )
    frozen_inventory = json.loads(
        (
            ROOT
            / "quality/qualifications/australian-m112-frozen-object-inventory-20261018.json"
        ).read_text(encoding="utf-8")
    )

    updated_by_key = {
        (row["dataset"], row["revision"], row["path"]): row
        for row in report["objects"]
    }
    baseline_by_key = {
        (row["dataset"], row["revision"], row["path"]): row
        for row in baseline["objects"]
    }
    changed_keys = {
        key
        for key in baseline_by_key
        if baseline_by_key[key] != updated_by_key[key]
    }
    expected_changed_keys = {
        (join["dataset"], join["dataset_revision"], join["path"])
        for join in increment["new_joins"]
    }

    assert increment["denominator_object_count"] == 1759
    assert (
        increment["approved_path_membership_sha256"]
        == frozen_inventory["scope"]["path_membership_sha256"]
    )
    assert set(updated_by_key) == set(baseline_by_key)
    assert changed_keys == expected_changed_keys
    assert len(increment["denominator_object_id_sha256"]) == 64
    assert gates["complete_raw_b1_b2_lineage"] == 6
    assert gates["exact_raw_digest_path_joins"] == 26
    assert gates["complete_raw_b1_b2_lineage_paths"] == 6
    assert gates["v4_admissions"] == 0
    assert gates["consumer_canaries"] == 0
    assert gates["raw_paths_without_direct_or_alias_sha256"] == 92
    assert gates["projection_paths_without_direct_or_alias_sha256"] == 12
    assert report["boundaries"]["rights_or_licensing_conclusion_added"] is False
    assert report["boundaries"]["source_payload_bytes_read_this_run"] is False


def test_join_increment_inputs_are_digest_bound_and_output_is_reproducible() -> (
    None
):
    report = build_report()
    for item in report["evidence_inputs"]:
        content = (ROOT / item["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == item["sha256"]

    if OUTPUT.exists():
        observed: Any = json.loads(OUTPUT.read_text(encoding="utf-8"))
        assert observed == report
