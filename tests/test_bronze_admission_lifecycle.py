"""Admission gates every record-level Bronze projection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tests.test_source_receipts import source_receipt

from global_medicines_atlas import bronze_landing
from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionState,
    DownstreamAdmissionError,
    admit_bronze_landing,
    create_admission_decision,
    latest_admission_decision,
    persist_admission_decision,
    record_admission_decision,
)
from global_medicines_atlas.bronze_landing import (
    BronzeAcquisition,
    BronzeLanding,
    land_bronze_payload,
    regenerate_parquet,
)
from global_medicines_atlas.bronze_transformation import (
    TransformationRunReceipt,
)
from global_medicines_atlas.receipts import (
    PayloadEvidence,
    require_temporal,
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision

NOW = datetime(2026, 8, 20, 8, 30, tzinfo=UTC)
VALID = b'{"medicine":"accepted"}'
MALFORMED = b"{not-json"
NON_OBJECT = b"[]"


def _receipt(payload: bytes):
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


def _admission_events(acquisition: BronzeAcquisition):
    root = acquisition.receipt_path.parents[2]
    source_id = acquisition.receipt.source.source_id
    acquisition_id = require_temporal(
        acquisition.receipt.temporal
    ).acquisition_id
    paths = sorted(
        (root / "admissions" / source_id / acquisition_id).glob("*.json")
    )
    return tuple(
        type(acquisition.admission)
        .model_validate_json(path.read_bytes())
        .model_copy(update={"path": path})
        for path in paths
    )


@pytest.mark.unit
def test_malformed_payload_is_quarantined_before_projection(
    tmp_path: Path,
) -> None:
    outcome = land_bronze_payload(
        MALFORMED,
        _receipt(MALFORMED),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
        admission_decided_at=NOW,
    )

    assert type(outcome) is BronzeAcquisition
    assert outcome.payload_path.read_bytes() == MALFORMED
    assert outcome.acquisition_receipt_path.is_file()
    assert outcome.receipt_path.is_file()
    assert outcome.landed_admission.state is BronzeAdmissionState.LANDED
    assert outcome.admission.state is BronzeAdmissionState.QUARANTINED
    assert outcome.admission.supersedes_decision_id == (
        outcome.landed_admission.decision_id
    )
    assert len(_admission_events(outcome)) == 2
    assert not (tmp_path / "bronze" / "parquet").exists()
    assert not (tmp_path / "bronze" / "lineage").exists()
    assert not (tmp_path / "bronze" / "transformations").exists()


@pytest.mark.unit
def test_json_array_is_admitted_without_universal_object_assumption(
    tmp_path: Path,
) -> None:
    outcome = land_bronze_payload(
        NON_OBJECT,
        _receipt(NON_OBJECT),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
        admission_decided_at=NOW,
    )

    assert isinstance(outcome, BronzeLanding)
    assert outcome.admission.state is BronzeAdmissionState.ACCEPTED
    assert outcome.admission.reason_codes == ()


@pytest.mark.unit
def test_acceptance_precedes_parquet_and_lineage_projection(
    tmp_path: Path,
) -> None:
    outcome = land_bronze_payload(
        VALID,
        _receipt(VALID),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
        admission_decided_at=NOW,
        transformation_completed_at=NOW + timedelta(seconds=1),
    )

    assert isinstance(outcome, BronzeLanding)
    assert outcome.landed_admission.state is BronzeAdmissionState.LANDED
    assert outcome.admission.state is BronzeAdmissionState.ACCEPTED
    assert outcome.admission.supersedes_decision_id == (
        outcome.landed_admission.decision_id
    )
    assert (
        outcome.admission.decided_at <= outcome.transformation_run.completed_at
    )
    assert outcome.parquet_path.is_file()
    assert outcome.lineage_path.is_file()
    assert outcome.transformation_receipt_path.is_file()
    assert len(_admission_events(outcome)) == 2


@pytest.mark.unit
def test_human_review_supersedes_without_overwriting_history(
    tmp_path: Path,
) -> None:
    outcome = land_bronze_payload(
        VALID,
        _receipt(VALID),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
        admission_decided_at=NOW,
        transformation_completed_at=NOW,
    )
    assert isinstance(outcome, BronzeLanding)
    previous_paths = {item.path for item in _admission_events(outcome)}

    reviewed = record_admission_decision(
        outcome,
        state=BronzeAdmissionState.REJECTED_FROM_PROCESSING,
        actor="maintainer:review",
        decided_at=NOW + timedelta(minutes=1),
        reason_codes=("human_review_rejected",),
        supersedes_decision_id=outcome.admission.decision_id,
    )

    assert reviewed.supersedes_decision_id == outcome.admission.decision_id
    assert reviewed.path is not None
    assert reviewed.path.is_file()
    assert len(_admission_events(outcome)) == 3
    assert all(path is not None and path.is_file() for path in previous_paths)
    with pytest.raises(DownstreamAdmissionError, match="fail closed"):
        regenerate_parquet(outcome)


@pytest.mark.unit
def test_admission_persistence_rejects_mismatched_identity(
    tmp_path: Path,
) -> None:
    outcome = land_bronze_payload(
        VALID,
        _receipt(VALID),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
        admission_decided_at=NOW,
        transformation_completed_at=NOW,
    )
    assert isinstance(outcome, BronzeLanding)

    with pytest.raises(ValueError, match="does not match acquisition"):
        persist_admission_decision(
            outcome.admission.model_copy(update={"acquisition_id": "f" * 64}),
            receipt_path=outcome.receipt_path,
            receipt=outcome.receipt,
        )
    with pytest.raises(ValueError, match="does not match content"):
        persist_admission_decision(
            outcome.admission.model_copy(update={"content_id": "e" * 64}),
            receipt_path=outcome.receipt_path,
            receipt=outcome.receipt,
        )
    with pytest.raises(ValueError, match="cannot be rewritten"):
        persist_admission_decision(
            outcome.admission.model_copy(update={"actor": "tampered"}),
            receipt_path=outcome.receipt_path,
            receipt=outcome.receipt,
        )


@pytest.mark.unit
def test_latest_admission_rejects_missing_or_branched_history(
    tmp_path: Path,
) -> None:
    outcome = land_bronze_payload(
        VALID,
        _receipt(VALID),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
        admission_decided_at=NOW,
        transformation_completed_at=NOW,
    )
    assert isinstance(outcome, BronzeLanding)
    admission_paths = {
        event.path
        for event in _admission_events(outcome)
        if event.path is not None
    }
    for path in admission_paths:
        path.unlink()
    with pytest.raises(DownstreamAdmissionError, match="no durable"):
        latest_admission_decision(outcome)

    temporal = require_temporal(outcome.receipt.temporal)
    independent = create_admission_decision(
        acquisition_id=temporal.acquisition_id,
        content_id=temporal.content_id or outcome.receipt.payload.sha256,
        state=BronzeAdmissionState.LANDED,
        reason_codes=("independent_review",),
        actor="maintainer:review",
        decided_at=NOW + timedelta(minutes=1),
    )
    for record in (outcome.landed_admission, independent):
        persist_admission_decision(
            record,
            receipt_path=outcome.receipt_path,
            receipt=outcome.receipt,
        )
    with pytest.raises(DownstreamAdmissionError, match="one unsuperseded"):
        latest_admission_decision(outcome)


@pytest.mark.unit
def test_admission_history_rejects_corruption_and_unknown_predecessor(
    tmp_path: Path,
) -> None:
    outcome = land_bronze_payload(
        VALID,
        _receipt(VALID),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
        admission_decided_at=NOW,
        transformation_completed_at=NOW,
    )
    assert isinstance(outcome, BronzeLanding)

    unknown = create_admission_decision(
        acquisition_id=outcome.admission.acquisition_id,
        content_id=outcome.admission.content_id,
        state=BronzeAdmissionState.ACCEPTED,
        reason_codes=("reviewed",),
        actor="maintainer:review",
        decided_at=NOW + timedelta(minutes=1),
        supersedes_decision_id="f" * 64,
    )
    with pytest.raises(ValueError, match="does not exist"):
        persist_admission_decision(
            unknown,
            receipt_path=outcome.receipt_path,
            receipt=outcome.receipt,
        )

    assert outcome.admission.path is not None
    outcome.admission.path.write_bytes(b"not-json")
    with pytest.raises(ValueError, match="cannot be rewritten or corrupted"):
        latest_admission_decision(outcome)


@pytest.mark.unit
def test_review_defaults_to_latest_durable_predecessor(tmp_path: Path) -> None:
    outcome = land_bronze_payload(
        VALID,
        _receipt(VALID),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
        admission_decided_at=NOW,
        transformation_completed_at=NOW,
    )
    assert isinstance(outcome, BronzeLanding)

    reviewed = record_admission_decision(
        outcome,
        state=BronzeAdmissionState.ACCEPTED,
        actor="maintainer:review",
        decided_at=NOW + timedelta(minutes=1),
        reason_codes=("human_review_accepted",),
    )

    assert reviewed.supersedes_decision_id == outcome.admission.decision_id

    automated = admit_bronze_landing(
        outcome,
        decided_at=NOW + timedelta(minutes=2),
    )
    assert automated.state is BronzeAdmissionState.ACCEPTED
    assert automated.supersedes_decision_id == reviewed.decision_id


@pytest.mark.unit
def test_transformation_cannot_precede_admission(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot complete before admission"):
        land_bronze_payload(
            VALID,
            _receipt(VALID),
            bronze_root=tmp_path / "bronze",
            media_hint="json",
            admission_decided_at=NOW + timedelta(seconds=1),
            transformation_completed_at=NOW,
        )


@pytest.mark.unit
def test_transformation_requires_durable_run_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def discard_path(
        receipt: TransformationRunReceipt,
        **_kwargs: object,
    ) -> TransformationRunReceipt:
        return receipt

    monkeypatch.setattr(
        bronze_landing,
        "write_transformation_run_receipt",
        discard_path,
    )

    with pytest.raises(ValueError, match="receipt path is required"):
        land_bronze_payload(
            VALID,
            _receipt(VALID),
            bronze_root=tmp_path / "bronze",
            media_hint="json",
            admission_decided_at=NOW,
            transformation_completed_at=NOW,
        )
