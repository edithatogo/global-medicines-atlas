"""Medicine-data integrity threat exercises."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from pydantic import ValidationError

from global_medicines_atlas.data_integrity import (
    DataIntegrityReceipt,
    IdentifierClaim,
    IntegrityDisposition,
    IntegrityExerciseResult,
    IntegrityThreat,
    colliding_identifier_claims,
    qualify_payload,
    qualify_snapshot_freshness,
    qualify_status_claim,
    run_data_integrity_exercises,
)
from global_medicines_atlas.models import AssertionKind, EvidenceStatus

NOW = datetime(2026, 7, 31, 12, tzinfo=UTC)


def test_poisoned_payload_is_quarantined() -> None:
    trusted = b"trusted"
    assert (
        qualify_payload(b"poisoned", sha256(trusted).hexdigest())
        is IntegrityDisposition.QUARANTINE
    )
    assert (
        qualify_payload(trusted, sha256(trusted).hexdigest())
        is IntegrityDisposition.ACCEPT
    )


@pytest.mark.parametrize("digest", ["bad", "z" * 64])
def test_invalid_trusted_digest_is_rejected(digest: str) -> None:
    with pytest.raises(ValueError, match="64 hexadecimal"):
        qualify_payload(b"payload", digest)


@pytest.mark.parametrize(
    ("retrieved_at", "expected"),
    [
        (NOW - timedelta(days=30), IntegrityDisposition.ACCEPT),
        (NOW - timedelta(days=30, seconds=1), IntegrityDisposition.BLOCK),
        (NOW + timedelta(seconds=1), IntegrityDisposition.BLOCK),
    ],
)
def test_snapshot_freshness_fails_closed(
    retrieved_at: datetime,
    expected: IntegrityDisposition,
) -> None:
    assert (
        qualify_snapshot_freshness(
            retrieved_at=retrieved_at,
            current_at=NOW,
            maximum_age=timedelta(days=30),
        )
        is expected
    )


def test_snapshot_freshness_requires_aware_time_and_positive_age() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        qualify_snapshot_freshness(
            retrieved_at=NOW.replace(tzinfo=None),
            current_at=NOW,
            maximum_age=timedelta(days=1),
        )
    with pytest.raises(ValueError, match="maximum_age must be positive"):
        qualify_snapshot_freshness(
            retrieved_at=NOW,
            current_at=NOW,
            maximum_age=timedelta(0),
        )


def test_identifier_collisions_remain_source_scoped() -> None:
    claims = (
        IdentifierClaim(
            jurisdiction="NZ",
            source_id="nzulm",
            system="local",
            value="42",
            concept_id="nz:42",
        ),
        IdentifierClaim(
            jurisdiction="AU",
            source_id="artg",
            system="local",
            value="42",
            concept_id="au:42",
        ),
    )
    assert set(colliding_identifier_claims(claims)) == set(claims)
    assert claims[0].scoped_key != claims[1].scoped_key


def test_duplicate_scoped_identifier_is_rejected() -> None:
    claim = IdentifierClaim(
        jurisdiction="NZ",
        source_id="nzulm",
        system="local",
        value="42",
        concept_id="nz:42",
    )
    with pytest.raises(ValueError, match="Duplicate source-scoped"):
        colliding_identifier_claims((claim, claim))


@pytest.mark.parametrize(
    ("source", "asserted", "evidence", "expected"),
    [
        (
            AssertionKind.REGULATORY,
            AssertionKind.REGULATORY,
            EvidenceStatus.CONFIRMED,
            IntegrityDisposition.ACCEPT,
        ),
        (
            AssertionKind.FUNDING,
            AssertionKind.REGULATORY,
            EvidenceStatus.CONFIRMED,
            IntegrityDisposition.BLOCK,
        ),
        (
            AssertionKind.REGULATORY,
            AssertionKind.REGULATORY,
            EvidenceStatus.INFERRED,
            IntegrityDisposition.BLOCK,
        ),
    ],
)
def test_status_claim_requires_matching_confirmed_evidence(
    source: AssertionKind,
    asserted: AssertionKind,
    evidence: EvidenceStatus,
    expected: IntegrityDisposition,
) -> None:
    assert (
        qualify_status_claim(
            source_dimension=source,
            asserted_dimension=asserted,
            evidence_status=evidence,
        )
        is expected
    )


def test_complete_threat_exercise_receipt_is_deterministic() -> None:
    receipt = run_data_integrity_exercises(executed_at=NOW)
    assert receipt.executed_at == NOW
    assert {result.threat for result in receipt.results} == set(IntegrityThreat)
    assert all(result.passed for result in receipt.results)
    assert all(
        result.disposition is not IntegrityDisposition.ACCEPT
        for result in receipt.results
    )


def test_receipt_rejects_missing_or_unsafe_exercises() -> None:
    unsafe = {
        "threat": IntegrityThreat.POISONED_DOWNLOAD,
        "disposition": IntegrityDisposition.ACCEPT,
        "control": "digest",
        "observed": "poison accepted",
        "passed": True,
    }
    with pytest.raises(ValidationError, match="blocking control"):
        IntegrityExerciseResult.model_validate(unsafe)
    with pytest.raises(ValidationError, match="at least 4 items"):
        DataIntegrityReceipt(executed_at=NOW, results=())

    blocked = tuple(
        IntegrityExerciseResult(
            threat=threat,
            disposition=IntegrityDisposition.BLOCK,
            control="control",
            observed="blocked",
            passed=True,
        )
        for threat in IntegrityThreat
    )
    with pytest.raises(ValidationError, match="duplicate integrity threats"):
        DataIntegrityReceipt(
            executed_at=NOW,
            results=(*blocked, blocked[0]),
        )
    with pytest.raises(ValidationError, match="every integrity threat once"):
        DataIntegrityReceipt(
            executed_at=NOW,
            results=(blocked[0],) * 4,
        )
    failed = blocked[0].model_copy(update={"passed": False})
    with pytest.raises(ValidationError, match="Every integrity threat"):
        DataIntegrityReceipt(
            executed_at=NOW,
            results=(failed, *blocked[1:]),
        )
