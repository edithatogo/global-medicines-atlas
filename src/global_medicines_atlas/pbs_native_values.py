"""Loss-aware PBS value candidates alongside complete native entity evidence.

Only established structural roles select a numeric candidate. Source meaning,
price basis, currency meaning, vocabulary membership and era equivalence remain
unresolved. Original nested fields and occurrence identities remain unchanged.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from decimal import Decimal
from typing import Any, cast

import pyarrow as pa

from .pbs_entities import iter_pbs_entity_batches
from .pbs_historical_projections import iter_pbs_historical_entity_batches
from .pbs_member_identity import PbsXmlMemberBinding
from .receipts import SourceReceipt

DECIMAL_TYPE = pa.decimal128(38, 9)
MAX_NUMERIC_CHARS = 256
_NUMBER = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?\Z")
_ADDITIONS = (
    pa.field("interpretation_state", pa.string(), nullable=False),
    pa.field("interpretation_reason", pa.string(), nullable=False),
    pa.field("semantic_evidence_sha256", pa.string()),
    pa.field("candidate_decimal", DECIMAL_TYPE),
    pa.field("candidate_conversion_status", pa.string(), nullable=False),
    pa.field("native_currency", pa.string()),
    pa.field("native_currency_state", pa.string(), nullable=False),
    pa.field("reference_meaning_state", pa.string(), nullable=False),
)


def _candidate(value: str | None, state: str) -> tuple[Decimal | None, str]:
    if value is None:
        return None, state
    if not value.strip():
        return None, "blank"
    if len(value) > MAX_NUMERIC_CHARS:
        return None, "unrepresentable"
    if not _NUMBER.fullmatch(value):
        return None, "unsupported_numeric_grammar"
    number = Decimal(value)
    try:
        pa.scalar(number, type=DECIMAL_TYPE)
    except pa.ArrowInvalid:
        return None, "unrepresentable"
    return number, "lossless_candidate"


def _values(row: dict[str, Any]) -> dict[str, Any]:
    price = row["mapping_target"] == "prices"
    currency = (
        next(
            (
                field
                for field in row["native_fields"]
                if field["path"] == field["record_id"] + "/attributes/currency"
            ),
            None,
        )
        if price
        else None
    )
    number, status = (
        _candidate(row["native_text"], row["text_state"])
        if price
        else (None, "not_price")
    )
    return {
        "interpretation_state": "native_unresolved",
        "interpretation_reason": "PBS source domain meaning and era equivalence are not qualified",
        "semantic_evidence_sha256": None,
        "candidate_decimal": number,
        "candidate_conversion_status": status,
        "native_currency": currency["value"] if currency else None,
        "native_currency_state": currency["state"]
        if currency
        else "missing_field"
        if price
        else "not_applicable",
        "reference_meaning_state": "native_reference_only"
        if row["mapping_target"] in {"amt_references", "classifications"}
        else "not_applicable",
    }


def iter_pbs_value_batches(
    payload: bytes, receipt: SourceReceipt, *, rows_per_batch: int = 1024
) -> Iterator[pa.RecordBatch]:
    """Retain every entity while adding explicit unresolved, loss-aware values.

    Source-bound native parsing and entity row/byte bounds are inherited. Added
    arrays are row-bounded. Decimal candidates never establish payable amounts,
    currency conversion, regulatory status, clinical meaning or code membership.
    No date interpretation or patient-rate inference is performed.
    """
    yield from _value_batches(
        iter_pbs_entity_batches(payload, receipt, rows_per_batch=rows_per_batch)
    )


def iter_pbs_historical_value_batches(
    archive_payload: bytes,
    member_payload: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    *,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Add unresolved value candidates after mandatory historical lineage checks.

    Retain parent receipt, archive/member identities and native fields intact.
    Shared conversions establish neither era equivalence nor domain semantics.
    """
    yield from _value_batches(
        iter_pbs_historical_entity_batches(
            archive_payload,
            member_payload,
            parent,
            binding,
            rows_per_batch=rows_per_batch,
        )
    )


def _value_batches(
    batches: Iterator[pa.RecordBatch],
) -> Iterator[pa.RecordBatch]:
    """Annotate only internally validated ordinary or historical entity streams."""
    for batch in batches:
        schema = batch.schema
        for field in _ADDITIONS:
            schema = schema.append(field)  # pyright: ignore[reportUnknownMemberType] -- Arrow schema append stub
        metadata = dict(schema.metadata or {})
        metadata.update({
            b"schema_name": b"global-medicines-atlas.pbs-silver.native-value-candidates",
            b"value_profile": b"pbs-native-unresolved-values-v1",
            b"domain_semantics_qualified": b"false",
            b"decimal_candidate_type": b"decimal128(38,9)",
            b"cross_era_equivalence": b"unestablished",
        })
        schema = schema.with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType] -- Arrow schema metadata stub
        values = [_values(row) for row in batch.to_pylist()]
        additions = [
            pa.array([row[field.name] for row in values], type=field.type)
            for field in _ADDITIONS
        ]
        yield pa.RecordBatch.from_arrays(  # pyright: ignore[reportUnknownMemberType] -- Arrow constructor stub
            [
                *[
                    cast("pa.Array[Any]", batch.column(index))
                    for index in range(batch.num_columns)
                ],
                *additions,
            ],
            schema=schema,
        )
