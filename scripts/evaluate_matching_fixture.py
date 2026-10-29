"""Assess candidate-generator behavior on the explicit synthetic labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from global_medicines_atlas.matching_models import EvaluationCase
from global_medicines_atlas.matching_qualification import (
    assess_matching_behavior,
)

DEFAULT_FIXTURE = Path("tests/fixtures/matching/cases.jsonl")
DEFAULT_THRESHOLDS = (0.65, 0.8, 0.95, 0.99)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--threshold",
        type=float,
        action="append",
        help="Lexical cutoff; repeat to compare operating points.",
    )
    arguments = parser.parse_args()
    fixture_bytes = arguments.fixture.read_bytes()
    cases = tuple(
        EvaluationCase.model_validate_json(line)
        for line in fixture_bytes.decode("utf-8").splitlines()
        if line
    )
    thresholds = tuple(arguments.threshold or DEFAULT_THRESHOLDS)
    assessments = tuple(
        assess_matching_behavior(cases, lexical_threshold=threshold)
        for threshold in thresholds
    )
    report = {
        "schema_version": 1,
        "assessment_kind": "synthetic_matching_behavior_screen",
        "fixture": {
            "path": arguments.fixture.as_posix(),
            "sha256": hashlib.sha256(fixture_bytes).hexdigest(),
            "case_count": len(cases),
            "synthetic": True,
        },
        "threshold_sweep": [
            {
                "lexical_threshold": item.lexical_threshold,
                "candidate_limit": item.candidate_limit,
                "overall_metrics": item.metrics.overall.model_dump(mode="json"),
                "metrics_by_mapping_level": {
                    name: metrics.model_dump(mode="json")
                    for name, metrics in item.metrics.by_mapping_level.items()
                },
                "outcomes": [
                    outcome.model_dump(mode="json") for outcome in item.outcomes
                ],
                "limitations": list(item.limitations),
                "production_promotion_eligible": (
                    item.production_promotion_eligible
                ),
            }
            for item in assessments
        ],
        "promotion_eligible": False,
        "calibration_status": "not_calibrated_synthetic_fixture_only",
    }
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(serialized, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    main()
