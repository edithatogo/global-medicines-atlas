"""PBS field states partition the pinned source without value promotion."""

import json
from pathlib import Path

import pytest

from global_medicines_atlas.pbs_domain_field_semantics import (
    DATE_PROFILE,
    INVENTORY,
    OBSERVED,
)
from global_medicines_atlas.pbs_field_reconciliation import (
    DOMAIN,
    FIELD_STATE,
    PACKAGE,
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
        else:
            assert row["interpretation_evidence"] is None
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
