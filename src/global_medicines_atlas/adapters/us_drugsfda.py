"""Drugs@FDA bulk-file projection into canonical regulatory assertions."""

from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO

from ..models import (
    AssertionKind,
    CanonicalMedicineRecord,
    EvidenceStatus,
    Identifier,
    MedicineConcept,
    Provenance,
    StatusAssertion,
)


def _rows(payload: str) -> tuple[dict[str, str], ...]:
    return tuple(dict(row) for row in csv.DictReader(StringIO(payload), delimiter="\t"))


def project_drugsfda_bulk(
    *,
    applications_tsv: str,
    products_tsv: str,
    marketing_status_tsv: str,
    status_lookup_tsv: str,
    source_sha256: str,
    retrieved_at: datetime,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project the four public Drugs@FDA tables needed for product status."""

    applications = {row["ApplNo"]: row for row in _rows(applications_tsv)}
    statuses = {
        row["MarketingStatusID"]: row["MarketingStatusDescription"]
        for row in _rows(status_lookup_tsv)
    }
    product_status = {
        (row["ApplNo"], row["ProductNo"]): statuses[row["MarketingStatusID"]]
        for row in _rows(marketing_status_tsv)
        if row["MarketingStatusID"] in statuses
    }
    provenance = Provenance(
        source_id="us-drugsfda",
        source_uri=(
            "https://www.fda.gov/drugs/drug-approvals-and-databases/"
            "drugsfda-data-files"
        ),
        retrieved_at=retrieved_at,
        source_sha256=source_sha256,
        transformation="drugsfda-bulk-v1",
    )
    records: list[CanonicalMedicineRecord] = []
    for product in _rows(products_tsv):
        application_number = product["ApplNo"]
        product_number = product["ProductNo"]
        if application_number not in applications:
            continue
        concept_id = f"us-drugsfda:{application_number}:{product_number}"
        status = product_status.get(
            (application_number, product_number),
            "unknown",
        )
        records.append(
            CanonicalMedicineRecord(
                concept=MedicineConcept(
                    concept_id=concept_id,
                    jurisdiction="USA",
                    level="product",
                    preferred_name=product["DrugName"],
                    identifiers=(
                        Identifier(
                            system="https://www.fda.gov/drugsatfda/application",
                            value=application_number,
                            identifier_type=applications[application_number]["ApplType"],
                        ),
                    ),
                ),
                assertions=(
                    StatusAssertion(
                        assertion_id=f"drugsfda:{application_number}:{product_number}",
                        concept_id=concept_id,
                        jurisdiction="USA",
                        kind=AssertionKind.REGULATORY,
                        authority="US Food and Drug Administration",
                        status_code=status.casefold().replace(" ", "-"),
                        evidence_status=EvidenceStatus.CONFIRMED,
                        provenance=provenance,
                    ),
                ),
                provenance=(provenance,),
            )
        )
    return tuple(sorted(records, key=lambda record: record.concept.concept_id))
