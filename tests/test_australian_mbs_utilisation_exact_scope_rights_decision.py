"""The MBS-utilisation rights approval is exact-scope and fail-closed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DECISION_PATH = (
    "quality/qualifications/"
    "australian-mbs-utilisation-exact-scope-rights-decision-20261004.json"
)
REGISTER_PATH = (
    "quality/qualifications/"
    "australian-m112-additional-deferred-source-candidates-20261004.json"
)
RECONCILIATION_PATH = (
    "quality/qualifications/"
    "australian-m112-utilisation-rights-reconciliation-20261004.json"
)
JOIN_PATH = (
    "quality/qualifications/"
    "australian-m112-receipt-sidecar-join-audit-20260930.json"
)


def _read(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_rights_decision_binds_all_and_only_the_14_joined_objects() -> None:
    decision = _read(DECISION_PATH)
    register = _read(REGISTER_PATH)
    joins = _read(JOIN_PATH)
    dataset = next(
        row
        for row in joins["datasets"]
        if row["dataset"] == decision["scope"]["dataset"]
    )
    objects = dataset["joined_objects"]

    assert decision["decision_authority"] == "sole maintainer"
    assert decision["scope"]["revision"] == dataset["revision"]
    assert decision["scope"]["manifest_sha256"] == dataset["manifest_sha256"]
    assert decision["scope"]["candidate_paths"] == len(objects) == 14
    assert decision["scope"]["source_id_counts"] == dataset["source_id_counts"]
    assert set(decision["scope"]["authorization_allowed_source_ids"]) == {
        "au-data-gov-mbs-demographics",
        "au-data-gov-mbs-group",
        "au-health-medicare-statistics",
    }
    assert decision["scope"][
        "authorized_source_ids_without_objects_in_scope"
    ] == ["au-health-medicare-statistics"]
    assert all(
        item["authorization_scope_match"]
        and item["path_matches_manifest"]
        and item["source_id_matches_manifest"]
        and item["category_matches_manifest"]
        and item["sha256_matches_manifest"]
        and item["byte_count_matches_manifest"]
        for item in objects
    )
    assert all(not item["rights_state_field_present"] for item in objects)

    sources = {item["source_id"] for item in objects}
    evidence_sources = {
        item["source_id"]
        for item in decision["official_evidence"]
        if "source_id" in item
    }
    assert evidence_sources == sources
    assert all(
        item["license"] == "Creative Commons Attribution 3.0 Australia"
        and item["metadata_response_sha256"]
        for item in decision["official_evidence"]
        if "source_id" in item
    )
    assert decision["disposition"]["redistribute"] == "permitted"
    assert decision["separate_open_gates"]["v4_admission"] is False
    assert decision["separate_open_gates"]["m112_federation_accepted"] is False
    assert (
        decision["separate_open_gates"][
            "approved_candidate_denominator_changed"
        ]
        is False
    )

    group = next(
        row
        for row in register["additional_deferred_sources"]
        if row["group_id"] == "au-mbs-utilisation-rights-ledger"
    )
    assert group["candidate_paths"] == 14
    reconciliation = _read(RECONCILIATION_PATH)
    assert reconciliation["supersedes"]["path"] == REGISTER_PATH
    assert (
        reconciliation["supersedes"]["sha256"]
        == hashlib.sha256((ROOT / REGISTER_PATH).read_bytes()).hexdigest()
    )
    assert reconciliation["rights_decision"]["path"] == DECISION_PATH
    assert (
        reconciliation["rights_decision"]["sha256"]
        == hashlib.sha256((ROOT / DECISION_PATH).read_bytes()).hexdigest()
    )
    disposition = reconciliation["current_disposition"]
    assert disposition["candidate_paths"] == 14
    assert disposition["rights_state"].startswith("maintainer-approved")
    assert "B1_B2_lineage" in disposition["lineage_state"]
    assert disposition["v4_admission"] is False
    assert disposition["consumer_canaries"] is False
    assert disposition["m112_federation_accepted"] is False
    assert disposition["candidate_denominator_changed"] is False
