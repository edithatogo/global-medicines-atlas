from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import AnyUrl

from global_medicines_atlas import mbs_source_silver_parity as parity
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


def _receipt(payload: bytes) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id="synthetic:mbs-source-silver",
        source=SourceIdentity(
            catalog_id="au-mbs",
            source_id="au-mbs",
            jurisdiction="AUS",
            authority="Synthetic",
            dataset_title="Synthetic MBS",
            catalog_version="2025-07-version-3",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("https://fixtures.invalid/mbs.xml"),
            retrieved_at=datetime(2026, 8, 30, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl("https://fixtures.invalid/rights"),
        evidence_class=EvidenceClass.LIVE,
        transformation=TransformationEvidence(
            transformation_id="fixture",
            transformation_sha256="a" * 64,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def _parquet(table: pa.Table) -> bytes:
    output = BytesIO()
    pq.write_table(table, output)  # pyright: ignore[reportUnknownMemberType]
    return output.getvalue()


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    source: bytes,
    silver: bytes,
    receipt: SourceReceipt,
) -> None:
    monkeypatch.setattr(parity, "SOURCE_OBJECT_BYTES", len(source))
    monkeypatch.setattr(
        parity,
        "SOURCE_OBJECT_SHA256",
        parity.hashlib.sha256(source).hexdigest(),
    )
    monkeypatch.setattr(parity, "SOURCE_RECEIPT_SHA256", receipt.digest())
    monkeypatch.setattr(parity, "SOURCE_URI", str(receipt.retrieval.uri))
    monkeypatch.setattr(parity, "SILVER_OBJECT_BYTES", len(silver))
    monkeypatch.setattr(
        parity,
        "SILVER_OBJECT_SHA256",
        parity.hashlib.sha256(silver).hexdigest(),
    )
    expected = pa.Table.from_batches(
        tuple(
            parity.iter_mbs_silver_batches(
                source, receipt, table="services", date_format="mbs-dmy"
            )
        )
    )
    monkeypatch.setattr(parity, "EXPECTED_ROWS", expected.num_rows)
    monkeypatch.setattr(parity, "EXPECTED_FIELDS", expected.num_columns)


def test_verifies_all_source_to_silver_values_and_emits_value_free_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = b"<MBS_XML><Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum></Data></MBS_XML>"
    receipt = _receipt(source)
    generated = pa.Table.from_batches(
        tuple(
            parity.iter_mbs_silver_batches(
                source, receipt, table="services", date_format="mbs-dmy"
            )
        )
    )
    silver = _parquet(generated)
    _configure(monkeypatch, source, silver, receipt)

    result = parity.verify_mbs_source_silver_parity(source, receipt, silver)

    assert result.source_to_silver_value_parity_verified is True
    assert result.row_count == 1
    assert result.source_values_in_receipt is False
    assert "00123" not in result.model_dump_json()


def test_rejects_same_schema_same_row_count_value_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = b"<MBS_XML><Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum></Data></MBS_XML>"
    receipt = _receipt(source)
    generated = pa.Table.from_batches(
        tuple(
            parity.iter_mbs_silver_batches(
                source, receipt, table="services", date_format="mbs-dmy"
            )
        )
    )
    mutated = generated.set_column(
        0,
        pa.field("source_record_id", pa.string(), nullable=False),
        pa.array(["mutated"]),
    )
    silver = _parquet(mutated)
    _configure(monkeypatch, source, silver, receipt)

    with pytest.raises(ValueError, match="row values differ"):
        parity.verify_mbs_source_silver_parity(source, receipt, silver)


def test_rejects_wrong_b1_receipt_even_when_payload_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = b"<MBS_XML><Data><ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum></Data></MBS_XML>"
    receipt = _receipt(source)
    generated = pa.Table.from_batches(
        tuple(
            parity.iter_mbs_silver_batches(
                source, receipt, table="services", date_format="mbs-dmy"
            )
        )
    )
    silver = _parquet(generated)
    _configure(monkeypatch, source, silver, receipt)
    wrong_receipt = receipt.model_copy(
        update={"rights_state": RightsState.UNKNOWN}
    )

    with pytest.raises(ValueError, match="B1 receipt"):
        parity.verify_mbs_source_silver_parity(source, wrong_receipt, silver)


def test_hosted_parity_receipt_is_durably_pinned_and_value_free() -> None:
    receipt_path = (
        Path(__file__).resolve().parents[1]
        / "quality/qualifications/mbs-source-silver-parity-2025-07-v3.json"
    )
    payload = receipt_path.read_bytes()
    receipt = parity.MbsSourceSilverParityReceipt.model_validate_json(payload)

    assert receipt.source_to_silver_value_parity_verified is True
    assert receipt.source_values_in_receipt is False
    assert receipt.row_count == 5_989
    assert receipt.field_count == 17
    assert receipt.source_object_sha256 == parity.SOURCE_OBJECT_SHA256
    assert receipt.silver_object_sha256 == parity.SILVER_OBJECT_SHA256
    assert "00123" not in receipt.model_dump_json()
    assert (
        hashlib.sha256(payload).hexdigest()
        == "009deabf772e91fedd7642f2b8f0e5a524abb76401620f8e93a8f3bd20189ded"
    )
