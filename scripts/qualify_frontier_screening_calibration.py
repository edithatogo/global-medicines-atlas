"""Build the bounded Frontier screening/calibration diagnostic receipt."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, cast

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
from global_medicines_atlas.matching_models import (
    EvaluationCase,
    EvaluationClass,
    MappingEndpoint,
    MappingLevel,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT / "quality/qualifications/frontier-screen-calibration-v2-20261018.json"
)
SCHEMA = ROOT / "schemas/frontier-screen-calibration-v2.json"
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


def generated_matcher_cases(
    partition: str, count: int
) -> tuple[EvaluationCase, ...]:
    """Generate disjoint, invented-name cases with labels fixed by construction."""
    cases: list[EvaluationCase] = []
    for index in range(count):
        positive = index % 2 == 0
        family = "calibration" if partition == "train" else "holdout"
        base = f"synthetic {family} molecule {index}"
        target_name = (
            (base if index % 4 == 0 else f"{base} tablet")
            if positive
            else (f"{base} analogue" if index % 4 == 1 else f"{base} analog")
        )
        source_id = f"{partition}:{index}:source"
        target_id = f"{partition}:{index}:target"
        endpoint = MappingEndpoint(
            concept_id=source_id,
            jurisdiction="NZL",
            level=MappingLevel.INGREDIENT,
            preferred_name=base,
            language="en",
            provenance_ids=(f"synthetic:{partition}:{index}",),
        )
        target = MappingEndpoint(
            concept_id=target_id,
            jurisdiction="AUS",
            level=MappingLevel.INGREDIENT,
            preferred_name=target_name,
            language="en",
            provenance_ids=(f"synthetic:{partition}:{index}:target",),
        )
        cases.append(
            EvaluationCase(
                case_id=f"{partition}-{index:04d}",
                evaluation_class=(
                    EvaluationClass.POSITIVE
                    if positive
                    else EvaluationClass.NEGATIVE
                ),
                mapping_level=MappingLevel.INGREDIENT,
                source=endpoint,
                targets=(target,),
                relevant_target_ids=frozenset({target_id})
                if positive
                else frozenset(),
                languages=("en",),
                tags=("generated-calibration", "synthetic", family),
                rationale=(
                    "Generated positive: target is the same invented record name."
                    if positive
                    else "Generated negative: target is a distinct invented analogue."
                ),
            )
        )
    return tuple(cases)


def screen_mbs_relationship_qualification(
    qualification: dict[str, Any],
) -> dict[str, Any]:
    """Screen the verified MBS edge cohort against explicit eligibility rules."""
    graph = qualification.get("graph")
    if not isinstance(graph, dict):
        raise TypeError("MBS graph qualification is missing its graph summary")
    graph = cast("dict[str, Any]", graph)
    expected = {
        "edge_kind": "source_record_has_benefit",
        "mapping_method": "source-explicit",
        "assertion_basis": "same_source_record",
        "inferred": False,
        "all_edges_same_record_bound": True,
        "confidence_calibration": "not_applicable_source_record",
    }
    for key, value in expected.items():
        if graph.get(key) != value:
            raise ValueError(
                f"MBS relationship screen failed {key} eligibility"
            )
    edge_count = graph.get("edge_count")
    if not isinstance(edge_count, int) or edge_count < 1:
        raise ValueError(
            "MBS relationship screen requires a positive edge count"
        )
    if graph.get("review_state") != "not_reviewed":
        raise ValueError("MBS relationship screen cannot rewrite review state")
    if (
        qualification.get("boundaries", {}).get("graph_publication_performed")
        is not False
    ):
        raise ValueError(
            "MBS relationship screen requires candidate-only graph"
        )
    return {
        "state": "eligible_candidate_relationships_screened",
        "edge_count": edge_count,
        "eligible_relationship_count": edge_count,
        "excluded_relationship_count": 0,
        "criteria": expected,
        "graph_sha256": graph["graph_sha256"],
        "review_or_release_authorized": False,
    }


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
    matcher_train = score_synthetic_candidate_cases(
        generated_matcher_cases("train", 400)
    )
    matcher_holdout = score_synthetic_candidate_cases(
        generated_matcher_cases("holdout", 400)
    )
    matcher_calibration = calibrate_scores(
        matcher_train,
        matcher_holdout,
        calibration_version="frontier-generated-matcher-v1",
    )
    mbs_qualification = json.loads(
        (
            ROOT
            / "quality/qualifications/australian-mbs-gold-real-silver-qualification-20261017.json"
        ).read_bytes()
    )
    mbs_relationship_screen = screen_mbs_relationship_qualification(
        mbs_qualification
    )
    return {
        "schema_id": "global-medicines-atlas.frontier-screen-calibration",
        "schema_version": 2,
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
        "relationship_screening": mbs_relationship_screen,
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
        "matcher_calibration": {
            "fixture_kind": "generated_cases_scored_by_actual_matcher",
            "state": matcher_calibration.state,
            "calibration_case_count": matcher_calibration.calibration_case_count,
            "calibration_positive_count": matcher_calibration.calibration_positive_count,
            "calibration_negative_count": matcher_calibration.calibration_negative_count,
            "holdout_case_count": matcher_calibration.holdout_case_count,
            "holdout_positive_count": matcher_calibration.holdout_positive_count,
            "holdout_negative_count": matcher_calibration.holdout_negative_count,
            "minimum_per_class": matcher_calibration.minimum_per_class,
            "calibration_case_id_overlap_count": matcher_calibration.case_overlap_count,
            "calibration_dataset_sha256": matcher_calibration.calibration_dataset_sha256,
            "holdout_dataset_sha256": matcher_calibration.holdout_dataset_sha256,
            "matcher_scored_count": len(matcher_train) + len(matcher_holdout),
            "calibrated_holdout_count": matcher_calibration.calibrated_holdout_count,
            "holdout_brier_score": matcher_calibration.holdout_brier_score,
            "holdout_expected_calibration_error": matcher_calibration.holdout_expected_calibration_error,
            "confidence_emitted": False,
            "confidence_authority": matcher_calibration.confidence_authority,
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
            "Relationship screening selects only explicit same-source-record MBS edges; it is not semantic equivalence review, product admission, rights clearance, or release authorization.",
            "Matcher calibration uses generated invented-name cases scored by the actual matcher; disjoint generated partitions validate a synthetic operating curve only and do not qualify real-source confidence.",
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
