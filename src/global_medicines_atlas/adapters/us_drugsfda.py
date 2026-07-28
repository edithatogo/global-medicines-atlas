"""Drugs@FDA bulk-file projection into canonical regulatory assertions."""

from __future__ import annotations

import csv
from io import StringIO

from pydantic import ConfigDict, Field

from ..ingestors import PayloadSet
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


class DrugsFdaParityReport(FrozenModel):
    """Deterministic differences between bulk and API product projections."""

    matched_product_ids: tuple[str, ...] = ()
    bulk_only_product_ids: tuple[str, ...] = ()
    api_only_product_ids: tuple[str, ...] = ()
    status_mismatches: tuple[str, ...] = ()

    @property
    def is_equivalent(self) -> bool:
        """Whether the two surfaces agree for the compared fixture scope."""
        return not (
            self.bulk_only_product_ids
            or self.api_only_product_ids
            or self.status_mismatches
        )


class _ApiIngredient(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = ""


class _ApiProduct(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    product_number: str = ""
    brand_name: str = ""
    marketing_status: str = "unknown"
    active_ingredients: tuple[_ApiIngredient, ...] = ()


class _ApiApplication(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    application_number: str = ""
    application_type: str = ""
    products: tuple[_ApiProduct, ...] = ()


class _ApiEnvelope(FrozenModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    results: tuple[_ApiApplication, ...] = Field(default_factory=tuple)


def _rows(payload: str) -> tuple[dict[str, str], ...]:
    return tuple(
        dict(row) for row in csv.DictReader(StringIO(payload), delimiter="\t")
    )


def _bulk_evidence_status(payloads: PayloadSet) -> EvidenceStatus:
    return (
        EvidenceStatus.CONFIRMED
        if all(
            member.receipt.satisfies_live_gate for member in payloads.members
        )
        else EvidenceStatus.UNKNOWN
    )


def project_drugsfda_bulk(
    *,
    payloads: PayloadSet,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project the four public Drugs@FDA tables needed for product status."""
    if payloads.source_id != "us-drugsfda" or payloads.jurisdiction != "USA":
        raise ValueError("payload set must identify USA us-drugsfda data")
    members = {member.name: member for member in payloads.members}
    expected = {
        "applications.tsv",
        "products.tsv",
        "marketing_status.tsv",
        "status_lookup.tsv",
    }
    if members.keys() != expected:
        raise ValueError("payload set must contain the four Drugs@FDA tables")
    if any(
        member.receipt.retrieval.acquisition_method
        is not AcquisitionMethod.DOWNLOAD
        for member in members.values()
    ):
        raise ValueError("bulk table receipts must use download acquisition")
    applications_tsv = members["applications.tsv"].payload.decode("utf-8")
    products_tsv = members["products.tsv"].payload.decode("utf-8")
    marketing_status_tsv = members["marketing_status.tsv"].payload.decode(
        "utf-8"
    )
    status_lookup_tsv = members["status_lookup.tsv"].payload.decode("utf-8")
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
            "https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files"
        ),
        retrieved_at=max(
            member.receipt.retrieval.retrieved_at for member in members.values()
        ),
        source_sha256=payloads.lineage_digest,
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
                            identifier_type=applications[application_number][
                                "ApplType"
                            ],
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
                        evidence_status=_bulk_evidence_status(payloads),
                        provenance=provenance,
                    ),
                ),
                provenance=(provenance,),
            )
        )
    return tuple(sorted(records, key=lambda record: record.concept.concept_id))


def _api_results(payload: str | bytes) -> tuple[_ApiApplication, ...]:
    return _ApiEnvelope.model_validate_json(payload).results


def _require_receipt(
    receipt: SourceReceipt,
    method: AcquisitionMethod,
) -> None:
    if receipt.source.source_id != "us-drugsfda":
        raise ValueError("receipt must identify us-drugsfda")
    if receipt.source.jurisdiction != "USA":
        raise ValueError("receipt must identify the USA jurisdiction")
    if receipt.retrieval.acquisition_method is not method:
        raise ValueError(f"receipt must use {method.value} acquisition")
    if receipt.retrieval.status is not AcquisitionStatus.SUCCEEDED:
        raise ValueError("receipt must record a successful acquisition")


def project_drugsfda_api(
    payload: str | bytes,
    *,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project openFDA Drugs@FDA results into regulatory assertions."""
    _require_receipt(receipt, AcquisitionMethod.API)
    payload_bytes = (
        payload.encode("utf-8") if isinstance(payload, str) else payload
    )
    if not receipt.payload.matches(payload_bytes):
        raise ValueError("API payload does not match receipt")
    evidence_status = (
        EvidenceStatus.CONFIRMED
        if receipt.satisfies_live_gate
        else EvidenceStatus.UNKNOWN
    )
    provenance = Provenance(
        source_id="us-drugsfda",
        source_uri=str(receipt.retrieval.uri),
        retrieved_at=receipt.retrieval.retrieved_at,
        source_sha256=receipt.payload.sha256,
        transformation="drugsfda-api-v1",
    )
    records: list[CanonicalMedicineRecord] = []
    for application in _api_results(payload):
        application_number = application.application_number.strip()
        application_type = application.application_type.strip()
        if not application_number:
            continue
        for product in application.products:
            product_number = product.product_number.strip()
            ingredient_name = (
                product.active_ingredients[0].name
                if product.active_ingredients
                else ""
            )
            name = (product.brand_name or ingredient_name).strip()
            if not product_number or not name:
                continue
            concept_id = f"us-drugsfda:{application_number}:{product_number}"
            status = product.marketing_status
            records.append(
                CanonicalMedicineRecord(
                    concept=MedicineConcept(
                        concept_id=concept_id,
                        jurisdiction="USA",
                        level="product",
                        preferred_name=name,
                        identifiers=(
                            Identifier(
                                system=(
                                    "https://www.fda.gov/drugsatfda/application"
                                ),
                                value=application_number,
                                identifier_type=application_type or None,
                            ),
                        ),
                    ),
                    assertions=(
                        StatusAssertion(
                            assertion_id=(
                                f"drugsfda:{application_number}:{product_number}"
                            ),
                            concept_id=concept_id,
                            jurisdiction="USA",
                            kind=AssertionKind.REGULATORY,
                            authority="US Food and Drug Administration",
                            status_code=status.casefold().replace(" ", "-"),
                            evidence_status=evidence_status,
                            provenance=provenance,
                        ),
                    ),
                    provenance=(provenance,),
                )
            )
    return tuple(sorted(records, key=lambda record: record.concept.concept_id))


def compare_drugsfda_surfaces(
    bulk_records: tuple[CanonicalMedicineRecord, ...],
    api_records: tuple[CanonicalMedicineRecord, ...],
) -> DrugsFdaParityReport:
    """Compare product identity and regulatory status across FDA surfaces."""
    bulk = {
        record.concept.concept_id: record.assertions[0].status_code
        for record in bulk_records
    }
    api = {
        record.concept.concept_id: record.assertions[0].status_code
        for record in api_records
    }
    common = bulk.keys() & api.keys()
    return DrugsFdaParityReport(
        matched_product_ids=tuple(
            sorted(
                product_id
                for product_id in common
                if bulk[product_id] == api[product_id]
            )
        ),
        bulk_only_product_ids=tuple(sorted(bulk.keys() - api.keys())),
        api_only_product_ids=tuple(sorted(api.keys() - bulk.keys())),
        status_mismatches=tuple(
            sorted(
                product_id
                for product_id in common
                if bulk[product_id] != api[product_id]
            )
        ),
    )
