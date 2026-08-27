"""Source-native Bronze records for French public tabular payloads."""

from __future__ import annotations

import csv
from io import StringIO

import pyarrow as pa

from .bronze_landing import SourceRecordBatch

FRENCH_PUBLIC_SOURCE_IDS = frozenset({"fr-bdpm", "fr-bdpm-smr-asmr"})
_FIELD_PREFIX = "source_unlabelled_field_"


def french_text_encoding(payload: bytes) -> str:
    """Select the lossless encoding used by the published French tables."""
    if b"\x00" in payload:
        raise ValueError("French tabular payload contains NUL bytes")
    try:
        payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        payload.decode("cp1252")
        return "cp1252"
    return "utf-8-sig"


def french_source_record_batch(
    source_id: str, payload: bytes
) -> SourceRecordBatch:
    """Preserve unlabeled tab-separated rows without semantic inference."""
    if source_id not in FRENCH_PUBLIC_SOURCE_IDS:
        raise ValueError(f"unsupported French source: {source_id}")
    encoding = french_text_encoding(payload)
    rows = [
        (row_number, values)
        for row_number, values in enumerate(
            csv.reader(
                StringIO(payload.decode(encoding), newline=""), delimiter="\t"
            ),
            start=1,
        )
        if values and any(values)
    ]
    if not rows:
        raise ValueError("French tabular payload has no records")
    maximum_fields = max(len(values) for _, values in rows)
    records: list[dict[str, str | int | None]] = []
    for row_number, values in rows:
        record: dict[str, str | int | None] = {
            "source_record_key": f"row:{row_number}",
            "source_row_number": row_number,
            "source_field_count": len(values),
        }
        record.update({
            f"{_FIELD_PREFIX}{offset}": value
            for offset, value in enumerate(values, start=1)
        })
        records.append(record)
    schema = pa.schema([
        pa.field("source_record_key", pa.string(), nullable=False),
        pa.field("source_row_number", pa.int64(), nullable=False),
        pa.field("source_field_count", pa.int64(), nullable=False),
        *(
            pa.field(f"{_FIELD_PREFIX}{offset}", pa.string())
            for offset in range(1, maximum_fields + 1)
        ),
    ])
    return SourceRecordBatch(
        table=pa.Table.from_pylist(records, schema=schema),
        parser_identity=f"gma:{source_id}:tabular-text:v1",
        record_id_column="source_record_key",
    )
