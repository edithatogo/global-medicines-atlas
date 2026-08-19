"""Payload evidentiary truth versus source-faithful Parquet."""

from __future__ import annotations

import pyarrow.parquet as pq
import pytest
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_landing import (
    EVIDENTIARY_TRUTH_SENTENCE,
    BronzeLanding,
    bronze_table_spec,
    land_bronze_payload,
    regenerate_parquet,
)
from global_medicines_atlas.receipts import (
    PayloadEvidence,
    SourceReceipt,
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision

PAYLOAD = b'{"application_number":"012345"}'


def _landable_receipt() -> SourceReceipt:
    receipt = source_receipt()
    payload = PayloadEvidence.from_bytes(PAYLOAD)
    return receipt.model_copy(
        update={
            "payload": payload,
            "reuse": acquire_new_decision(receipt.source.source_id),
            "temporal": temporal_identity_from_source(
                retrieved_at=receipt.retrieval.retrieved_at,
                source_id=receipt.source.source_id,
                payload_sha256=payload.sha256,
            ),
        }
    )


@pytest.mark.unit
def test_truth_sentence_keeps_three_way_split() -> None:
    assert "evidentiary truth" in EVIDENTIARY_TRUTH_SENTENCE
    assert "portable analytical representation" in EVIDENTIARY_TRUTH_SENTENCE
    assert "rebuildable metadata" in EVIDENTIARY_TRUTH_SENTENCE
    assert "Arrow/Parquet is portable" not in EVIDENTIARY_TRUTH_SENTENCE
    assert "raw-as-landed" not in EVIDENTIARY_TRUTH_SENTENCE


@pytest.mark.unit
def test_payload_bytes_are_preserved_and_parquet_is_not_the_payload(
    tmp_path,
) -> None:
    receipt = _landable_receipt()
    landing = land_bronze_payload(
        PAYLOAD,
        receipt,
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )

    assert landing.payload_path.read_bytes() == PAYLOAD
    assert landing.payload_path.suffix == ".json"
    table = pq.read_table(landing.parquet_path)
    assert table.column("payload_sha256")[0].as_py() == receipt.payload.sha256
    assert table.column("native_record")[0].as_py() == PAYLOAD.decode()
    assert landing.parquet_path.read_bytes() != PAYLOAD
    assert "evidentiary" not in landing.parquet_path.name


@pytest.mark.unit
def test_acquisition_id_immutable_across_parquet_regeneration(
    tmp_path,
) -> None:
    receipt = _landable_receipt()
    landing = land_bronze_payload(
        PAYLOAD,
        receipt,
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    original_id = landing.receipt.temporal.acquisition_id
    original_digest = landing.receipt.payload.sha256
    regenerate_parquet(landing)
    table = pq.read_table(landing.parquet_path)

    assert table.column("acquisition_id")[0].as_py() == original_id
    assert landing.payload_path.read_bytes() == PAYLOAD
    assert landing.receipt.payload.sha256 == original_digest
    assert landing.receipt.temporal.source_published_at is None


@pytest.mark.unit
def test_landing_without_reuse_gate_fails(tmp_path) -> None:
    with pytest.raises(ValueError, match="reuse gate"):
        land_bronze_payload(
            PAYLOAD,
            source_receipt(),
            bronze_root=tmp_path / "bronze",
        )


@pytest.mark.unit
def test_unknown_media_uses_bin_and_digest_must_match(tmp_path) -> None:
    receipt = _landable_receipt()
    landing = land_bronze_payload(
        PAYLOAD,
        receipt,
        bronze_root=tmp_path / "bronze",
    )
    assert landing.payload_path.suffix == ".bin"
    with pytest.raises(ValueError, match="digest"):
        land_bronze_payload(
            b"not-the-receipt-payload",
            receipt,
            bronze_root=tmp_path / "other",
            media_hint="json",
        )

    payload_path = tmp_path / "payload.bin"
    payload_path.write_bytes(PAYLOAD)
    parquet_path = tmp_path / "table.parquet"
    missing_reuse = BronzeLanding(
        payload_path=payload_path,
        parquet_path=parquet_path,
        receipt_path=tmp_path / "receipt.json",
        lineage_path=tmp_path / "lineage.json",
        table=bronze_table_spec(source_receipt(), parquet_path),
        receipt=source_receipt(),
    )
    with pytest.raises(ValueError, match="reuse gate"):
        regenerate_parquet(missing_reuse)
