"""Synthetic contracts and representative native-format Japanese adapters."""

from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO
from types import MappingProxyType

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
from .fixture_contracts import FixtureProjection, project_fixture

MAX_NATIVE_FIXTURE_BYTES = 1_000_000
PMDA_SOURCE_ID = "jp-pmda"
MHLW_SOURCE_ID = "jp-mhlw-nhi"

# These mappings are reviewed English descriptions of fixture field semantics,
# not certified translations of the live sources. Translation review remains
# an external gate before any live-source promotion.
PMDA_FIELD_MAPPINGS = MappingProxyType({
    "承認番号": "approval_number",
    "販売名": "product_name",
    "一般名": "generic_name",
    "承認年月日": "approval_date",
    "承認区分": "approval_category",
})
MHLW_NHI_FIELD_MAPPINGS = MappingProxyType({
    "薬価基準収載医薬品コード": "nhi_code",
    "品名": "product_name",
    "規格単位": "strength_unit",
    "薬価": "listed_price_yen",
    "収載区分": "listing_category",
    "適用年月日": "effective_date",
})
TRANSLATION_REVIEW_GATE = (
    "Japanese field mappings are representative and require independent "
    "translation review before live-source qualification."
)

SOURCE_CONTRACTS = {
    PMDA_SOURCE_ID: (
        "Pharmaceuticals and Medical Devices Agency",
        AssertionKind.REGULATORY,
        "https://www.pmda.go.jp/english/review-services/reviews/approved-information/drugs/0002.html",
    ),
    MHLW_SOURCE_ID: (
        "Ministry of Health, Labour and Welfare",
        AssertionKind.FUNDING,
        "https://www.mhlw.go.jp/topics/2024/04/tp20240401-01.html",
    ),
}


def project_japan_fixture(
    payload: bytes,
    *,
    retrieved_at: datetime,
) -> FixtureProjection:
    """Project synthetic PMDA and NHI evidence as independent dimensions."""
    return project_fixture(
        payload=payload,
        retrieved_at=retrieved_at,
        jurisdiction="JPN",
        transformation_id="japan-pmda-mhlw-nhi-fixture-v1",
        source_contracts=SOURCE_CONTRACTS,
    )


def project_pmda_approval_csv(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project a bounded representative PMDA approval CSV fixture."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=PMDA_SOURCE_ID,
        jurisdiction="JPN",
        transformation="jp-pmda-approval-csv-v1",
    )
    rows = _native_rows(payload, PMDA_FIELD_MAPPINGS, source="PMDA")
    records: list[CanonicalMedicineRecord] = []
    for row in rows:
        approval_number = _required(row, "approval_number", source="PMDA")
        product_name = _required(row, "product_name", source="PMDA")
        approval_category = _required(
            row,
            "approval_category",
            source="PMDA",
        )
        approval_date = _source_date(
            _required(row, "approval_date", source="PMDA"),
            source="PMDA",
        )
        generic_name = _required(row, "generic_name", source="PMDA")
        concept_id = f"jp-pmda:{approval_number}"
        records.append(
            CanonicalMedicineRecord(
                concept=MedicineConcept(
                    concept_id=concept_id,
                    jurisdiction="JPN",
                    level="product",
                    preferred_name=product_name,
                    identifiers=(
                        Identifier(
                            system="https://www.pmda.go.jp/",
                            value=approval_number,
                            identifier_type="pmda-approval-number",
                        ),
                    ),
                ),
                assertions=(
                    StatusAssertion(
                        assertion_id=f"{concept_id}:regulatory",
                        concept_id=concept_id,
                        jurisdiction="JPN",
                        kind=AssertionKind.REGULATORY,
                        authority=SOURCE_CONTRACTS[PMDA_SOURCE_ID][0],
                        status_code="approved",
                        evidence_status=EvidenceStatus.UNKNOWN,
                        effective_from=approval_date,
                        restrictions=(
                            f"source-approval-category:{approval_category}",
                            f"source-generic-name:{generic_name}",
                            TRANSLATION_REVIEW_GATE,
                        ),
                        provenance=provenance,
                    ),
                ),
                provenance=(provenance,),
            )
        )
    return tuple(sorted(records, key=lambda item: item.concept.concept_id))


