import pytest

from global_medicines_atlas.matching import (
    MatchingRecord,
    generate_candidates,
)
from global_medicines_atlas.matching_models import (
    AbstentionReason,
    CandidateMethod,
)
from global_medicines_atlas.models import Identifier


def _record(
    record_id: str,
    name: str,
    *,
    identifier: str | None = None,
    jurisdiction: str | None = None,
    strength: int = 500,
) -> MatchingRecord:
    return MatchingRecord(
        record_id=record_id,
        jurisdiction=(
            jurisdiction
            if jurisdiction is not None
            else ("NZ" if record_id.startswith("nz") else "AU")
        ),
        name=name,
        identifiers=(
            (Identifier(system="urn:gtin", value=identifier),)
            if identifier
            else ()
        ),
        ingredients=("paracetamol",),
        strength_value=strength,
        strength_unit="mg",
        dose_form="tablet",
        route="oral",
    )


def test_identifier_candidates_precede_higher_lexical_only_candidates() -> None:
    source = _record("nz-1", "Paracetamol Brand", identifier="123")
    lexical = _record("au-lexical", "Paracetamol Brand")
    identifier = _record(
        "au-identifier", "Completely different label", identifier="123"
    )

    result = generate_candidates(source, (lexical, identifier))

    assert [item.target_record_id for item in result.candidates] == [
        "au-identifier",
        "au-lexical",
    ]
    assert result.candidates[0].methods[0] is CandidateMethod.IDENTIFIER
    assert all(item.pending_review for item in result.candidates)
    assert [item.rank for item in result.candidates] == [1, 2]
    assert result.candidates[0].score == pytest.approx(1.0)
    assert result.candidates[0].evidence[0].score == pytest.approx(1.0)
    assert result.source_record_id == source.record_id
    assert result.abstained is False
    assert result.abstention_reason is None
    assert result.absence_is_negative_proof is False


def test_duplicate_target_ids_are_deduplicated_deterministically() -> None:
    source = _record("nz-1", "Paracetamol", identifier="123")
    target = _record("au-1", "Paracetamol", identifier="123")

    result = generate_candidates(source, (target, target))

    assert len(result.candidates) == 1
    assert result.candidates[0].methods == (
        CandidateMethod.IDENTIFIER,
        CandidateMethod.LEXICAL,
    )
    assert tuple(
        evidence.method for evidence in result.candidates[0].evidence
    ) == (CandidateMethod.IDENTIFIER, CandidateMethod.LEXICAL)


def test_same_jurisdiction_targets_are_excluded() -> None:
    source = _record("nz-1", "Paracetamol", identifier="123")
    same_jurisdiction = _record(
        "nz-2",
        "Paracetamol",
        identifier="123",
        jurisdiction="NZ",
    )
    cross_jurisdiction = _record(
        "au-1",
        "Paracetamol",
        identifier="123",
        jurisdiction="AU",
    )

    result = generate_candidates(
        source, (same_jurisdiction, cross_jurisdiction)
    )

    assert [
        (item.target_jurisdiction, item.target_record_id)
        for item in result.candidates
    ] == [("AU", "au-1")]


def test_jurisdiction_local_identifier_collisions_are_preserved() -> None:
    source = _record("nz-1", "Paracetamol", identifier="123")
    australian = _record(
        "local-1",
        "Paracetamol",
        identifier="123",
        jurisdiction="AU",
    )
    canadian = _record(
        "local-1",
        "Paracetamol",
        identifier="123",
        jurisdiction="CA",
    )

    forward = generate_candidates(source, (canadian, australian))
    reverse = generate_candidates(source, (australian, canadian))

    expected = [("AU", "local-1"), ("CA", "local-1")]
    assert [
        (item.target_jurisdiction, item.target_record_id)
        for item in forward.candidates
    ] == expected
    assert forward == reverse


def test_no_candidate_abstains_without_negative_proof() -> None:
    source = MatchingRecord(
        record_id="nz-1", jurisdiction="NZ", name="Medicine Alpha"
    )
    target = MatchingRecord(
        record_id="au-1", jurisdiction="AU", name="Unrelated Beta"
    )

    result = generate_candidates(source, (target,), lexical_threshold=0.99)

    assert result.abstained
    assert result.abstention_reason is AbstentionReason.INSUFFICIENT_EVIDENCE
    assert result.absence_is_negative_proof is False
    assert result.source_record_id == "nz-1"
    assert result.candidates == ()


@pytest.mark.parametrize("threshold", [-0.001, 1.001])
def test_lexical_threshold_rejects_values_outside_closed_interval(
    threshold: float,
) -> None:
    source = _record("nz-1", "Paracetamol")

    with pytest.raises(ValueError, match="between zero and one"):
        generate_candidates(source, (), lexical_threshold=threshold)


def test_lexical_threshold_accepts_both_closed_interval_boundaries() -> None:
    source = _record("nz-1", "Paracetamol")
    target = _record("au-1", "Different medicine")

    at_zero = generate_candidates(source, (target,), lexical_threshold=0)
    at_one = generate_candidates(source, (target,), lexical_threshold=1)

    assert len(at_zero.candidates) == 1
    assert at_zero.candidates[0].methods == (CandidateMethod.LEXICAL,)
    assert at_one.candidates == ()


def test_limit_is_positive_and_applied_after_deterministic_ranking() -> None:
    source = _record("nz-1", "Paracetamol", identifier="123")
    targets = (
        _record("ca-2", "Paracetamol", identifier="123", jurisdiction="CA"),
        _record("au-2", "Paracetamol", identifier="123", jurisdiction="AU"),
        _record("au-1", "Paracetamol", identifier="123", jurisdiction="AU"),
    )

    with pytest.raises(ValueError, match="limit must be positive"):
        generate_candidates(source, targets, limit=0)

    result = generate_candidates(source, targets, limit=2)

    assert [
        (item.rank, item.target_jurisdiction, item.target_record_id)
        for item in result.candidates
    ] == [(1, "AU", "au-1"), (2, "AU", "au-2")]
