"""Australian Register of Therapeutic Goods regulatory adapter."""

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

SOURCE_ID = "au-artg"


def project_artg_csv(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project medicine entries from a minimal ARTG CSV export."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=SOURCE_ID,
        jurisdiction="AUS",
        transformation="au-artg-csv-v1",
    )
    rows = csv.DictReader(StringIO(payload.decode("utf-8-sig")))
    records: list[CanonicalMedicineRecord] = []
    for row in rows:
        artg_id = _required(row, "artg_id")
        name = _required(row, "product_name")
        status = _required(row, "entry_status")
        concept_id = f"au-artg:{artg_id}"
        records.append(
            CanonicalMedicineRecord(
                concept=MedicineConcept(
                    concept_id=concept_id,
                    jurisdiction="AUS",
                    level="product",
                    preferred_name=name,
                    identifiers=(
                        Identifier(
                            system="https://www.tga.gov.au/resources/artg/",
                            value=artg_id,
                            identifier_type="artg-id",
                        ),
                    ),
                ),
                assertions=(
                    StatusAssertion(
                        assertion_id=f"{concept_id}:regulatory",
                        concept_id=concept_id,
                        jurisdiction="AUS",
                        kind=AssertionKind.REGULATORY,
                        authority="Therapeutic Goods Administration",
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
        raise ValueError(f"Missing required ARTG field: {field}")
    return value


def _status_code(value: str) -> str:
    return "-".join(value.casefold().split())
