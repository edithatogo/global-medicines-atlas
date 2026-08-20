# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false

"""Bronze reconstruction from immutable payloads and receipts."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from tests.test_source_receipts import source_receipt

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionState,
    record_admission_decision,
)
from global_medicines_atlas.bronze_landing import (
    PARQUET_DIR,
    PAYLOAD_DIR,
    RECEIPT_DIR,
    BronzeLanding,
    land_bronze_payload,
)
from global_medicines_atlas.bronze_recovery import (
    CATALOGUE_DIR,
    BronzeRecoveryError,
    RecoveryScenario,
    load_receipt_for_reconstruction,
    reconstruct_bronze,
    resume_interrupted_acquisition,
    write_recovery_evidence,
)
from global_medicines_atlas.receipts import (
    PayloadEvidence,
    SourceReceipt,
    require_temporal,
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision

PAYLOAD = b'{"application_number":"012345"}'
LATER_PAYLOAD = b'{"application_number":"999999"}'
NOW = datetime(2026, 8, 20, 6, 47, tzinfo=UTC)


def _landable(
    payload: bytes = PAYLOAD,
    *,
    retrieved_at: datetime = NOW,
    original_uri: str | None = None,
) -> SourceReceipt:
    receipt = source_receipt()
    evidence = PayloadEvidence.from_bytes(payload)
    retrieval = receipt.retrieval.model_copy(
        update={"retrieved_at": retrieved_at}
    )
    uri = original_uri or str(retrieval.uri)
    return receipt.model_copy(
        update={
            "payload": evidence,
            "retrieval": retrieval,
            "reuse": acquire_new_decision(receipt.source.source_id),
            "temporal": temporal_identity_from_source(
                retrieved_at=retrieved_at,
                source_id=receipt.source.source_id,
                payload_sha256=evidence.sha256,
                original_uri=uri,
            ),
        }
    )


def _seed_store(root: Path, payload: bytes = PAYLOAD) -> BronzeLanding:
    return land_bronze_payload(
        payload,
        _landable(payload),
        bronze_root=root,
        media_hint="json",
    )


def _acquisition_id(landing: BronzeLanding) -> str:
    return require_temporal(landing.receipt.temporal).acquisition_id


def _copy_truth(src: Path, dest: Path) -> None:
    for name in (PAYLOAD_DIR, RECEIPT_DIR):
        origin = src / name
        if not origin.exists():
            continue
        for path in origin.rglob("*"):
            if path.is_file():
                target = dest / path.relative_to(src)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())


@pytest.mark.unit
def test_clean_room_rebuild_from_payloads_and_receipts_only(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original"
    landing = _seed_store(original)
    empty = tmp_path / "clean-room"
    _copy_truth(original, empty)
    assert not list((empty / PARQUET_DIR).rglob("*.parquet"))
    assert not list((empty / CATALOGUE_DIR).rglob("*"))

    evidence = reconstruct_bronze(empty)

    rebuilt = pq.read_table(
        empty
        / PARQUET_DIR
        / landing.receipt.source.source_id
        / f"{_acquisition_id(landing)}.parquet"
    )
    assert rebuilt.column("payload_sha256")[0].as_py() == (
        landing.receipt.payload.sha256
    )
    assert rebuilt.column("acquisition_id")[0].as_py() == (
        _acquisition_id(landing)
    )
    assert evidence.hugging_face_is_source_of_truth is False
    assert RecoveryScenario.CLEAN_ROOM_REBUILD in evidence.scenarios
    assert "huggingface.co" not in evidence.canonical_json().decode()


@pytest.mark.unit
def test_rebuildable_databases_are_not_required(tmp_path: Path) -> None:
    bronze = tmp_path / "bronze"
    landing = _seed_store(bronze)
    duckdb = bronze / "analytics.duckdb"
    lance = bronze / "vectors.lancedb"
    duckdb.write_bytes(b"not-a-database")
    lance.mkdir()
    (lance / "table.lance").write_bytes(b"derived")
    duckdb.unlink()
    (lance / "table.lance").unlink()
    lance.rmdir()

    evidence = reconstruct_bronze(bronze)

    assert landing.payload_path.read_bytes() == PAYLOAD
    assert evidence.rebuildable_derivatives_absent is True
    assert RecoveryScenario.REBUILDABLE_DATABASE_LOSS in evidence.scenarios


@pytest.mark.unit
def test_catalogue_deletion_rebuilds_from_receipts(tmp_path: Path) -> None:
    bronze = tmp_path / "bronze"
    landing = _seed_store(bronze)
    reconstruct_bronze(bronze)
    catalogue_files = list((bronze / CATALOGUE_DIR).rglob("*.json"))
    assert catalogue_files
    for path in catalogue_files:
        path.unlink()

    evidence = reconstruct_bronze(bronze)

    restored = list((bronze / CATALOGUE_DIR).rglob("*.json"))
    assert restored
    body = json.loads(restored[0].read_bytes())
    assert body["properties"]["gma.evidentiary-truth"] == (
        "payload-and-receipt"
    )
    assert body["properties"]["gma.acquisition-id"] == (
        _acquisition_id(landing)
    )
    assert RecoveryScenario.CATALOGUE_DELETION in evidence.scenarios


@pytest.mark.unit
def test_parquet_deletion_regenerates_without_new_acquisition(
    tmp_path: Path,
) -> None:
    bronze = tmp_path / "bronze"
    landing = _seed_store(bronze)
    acquisition_id = _acquisition_id(landing)
    landing.parquet_path.unlink()

    evidence = reconstruct_bronze(bronze)

    table = pq.read_table(landing.parquet_path)
    assert table.column("acquisition_id")[0].as_py() == acquisition_id
    assert landing.payload_path.read_bytes() == PAYLOAD
    assert RecoveryScenario.PARQUET_DELETION in evidence.scenarios


@pytest.mark.unit
def test_interrupted_acquisition_fails_closed_then_resumes(
    tmp_path: Path,
) -> None:
    bronze = tmp_path / "bronze"
    receipt = _landable()
    content_id = receipt.payload.sha256
    staged = bronze / PAYLOAD_DIR / "by_content" / content_id / "payload.json"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(PAYLOAD)

    with pytest.raises(BronzeRecoveryError, match="incomplete"):
        reconstruct_bronze(bronze, fail_closed_on_incomplete=True)

    landing = resume_interrupted_acquisition(
        bronze,
        payload=PAYLOAD,
        receipt=receipt,
        media_hint="json",
    )
    evidence = reconstruct_bronze(bronze)

    assert landing.payload_path.read_bytes() == PAYLOAD
    assert landing.parquet_path.is_file()
    assert RecoveryScenario.INTERRUPTED_ACQUISITION in evidence.scenarios


@pytest.mark.unit
def test_recovery_restores_missing_acquisition_event(tmp_path: Path) -> None:
    bronze = tmp_path / "bronze"
    landing = _seed_store(bronze)
    event = landing.acquisition_receipt_path
    event.unlink()
    landing.parquet_path.unlink()

    reconstruct_bronze(bronze)

    assert event.is_file()
    assert landing.parquet_path.is_file()


@pytest.mark.unit
def test_recovery_keeps_quarantined_acquisition_unprojected(
    tmp_path: Path,
) -> None:
    bronze = tmp_path / "bronze"
    malformed = b"{not-json"
    receipt = _landable(malformed)
    content_id = receipt.payload.sha256
    payload_path = (
        bronze / PAYLOAD_DIR / "by_content" / content_id / "payload.json"
    )
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_bytes(malformed)
    temporal = require_temporal(receipt.temporal)
    receipt_path = (
        bronze
        / RECEIPT_DIR
        / receipt.source.source_id
        / f"{temporal.acquisition_id}.json"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes(receipt.canonical_json() + b"\n")

    evidence = reconstruct_bronze(bronze)

    assert evidence.landings == ()
    assert not (bronze / PARQUET_DIR).exists()


@pytest.mark.unit
def test_recovery_respects_superseding_rejection(tmp_path: Path) -> None:
    bronze = tmp_path / "bronze"
    landing = _seed_store(bronze)
    record_admission_decision(
        landing,
        state=BronzeAdmissionState.REJECTED_FROM_PROCESSING,
        actor="maintainer:review",
        reason_codes=("human_review_rejected",),
        decided_at=NOW + timedelta(minutes=1),
    )
    landing.parquet_path.unlink()

    evidence = reconstruct_bronze(bronze)

    assert evidence.landings == ()
    assert not landing.parquet_path.exists()


@pytest.mark.unit
def test_partial_storage_loss_rebuilds_analytical_layers(
    tmp_path: Path,
) -> None:
    bronze = tmp_path / "bronze"
    landing = _seed_store(bronze)
    reconstruct_bronze(bronze)
    landing.parquet_path.unlink()
    landing.lineage_path.unlink()
    for path in (bronze / CATALOGUE_DIR).rglob("*.json"):
        path.unlink()

    evidence = reconstruct_bronze(bronze)

    assert landing.parquet_path.is_file()
    assert landing.lineage_path.is_file()
    assert list((bronze / CATALOGUE_DIR).rglob("*.json"))
    assert RecoveryScenario.PARTIAL_STORAGE_LOSS in evidence.scenarios


@pytest.mark.unit
def test_duplicate_retrieval_keeps_one_payload_two_acquisitions(
    tmp_path: Path,
) -> None:
    bronze = tmp_path / "bronze"
    first = land_bronze_payload(
        PAYLOAD,
        _landable(PAYLOAD, retrieved_at=NOW),
        bronze_root=bronze,
        media_hint="json",
    )
    second = land_bronze_payload(
        PAYLOAD,
        _landable(
            PAYLOAD,
            retrieved_at=NOW + timedelta(minutes=5),
            original_uri="https://example.test/medsafe-retry",
        ),
        bronze_root=bronze,
        media_hint="json",
    )

    evidence = reconstruct_bronze(bronze)

    assert first.payload_path == second.payload_path
    assert _acquisition_id(first) != _acquisition_id(second)
    receipts = list((bronze / RECEIPT_DIR).rglob("*.json"))
    assert len(receipts) == 2
    assert first.payload_path.read_bytes() == PAYLOAD
    assert RecoveryScenario.DUPLICATE_RETRIEVAL in evidence.scenarios


@pytest.mark.unit
def test_code_rollback_preserves_newer_payload_and_receipt_bytes(
    tmp_path: Path,
) -> None:
    bronze = tmp_path / "bronze"
    landing = _seed_store(bronze, LATER_PAYLOAD)
    raw_receipt = landing.receipt_path.read_bytes()
    document = json.loads(raw_receipt)
    document["future_parser_generation"] = 2
    landing.receipt_path.write_bytes(
        json.dumps(document, sort_keys=True).encode() + b"\n"
    )
    newer_receipt = landing.receipt_path.read_bytes()
    landing.parquet_path.unlink()

    evidence = reconstruct_bronze(bronze, parser_generation=1)

    assert landing.payload_path.read_bytes() == LATER_PAYLOAD
    assert landing.receipt_path.read_bytes() == newer_receipt
    table = pq.read_table(landing.parquet_path)
    assert (
        table.column("payload_sha256")[0].as_py()
        == sha256(LATER_PAYLOAD).hexdigest()
    )
    assert RecoveryScenario.CODE_ROLLBACK_NEWER_PAYLOADS in evidence.scenarios


@pytest.mark.unit
def test_recovery_evidence_is_compact_and_machine_verifiable(
    tmp_path: Path,
) -> None:
    bronze = tmp_path / "bronze"
    _seed_store(bronze)
    evidence = reconstruct_bronze(bronze)
    path = write_recovery_evidence(evidence, tmp_path / "recovery.json")
    payload = json.loads(path.read_bytes())

    assert payload["schema_id"] == (
        "global-medicines-atlas.bronze-recovery-evidence"
    )
    assert payload["hugging_face_is_source_of_truth"] is False
    assert payload["evidentiary_inputs"] == ["payload", "receipt"]
    assert "evidence_digest" in payload
    assert len(payload["evidence_digest"]) == 64
    assert payload["landings"]
    assert len(path.read_bytes()) < 16_384


@pytest.mark.unit
def test_receipt_document_must_be_a_json_object() -> None:
    with pytest.raises(BronzeRecoveryError, match="JSON object"):
        load_receipt_for_reconstruction(b"[1]")


@pytest.mark.unit
def test_future_parser_rejects_unknown_receipt_fields() -> None:
    document = json.loads(_landable().model_dump_json())
    document["future_parser_generation"] = 2
    raw = json.dumps(document, sort_keys=True).encode()
    with pytest.raises(BronzeRecoveryError, match="exceed this parser"):
        load_receipt_for_reconstruction(raw, parser_generation=2)


@pytest.mark.unit
def test_empty_store_has_no_payload_tree(tmp_path: Path) -> None:
    bronze = tmp_path / "bronze"
    bronze.mkdir()
    evidence = reconstruct_bronze(bronze)
    assert evidence.landings == ()
    assert evidence.incomplete_count == 0


@pytest.mark.unit
def test_blank_journal_lines_are_ignored(tmp_path: Path) -> None:
    bronze = tmp_path / "bronze"
    _seed_store(bronze)
    journal = bronze / "recovery" / "journal.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text("\n\n", encoding="utf-8")
    evidence = reconstruct_bronze(bronze)
    assert evidence.landings


@pytest.mark.unit
def test_resume_rejects_mismatched_staged_payload(tmp_path: Path) -> None:
    bronze = tmp_path / "bronze"
    receipt = _landable()
    staged = (
        bronze
        / PAYLOAD_DIR
        / "by_content"
        / receipt.payload.sha256
        / "payload.json"
    )
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(b"not-the-payload")
    with pytest.raises(BronzeRecoveryError, match="staged payload"):
        resume_interrupted_acquisition(
            bronze,
            payload=PAYLOAD,
            receipt=receipt,
            media_hint="json",
        )


@pytest.mark.unit
def test_receipt_without_payload_is_incomplete_not_invented(
    tmp_path: Path,
) -> None:
    bronze = tmp_path / "bronze"
    landing = _seed_store(bronze)
    landing.payload_path.unlink()
    evidence = reconstruct_bronze(bronze)
    assert evidence.incomplete_count >= 1
    assert evidence.landings == ()
    with pytest.raises(BronzeRecoveryError, match="incomplete"):
        reconstruct_bronze(bronze, fail_closed_on_incomplete=True)


@pytest.mark.unit
def test_payload_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    bronze = tmp_path / "bronze"
    landing = _seed_store(bronze)
    landing.payload_path.write_bytes(b"tampered-bytes")
    with pytest.raises(BronzeRecoveryError, match="payload digest"):
        reconstruct_bronze(bronze)


@pytest.mark.unit
def test_rebuild_fails_closed_if_receipt_bytes_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bronze = tmp_path / "bronze"
    landing = _seed_store(bronze)
    original = Path.read_bytes
    reads = {"count": 0}

    def sometimes_mutated(self: Path) -> bytes:
        data = original(self)
        if self.resolve() == landing.receipt_path.resolve():
            reads["count"] += 1
            if reads["count"] >= 2:
                return data + b" "
        return data

    monkeypatch.setattr(Path, "read_bytes", sometimes_mutated)
    with pytest.raises(BronzeRecoveryError, match="immutable"):
        reconstruct_bronze(bronze)


@pytest.mark.property
@settings(deadline=None)
@given(st.binary(min_size=1, max_size=64))
def test_reconstructed_parquet_digest_tracks_payload(payload: bytes) -> None:
    with tempfile.TemporaryDirectory() as raw:
        bronze = Path(raw)
        admitted_payload = json.dumps({"value": payload.hex()}).encode()
        landing = land_bronze_payload(
            admitted_payload,
            _landable(admitted_payload),
            bronze_root=bronze,
            media_hint="json",
        )
        assert isinstance(landing, BronzeLanding)
        landing.parquet_path.unlink()
        reconstruct_bronze(bronze)
        table = pq.read_table(landing.parquet_path)
        assert (
            table.column("payload_sha256")[0].as_py()
            == sha256(admitted_payload).hexdigest()
        )
