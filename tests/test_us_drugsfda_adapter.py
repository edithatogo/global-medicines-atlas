"""Fixture-level contract tests for the public Drugs@FDA bulk adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from pydantic import AnyUrl

from global_medicines_atlas.adapters.us_drugsfda import (
    compare_drugsfda_surfaces,
    project_drugsfda_api,
    project_drugsfda_bulk,
)
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
    members: list[PayloadMember] = []
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
                uri=AnyUrl(f"https://example.test/{name}"),
                retrieved_at=datetime(2026, 7, 29, tzinfo=UTC),
                acquisition_method=AcquisitionMethod.DOWNLOAD,
                status=AcquisitionStatus.SUCCEEDED,
            ),
            payload=PayloadEvidence.from_bytes(payload),
            rights_state=(
                RightsState.PERMITTED if live else RightsState.UNKNOWN
            ),
            rights_reference=(
                AnyUrl("https://rights.example/drugsfda") if live else None
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
    assert record.concept.jurisdiction == "USA"
    assert record.concept.level == "product"
    assert record.concept.preferred_name == "Example Drug"
    assert tuple(
        (identifier.system, identifier.value, identifier.identifier_type)
        for identifier in record.concept.identifiers
    ) == (
        (
            "https://www.fda.gov/drugsatfda/application",
            "012345",
            "NDA",
        ),
    )
    assertion = record.assertions[0]
    assert assertion.assertion_id == "drugsfda:012345:001"
    assert assertion.concept_id == record.concept.concept_id
    assert assertion.jurisdiction == "USA"
    assert assertion.kind == AssertionKind.REGULATORY
    assert assertion.authority == "US Food and Drug Administration"
    assert assertion.status_code == "prescription"
    assert assertion.evidence_status is EvidenceStatus.UNKNOWN
    provenance = record.provenance[0]
    assert assertion.provenance == provenance
    assert provenance.source_id == "us-drugsfda"
    assert provenance.source_uri == (
        "https://www.fda.gov/drugs/"
        "drug-approvals-and-databases/drugsfda-data-files"
    )
    assert provenance.retrieved_at == datetime(2026, 7, 29, tzinfo=UTC)
    assert provenance.source_sha256 == source_payloads.lineage_digest
    assert provenance.transformation == "drugsfda-bulk-v1"


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


def api_receipt(payload: str) -> SourceReceipt:
    payload_bytes = payload.encode()
    return SourceReceipt(
        receipt_id="drugsfda-api",
        source=SourceIdentity(
            catalog_id="us-drugsfda",
            source_id="us-drugsfda",
            jurisdiction="USA",
            authority="US Food and Drug Administration",
            dataset_title="openFDA Drugs@FDA",
            catalog_version="1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("https://api.fda.gov/drug/drugsfda.json"),
            retrieved_at=datetime(2026, 7, 30, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.API,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=PayloadEvidence.from_bytes(payload_bytes),
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.FIXTURE,
        transformation=TransformationEvidence(
            transformation_id="drugsfda-api-fixture-v1",
            transformation_sha256="a" * 64,
            output_sha256=sha256(payload_bytes).hexdigest(),
            output_byte_count=len(payload_bytes),
        ),
    )


def test_drugsfda_api_projects_exact_identity_status_and_metadata() -> None:
    payload = """
    {
      "results": [{
        "application_number": " 012345 ",
        "application_type": " NDA ",
        "products": [
          {
            "product_number": " 002 ",
            "brand_name": "",
            "marketing_status": "Discontinued Drug Product",
            "active_ingredients": [{"name": " EXAMPLINE "}]
          },
          {"product_number": "", "brand_name": "Skipped"}
        ]
      }, {
        "application_number": "",
        "products": [{"product_number": "001", "brand_name": "Skipped"}]
      }]
    }
    """
    source_receipt = api_receipt(payload)

    records = project_drugsfda_api(payload, receipt=source_receipt)

    assert len(records) == 1
    record = records[0]
    assert record.concept.concept_id == "us-drugsfda:012345:002"
    assert record.concept.preferred_name == "EXAMPLINE"
    assert tuple(
        (item.system, item.value, item.identifier_type)
        for item in record.concept.identifiers
    ) == (
        (
            "https://www.fda.gov/drugsatfda/application",
            "012345",
            "NDA",
        ),
    )
    assertion = record.assertions[0]
    assert assertion.assertion_id == "drugsfda:012345:002"
    assert assertion.concept_id == record.concept.concept_id
    assert assertion.status_code == "discontinued-drug-product"
    assert assertion.kind is AssertionKind.REGULATORY
    assert assertion.evidence_status is EvidenceStatus.UNKNOWN
    provenance = record.provenance[0]
    assert assertion.provenance == provenance
    assert provenance.source_id == "us-drugsfda"
    assert provenance.source_uri == str(source_receipt.retrieval.uri)
    assert provenance.retrieved_at == source_receipt.retrieval.retrieved_at
    assert provenance.source_sha256 == source_receipt.payload.sha256
    assert provenance.transformation == "drugsfda-api-v1"


def test_drugsfda_surface_comparison_partitions_every_difference() -> None:
    bulk = project_drugsfda_bulk(payloads=payloads())
    matched = bulk[0]
    mismatch = matched.model_copy(
        update={
            "concept": matched.concept.model_copy(
                update={"concept_id": "us-drugsfda:222222:001"}
            ),
            "assertions": (
                matched.assertions[0].model_copy(
                    update={
                        "assertion_id": "drugsfda:222222:001",
                        "concept_id": "us-drugsfda:222222:001",
                        "status_code": "approved",
                    }
                ),
            ),
        }
    )
    api_mismatch = mismatch.model_copy(
        update={
            "assertions": (
                mismatch.assertions[0].model_copy(
                    update={"status_code": "discontinued"}
                ),
            )
        }
    )
    api_only = matched.model_copy(
        update={
            "concept": matched.concept.model_copy(
                update={"concept_id": "us-drugsfda:333333:001"}
            ),
            "assertions": (
                matched.assertions[0].model_copy(
                    update={
                        "assertion_id": "drugsfda:333333:001",
                        "concept_id": "us-drugsfda:333333:001",
                    }
                ),
            ),
        }
    )

    report = compare_drugsfda_surfaces(
        (mismatch, matched),
        (api_only, matched, api_mismatch),
    )

    assert report.matched_product_ids == ("us-drugsfda:012345:001",)
    assert report.bulk_only_product_ids == ()
    assert report.api_only_product_ids == ("us-drugsfda:333333:001",)
    assert report.status_mismatches == ("us-drugsfda:222222:001",)
    assert report.is_equivalent is False
    assert compare_drugsfda_surfaces(bulk, bulk).is_equivalent is True
