"""Relationship eligibility screening uses edge evidence, not model parity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.qualify_frontier_screening_calibration import (
    build_receipt,
    screen_mbs_relationship_qualification,
)

ROOT = Path(__file__).parents[1]
MBS_QUALIFICATION = ROOT / (
    "quality/qualifications/"
    "australian-mbs-gold-real-silver-qualification-20261017.json"
)


def test_same_record_mbs_relationships_are_screened_as_candidate_eligible() -> (
    None
):
    qualification = json.loads(MBS_QUALIFICATION.read_bytes())

    screen = screen_mbs_relationship_qualification(qualification)

    assert screen["state"] == "eligible_candidate_relationships_screened"
    assert screen["eligible_relationship_count"] == 5989
    assert screen["excluded_relationship_count"] == 0
    assert screen["criteria"] == {
        "edge_kind": "source_record_has_benefit",
        "mapping_method": "source-explicit",
        "assertion_basis": "same_source_record",
        "inferred": False,
        "all_edges_same_record_bound": True,
        "confidence_calibration": "not_applicable_source_record",
    }
    assert screen["review_or_release_authorized"] is False


def test_relationship_screen_fails_closed_on_unbound_or_inferred_edge() -> None:
    qualification = json.loads(MBS_QUALIFICATION.read_bytes())
    qualification["graph"]["all_edges_same_record_bound"] = False

    with pytest.raises(ValueError, match="all_edges_same_record_bound"):
        screen_mbs_relationship_qualification(qualification)


def test_matcher_calibration_uses_real_matcher_outputs_and_disjoint_cases() -> (
    None
):
    receipt = build_receipt()

    calibration = receipt["matcher_calibration"]
    assert (
        calibration["fixture_kind"]
        == "generated_cases_scored_by_actual_matcher"
    )
    assert calibration["state"] == "measured_synthetic_only"
    assert calibration["calibration_case_count"] == 400
    assert calibration["holdout_case_count"] == 400
    assert calibration["calibration_case_id_overlap_count"] == 0
    assert calibration["calibration_positive_count"] >= 100
    assert calibration["calibration_negative_count"] >= 100
    assert calibration["holdout_positive_count"] >= 100
    assert calibration["holdout_negative_count"] >= 100
    assert calibration["matcher_scored_count"] == 800
    assert calibration["confidence_emitted"] is False
    assert calibration["holdout_brier_score"] is not None
