"""Fixture-level contract tests for the public Drugs@FDA bulk adapter."""

from __future__ import annotations

from datetime import UTC, datetime

from global_medicines_atlas.adapters.us_drugsfda import project_drugsfda_bulk
from global_medicines_atlas.models import AssertionKind

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


def test_drugsfda_bulk_projects_confirmed_regulatory_status() -> None:
    records = project_drugsfda_bulk(
        applications_tsv=APPLICATIONS,
        products_tsv=PRODUCTS,
        marketing_status_tsv=MARKETING,
        status_lookup_tsv=STATUS_LOOKUP,
        source_sha256="a" * 64,
        retrieved_at=datetime(2026, 7, 29, tzinfo=UTC),
    )

    assert len(records) == 1
    record = records[0]
    assert record.concept.concept_id == "us-drugsfda:012345:001"
    assert record.concept.preferred_name == "Example Drug"
    assert record.assertions[0].kind == AssertionKind.REGULATORY
    assert record.assertions[0].status_code == "prescription"
    assert record.provenance[0].source_sha256 == "a" * 64


def test_drugsfda_adapter_does_not_create_funding_assertions() -> None:
    records = project_drugsfda_bulk(
        applications_tsv=APPLICATIONS,
        products_tsv=PRODUCTS,
        marketing_status_tsv=MARKETING,
        status_lookup_tsv=STATUS_LOOKUP,
        source_sha256="b" * 64,
        retrieved_at=datetime(2026, 7, 29, tzinfo=UTC),
    )

    assert all(
        assertion.kind != AssertionKind.FUNDING
        for record in records
        for assertion in record.assertions
    )
