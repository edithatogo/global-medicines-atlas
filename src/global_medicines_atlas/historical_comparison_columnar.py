"""In-memory Arrow projections of native candidates, not qualified Gold.

No acquisition, file access, publication, rights decision or status inference
occurs here. The envelope retains both bounded inputs even on abstention.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator

import pyarrow as pa

from .historical_comparison import NativeComparison, NativeSnapshot

MAX_BATCH_ROWS = 1024
MAX_CANONICAL_BYTES = 128 * 1024 * 1024
_METADATA: dict[bytes | str, bytes | str] = {
    b"schema_id": b"global-medicines-atlas.native-comparison-arrow",
    b"schema_version": b"1",
    b"qualification": b"native_difference_candidate",
    b"absence_interpretation": b"unknown",
}
_FIELD = pa.struct([
    pa.field("name", pa.string(), nullable=False),
    pa.field("state", pa.string(), nullable=False),
    pa.field("value", pa.string()),
])
_ROW = pa.struct([
    pa.field("native_id", pa.string(), nullable=False),
    pa.field("occurrence_id", pa.string(), nullable=False),
    pa.field("fields", pa.list_(_FIELD), nullable=False),
])
_SNAPSHOT = pa.struct([
    *[
        pa.field(name, pa.string(), nullable=False)
        for name in (
            "source_id",
            "table",
            "dimension",
            "schema_era",
            "identity_profile",
            "scope_id",
            "source_revision",
            "source_path",
            "b1_sha256",
            "b2_sha256",
            "cohort",
            "observed_at",
        )
    ],
    pa.field("declared_rows", pa.int64(), nullable=False),
    pa.field("actual_rows", pa.int64(), nullable=False),
    pa.field("complete", pa.bool_(), nullable=False),
    pa.field("rows", pa.list_(_ROW), nullable=False),
])
ENVELOPE_SCHEMA = pa.schema(
    [
        pa.field("comparison_sha256", pa.string(), nullable=False),
        pa.field("outcome", pa.string(), nullable=False),
        pa.field("reasons", pa.list_(pa.string()), nullable=False),
        pa.field("difference_count", pa.int64(), nullable=False),
        pa.field("left", _SNAPSHOT, nullable=False),
        pa.field("right", _SNAPSHOT, nullable=False),
    ],
    metadata=_METADATA,
)
DIFFERENCE_SCHEMA = pa.schema(
    [
        pa.field("comparison_sha256", pa.string(), nullable=False),
        pa.field("ordinal", pa.int64(), nullable=False),
        pa.field("native_id", pa.string(), nullable=False),
        pa.field("field_name", pa.string()),
        pa.field("kind", pa.string(), nullable=False),
        pa.field("left_occurrence", pa.string()),
        pa.field("right_occurrence", pa.string()),
        pa.field("left", _FIELD),
        pa.field("right", _FIELD),
    ],
    metadata=_METADATA,
)


def _digest(value: NativeComparison) -> str:
    digest = hashlib.sha256(b"gma-native-comparison-arrow-v1\0")
    size = 0
    encoder = json.JSONEncoder(
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    for chunk in encoder.iterencode(value.model_dump(mode="json")):
        encoded = chunk.encode("utf-8")
        size += len(encoded)
        if size > MAX_CANONICAL_BYTES:
            raise ValueError("comparison canonical byte limit exceeded")
        digest.update(encoded)
    return digest.hexdigest()


def _snapshot(value: NativeSnapshot) -> dict[str, object]:
    output = value.model_dump(mode="json")
    output["actual_rows"] = len(value.rows)
    return output


def _batches(
    value: NativeComparison,
    digest: str,
    rows_per_batch: int,
) -> Iterator[pa.RecordBatch]:
    for start in range(0, len(value.differences), rows_per_batch):
        rows = [
            {
                **difference.model_dump(mode="json"),
                "comparison_sha256": digest,
                "ordinal": start + offset,
            }
            for offset, difference in enumerate(
                value.differences[start : start + rows_per_batch]
            )
        ]
        yield pa.RecordBatch.from_pylist(rows, schema=DIFFERENCE_SCHEMA)


def project_native_comparison(
    value: NativeComparison,
    *,
    rows_per_batch: int = MAX_BATCH_ROWS,
) -> tuple[pa.Table, Iterator[pa.RecordBatch]]:
    """Validate eagerly and return one envelope plus bounded difference batches.

    The digest binds the versioned canonical JSON of the entire comparison;
    it is not proof of the source bytes or independent qualification. String
    timestamps preserve the input JSON precision and offset without rounding.
    """
    if (
        type(rows_per_batch) is not int
        or not 1 <= rows_per_batch <= MAX_BATCH_ROWS
    ):
        raise ValueError("rows_per_batch must be an integer from 1 to 1024")
    value = NativeComparison.model_validate(value.model_dump(warnings=False))
    digest = _digest(value)
    envelope = pa.Table.from_pylist(
        [
            {
                "comparison_sha256": digest,
                "outcome": value.outcome,
                "reasons": list(value.reasons),
                "difference_count": len(value.differences),
                "left": _snapshot(value.left),
                "right": _snapshot(value.right),
            }
        ],
        schema=ENVELOPE_SCHEMA,
    )
    return envelope, _batches(value, digest, rows_per_batch)
