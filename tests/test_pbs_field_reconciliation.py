"""PBS field states partition the pinned source without value promotion."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import global_medicines_atlas.pbs_field_reconciliation as reconciliation
from global_medicines_atlas.pbs_domain_field_semantics import (
    DATE_PROFILE,
    INVENTORY,
    OBSERVED,
)
from global_medicines_atlas.pbs_field_reconciliation import (
    CONTEXT_SCREEN,
    CURRENT_RECONCILIATION,
    DATE_OCCURRENCE_CROSSWALK,
    DOMAIN,
    DOMAIN_V4,
    FIELD_STATE,
    PACKAGE,
    REFERENCE_PACKET,
    REFERENCE_REVIEW,
    REFERENCE_SCREEN,
    SCREEN,
    SOURCE_FIELDS,
    SUPERSEDED_REPORT,
    reconcile_pbs_field_states,
    reconcile_pbs_field_states_v5,
    reconcile_pbs_field_states_v6,
    reconcile_pbs_field_states_v7,
    reconcile_pbs_field_states_v8,
)
from global_medicines_atlas.pbs_reference_case_adjudication import (
    ADJUDICATION_PATH,
)
from global_medicines_atlas.pbs_reference_context import (
    screen_reference_context,
)

ROOT = Path(__file__).resolve().parents[1]


def test_context_reconciliation_accepts_balanced_sampling_policy(
    monkeypatch: pytest.MonkeyPatch,
):
    context = screen_reference_context(
        b'<root xmlns="http://schema.pbs.gov.au/" '
        b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        b'xmlns:xlink="http://www.w3.org/1999/xlink" '
        b'xmlns:xml="http://www.w3.org/XML/1998/namespace">'
        b'<edge rdf:resource="unmatched"/>'
        b'<target xml:id="target-id"/><link xlink:href="#target-id"/>'
        b"</root>"
    )
    monkeypatch.setattr(
        reconciliation, "REFERENCE_FIELDS", context["reference_occurrences"]
    )

    assert reconciliation._context_screen_matches(
        context, schema_version=context["schema_version"]
    )


def test_every_pinned_field_has_one_evidenced_state():
    report = reconcile_pbs_field_states(ROOT)
    coverage = report["field_state_coverage"]
    assert coverage == {
        "interpreted": 934_628,
        "native_unresolved": 18_208_758 - 934_628,
        "unavailable": 0,
        "source_fields": 18_208_758,
        "denominator_closed": True,
        "all_native_values_remain_unresolved": True,
        "semantic_field_states_distinct_from_structural_destinations": True,
    }
    assert (
        sum(
            row["field_count"] for row in report["role_reconciliation"].values()
        )
        == coverage["source_fields"]
    )
    assert len(report["path_reconciliation"]) == 5_163
    assert (
        sum(row["field_count"] for row in report["path_reconciliation"])
        == coverage["source_fields"]
    )
    assert all(
        row["semantic_state"] in {"interpreted", "native_unresolved"}
        for row in report["path_reconciliation"]
    )
    for role, row in report["role_reconciliation"].items():
        assert row["structural_state"] in {
            "structural_destination_mapped",
            "unmapped_native",
        }
        if row["structural_state"] == "structural_destination_mapped":
            assert row["structural_evidence"] is not None, role
            assert row["structural_evidence"]["evidence_kind"] == (
                "structural_destination_only"
            )
            assert row["structural_evidence"]["value_interpretation"] is False
        elif role != "references":
            assert row["structural_evidence"] is None
    reference = report["role_reconciliation"]["references"]
    assert reference["structural_state"] == "unmapped_native"
    assert (
        reference["structural_evidence"]["semantic_relationships_qualified"]
        is False
    )
    assert (
        report["source_local_reference_review"]["screen_reference_denominator"]
        == 2_160_066
    )
    assert report["source"]["reference_screen_run_id"] == "40103169910"
    assert report["source"]["reference_screen_workflow_commit"] == (
        "83465c87d5952e123cedd93a02b1ec9b4daa4eb4"
    )
    assert report["source_local_reference_review"]["per_kind_screen"] == {
        "rdf_resource": {
            "reference_fields": 1_167_610,
            "semantic_links_qualified": False,
            "status_counts": {
                "no_exact_literal": 73_577,
                "unique_exact_literal": 1_094_033,
            },
        },
        "xlink_href": {
            "reference_fields": 992_456,
            "semantic_links_qualified": False,
            "status_counts": {"unique_exact_literal": 992_456},
        },
    }
    assert report["source"]["reference_context_screen_run_id"] == "40103169910"
    assert report["source"]["reference_context_screen_workflow_commit"] == (
        "83465c87d5952e123cedd93a02b1ec9b4daa4eb4"
    )
    context_screen = report["source_local_reference_review"]["context_screen"]
    assert context_screen == {
        "status": "value_free_context_screen_reconciled",
        "workflow_run_id": "40103169910",
        "workflow_commit": "83465c87d5952e123cedd93a02b1ec9b4daa4eb4",
        "receipt_sha256": "7f223a138a89064c4dbdaad375174f5584cd0de1871dc34735167a3d670fe688",
        "receipt_file_sha256": "62a01d660dc8e59bcef39768f64a9deda10bc5a58ae899e3f138ec2816862722",
        "source_receipt_sha256": "a5eb06cf7e655eb0e0d8fe5d244297721ebede51e96c237333f7dffd76e1ccd1",
        "source_revision": "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7",
        "source_member_sha256": "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43",
        "source_native_digest": "890c607f0e8c9de95c37770610fdc51fd241ea97210ef5ea61d7ad22fd228a25",
        "schema_version": 3,
        "strata_count": 184,
        "examples_emitted": 46,
        "examples_omitted": 2_160_020,
        "sample_summary": {
            "examples_emitted": 46,
            "no_exact_literal": 11,
            "unique_exact_literal": 35,
            "sampled_reference_kind_counts": {
                "rdf_resource": 29,
                "xlink_href": 17,
            },
            "distinct_predicate_qname_count": 17,
            "nearest_subject_elements": 8,
        },
        "external_targets_fetched": 0,
        "uri_resolution_performed": False,
        "uri_resolution_screen_performed": True,
        "unique_exact_literal_no_xml_base_candidates": 2_086_489,
        "source_values_emitted": False,
        "semantic_relationships_qualified": False,
        "calibration_note": (
            "The 46 deterministic value-free cases have structural pointer "
            "roles reviewed; semantic relationships remain unreviewed. The "
            "sample is not probability-based and cannot estimate semantic "
            "match precision. Matcher behavior remains unqualified."
        ),
    }
    packet = report["source_local_reference_review"]["review_packet"]
    assert packet["cases"] == 46
    assert packet["adjudicated_cases"] == 0
    assert packet["semantic_relationships_qualified"] is False
    assert report["supersedes_report"]["path"] == SUPERSEDED_REPORT
    assert (
        report["source_local_reference_review"]["reference_role_field_count"]
        == reference["field_count"]
    )
    assert report["date_role_overlay"]["field_count"] == 2_800
    assert report["date_role_overlay"]["additive_to_denominator"] is False
    assert report["non_claims"]["cross_era_or_jurisdiction_pooling"] is False
    assert report["non_claims"]["current_listing_status"] is False
    assert report["non_claims"]["patient_rates"].startswith("unavailable:")
    assert report["domain_semantics_qualified"] is False
    assert report["bounded_domain_semantics_qualified"] is True
    assert report["rights_conclusion_changed"] is False


def test_v4_domain_semantics_bind_without_reclassifying_native_values():
    report = reconcile_pbs_field_states(ROOT)
    bounded = report["bounded_domain_semantics"]

    assert bounded["path"] == DOMAIN_V4
    assert bounded["profile_id"] == (
        "pbs-v3.1-pinned-2026-04-01-domain-fields-v4"
    )
    assert bounded["source_member_sha256"] == (
        "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
    )
    assert bounded["complete_domain_semantics_qualified"] is False
    assert bounded["counts_are_additive_to_field_partition"] is False
    assert bounded["field_state_partition"] == {
        "interpreted": 934_628,
        "native_unresolved": 18_208_758 - 934_628,
        "unavailable": 0,
        "source_fields": 18_208_758,
        "newly_interpreted_native_value_fields": 0,
        "state_counts_changed": False,
        "all_native_values_remain_unresolved": True,
    }
    assert bounded["qualified_domains"]["status"]["field_count"] == 0
    assert bounded["qualified_domains"]["price"]["field_count"] == (11_539_739)


def test_v5_adds_direct_date_grammar_without_changing_field_states():
    report = reconcile_pbs_field_states_v5(ROOT)
    bounded = report["bounded_domain_semantics_v5"]

    assert report["profile_id"] == "pbs-v3-2026-04-01-field-state-v5"
    assert bounded["path"].endswith(
        "pbs-domain-field-semantics-20261025-v5.json"
    )
    assert bounded["qualified_lexical_grammar"] == {
        "source_schema_field": "restriction_effective_date_text",
        "field_count": 3_028,
        "grammar": "YYYY-MM-DD (XML Schema date lexical representation)",
        "archive_schema_version": "3.1",
        "documentation_release": "3.1.9",
        "schema_patch_bound": False,
        "native_values_validated": False,
    }
    assert bounded["field_state_partition"] == {
        "interpreted": 934_628,
        "native_unresolved": 18_208_758 - 934_628,
        "unavailable": 0,
        "source_fields": 18_208_758,
        "state_counts_changed": False,
        "newly_interpreted_native_value_fields": 0,
    }
    assert (
        report["source_local_reference_review"][
            "semantic_relationships_qualified"
        ]
        is False
    )
    assert report["non_claims"]["current_listing_status"] is False
    assert report["non_claims"]["patient_rates"].startswith("unavailable:")


def test_v6_qualifies_only_exact_same_member_xlink_targets():
    report = reconcile_pbs_field_states_v6(ROOT)
    coverage = report["field_state_coverage"]
    links = report["source_local_xlink_link_semantics"]
    xlink_rows = [
        row
        for row in report["path_reconciliation"]
        if "{http:~1~1www.w3.org~11999~1xlink}href" in row["schema_path"]
    ]

    assert report["profile_id"] == "pbs-v3-2026-04-01-field-state-v6"
    assert coverage["source_fields"] == 18_208_758
    assert coverage["interpreted"] == 1_927_084
    assert coverage["native_unresolved"] == 16_281_674
    assert coverage["unavailable"] == 0
    assert sum(row["field_count"] for row in xlink_rows) == 992_456
    assert len(xlink_rows) == 186
    assert all(row["semantic_state"] == "interpreted" for row in xlink_rows)
    assert links["same_member_unique_xml_id_targets"] == 992_456
    assert links["reviewed_same_member_positive_examples"] == 17
    assert links["negative_control_cases"] == 11
    assert links["other_rdf_local_candidate_cases"] == 18
    assert links["semantic_precision_or_recall_estimated"] is False
    assert links["pbs_predicate_or_clinical_meaning_qualified"] is False
    assert links["edge_payload_emitted"] is False
    assert links["source_values_emitted"] is False
    assert coverage["interpreted"] + coverage["native_unresolved"] == 18_208_758


def test_v7_qualifies_generic_rdf_resource_field_role_without_edges():
    report = reconcile_pbs_field_states_v7(ROOT)
    coverage = report["field_state_coverage"]
    references = report["source_local_rdf_resource_semantics"]
    rdf_rows = [
        row
        for row in report["path_reconciliation"]
        if "{http:~1~1www.w3.org~11999~102~122-rdf-syntax-ns#}resource"
        in row["schema_path"]
    ]

    assert report["profile_id"] == "pbs-v3-2026-04-01-field-state-v7"
    assert coverage == {
        "interpreted": 3_086_366,
        "native_unresolved": 15_122_392,
        "unavailable": 0,
        "source_fields": 18_208_758,
        "denominator_closed": True,
        "all_native_values_remain_unresolved": False,
        "semantic_field_states_distinct_from_structural_destinations": True,
    }
    assert len(rdf_rows) == 370
    assert sum(row["field_count"] for row in rdf_rows) == 1_167_610
    assert (
        sum(
            row["field_count"]
            for row in rdf_rows
            if row["semantic_interpretation"]["domain"]
            == "amt_literal_reference_resource"
        )
        == 8_328
    )
    assert all(row["semantic_state"] == "interpreted" for row in rdf_rows)
    assert references["rdf_resource_fields"] == 1_167_610
    assert references["newly_interpreted_generic_resource_references"] == (
        1_159_282
    )
    assert references["target_identity_resolution_qualified"] is False
    assert references["semantic_relationships_qualified"] is False
    assert references["edge_payload_emitted"] is False
    assert references["source_values_emitted"] is False


def test_v7_rejects_changed_rdf_screen_outcomes(
    monkeypatch: pytest.MonkeyPatch,
):
    relative_path = reconciliation.URI_SCREEN_V3

    def mutate(envelope: dict[str, Any]) -> None:
        envelope["report"]["qualification"]["outcome_counts_by_qname"][
            "rdf:resource"
        ]["absolute_uri_unique_candidate"] += 1

    _intercept_json_loads(monkeypatch, relative_path, mutate)

    with pytest.raises(
        ValueError, match="PBS RDF resource screen qualification differs"
    ):
        reconcile_pbs_field_states_v7(ROOT)


def test_v7_retained_report_is_canonical_and_digest_bound():
    report_path = ROOT / reconciliation.CURRENT_RECONCILIATION_V7
    envelope = json.loads(report_path.read_bytes())
    canonical = json.dumps(
        envelope["report"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    assert hashlib.sha256(canonical).hexdigest() == envelope["report_sha256"]
    assert envelope["report"]["profile_id"] == (
        "pbs-v3-2026-04-01-field-state-v7"
    )


def test_v8_qualifies_generic_rdf_about_subject_role_without_resolution():
    report = reconcile_pbs_field_states_v8(ROOT)
    coverage = report["field_state_coverage"]
    references = report["source_local_rdf_about_semantics"]
    about_rows = [
        row
        for row in report["path_reconciliation"]
        if "{http:~1~1www.w3.org~11999~102~122-rdf-syntax-ns#}about"
        in row["schema_path"]
    ]

    assert report["profile_id"] == "pbs-v3-2026-04-01-field-state-v8"
    assert coverage["interpreted"] == 3_096_734
    assert coverage["native_unresolved"] == 15_112_024
    assert coverage["unavailable"] == 0
    assert coverage["source_fields"] == 18_208_758
    assert coverage["denominator_closed"] is True
    assert len(about_rows) == 34
    assert sum(row["field_count"] for row in about_rows) == 10_368
    assert all(row["semantic_state"] == "interpreted" for row in about_rows)
    assert references["newly_interpreted_subject_iri_references"] == 10_368
    assert references["rdf_about_fields"] == 10_368
    assert references["subject_iri_resolution_qualified"] is False
    assert references["semantic_relationships_qualified"] is False
    assert references["edge_payload_emitted"] is False
    assert references["source_values_read"] is False
    assert references["source_values_emitted"] is False


def test_v8_rejects_changed_rdf_about_definition_count(
    monkeypatch: pytest.MonkeyPatch,
):
    def mutate(envelope: dict[str, Any]) -> None:
        envelope["report"]["qualification"]["definition_counts_by_qname"][
            "rdf:about"
        ] += 1

    _intercept_json_loads(monkeypatch, reconciliation.URI_SCREEN_V3, mutate)

    with pytest.raises(
        ValueError, match="PBS RDF about screen qualification differs"
    ):
        reconcile_pbs_field_states_v8(ROOT)


def test_v8_retained_report_is_canonical_and_digest_bound():
    report_path = ROOT / reconciliation.CURRENT_RECONCILIATION_V8
    envelope = json.loads(report_path.read_bytes())
    canonical = json.dumps(
        envelope["report"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    assert hashlib.sha256(canonical).hexdigest() == envelope["report_sha256"]
    assert envelope["report"]["profile_id"] == (
        "pbs-v3-2026-04-01-field-state-v8"
    )


def test_reference_case_structural_review_keeps_semantic_links_unqualified():
    report = reconcile_pbs_field_states(ROOT)
    review = report["source_local_reference_review"]["structural_case_review"]

    assert review["path"] == ADJUDICATION_PATH
    assert review["cases"] == 46
    assert review["structural_pointer_roles_supported"] == 46
    assert review["no_target_hard_negatives"] == 11
    assert review["semantic_relationships_qualified"] is False
    assert review["edges_emitted"] is False
    assert (
        report["source_local_reference_review"]["review_packet"][
            "adjudicated_cases"
        ]
        == 0
    )


def test_date_population_reconciliation_binds_current_reports_and_arithmetic():
    path = ROOT / (
        "quality/qualifications/"
        "pbs-date-field-population-reconciliation-20261025-r2.json"
    )
    envelope = json.loads(path.read_bytes())
    report = envelope["report"]
    canonical = json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == envelope["report_sha256"]
    assert report["schema_version"] == 2
    assert report["profile_id"] == (
        "pbs-v3.1-pinned-2026-04-01-date-fields-reconciliation-v2"
    )
    assert report["evidence"]["field_state"]["path"] == (CURRENT_RECONCILIATION)
    assert report["evidence"]["field_state"]["file_sha256"] == (
        hashlib.sha256((ROOT / CURRENT_RECONCILIATION).read_bytes()).hexdigest()
    )
    assert report["evidence"]["domain_semantics_v4"] == {
        "file_sha256": "1336cd51392a08c29928cb66ae7f80a65589ceaa17b2c0c70f33c0d9a72c40c8",
        "path": DOMAIN_V4,
        "report_sha256": "f2813888a484c0b36f4dbfbf967a418f07215f15c5379883789ecb8407fc18db",
    }
    assert report["supersedes_report"]["path"].endswith(
        "pbs-date-field-population-reconciliation-20261025.json"
    )

    populations = report["date_populations"]
    profile = populations["date_profile"]
    roles = profile["role_counts"]
    assert profile["role_slots"] == (
        roles["pbs_effective_date"]
        + roles["schedule_effective_date"]
        + roles["schedule_dct_valid"]
    )
    assert (
        profile["converted"] + profile["recognized_slot_missing"]
        == (profile["role_slots"])
    )
    crosswalk = populations["exact_occurrence_crosswalk"]
    assert (
        crosswalk["item_effective_date_profile_fields"]
        == roles["pbs_effective_date"]
    )
    assert (
        crosswalk["direct_restriction_effective_date_path_fields"]
        == (
            populations["domain_role_counts"][
                "direct_restriction_effective_date_literal"
            ]
        )
    )
    assert crosswalk["overlap_fields"] == 0
    assert (
        crosswalk["item_effective_date_profile_fields"]
        + crosswalk["direct_restriction_effective_date_path_fields"]
        == 5_826
    )

    evidence = report["evidence"]
    for name, expected_path in (
        ("domain_semantics", DOMAIN),
        ("field_state", CURRENT_RECONCILIATION),
        ("date_crosswalk", DATE_OCCURRENCE_CROSSWALK),
    ):
        binding = evidence[name]
        assert binding["path"] == expected_path
        referenced = json.loads((ROOT / binding["path"]).read_bytes())
        assert (
            hashlib.sha256((ROOT / binding["path"]).read_bytes()).hexdigest()
            == (binding["file_sha256"])
        )
        referenced_report = referenced["report"]
        referenced_canonical = json.dumps(
            referenced_report,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        assert (
            hashlib.sha256(referenced_canonical).hexdigest()
            == (referenced["report_sha256"])
        )

    current = json.loads((ROOT / CURRENT_RECONCILIATION).read_bytes())
    coverage = current["report"]["field_state_coverage"]
    assert coverage["source_fields"] == SOURCE_FIELDS
    assert (
        coverage["interpreted"]
        + coverage["native_unresolved"]
        + coverage["unavailable"]
        == SOURCE_FIELDS
    )
    assert (
        report["field_state_partition"]["interpreted"]
        == coverage["interpreted"]
    )


def test_tampered_prior_field_state_receipt_is_rejected(tmp_path: Path):
    _copy_reconciliation_inputs(tmp_path)
    destination = tmp_path / FIELD_STATE
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = ROOT / FIELD_STATE
    value = json.loads(source.read_bytes())
    value["field_state_coverage"]["source_fields"] -= 1
    destination.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="receipt digest differs"):
        reconcile_pbs_field_states(tmp_path)


def test_domain_v4_scope_mismatch_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _copy_reconciliation_inputs(tmp_path)
    path = tmp_path / DOMAIN_V4
    envelope = json.loads(path.read_bytes())
    envelope["report"]["scope"]["complete_domain_semantics_qualified"] = True
    canonical = json.dumps(
        envelope["report"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    envelope["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    path.write_text(json.dumps(envelope), encoding="utf-8")
    monkeypatch.setattr(
        reconciliation,
        "DOMAIN_V4_FILE_SHA256",
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        reconciliation, "DOMAIN_V4_REPORT_SHA256", envelope["report_sha256"]
    )

    with pytest.raises(
        ValueError, match="PBS bounded domain-field v4 evidence differs"
    ):
        reconcile_pbs_field_states(tmp_path)


def test_reference_case_receipt_byte_mismatch_is_rejected(tmp_path: Path):
    _copy_reconciliation_inputs(tmp_path)
    path = tmp_path / ADJUDICATION_PATH
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(
        ValueError, match="PBS reference case receipt bytes differ"
    ):
        reconcile_pbs_field_states(tmp_path)


def test_reference_case_review_scope_mismatch_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _copy_reconciliation_inputs(tmp_path)
    path = tmp_path / ADJUDICATION_PATH
    envelope = json.loads(path.read_bytes())
    envelope["report"]["review_scope"]["semantic_relationships_qualified"] = (
        True
    )
    canonical = json.dumps(
        envelope["report"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    envelope["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    path.write_text(json.dumps(envelope), encoding="utf-8")
    monkeypatch.setattr(
        reconciliation,
        "REFERENCE_CASE_FILE_SHA256",
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        reconciliation,
        "REFERENCE_CASE_REPORT_SHA256",
        envelope["report_sha256"],
    )

    def changed_review_report(root: Path) -> dict[str, object]:
        return envelope["report"] if root else {}

    monkeypatch.setattr(
        reconciliation,
        "validate_reference_case_adjudication",
        changed_review_report,
    )

    with pytest.raises(
        ValueError, match="PBS reference case review boundary differs"
    ):
        reconcile_pbs_field_states(tmp_path)


def test_v4_domain_recomputation_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
):

    def changed_domain_report(root: Path) -> dict[str, object]:
        return {} if root else {"unexpected": True}

    monkeypatch.setattr(
        reconciliation,
        "qualify_pbs_domain_fields_v4",
        changed_domain_report,
    )

    with pytest.raises(
        ValueError, match="PBS bounded domain-field v4 evidence differs"
    ):
        reconcile_pbs_field_states(ROOT)


def _copy_reconciliation_inputs(tmp_path: Path) -> None:
    for relative in (
        PACKAGE,
        SCREEN,
        REFERENCE_SCREEN,
        CONTEXT_SCREEN,
        REFERENCE_PACKET,
        ADJUDICATION_PATH,
        REFERENCE_REVIEW,
        FIELD_STATE,
        SUPERSEDED_REPORT,
        DOMAIN,
        DOMAIN_V4,
        INVENTORY,
        OBSERVED,
        DATE_PROFILE,
        DATE_OCCURRENCE_CROSSWALK,
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())


def test_tampered_exact_date_profile_digest_is_rejected(tmp_path: Path):
    _copy_reconciliation_inputs(tmp_path)
    date_profile = tmp_path / DATE_PROFILE
    date_profile.write_bytes(date_profile.read_bytes() + b" ")
    with pytest.raises(ValueError, match="exact-source date-profile receipt"):
        reconcile_pbs_field_states(tmp_path)


def test_tampered_date_occurrence_crosswalk_digest_is_rejected(
    tmp_path: Path,
):
    _copy_reconciliation_inputs(tmp_path)
    crosswalk = tmp_path / DATE_OCCURRENCE_CROSSWALK
    crosswalk.write_bytes(crosswalk.read_bytes() + b" ")
    with pytest.raises(
        ValueError, match="exact-source date occurrence crosswalk"
    ):
        reconcile_pbs_field_states(tmp_path)


def test_date_profile_with_expected_digest_but_wrong_binding_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _copy_reconciliation_inputs(tmp_path)
    date_profile = tmp_path / DATE_PROFILE
    value = json.loads(date_profile.read_bytes())
    value["date_profile"]["format"] = "MM/DD/YYYY"
    date_profile.write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setattr(
        reconciliation,
        "DATE_PROFILE_SHA256",
        hashlib.sha256(date_profile.read_bytes()).hexdigest(),
    )
    with pytest.raises(ValueError, match="exact-source item date role"):
        reconcile_pbs_field_states(tmp_path)


def test_date_crosswalk_with_expected_digest_but_wrong_binding_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _copy_reconciliation_inputs(tmp_path)
    crosswalk = tmp_path / DATE_OCCURRENCE_CROSSWALK
    envelope = json.loads(crosswalk.read_bytes())
    envelope["report"]["crosswalk"]["join"]["item_profile_only_fields"] -= 1
    canonical = json.dumps(
        envelope["report"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    envelope["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    crosswalk.write_text(json.dumps(envelope), encoding="utf-8")
    monkeypatch.setattr(
        reconciliation,
        "DATE_OCCURRENCE_CROSSWALK_SHA256",
        hashlib.sha256(crosswalk.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        reconciliation,
        "DATE_OCCURRENCE_CROSSWALK_REPORT_SHA256",
        envelope["report_sha256"],
    )
    with pytest.raises(
        ValueError, match="exact-source date occurrence crosswalk differs"
    ):
        reconcile_pbs_field_states(tmp_path)


def test_interpreted_roles_carry_their_domain_specific_limits():
    report = reconcile_pbs_field_states(ROOT)
    for role in ("prices", "pricing_components"):
        evidence = report["role_reconciliation"][role]["structural_evidence"]
        assert evidence["evidence_kind"] == "structural_destination_only"
        assert evidence["domain"] == "price"
        assert "payable benefit or patient cost" in evidence["limits"][0]
    for role in ("restrictions", "prescribing_rules"):
        evidence = report["role_reconciliation"][role]["structural_evidence"]
        assert evidence["evidence_kind"] == "structural_destination_only"
        assert evidence["domain"] == "restriction"
        assert evidence["limits"]


def test_semantic_adjudication_promotes_only_exact_supported_paths():
    report = reconcile_pbs_field_states(ROOT)
    adjudication = report["semantic_adjudication"]
    assert adjudication["field_count_conserved"] is True
    assert adjudication["source_values_read"] is False
    assert adjudication["source_values_emitted"] is False
    assert adjudication["date_profile_sha256"] == (
        "383f69a7e69e62527b07d45d0833ce21ccaea07e2d7a0b7fbc3d1b9a0f97ecfb"
    )
    assert adjudication["date_profile_item_effective_date_fields"] == 2_798
    crosswalk = adjudication["date_occurrence_crosswalk"]
    assert crosswalk["workflow_run_id"] == "40121732132"
    assert crosswalk["identity"] == "source_field_id_exact_match"
    assert crosswalk["item_profile_only_fields"] == 2_798
    assert crosswalk["restriction_only_fields"] == 3_028
    assert crosswalk["overlap_fields"] == 0
    assert crosswalk["date_role_slots_without_source_field"] == 0
    assert crosswalk["source_values_emitted"] is False
    assert adjudication["interpretations"] == {
        "amt_literal_reference": 8_328,
        "amt_literal_reference_resource": 8_328,
        "item_identity_literal": 2_798,
        "item_effective_date_literal": 2_798,
        "pbs_dollar_amount": 71_668,
        "pbs_patient_contribution_dollar_amount": 2_279,
        "pbs_product_price_dollar_amount": 817_216,
        "product_presentation_label": 12_128,
        "restriction_text": 6_056,
        "restriction_effective_date_literal": 3_028,
        "schedule_metadata_valid_date_literal": 1,
    }
    assert not any(
        row["semantic_interpretation"]["domain"]
        == "classification_code_candidate"
        for row in report["path_reconciliation"]
    )
    assert any(
        "ATC typing is not a source-level assertion" in claim
        for claim in adjudication["explicit_non_claims"]
    )
    assert len(adjudication["explicit_non_claims"]) == 8
    assert any(
        "price" in claim for claim in adjudication["explicit_non_claims"]
    )
    assert any(
        "currentness" in claim for claim in adjudication["explicit_non_claims"]
    )
    assert any(
        "unknown wrappers" in claim
        for claim in adjudication["explicit_non_claims"]
    )
    assert any(
        "not resolved" in claim for claim in adjudication["explicit_non_claims"]
    )


@pytest.mark.parametrize(
    ("path", "state", "domain"),
    [
        (
            "/{http:~1~1schema.pbs.gov.au~1}root/{http:~1~1schema.pbs.gov.au~1}classification/{http:~1~1schema.pbs.gov.au~1}code/text",
            "native_unresolved",
            "classification_code_candidate",
        ),
        (
            "/{http:~1~1schema.pbs.gov.au~1}root/{http:~1~1schema.pbs.gov.au~1}prescribing-texts-list/{http:~1~1schema.pbs.gov.au~1}restriction/attributes/effective-date",
            "interpreted",
            "restriction_effective_date_literal",
        ),
        (
            "/{http:~1~1schema.pbs.gov.au~1}root/{http:~1~1schema.pbs.gov.au~1}schedule/attributes/effective-date",
            "interpreted",
            "schedule_effective_date_literal",
        ),
        (
            "/{http:~1~1schema.pbs.gov.au~1}root/{http:~1~1schema.pbs.gov.au~1}schedule/{http:~1~1schema.pbs.gov.au~1}program/{http:~1~1schema.pbs.gov.au~1}prescribing-rule/{http:~1~1schema.pbs.gov.au~1}product-listing/{http:~1~1schema.pbs.gov.au~1}reimbursement/{http:~1~1schema.pbs.gov.au~1}dpmq/{http:~1~1schema.pbs.gov.au~1}price/{http:~1~1schema.pbs.gov.au~1}amount/text",
            "interpreted",
            "pbs_product_price_dollar_amount",
        ),
        (
            "/{http:~1~1schema.pbs.gov.au~1}root/{http:~1~1schema.pbs.gov.au~1}schedule/{http:~1~1schema.pbs.gov.au~1}program/{http:~1~1schema.pbs.gov.au~1}prescribing-rule/{http:~1~1schema.pbs.gov.au~1}product-listing/{http:~1~1schema.pbs.gov.au~1}reimbursement/{http:~1~1schema.pbs.gov.au~1}dpmq/{http:~1~1schema.pbs.gov.au~1}price/{http:~1~1schema.pbs.gov.au~1}contribution/{http:~1~1schema.pbs.gov.au~1}amount/text",
            "interpreted",
            "pbs_patient_contribution_dollar_amount",
        ),
        (
            "/{http:~1~1schema.pbs.gov.au~1}root/{http:~1~1extension.schema.pbs.gov.au~1}amount/text",
            "native_unresolved",
            None,
        ),
    ],
)
def test_exact_unusual_domain_paths_keep_bounded_semantics(path, state, domain):
    result = reconciliation._semantic_adjudication(path)
    assert result["state"] == state
    assert result["domain"] == domain


def test_exact_item_effective_date_path_has_source_role_only():
    path = (
        "/{http:~1~1schema.pbs.gov.au~1}root/"
        "{http:~1~1schema.pbs.gov.au~1}pharmaceutical-items-list/"
        "{http:~1~1schema.pbs.gov.au~1}pharmaceutical-item/"
        "{http:~1~1schema.pbs.gov.au~1}effective/"
        "{http:~1~1schema.pbs.gov.au~1}date/text"
    )
    result = reconciliation._semantic_adjudication(path)
    assert result == {
        "state": "interpreted",
        "domain": "item_effective_date_literal",
        "meaning": "source PBS item effective-date literal; temporal role only",
        "rule": "exact pinned pharmaceutical-item/effective/date/text QName path and qualified v3 date-role receipt",
    }


def test_restriction_text_is_limited_to_direct_source_slots():
    direct = (
        "/{http:~1~1schema.pbs.gov.au~1}root/"
        "{http:~1~1schema.pbs.gov.au~1}prescribing-texts-list/"
        "{http:~1~1schema.pbs.gov.au~1}restriction/text"
    )
    nested = direct.removesuffix("/text") + (
        "/{http:~1~1docbook.org~1ns~1docbook#}para/text"
    )
    assert reconciliation._semantic_adjudication(direct)["domain"] == (
        "restriction_text"
    )
    assert (
        "reason for subsidisation"
        in reconciliation._semantic_adjudication(direct)["meaning"]
    )
    assert reconciliation._semantic_adjudication(nested)["state"] == (
        "native_unresolved"
    )


def test_versioned_path_qname_matrix_is_reconciled_and_value_free():
    envelope = json.loads((ROOT / CURRENT_RECONCILIATION).read_bytes())
    receipt = envelope["report"]
    canonical = json.dumps(
        receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == envelope["report_sha256"]
    current = reconcile_pbs_field_states(ROOT)
    assert receipt["field_state_coverage"] == current["field_state_coverage"]
    assert receipt["semantic_adjudication"] == current["semantic_adjudication"]
    matrix = receipt["path_reconciliation"]
    assert len(matrix) == 5_163
    assert sum(row["field_count"] for row in matrix) == 18_208_758
    assert all(
        "value" not in row and "source_value" not in row for row in matrix
    )
    restriction_text = [
        row
        for row in matrix
        if row["semantic_interpretation"]["domain"] == "restriction_text"
    ]
    assert {
        row["schema_path"].rsplit("/", maxsplit=1)[-1]
        for row in restriction_text
    } == {
        "text",
        "tail",
    }
    assert len(restriction_text) == 2
    assert all(
        "reason for subsidisation" in row["semantic_interpretation"]["meaning"]
        and row["semantic_interpretation"]["rule"]
        == (
            "exact direct text or tail slot on the pinned PBS "
            "prescribing-texts restriction QName path and official "
            "PBS XML v3.1.9 restriction definition"
        )
        for row in restriction_text
    )
    assert receipt["semantic_adjudication"]["source_values_read"] is False
    assert receipt["semantic_adjudication"]["source_values_emitted"] is False


@pytest.mark.parametrize(
    ("schema_path", "expected"),
    [
        ("/root/attributes/id", "/root"),
        ("/root/child/attributes/id", "/root/child"),
        ("/root/text", "/root"),
        ("/root/tail", "/root"),
    ],
)
def test_entity_path_accepts_native_attributes_and_text(
    schema_path: str, expected: str
):
    assert reconciliation._entity_path(schema_path) == expected


def test_entity_path_rejects_non_field_paths():
    with pytest.raises(
        ValueError, match="PBS schema path does not identify a native field"
    ):
        reconciliation._entity_path("/root/attributes")


def _intercept_json_loads(monkeypatch, relative_path: str, mutate):
    """Mutate one decoded receipt while retaining all other source evidence."""
    target_bytes = (ROOT / relative_path).read_bytes()
    original_loads = json.loads

    def loads(data, *args, **kwargs):
        value = original_loads(data, *args, **kwargs)
        if data == target_bytes:
            mutate(value)
        return value

    monkeypatch.setattr(reconciliation.json, "loads", loads)


def _bypass_preflight_data_reads(monkeypatch):
    """Keep mutations aimed at the reconciler's later partition checks."""
    domain_report = reconciliation.qualify_pbs_domain_fields(ROOT)
    profile = reconciliation.load_observed_profile(ROOT)
    monkeypatch.setattr(
        reconciliation, "qualify_pbs_domain_fields", lambda _root: domain_report
    )
    monkeypatch.setattr(
        reconciliation, "load_observed_profile", lambda _root: profile
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "rejected"),
        ("source_fields", 1),
        ("package_receipt_sha256", "0" * 64),
        ("screen_receipt_sha256", "0" * 64),
    ],
)
def test_tampered_native_field_receipt_is_rejected(
    monkeypatch, field: str, value
):
    def mutate(receipt):
        if field == "status":
            receipt[field] = value
        elif field == "source_fields":
            receipt["field_state_coverage"][field] = value
        else:
            receipt[field] = value

    _intercept_json_loads(monkeypatch, FIELD_STATE, mutate)
    with pytest.raises(
        ValueError, match="PBS native field-state receipt differs"
    ):
        reconcile_pbs_field_states(ROOT)


