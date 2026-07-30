"""Synthetic UK contracts plus native-shaped MHRA and NICE parsers."""

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
from ..parser_safety import ParserPolicy, parse_xml
from ..receipts import RightsState, SourceReceipt
from ._receipt import provenance_from_receipt
from .fixture_contracts import (
    FixtureProjection,
    SourceAccessLimit,
    project_fixture,
)

MHRA_SOURCE_ID = "uk-mhra"
NICE_SOURCE_ID = "uk-nice"
MAX_NATIVE_PAYLOAD_BYTES = 1_000_000

SOURCE_CONTRACTS = {
    MHRA_SOURCE_ID: (
        "Medicines and Healthcare products Regulatory Agency",
        AssertionKind.REGULATORY,
        "https://products.mhra.gov.uk/",
    ),
    NICE_SOURCE_ID: (
        "National Institute for Health and Care Excellence",
        AssertionKind.FUNDING,
        "https://www.nice.org.uk/guidance/published",
    ),
}

DMD_DECLARATION = SourceAccessLimit(
    source_id="uk-dmd",
    access="licensed-declaration-only",
    rights_state=RightsState.RESTRICTED,
    payload_included=False,
    evidence_limit=(
        "dm+d is declared as a licensed terminology dependency only. "
        "No dm+d payload, identifier mapping, regulatory assertion, funding "
        "assertion, or formulary assertion is included."
    ),
)


def project_uk_fixture(
    payload: bytes,
    *,
    retrieved_at: datetime,
) -> FixtureProjection:
    """Project synthetic MHRA/NICE evidence and append the dm+d boundary."""
    projection = project_fixture(
        payload=payload,
        retrieved_at=retrieved_at,
        jurisdiction="GBR",
        transformation_id="uk-mhra-nice-fixture-v1",
        source_contracts=SOURCE_CONTRACTS,
    )
    return FixtureProjection(
        records=projection.records,
        receipts=projection.receipts,
        access_limits=(*projection.access_limits, DMD_DECLARATION),
    )


def project_mhra_products_csv(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project a bounded, native-shaped MHRA products CSV fixture."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=MHRA_SOURCE_ID,
        jurisdiction="GBR",
        transformation="uk-mhra-products-csv-v1",
    )
    rows = csv.DictReader(StringIO(_decode_native(payload, "MHRA")))
    records = [
        _record(
            local_id=_required(row, "pl_number", "MHRA"),
            name=_required(row, "product_name", "MHRA"),
            level="nationally-authorised-product",
            identifier_system="https://products.mhra.gov.uk/pl-number",
            identifier_type="product-licence-number",
            status=_required(row, "licence_status", "MHRA"),
            kind=AssertionKind.REGULATORY,
            authority=("Medicines and Healthcare products Regulatory Agency"),
            source_id=MHRA_SOURCE_ID,
            provenance=provenance,
        )
        for row in rows
    ]
    return tuple(sorted(records, key=lambda record: record.concept.concept_id))


def project_nice_appraisals_xml(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project a bounded NICE appraisal syndication XML fixture."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=NICE_SOURCE_ID,
        jurisdiction="GBR",
        transformation="uk-nice-appraisal-xml-v1",
    )
    root = _native_xml(payload, "NICE")
    records = [
        _record(
            local_id=_required_text(appraisal, "guidance-id", "NICE"),
            name=_required_text(appraisal, "medicine", "NICE"),
            level="appraisal",
            identifier_system="https://www.nice.org.uk/guidance",
            identifier_type="technology-appraisal",
            status=_required_text(
                appraisal,
                "recommendation",
                "NICE",
            ),
            kind=AssertionKind.FUNDING,
            authority=("National Institute for Health and Care Excellence"),
            source_id=NICE_SOURCE_ID,
            provenance=provenance,
            restrictions=tuple(
                text
                for node in appraisal.findall("./conditions/condition")
                if (text := (node.text or "").strip())
            ),
        )
        for appraisal in root.findall(".//appraisal")
    ]
    return tuple(sorted(records, key=lambda record: record.concept.concept_id))


def _record(
    *,
    local_id: str,
    name: str,
    level: str,
    identifier_system: str,
    identifier_type: str,
    status: str,
    kind: AssertionKind,
    authority: str,
    source_id: str,
    provenance: Provenance,
    restrictions: tuple[str, ...] = (),
) -> CanonicalMedicineRecord:
    concept_id = f"{source_id}:{local_id}"
    return CanonicalMedicineRecord(
        concept=MedicineConcept(
            concept_id=concept_id,
            jurisdiction="GBR",
            level=level,
            preferred_name=name,
            identifiers=(
                Identifier(
                    system=identifier_system,
                    value=local_id,
                    identifier_type=identifier_type,
                ),
            ),
        ),
        assertions=(
            StatusAssertion(
                assertion_id=f"{concept_id}:{kind.value}",
                concept_id=concept_id,
                jurisdiction="GBR",
                kind=kind,
                authority=authority,
                status_code=_status_code(status),
                evidence_status=EvidenceStatus.UNKNOWN,
                restrictions=restrictions,
                provenance=provenance,
            ),
        ),
        provenance=(provenance,),
    )


def _decode_native(payload: bytes, label: str) -> str:
    if len(payload) > MAX_NATIVE_PAYLOAD_BYTES:
        raise ValueError(f"{label} fixture exceeds the 1 MB contract limit")
    return payload.decode("utf-8-sig")


def _native_xml(payload: bytes, _label: str) -> ET.Element:
    _decode_native(payload, _label)
    return parse_xml(
        payload,
        policy=ParserPolicy(max_bytes=MAX_NATIVE_PAYLOAD_BYTES),
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
