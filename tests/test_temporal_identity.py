"""Temporal identity fields stay independent on every acquisition."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.receipts import (
    acquisition_id_for,
    temporal_identity_from_source,
)

NOW = datetime(2026, 8, 19, 8, 0, tzinfo=UTC)
PUBLISHED = datetime(2026, 1, 15, tzinfo=UTC)
VALID_FROM = datetime(2026, 2, 1, tzinfo=UTC)
VALID_TO = datetime(2026, 12, 31, tzinfo=UTC)
SHA = "a" * 64


@pytest.mark.unit
def test_temporal_fields_are_distinct() -> None:
    identity = temporal_identity_from_source(
        retrieved_at=NOW,
        source_id="us-drugsfda",
        payload_sha256=SHA,
        source_published_at=PUBLISHED,
        source_effective_at=PUBLISHED,
        valid_from=VALID_FROM,
        valid_to=VALID_TO,
    )

    assert identity.retrieved_at == NOW
    assert identity.source_published_at == PUBLISHED
    assert identity.source_published_at != identity.retrieved_at
    assert identity.valid_from == VALID_FROM
    assert identity.valid_to == VALID_TO
    assert identity.acquisition_id == acquisition_id_for(
        source_id="us-drugsfda",
        payload_sha256=SHA,
    )


@pytest.mark.unit
def test_substituting_retrieved_at_for_published_time_fails() -> None:
    with pytest.raises(ValueError, match="retrieved_at"):
        temporal_identity_from_source(
            retrieved_at=NOW,
            source_id="us-drugsfda",
            payload_sha256=SHA,
            substitute_retrieved_as_published=True,
        )


@pytest.mark.unit
def test_valid_times_absent_when_source_did_not_supply_them() -> None:
    identity = temporal_identity_from_source(
        retrieved_at=NOW,
        source_id="us-drugsfda",
        payload_sha256=SHA,
    )

    assert identity.source_published_at is None
    assert identity.valid_from is None
    assert identity.valid_to is None
    assert identity.retrieved_at == NOW


@pytest.mark.unit
def test_receipt_does_not_fill_published_from_retrieved() -> None:
    receipt = source_receipt()

    assert receipt.temporal.retrieved_at == receipt.retrieval.retrieved_at
    assert receipt.temporal.source_published_at is None
    assert receipt.temporal.acquisition_id == acquisition_id_for(
        source_id=receipt.source.source_id,
        payload_sha256=receipt.payload.sha256,
    )


@pytest.mark.unit
def test_acquisition_id_stable_for_same_payload() -> None:
    first = acquisition_id_for(source_id="us-drugsfda", payload_sha256=SHA)
    second = acquisition_id_for(source_id="us-drugsfda", payload_sha256=SHA)
    other = acquisition_id_for(
        source_id="us-drugsfda",
        payload_sha256="b" * 64,
    )

    assert first == second
    assert first != other


@pytest.mark.edge
def test_valid_interval_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        temporal_identity_from_source(
            retrieved_at=NOW,
            source_id="us-drugsfda",
            payload_sha256=SHA,
            valid_from=NOW,
            valid_to=NOW - timedelta(days=1),
        )
