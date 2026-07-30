"""Australian Pharmaceutical Benefits Scheme funding XML adapter."""

from __future__ import annotations

from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import]
    ElementTree as ET,
)

from ..models import (
    AssertionKind,
    CanonicalMedicineRecord,
    EvidenceStatus,
    Identifier,
    MedicineConcept,
    StatusAssertion,
)
from ..parser_safety import ParserPolicy, parse_xml
from ..receipts import SourceReceipt
from ._receipt import provenance_from_receipt

SOURCE_ID = "au-pbs"
MAX_FIXTURE_BYTES = 1_000_000


def project_pbs_xml(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project listed items from a minimal PBS XML schedule."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=SOURCE_ID,
        jurisdiction="AUS",
        transformation="au-pbs-xml-v1",
    )
    root = _fixture_xml(payload)
    records: list[CanonicalMedicineRecord] = []
    for item in root.findall(".//item"):
        item_code = _required_text(item, "item-code")
        name = _required_text(item, "product-name")
        status = _required_text(item, "listing-status")
        restrictions = tuple(
            text
            for node in item.findall("./restrictions/restriction")
            if (text := (node.text or "").strip())
        )
        concept_id = f"au-pbs:{item_code}"
        records.append(
            CanonicalMedicineRecord(
                concept=MedicineConcept(
                    concept_id=concept_id,
                    jurisdiction="AUS",
                    level="presentation",
                    preferred_name=name,
                    identifiers=(
                        Identifier(
                            system="https://www.pbs.gov.au/medicine/item/",
                            value=item_code,
                            identifier_type="pbs-item-code",
                        ),
                    ),
                ),
                assertions=(
                    StatusAssertion(
                        assertion_id=f"{concept_id}:funding",
                        concept_id=concept_id,
                        jurisdiction="AUS",
                        kind=AssertionKind.FUNDING,
                        authority="Department of Health, Disability and Ageing",
                        status_code=_status_code(status),
                        evidence_status=(
                            EvidenceStatus.CONFIRMED
                            if receipt.satisfies_live_gate
                            else EvidenceStatus.UNKNOWN
                        ),
                        restrictions=restrictions,
                        provenance=provenance,
                    ),
                ),
                provenance=(provenance,),
            )
        )
    return tuple(sorted(records, key=lambda record: record.concept.concept_id))


def _fixture_xml(payload: bytes) -> ET.Element:
    return parse_xml(
        payload,
        policy=ParserPolicy(max_bytes=MAX_FIXTURE_BYTES),
    )


def _required_text(parent: ET.Element, path: str) -> str:
    value = parent.findtext(path, default="").strip()
    if not value:
        raise ValueError(f"Missing required PBS XML field: {path}")
    return value


def _status_code(value: str) -> str:
    return "-".join(value.casefold().split())
