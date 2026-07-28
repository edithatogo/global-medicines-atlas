import hashlib
import json

import pytest
from pydantic import ValidationError

from global_medicines_atlas.matching_columnar import (
    DISCLAIMER,
    MatchingOutputManifest,
)
from global_medicines_atlas.matching_evaluation import MatchingMetrics
from global_medicines_atlas.matching_release import (
    EngineDisposition,
    MatchingReleaseEvidence,
    MatchingReleaseState,
    qualify_matching_release,
)

DIGEST = "a" * 64


def metrics() -> MatchingMetrics:
    return MatchingMetrics(
        case_count=10,
        evaluated_count=8,
        true_positive=6,
        false_positive=1,
        false_negative=1,
        true_negative=2,
        precision=6 / 7,
        recall=6 / 7,
        f_score=6 / 7,
        candidate_recall_at_k=0.9,
        brier_score=0.1,
        expected_calibration_error=0.08,
        coverage=0.8,
        abstention_rate=0.2,
        selective_risk=0.125,
    )


def manifest() -> MatchingOutputManifest:
    return MatchingOutputManifest(
        candidate_count=8,
        feature_count=80,
        files={"matching_candidates.parquet": DIGEST},
        input_digest=DIGEST,
        clinical_equivalence_disclaimer=DISCLAIMER,
    )


def manifest_digest(value: MatchingOutputManifest | None = None) -> str:
    return hashlib.sha256((value or manifest()).canonical_json()).hexdigest()


def test_fixture_evidence_remains_fail_closed():
    evidence = qualify_matching_release(
        metrics=metrics(),
        output_manifest=manifest(),
        output_manifest_digest=manifest_digest(),
        corpus_digest=DIGEST,
        holdout_digest=DIGEST,
        calibration_version="cal-v1",
        index_version="index-v1",
        model_version="python-reference-v1",
        engine_disposition=EngineDisposition(
            rationale="No representative scale or profile benefit."
        ),
        open_review_count=4,
        unresolved_conflict_count=0,
        limitations=("Synthetic corpus only.",),
        gates={
            "corpus_reviewed": False,
            "holdout_sealed": False,
            "metrics_passed": True,
            "calibration_passed": True,
            "artifacts_reproducible": True,
            "human_adjudication_complete": False,
        },
    )
    assert evidence.state is MatchingReleaseState.FIXTURE_QUALIFIED
    assert "open_reviews" in evidence.unresolved_gates
    fixture = json.loads(
        __import__("pathlib")
        .Path("tests/fixtures/release-evidence/blocked-v0.5.json")
        .read_text(encoding="utf-8")
    )
    assert set(fixture["required_unresolved_gates"]) <= set(
        evidence.unresolved_gates
    )


def test_reviewed_state_rejects_open_gates():
    payload = {
        "state": "reviewed",
        "metrics": metrics().model_dump(mode="json"),
        "output_manifest": manifest().model_dump(mode="json"),
        "output_manifest_digest": manifest_digest(),
        "corpus_digest": DIGEST,
        "holdout_digest": DIGEST,
        "calibration_version": "cal-v1",
        "index_version": "index-v1",
        "model_version": "python-reference-v1",
        "engine_disposition": EngineDisposition(
            rationale="Reference engine retained."
        ).model_dump(mode="json"),
        "open_review_count": 1,
        "unresolved_conflict_count": 0,
        "limitations": ["Known limitations."],
        "gates": {
            "corpus_reviewed": True,
            "holdout_sealed": True,
            "metrics_passed": True,
            "calibration_passed": True,
            "artifacts_reproducible": True,
            "human_adjudication_complete": True,
        },
        "unresolved_gates": ["open_reviews"],
    }
    with pytest.raises(
        ValidationError, match="state must be fixture_qualified"
    ):
        MatchingReleaseEvidence.model_validate(payload)


def test_release_evidence_is_canonical():
    evidence = qualify_matching_release(
        metrics=metrics(),
        output_manifest=manifest(),
        output_manifest_digest=manifest_digest(),
        corpus_digest=DIGEST,
        holdout_digest=DIGEST,
        calibration_version="cal-v1",
        index_version="index-v1",
        model_version="python-reference-v1",
        engine_disposition=EngineDisposition(
            rationale="Reference engine retained."
        ),
        open_review_count=0,
        unresolved_conflict_count=0,
        limitations=("No clinical equivalence claims.",),
        gates={
            "corpus_reviewed": True,
            "holdout_sealed": True,
            "metrics_passed": True,
            "calibration_passed": True,
            "artifacts_reproducible": True,
            "human_adjudication_complete": True,
        },
    )
    assert evidence.state is MatchingReleaseState.REVIEWED
    assert evidence.clinical_equivalence_disclaimer == DISCLAIMER
    assert hashlib.sha256(evidence.canonical_json()).hexdigest()


