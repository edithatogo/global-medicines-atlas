"""PBS field states partition the pinned source without value promotion."""

import hashlib
import json
from pathlib import Path

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
    FIELD_STATE,
    PACKAGE,
    REFERENCE_PACKET,
    REFERENCE_REVIEW,
    REFERENCE_SCREEN,
    SCREEN,
    SUPERSEDED_REPORT,
    reconcile_pbs_field_states,
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
        "interpreted": 43_465,
        "native_unresolved": 18_208_758 - 43_465,
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
            "The 46 deterministic value-free cases remain unreviewed; the "
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
    assert report["rights_conclusion_changed"] is False


def test_tampered_prior_field_state_receipt_is_rejected(tmp_path: Path):
    for relative in (
        PACKAGE,
        SCREEN,
        REFERENCE_SCREEN,
        CONTEXT_SCREEN,
        REFERENCE_PACKET,
        REFERENCE_REVIEW,
        SUPERSEDED_REPORT,
        DOMAIN,
        INVENTORY,
        OBSERVED,
        DATE_PROFILE,
        DATE_OCCURRENCE_CROSSWALK,
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
    destination = tmp_path / FIELD_STATE
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = ROOT / FIELD_STATE
    value = json.loads(source.read_bytes())
    value["field_state_coverage"]["source_fields"] -= 1
    destination.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="receipt digest differs"):
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
        row["semantic_interpretation"]["meaning"]
        == "restriction-associated native text occurrence"
        and row["semantic_interpretation"]["rule"]
        == "exact direct text or tail slot on the pinned PBS prescribing-texts restriction QName path"
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
