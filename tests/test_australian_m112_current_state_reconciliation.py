"""Contract tests for the current Australian M-112 reconciliation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECONCILIATION = (
    ROOT / "quality/qualifications/"
    "australian-m112-current-state-reconciliation-20261004.json"
)
ADDENDUM = (
    ROOT / "quality/qualifications/"
    "australian-m112-current-state-addendum-20261004.json"
)


def _read(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_m112_reconciliation_uses_approved_denominator_and_latest_readback() -> (
    None
):
    receipt = json.loads(RECONCILIATION.read_text(encoding="utf-8"))
    decision = _read(
        "quality/qualifications/australian-m112-denominator-decision-20260930.json"
    )
    readback = _read(
        "quality/qualifications/australian-m112-public-tree-readback-20261003.json"
    )

    denominator = receipt["scope"]
    approved = decision["denominator"]
    assert denominator["producer_datasets"] == approved["datasets"]
    assert denominator["raw_source_payload_paths"] == 1_736
    assert denominator["existing_projection_paths"] == 23
    assert denominator["total_candidate_paths"] == 1_759
    assert (
        decision["status"] == "maintainer_approved_exact_candidate_denominator"
    )

    observed = receipt["public_metadata_readback"]
    assert observed["candidate_paths_present"] == 1_759
    assert observed["candidate_paths_missing"] == 0
    assert observed["complete_stable_scans"] == 2
    assert observed["payload_bytes_or_values_read"] is False
    assert (
        observed["full_denominator_anonymous_object_digest_readback_performed"]
        is False
    )
    assert readback["observations"]["candidate_paths_present"] == 1_759
    assert all(
        row["all_candidate_paths_present"] for row in readback["datasets"]
    )


def test_m112_reconciliation_corrects_stale_status_without_promoting_gates() -> (
    None
):
    receipt = json.loads(RECONCILIATION.read_text(encoding="utf-8"))
    crosswalk = _read(
        "quality/qualifications/australian-m112-source-rights-lineage-crosswalk-20260930.json"
    )
    registry = _read(
        "quality/qualifications/hf-public-metadata-readback-20261001.json"
    )

    assert receipt["status"] == (
        "approved_denominator_reconciled_metadata_presence_complete_"
        "rights_lineage_admission_blocked"
    )
    assert (
        receipt["reconciles_historical_crosswalk"][
            "prior_crosswalk_preserved_unchanged"
        ]
        is True
    )
    assert any(
        "denominator remains unapproved" in item for item in crosswalk["gaps"]
    )
    assert (
        receipt["registry_and_collection_metadata"]["policy_aus_members"] == 5
    )
    assert receipt["registry_and_collection_metadata"]["heor_members"] == 6
    assert registry["registry"]["public_access_mismatch_count"] == 0

    rights = receipt["source_rights_and_lineage_reconciliation"]
    assert rights["utilisation_receipt_sidecar_objects_joined"] == 20
    assert (
        rights["utilisation_objects_within_existing_authorization_scope"] == 20
    )
    assert rights["utilisation_objects_with_rights_state_in_sidecar"] == 0
    assert rights["reimbursement_atlas_raw_candidate_paths"] == 1_707
    assert (
        rights[
            "existing_projection_paths_with_complete_v4_lineage_and_admission_receipts"
        ]
        == 0
    )
    assert receipt["boundaries"]["new_licensing_or_rights_conclusion"] is False
    assert receipt["boundaries"]["v4_admission_performed"] is False
    assert receipt["boundaries"]["m112_federation_accepted"] is False


def test_m112_reconciliation_hash_binds_each_evidence_input() -> None:
    receipt = json.loads(RECONCILIATION.read_text(encoding="utf-8"))

    for reference in receipt["evidence_inputs"].values():
        path = ROOT / reference["path"]
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest() == reference["sha256"]
        )


def test_m112_addendum_supersedes_only_the_stale_mbs_lifecycle_snapshot() -> (
    None
):
    receipt = json.loads(ADDENDUM.read_text(encoding="utf-8"))
    assert receipt["supersedes"]["path"] == (
        "quality/qualifications/"
        "australian-m112-current-state-reconciliation-20261004.json"
    )
    assert receipt["august_2026_mbs"]["local_gma_b1_b2_lifecycle_complete"]
    assert receipt["august_2026_mbs"][
        "source_identity_joined_to_two_approved_archive_aliases"
    ]
    assert not receipt["august_2026_mbs"][
        "producer_archive_root_manifest_repaired"
    ]
    assert not receipt["august_2026_mbs"][
        "producer_archive_projection_lineage_complete"
    ]
    assert not receipt["august_2026_mbs"]["m112_v4_admission"]
    assert not receipt["august_2026_mbs"]["m112_consumer_canaries"]
    assert receipt["july_2025_v4_metadata"]["candidate_only"]
    assert receipt["july_2025_v4_metadata"]["reported_blockers"] == [
        "public_v4_identity_unverified"
    ]
    assert (
        receipt["unchanged_current_state"][
            "full_denominator_anonymous_digest_readback_complete"
        ]
        is False
    )
    assert (
        receipt["unchanged_current_state"]["m112_federation_accepted"] is False
    )
    for reference in receipt["evidence_inputs"].values():
        path = ROOT / reference["path"]
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest() == reference["sha256"]
        )
