"""Build the bounded Frontier screening/calibration diagnostic receipt."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import jsonschema

from global_medicines_atlas.frontier_candidate_benchmark import (
    load_synthetic_matching_cases,
    score_synthetic_candidate_cases,
)
from global_medicines_atlas.frontier_content_screening import (
    ScreenedPayload,
    screen_graph_payloads,
)
from global_medicines_atlas.frontier_score_calibration import (
    ScoreOutcome,
    calibrate_scores,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT / "quality/qualifications/frontier-screen-calibration-20261018.json"
)
SCHEMA = ROOT / "schemas/frontier-screen-calibration-v1.json"
MATCHING_FIXTURE = ROOT / "tests/fixtures/matching"
CALIBRATION_VERSION = "frontier-synthetic-platt-v1"


def _synthetic_curve(prefix: str, count: int) -> tuple[ScoreOutcome, ...]:
    observations: list[ScoreOutcome] = []
    for index in range(count):
        score = (index % 20 + 0.5) / 20
        probability = 1 / (1 + math.exp(-(-2.0 + 4.0 * score)))
        correct = (index * 37 % 1000) < round(probability * 1000)
        observations.append(
            ScoreOutcome(
                case_id=f"{prefix}-{index}",
                score=score,
                correct=correct,
            )
        )
    return tuple(observations)


def build_receipt() -> dict[str, Any]:
    canary = "SYNTHETIC-RESTRICTED-CONTENT-CANARY"
    blocked_digest = hashlib.sha256(canary.encode()).hexdigest()
    screen_cases = (
        (
            "clean",
            ScreenedPayload(
                path="synthetic-clean",
                payload='{"name":"Medicine X"}',
            ),
        ),
        (
            "sensitive_field_name",
            ScreenedPayload(
                path="synthetic-field-canary",
                payload='{"patient_id":"SYNTHETIC-VALUE"}',
            ),
        ),
        (
            "email_like_value",
            ScreenedPayload(
                path="synthetic-email-canary",
                payload='{"contact":"synthetic@example.invalid"}',
            ),
        ),
        (
            "known_value_digest",
            ScreenedPayload(
                path="synthetic-digest-canary",
                payload=json.dumps({"value": canary}),
            ),
        ),
    )
    screening_results = {
        label: screen_graph_payloads(
            (payload,), blocked_value_sha256=frozenset({blocked_digest})
        )
        for label, payload in screen_cases
    }
    categories = sorted({
        finding.category
        for result in screening_results.values()
        for finding in result.findings
    })
    category_counts = {
        category: sum(
            finding.category == category
            for result in screening_results.values()
            for finding in result.findings
        )
        for category in categories
    }

    cases = load_synthetic_matching_cases(MATCHING_FIXTURE)
    candidate_outcomes = score_synthetic_candidate_cases(cases)
    candidate_calibration = calibrate_scores(
        candidate_outcomes,
        (),
        calibration_version=CALIBRATION_VERSION,
    )
    mechanics_calibration = calibrate_scores(
        _synthetic_curve("mechanics-calibration", 400),
        _synthetic_curve("mechanics-holdout", 400),
        calibration_version=CALIBRATION_VERSION,
    )
    return {
        "schema_id": "global-medicines-atlas.frontier-screen-calibration",
        "schema_version": 1,
        "track_id": "federated_medallion_frontier_experiments_20260829",
        "screening": {
            "fixture_kind": "synthetic_canaries_only",
            "payload_count": len(screening_results),
            "clean_payload_count": sum(
                result.state == "no_pattern_detected"
                for result in screening_results.values()
            ),
            "review_required_payload_count": sum(
                result.state == "review_required"
                for result in screening_results.values()
            ),
            "finding_counts": category_counts,
            "raw_values_recorded": False,
            "blocked_value_digests_recorded": False,
            "rights_cleared": False,
            "restricted_terminology_cleared": False,
            "exporter_integration": "MBS and PBS field payloads; reference, RDF-star and RDF 1.2 paths",
        },
        "candidate_calibration": {
            "fixture_sha256": hashlib.sha256(
                (MATCHING_FIXTURE / "cases.jsonl").read_bytes()
            ).hexdigest(),
            "case_count": len(cases),
            "scored_top_candidate_count": len(candidate_outcomes),
            "positive_scored_count": sum(
                outcome.correct for outcome in candidate_outcomes
            ),
            "negative_scored_count": sum(
                not outcome.correct for outcome in candidate_outcomes
            ),
            "minimum_per_class": candidate_calibration.minimum_per_class,
            "independent_holdout_count": 0,
            "state": candidate_calibration.state,
            "calibration_dataset_sha256": candidate_calibration.calibration_dataset_sha256,
            "holdout_dataset_sha256": candidate_calibration.holdout_dataset_sha256,
            "calibrated_holdout_count": candidate_calibration.calibrated_holdout_count,
            "confidence_emitted": candidate_calibration.calibrated_holdout_count
            > 0,
        },
        "calibration_mechanics_control": {
            "fixture_kind": "generated_synthetic_score_curve_not_matcher_output",
            "state": mechanics_calibration.state,
            "calibration_case_count": mechanics_calibration.calibration_case_count,
            "calibration_positive_count": mechanics_calibration.calibration_positive_count,
            "calibration_negative_count": mechanics_calibration.calibration_negative_count,
            "minimum_per_class": mechanics_calibration.minimum_per_class,
            "holdout_case_count": mechanics_calibration.holdout_case_count,
            "holdout_positive_count": mechanics_calibration.holdout_positive_count,
            "holdout_negative_count": mechanics_calibration.holdout_negative_count,
            "case_overlap_count": mechanics_calibration.case_overlap_count,
            "calibration_dataset_sha256": mechanics_calibration.calibration_dataset_sha256,
            "holdout_dataset_sha256": mechanics_calibration.holdout_dataset_sha256,
            "calibrated_holdout_count": mechanics_calibration.calibrated_holdout_count,
            "holdout_brier_score": mechanics_calibration.holdout_brier_score,
            "holdout_expected_calibration_error": mechanics_calibration.holdout_expected_calibration_error,
            "confidence_authority": mechanics_calibration.confidence_authority,
        },
        "boundaries": {
            "new_sources_added_or_acquired": False,
            "source_payloads_accessed": False,
            "source_coverage_claimed": False,
            "rights_or_licensing_conclusion": False,
            "clinical_equivalence_claim": False,
            "production_dependency_adopted": False,
            "production_authority_promoted": False,
        },
        "limitations": [
            "The content screen detects sensitive field-name patterns, email-like values and exact caller-supplied SHA-256 canaries only.",
            "A clean screen is not exhaustive content inspection, rights clearance, or restricted-terminology clearance.",
            "The current six-case matcher fixture produces too few scored candidates for calibration; it emits no confidence.",
            "The successful fit is a mechanics control over generated scores, not a calibration claim for the retrieval model.",
            "The fixed 100-per-class floor is an exploratory implementation guardrail, not evidence of statistical adequacy for external use.",
        ],
    }


def canonical_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def main() -> None:
    value = build_receipt()
    jsonschema.validate(value, json.loads(SCHEMA.read_text(encoding="utf-8")))
    OUTPUT.write_bytes(canonical_bytes(value))
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
