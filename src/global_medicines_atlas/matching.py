"""Deterministic identifier-first medicine candidate generation."""

from __future__ import annotations

from pydantic import Field

from .matching_identifiers import IdentifierEvidence, shared_identifiers
from .matching_lexical import LexicalEvidence, compare_features, lexical_score
from .matching_models import AbstentionReason, CandidateMethod
from .matching_normalization import MatchingFeatures, build_features
from .models import FrozenModel, Identifier


class MatchingRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=2, max_length=3)
    name: str = Field(min_length=1)
    identifiers: tuple[Identifier, ...] = ()
    ingredients: tuple[str, ...] = ()
    strength_value: str | float | int | None = None
    strength_unit: str | None = None
    dose_form: str | None = None
    route: str | None = None

    def features(self) -> MatchingFeatures:
        return build_features(
            name=self.name,
            ingredients=self.ingredients,
            strength_value=self.strength_value,
            strength_unit=self.strength_unit,
            dose_form=self.dose_form,
            route=self.route,
        )


class MethodEvidence(FrozenModel):
    method: CandidateMethod
    identifier_matches: tuple[IdentifierEvidence, ...] = ()
    lexical_features: tuple[LexicalEvidence, ...] = ()
    score: float = Field(ge=0, le=1)


class MatchCandidate(FrozenModel):
    source_record_id: str
    target_record_id: str
    target_jurisdiction: str
    rank: int = Field(ge=1)
    score: float = Field(ge=0, le=1)
    methods: tuple[CandidateMethod, ...] = Field(min_length=1)
    evidence: tuple[MethodEvidence, ...] = Field(min_length=1)
    pending_review: bool = True


class CandidateGenerationResult(FrozenModel):
    source_record_id: str
    candidates: tuple[MatchCandidate, ...]
    abstained: bool
    abstention_reason: AbstentionReason | None = None
    absence_is_negative_proof: bool = False


def generate_candidates(
    source: MatchingRecord,
    targets: tuple[MatchingRecord, ...],
    *,
    lexical_threshold: float = 0.65,
    limit: int = 20,
) -> CandidateGenerationResult:
    if not 0 <= lexical_threshold <= 1:
        raise ValueError("lexical_threshold must be between zero and one")
    if limit < 1:
        raise ValueError("limit must be positive")

    source_features = source.features()
    by_target: dict[tuple[str, str], list[MethodEvidence]] = {}
    target_by_id: dict[tuple[str, str], MatchingRecord] = {}
    for target in sorted(
        targets, key=lambda item: (item.jurisdiction, item.record_id)
    ):
        if target.jurisdiction == source.jurisdiction:
            continue
        target_key = (target.jurisdiction, target.record_id)
        target_by_id.setdefault(target_key, target)
        identifiers = shared_identifiers(source.identifiers, target.identifiers)
        lexical = compare_features(source_features, target.features())
        score = lexical_score(lexical)
        evidence: list[MethodEvidence] = []
        if identifiers:
            evidence.append(
                MethodEvidence(
                    method=CandidateMethod.IDENTIFIER,
                    identifier_matches=identifiers,
                    score=1.0,
                )
            )
        if score >= lexical_threshold:
            evidence.append(
                MethodEvidence(
                    method=CandidateMethod.LEXICAL,
                    lexical_features=lexical,
                    score=score,
                )
            )
        if evidence:
            by_target.setdefault(target_key, []).extend(evidence)

    ordered: list[tuple[MatchingRecord, tuple[MethodEvidence, ...], float]] = []
    for target_key, raw_evidence in by_target.items():
        deduplicated = {
            (item.method, item.model_dump_json()): item for item in raw_evidence
        }
        combined_evidence = tuple(
            sorted(
                deduplicated.values(),
                key=lambda item: (
                    0 if item.method is CandidateMethod.IDENTIFIER else 1,
                    -item.score,
                ),
            )
        )
        score = max(item.score for item in combined_evidence)
        ordered.append((target_by_id[target_key], combined_evidence, score))
    ordered.sort(
        key=lambda item: (
            0
            if any(
                evidence.method is CandidateMethod.IDENTIFIER
                for evidence in item[1]
            )
            else 1,
            -item[2],
            item[0].jurisdiction,
            item[0].record_id,
        )
    )
    candidates = tuple(
        MatchCandidate(
            source_record_id=source.record_id,
            target_record_id=target.record_id,
            target_jurisdiction=target.jurisdiction,
            rank=rank,
            score=score,
            methods=tuple(item.method for item in evidence),
            evidence=evidence,
        )
        for rank, (target, evidence, score) in enumerate(
            ordered[:limit], start=1
        )
    )
    return CandidateGenerationResult(
        source_record_id=source.record_id,
        candidates=candidates,
        abstained=not candidates,
        abstention_reason=(
            AbstentionReason.INSUFFICIENT_EVIDENCE if not candidates else None
        ),
    )
