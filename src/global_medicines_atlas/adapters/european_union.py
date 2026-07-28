"""Synthetic contracts and native-shaped parsers for central EU sources."""

from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO
from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import]
    ElementTree as ET,
)

from ..models import (
    AssertionKind,
    CanonicalMedicineRecord,
    EvidenceStatus,
    Identifier,
    MedicineConcept,
    Provenance,
    StatusAssertion,
)
from ..receipts import SourceReceipt
from ._receipt import provenance_from_receipt
from .fixture_contracts import FixtureProjection, project_fixture

EMA_SOURCE_ID = "eu-ema"
UNION_REGISTER_SOURCE_ID = "eu-union-register"
MAX_NATIVE_PAYLOAD_BYTES = 1_000_000

SOURCE_CONTRACTS = {
    EMA_SOURCE_ID: (
        "European Medicines Agency",
        AssertionKind.REGULATORY,
        "https://www.ema.europa.eu/en/medicines",
    ),
    UNION_REGISTER_SOURCE_ID: (
        "European Commission",
        AssertionKind.REGULATORY,
        "https://ec.europa.eu/health/documents/community-register/",
    ),
}


def project_eu_fixture(
    payload: bytes,
    *,
    retrieved_at: datetime,
) -> FixtureProjection:
    """Project synthetic EMA/Register records; no funding status is inferred."""
    return project_fixture(
        payload=payload,
        retrieved_at=retrieved_at,
        jurisdiction="EU",
        transformation_id="eu-ema-union-register-fixture-v1",
        source_contracts=SOURCE_CONTRACTS,
    )


def project_ema_medicine_csv(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project a bounded EMA medicine-download CSV fixture."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=EMA_SOURCE_ID,
        jurisdiction="EU",
        transformation="eu-ema-medicine-csv-v1",
    )
    rows = csv.DictReader(StringIO(_decode_native(payload, "EMA")))
    records = [
        _record(
            local_id=_required(row, "ema_product_number", "EMA"),
            name=_required(row, "medicine_name", "EMA"),
            identifier_system="https://www.ema.europa.eu/product-number",
            status=_required(row, "authorisation_status", "EMA"),
            authority="European Medicines Agency",
            source_id=EMA_SOURCE_ID,
            provenance=provenance,
        )
        for row in rows
    ]
    return tuple(sorted(records, key=lambda record: record.concept.concept_id))


def project_union_register_xml(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project a bounded Union Register XML fixture."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=UNION_REGISTER_SOURCE_ID,
        jurisdiction="EU",
        transformation="eu-union-register-xml-v1",
    )
    root = _native_xml(payload, "Union Register")
    records = [
        _record(
            local_id=_required_text(product, "number", "Union Register"),
            name=_required_text(product, "name", "Union Register"),
            identifier_system=(
                "https://ec.europa.eu/health/documents/"
                "community-register/product-number"
            ),
            status=_required_text(
                product,
                "authorisation-status",
                "Union Register",
            ),
            authority="European Commission",
            source_id=UNION_REGISTER_SOURCE_ID,
            provenance=provenance,
        )
        for product in root.findall(".//product")
    ]
    return tuple(sorted(records, key=lambda record: record.concept.concept_id))


def _record(
    *,
    local_id: str,
    name: str,
    identifier_system: str,
    status: str,
    authority: str,
    source_id: str,
    provenance: Provenance,
) -> CanonicalMedicineRecord:
    concept_id = f"{source_id}:{local_id}"
    return CanonicalMedicineRecord(
        concept=MedicineConcept(
            concept_id=concept_id,
            jurisdiction="EU",
            level="centrally-authorised-product",
            preferred_name=name,
            identifiers=(
                Identifier(
                    system=identifier_system,
                    value=local_id,
                    identifier_type="central-authorisation-number",
                ),
            ),
        ),
        assertions=(
            StatusAssertion(
                assertion_id=f"{concept_id}:regulatory",
                concept_id=concept_id,
                jurisdiction="EU",
                kind=AssertionKind.REGULATORY,
                authority=authority,
                status_code=_status_code(status),
                evidence_status=EvidenceStatus.UNKNOWN,
                provenance=provenance,
            ),
        ),
        provenance=(provenance,),
    )


def _decode_native(payload: bytes, label: str) -> str:
    if len(payload) > MAX_NATIVE_PAYLOAD_BYTES:
        raise ValueError(f"{label} fixture exceeds the 1 MB contract limit")
    return payload.decode("utf-8-sig")


def _native_xml(payload: bytes, label: str) -> ET.Element:
    _decode_native(payload, label)
    upper_payload = payload.upper()
    if b"<!DOCTYPE" in upper_payload or b"<!ENTITY" in upper_payload:
        raise ValueError(f"{label} fixture must not contain a DTD or entities")
    return ET.fromstring(  # ruff: ignore[suspicious-xml-element-tree-usage]
        payload
    )


def _required(row: dict[str, str | None], field: str, label: str) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise ValueError(f"Missing required {label} field: {field}")
    return value


def _required_text(parent: ET.Element, path: str, label: str) -> str:
    value = parent.findtext(path, default="").strip()
    if not value:
        raise ValueError(f"Missing required {label} XML field: {path}")
    return value


def _status_code(value: str) -> str:
    return "-".join(value.casefold().split())
