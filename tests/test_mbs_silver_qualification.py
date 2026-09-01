"""Aggregate qualification for receipt-bound MBS Silver candidates."""

from datetime import UTC, datetime

import pytest
from pydantic import AnyUrl, ValidationError

from global_medicines_atlas.mbs_silver_qualification import (
    MbsSilverQualification,
    qualify_mbs_silver,
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


def _xml() -> bytes:
    return b"""<MBS_XML><Data>
      <ItemNum>00123</ItemNum><SubItemNum>00</SubItemNum>
      <ItemStartDate>30.08.2026</ItemStartDate>
      <ScheduleFee>42.500</ScheduleFee><Benefit75></Benefit75>
      <Description>Example service</Description>
    </Data><Data>
      <ItemNum>00456</ItemNum><SubItemNum>00</SubItemNum>
      <ItemStartDate>not-a-date</ItemStartDate>
      <ScheduleFee>0.1234567891</ScheduleFee>
    </Data></MBS_XML>"""


def _receipt(payload: bytes) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id="synthetic:mbs-silver-qualification",
        source=SourceIdentity(
            catalog_id="au-mbs",
            source_id="au-mbs",
            jurisdiction="AUS",
            authority="Synthetic",
            dataset_title="Synthetic MBS",
            catalog_version="synthetic-ddmmyyyy-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("https://fixtures.invalid/mbs"),
            retrieved_at=datetime(2026, 9, 1, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id="synthetic",
            transformation_sha256="a" * 64,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def test_qualification_accounts_for_all_tables_fields_and_source_rows() -> None:
    payload = _xml()
    report = qualify_mbs_silver(
        payload, _receipt(payload), date_format="mbs-dmy", rows_per_batch=1
    )

    assert report.source_record_count == 2
    assert report.field_count == 40
    assert report.field_occurrence_count == 80
    assert [table.table for table in report.tables] == [
        "services",
        "hierarchy",
        "descriptions",
        "fees",
        "benefits",
        "caps",
    ]
    assert all(table.row_count == 2 for table in report.tables)
    assert sum(table.field_count for table in report.tables) == 40
    assert report.quality_counts["unrepresentable"] == 1
    assert report.quality_counts["invalid"] == 1
    assert report.quality_counts["null"] == 1
    assert report.promotion_status == "candidate_only"
    assert report.blockers == (
        "public_v4_identity_unverified",
        "real_source_era_unqualified",
        "quality_findings_present",
    )


def test_qualification_is_deterministic_and_binds_receipt_and_payload() -> None:
    payload = _xml()
    receipt = _receipt(payload)
    first = qualify_mbs_silver(payload, receipt, date_format="mbs-dmy")
    second = qualify_mbs_silver(payload, receipt, date_format="mbs-dmy")

    assert first == second
    assert first.source_sha256 == receipt.payload.sha256
    assert first.receipt_sha256 == receipt.digest()
    assert len(first.qualification_sha256) == 64
    assert (
        MbsSilverQualification.model_validate_json(first.model_dump_json())
        == first
    )

    with pytest.raises(ValueError, match="payload"):
        qualify_mbs_silver(payload + b" ", receipt, date_format="mbs-dmy")


def test_serialized_qualification_rejects_promotion_or_denominator_drift() -> (
    None
):
    payload = _xml()
    values = qualify_mbs_silver(
        payload, _receipt(payload), date_format="mbs-dmy"
    ).model_dump()
    values["promotion_status"] = "promoted"
    with pytest.raises(ValidationError):
        MbsSilverQualification.model_validate(values)

    values = qualify_mbs_silver(
        payload, _receipt(payload), date_format="mbs-dmy"
    ).model_dump()
    values["source_record_count"] = 3
    with pytest.raises(ValidationError, match="row denominator"):
        MbsSilverQualification.model_validate(values)
