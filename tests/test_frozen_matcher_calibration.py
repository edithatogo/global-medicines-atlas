"""Synthetic operating points cannot silently become real-source calibration."""

import json
from pathlib import Path

import pytest
from scripts.qualify_frozen_matcher_calibration import (
    AVAILABILITY,
    build_report,
    operating_points,
)

from global_medicines_atlas.frontier_score_calibration import ScoreOutcome

ROOT = Path(__file__).resolve().parents[1]


def test_operating_points_preserve_false_positives_and_abstention() -> None:
    rows = (
        ScoreOutcome(case_id="synthetic-positive", score=0.9, correct=True),
        ScoreOutcome(case_id="synthetic-negative", score=0.8, correct=False),
    )
    points = operating_points(rows)
    assert points[0]["false_positive"] == 1
    assert points[-1]["precision"] is None
    assert points[-1]["false_negative"] == 1


def test_frozen_scope_does_not_emit_a_real_threshold_or_confidence() -> None:
    report = build_report()
    real = report["real_source_calibration"]
    assert real["reviewed_eligible_pair_labels"] == 0
    assert real["selected_threshold"] is None
    assert real["real_source_confidence_emitted"] is False
    assert (
        report["synthetic_actual_matcher_control"]["state"]
        == "measured_synthetic_only"
    )
    assert report["boundaries"]["real_source_calibration_completed"] is False


def test_availability_input_drift_requires_review(tmp_path: Path) -> None:
    target = tmp_path / AVAILABILITY
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / AVAILABILITY).read_bytes())
    with pytest.raises(ValueError, match="Retained source scope changed"):
        build_report(tmp_path)


def test_committed_calibration_report_is_reproducible() -> None:
    expected = json.dumps(build_report(), indent=2, sort_keys=True) + "\n"
    assert (
        ROOT
        / "quality/qualifications/frontier-frozen-matcher-calibration-20261021.json"
    ).read_text() == expected
