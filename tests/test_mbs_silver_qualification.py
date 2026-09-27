"""Aggregate qualification for receipt-bound MBS Silver candidates."""

from datetime import UTC, date, datetime

import pytest
from pydantic import AnyUrl, ValidationError

from global_medicines_atlas.mbs_silver_qualification import (
    OFFICIAL_MBS_V3_URI,
    MbsSilverQualification,
    MbsSourceEraVerification,
    qualify_mbs_silver,
    report_digest,
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
      <ScheduleFee>9999999999999999999999999999999.990000000</ScheduleFee>
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
    assert report.quality_counts["invalid"] == 2
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


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("tables", "table denominator"),
        ("fields", "field denominator"),
        ("quality", "quality outcomes"),
        ("quality_count", "quality outcome denominator"),
        ("quality_unknown", "quality outcome denominator"),
        ("blockers", "candidate blockers"),
        ("digest", "qualification digest"),
    ],
)
def test_serialized_qualification_rejects_all_evidence_drift(
    change: str, message: str
) -> None:
    payload = _xml()
    report = qualify_mbs_silver(
        payload, _receipt(payload), date_format="mbs-dmy"
    )
    values = report.model_dump()
    if change == "tables":
        values["tables"] = tuple(reversed(values["tables"]))
    elif change == "fields":
        first = dict(values["tables"][0])
        second = dict(values["tables"][1])
        first["field_count"] += 1
        first["field_occurrence_count"] += first["row_count"]
        second["field_count"] -= 1
        second["field_occurrence_count"] -= second["row_count"]
        values["tables"] = (first, second, *values["tables"][2:])
    elif change == "quality":
        values["quality"] = tuple(reversed(values["quality"]))
    elif change == "quality_count":
        values["quality"] = values["quality"][:-1]
        values["blockers"] = values["blockers"][:-1]
    elif change == "quality_unknown":
        values["quality"][0]["status"] = "invented"
    elif change == "blockers":
        values["blockers"] = values["blockers"][:-1]
    else:
        values["qualification_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match=message):
        MbsSilverQualification.model_validate(values)


def test_clean_candidate_retains_only_external_identity_blockers() -> None:
    payload = b"""<MBS_XML><Data><ItemNum>00123</ItemNum>
      <SubItemNum>00</SubItemNum></Data></MBS_XML>"""
    report = qualify_mbs_silver(payload, _receipt(payload))
    assert report.blockers == (
        "public_v4_identity_unverified",
        "real_source_era_unqualified",
    )


def test_source_era_verification_is_bound_to_archive_identity() -> None:
    payload = b"<MBS_XML><Data><ItemNum>00123</ItemNum></Data></MBS_XML>"
    receipt = _receipt(payload)
    verification = MbsSourceEraVerification(
        official_source_uri=AnyUrl(OFFICIAL_MBS_V3_URI),
        release_id="MBS-XML-20250701 Version 3",
        released_at=date(2025, 6, 16),
        effective_at=date(2025, 7, 1),
        official_source_sha256=receipt.payload.sha256,
        official_source_byte_count=receipt.payload.byte_count,
        compared_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    report = qualify_mbs_silver(payload, receipt)
    provisional = MbsSilverQualification.model_construct(
        source_sha256=report.source_sha256,
        source_byte_count=report.source_byte_count,
        receipt_sha256=report.receipt_sha256,
        schema_era="2025-07-version-3",
        source_era_verification=verification,
        date_format=report.date_format,
        source_record_count=report.source_record_count,
        tables=report.tables,
        quality=report.quality,
        blockers=("public_v4_identity_unverified",),
        qualification_sha256="0" * 64,
    )
    values = provisional.model_dump()
    values["qualification_sha256"] = report_digest(provisional)
    validated = MbsSilverQualification.model_validate(values)
    assert validated.blockers == ("public_v4_identity_unverified",)
    assert (
        MbsSilverQualification.model_validate_json(validated.model_dump_json())
        == validated
    )

    with pytest.raises(ValidationError, match="differs from B2 identity"):
        MbsSilverQualification.model_validate(
            values | {"source_byte_count": len(payload) + 1}
        )

    with pytest.raises(ValidationError, match="catalog era"):
        MbsSilverQualification.model_validate(values | {"schema_era": "other"})


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"official_source_uri": AnyUrl("https://example.org/mbs.xml")}, "URI"),
        ({"release_id": "unrelated release"}, "metadata"),
    ],
)
def test_source_era_verification_rejects_unrelated_official_identity(
    change: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        MbsSourceEraVerification.model_validate(
            {
                "official_source_uri": AnyUrl(OFFICIAL_MBS_V3_URI),
                "release_id": "MBS-XML-20250701 Version 3",
                "released_at": date(2025, 6, 16),
                "effective_at": date(2025, 7, 1),
                "official_source_sha256": "a" * 64,
                "official_source_byte_count": 1,
                "compared_at": datetime(2026, 9, 1, tzinfo=UTC),
            }
            | change
        )
