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


def test_duplicate_target_ids_are_deduplicated_deterministically() -> None:
    source = _record("nz-1", "Paracetamol", identifier="123")
    target = _record("au-1", "Paracetamol", identifier="123")

    result = generate_candidates(source, (target, target))

    assert len(result.candidates) == 1
    assert result.candidates[0].methods == (
        CandidateMethod.IDENTIFIER,
        CandidateMethod.LEXICAL,
    )


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
