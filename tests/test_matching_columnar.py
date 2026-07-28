from datetime import UTC, datetime

import duckdb
import pyarrow.parquet as pq

from global_medicines_atlas.matching_columnar import (
    DISCLAIMER,
    write_matching_outputs,
)
from global_medicines_atlas.matching_features import (
    FeatureDisposition,
    FeatureKind,
    MatchFeatures,
    feature,
)
from global_medicines_atlas.matching_models import MappingLevel
from global_medicines_atlas.matching_policy import (
    MatchCandidate,
    PolicyDecision,
    PolicyReason,
)
from global_medicines_atlas.review_queue import ReviewQueueEntry

NOW = datetime(2026, 7, 29, tzinfo=UTC)


def sample_entry(candidate_id: str = "candidate-1") -> ReviewQueueEntry:
    missing = lambda kind: feature(  # ruff: ignore[lambda-assignment]
        kind,
        FeatureDisposition.MISSING,
        0,
        "Not supplied",
    )
    features = MatchFeatures(
        mapping_level=MappingLevel.MEDICINAL_PRODUCT,
        identifiers=feature(
            FeatureKind.IDENTIFIER,
            FeatureDisposition.AGREEMENT,
            0.8,
            "Shared governed identifier",
        ),
        ingredients=missing(FeatureKind.INGREDIENT),
        strength=missing(FeatureKind.STRENGTH),
        unit=missing(FeatureKind.UNIT),
        form=missing(FeatureKind.FORM),
        route=missing(FeatureKind.ROUTE),
        lexical=missing(FeatureKind.LEXICAL),
        semantic=missing(FeatureKind.SEMANTIC),
        rxnorm=missing(FeatureKind.RXNORM),
        temporal=missing(FeatureKind.TEMPORAL),
        feature_version="features-v1",
        evaluated_at=NOW,
    )
    candidate = MatchCandidate(
        candidate_id=candidate_id,
        source_concept_id="nz-1",
        target_concept_id="au-1",
        source_jurisdiction="NZ",
        target_jurisdiction="AU",
        mapping_level=MappingLevel.MEDICINAL_PRODUCT,
        features=features,
        index_version="index-v1",
        model_version="python-reference-v1",
    )
    decision = PolicyDecision(
        candidate_id=candidate_id,
        confidence=0.8,
        abstained=False,
        reason_codes=(PolicyReason.REVIEW_REQUIRED,),
        policy_version="review-only-v1",
    )
    return ReviewQueueEntry(
        candidate=candidate,
        decision=decision,
        queued_at=NOW,
    )


def test_outputs_are_sorted_and_expose_duckdb_views(tmp_path):
    manifest = write_matching_outputs(
        [sample_entry("z-candidate"), sample_entry("a-candidate")],
        tmp_path,
    )
    table = pq.read_table(tmp_path / "matching_candidates.parquet")
    assert table.column("candidate_id").to_pylist() == [
        "a-candidate",
        "z-candidate",
    ]
    connection = duckdb.connect(str(tmp_path / "matching.duckdb"))
    try:
        assert connection.sql(
            "select sum(candidate_count) from matching_review_summary"
        ).fetchone() == (2,)
    finally:
        connection.close()
    assert manifest.candidate_count == 2
    assert manifest.feature_count == 20
    assert manifest.clinical_equivalence_disclaimer == DISCLAIMER


def test_output_manifest_and_jsonl_are_reproducible(tmp_path):
    entries = [sample_entry()]
    first = write_matching_outputs(entries, tmp_path)
    first_queue = (tmp_path / "review_queue.jsonl").read_bytes()
    second = write_matching_outputs(entries, tmp_path)
    assert first.input_digest == second.input_digest
    assert first.files == second.files
    assert first_queue == (tmp_path / "review_queue.jsonl").read_bytes()
    assert b'"clinical_equivalence_claim":false' in first_queue


def test_empty_queue_has_stable_schemas(tmp_path):
    manifest = write_matching_outputs([], tmp_path)
    assert manifest.candidate_count == 0
    assert pq.read_table(tmp_path / "matching_candidates.parquet").schema.names
