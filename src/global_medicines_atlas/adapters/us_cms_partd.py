"""Plan-level CMS Part D formulary and pricing projection."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Literal

from pydantic import Field

from ..models import (
    AssertionKind,
    CanonicalMedicineRecord,
    EvidenceStatus,
    FrozenModel,
    Identifier,
    MedicineConcept,
    Provenance,
    StatusAssertion,
)
from ..receipts import AcquisitionMethod, AcquisitionStatus, SourceReceipt


class UsMedicinesFundingContext(FrozenModel):
    """Structural boundary for United States medicines coverage evidence."""

    national_medicines_funding_list_exists: Literal[False] = False
    coverage_unit: Literal["payer-plan"] = "payer-plan"
    explanation: str = Field(
        default=(
            "The United States has no single national medicines funding list; "
            "CMS Part D evidence is plan-specific and does not establish "
            "coverage by other public or private payers."
        ),
        min_length=1,
    )


class CmsPartDProjection(FrozenModel):
    """Plan-specific records plus the national-system interpretation boundary."""

    funding_context: UsMedicinesFundingContext = Field(
        default_factory=UsMedicinesFundingContext
    )
    records: tuple[CanonicalMedicineRecord, ...]


def _truthy(value: str) -> bool:
    return value.strip().casefold() in {"1", "true", "yes", "y"}


def project_cms_partd_csv(
    payload: str,
    *,
    receipt: SourceReceipt,
) -> CmsPartDProjection:
    """Project CMS fixture rows without promoting them to national coverage."""
    if receipt.source.source_id != "us-cms-partd-formulary":
        raise ValueError("receipt must identify us-cms-partd-formulary")
    if receipt.source.jurisdiction != "USA":
        raise ValueError("receipt must identify the USA jurisdiction")
    if receipt.retrieval.acquisition_method not in {
        AcquisitionMethod.API,
        AcquisitionMethod.DOWNLOAD,
    }:
        raise ValueError("CMS receipt must use API or download acquisition")
    if receipt.retrieval.status is not AcquisitionStatus.SUCCEEDED:
        raise ValueError("CMS receipt must record a successful acquisition")
    payload_bytes = payload.encode("utf-8")
    if not receipt.payload.matches(payload_bytes):
        raise ValueError("CMS payload does not match receipt")
    evidence_status = (
        EvidenceStatus.CONFIRMED
        if receipt.satisfies_live_gate
        else EvidenceStatus.UNKNOWN
    )
    provenance = Provenance(
        source_id="us-cms-partd-formulary",
        source_uri=str(receipt.retrieval.uri),
        retrieved_at=receipt.retrieval.retrieved_at,
        source_sha256=receipt.payload.sha256,
        source_version=receipt.source.catalog_version,
        transformation="cms-partd-plan-formulary-v1",
    )
    records: list[CanonicalMedicineRecord] = []
    for row in csv.DictReader(StringIO(payload)):
        contract_id = row["contract_id"].strip()
        plan_id = row["plan_id"].strip()
        ndc = row["ndc"].strip()
        drug_name = row["drug_name"].strip()
        if not all((contract_id, plan_id, ndc, drug_name)):
            continue
        plan_key = f"{contract_id}:{plan_id}"
        concept_id = f"us-cms-partd:{plan_key}:{ndc}"
        restrictions = (
            f"plan={plan_key}",
            f"tier={row['tier'].strip()}",
            f"retail_price_usd={row['retail_price_usd'].strip()}",
            f"prior_authorization={_truthy(row['prior_authorization'])}",
            f"step_therapy={_truthy(row['step_therapy'])}",
            "scope=medicare-part-d-plan-not-national",
        )
        records.append(
            CanonicalMedicineRecord(
                concept=MedicineConcept(
                    concept_id=concept_id,
                    jurisdiction="USA",
                    level="payer-plan-product",
                    preferred_name=drug_name,
                    identifiers=(
                        Identifier(
                            system="https://www.cms.gov/medicare/part-d/plan",
                            value=plan_key,
                            identifier_type="contract-plan",
                        ),
                        Identifier(
                            system="http://hl7.org/fhir/sid/ndc",
                            value=ndc,
                            identifier_type="ndc",
                        ),
                    ),
                ),
                assertions=(
                    StatusAssertion(
                        assertion_id=f"cms-partd:{plan_key}:{ndc}",
                        concept_id=concept_id,
                        jurisdiction="USA",
                        kind=AssertionKind.FORMULARY,
                        authority="Centers for Medicare & Medicaid Services",
                        status_code=row["formulary_status"]
                        .strip()
                        .casefold()
                        .replace(" ", "-"),
                        evidence_status=evidence_status,
                        restrictions=restrictions,
                        provenance=provenance,
                    ),
                ),
                provenance=(provenance,),
            )
        )
    projected_records: tuple[CanonicalMedicineRecord, ...] = tuple(
        sorted(records, key=lambda record: record.concept.concept_id)
    )
    return CmsPartDProjection(records=projected_records)
