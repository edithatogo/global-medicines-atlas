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
    DOMAIN,
    FIELD_STATE,
    PACKAGE,
    REFERENCE_REVIEW,
    SCREEN,
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
        REFERENCE_REVIEW,
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
