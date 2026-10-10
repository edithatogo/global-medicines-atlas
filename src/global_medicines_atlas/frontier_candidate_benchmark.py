"""Offline retrieval benchmark over the governed synthetic matching corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal, cast

from pydantic import Field

from .matching import MatchingRecord, generate_candidates
from .matching_models import EvaluationCase, EvaluationClass
from .models import FrozenModel

_SCHEMA_ID = "global-medicines-atlas.frontier-candidate-benchmark"
_DEFAULT_LIMIT = 5
LEXICAL_THRESHOLD = 0.65


class CandidateMethodDisposition(FrozenModel):
    """Measured, unavailable, or unjustified candidate method."""

    candidate: Literal[
        "ontology_assisted",
        "lancedb_embedding_nlp",
        "tantivy",
        "qdrant",
    ]
    status: Literal["unavailable", "not_justified"]
    reason: str = Field(min_length=1, max_length=512)


class LexicalBenchmark(FrozenModel):
    """Candidate retrieval metrics that do not imply calibrated confidence."""

    candidate: Literal["identifier_first_lexical"]
    status: Literal["measured"]
    retrieval_case_count: int = Field(ge=0)
    relevant_case_count: int = Field(ge=0)
    candidate_recall_at_k: float = Field(ge=0, le=1)
    negative_candidate_case_count: int = Field(ge=0)
    negative_case_count: int = Field(ge=0)
    negative_candidate_rate: float = Field(ge=0, le=1)
    abstention_case_count: int = Field(ge=0)
    abstention_rate: float = Field(ge=0, le=1)
    operation_count: int = Field(ge=0)
    calibration_evaluated: Literal[False]
    note: str = Field(min_length=1, max_length=512)


class CandidateBenchmarkReceipt(FrozenModel):
    """Deterministic benchmark output with explicit candidate dispositions."""

    schema_id: Literal["global-medicines-atlas.frontier-candidate-benchmark"]
    schema_version: Literal[1]
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_count: int = Field(gt=0)
    limit: int = Field(gt=0)
    synthetic: Literal[True]
    clinical_equivalence_claims: Literal[False]
    production_dependency_adopted: Literal[False]
    lexical: LexicalBenchmark
    alternatives: tuple[CandidateMethodDisposition, ...] = Field(
        min_length=4, max_length=4
    )


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _measure_lexical(
    cases: tuple[EvaluationCase, ...], limit: int
) -> LexicalBenchmark:
    relevant_count = retrieval_count = negative_count = 0
    negative_candidate_count = abstention_count = operation_count = 0
    for case in cases:
        source = MatchingRecord(
            record_id=case.source.concept_id,
            jurisdiction=case.source.jurisdiction,
            name=case.source.preferred_name,
            identifiers=case.source.identifiers,
        )
        targets = tuple(
            MatchingRecord(
                record_id=target.concept_id,
                jurisdiction=target.jurisdiction,
                name=target.preferred_name,
                identifiers=target.identifiers,
            )
            for target in case.targets
        )
        operation_count += len(targets)
        result = generate_candidates(
            source,
            targets,
            lexical_threshold=LEXICAL_THRESHOLD,
            limit=limit,
        )
        selected = {item.target_record_id for item in result.candidates}
        if case.relevant_target_ids:
            relevant_count += 1
            retrieval_count += bool(selected & case.relevant_target_ids)
        if case.evaluation_class is EvaluationClass.NEGATIVE:
            negative_count += 1
            negative_candidate_count += bool(selected)
        abstention_count += result.abstained

    return LexicalBenchmark(
        candidate="identifier_first_lexical",
        status="measured",
        retrieval_case_count=retrieval_count,
        relevant_case_count=relevant_count,
        candidate_recall_at_k=(
            retrieval_count / relevant_count if relevant_count else 0.0
        ),
        negative_candidate_case_count=negative_candidate_count,
        negative_case_count=negative_count,
        negative_candidate_rate=(
            negative_candidate_count / negative_count if negative_count else 0.0
        ),
        abstention_case_count=abstention_count,
        abstention_rate=abstention_count / len(cases),
        operation_count=operation_count,
        calibration_evaluated=False,
        note=(
            "Candidate retrieval only; existing scores are not calibrated "
            "confidence and remain pending review."
        ),
    )


def load_synthetic_matching_cases(
    directory: Path,
) -> tuple[EvaluationCase, ...]:
    """Load cases only when the adjacent manifest declares a synthetic corpus."""
    manifest = json.loads((directory / "manifest.json").read_text())
    if (
        manifest.get("synthetic") is not True
        or manifest.get("clinical_equivalence_claims") is not False
    ):
        raise ValueError("matching benchmark requires a synthetic-only corpus")
    cases = tuple(
        EvaluationCase.model_validate_json(line)
        for line in (directory / "cases.jsonl").read_text().splitlines()
        if line
    )
    if len(cases) != manifest.get("fixture_count"):
        raise ValueError(
            "synthetic matching corpus count does not match manifest"
        )
    return cases


def benchmark_synthetic_candidates(
    cases: tuple[EvaluationCase, ...], *, limit: int = _DEFAULT_LIMIT
) -> CandidateBenchmarkReceipt:
    """Measure current identifier-first lexical recall on synthetic cases."""
    if not cases:
        raise ValueError("benchmark requires at least one synthetic case")
    if limit < 1:
        raise ValueError("candidate limit must be positive")
    ordered_cases = tuple(sorted(cases, key=lambda case: case.case_id))
    if len({case.case_id for case in ordered_cases}) != len(ordered_cases):
        raise ValueError("synthetic case identifiers must be unique")

    fixture_value: list[dict[str, object]] = []
    for case in ordered_cases:
        payload = cast("dict[str, object]", case.model_dump(mode="json"))
        payload["relevant_target_ids"] = sorted(case.relevant_target_ids)
        fixture_value.append(payload)
    fixture_digest = _canonical_digest(fixture_value)
    query_digest = _canonical_digest({
        "candidate_method": "identifier_first_lexical",
        "identifier_precedence": True,
        "k": limit,
        "lexical_threshold": LEXICAL_THRESHOLD,
        "ranking": ["identifier", "score_desc", "jurisdiction", "record_id"],
    })

    return CandidateBenchmarkReceipt(
        schema_id=_SCHEMA_ID,
        schema_version=1,
        fixture_sha256=fixture_digest,
        query_sha256=query_digest,
        case_count=len(ordered_cases),
        limit=limit,
        synthetic=True,
        clinical_equivalence_claims=False,
        production_dependency_adopted=False,
        lexical=_measure_lexical(ordered_cases, limit),
        alternatives=(
            CandidateMethodDisposition(
                candidate="ontology_assisted",
                status="unavailable",
                reason=(
                    "No governed synthetic ontology fixture with explicit "
                    "relationship semantics is present in this corpus."
                ),
            ),
            CandidateMethodDisposition(
                candidate="lancedb_embedding_nlp",
                status="unavailable",
                reason=(
                    "No exact synthetic embedding artifact and pinned model "
                    "revision are bound to these fixture cases."
                ),
            ),
            CandidateMethodDisposition(
                candidate="tantivy",
                status="not_justified",
                reason=(
                    "The bounded candidate pools establish no measured full-text "
                    "index requirement."
                ),
            ),
            CandidateMethodDisposition(
                candidate="qdrant",
                status="not_justified",
                reason=(
                    "The synthetic corpus establishes no measured vector-scale "
                    "or service requirement."
                ),
            ),
        ),
    )


def canonical_candidate_benchmark_bytes(
    receipt: CandidateBenchmarkReceipt,
) -> bytes:
    """Serialize a receipt deterministically for review and provenance."""
    return (
        json.dumps(
            receipt.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
