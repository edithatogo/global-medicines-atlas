"""Synthetic retrieval benchmarks keep unavailable methods explicit."""

import hashlib
import json
import sys
from pathlib import Path

import pytest
from scripts.benchmark_frontier_candidates import main

from global_medicines_atlas import frontier_candidate_benchmark
from global_medicines_atlas.frontier_candidate_benchmark import (
    benchmark_synthetic_candidates,
    canonical_candidate_benchmark_bytes,
    load_synthetic_matching_cases,
)
from global_medicines_atlas.matching import (
    CandidateGenerationResult,
    MatchingRecord,
)

FIXTURES = Path(__file__).parent / "fixtures" / "matching"
BENCHMARK_RECEIPT = (
    Path(__file__).parents[1]
    / "quality/benchmarks/frontier-candidate-benchmark-20261018.json"
)


def test_synthetic_candidate_benchmark_is_deterministic_and_bounded() -> None:
    cases = load_synthetic_matching_cases(FIXTURES)

    first = benchmark_synthetic_candidates(cases, limit=5)
    second = benchmark_synthetic_candidates(tuple(reversed(cases)), limit=5)

    assert first == second
    assert first.synthetic is True
    assert first.case_count == 6
    assert first.clinical_equivalence_claims is False
    assert first.production_dependency_adopted is False
    assert first.lexical.status == "measured"
    assert first.lexical.calibration_evaluated is False
    assert first.lexical.retrieval_case_count > 0
    assert first.lexical.candidate_recall_at_k == pytest.approx(0.5)
    assert first.lexical.negative_candidate_case_count == 2
    assert first.lexical.negative_candidate_rate == pytest.approx(1.0)
    assert first.lexical.operation_count == sum(
        len(case.targets) for case in cases
    )
    assert canonical_candidate_benchmark_bytes(first) == (
        canonical_candidate_benchmark_bytes(second)
    )


def test_multilingual_identifier_positive_has_shared_source_identifier() -> (
    None
):
    case = next(
        item
        for item in load_synthetic_matching_cases(FIXTURES)
        if item.case_id == "multilingual-positive"
    )
    target = next(
        item
        for item in case.targets
        if item.concept_id in case.relevant_target_ids
    )
    source = MatchingRecord(
        record_id=case.source.concept_id,
        jurisdiction=case.source.jurisdiction,
        name=case.source.preferred_name,
        identifiers=case.source.identifiers,
    )
    target_record = MatchingRecord(
        record_id=target.concept_id,
        jurisdiction=target.jurisdiction,
        name=target.preferred_name,
        identifiers=target.identifiers,
    )

    result = frontier_candidate_benchmark.generate_candidates(
        source, (target_record,), lexical_threshold=0.65, limit=5
    )

    assert {item.target_record_id for item in result.candidates} == {
        target.concept_id
    }


def test_corrected_synthetic_benchmark_receipt_keeps_candidate_boundaries() -> (
    None
):
    receipt_bytes = BENCHMARK_RECEIPT.read_bytes()
    receipt = json.loads(receipt_bytes)

    assert hashlib.sha256(receipt_bytes).hexdigest() == (
        "8c2faa37fcd2c576a633f85925c3929b6ebc117024fed3df0340a16412a4a601"
    )
    assert receipt["fixture_sha256"] == (
        "6a1a65da416335dfcdddad85069f5cee1b1b9e2d3404f96554e64a3f2afb4d03"
    )
    assert receipt["case_count"] == 6
    assert receipt["synthetic"] is True
    assert receipt["clinical_equivalence_claims"] is False
    assert receipt["production_dependency_adopted"] is False
    assert receipt["lexical"]["candidate_recall_at_k"] == pytest.approx(0.5)
    assert receipt["lexical"]["negative_candidate_rate"] == pytest.approx(1.0)
    assert receipt["lexical"]["calibration_evaluated"] is False


def test_candidate_benchmark_discloses_unavailable_and_unjustified_methods() -> (
    None
):
    receipt = benchmark_synthetic_candidates(
        load_synthetic_matching_cases(FIXTURES)
    )
    payload = json.loads(canonical_candidate_benchmark_bytes(receipt))

    alternatives = {item["candidate"]: item for item in payload["alternatives"]}
    assert alternatives["ontology_assisted"]["status"] == "unavailable"
    assert alternatives["lancedb_embedding_nlp"]["status"] == "unavailable"
    assert alternatives["tantivy"]["status"] == "not_justified"
    assert alternatives["qdrant"]["status"] == "not_justified"


def test_measured_lexical_threshold_matches_query_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_thresholds: list[float] = []
    generate = frontier_candidate_benchmark.generate_candidates

    def record_threshold(
        source: MatchingRecord,
        targets: tuple[MatchingRecord, ...],
        *,
        lexical_threshold: float,
        limit: int,
    ) -> CandidateGenerationResult:
        observed_thresholds.append(lexical_threshold)
        return generate(
            source,
            targets,
            lexical_threshold=lexical_threshold,
            limit=limit,
        )

    monkeypatch.setattr(
        frontier_candidate_benchmark,
        "generate_candidates",
        record_threshold,
    )
    cases = load_synthetic_matching_cases(FIXTURES)
    receipt = benchmark_synthetic_candidates(cases)
    query = {
        "candidate_method": "identifier_first_lexical",
        "identifier_precedence": True,
        "k": receipt.limit,
        "lexical_threshold": frontier_candidate_benchmark.LEXICAL_THRESHOLD,
        "ranking": ["identifier", "score_desc", "jurisdiction", "record_id"],
    }
    expected_query = hashlib.sha256(
        json.dumps(query, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    assert observed_thresholds == [
        frontier_candidate_benchmark.LEXICAL_THRESHOLD
    ] * len(cases)
    assert receipt.query_sha256 == expected_query


def test_synthetic_candidate_benchmark_rejects_empty_corpus() -> None:
    with pytest.raises(ValueError, match="at least one synthetic case"):
        benchmark_synthetic_candidates(())


def test_benchmark_cli_writes_a_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "receipt.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark_frontier_candidates.py",
            "--fixture-dir",
            str(FIXTURES),
            "--output",
            str(output),
        ],
    )

    main()

    payload = json.loads(output.read_bytes())
    assert (
        payload["schema_id"]
        == "global-medicines-atlas.frontier-candidate-benchmark"
    )
    assert payload["synthetic"] is True
