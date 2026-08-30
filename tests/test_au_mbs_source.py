"""Independent-domain contracts for Australian MBS source evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyUrl, ValidationError

from global_medicines_atlas.adapters import au_mbs
from global_medicines_atlas.adapters.au_mbs import (
    LEGACY_MBS_SHA256,
    MBS_NATIVE_FIELDS,
    MbsSourceBatch,
    parse_mbs_source_xml,
    qualify_legacy_mbs_xml,
)
from global_medicines_atlas.mbs_compatibility import select_p7_records
from global_medicines_atlas.models import CanonicalMedicineRecord
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
SHA = "a" * 64


def _receipt(payload: bytes, *, source_id: str = "au-mbs") -> SourceReceipt:
    payload_evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id="fixture:au-mbs",
        source=SourceIdentity(
            catalog_id=source_id,
            source_id=source_id,
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
        payload=payload_evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id="au-mbs-source-fixture",
            transformation_sha256=SHA,
            output_sha256=payload_evidence.sha256,
            output_byte_count=payload_evidence.byte_count,
        ),
    )


def test_p7_selection_preserves_native_records() -> None:
    payload = FIXTURE.read_bytes().replace(
        b"<Group>P7</Group>", b"<Group>P1</Group>", 1
    )
    batch = parse_mbs_source_xml(payload, _receipt(payload))
    assert select_p7_records(batch) == (batch.records[1],)
    assert select_p7_records(batch)[0].value("Benefit75") == "31.90"


def test_mbs_native_denominator_contains_all_40_observed_fields() -> None:
    assert len(MBS_NATIVE_FIELDS) == 40
    assert len(set(MBS_NATIVE_FIELDS)) == 40
    assert {"ItemNum", "ScheduleFee", "Benefit100", "Description"}.issubset(
        MBS_NATIVE_FIELDS
    )


def test_source_parser_preserves_native_order_nulls_and_identity() -> None:
    payload = FIXTURE.read_bytes()

    batch = parse_mbs_source_xml(payload, _receipt(payload))

    assert isinstance(batch, MbsSourceBatch)
    assert not isinstance(batch, CanonicalMedicineRecord)
    assert batch.source_id == "au-mbs"
    assert batch.record_count == 2
    assert batch.observed_fields == (
        "Benefit75",
        "Description",
        "Group",
        "ItemNum",
        "ItemStartDate",
        "ScheduleFee",
        "SubItemNum",
    )
    first, second = batch.records
    assert first.source_record_id == "au-mbs:123:00:2025-07-01:0"
    assert [field.name for field in first.fields] == [
        "ItemNum",
        "SubItemNum",
        "ItemStartDate",
        "Group",
        "ScheduleFee",
        "Description",
    ]
    assert second.value("SubItemNum") is None
    assert second.value("Benefit75") == "31.90"
    assert batch.provenance.source_sha256 == _receipt(payload).payload.sha256


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"<MBSItems><MBSItem /></MBSItems>", "MBS_XML"),
        (b"<MBS_XML />", "Data"),
        (
            b"<MBS_XML><Data><ItemNum>1</ItemNum><Unknown>x</Unknown></Data></MBS_XML>",
            "unknown native field",
        ),
        (
            b"<MBS_XML><Data><ItemNum>1</ItemNum><ItemNum>2</ItemNum></Data></MBS_XML>",
            "duplicate native field",
        ),
    ],
)
def test_source_parser_fails_closed_on_shape_drift(
    payload: bytes,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_mbs_source_xml(payload, _receipt(payload))


def test_source_parser_requires_receipt_bound_to_mbs_bytes() -> None:
    payload = FIXTURE.read_bytes()
    with pytest.raises(ValueError, match="source_id"):
        parse_mbs_source_xml(payload, _receipt(payload, source_id="au-pbs"))


def test_exact_legacy_qualification_rejects_fixture_bytes() -> None:
    payload = FIXTURE.read_bytes()
    assert _receipt(payload).payload.sha256 != LEGACY_MBS_SHA256
    with pytest.raises(ValueError, match="exact July 2025 MBS payload"):
        qualify_legacy_mbs_xml(payload, _receipt(payload))


def test_mbs_batch_source_identity_cannot_be_overridden() -> None:
    payload = FIXTURE.read_bytes()
    batch = parse_mbs_source_xml(payload, _receipt(payload))

    with pytest.raises(ValidationError):
        MbsSourceBatch.model_validate({
            **batch.model_dump(),
            "source_id": "au-pbs",
        })


def test_exact_legacy_qualification_accepts_the_complete_denominator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fields = "".join(
        f"<{name}>{'1' if name == 'ItemNum' else ''}</{name}>"
        for name in MBS_NATIVE_FIELDS
    )
    payload = f"<MBS_XML><Data>{fields}</Data></MBS_XML>".encode()
    receipt = _receipt(payload)
    monkeypatch.setattr(au_mbs, "LEGACY_MBS_BYTES", len(payload))
    monkeypatch.setattr(au_mbs, "LEGACY_MBS_SHA256", receipt.payload.sha256)
    monkeypatch.setattr(au_mbs, "LEGACY_MBS_RECORDS", 1)
    monkeypatch.setattr(au_mbs, "LEGACY_FIELD_COUNT_DISTRIBUTION", {40: 1})

    batch = qualify_legacy_mbs_xml(payload, receipt)

    assert batch.record_count == 1
    assert batch.observed_fields == MBS_NATIVE_FIELDS


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            b"<MBS_XML><Data><ItemNum><Nested /></ItemNum></Data></MBS_XML>",
            "must not be nested",
        ),
        (
            b"<MBS_XML><Data><Description>x</Description></Data></MBS_XML>",
            "missing required identity",
        ),
        (
            b"<MBS_XML><Data><ItemNum>1</ItemNum></Data><Meta /></MBS_XML>",
            "unexpected non-Data",
        ),
    ],
)
def test_source_parser_rejects_nested_missing_identity_and_root_metadata(
    payload: bytes,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_mbs_source_xml(payload, _receipt(payload))
