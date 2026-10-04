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


def test_prepared_object_rights_records_preserve_receipts_and_exact_scope() -> (
    None
):
    path = (
        "quality/qualifications/"
        "australian-mbs-utilisation-object-rights-metadata-20261004.json"
    )
    prepared = _read(path)
    decision = _read(DECISION_PATH)
    dataset = next(
        row
        for row in _read(JOIN_PATH)["datasets"]
        if row["dataset"] == decision["scope"]["dataset"]
    )
    for reference, source in [
        ("rights_decision", DECISION_PATH),
        ("receipt_join_audit", JOIN_PATH),
    ]:
        assert prepared[reference]["path"] == source
        assert (
            prepared[reference]["sha256"]
            == hashlib.sha256((ROOT / source).read_bytes()).hexdigest()
        )
    assert prepared["dataset"] == dataset["dataset"]
    assert prepared["source_revision"] == dataset["revision"]
    assert prepared["manifest_sha256"] == dataset["manifest_sha256"]
    records = prepared["records"]
    assert len(records) == len({row["path"] for row in records}) == 14
    assert {row["path"] for row in records} == {
        row["path"] for row in dataset["joined_objects"]
    }
    expected = {row["path"]: row for row in dataset["joined_objects"]}
    for row in records:
        original = expected[row["path"]]
        for field in (
            "source_id",
            "category",
            "sha256",
            "byte_count",
            "receipt_path",
            "receipt_sha256",
        ):
            assert row[field] == original[field]
        assert row["rights_state"] == "maintainer-approved-exact-object"
        assert row["reuse"] == decision["disposition"]
        assert row["approval_record"] == prepared["rights_decision"]
        assert row["recorded_at"] == prepared["recorded_at"]
    assert prepared["status"] == "prepared_not_published"
    assert prepared["historical_receipts_modified"] is False
    assert prepared["complete_b1_b2_lineage"] is False
    assert prepared["v4_admission"] is False
    assert prepared["consumer_canaries"] is False


def test_rights_append_contract_binds_exact_payload_and_preservation() -> None:
    contract = _read(
        "quality/qualifications/"
        "australian-mbs-utilisation-rights-append-contract-20261004.json"
    )
    payload_path = (
        "quality/qualifications/"
        "australian-mbs-utilisation-object-rights-metadata-20261004.json"
    )
    payload = (ROOT / payload_path).read_bytes()
    metadata = _read(payload_path)
    digest = hashlib.sha256(payload).hexdigest()
    addition = contract["addition"]
    assert addition == {
        "local_path": payload_path,
        "path": f"metadata/rights/mbs-utilisation/{digest}.json",
        "sha256": digest,
        "byte_count": len(payload),
    }
    assert contract["dataset"] == metadata["dataset"]
    assert contract["expected_parent_revision"] == metadata["source_revision"]
    assert contract["rights_decision"] == metadata["rights_decision"]
    assert contract["source_manifest_sha256"] == metadata["manifest_sha256"]
    assert contract["status"] == "prepared_not_executed"
    controls = contract["execution_controls"]
    assert controls["origin"] == "github_actions_only"
    assert controls["environment"] == "australian-hf-publication"
    assert controls["exact_reviewed_main_commit_required"] is True
    assert controls["parent_compare_and_swap_required"] is True
    assert controls["durable_intent_before_write"] is True
    assert controls["allowed_operations"] == ["add_exact_metadata_object"]
    assert controls["historical_overwrite_allowed"] is False
    assert controls["raw_source_acquisition_allowed"] is False
    assert contract["verification"]["expected_inventory_delta"] == {
        "added": [addition["path"]],
        "removed": [],
        "modified": [],
    }
    assert (
        contract["verification"]["anonymous_all_object_digest_readback"] is True
    )
    assert contract["verification"]["durable_receipt_before_cleanup"] is True
    assert (
        contract["verification"]["preserve_failed_published_revision"] is True
    )
    assert contract["recovery"]["retry_after_ambiguous_write"] == (
        "read_back_and_reconcile_before_any_new_write"
    )
    assert contract["completion_claims"] == {
        "external_publication_performed": False,
        "complete_b1_b2_lineage": False,
        "v4_admission": False,
        "consumer_canaries": False,
        "m112_federation_accepted": False,
    }
