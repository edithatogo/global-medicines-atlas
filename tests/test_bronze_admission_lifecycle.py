"""Admission gates every record-level Bronze projection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionState,
    DownstreamAdmissionError,
    record_admission_decision,
)
from global_medicines_atlas.bronze_landing import (
    BronzeAcquisition,
    BronzeLanding,
    land_bronze_payload,
    regenerate_parquet,
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
