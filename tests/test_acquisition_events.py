"""Append-only acquisition events keep history distinct from payload identity."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_landing import land_bronze_payload
from global_medicines_atlas.receipts import (
    AcquisitionEvent,
    PayloadEvidence,
    SourceReceipt,
    TemporalIdentity,
    acquisition_event_id_for,
    acquisition_id_for,
    content_id_for,
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/bronze-acquisition-event-v3.json"
PAYLOAD = b'{"application_number":"012345"}'
NOW = datetime(2026, 8, 20, 6, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=3)
PUBLISHED = datetime(2026, 1, 15, tzinfo=UTC)
SHA = "a" * 64


def _landable(
    *,
    retrieved_at: datetime = NOW,
    payload: bytes = PAYLOAD,
) -> SourceReceipt:
    receipt = source_receipt()
    evidence = PayloadEvidence.from_bytes(payload)
    retrieval = receipt.retrieval.model_copy(
        update={"retrieved_at": retrieved_at}
    )
    return receipt.model_copy(
        update={
            "payload": evidence,
            "retrieval": retrieval,
            "reuse": acquire_new_decision(receipt.source.source_id),
            "temporal": temporal_identity_from_source(
                retrieved_at=retrieved_at,
                source_id=receipt.source.source_id,
                payload_sha256=evidence.sha256,
                source_published_at=None,
                original_uri=str(retrieval.uri),
                source_version=receipt.source.catalog_version,
            ),
        }
    )


@pytest.mark.unit
def test_six_identities_are_independent() -> None:
    identity = temporal_identity_from_source(
        retrieved_at=NOW,
        source_id="us-drugsfda",
        payload_sha256=SHA,
        source_published_at=PUBLISHED,
        source_effective_at=PUBLISHED,
        valid_from=datetime(2026, 2, 1, tzinfo=UTC),
        valid_to=datetime(2026, 12, 31, tzinfo=UTC),
        source_version="2026-01-15",
        original_uri="https://example.test/drugsfda.zip",
    )

    assert identity.content_id == content_id_for(payload_sha256=SHA)
    assert identity.acquisition_id == acquisition_event_id_for(
        source_id="us-drugsfda",
        payload_sha256=SHA,
        retrieved_at=NOW,
        source_version="2026-01-15",
        original_uri="https://example.test/drugsfda.zip",
    )
    assert identity.content_id != identity.acquisition_id
    assert identity.source_version == "2026-01-15"
    assert identity.source_published_at == PUBLISHED
    assert identity.source_effective_at == PUBLISHED
    assert identity.retrieved_at == NOW
    assert identity.retrieved_at != identity.source_published_at
    assert identity.valid_from is not None
    assert identity.valid_to is not None


@pytest.mark.unit
def test_legacy_acquisition_id_for_remains_content_stable() -> None:
    first = acquisition_id_for(source_id="us-drugsfda", payload_sha256=SHA)
    second = acquisition_id_for(source_id="us-drugsfda", payload_sha256=SHA)
    assert first == second
    assert first != content_id_for(payload_sha256=SHA)


@pytest.mark.unit
def test_same_bytes_different_retrievals_keep_history() -> None:
    first = temporal_identity_from_source(
        retrieved_at=NOW,
        source_id="us-drugsfda",
        payload_sha256=SHA,
    )
    second = temporal_identity_from_source(
        retrieved_at=LATER,
        source_id="us-drugsfda",
        payload_sha256=SHA,
    )

    assert first.content_id == second.content_id == SHA
    assert first.acquisition_id != second.acquisition_id


@pytest.mark.unit
def test_valid_interval_absent_when_source_did_not_supply_it() -> None:
    identity = temporal_identity_from_source(
        retrieved_at=NOW,
        source_id="us-drugsfda",
        payload_sha256=SHA,
    )
    assert identity.valid_from is None
    assert identity.valid_to is None
    assert identity.source_published_at is None


@pytest.mark.unit
def test_legacy_temporal_json_without_content_id_still_validates() -> None:
    legacy = {
        "retrieved_at": NOW.isoformat(),
        "acquisition_id": SHA,
    }
    identity = TemporalIdentity.model_validate(legacy)
    assert identity.acquisition_id == SHA
    assert identity.content_id is None
    assert identity.source_version is None


@pytest.mark.unit
def test_source_receipt_binds_content_id_from_payload_digest() -> None:
    dumped = source_receipt().model_dump(mode="python")
    dumped["temporal"]["content_id"] = None
    rebuilt = SourceReceipt.model_validate(dumped)
    assert rebuilt.temporal is not None
    assert rebuilt.temporal.content_id == rebuilt.payload.sha256


@pytest.mark.unit
def test_receipt_copy_keeps_content_id_coupled_to_payload() -> None:
    receipt = source_receipt()
    payload = PayloadEvidence.from_bytes(b"member-bytes")
    copied = receipt.model_copy(update={"payload": payload})
    assert copied.temporal is not None
    assert receipt.temporal is not None
    assert copied.payload.sha256 == payload.sha256
    assert copied.temporal.content_id == payload.sha256
    assert copied.temporal.acquisition_id == receipt.temporal.acquisition_id


@pytest.mark.unit
def test_identical_bytes_are_deduplicated_but_events_are_appended(
    tmp_path: Path,
) -> None:
    first = land_bronze_payload(
        PAYLOAD,
        _landable(retrieved_at=NOW),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    second = land_bronze_payload(
        PAYLOAD,
        _landable(retrieved_at=LATER),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )

    assert first.payload_path == second.payload_path
    assert first.payload_path.read_bytes() == PAYLOAD
    assert first.receipt.temporal.acquisition_id != (
        second.receipt.temporal.acquisition_id
    )
    assert first.receipt.temporal.content_id == (
        second.receipt.temporal.content_id
    )
    assert first.receipt_path != second.receipt_path
    assert first.receipt_path.is_file()
    assert second.receipt_path.is_file()
    event_dir = (
        tmp_path / "bronze" / "acquisitions" / "medsafe-product-register"
    )
    event_ids = {path.stem for path in event_dir.glob("*.json")}
    assert first.receipt.temporal.acquisition_id in event_ids
    assert second.receipt.temporal.acquisition_id in event_ids


@pytest.mark.unit
def test_existing_payload_bytes_are_never_mutated(tmp_path: Path) -> None:
    landing = land_bronze_payload(
        PAYLOAD,
        _landable(),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    landing.payload_path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="content store"):
        land_bronze_payload(
            PAYLOAD,
            _landable(retrieved_at=LATER),
            bronze_root=tmp_path / "bronze",
            media_hint="json",
        )
    assert landing.payload_path.read_bytes() == b"tampered"


@pytest.mark.unit
def test_acquisition_event_file_is_append_only(tmp_path: Path) -> None:
    receipt = _landable()
    landing = land_bronze_payload(
        PAYLOAD,
        receipt,
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    event_path = (
        tmp_path
        / "bronze"
        / "acquisitions"
        / receipt.source.source_id
        / f"{receipt.temporal.acquisition_id}.json"
    )
    event_path.write_bytes(b'{"mutated":true}\n')
    with pytest.raises(ValueError, match="append-only"):
        land_bronze_payload(
            PAYLOAD,
            receipt,
            bronze_root=tmp_path / "bronze",
            media_hint="json",
        )
    assert event_path.read_bytes() == b'{"mutated":true}\n'
    assert landing.payload_path.read_bytes() == PAYLOAD


@pytest.mark.unit
def test_acquisition_event_schema_accepts_canonical_dump(
    tmp_path: Path,
) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    landing = land_bronze_payload(
        PAYLOAD,
        _landable(),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    event_path = (
        tmp_path
        / "bronze"
        / "acquisitions"
        / landing.receipt.source.source_id
        / f"{landing.receipt.temporal.acquisition_id}.json"
    )
    document = json.loads(event_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(document)
    assert document["content_id"] == landing.receipt.payload.sha256
    assert document["acquisition_id"] == (
        landing.receipt.temporal.acquisition_id
    )


@pytest.mark.unit
def test_v2_acquisition_event_remains_migration_safe_without_sensitivity() -> (
    None
):
    receipt = _landable()
    temporal = receipt.temporal
    assert temporal is not None
    rebuilt = AcquisitionEvent.model_validate({
        "schema_version": 2,
        "acquisition_id": temporal.acquisition_id,
        "content_id": receipt.payload.sha256,
        "source_id": receipt.source.source_id,
        "retrieved_at": temporal.retrieved_at,
        "payload_sha256": receipt.payload.sha256,
    })
    assert rebuilt.schema_version == 2
    assert rebuilt.sensitivity.publication.value == "review_required"


@pytest.mark.edge
def test_event_model_rejects_collapsed_content_and_acquisition_ids() -> None:
    with pytest.raises(ValidationError, match="must not equal"):
        AcquisitionEvent(
            acquisition_id=SHA,
            content_id=SHA,
            source_id="us-drugsfda",
            source_version=None,
            retrieved_at=NOW,
            payload_sha256=SHA,
        )


@pytest.mark.edge
def test_event_model_rejects_content_id_decoupled_from_payload() -> None:
    other = "b" * 64
    with pytest.raises(ValidationError, match="must equal payload digest"):
        AcquisitionEvent(
            acquisition_id=SHA,
            content_id=other,
            source_id="us-drugsfda",
            source_version=None,
            retrieved_at=NOW,
            payload_sha256=SHA,
        )


@pytest.mark.property
@given(st.binary(min_size=1, max_size=256), st.binary(min_size=1, max_size=256))
def test_event_id_changes_when_retrieval_clock_or_bytes_change(
    first: bytes,
    second: bytes,
) -> None:
    digest_a = PayloadEvidence.from_bytes(first).sha256
    digest_b = PayloadEvidence.from_bytes(second).sha256
    event_a = acquisition_event_id_for(
        source_id="src",
        payload_sha256=digest_a,
        retrieved_at=NOW,
    )
    event_b = acquisition_event_id_for(
        source_id="src",
        payload_sha256=digest_a,
        retrieved_at=LATER,
    )
    event_c = acquisition_event_id_for(
        source_id="src",
        payload_sha256=digest_b,
        retrieved_at=NOW,
    )
    assert content_id_for(payload_sha256=digest_a) == digest_a
    assert event_a != event_b
    if first != second:
        assert digest_a != digest_b
        assert event_a != event_c


@pytest.mark.edge
def test_content_id_must_match_payload_digest() -> None:
    receipt = source_receipt()
    dumped = receipt.model_dump(mode="python")
    dumped["temporal"]["content_id"] = "b" * 64
    with pytest.raises(ValidationError, match="content_id"):
        SourceReceipt.model_validate(dumped)
