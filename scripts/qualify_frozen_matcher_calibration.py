"""Exercise existing matcher calibration while enforcing the real-label gap."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts import qualify_frontier_screening_calibration as controls

from global_medicines_atlas.frontier_candidate_benchmark import (
    LEXICAL_THRESHOLD,
    score_synthetic_candidate_cases,
)
from global_medicines_atlas.frontier_score_calibration import (
    ScoreOutcome,
    calibrate_scores,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "quality/qualifications/frontier-frozen-matcher-calibration-20261021.json"
)
AVAILABILITY = "quality/qualifications/frontier-real-matcher-label-availability-20261021.json"


def operating_points(rows: tuple[ScoreOutcome, ...]) -> list[dict[str, Any]]:
    """Measure predeclared synthetic cutoffs without selecting a threshold."""
    result: list[dict[str, Any]] = []
    for cutoff in (0.5, 0.65, 0.8, 0.9, 1.0):
        tp = sum(row.correct and row.score >= cutoff for row in rows)
        fp = sum(not row.correct and row.score >= cutoff for row in rows)
        fn = sum(row.correct and row.score < cutoff for row in rows)
        tn = len(rows) - tp - fp - fn
        result.append({
            "cutoff": cutoff,
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        })
    return result


def build_report(root: Path = ROOT) -> dict[str, Any]:
    """Bind the unchanged retained scope and run the existing synthetic control."""
    audit = json.loads((root / AVAILABILITY).read_bytes())
    paths = sorted((root / "quality/bronze/receipts").rglob("*.json"))
    counts: Counter[str] = Counter()
    bindings: dict[str, str] = {}
    for path in paths:
        payload = path.read_bytes()
        receipt = json.loads(payload)
        source = receipt["source"]
        counts[f"{source['source_id']}|{source['jurisdiction']}"] += 1
        bindings[path.relative_to(root).as_posix()] = hashlib.sha256(
            payload
        ).hexdigest()
    if (
        dict(counts)
        != audit["current_bronze_receipts"]["source_id_jurisdiction_counts"]
    ):
        raise ValueError(
            "Retained source scope changed; repeat label availability review"
        )
    if len({key.rsplit("|", 1)[1] for key in counts}) != 1:
        raise ValueError(
            "Cross-jurisdiction inventory changed; repeat label review"
        )
    for binding in (
        audit["matcher"],
        audit["fixture_boundary"],
        audit["reviewed_mbs_edge_set"],
    ):
        path = binding["path"]
        digest = hashlib.sha256((root / path).read_bytes()).hexdigest()
        if digest != binding["sha256"]:
            raise ValueError("Label availability audit input drift")
        bindings[path] = digest
    if (
        audit["reviewed_mbs_edge_set"][
            "cross_jurisdiction_medicine_identity_labels"
        ]
        is not False
    ):
        raise ValueError(
            "Reviewed relationship scope changed; repeat label review"
        )
    bindings[AVAILABILITY] = hashlib.sha256(
        (root / AVAILABILITY).read_bytes()
    ).hexdigest()
    for path in (
        "scripts/qualify_frozen_matcher_calibration.py",
        "scripts/qualify_frontier_screening_calibration.py",
        "src/global_medicines_atlas/frontier_candidate_benchmark.py",
        "src/global_medicines_atlas/frontier_score_calibration.py",
    ):
        bindings[path] = hashlib.sha256((root / path).read_bytes()).hexdigest()
    train = score_synthetic_candidate_cases(
        controls.generated_matcher_cases("train", 400)
    )
    holdout = score_synthetic_candidate_cases(
        controls.generated_matcher_cases("holdout", 400)
    )
    control = calibrate_scores(
        train, holdout, calibration_version="frozen-synthetic-actual-matcher-v1"
    )
    return {
        "schema_id": "global-medicines-atlas.frozen-matcher-calibration",
        "schema_version": 1,
        "real_source_calibration": {
            "state": "blocked_missing_reviewed_cross_jurisdiction_medicine_labels",
            "reviewed_eligible_pair_labels": 0,
            "real_source_confidence_emitted": False,
            "selected_threshold": None,
        },
        "retained_receipt_scope": dict(sorted(counts.items())),
        "synthetic_actual_matcher_control": control.model_dump(mode="json"),
        "synthetic_operating_point_scope": {
            "population": "scored top candidates after the existing retrieval floor",
            "retrieval_floor": LEXICAL_THRESHOLD,
            "generated_train_cases": 400,
            "generated_holdout_cases": 400,
            "unscored_train_cases": 400 - len(train),
            "unscored_holdout_cases": 400 - len(holdout),
            "end_to_end_retrieval_recall_claimed": False,
        },
        "synthetic_holdout_operating_points": operating_points(holdout),
        "inputs": dict(sorted(bindings.items())),
        "boundaries": {
            "new_sources_added": False,
            "source_payloads_accessed": False,
            "production_matcher_behavior_changed": False,
            "synthetic_labels_promoted_to_real": False,
            "real_source_calibration_completed": False,
        },
    }


if __name__ == "__main__":
    OUTPUT.write_text(
        json.dumps(build_report(), indent=2, sort_keys=True) + "\n"
    )
    print(OUTPUT.name)
