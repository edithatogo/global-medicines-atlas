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
    DOMAIN,
    FIELD_STATE,
    PACKAGE,
    REFERENCE_REVIEW,
    REFERENCE_SCREEN,
    SCREEN,
    SUPERSEDED_REPORT,
    reconcile_pbs_field_states,
)

ROOT = Path(__file__).resolve().parents[1]


def test_every_pinned_field_has_one_evidenced_state():
    report = reconcile_pbs_field_states(ROOT)
    coverage = report["field_state_coverage"]
    assert coverage == {
        "interpreted": 17_252_839,
        "native_unresolved": 955_919,
        "unavailable": 0,
        "source_fields": 18_208_758,
        "denominator_closed": True,
        "all_native_values_remain_unresolved": True,
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
        row["state"] in {"interpreted", "native_unresolved"}
        for row in report["path_reconciliation"]
    )
    for role, row in report["role_reconciliation"].items():
        assert row["state"] in {"interpreted", "native_unresolved"}
        if row["state"] == "interpreted":
            assert row["interpretation_evidence"] is not None, role
            assert (
                row["interpretation_evidence"]["value_interpretation"] is False
            )
        elif role != "references":
            assert row["interpretation_evidence"] is None
    reference = report["role_reconciliation"]["references"]
    assert reference["state"] == "native_unresolved"
    assert (
        reference["interpretation_evidence"]["semantic_relationships_qualified"]
        is False
    )
    assert (
        report["source_local_reference_review"]["screen_reference_denominator"]
        == 2_160_066
    )
    assert report["source"]["reference_screen_run_id"] == "40076190245"
    assert report["source"]["reference_screen_workflow_commit"] == (
        "b3139f9c655f48ccbb7a1714712219ac2281d838"
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
    assert report["source"]["reference_context_screen_run_id"] == "40091358786"
    assert report["source"]["reference_context_screen_workflow_commit"] == (
        "a198ffff88531f06a34e4f237af6d55dfc74260a"
    )
    context_screen = report["source_local_reference_review"]["context_screen"]
    assert context_screen == {
        "status": "value_free_context_screen_reconciled",
        "workflow_run_id": "40091358786",
        "workflow_commit": "a198ffff88531f06a34e4f237af6d55dfc74260a",
        "receipt_sha256": "5bcc25fef1ad5a1a68a05fdc943f5b96e89848b56d5b6c506e9cba49d3b9db37",
        "receipt_file_sha256": "1bed1a970d599e2bf8cc422352bced094c9568afd4776930b9df2a01d0273313",
        "source_receipt_sha256": "a5eb06cf7e655eb0e0d8fe5d244297721ebede51e96c237333f7dffd76e1ccd1",
        "source_revision": "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7",
        "source_member_sha256": "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43",
        "source_native_digest": "890c607f0e8c9de95c37770610fdc51fd241ea97210ef5ea61d7ad22fd228a25",
        "schema_version": 3,
        "strata_count": 184,
        "examples_emitted": 61,
        "examples_omitted": 2_160_005,
        "sample_summary": {
            "examples_emitted": 61,
            "no_exact_literal": 52,
            "unique_exact_literal": 9,
            "sampled_reference_kind_counts": {"rdf_resource": 61},
            "distinct_predicate_qname_count": 2,
            "nearest_subject_elements": 0,
        },
        "external_targets_fetched": 0,
        "uri_resolution_performed": False,
        "uri_resolution_screen_performed": True,
        "unique_exact_literal_no_xml_base_candidates": 2_086_489,
        "source_values_emitted": False,
        "semantic_relationships_qualified": False,
        "calibration_note": (
            "The bounded sample is value-free diagnostic context; it has no "
            "reviewed semantic labels or negative controls and does not "
            "qualify matcher behavior."
        ),
    }
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
        REFERENCE_REVIEW,
        SUPERSEDED_REPORT,
        DOMAIN,
        INVENTORY,
        OBSERVED,
        DATE_PROFILE,
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
        evidence = report["role_reconciliation"][role][
            "interpretation_evidence"
        ]
        assert evidence["domain"] == "price"
        assert "payable benefit or patient cost" in evidence["limits"][0]
    for role in ("restrictions", "prescribing_rules"):
        evidence = report["role_reconciliation"][role][
            "interpretation_evidence"
        ]
        assert evidence["domain"] == "restriction"
        assert evidence["limits"]


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


def test_reference_review_requires_v2_context_screen(monkeypatch):
    def mutate(envelope):
        envelope["report"]["source_context_screen"]["schema_version"] = 1
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
