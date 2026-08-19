"""Bronze quarantine keeps evidentiary payloads even when processing fails."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionRecord,
    BronzeAdmissionState,
    DownstreamAdmissionError,
    ValidationResult,
    admit_bronze_landing,
    classify_bronze_payload,
    evaluate_bronze_admission,
    require_admitted_for_processing,
)
from global_medicines_atlas.bronze_landing import land_bronze_payload
from global_medicines_atlas.receipts import (
    PayloadEvidence,
    SourceReceipt,
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/bronze-admission-v1.json"
NOW = datetime(2026, 8, 20, 6, 30, tzinfo=UTC)
PAYLOAD = b'{"ok":true}'
MALFORMED = b"{not-json"


def _landable(payload: bytes = PAYLOAD) -> SourceReceipt:
    receipt = source_receipt()
    evidence = PayloadEvidence.from_bytes(payload)
    retrieval = receipt.retrieval.model_copy(update={"retrieved_at": NOW})
    return receipt.model_copy(
        update={
            "payload": evidence,
            "retrieval": retrieval,
            "reuse": acquire_new_decision(receipt.source.source_id),
            "temporal": temporal_identity_from_source(
                retrieved_at=NOW,
                source_id=receipt.source.source_id,
                payload_sha256=evidence.sha256,
                original_uri=str(retrieval.uri),
            ),
        }
    )


@pytest.mark.unit
def test_landed_payload_is_preserved_when_validation_fails(
    tmp_path: Path,
) -> None:
    landing = land_bronze_payload(
        MALFORMED,
        _landable(MALFORMED),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    record = evaluate_bronze_admission(landing)

    assert record.state is BronzeAdmissionState.QUARANTINED
    assert landing.payload_path.read_bytes() == MALFORMED
    assert "malformed_payload" in record.reason_codes
    with pytest.raises(DownstreamAdmissionError, match="fail closed"):
        require_admitted_for_processing(record)


@pytest.mark.unit
def test_accepted_material_is_consumable(tmp_path: Path) -> None:
    landing = land_bronze_payload(
        PAYLOAD,
        _landable(),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    record = evaluate_bronze_admission(landing)
    admitted = require_admitted_for_processing(record)
    assert admitted.state is BronzeAdmissionState.ACCEPTED
    assert landing.payload_path.read_bytes() == PAYLOAD


@pytest.mark.unit
def test_quarantined_requires_explicit_authorization(tmp_path: Path) -> None:
    landing = land_bronze_payload(
        MALFORMED,
        _landable(MALFORMED),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    record = evaluate_bronze_admission(landing)
    authorized = require_admitted_for_processing(record, authorized=True)
    assert authorized.state is BronzeAdmissionState.QUARANTINED
    rejected = record.model_copy(
        update={"state": BronzeAdmissionState.REJECTED_FROM_PROCESSING}
    )
    with pytest.raises(DownstreamAdmissionError):
        require_admitted_for_processing(rejected, authorized=True)


@pytest.mark.unit
def test_admission_never_deletes_or_rewrites_payload(tmp_path: Path) -> None:
    landing = land_bronze_payload(
        MALFORMED,
        _landable(MALFORMED),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    before = landing.payload_path.read_bytes()
    record = admit_bronze_landing(landing)
    assert landing.payload_path.read_bytes() == before == MALFORMED
    assert record.state is BronzeAdmissionState.QUARANTINED
    assert record.path.is_file()


@pytest.mark.unit
def test_landed_state_is_not_yet_processable() -> None:
    record = BronzeAdmissionRecord(
        acquisition_id="a" * 64,
        content_id="b" * 64,
        state=BronzeAdmissionState.LANDED,
        reason_codes=(),
        validation_results=(),
        reviewer_status="unreviewed",
    )
    with pytest.raises(DownstreamAdmissionError, match="not yet admitted"):
        require_admitted_for_processing(record)


@pytest.mark.unit
def test_admission_schema_round_trip(tmp_path: Path) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    landing = land_bronze_payload(
        PAYLOAD,
        _landable(),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    record = admit_bronze_landing(landing)
    document = json.loads(record.path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(document)
    assert document["state"] == "accepted"


@pytest.mark.edge
def test_schema_rejects_unknown_admission_state() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    with pytest.raises(Exception, match=r"enum|state"):
        validator.validate({
            "schema_id": "global-medicines-atlas.bronze-admission",
            "schema_version": 1,
            "acquisition_id": "a" * 64,
            "content_id": "b" * 64,
            "state": "deleted",
            "reason_codes": [],
            "validation_results": [],
            "reviewer_status": "unreviewed",
        })


@pytest.mark.edge
def test_admission_record_is_immutable() -> None:
    record = BronzeAdmissionRecord(
        acquisition_id="a" * 64,
        content_id="b" * 64,
        state=BronzeAdmissionState.LANDED,
        reason_codes=("incomplete_payload",),
        validation_results=(
            ValidationResult(
                check_id="json-parse",
                passed=False,
                message="truncated",
            ),
        ),
        reviewer_status="unreviewed",
    )
    with pytest.raises(ValidationError):
        record.state = BronzeAdmissionState.ACCEPTED


@pytest.mark.property
@given(st.binary(min_size=1, max_size=128))
def test_payload_classification_never_drops_bytes(payload: bytes) -> None:
    record = classify_bronze_payload(payload)
    assert record.content_id == PayloadEvidence.from_bytes(payload).sha256
    try:
        parsed = json.loads(payload)
        well_formed = isinstance(parsed, dict)
    except json.JSONDecodeError, UnicodeDecodeError, ValueError:
        well_formed = False
    if well_formed:
        assert record.state is BronzeAdmissionState.ACCEPTED
    else:
        assert record.state is BronzeAdmissionState.QUARANTINED
