"""Health Canada DPD and Notice of Compliance adapters."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import UTC, date, datetime, time
from io import StringIO
from typing import cast

import orjson

from ..ingestors import (
    PayloadMember,
    PayloadSet,
    ProjectionOutcome,
    ProjectionSchema,
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
from ..parity import ParityResult, compare_projections
from ..receipts import AcquisitionMethod, SourceReceipt
from ._receipt import provenance_from_receipt
from .fixture_contracts import FixtureProjection, project_fixture

MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 1_000
MAX_FIELD_LENGTH = 4_096

SOURCE_CONTRACTS = {
    "ca-dpd": (
        "Health Canada",
        AssertionKind.REGULATORY,
        "https://health-products.canada.ca/dpd-bdpp/",
    ),
    "ca-noc": (
        "Health Canada",
        AssertionKind.REGULATORY,
        "https://health-products.canada.ca/noc-ac/",
    ),
}

DPD_PARITY_SCHEMA = ProjectionSchema(
    schema_id="ca-dpd-canonical-product-v1",
    fields={
        "concept_id": "string",
        "din": "string",
        "drug_code": "string",
        "preferred_name": "string",
        "regulatory_status": "string",
    },
)


def project_dpd_api(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project a bounded DPD API response into regulatory assertions."""
    provenance = _validated_provenance(
        payload,
        receipt,
        source_id="ca-dpd",
        method=AcquisitionMethod.API,
        transformation="ca-dpd-api-v1",
    )
    document = cast("object", orjson.loads(payload))
    if not isinstance(document, dict):
        raise TypeError("DPD API payload must be a JSON object")
    document = cast("dict[object, object]", document)
    rows = document.get("results")
    if not isinstance(rows, list):
        raise TypeError("DPD API payload requires a results list")
    rows = cast("list[object]", rows)
    if len(rows) > MAX_RECORDS:
        raise ValueError("DPD API record limit exceeded")
    return _project_dpd_rows(rows, provenance, receipt)


def project_dpd_bulk(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project a bounded DPD bulk CSV extract into regulatory assertions."""
    provenance = _validated_provenance(
        payload,
        receipt,
        source_id="ca-dpd",
        method=AcquisitionMethod.DOWNLOAD,
        transformation="ca-dpd-bulk-csv-v1",
    )
    rows = _csv_rows(payload, source_name="DPD bulk")
    normalized: list[dict[str, object]] = [
        {
            "drug_code": _required(row, "DRUG_CODE", "DPD bulk"),
            "brand_name": _required(row, "BRAND_NAME", "DPD bulk"),
            "status": _required(row, "STATUS", "DPD bulk"),
            "din": _required(row, "DIN", "DPD bulk"),
        }
        for row in rows
    ]
    return _project_dpd_rows(normalized, provenance, receipt)


def compare_dpd_api_bulk(
    api_payload: bytes,
    api_receipt: SourceReceipt,
    bulk_payload: bytes,
    bulk_receipt: SourceReceipt,
    *,
    api_population_id: str,
    bulk_population_id: str,
) -> ParityResult:
    """Compare like-for-like DPD API and bulk canonical projections."""
    api_records = project_dpd_api(api_payload, api_receipt)
    bulk_records = project_dpd_bulk(bulk_payload, bulk_receipt)
    return compare_projections(
        _dpd_parity_outcome(
            payload=api_payload,
            receipt=api_receipt,
            records=api_records,
            population_id=api_population_id,
        ),
        _dpd_parity_outcome(
            payload=bulk_payload,
            receipt=bulk_receipt,
            records=bulk_records,
            population_id=bulk_population_id,
        ),
    )


def project_noc_extract(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project a bounded NOC CSV extract into regulatory assertions."""
    provenance = _validated_provenance(
        payload,
        receipt,
        source_id="ca-noc",
        method=AcquisitionMethod.DOWNLOAD,
        transformation="ca-noc-extract-csv-v1",
    )
    records: list[CanonicalMedicineRecord] = []
    for row in _csv_rows(payload, source_name="NOC extract"):
        notice_number = _required(row, "NOC_NUMBER", "NOC extract")
        name = _required(row, "PRODUCT_NAME", "NOC extract")
        status = _required(row, "NOTICE_STATUS", "NOC extract")
        din = _required(row, "DIN", "NOC extract")
        effective_at = _optional_date(row.get("NOTICE_DATE"))
        concept_id = f"ca-noc:{notice_number}"
        records.append(
            _record(
                concept_id=concept_id,
                name=name,
                identifier_system=("https://health-products.canada.ca/noc-ac/"),
                identifiers=(notice_number, din),
                identifier_types=("noc-number", "din"),
                status=status,
                provenance=provenance,
                evidence_status=_evidence_status(receipt),
                effective_at=effective_at,
            )
        )
    return tuple(sorted(records, key=lambda item: item.concept.concept_id))


def project_canada_fixture(
    payload: bytes,
    *,
    retrieved_at: datetime,
) -> FixtureProjection:
    """Project synthetic DPD/NOC records; no funding status is inferred."""
    return project_fixture(
        payload=payload,
        retrieved_at=retrieved_at,
        jurisdiction="CAN",
        transformation_id="canada-dpd-noc-fixture-v1",
        source_contracts=SOURCE_CONTRACTS,
    )


def _validated_provenance(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    source_id: str,
    method: AcquisitionMethod,
    transformation: str,
) -> Provenance:
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError("Canadian source payload byte limit exceeded")
    if receipt.retrieval.acquisition_method is not method:
        raise ValueError(f"Expected acquisition method {method.value!r}")
    return provenance_from_receipt(
        receipt,
        payload,
        source_id=source_id,
        jurisdiction="CAN",
        transformation=transformation,
    )


def _csv_rows(
    payload: bytes,
    *,
    source_name: str,
) -> tuple[dict[str, str | None], ...]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"{source_name} must be UTF-8") from error
    rows = tuple(csv.DictReader(StringIO(text)))
    if len(rows) > MAX_RECORDS:
        raise ValueError(f"{source_name} record limit exceeded")
    for row in rows:
        if any(
            value is not None and len(value) > MAX_FIELD_LENGTH
            for value in row.values()
        ):
            raise ValueError(f"{source_name} field limit exceeded")
    return rows


