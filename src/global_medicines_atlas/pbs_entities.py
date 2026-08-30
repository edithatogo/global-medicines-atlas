"""Bounded PBS element rows retaining complete native field lineage."""

from __future__ import annotations

import json
from collections.abc import Iterator
from itertools import chain, groupby
from typing import Any

import pyarrow as pa

from .adapters.au_pbs import XML_NAMESPACE
from .pbs_domain import iter_pbs_domain_batches
from .receipts import SourceReceipt

MAX_ELEMENT_FIELDS = 4096
MAX_ELEMENT_BYTES = 1024 * 1024
MAX_BATCH_BYTES = 8 * 1024 * 1024
_HISTORICAL_LINEAGE = (
    "source_id",
    "source_sha256",
    "schema_era",
    "receipt_sha256",
    "member_binding_sha256",
    "archive_sha256",
    "member_path",
)


def _encoded_size(value: object) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    )


def _schema(native: pa.Schema) -> pa.Schema:
    fields: list[pa.Field[pa.DataType]] = [
        pa.field(name, pa.string(), nullable=nullable)
        for name, nullable in (
            ("entity_id", False),
            ("parent_entity_id", True),
            ("item_occurrence_id", True),
            ("native_name", False),
            ("mapping_target", False),
            ("native_xml_id", True),
            ("xml_id_state", False),
            ("native_text", True),
            ("text_state", False),
            ("native_tail", True),
            ("tail_state", False),
        )
    ]
    if "member_binding_sha256" in native.names:
        fields.extend(
            pa.field(name, pa.string(), nullable=False)
            for name in _HISTORICAL_LINEAGE
        )
    fields.append(
        pa.field(
            "native_fields",
            pa.list_(
                pa.field("element", pa.struct(list(native)), nullable=False)
            ),
            nullable=False,
        )
    )
    metadata = dict(native.metadata or {})
    metadata.update({
        b"schema_name": b"global-medicines-atlas.pbs-silver.entities",
        b"entity_profile": b"pbs-native-elements-v1",
        b"byte_budget_measure": b"utf8-compact-json-not-python-resident-memory",
    })
    return pa.schema(fields).with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType]


def _row(fields: list[dict[str, Any]]) -> dict[str, Any]:
    first = fields[0]
    record_id = first["record_id"]
    parts = record_id.split("/")
    parent = "/".join(parts[:-2])
    slots = {field["path"][len(record_id) + 1 :]: field for field in fields}
    xml_id_key = "attributes/" + f"{{{XML_NAMESPACE}}}id".replace(
        "~", "~0"
    ).replace("/", "~1")
    xml_id = slots.get(xml_id_key)
    lineage = (
        {name: first[name] for name in _HISTORICAL_LINEAGE}
        if "member_binding_sha256" in first
        else {}
    )
    return {
        **lineage,
        "entity_id": f"{first['source_sha256']}:{record_id}",
        "parent_entity_id": f"{first['source_sha256']}:{parent}"
        if parent
        else None,
        "item_occurrence_id": first["item_occurrence_id"],
        "native_name": parts[-2].replace("~1", "/").replace("~0", "~"),
        "mapping_target": first["mapping_target"],
        "native_xml_id": xml_id["value"] if xml_id is not None else None,
        "xml_id_state": xml_id["state"]
        if xml_id is not None
        else "missing_field",
        "native_text": slots["text"]["value"],
        "text_state": slots["text"]["state"],
        "native_tail": slots["tail"]["value"],
        "tail_state": slots["tail"]["state"],
        "native_fields": fields,
    }


def _native_rows(
    batches: Iterator[pa.RecordBatch],
) -> Iterator[tuple[pa.Schema, dict[str, Any]]]:
    for batch in batches:
        for row in batch.to_pylist():
            yield batch.schema, row


def _entities(
    batches: Iterator[pa.RecordBatch],
) -> Iterator[tuple[pa.Schema, dict[str, Any]]]:
    entity_schema: pa.Schema | None = None
    for _, group in groupby(
        _native_rows(batches),
        key=lambda pair: pair[1]["record_id"],
    ):
        schema, first = next(group)
        if entity_schema is None:
            # A single receipt-bound input has identical native batch metadata.
            entity_schema = _schema(schema)
        fields: list[dict[str, Any]] = []
        size = 0
        for _, field in chain(((schema, first),), group):
            size += _encoded_size(field)
            if len(fields) >= MAX_ELEMENT_FIELDS or size > MAX_ELEMENT_BYTES:
                raise ValueError("PBS entity element exceeds field/byte limit")
            fields.append(field)
        yield entity_schema, _row(fields)


def iter_pbs_entity_batches(
    payload: bytes, receipt: SourceReceipt, *, rows_per_batch: int = 1024
) -> Iterator[pa.RecordBatch]:
    """Yield occurrence rows, not flattened clinical or medicine assertions.

    All original mapped field rows are nested intact and can be flattened back
    in order. Empty elements and duplicate xml:id values survive independently.
    Parent links retain mixed-text structure; no descendant text is concatenated.
    Native parsing bounds still apply and retain a tree. Additional accumulation
    is capped by element fields/encoded bytes and output rows/encoded bytes, not
    claimed as a bound on total Python/Arrow resident memory. Oversized entities
    raise without truncation; callers must discard partial outputs after errors.
    """
    yield from _entity_batches(
        iter_pbs_domain_batches(
            payload, receipt, rows_per_batch=rows_per_batch
        ),
        rows_per_batch,
    )


def _entity_batches(
    batches: Iterator[pa.RecordBatch], rows_per_batch: int
) -> Iterator[pa.RecordBatch]:
    """Group only an internally validated domain stream using shared bounds."""
    rows: list[dict[str, Any]] = []
    size = 0
    schema: pa.Schema | None = None
    for schema, entity in _entities(batches):
        entity_size = _encoded_size(entity)
        if entity_size > MAX_BATCH_BYTES:
            raise ValueError("PBS entity exceeds batch byte limit")
        if rows and (
            len(rows) >= rows_per_batch or size + entity_size > MAX_BATCH_BYTES
        ):
            yield pa.RecordBatch.from_pylist(rows, schema=schema)
            rows, size = [], 0
        rows.append(entity)
        size += entity_size
    if rows:
        yield pa.RecordBatch.from_pylist(rows, schema=schema)