def test_noncanonical_domain_report_is_rejected(monkeypatch):
    def mutate(envelope):
        envelope["report"]["domains"]["item"]["meaning"] += " tampered"

    _intercept_json_loads(monkeypatch, DOMAIN, mutate)
    with pytest.raises(
        ValueError, match="PBS field-meaning evidence digest differs"
    ):
        reconcile_pbs_field_states(ROOT)


def test_reference_review_per_kind_counts_must_match_exact_screen(monkeypatch):
    def mutate(envelope):
        review = envelope["report"]
        review["exact_source_screen"]["per_kind"]["xlink_href"][
            "status_counts"
        ]["unique_exact_literal"] -= 1
        canonical = json.dumps(
            review,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        envelope["report_sha256"] = hashlib.sha256(canonical).hexdigest()

    _intercept_json_loads(monkeypatch, REFERENCE_REVIEW, mutate)
    with pytest.raises(
        ValueError, match="PBS source-local reference review differs"
    ):
        reconcile_pbs_field_states(ROOT)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("screen_run_id", "40040624594"),
        (
            "screen_workflow_commit",
            "43f72eb7844a1f3adf13ec1fb34788c1bb8faf71",
        ),
        (
            "screen_receipt_sha256",
            "a221facbc5b9bf0250b00d9036d5b909f6408fc99d3af390b687f1f6ad8950b4",
        ),
    ],
)
def test_reference_review_must_bind_the_exact_context_screen(
    monkeypatch, field: str, value: str
):
    def mutate(envelope):
        envelope["report"]["source"][field] = value
        canonical = json.dumps(
            envelope["report"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        envelope["report_sha256"] = hashlib.sha256(canonical).hexdigest()

    _intercept_json_loads(monkeypatch, REFERENCE_REVIEW, mutate)
    with pytest.raises(
        ValueError, match="PBS source-local reference review differs"
    ):
        reconcile_pbs_field_states(ROOT)


def test_reference_review_requires_v3_context_screen(monkeypatch):
    def mutate(envelope):
        envelope["report"]["source_context_screen"]["schema_version"] = 2
        canonical = json.dumps(
            envelope["report"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        envelope["report_sha256"] = hashlib.sha256(canonical).hexdigest()

    _intercept_json_loads(monkeypatch, REFERENCE_REVIEW, mutate)
    with pytest.raises(
        ValueError, match="PBS source-local reference review differs"
    ):
        reconcile_pbs_field_states(ROOT)


def test_context_screen_must_bind_exact_source_and_abstain(monkeypatch):
    def mutate(envelope):
        envelope["report"]["qualification"][
            "semantic_relationships_qualified"
        ] = True
        canonical = json.dumps(
            envelope["report"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        envelope["report_sha256"] = hashlib.sha256(canonical).hexdigest()

    _intercept_json_loads(monkeypatch, CONTEXT_SCREEN, mutate)
    with pytest.raises(
        ValueError, match="PBS source-context screen receipt differs"
    ):
        reconcile_pbs_field_states(ROOT)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda report: report["qualification"]["role_field_counts"].pop(
            "items"
        ),
        lambda report: report["qualification"]["role_field_counts"].__setitem__(
            "items", report["qualification"]["role_field_counts"]["items"] + 1
        ),
    ],
    ids=("missing-role", "non-closing-total"),
)
def test_invalid_observed_role_partition_is_rejected(monkeypatch, mutate):
    def mutate_envelope(envelope):
        mutate(envelope["report"])
        canonical = json.dumps(
            envelope["report"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        envelope["report_sha256"] = hashlib.sha256(canonical).hexdigest()

    observed_path = (
        "quality/qualifications/"
        "pbs-observed-domain-values-qualification-20261022-39672588063.json"
    )
    _bypass_preflight_data_reads(monkeypatch)
    _intercept_json_loads(monkeypatch, observed_path, mutate_envelope)
    with pytest.raises(
        ValueError, match="PBS source role partition does not close"
    ):
        reconcile_pbs_field_states(ROOT)


def test_interpreted_role_count_must_match_domain_evidence(monkeypatch):
    def mutate_envelope(envelope):
        counts = envelope["report"]["qualification"]["role_field_counts"]
        counts["items"] += 1
        counts["historical_records"] -= 1
        canonical = json.dumps(
            envelope["report"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        envelope["report_sha256"] = hashlib.sha256(canonical).hexdigest()

    observed_path = (
        "quality/qualifications/"
        "pbs-observed-domain-values-qualification-20261022-39672588063.json"
    )
    _bypass_preflight_data_reads(monkeypatch)
    _intercept_json_loads(monkeypatch, observed_path, mutate_envelope)
    with pytest.raises(
        ValueError,
        match="PBS interpreted role counts differ from meaning evidence",
    ):
        reconcile_pbs_field_states(ROOT)


def test_path_role_partition_failure_is_rejected(monkeypatch):
    inventory_path = reconciliation.PATH_INVENTORY

    def mutate_inventory(inventory):
        inventory["paths"][0]["native_fields"] += 1

    _bypass_preflight_data_reads(monkeypatch)
    _intercept_json_loads(monkeypatch, inventory_path, mutate_inventory)
    with pytest.raises(
        ValueError, match="PBS schema-path field-state partition does not close"
    ):
        reconcile_pbs_field_states(ROOT)
