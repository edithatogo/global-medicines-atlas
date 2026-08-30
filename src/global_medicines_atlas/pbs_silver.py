"""PBS native-field Arrow candidates over the receipt-bound XML inventory.

The existing PBS parser retains a bounded XML tree; only the additional Arrow
row buffer is batch-bounded. This is not a constant-memory streaming parser or
real-schedule qualification. Source bytes remain evidentiary truth, including
lexical details (prefixes, comments and entity spelling) outside the inventory.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pyarrow as pa

from .australian_silver_metadata import receipt_projection_metadata
from .australian_source_contracts import pbs_native_fields
from .receipts import SourceReceipt

MAX_BATCH_ROWS = 4096


def pbs_silver_schema() -> pa.Schema:
    """Return the versioned native-field schema, without domain assertions."""
    return pa.schema(
        [
            pa.field("source_field_id", pa.string(), nullable=False),
            pa.field("source_ordinal", pa.int64(), nullable=False),
            pa.field("receipt_sha256", pa.string(), nullable=False),
            pa.field("source_id", pa.string(), nullable=False),
            pa.field("source_sha256", pa.string(), nullable=False),
            pa.field("schema_era", pa.string(), nullable=False),
            pa.field("record_id", pa.string(), nullable=False),
            pa.field("path", pa.string(), nullable=False),
            pa.field("schema_path", pa.string(), nullable=False),
            pa.field("value", pa.string()),
            pa.field("state", pa.string(), nullable=False),
        ],
        metadata={
            "schema_name": "global-medicines-atlas.pbs-silver.native-fields",
            "schema_version": "1.0",
            "source_id": "au-pbs",
            "dimension": "uninterpreted_source_structure",
            "qualification": "candidate",
            "mapping_status": "source_native",
            "absence_interpretation": "unknown",
            "conversion": "none",
            "path_encoding": "escaped-expanded-XML-name-with-occurrence",
        },
    )


def iter_pbs_silver_batches(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Yield every native slot in source order with exact B1/B2 identities.

    Expanded names preserve namespace URIs, not original prefix spellings.
    Element occurrences remain distinct even when native xml:id values repeat.
    Absent elements have no invented rows; existing empty text/tail slots are
    null. Currency, date and terminology strings are not interpreted. The source
    receipt must describe these XML bytes, not a containing ZIP archive.
    """
    if (
        type(rows_per_batch) is not int
        or not 1 <= rows_per_batch <= MAX_BATCH_ROWS
    ):
        raise ValueError("PBS Silver batch size must be between 1 and 4096")
    receipt = SourceReceipt.model_validate(receipt.model_dump())
    schema = pbs_silver_schema()
    metadata = dict(schema.metadata or {})
    metadata.update(receipt_projection_metadata(receipt))
    schema = schema.with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType]
    digest = receipt.digest()
    rows: list[dict[str, Any]] = []
    for ordinal, field in enumerate(pbs_native_fields(payload, receipt)):
        rows.append({
            **field.model_dump(),
            "source_field_id": f"{field.source_sha256}:{field.path}",
            "source_ordinal": ordinal,
            "receipt_sha256": digest,
        })
        if len(rows) == rows_per_batch:
            yield pa.RecordBatch.from_pylist(rows, schema=schema)
            rows = []
    if rows:
        yield pa.RecordBatch.from_pylist(rows, schema=schema)