def _project_dpd_rows(
    rows: Sequence[object],
    provenance: Provenance,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    records: list[CanonicalMedicineRecord] = []
    for item in rows:
        if not isinstance(item, dict):
            raise TypeError("Every DPD record must be an object")
        typed_item = cast("dict[object, object]", item)
        row = {str(key): value for key, value in typed_item.items()}
        drug_code = _json_field(row, "drug_code")
        name = _json_field(row, "brand_name")
        status = _json_field(row, "status")
        din = _json_field(row, "din")
        concept_id = f"ca-dpd:{drug_code}"
        records.append(
            _record(
                concept_id=concept_id,
                name=name,
                identifier_system=(
                    "https://health-products.canada.ca/dpd-bdpp/"
                ),
                identifiers=(drug_code, din),
                identifier_types=("drug-code", "din"),
                status=status,
                provenance=provenance,
                evidence_status=_evidence_status(receipt),
            )
        )
    return tuple(sorted(records, key=lambda item: item.concept.concept_id))


def _dpd_parity_outcome(
    *,
    payload: bytes,
    receipt: SourceReceipt,
    records: tuple[CanonicalMedicineRecord, ...],
    population_id: str,
) -> ProjectionOutcome:
    payloads = PayloadSet(
        source_id="ca-dpd",
        jurisdiction="CAN",
        members=(
            PayloadMember(
                name="dpd",
                payload=payload,
                receipt=receipt,
            ),
        ),
    )
    comparable_records = tuple(_parity_record(record) for record in records)
    return ProjectionOutcome(
        source_id="ca-dpd",
        jurisdiction="CAN",
        projection_id="ca-dpd-canonical-product-v1",
        population_id=population_id,
        payload_set_digest=payloads.lineage_digest,
        receipt_ids=payloads.receipt_ids,
        schema_fingerprint=DPD_PARITY_SCHEMA.fingerprint,
        records=comparable_records,
    )


def _parity_record(
    record: CanonicalMedicineRecord,
) -> CanonicalMedicineRecord:
    """Remove acquisition-surface metadata from the semantic comparison."""
    provenance = Provenance(
        source_id="ca-dpd",
        source_uri="urn:global-medicines-atlas:parity:ca-dpd",
        transformation="ca-dpd-canonical-product-v1",
    )
    assertions = tuple(
        assertion.model_copy(update={"provenance": provenance})
        for assertion in record.assertions
    )
    return record.model_copy(
        update={
            "assertions": assertions,
            "provenance": (provenance,),
        }
    )


def _record(
    *,
    concept_id: str,
    name: str,
    identifier_system: str,
    identifiers: tuple[str, ...],
    identifier_types: tuple[str, ...],
    status: str,
    provenance: Provenance,
    evidence_status: EvidenceStatus,
    effective_at: datetime | None = None,
) -> CanonicalMedicineRecord:
    assertion = StatusAssertion(
        assertion_id=f"{concept_id}:regulatory",
        concept_id=concept_id,
        jurisdiction="CAN",
        kind=AssertionKind.REGULATORY,
        authority="Health Canada",
        status_code=_status_code(status),
        evidence_status=evidence_status,
        effective_from=effective_at,
        provenance=provenance,
    )
    return CanonicalMedicineRecord(
        concept=MedicineConcept(
            concept_id=concept_id,
            jurisdiction="CAN",
            level="product",
            preferred_name=name,
            identifiers=tuple(
                Identifier(
                    system=identifier_system,
                    value=value,
                    identifier_type=identifier_type,
                )
                for value, identifier_type in zip(
                    identifiers,
                    identifier_types,
                    strict=True,
                )
            ),
        ),
        assertions=(assertion,),
        provenance=(provenance,),
    )


def _required(
    row: dict[str, str | None],
    field: str,
    source_name: str,
) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise ValueError(f"Missing required {source_name} field: {field}")
    return _bounded_field(value, field)


def _json_field(row: dict[str, object], field: str) -> str:
    value = row.get(field)
    if value is None or isinstance(value, (dict, list, bool)):
        raise ValueError(f"Missing or invalid DPD API field: {field}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"Missing or invalid DPD API field: {field}")
    return _bounded_field(text, field)


def _bounded_field(value: str, field: str) -> str:
    if len(value) > MAX_FIELD_LENGTH:
        raise ValueError(f"Canadian source field limit exceeded: {field}")
    return value


def _status_code(value: str) -> str:
    return "-".join(value.casefold().split())


def _evidence_status(receipt: SourceReceipt) -> EvidenceStatus:
    if receipt.satisfies_live_gate:
        return EvidenceStatus.CONFIRMED
    return EvidenceStatus.UNKNOWN


def _optional_date(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError as error:
        raise ValueError("NOTICE_DATE must use YYYY-MM-DD") from error
    return datetime.combine(parsed, time.min, tzinfo=UTC)
