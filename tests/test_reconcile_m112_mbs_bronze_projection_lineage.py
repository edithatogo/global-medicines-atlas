"""Reconciliation tests for MBS Bronze projection replay."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pyarrow.parquet as pq
from pydantic import AnyUrl
from scripts.reconcile_m112_mbs_bronze_projection_lineage import (
    rebuild_projection_bytes,
)

from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
)

FIXTURE = Path(__file__).parent / "fixtures" / "adapters" / "au_mbs.xml"
FIXTURE_RECORD_COUNT = 2


def _receipt(payload: bytes) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id="fixture:m112-mbs-bronze-projection",
        source=SourceIdentity(
            catalog_id="au-mbs",
            source_id="au-mbs",
            jurisdiction="AUS",
            authority="Australian Government Department of Health",
            dataset_title="Synthetic MBS source fixture",
            catalog_version="fixture-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("https://fixtures.invalid/au-mbs"),
            retrieved_at=datetime(2026, 8, 29, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id="au-mbs-source-fixture",
            transformation_sha256="a" * 64,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def test_projection_replay_is_deterministic_and_keeps_p7_selection() -> None:
    payload = FIXTURE.read_bytes()
    receipt = _receipt(payload)

    first = rebuild_projection_bytes(
        payload, receipt, expected_record_count=FIXTURE_RECORD_COUNT
    )
    second = rebuild_projection_bytes(
        payload, receipt, expected_record_count=FIXTURE_RECORD_COUNT
    )

    assert set(first) == {"source.parquet", "p7.parquet"}
    assert first == second
    assert (
        hashlib.sha256(first["source.parquet"]).hexdigest()
        == hashlib.sha256(second["source.parquet"]).hexdigest()
    )
    assert (
        pq.read_table(BytesIO(first["source.parquet"])).num_rows  # pyright: ignore[reportUnknownMemberType]
        == FIXTURE_RECORD_COUNT
    )
    assert (
        pq.read_table(BytesIO(first["p7.parquet"])).num_rows  # pyright: ignore[reportUnknownMemberType]
        == FIXTURE_RECORD_COUNT
    )
    p7_schema = pq.read_schema(BytesIO(first["p7.parquet"]))  # pyright: ignore[reportUnknownMemberType]
    assert p7_schema.metadata is not None
    assert p7_schema.metadata[b"selection"] == b"Group=P7"
