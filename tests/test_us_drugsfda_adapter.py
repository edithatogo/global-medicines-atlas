"""Fixture-level contract tests for the public Drugs@FDA bulk adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from global_medicines_atlas.adapters.us_drugsfda import project_drugsfda_bulk
from global_medicines_atlas.ingestors import PayloadMember, PayloadSet
from global_medicines_atlas.models import AssertionKind, EvidenceStatus
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

APPLICATIONS = "ApplNo\tApplType\tSponsorName\n012345\tNDA\tExample Sponsor\n"
PRODUCTS = (
    "ApplNo\tProductNo\tForm\tStrength\tReferenceDrug\tDrugName\t"
    "ActiveIngredient\tReferenceStandard\n"
    "012345\t001\tTABLET;ORAL\t500MG\t1\tExample Drug\tEXAMPLINE\t1\n"
    "999999\t001\tTABLET;ORAL\t10MG\t0\tOrphan Row\tORPHANINE\t0\n"
)
MARKETING = "ApplNo\tProductNo\tMarketingStatusID\n012345\t001\t1\n"
STATUS_LOOKUP = (
    "MarketingStatusID\tMarketingStatusDescription\n1\tPrescription\n"
)


def payloads(*, live: bool = False) -> PayloadSet:
    values = {
        "applications.tsv": APPLICATIONS.encode(),
        "products.tsv": PRODUCTS.encode(),
        "marketing_status.tsv": MARKETING.encode(),
        "status_lookup.tsv": STATUS_LOOKUP.encode(),
    }
    members = []
    for name, payload in values.items():
        digest = sha256(payload).hexdigest()
        receipt = SourceReceipt(
            receipt_id=f"drugsfda-{name}",
            source=SourceIdentity(
                catalog_id="us-drugsfda",
                source_id="us-drugsfda",
                jurisdiction="USA",
                authority="US Food and Drug Administration",
                dataset_title="Drugs@FDA extracted table",
                catalog_version="1",
            ),
            retrieval=RetrievalEvidence(
                uri=f"https://example.test/{name}",
                retrieved_at=datetime(2026, 7, 29, tzinfo=UTC),
                acquisition_method=AcquisitionMethod.DOWNLOAD,
                status=AcquisitionStatus.SUCCEEDED,
            ),
            payload=PayloadEvidence.from_bytes(payload),
            rights_state=(
                RightsState.PERMITTED if live else RightsState.UNKNOWN
            ),
            rights_reference=(
                "https://rights.example/drugsfda" if live else None
            ),
            evidence_class=EvidenceClass.LIVE
            if live
            else EvidenceClass.FIXTURE,
            transformation=TransformationEvidence(
                transformation_id=f"extract:{name}",
                transformation_sha256="a" * 64,
                output_sha256=digest,
                output_byte_count=len(payload),
            ),
        )
        members.append(
            PayloadMember(name=name, payload=payload, receipt=receipt)
        )
    return PayloadSet(
        source_id="us-drugsfda",
        jurisdiction="USA",
        members=tuple(members),
    )


def test_drugsfda_bulk_fixture_is_not_confirmed() -> None:
    source_payloads = payloads()
    records = project_drugsfda_bulk(payloads=source_payloads)

    assert len(records) == 1
    record = records[0]
    assert record.concept.concept_id == "us-drugsfda:012345:001"
    assert record.concept.preferred_name == "Example Drug"
    assert record.assertions[0].kind == AssertionKind.REGULATORY
    assert record.assertions[0].status_code == "prescription"
    assert record.assertions[0].evidence_status is EvidenceStatus.UNKNOWN
    assert record.provenance[0].source_sha256 == source_payloads.lineage_digest


def test_drugsfda_bulk_confirms_only_when_every_receipt_is_live() -> None:
    records = project_drugsfda_bulk(payloads=payloads(live=True))

    assert records[0].assertions[0].evidence_status is EvidenceStatus.CONFIRMED


def test_drugsfda_bulk_is_unknown_when_one_receipt_is_not_live() -> None:
    source_payloads = payloads(live=True)
    first, *rest = source_payloads.members
    fixture_receipt = first.receipt.model_copy(
        update={
            "evidence_class": EvidenceClass.FIXTURE,
            "rights_state": RightsState.UNKNOWN,
            "rights_reference": None,
        }
    )
    mixed_payloads = source_payloads.model_copy(
        update={
            "members": (
                first.model_copy(update={"receipt": fixture_receipt}),
                *rest,
            )
        }
    )

    records = project_drugsfda_bulk(payloads=mixed_payloads)

    assert records[0].assertions[0].evidence_status is EvidenceStatus.UNKNOWN


def test_drugsfda_adapter_does_not_create_funding_assertions() -> None:
    records = project_drugsfda_bulk(payloads=payloads())

    assert all(
        assertion.kind != AssertionKind.FUNDING
        for record in records
        for assertion in record.assertions
    )