def test_manifest_digest_must_bind_canonical_manifest():
    with pytest.raises(ValueError, match="digest does not match"):
        qualify_matching_release(
            metrics=metrics(),
            output_manifest=manifest(),
            output_manifest_digest=DIGEST,
            corpus_digest=DIGEST,
            holdout_digest=DIGEST,
            calibration_version="cal-v1",
            index_version="index-v1",
            model_version="python-reference-v1",
            engine_disposition=EngineDisposition(rationale="Reference."),
            open_review_count=0,
            unresolved_conflict_count=0,
            limitations=("Known limitations.",),
            gates={
                "corpus_reviewed": True,
                "holdout_sealed": True,
                "metrics_passed": True,
                "calibration_passed": True,
                "artifacts_reproducible": True,
                "human_adjudication_complete": True,
            },
        )


def test_direct_construction_rejects_forged_state_and_unresolved_gates():
    evidence = qualify_matching_release(
        metrics=metrics(),
        output_manifest=manifest(),
        output_manifest_digest=manifest_digest(),
        corpus_digest=DIGEST,
        holdout_digest=DIGEST,
        calibration_version="cal-v1",
        index_version="index-v1",
        model_version="python-reference-v1",
        engine_disposition=EngineDisposition(rationale="Reference."),
        open_review_count=2,
        unresolved_conflict_count=0,
        limitations=("Known limitations.",),
        gates={
            "corpus_reviewed": False,
            "holdout_sealed": False,
            "metrics_passed": True,
            "calibration_passed": True,
            "artifacts_reproducible": True,
            "human_adjudication_complete": False,
        },
    )
    payload = evidence.model_dump(mode="json")
    payload["state"] = "reviewed"
    payload["unresolved_gates"] = []
    with pytest.raises(ValidationError, match="Unresolved gates"):
        MatchingReleaseEvidence.model_validate(payload)


def test_promoted_engine_requires_explicit_promotion_gates():
    base_gates = {
        "corpus_reviewed": True,
        "holdout_sealed": True,
        "metrics_passed": True,
        "calibration_passed": True,
        "artifacts_reproducible": True,
        "human_adjudication_complete": True,
    }
    with pytest.raises(ValidationError, match="engine-promotion gates"):
        qualify_matching_release(
            metrics=metrics(),
            output_manifest=manifest(),
            output_manifest_digest=manifest_digest(),
            corpus_digest=DIGEST,
            holdout_digest=DIGEST,
            calibration_version="cal-v1",
            index_version="index-v1",
            model_version="mojo-v1",
            engine_disposition=EngineDisposition(
                mojo="promoted",
                rationale="Unsupported promotion attempt.",
            ),
            open_review_count=0,
            unresolved_conflict_count=0,
            limitations=("Known limitations.",),
            gates=base_gates,
        )


def test_failed_promotion_gate_prevents_reviewed_state():
    evidence = qualify_matching_release(
        metrics=metrics(),
        output_manifest=manifest(),
        output_manifest_digest=manifest_digest(),
        corpus_digest=DIGEST,
        holdout_digest=DIGEST,
        calibration_version="cal-v1",
        index_version="index-v1",
        model_version="mojo-v1",
        engine_disposition=EngineDisposition(
            mojo="promoted",
            rationale="Promotion remains gated.",
        ),
        open_review_count=0,
        unresolved_conflict_count=0,
        limitations=("Known limitations.",),
        gates={
            "corpus_reviewed": True,
            "holdout_sealed": True,
            "metrics_passed": True,
            "calibration_passed": True,
            "artifacts_reproducible": True,
            "human_adjudication_complete": True,
            "engine_parity_passed": True,
            "representative_benchmark_passed": False,
            "scalene_profile_justifies_promotion": True,
        },
    )
    assert evidence.state is MatchingReleaseState.FIXTURE_QUALIFIED
    assert evidence.unresolved_gates == ("representative_benchmark_passed",)
