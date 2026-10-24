"""Current M-112 rights preflight preserves exact scope and release gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = (
    ROOT / "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261024-77.json"
)
PREVIOUS_PREFLIGHT = (
    ROOT / "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261024-76.json"
)
PRESERVED_MAIN_PREFLIGHT = (
    ROOT / "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261020-5.json"
)
PRESERVED_MAIN_PREFLIGHT_SHA256 = (
    "6022ff3ca2b1a5fe8a095bc5ebba48e3ac86297e3b7ddeff63e92ea5af21dc82"
)
PRESERVED_AUGUST_RIGHTS_PREFLIGHT = (
    ROOT / "quality/qualifications/"
    "australian-m112-rights-release-preflight-20261020-6.json"
)
PRESERVED_AUGUST_RIGHTS_PREFLIGHT_SHA256 = (
    "20cf284b95eb83436fdd437eca1d5075dda1bc6bc23bda7c12f1591d25c9bd3f"
)


def _json(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def test_preflight_binds_current_inputs_and_preserves_historical_snapshot() -> (
    None
):
    report = _json(PREFLIGHT)
    assert "tests/test_m112_rights_release_preflight.py" not in report["inputs"]
    assert (
        "conductor/tracks/australian_benefits_silver_gold_20260829/evidence.jsonl"
        not in report["inputs"]
    )
    for path, expected_digest in report["inputs"].items():
        assert (
            hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            == expected_digest
        )
    inventory_correction = report["inventory_correction"]
    assert (
        inventory_correction["test_path"]
        == "tests/test_pbs_reference_review_packet.py"
    )
    assert inventory_correction["test_lane"] == "unit"
    assert inventory_correction["source_semantics_changed"] is False
    assert report["status"] == (
        "frozen_m112_exact_object_rights_attested_lineage_and_admission_gaps_open"
    )
    assert report["effective_m112_rights"]["resolved_object_count"] == 1759
    assert report["effective_m112_rights"]["unresolved_object_count"] == 0
    assert not any(
        "full PBS utilisation vocabulary exclusion review" in item["work"]
        for item in report["remaining_rights_work"]
    )
    reconciliation = report["current_rights_reconciliation"]
    assert reconciliation["approved_denominator"] == 1759
    assert reconciliation["membership_changed"] is False
    assert reconciliation["v4_admissions"] == 8
    assert reconciliation["consumer_canaries"] == 8
    assert reconciliation["deferred_objects"] == 1751
    assert (
        hashlib.sha256((ROOT / reconciliation["path"]).read_bytes()).hexdigest()
        == reconciliation["sha256"]
    )
    q2 = report["q2_admission"]
    assert q2["workflow_run_id"] == 39419974066
    assert q2["consumer_canary_passed"] is True
    assert q2["source_values_or_rows_interpreted"] is False
    assert q2["source_payload_bytes_retained"] is False
    assert q2["reader_cache_bytes_after_close"] == 0
    assert (
        hashlib.sha256((ROOT / q2["receipt_path"]).read_bytes()).hexdigest()
        == q2["receipt_sha256"]
    )
    assert any(
        run["run_id"] == 39419974066
        for run in report["m112_admission_canary_readback"][
            "successful_workflow_runs"
        ]
    )
    raw = report["mbs_raw_object_rights_attestation"]
    assert raw["object_count"] == 6
    assert raw["public_release_rights_attested"] is True
    assert raw["permission_instrument_existence_and_applicability"] == (
        "maintainer_attested_not_independently_reviewed"
    )
    assert raw["b1_b2_lineage_or_admission_inferred"] is False
    assert raw["v4_admission"] is False
    assert raw["consumer_canary"] is False
    q3 = report["q3_admission"]
    assert q3["workflow_run_id"] == 39356792827
    assert q3["consumer_canary_passed"] is True
    assert (
        hashlib.sha256((ROOT / q3["receipt_path"]).read_bytes()).hexdigest()
        == q3["receipt_sha256"]
    )
    projection = report["pbs_source_archive_exact_publication"][
        "source_projection"
    ]
    assert projection["public_release_rights_attested"] is True
    assert projection["permission_instrument_independently_reviewed"] is False
    assert projection["release_performed_by_this_reconciliation"] is False


def test_preflight_binds_current_silver_semantics_readbacks() -> None:
    report = _json(PREFLIGHT)
    pbs_screen = report["pbs_native_reference_screen_actual_readback"]
    assert pbs_screen["run_id"] == 40076190245
    assert pbs_screen["native_fields"] == 18_208_758
    assert pbs_screen["reference_fields"] == 2_160_066
    assert pbs_screen["per_kind_counts"]["rdf:resource"]["occurrences"] == (
        1_167_610
    )
    assert pbs_screen["per_kind_counts"]["xlink:href"]["occurrences"] == (
        992_456
    )
    assert pbs_screen["semantic_relationships_qualified"] is False
    assert pbs_screen["domain_semantics_qualified"] is False
    assert pbs_screen["source_context_screen_included"] is True
    assert pbs_screen["context_screen_implementation_present"] is True
    assert pbs_screen["source_context_review_pending"] is True
    assert (
        hashlib.sha256((ROOT / pbs_screen["receipt"]).read_bytes()).hexdigest()
        == pbs_screen["receipt_sha256"]
    )
    header = report["historical_workbook_header_profile_actual_readback"]
    assert header["run_id"] == 40040624592
    assert header["workbooks"] == 91
    assert header["interpreted_header_column_bindings"] == 728
    assert header["non_header_cells"] == 310_177_657
    assert header["non_header_cells_state"] == "native_unresolved"
    assert header["whole_workbook_semantics_complete"] is False


def test_preflight_binds_p7_per_cell_calendar_readback() -> None:
    report = _json(PREFLIGHT)
    p7 = report["mbs_p7_value_era_rules_actual_readback"]
    assert p7["date_cells"] == 1_280
    assert p7["date_cells_ambiguous_dmy_mdy"] == 1_194
    assert p7["uniquely_determined_calendar_dates_interpreted"] == 86
    assert p7["native_unresolved_cells"] == 13_656
    assert p7["date_profile_selected"] is False
    assert p7["formula_evaluation"] is False
    calendar = report["mbs_p7_calendar_profile_actual_readback"]
    assert calendar["run_id"] == 40086831574
    assert calendar["populated_date_cells"] == 1_280
    assert calendar["ambiguous_calendar_order"] == 1_194
    assert calendar["unique_calendar_date"] == 86
    assert calendar["invalid"] == 0
    assert calendar["unsupported_serial_date"] == 0
    assert calendar["date_order_selected"] is False
    assert calendar["source_values_emitted"] is False
    assert (
        hashlib.sha256((ROOT / calendar["receipt"]).read_bytes()).hexdigest()
        == calendar["receipt_sha256"]
    )
    p7_run = report["mbs_p7_exact_main_field_state"]
    assert p7_run["workflow_run_id"] == 40094025412
    assert (
        p7_run["workflow_commit"] == "11be72e328affc0df87395fd59165ef4f5bf9055"
    )
    assert p7_run["interpreted_unique_calendar_date_cells"] == 86
    assert p7_run["native_unresolved_cells"] == 13_656
    assert p7_run["workbook_wide_date_order_selected"] is False


def test_preflight_binds_bounded_pbs_semantics_and_packet() -> None:
    report = _json(PREFLIGHT)
    pbs_semantics = report["pbs_native_domain_semantic_adjudication"]
    assert pbs_semantics["source_fields"] == 18_208_758
    assert pbs_semantics["interpreted_fields"] == 40_667
    assert pbs_semantics["native_unresolved_fields"] == 18_168_091
    assert pbs_semantics["native_values_interpreted"] is False
    pbs_packet = report["pbs_native_reference_review_packet"]
    assert pbs_packet["workflow_run_id"] == 40091358786
    assert pbs_packet["context_examples"] == 61
    assert pbs_packet["source_cases_reviewed"] == 0
    assert pbs_packet["semantic_relationships_qualified"] is False


def test_preflight_binds_pbs_context_screen_attempt_and_readback() -> None:
    report = _json(PREFLIGHT)
    context_screen = report[
        "pbs_native_reference_context_screen_latest_attempt"
    ]
    assert context_screen["run_id"] == 40091358786
    assert context_screen["status"] == "success"
    assert context_screen["source_values_emitted"] is False
    assert context_screen["semantic_relationships_qualified"] is False
    assert context_screen["source_cases_reviewed"] == 0
    assert (
        hashlib.sha256(
            (ROOT / context_screen["receipt"]).read_bytes()
        ).hexdigest()
        == context_screen["receipt_sha256"]
    )
    context_readback = report[
        "pbs_native_reference_context_screen_actual_readback"
    ]
    assert context_readback["run_id"] == 40091358786
    assert context_readback["context_schema_version"] == 3
    assert context_readback["structural_strata"] == 184
    assert context_readback["value_free_examples"] == 61
    assert context_readback["omitted_occurrences"] == 2_160_005
    assert context_readback["examples_by_status"] == {
        "no_exact_literal": 52,
        "unique_exact_literal": 9,
    }
    assert context_readback["example_reference_kinds"] == {"rdf_resource": 61}
    assert context_readback["examples_with_nearest_subject"] == 0
    assert (
        context_readback["screen_is_sufficient_for_semantic_calibration"]
        is False
    )
    assert context_readback["source_cases_reviewed"] == 0
    assert context_readback["semantic_relationships_qualified"] is False
    assert context_readback["consumer_canaries"] == 0
    assert (
        hashlib.sha256(
            (ROOT / context_readback["receipt"]).read_bytes()
        ).hexdigest()
        == context_readback["receipt_sha256"]
    )
    prior_failure = report["pbs_native_reference_context_screen_prior_failure"]
    assert prior_failure["run_id"] == 40052770374
    assert prior_failure["status"] == "failed"


def test_preflight_binds_context_sampler_fairness_followup() -> None:
    report = _json(PREFLIGHT)
    followup = report["pbs_native_reference_context_sampling_followup"]
    assert followup["implementation_commit"] == "555d013c"
    assert followup["example_selection_policy"] == (
        "one_example_per_stratum_round_robin_by_kind_status"
    )
    assert followup["staging_byte_limit"] == 4_194_304
    assert followup["final_example_byte_limit"] == 64_000
    assert followup["final_example_count_limit"] == 1_000
    assert followup["exact_main_source_rerun_pending"] is True
    assert followup["source_cases_reviewed"] == 0
    assert followup["semantic_relationships_qualified"] is False


def test_preflight_binds_uri_context_v3_candidate_without_source_claims() -> (
    None
):
    candidate = _json(PREFLIGHT)["pbs_native_reference_context_v3_candidate"]
    assert candidate["schema_version"] == 3
    assert candidate["implementation_commit"] == "48c2a7c5"
    assert candidate["validation_commit"] == "ecdd34e8"
    assert candidate["exact_main_run_status"] == "passed"
    assert candidate["exact_main_run_id"] == 40091358786
    assert candidate["source_cases_reviewed"] == 0
    assert candidate["semantic_relationships_qualified"] is False
    assert candidate["source_values_emitted"] is False
    assert candidate["external_targets_fetched"] is False


def test_preflight_successor_preserves_the_snapshot_chain() -> None:
    report = _json(PREFLIGHT)
    encoding = report["pbs_reference_context_receipt_encoding"]
    assert encoding["encoding"] == "zlib-base64-json"
    assert encoding["uncompressed_context_byte_limit"] == 4_194_304
    assert encoding["compressed_receipt_byte_limit"] == 32_000
    assert encoding["value_free_complete_profile_preserved"] is True
    assert encoding["semantic_relationships_qualified"] is False
    assert (
        report["reference_packet_coverage_followup"]["hosted_recheck"]
        == "exact-main context run 40091358786 passed; 61 bounded examples "
        "prepared; source cases remain unreviewed"
    )
    previous = report["previous_preflight"]
    assert previous["path"].endswith(
        "australian-m112-rights-release-preflight-20261024-76.json"
    )
    assert previous["preserved_unchanged"] is True
    assert (
        hashlib.sha256(PREVIOUS_PREFLIGHT.read_bytes()).hexdigest()
        == previous["sha256"]
    )
    previous_report = _json(PREVIOUS_PREFLIGHT)
    assert previous_report["previous_preflight"]["path"].endswith(
        "australian-m112-rights-release-preflight-20261024-75.json"
    )
    assert (
        previous_report["release_and_admission_boundaries"]["v4_admissions"]
        == 8
    )
    assert (
        previous_report["release_and_admission_boundaries"]["consumer_canaries"]
        == 8
    )
    predecessor_path = ROOT / previous_report["previous_preflight"]["path"]
    predecessor = _json(predecessor_path)
    assert predecessor["previous_preflight"]["path"].endswith(
        "australian-m112-rights-release-preflight-20261024-74.json"
    )
    older_path = ROOT / predecessor["previous_preflight"]["path"]
    older = _json(older_path)
    assert older["previous_preflight"]["path"].endswith(
        "australian-m112-rights-release-preflight-20261024-73.json"
    )


def test_full_local_profile_failure_and_recovery_are_explicit() -> None:
    report = _json(PREFLIGHT)
    profile = report["local_full_profile"]
    assert profile["status"] == "failed_preserved"
    assert profile["passed"] == 7_960
    assert profile["failed"] == 5
    assert profile["skipped"] == 4
    assert 96.82 < profile["coverage_percent"] < 96.84
    assert profile["failure_only_recheck"] == "4 passed"
    assert profile["pbs_date_isolated_recheck"] == "1 passed"
    latest = report["latest_local_full_profile_attempt"]
    assert latest["passed"] == 8073
    assert latest["failed"] == 10
    assert latest["skipped"] == 4
    assert 96.93 < latest["coverage_percent"] < 96.95
    assert latest["status"] == (
        "failed_full_profile_with_exact_input_hash_mismatch_and_transient_environment_failures"
    )
    assert len(latest["failure_nodes"]) == 10


def test_pbs_native_silver_field_state_is_candidate_only() -> None:
    report = _json(PREFLIGHT)
    pbs_silver = report["pbs_native_silver_field_state_current_readback"]
    assert pbs_silver["source_fields"] == 18_208_758
    assert pbs_silver["native_unresolved_fields"] == 955_919
    assert pbs_silver["interpreted_fields"] == 17_252_839
    assert pbs_silver["unavailable_fields"] == 0
    assert pbs_silver["native_values_remain_unresolved"] is True
    assert pbs_silver["candidate_only"] is True
    assert pbs_silver["rights_qualified"] is True
    assert pbs_silver["admitted"] is False
    assert pbs_silver["published"] is False
    assert (
        hashlib.sha256((ROOT / pbs_silver["receipt"]).read_bytes()).hexdigest()
        == pbs_silver["receipt_sha256"]
    )


def test_pbs_native_silver_exact_derived_rights_attestation() -> None:
    binding = _json(PREFLIGHT)[
        "pbs_native_silver_exact_derived_rights_attestation"
    ]
    attestation_path = ROOT / binding["path"]
    assert (
        hashlib.sha256(attestation_path.read_bytes()).hexdigest()
        == binding["sha256"]
    )
    attestation = _json(attestation_path)
    report_binding = attestation["source_report"]
    source_report_path = ROOT / report_binding["path"]
    assert (
        hashlib.sha256(source_report_path.read_bytes()).hexdigest()
        == report_binding["sha256"]
        == binding["report_sha256"]
    )
    source_report = _json(source_report_path)
    output = source_report["candidate_output"]
    assert attestation["authorized_output"] == {
        "dataset": source_report["dataset"],
        "revision": source_report["revision"],
        **{
            key: output[key]
            for key in (
                "output_id",
                "parquet_sha256",
                "parquet_bytes",
                "archive_sha256",
                "member_sha256",
                "native_core_sha256",
            )
        },
    }
    assert attestation["maintainer_response"] == "Attest exact output"
    assert attestation["public_release_rights_attested"] is True
    assert binding["instrument_independently_reviewed"] is False
    assert all(value is False for value in attestation["boundaries"].values())
    assert (
        binding["new_admissions"]
        == binding["consumer_canaries"]
        == binding["publications"]
        == 0
    )


def test_scoped_rights_do_not_cross_object_or_release_boundaries() -> None:
    report = _json(PREFLIGHT)
    july = report["july_2025_mbs_silver"]
    assert len(july["objects"]) == 6
    assert july["public_release_authorized"] is True
    assert july["public_release_performed"] is False
    current_public = july["current_public_tree_readback"]
    assert current_public["dataset"] == (
        "edithatogo/australian-mbs-source-archive"
    )
    assert current_public["revision"] == (
        "42d73b6facac016f14a335d36d83f1a3b630add8"
    )
    assert current_public["anonymous_metadata_identity_verified"] is True
    assert current_public["exact_object_count"] == 6
    assert current_public["public_release_observed"] is True
    assert current_public["current_revision_payload_bytes_reverified"] is False
    assert july["permission_instrument_existence_and_applicability"] == (
        "maintainer_attested_not_independently_reviewed_or_located_at_maintainer_direction"
    )
    august = report["august_2026_mbs_bronze_projections"]
    assert len(august["objects"]) == 4
    assert august["rights_state"] == (
        "maintainer_attested_exact_public_release_permission_for_bronze_projection"
    )
    assert august["public_release_rights_attested"] is True
    assert august["public_release_performed_by_this_action"] is False
    assert august["m108_assessment_derived_output_authority"] == "absent"
    assert all(obj["lineage_complete"] for obj in august["objects"])
    assert all(
        obj["rights_state"] == august["rights_state"]
        for obj in august["objects"]
    )
    cms = report["cms_hcpcs_reference"]
    assert cms["rights_state"] == "permitted"
    assert cms["reviewer_status"] == "approved"
    assert cms["acquisition_time_rights_state_preserved"] == "unknown"
    assert cms["external_publication_authorized"] is False
    assert cms["derived_table_rights_concluded"] is False
    gates = report["release_and_admission_boundaries"]
    assert gates["all_remaining_deferrals_preserved"] is True
    assert gates["deferred_objects"] == 1751
    assert gates["v4_admissions"] == 8
    assert gates["consumer_canaries"] == 8
    assert gates["external_publications_performed"] is False


def test_out_of_denominator_mbs_outputs_remain_a_separate_rights_exception() -> (
    None
):
    report = _json(PREVIOUS_PREFLIGHT)
    exception = report["august_2026_mbs_out_of_denominator_scope_exception"]
    scope = _json(ROOT / exception["path"])
    assert exception["object_count"] == 4
    assert exception["dataset_revision"] == scope["revision"]
    assert exception["outside_frozen_inventory"] is True
    assert exception["frozen_inventory_membership_changed"] is False
    assert scope["scope"]["rights_authorized_by_this_record"] is True
    assert scope["scope"]["rights_state"] == (
        "maintainer_attested_exact_public_release_permission_for_bronze_projection"
    )
    assert scope["scope"]["frozen_m112_object_count"] == 1759
    assert all(
        not item["in_frozen_m112_inventory"] for item in scope["objects"]
    )
    assert all(
        item["rights_state"] == scope["scope"]["rights_state"]
        for item in scope["objects"]
    )
    assert all(
        not item["in_frozen_m112_inventory"] for item in scope["objects"]
    )
    assert scope["scope"]["public_release_performed_by_this_action"] is False


def test_reimbursement_projection_rights_are_bounded_and_do_not_admit() -> None:
    report = _json(PREVIOUS_PREFLIGHT)
    projections = report["reimbursement_atlas_medallion_projections"]
    assert projections["object_count"] == 12
    assert projections["public_redistribution_rights_attested"] is True
    assert projections["public_release_performed"] is False
    assert projections["v4_admissions"] == 0
    assert projections["consumer_canaries"] == 0
    assert all(
        item["rights_state"] == projections["rights_state"]
        for item in projections["objects"]
    )
    assert all(item["lineage_complete"] for item in projections["objects"])
    assert all(not item["v4_admission"] for item in projections["objects"])
    assert all(not item["consumer_canary"] for item in projections["objects"])


def test_main_cms_rights_readback_is_preserved_separately_from_m112_counts() -> (
    None
):
    report = _json(PRESERVED_MAIN_PREFLIGHT)

    assert (
        hashlib.sha256(PRESERVED_MAIN_PREFLIGHT.read_bytes()).hexdigest()
        == PRESERVED_MAIN_PREFLIGHT_SHA256
    )
    assert report["cms_hcpcs_reference"]["latest_admission_state"] == "landed"
    assert (
        report["cms_hcpcs_reference"]["latest_admission_reviewer_status"]
        == "approved"
    )
    assert (
        report["cms_hcpcs_reference"]["acquisition_time_rights_state_preserved"]
        == "unknown"
    )
    assert report["release_and_admission_boundaries"]["v4_admissions"] == 3
    assert report["release_and_admission_boundaries"]["consumer_canaries"] == 3


def test_latest_main_rights_snapshot_is_preserved_without_replacing_q3_delta() -> (
    None
):
    report = _json(PRESERVED_AUGUST_RIGHTS_PREFLIGHT)

    assert (
        hashlib.sha256(
            PRESERVED_AUGUST_RIGHTS_PREFLIGHT.read_bytes()
        ).hexdigest()
        == PRESERVED_AUGUST_RIGHTS_PREFLIGHT_SHA256
    )
    assert report["previous_preflight"]["sha256"] == (
        PRESERVED_MAIN_PREFLIGHT_SHA256
    )
    assert report["august_2026_mbs_bronze_projections"][
        "attestation_sha256"
    ] == ("d746b166b6c9de75b0ff00c1a709c8929535dc3373f4bfd574a8727e789b8b9f")
    assert report["cms_hcpcs_reference"][
        "latest_admission_reviewer_status"
    ] == ("approved")
    assert report["release_and_admission_boundaries"]["v4_admissions"] == 3
    assert report["release_and_admission_boundaries"]["consumer_canaries"] == 3


def test_pbs_rights_attestation_is_exact_and_keeps_other_gates_open() -> None:
    report = _json(PREFLIGHT)
    pbs = report["pbs_utilisation_raw_objects"]
    assert pbs["full_object_release_requires_exclusion_review"] is False
    assert pbs["rights_exclusion_fully_resolved_by_exact_attestation"] is True
    assert pbs["permission_instrument_existence_and_applicability"] == (
        "maintainer_attested_not_independently_reviewed"
    )
    assert pbs["exact_rights_attestation_path"].endswith(
        "australian-pbs-utilisation-six-object-rights-attestation-20261020.json"
    )
    assert pbs["public_release_performed_by_this_reconciliation"] is False
    assert pbs["v4_admission"] is False
    assert pbs["consumer_canary"] is False
    assert len(pbs["objects"]) == 6
    assert all(
        obj["rights_state"] == pbs["rights_state"] for obj in pbs["objects"]
    )
    limited_screen = pbs["limited_vocabulary_screen"]
    assert (
        limited_screen["results"]["full_vocabulary_exclusion_review_complete"]
        is False
    )
    assert (
        limited_screen["full_object_release_requires_exclusion_review"] is False
    )
    assert (
        limited_screen["rights_exclusion_fully_resolved_by_exact_attestation"]
        is True
    )


def test_q1_hr_exact_hosted_identity_is_in_current_preflight() -> None:
    report = _json(PREFLIGHT)
    q1 = report["q1_hr_admission"]
    assert q1["workflow_run_id"] == 39575404598
    assert q1["workflow_commit"] == "b6e8a8e4f6d633dfea0056104b62972a669c1b3e"
    assert q1["admissions"] == q1["consumer_canaries"] == 1
    assert q1["source_values_or_rows_interpreted"] is False
    assert q1["reader_cache_bytes_after_close"] == 0
    receipt_path = ROOT / q1["path"]
    assert hashlib.sha256(receipt_path.read_bytes()).hexdigest() == q1["sha256"]


def test_historical_workbook_timeout_retry_scope_is_exact_and_qualified() -> (
    None
):
    report = _json(PREFLIGHT)
    workbook_retry = report["historical_workbook_six_member_runtime_retry"]
    assert workbook_retry["original_run_id"] == 39724026209
    assert workbook_retry["successful_members"] == 91
    assert workbook_retry["cancelled_groups"] == [65, 71, 80, 84, 86, 87]
    assert workbook_retry["retry_job_timeout_minutes"] == 60
    assert workbook_retry["retry_qualified"] is True
    assert workbook_retry["new_sources"] == 0
    assert workbook_retry["new_admissions"] == 0
    for item in workbook_retry["incomplete_receipts"]:
        assert _json(ROOT / item["path"])["status"] == "incomplete"
        assert (
            hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
            == item["sha256"]
        )


def test_two_run_reconciler_qualifies_exact_candidate_cohort() -> None:
    report = _json(PREFLIGHT)["historical_workbook_two_run_reconciler"]
    assert report["original_successes"] == 85
    assert report["required_retry_groups"] == [65, 71, 80, 84, 86, 87]
    assert report["requires_distinct_run_and_commit_per_group"] is True
    assert report["actual_retry_qualified"] is True
    assert report["all_91_qualified"] is True
    assert report["new_admissions"] == 0


def test_historical_workbook_candidate_output_inventory_keeps_gates_closed() -> (
    None
):
    report = _json(PREFLIGHT)["historical_workbook_candidate_output_inventory"]
    assert report["original_run_id"] == 39724026209
    assert report["retry_run_id"] == 39891918206
    assert report["all_91_qualified"] is True
    assert report["candidate_output_count"] == 91
    assert report["native_unresolved_cells"] == 310_177_657
    assert report["interpreted_cells"] == 0
    assert (
        hashlib.sha256((ROOT / report["receipt"]).read_bytes()).hexdigest()
        == report["receipt_sha256"]
    )
    assert report["field_state"] == "native_unresolved"
    assert report["rights_qualified"] is True
    assert report["admitted"] is False
    assert report["published"] is False


def test_historical_workbook_rights_attestation_binds_exact_91_outputs() -> (
    None
):
    preflight = _json(PREFLIGHT)
    binding = preflight["historical_workbook_91_derived_rights_attestation"]
    attestation_path = ROOT / binding["path"]
    assert (
        hashlib.sha256(attestation_path.read_bytes()).hexdigest()
        == binding["sha256"]
    )
    attestation = _json(attestation_path)
    cohort_binding = attestation["cohort_report"]
    cohort_path = ROOT / cohort_binding["path"]
    assert (
        hashlib.sha256(cohort_path.read_bytes()).hexdigest()
        == cohort_binding["sha256"]
    )
    cohort = _json(cohort_path)
    expected = {
        int(group): {
            "group": int(group),
            **{
                key: entry[key]
                for key in (
                    "output_id",
                    "parquet_sha256",
                    "parquet_bytes",
                    "source_sha256",
                    "member_sha256",
                    "member_path_sha256",
                )
            },
        }
        for group, entry in cohort["candidate_outputs_by_group"].items()
    }
    authorized_outputs = attestation["authorized_outputs"]
    assert len(authorized_outputs) == binding["output_count"] == 91
    assert len({entry["group"] for entry in authorized_outputs}) == 91
    assert len({entry["output_id"] for entry in authorized_outputs}) == 91
    actual = {entry["group"]: entry for entry in authorized_outputs}
    assert len(expected) == len(actual) == binding["output_count"] == 91
    assert actual == expected
    assert len({entry["output_id"] for entry in actual.values()}) == 91
    assert (
        attestation["maintainer_response"] == "Attest permission covers all 91"
    )
    assert attestation["public_release_rights_attested"] is True
    assert binding["instrument_independently_reviewed"] is False
    assert all(value is False for value in attestation["boundaries"].values())
    assert (
        binding["new_admissions"]
        == binding["consumer_canaries"]
        == binding["publications"]
        == 0
    )
