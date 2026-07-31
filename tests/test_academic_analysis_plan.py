"""Phase 2 contract tests for the prospective analysis and validation plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError
from scripts.build_academic_analysis_plan import build_analysis_plan_markdown

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/academic-analysis-plan-v1.json"
CONTRACT = ROOT / "research/protocol/academic-analysis-plan-v1.json"
DOCUMENT = ROOT / "docs/research/academic-analysis-plan.md"
DEVIATION_SCHEMA = ROOT / "schemas/academic-deviation-v1.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_analysis_plan_validates_and_keeps_outcomes_separate() -> None:
    schema = _load(SCHEMA)
    Draft202012Validator.check_schema(schema)
    plan = _load(CONTRACT)
    Draft202012Validator(schema).validate(plan)

    assert plan["protocol_identity"]["path"] == (
        "research/protocol/academic-protocol-v1.json"
    )
    assert plan["outcome_dimensions"] == ["regulatory_status", "funding_status"]
    assert plan["joint_outcome_inference"] is False


def test_matching_and_adjudication_are_fail_closed() -> None:
    plan = _load(CONTRACT)
    matching = plan["matching_validation"]
    assert matching["automatic_acceptance"] == "exact_rules_only"
    assert matching["unresolved_state"] == "insufficient_evidence"
    assert matching["material_mismatch_state"] == "inappropriate_comparison"
    assert matching["adjudication"]["independent_reviewers"] >= 2
    assert matching["adjudication"]["consensus_required"] is True
    assert matching["inter_rater"]["agreement_statistics"] == [
        "percent_agreement",
        "cohen_kappa_with_95_percent_ci",
    ]
    assert matching["inter_rater"]["agreement_is_not_validity"] is True


def test_negative_controls_cover_m090_dimensions_and_status_leakage() -> None:
    controls = _load(CONTRACT)["matching_validation"]["negative_controls"]
    dimensions = {control["dimension"] for control in controls}
    assert dimensions == {
        "entity",
        "indication",
        "population",
        "temporal",
        "mapping",
        "status_dimension",
    }
    assert all(control["expected_validity"] != "valid" for control in controls)


def test_missingness_conflicts_denominators_and_uncertainty_are_explicit() -> (
    None
):
    evidence = _load(CONTRACT)["evidence_handling"]
    assert evidence["missingness"]["absence_interpretation"] == (
        "insufficient_evidence_not_negative_status"
    )
    assert evidence["conflicts"]["resolution"] == "retain_all_assertions"
    assert evidence["conflicts"]["silent_overwrite"] is False
    assert {
        item["denominator_id"] for item in evidence["coverage_denominators"]
    } == {
        "catalog_sources",
        "eligible_entities",
        "eligible_assertions",
        "valid_comparisons",
    }
    assert evidence["uncertainty"]["unknowns_reported_separately"] is True


def test_analyses_sensitivities_and_multiplicity_are_bounded() -> None:
    analysis = _load(CONTRACT)["analysis"]
    assert {item["outcome"] for item in analysis["descriptive"]} == {
        "regulatory_status",
        "funding_status",
        "coverage",
        "comparison_validity",
    }
    assert len(analysis["sensitivity"]) >= 4
    assert analysis["multiplicity"]["confirmatory_hypothesis_tests"] == []
    assert analysis["multiplicity"]["p_values"] == "not_planned"
    assert analysis["multiplicity"]["unplanned_analyses"] == "label_exploratory"


@pytest.mark.parametrize(
    "identity",
    ["software", "schemas", "fixtures", "random_seed", "environment"],
)
def test_reproducibility_identities_are_immutable(identity: str) -> None:
    item = _load(CONTRACT)["reproducibility"][identity]
    assert item["mutable_reference_allowed"] is False
    assert item["verification"]


def test_deviation_contract_is_prospective_and_non_destructive() -> None:
    deviations = _load(CONTRACT)["deviations"]
    assert deviations["register_path"] == "research/protocol/deviations.jsonl"
    assert deviations["append_only"] is True
    assert deviations["post_registration_changes_are_amendments"] is True
    assert deviations["undeclared_outcome_switching"] == "prohibited"


def test_deviation_records_have_a_strict_standalone_schema() -> None:
    schema = _load(DEVIATION_SCHEMA)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    record = {
        "schema_id": "global-medicines-atlas.academic-deviation",
        "schema_version": 1,
        "deviation_id": "DEV-0001",
        "recorded_at": "2026-08-01T00:00:00Z",
        "classification": "prospective_amendment",
        "planned_method": "Use exact mappings only.",
        "actual_method": "Also report caveated mappings separately.",
        "reason": "Prespecified robustness extension.",
        "impact": "No outcome switching; labelled sensitivity analysis.",
        "author": "maintainer",
    }
    validator.validate(record)
    with pytest.raises(ValidationError, match="Additional properties"):
        validator.validate({**record, "unregistered_field": "not allowed"})


def test_rendered_analysis_plan_is_committed_and_deterministic() -> None:
    expected = build_analysis_plan_markdown(_load(CONTRACT))
    assert DOCUMENT.read_text(encoding="utf-8") == expected
    assert expected.startswith(
        "# Global Medicines Atlas analysis and validation plan\n"
    )
    assert "Regulatory and funding outcomes remain separate" in expected
    assert "insufficient_evidence" in expected