def project_mhlw_nhi_price_csv(
    payload: bytes,
    receipt: SourceReceipt,
) -> tuple[CanonicalMedicineRecord, ...]:
    """Project a bounded representative MHLW NHI price-list CSV fixture."""
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id=MHLW_SOURCE_ID,
        jurisdiction="JPN",
        transformation="jp-mhlw-nhi-price-csv-v1",
    )
    rows = _native_rows(payload, MHLW_NHI_FIELD_MAPPINGS, source="MHLW NHI")
    records: list[CanonicalMedicineRecord] = []
    for row in rows:
        nhi_code = _required(row, "nhi_code", source="MHLW NHI")
        product_name = _required(row, "product_name", source="MHLW NHI")
        category = _required(row, "listing_category", source="MHLW NHI")
        strength_unit = _required(row, "strength_unit", source="MHLW NHI")
        price = _positive_decimal(
            _required(row, "listed_price_yen", source="MHLW NHI")
        )
        effective_date = _source_date(
            _required(row, "effective_date", source="MHLW NHI"),
            source="MHLW NHI",
        )
        concept_id = f"jp-mhlw-nhi:{nhi_code}"
        records.append(
            CanonicalMedicineRecord(
                concept=MedicineConcept(
                    concept_id=concept_id,
                    jurisdiction="JPN",
                    level="presentation",
                    preferred_name=product_name,
                    identifiers=(
                        Identifier(
                            system="https://www.mhlw.go.jp/",
                            value=nhi_code,
                            identifier_type="mhlw-nhi-code",
                        ),
                    ),
                ),
                assertions=(
                    StatusAssertion(
                        assertion_id=f"{concept_id}:funding",
                        concept_id=concept_id,
                        jurisdiction="JPN",
                        kind=AssertionKind.FUNDING,
                        authority=SOURCE_CONTRACTS[MHLW_SOURCE_ID][0],
                        status_code="nhi-listed",
                        evidence_status=EvidenceStatus.UNKNOWN,
                        effective_from=effective_date,
                        restrictions=(
                            f"source-listing-category:{category}",
                            f"source-strength-unit:{strength_unit}",
                            f"listed-price-jpy:{price}",
                            TRANSLATION_REVIEW_GATE,
                        ),
                        provenance=provenance,
                    ),
                ),
                provenance=(provenance,),
            )
        )
    return tuple(sorted(records, key=lambda item: item.concept.concept_id))


def _native_rows(
    payload: bytes,
    mappings: MappingProxyType[str, str],
    *,
    source: str,
) -> tuple[dict[str, str | None], ...]:
    if len(payload) > MAX_NATIVE_FIXTURE_BYTES:
        raise ValueError(f"{source} fixture exceeds the 1 MB contract limit")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"{source} fixture must be UTF-8 CSV") from error
    reader = csv.DictReader(StringIO(text))
    headers = set(reader.fieldnames or ())
    missing = set(mappings).difference(headers)
    if missing:
        raise ValueError(
            f"{source} fixture is missing native fields: "
            + ", ".join(sorted(missing))
        )
    return tuple(
        {english: row.get(japanese) for japanese, english in mappings.items()}
        for row in reader
    )


def _required(
    row: dict[str, str | None],
    field: str,
    *,
    source: str,
) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise ValueError(f"Missing required {source} field: {field}")
    return value


def _source_date(value: str, *, source: str) -> datetime:
    try:
        return datetime.fromisoformat(f"{value}T00:00:00+09:00")
    except ValueError as error:
        raise ValueError(
            f"Invalid {source} date; expected YYYY-MM-DD"
        ) from error


def _positive_decimal(value: str) -> str:
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError("MHLW NHI price must be numeric") from error
    if number < 0:
        raise ValueError("MHLW NHI price must not be negative")
    return value
