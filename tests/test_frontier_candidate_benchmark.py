"""Synthetic retrieval benchmarks keep unavailable methods explicit."""

import json
import sys
from pathlib import Path

import pytest
from scripts.benchmark_frontier_candidates import main

from global_medicines_atlas.frontier_candidate_benchmark import (
    benchmark_synthetic_candidates,
    canonical_candidate_benchmark_bytes,
    load_synthetic_matching_cases,
)

FIXTURES = Path(__file__).parent / "fixtures" / "matching"


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
    assert first.lexical.candidate_recall_at_k == pytest.approx(0.25)
    assert first.lexical.negative_candidate_case_count == 2
    assert first.lexical.negative_candidate_rate == pytest.approx(1.0)
    assert first.lexical.operation_count == sum(
        len(case.targets) for case in cases
    )
    assert canonical_candidate_benchmark_bytes(first) == (
        canonical_candidate_benchmark_bytes(second)
    )


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
