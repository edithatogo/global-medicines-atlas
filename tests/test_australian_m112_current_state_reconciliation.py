"""Contract tests for the current Australian M-112 reconciliation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import scripts.qualify_australian_existing_derived_gates as derived_gates
import scripts.qualify_australian_schedule_source_privacy as mbs_source_privacy
import scripts.qualify_m112_existing_reimbursement_batch as batch_qualification

ROOT = Path(__file__).resolve().parents[1]
RECONCILIATION = (
    ROOT / "quality/qualifications/"
    "australian-m112-current-state-reconciliation-20261004.json"
)
ADDENDUM = (
    ROOT / "quality/qualifications/"
    "australian-m112-current-state-addendum-20261004.json"
)
LIVE_V4_READBACK = (
    ROOT / "quality/qualifications/"
    "australian-m112-live-public-v4-metadata-readback-20261004.json"
)
LIVE_V4_ADDENDUM = (
    ROOT / "quality/qualifications/"
    "australian-m112-current-state-addendum-20261004.json"
)


def _read(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_existing_mbs_silver_role_receipt_binds_value_free_reports() -> None:
    reports = (
        ROOT / "quality/qualifications/"
        "shared-mbs-silver-delivery-20261115-43608538996"
    )
    qualification = json.loads((reports / "qualification.json").read_bytes())
    assert qualification["producer_commit"] == (
        "946757ccdf5b21130811233f285807f5307ea209"
    )
    assert qualification["status"] == "passed"
    assert qualification["source_values_included"] is False
    assert qualification["publication_performed"] is False
    assert qualification["admission_performed"] is False
    assert len(qualification["tables"]) == 6
    for table in qualification["tables"]:
        for key in (
            "passed",
            "schema_equal",
            "row_values_equal",
            "native_values_preserved",
            "deterministic_replay",
        ):
            assert table[key] is True
    assert set(qualification["role_report_sha256"]) == {
        "cache-cleanup",
        "primary-restore",
        "silver-promotion",
        "v1-conformance",
        "v2-field-lineage",
        "v3-backfill-replay",
    }
    for name, expected in qualification["role_report_sha256"].items():
        report = json.loads((reports / f"{name}.json").read_bytes())
        canonical = json.dumps(
            report, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
        assert hashlib.sha256(canonical).hexdigest() == expected
    cleanup = json.loads((reports / "cache-cleanup.json").read_bytes())
    restore = json.loads((reports / "primary-restore.json").read_bytes())
    assert cleanup["source_payload_written_to_disk"] is False
    assert cleanup["disk_cache_exercised"] is False
    assert cleanup["remaining_entries"] == 0
    assert restore["object_count"] == 6
    assert restore["status"] == "passed"


def test_existing_archive_batch_binds_evidence_without_promoting_gates() -> (
    None
):
    batch = _read(
        "quality/qualifications/"
        "australian-federation-existing-archive-reconciliation-20261115.json"
    )
    for reference in batch["evidence_inputs"].values():
        evidence_path = ROOT / reference["path"]
        if (
            reference["path"]
            == "quality/qualifications/stable-v1-contract.json"
        ):
            # This dated batch bound the pre-D-006-14 contract; preserve its bytes.
            evidence_path = (
                ROOT
                / "quality/qualifications/scoped-software-v1-original-contract-20261114.json"
            )
        assert (
            hashlib.sha256(evidence_path.read_bytes()).hexdigest()
            == reference["sha256"]
        )

    historical = _read(batch["evidence_inputs"]["frozen_comparison"]["path"])
    ledger = _read(batch["evidence_inputs"]["raw_admission_ledger"]["path"])
    frozen = batch["frozen_inventory"]
    assert (
        frozen["matching_paths"]
        == historical["frozen_inventory"]["matching_objects"]
        == 1759
    )
    assert frozen["matching_observed_on"] == historical["observed_on"]
    assert frozen["fresh_full_inventory_readback_performed"] is False
    assert (
        frozen["raw_v4_admissions"]
        == ledger["effective_counts"]["raw_v4_admissions"]
        == 14
    )
    assert (
        frozen["raw_reader_canaries"]
        == ledger["effective_counts"]["raw_admitted_object_reader_canaries"]
        == 14
    )
    assert (
        frozen["deferred_admission"]
        == ledger["effective_counts"]["deferred_objects"]
        == 1745
    )
    assert frozen["six_mbs_silver_tables_included_in_raw_count"] is False

    annual = _read(batch["evidence_inputs"]["annual_workbook_profile"]["path"])
    mbs = batch["mbs_annual_workbook"]
    assert mbs["raw_sha256"] == annual["source"]["sha256"]
    assert mbs["receipt_sha256"] == annual["source"]["receipt_sha256"]
    assert (
        mbs["patients_sheet_classified_rows"]
        == annual["profile"]["data_rows"]
        == 2202
    )
    assert mbs["m106_accepted"] is False
    assert mbs["patient_values_emitted"] is False

    receipt = _read(
        batch["evidence_inputs"]["aihw_publication_receipt"]["path"]
    )
    aihw = batch["aihw_monthly_atc2"]
    assert aihw["revision"] == receipt["revision"]
    assert (
        aihw["manifest_canonical_sorted_compact_json_sha256"]
        == receipt["manifest_sha256"]
    )
    assert aihw["manifest_raw_bytes_sha256"] != receipt["manifest_sha256"]
    assert aihw["manifest_file_count"] == receipt["archive_file_count"] == 1078
    assert (
        aihw["participant_files_published"]
        == receipt["participant_files_published"]
        == 0
    )
    assert (
        aihw["anonymous_new_pair_digest_verification"]
        == receipt["anonymous_digest_verification"]
        == "passed"
    )
    assert aihw["september_2025_edition_identified"] is False
    assert (
        batch["existing_derived_evidence"]["mbs_july_2025_silver_tables"] == 6
    )
    assert (
        batch["existing_derived_evidence"]["pbs_april_2026_silver_v4_admitted"]
        is False
    )
    assert batch["federation_requirement_states"] == {
        f"M-{number}": "blocked" for number in range(105, 113)
    }
    assert all(value is False for value in batch["boundaries"].values())


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
    assert receipt["july_2025_v4_metadata"]["reported_blockers"] == []
    assert receipt["july_2025_v4_metadata"]["resolved_blockers"] == [
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


def test_live_v4_metadata_readback_fails_closed_on_stale_hosted_receipt() -> (
    None
):
    receipt = json.loads(LIVE_V4_READBACK.read_text(encoding="utf-8"))

    assert receipt["live_head"]["private"] is False
    assert receipt["live_head"]["gated"] is False
    assert receipt["object_reconciliation"]["expected_objects"] == 9
    assert receipt["object_reconciliation"]["matched_to_receipt"] == 9
    assert receipt["current_manifest_matches_receipt"] is True
    assert receipt["manifest_declares_candidate_only"] is True
    assert receipt["publication_receipt_binds_current_head"] is False
    assert (
        receipt["prior_publication_receipt"]["revision_matches_current_head"]
        is False
    )
    assert receipt["status"] == (
        "candidate_identity_verified_historical_receipt_and_current_objects_match"
    )
    assert receipt["object_reconciliation"]["mismatched_or_unverified"] == 0
    assert receipt["boundaries"]["current_tree_identity_verified"] is True
    assert receipt["boundaries"]["v4_admission_performed"] is False
    assert receipt["boundaries"]["consumer_canaries_performed"] is False
    assert receipt["boundaries"]["m112_federation_accepted"] is False
    assert receipt["boundaries"]["source_payload_bytes_read"] is False
    assert receipt["boundaries"]["source_payload_values_read"] is False


def test_latest_addendum_supersedes_only_v4_identity_blocker() -> None:
    receipt = json.loads(LIVE_V4_ADDENDUM.read_text(encoding="utf-8"))
    assert (
        "July 2025 MBS v4 candidate identity verification"
        in receipt["supersedes"]["scope"]
    )
    assert (
        "August MBS local B1/B2 lifecycle state"
        in receipt["supersedes"]["scope"]
    )
    assert receipt["approved_scope"]["candidate_paths"] == 1_759
    assert receipt["approved_scope"]["denominator_changed"] is False
    v4 = receipt["july_2025_v4_metadata"]
    assert v4["candidate_only"] is True
    assert v4["verified_objects"] == 9
    assert v4["identity_verification"] == (
        "verified_against_historical_immutable_receipt_and_current_tree"
    )
    assert v4["reported_blockers"] == []
    assert v4["resolved_blockers"] == ["public_v4_identity_unverified"]
    assert v4["v4_admission"] is False
    assert v4["consumer_canaries"] is False
    for reference in receipt["evidence_inputs"].values():
        path = ROOT / reference["path"]
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest() == reference["sha256"]
        )

    acceptance = (
        ROOT / "docs/qualification/australian-health-federation-acceptance.md"
    ).read_text(encoding="utf-8")
    assert (
        "The July 2025 six-table Silver cohort separately passed its scoped "
        "v4 remote-reader qualification"
    ) in acceptance
    assert "no typed v4 admission" in acceptance
    assert "`f9f9` has no admission sidecar" in acceptance
    assert "explicitly deferred from M-108 admission" in acceptance
    assert "v4 source-receipt reference is absent locally" not in acceptance


def test_acceptance_page_reconciles_exact_mbs_utilisation_rights_scope() -> (
    None
):
    acceptance = (
        ROOT / "docs/qualification/australian-health-federation-acceptance.md"
    ).read_text(encoding="utf-8")
    rights = _read(
        "quality/qualifications/"
        "australian-m112-utilisation-rights-reconciliation-20261004.json"
    )
    disposition = rights["current_disposition"]

    assert "exact 14-object MBS-utilisation manifest" in acceptance
    assert (
        "joins each path to its B1/B2 lifecycle and digest evidence"
        in acceptance
    )
    assert "landed-admission reviewer status still unreviewed" in acceptance
    assert (
        "supplemental reconciliation binds the maintainer's exact six-file "
        "PBS-utilisation rights attestation to all six frozen path/digest/byte "
        "identities and their complete B1/B2 lineage"
    ) in acceptance
    assert (
        "australian-m112-pbs-utilisation-rights-lineage-reconciliation-20261028.json"
        in acceptance
    )
    assert "does not qualify a wider PBS-utilisation population" in acceptance
    assert disposition["candidate_paths"] == 14
    assert disposition["v4_admission"] is False
    assert disposition["m112_federation_accepted"] is False


def test_release_field_contract_binds_retained_evidence_without_scope_change():
    contract = _read(
        "quality/qualifications/"
        "australian-benefits-release-field-contract-20261028.json"
    )
    for binding in contract["evidence"].values():
        payload = (ROOT / binding["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == binding["sha256"]
    inventory = _read(contract["evidence"]["frozen_inventory"]["path"])
    assert (
        contract["scope"]["frozen_candidate_paths"]
        == (inventory["denominator"]["total_candidate_paths"])
    )
    assert contract["scope"]["scope_amendment"] is False
    assert contract["scope"]["all_91_workbooks_remain_required"] is True
    assert (
        contract["scope"][
            "all_frozen_source_families_remain_in_qualification_denominator"
        ]
        is True
    )


def test_release_field_contract_keeps_header_and_value_partitions_separate():
    contract = _read(
        "quality/qualifications/"
        "australian-benefits-release-field-contract-20261028.json"
    )
    columns = _read(contract["evidence"]["mbs_workbook_columns"]["path"])
    workbook = contract["baseline"]["mbs_workbooks"]
    assert workbook["workbooks"] == columns["scope"]["workbooks"]
    assert (
        workbook["header_bindings"]
        == (columns["scope"]["interpreted_header_bindings"])
    )
    assert (
        workbook["non_header_values_native_unresolved"]
        == (columns["scope"]["non_header_values"])
    )
    assert workbook["non_header_values_interpreted"] == 0
    pbs = _read(contract["evidence"]["pbs_field_states"]["path"])["report"]
    partition = pbs["field_state_coverage"]
    baseline = contract["baseline"]["pbs_native"]
    states = contract["field_states"]
    assert set(states) == {"interpreted", "native_unresolved", "unavailable"}
    assert sum(baseline[state] for state in states) == baseline["source_fields"]
    for key in ["source_fields", *states]:
        assert baseline[key] == partition[key]


def test_release_field_contract_is_requirements_not_gate_clearance():
    contract = _read(
        "quality/qualifications/"
        "australian-benefits-release-field-contract-20261028.json"
    )
    assert contract["status"] == "requirements_frozen_qualification_incomplete"
    assert set(contract["required_consumers"]) == {
        "API",
        "CLI",
        "Atlas",
        "deterministic_export",
    }
    assert all(row["required"] for row in contract["consumer_requirements"])
    assert {row["id"] for row in contract["conditional_claims"]} == {
        "value_and_era",
        "domain_meaning",
        "broader_relationships",
        "historical_comparison",
    }
    assert not any(contract["non_claims"].values())


def test_existing_reimbursement_batch_retains_per_object_privacy_gates() -> (
    None
):
    report = batch_qualification.build_report()
    saved = _read(
        "quality/qualifications/"
        "australian-m112-reimbursement-batch-readiness-20261115.json"
    )
    assert report == saved
    assert report["result"] == {
        "metadata_identity_rights_lineage_joined": 1719,
        "raw_source_sensitivity_unknown": 1707,
        "projection_sensitivity_not_qualified": 12,
        "ready_for_payload_read": 0,
        "new_admissions": 0,
        "consumer_checks_on_selected_objects": 0,
        "other_metadata_rows_reconciled": 26,
        "other_prior_separate_mbs_silver_consumer_receipts": 6,
    }
    objects = report["objects"]
    assert len({row["path"] for row in objects}) == 1719
    assert all(row["ready_for_payload_read"] is False for row in objects)
    assert all(row["v4_admission"] == "not_performed" for row in objects)
    assert all(
        row["consumer_check"] == "not_performed_privacy_gate_blocked"
        for row in objects
    )
    assert (
        sum(
            row["lineage_evidence"] == "exact_layer_partition_metadata_linked"
            for row in objects
        )
        == 3
    )
    assert (
        sum(
            row["lineage_evidence"]
            == "byte_identical_producer_projection_metadata_linked"
            for row in objects
        )
        == 9
    )
    assert all(value is False for value in report["boundaries"].values())
    other = report["other_frozen_objects"]
    assert len(other) == 26
    assert len({(row["dataset"], row["path"]) for row in other}) == 26
    previous_silver = [
        row
        for row in other
        if row["prior_separate_silver_consumer"] is not None
    ]
    assert len(previous_silver) == 6
    assert all(
        row["prior_separate_silver_consumer"]["qualified_revision"]
        != row["frozen_revision"]
        for row in previous_silver
    )
    assert all(row["current_payload_read"] == "not_performed" for row in other)
    assert all(
        row["current_raw_v4_admission"] == "not_performed" for row in other
    )


def test_existing_projection_partition_requires_its_recorded_relation() -> None:
    docs = {
        key: batch_qualification._read_bound(
            ROOT, *batch_qualification.INPUTS[key]
        )
        for key in (
            "frozen",
            "overlay",
            "projection_attestation",
            "projection_lineage",
        )
    }
    path = "data/medallion/silver/data.jsonl"
    dataset = batch_qualification.DATASET
    frozen = next(
        x
        for x in docs["frozen"]["members"]
        if x["dataset"] == dataset and x["path"] == path
    )
    overlay = next(
        x
        for x in docs["overlay"]["objects"]
        if x["dataset"] == dataset and x["path"] == path
    )
    rights = next(
        x
        for x in docs["projection_attestation"]["authorized_objects"]
        if x["path"] == path
    )
    lineage = next(
        x
        for x in docs["projection_lineage"]["objects"]
        if x["dataset_path"] == path
    )
    args = {
        "path": path,
        "frozen": frozen,
        "overlay": overlay,
        "rights": rights,
    }
    assert lineage["producer_source_sha256"] != lineage["dataset_sha256"]
    record = batch_qualification._projection_record(**args, lineage=lineage)
    assert record["lineage_evidence"] == "exact_layer_partition_metadata_linked"
    assert record["ready_for_payload_read"] is False
    with pytest.raises(ValueError, match="byte-identical"):
        batch_qualification._projection_record(
            **args,
            lineage={
                **lineage,
                "projection_relation": "byte_identical_to_exact_producer_source_path",
            },
        )
    with pytest.raises(ValueError, match="partition"):
        batch_qualification._projection_record(
            **args, lineage={**lineage, "producer_source_sha256": "0" * 64}
        )
    with pytest.raises(ValueError, match="unsupported"):
        batch_qualification._projection_record(
            **args, lineage={**lineage, "projection_relation": "unverified"}
        )


def test_batch_metadata_reader_rejects_unbound_paths(tmp_path: Path) -> None:
    parent = tmp_path / "quality" / "qualifications"
    parent.mkdir(parents=True)
    body = b'{"schema_id":"test"}'
    (parent / "record.json").write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    assert batch_qualification._read_bound(
        tmp_path, "quality/qualifications/record.json", digest
    ) == {"schema_id": "test"}
    with pytest.raises(ValueError, match="digest"):
        batch_qualification._read_bound(
            tmp_path, "quality/qualifications/record.json", "0" * 64
        )
    with pytest.raises(ValueError, match="invalid"):
        batch_qualification._read_bound(
            tmp_path, "quality/qualifications/../record.json", digest
        )
    (parent / "link.json").symlink_to(parent / "record.json")
    with pytest.raises(ValueError, match="symlink"):
        batch_qualification._read_bound(
            tmp_path, "quality/qualifications/link.json", digest
        )


def test_pbs_reader_rechecks_bind_six_prior_admissions() -> None:
    manifest = _read(
        "quality/qualifications/"
        "australian-m112-pbs-reader-recheck-20261115/manifest.json"
    )
    ledger_ref = manifest["prior_ledger"]
    ledger_bytes = (ROOT / ledger_ref["path"]).read_bytes()
    assert hashlib.sha256(ledger_bytes).hexdigest() == ledger_ref["sha256"]
    ledger = json.loads(ledger_bytes)
    keys = ("dataset", "revision", "path", "sha256", "byte_count")
    admitted = {
        tuple(row[k] for k in keys) for row in ledger["new_admitted_identities"]
    }
    assert len(admitted) == manifest["rechecked_existing_objects"] == 6
    assert {
        tuple(row[k] for k in keys) for row in manifest["objects"]
    } == admitted
    assert manifest["new_unique_admissions"] == 0
    assert manifest["raw_admissions_before_and_after"] == 14
    assert manifest["raw_canaries_before_and_after"] == 14
    assert manifest["deferred_before_and_after"] == 1745
    assert all(value is False for value in manifest["boundaries"].values())
    for row in manifest["objects"]:
        receipt_bytes = (ROOT / row["receipt_path"]).read_bytes()
        assert (
            hashlib.sha256(receipt_bytes).hexdigest() == row["receipt_sha256"]
        )
        receipt = json.loads(receipt_bytes)
        assert receipt["status"] == row["status"] == "passed"
        assert tuple(receipt["admission"][k] for k in keys) == tuple(
            row[k] for k in keys
        )
        canary = receipt["consumer_canary"]
        assert canary["status"] == "passed"
        assert all(
            canary["object"][k] == row[k]
            for k in ("dataset", "revision", "path", "sha256")
        )
        assert canary["object"]["bytes"] == row["byte_count"]
        assert canary["hosted_workflow"]["run_id"] == row["run_id"]
        assert (
            canary["hosted_workflow"]["commit"] == manifest["workflow_commit"]
        )
        assert canary["verification"]["remote_digest_match"] is True
        assert canary["verification"]["consumer_stream_digest_match"] is True
        assert canary["verification"]["reader_cache_bytes_after_close"] == 0
        assert canary["boundaries"]["source_values_or_rows_included"] is False
        assert canary["boundaries"]["source_payload_bytes_retained"] is False
        assert canary["boundaries"]["public_dataset_mutated"] is False


def test_mbs_reader_rechecks_bind_eight_prior_admissions() -> None:  # ruff: ignore[too-many-statements] -- Each object must bind its own independent evidence.
    manifest = _read(
        "quality/qualifications/"
        "australian-m112-mbs-reader-recheck-20261115/manifest.json"
    )
    ledger_ref = manifest["prior_ledger"]
    ledger_bytes = (ROOT / ledger_ref["path"]).read_bytes()
    assert hashlib.sha256(ledger_bytes).hexdigest() == ledger_ref["sha256"]
    ledger = json.loads(ledger_bytes)
    keys = (
        "dataset",
        "revision",
        "path",
        "sha256",
        "contract_path",
        "contract_sha256",
    )
    previous = {
        tuple(row[key] for key in keys)
        for row in ledger["prior_admitted_identities"]
    }
    assert len(previous) == manifest["rechecked_existing_objects"] == 8
    assert {
        tuple(row[key] for key in keys) for row in manifest["objects"]
    } == previous
    assert manifest["new_unique_admissions"] == 0
    assert (
        manifest["raw_admissions_before_and_after"]
        == ledger["effective_counts"]["raw_v4_admissions"]
        == 14
    )
    assert (
        manifest["raw_canaries_before_and_after"]
        == ledger["effective_counts"]["raw_admitted_object_reader_canaries"]
        == 14
    )
    assert (
        manifest["deferred_before_and_after"]
        == ledger["effective_counts"]["deferred_objects"]
        == 1745
    )
    assert all(value is False for value in manifest["boundaries"].values())
    assert (
        sum(row["byte_count"] for row in manifest["objects"])
        == manifest["total_bytes"]
    )
    for row in manifest["objects"]:
        contract_bytes = (ROOT / row["contract_path"]).read_bytes()
        assert (
            hashlib.sha256(contract_bytes).hexdigest() == row["contract_sha256"]
        )
        contract = json.loads(contract_bytes)
        assert contract["rights"]["sensitivity"] == "non_sensitive"
        assert contract["rights"]["publication"] == "approved_exact_scope"
        assert contract["rights"]["subject_sha256"] == row["sha256"]
        assert contract["location"]["bytes"] == row["byte_count"]
        receipt_bytes = (ROOT / row["receipt_path"]).read_bytes()
        assert (
            hashlib.sha256(receipt_bytes).hexdigest() == row["receipt_sha256"]
        )
        receipt = json.loads(receipt_bytes)
        assert receipt["status"] == "admitted_with_consumer_canary"
        assert receipt["source_values_or_payload_bytes_retained"] is False
        assert receipt["receipt_closure"]["receipt_content_retained"] is False
        assert receipt["admission"]["contract_sha256"] == row["contract_sha256"]
        assert all(
            receipt["admission"][key] == row[key]
            for key in ("dataset", "revision", "path", "sha256", "byte_count")
        )
        canary = receipt["consumer_canary"]
        assert canary["status"] == row["status"] == "passed"
        assert all(
            canary["object"][key] == row[key]
            for key in ("dataset", "revision", "path", "sha256")
        )
        assert canary["object"]["bytes"] == row["byte_count"]
        assert canary["hosted_workflow"]["run_id"] == row["run_id"]
        assert canary["hosted_workflow"]["run_attempt"] == row["run_attempt"]
        assert (
            canary["hosted_workflow"]["commit"] == manifest["workflow_commit"]
        )
        assert canary["verification"]["origin"] == "remote"
        assert canary["verification"]["remote_digest_match"] is True
        assert canary["verification"]["consumer_stream_digest_match"] is True
        assert canary["verification"]["reader_cache_bytes_after_close"] == 0
        assert (
            canary["verification"]["source_values_or_rows_interpreted"] is False
        )
        assert canary["boundaries"]["source_values_or_rows_included"] is False
        assert canary["boundaries"]["source_payload_bytes_retained"] is False
        assert canary["boundaries"]["public_dataset_mutated"] is False
    retry = manifest["retained_retry"]
    assert retry["first_attempt_status"] == "failed_before_reader"
    assert (
        retry["first_attempt_failure"]
        == "anonymous_github_receipt_http_403_rate_limit"
    )
    assert retry["additional_attempts"] == 1
    assert retry["second_attempt_status"] == "passed"
    assert [
        (row["run_id"], row["run_attempt"])
        for row in manifest["objects"]
        if row["run_attempt"] != 1
    ] == [(retry["run_id"], 2)]


def test_existing_derived_objects_reconcile_without_promoting_gates() -> None:
    report = derived_gates.build_report(ROOT)
    recorded = _read(
        "quality/qualifications/australian-existing-derived-gates-20261115.json"
    )
    assert report == recorded
    assert report["result"] == {
        "mbs_outside_frozen_candidates": 4,
        "pbs_silver_candidates": 1,
        "candidate_privacy_qualified_by_this_check": 0,
        "new_admissions": 0,
        "new_live_consumer_canaries": 0,
        "previous_mbs_silver_consumer_objects_revalidated": 6,
    }
    assert all(value is False for value in report["boundaries"].values())
    assert len({row["path"] for row in report["mbs_candidates"]}) == 4
    for row in report["mbs_candidates"]:
        assert row["frozen_m112_member"] is False
        assert row["privacy"] == "not_qualified_in_selected_evidence"
        assert row["v4_admission"] == row["consumer_check"] == "not_performed"
        assert row["payload_read_permitted_by_this_report"] is False
    pbs = report["pbs_candidate"]
    assert pbs["revision"] == "3995deb3e2a82f09472d6a78020fb13bbbc96056"
    assert (
        pbs["public_location"]
        == "prior_hosted_and_anonymous_digest_verification_passed"
    )
    assert pbs["field_state"] == "prior_receipt_names_different_output"
    assert pbs["privacy"] == "not_qualified_in_selected_evidence"
    assert pbs["v4_admission"] == pbs["consumer_check"] == "not_performed"
    assert pbs["independent_recovery"] == "not_qualified"
    consumers = report["prior_mbs_consumer_objects"]
    assert len(consumers) == len({row["path"] for row in consumers}) == 6
    assert all(
        row["admission"] == "previously_admitted_candidate_product"
        for row in consumers
    )
    assert all(
        row["privacy"] == "non_sensitive_in_exact_previously_admitted_contract"
        for row in consumers
    )


def test_derived_mbs_equal_size_does_not_prove_identity() -> None:
    sources = {
        name: _read(path)
        for name, (path, _digest) in derived_gates.INPUTS.items()
    }
    tree = sources["mbs_tree"]["readback"]["objects"]
    assert tree[0]["byte_count"] == tree[2]["byte_count"]
    tree[0]["sha256"] = tree[2]["sha256"]
    with pytest.raises(ValueError, match="object binding differs"):
        derived_gates.mbs_candidates(sources)


def test_august_mbs_source_privacy_is_bound_without_output_promotion() -> None:
    report = mbs_source_privacy.build_report(ROOT)
    assert report == _read(
        "quality/qualifications/australian-schedule-source-privacy-check-20261115.json"
    )
    assert len(report["mbs_products"]) == 2
    assert sum(row["object_count"] for row in report["mbs_products"]) == 4
    assert all(
        row["projection_privacy"] == "not_qualified_by_source_classification"
        and row["v4_admission"] == "not_performed"
        for row in report["mbs_products"]
    )
    assert all(value is False for value in report["boundaries"].values())
    assert report["pbs_source"]["source_privacy"] == (
        "unknown_in_imported_acquisition_record"
    )


@pytest.mark.parametrize(
    "mutation",
    ["personal_data", "source_digest", "product_source", "duplicate_object"],
)
def test_august_mbs_source_privacy_rejects_unbound_or_sensitive_evidence(
    mutation: str,
) -> None:
    scope = _read(derived_gates.INPUTS["mbs_scope"][0])
    receipts = {
        identity: _read(binding[0])
        for identity, binding in mbs_source_privacy.SOURCE_RECEIPTS.items()
    }
    first = next(iter(receipts.values()))
    if mutation == "personal_data":
        first["sensitivity"]["personal_data"] = "unknown"
    elif mutation == "source_digest":
        first["payload_sha256"] = "a" * 64
    elif mutation == "product_source":
        scope["products"][0]["source"]["sha256"] = "b" * 64
    else:
        scope["objects"][0]["path"] = scope["objects"][1]["path"]
    with pytest.raises(
        ValueError,
        match=r"source privacy receipt|source binding|product identities",
    ):
        mbs_source_privacy.qualify_documents(scope, receipts)


@pytest.mark.parametrize(
    "mutation", ["event_privacy", "member_source", "lineage"]
)
def test_pbs_source_privacy_rejects_mismatched_source_evidence(
    mutation: str,
) -> None:
    event = _read(mbs_source_privacy.PBS_EVENT[0])
    lineage = _read(mbs_source_privacy.PBS_LINEAGE[0])
    package = _read(derived_gates.INPUTS["pbs_package"][0])
    if mutation == "event_privacy":
        event["sensitivity"]["data_sensitivity"] = "non_sensitive"
    elif mutation == "member_source":
        package["member_binding"]["archive_payload"]["sha256"] = "a" * 64
    else:
        for row in lineage["objects"]:
            if (
                row["dataset"] == "edithatogo/australian-pbs-source-archive"
                and row["path"] == mbs_source_privacy.PBS_SOURCE_PATH
            ):
                row["local_records"]["acquisition_event_path"] = "wrong.json"
                break
    with pytest.raises(ValueError, match=r"PBS .* binding differs"):
        mbs_source_privacy.qualify_pbs_source(event, lineage, package)


def test_derived_pbs_rejects_misbound_verified_revision() -> None:
    sources = {
        name: _read(path)
        for name, (path, _digest) in derived_gates.INPUTS.items()
    }
    sources["pbs_verification"]["revision"] = "a" * 40
    with pytest.raises(ValueError, match="candidate evidence differs"):
        derived_gates.pbs_candidate(sources)


def test_existing_consumer_check_rejects_wrong_object_and_request() -> None:
    receipt = _read(derived_gates.INPUTS["consumer_receipt"][0])
    manifest = _read(derived_gates.INPUTS["consumer_manifest"][0])
    semantics = _read(derived_gates.INPUTS["consumer_semantic_manifest"][0])
    receipt["remote_reads"][0]["object_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="object, privacy or canary"):
        derived_gates.checked_consumers(ROOT, receipt, manifest, semantics)
    receipt = _read(derived_gates.INPUTS["consumer_receipt"][0])
    receipt["consumer_canary"]["evidence"][0]["request_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="object, privacy or canary"):
        derived_gates.checked_consumers(ROOT, receipt, manifest, semantics)


def test_fresh_mbs_consumers_match_prior_objects_without_browser() -> None:
    rows = derived_gates.check_fresh_consumers(ROOT)
    assert {row["table"] for row in rows} == derived_gates.CONSUMER_TABLES
    assert all(
        row["consumer_check"]
        == "fresh_hosted_browser_free_four_surface_canary_passed"
        and row["privacy"]
        == "non_sensitive_in_exact_previously_admitted_contract"
        for row in rows
    )


@pytest.mark.parametrize(
    "mutation",
    ["commit", "object", "browser_claim", "unexpected_browser_evidence"],
)
def test_fresh_mbs_consumer_evidence_rejects_mismatches(mutation: str) -> None:
    receipt = _read(
        derived_gates.FRESH_SILVER_DIR + "admission-remote-read.json"
    )
    manifest = _read(derived_gates.FRESH_SILVER_DIR + "artifact-manifest.json")
    semantics = _read(derived_gates.INPUTS["consumer_semantic_manifest"][0])
    if mutation == "commit":
        receipt["contract_commit"] = "a" * 40
    elif mutation == "object":
        receipt["remote_reads"][0]["object_sha256"] = "b" * 64
    elif mutation == "browser_claim":
        receipt["consumer_canary"]["browser_qualification"] = "passed"
    else:
        receipt["consumer_canary"]["evidence"][0]["browser"] = {
            "http_status": 200,
            "row_count": 2,
        }
    with pytest.raises(
        ValueError,
        match=r"boundary differs|object, privacy or canary|canary summary differs",
    ):
        derived_gates.checked_consumers(
            ROOT,
            receipt,
            manifest,
            semantics,
            evidence_directory=derived_gates.FRESH_SILVER_DIR,
            workflow_run=derived_gates.FRESH_RUN,
            browser_expected=False,
            expected_commit=derived_gates.FRESH_COMMIT,
        )


def test_existing_consumer_check_rejects_unqualified_privacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = _read(derived_gates.INPUTS["consumer_receipt"][0])
    manifest = _read(derived_gates.INPUTS["consumer_manifest"][0])
    semantics = _read(derived_gates.INPUTS["consumer_semantic_manifest"][0])
    original = derived_gates.bounded.read_bound_metadata

    def read_with_unqualified_privacy(
        root: Path, relative: str, digest: str
    ) -> dict[str, Any]:
        result = original(root, relative, digest)
        if relative.endswith("metadata/contracts/services.json"):
            result["rights"]["sensitivity"] = "unknown"
        return result

    monkeypatch.setattr(
        derived_gates.bounded,
        "read_bound_metadata",
        read_with_unqualified_privacy,
    )
    with pytest.raises(ValueError, match="object, privacy or canary"):
        derived_gates.checked_consumers(ROOT, receipt, manifest, semantics)
