"""Medsafe medicine registry CSV regulatory adapter."""

from __future__ import annotations

import csv
from io import StringIO

from ..models import (
    AssertionKind,
    CanonicalMedicineRecord,
    EvidenceStatus,
    Identifier,
    MedicineConcept,
    StatusAssertion,
)
from ..receipts import SourceReceipt
from ._receipt import provenance_from_receipt

SOURCE_ID = "nz-medsafe"


def project_medsafe_registry_csv(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project registered products from a minimal Medsafe registry export."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=SOURCE_ID,
        jurisdiction="NZL",
        transformation="nz-medsafe-registry-csv-v1",
    )
    rows = csv.DictReader(StringIO(payload.decode("utf-8-sig")))
    records: list[CanonicalMedicineRecord] = []
    for row in rows:
        application = _required(row, "application_number")
        product = _required(row, "product_name")
        status = _required(row, "registration_status")
        concept_id = f"nz-medsafe:{application}"
        records.append(
            CanonicalMedicineRecord(
                concept=MedicineConcept(
                    concept_id=concept_id,
                    jurisdiction="NZL",
                    level="product",
                    preferred_name=product,
                    identifiers=(
                        Identifier(
                            system="https://www.medsafe.govt.nz/regulatory/",
                            value=application,
                            identifier_type="application-number",
                        ),
                    ),
                ),
                assertions=(
                    StatusAssertion(
                        assertion_id=f"{concept_id}:regulatory",
                        concept_id=concept_id,
                        jurisdiction="NZL",
                        kind=AssertionKind.REGULATORY,
                        authority="Medsafe",
                        status_code=_status_code(status),
                        evidence_status=(
                            EvidenceStatus.CONFIRMED
                            if receipt.satisfies_live_gate
                            else EvidenceStatus.UNKNOWN
                        ),
                        provenance=provenance,
                    ),
                ),
                provenance=(provenance,),
            )
        )
    return tuple(sorted(records, key=lambda record: record.concept.concept_id))


def _required(row: dict[str, str | None], field: str) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise ValueError(f"Missing required Medsafe registry field: {field}")
    return value


def _status_code(value: str) -> str:
    return "-".join(value.casefold().split())
