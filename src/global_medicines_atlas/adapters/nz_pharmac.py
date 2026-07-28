"""NZ Pharmaceutical Schedule XML funding adapter."""

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
from ..receipts import SourceReceipt
from ._receipt import provenance_from_receipt

SOURCE_ID = "nz-pharmac"
MAX_FIXTURE_BYTES = 1_000_000


def project_pharmac_schedule_xml(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project funded presentations from a Pharmac production-style XML file."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=SOURCE_ID,
        jurisdiction="NZL",
        transformation="nz-pharmac-schedule-xml-v1",
    )
    root = _fixture_xml(payload)
    records: list[CanonicalMedicineRecord] = []
    for presentation in root.findall(".//presentation"):
        pharmacode = _required_text(presentation, "pharmacode")
        name = _required_text(presentation, "name")
        status = _required_text(presentation, "funding-status")
        restrictions = tuple(
            text
            for node in presentation.findall("./restrictions/restriction")
            if (text := (node.text or "").strip())
        )
        concept_id = f"nz-pharmac:{pharmacode}"
        records.append(
            CanonicalMedicineRecord(
                concept=MedicineConcept(
                    concept_id=concept_id,
                    jurisdiction="NZL",
                    level="presentation",
                    preferred_name=name,
                    identifiers=(
                        Identifier(
                            system="https://schedule.pharmac.govt.nz/pharmacode",
                            value=pharmacode,
                            identifier_type="pharmacode",
                        ),
                    ),
                ),
                assertions=(
                    StatusAssertion(
                        assertion_id=f"{concept_id}:funding",
                        concept_id=concept_id,
                        jurisdiction="NZL",
                        kind=AssertionKind.FUNDING,
                        authority="Pharmac",
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
    if len(payload) > MAX_FIXTURE_BYTES:
        raise ValueError("Pharmac fixture exceeds the 1 MB contract limit")
    upper_payload = payload.upper()
    if b"<!DOCTYPE" in upper_payload or b"<!ENTITY" in upper_payload:
        raise ValueError("Pharmac fixture must not contain a DTD or entities")
    return ET.fromstring(  # ruff: ignore[suspicious-xml-element-tree-usage]
        payload
    )


def _required_text(parent: ET.Element, path: str) -> str:
    value = parent.findtext(path, default="").strip()
    if not value:
        raise ValueError(f"Missing required Pharmac XML field: {path}")
    return value


def _status_code(value: str) -> str:
    return "-".join(value.casefold().split())
