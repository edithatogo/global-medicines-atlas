"""Separate historical PBS member candidates with mandatory archive lineage."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pyarrow as pa

from .australian_silver_metadata import receipt_projection_metadata
from .pbs_member_identity import (
    PbsXmlMemberBinding,
    validate_pbs_xml_member_binding,
)
from .pbs_silver import MAX_BATCH_ROWS, pbs_silver_schema
from .pbs_xml_slots import iter_pbs_xml_slots
from .receipts import SourceReceipt

MAX_BATCH_BYTES = 8 * 1024 * 1024


def _schema(parent: SourceReceipt, binding: PbsXmlMemberBinding) -> pa.Schema:
    native = pbs_silver_schema()
    fields: list[pa.Field[pa.DataType]] = list(native)
    fields.extend(
        pa.field(name, pa.string(), nullable=False)
        for name in ("member_binding_sha256", "archive_sha256", "member_path")
    )
    metadata = dict(native.metadata or {})
    metadata.update(receipt_projection_metadata(parent))
    metadata.update({
        b"schema_name": b"global-medicines-atlas.pbs-silver.historical-native-fields",
        b"source_id": binding.source.source_id.encode(),
        b"member_binding": binding.canonical_json(),
        b"member_binding_sha256": binding.digest().encode(),
        b"receipt_scope": b"parent-archive-B1",
        b"source_sha256_scope": b"extracted-XML-member",
        b"historical_profile": b"pbs-historical-member-native-v1",
        b"byte_budget_measure": b"utf8-compact-json-not-python-resident-memory",
    })
    return pa.schema(fields).with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType]


def iter_pbs_historical_silver_batches(
    archive_payload: bytes,
    member_payload: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    *,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Yield historical member slots only after exact archive lineage checks.

    No SourceReceipt is fabricated, copied with another source, or relabelled.
    The original historical source remains distinct from the ordinary au-pbs
    route. Full binding metadata retains parent/archive/member sizes and IDs;
    each row carries parent receipt, archive, member and binding references.
    Native values are not converted. This is a candidate projection, not source
    admission, current coverage, real-corpus qualification or public delivery.
    Existing ZIP/XML bounds apply; validation and projection parse separately.
    Output rows/encoded bytes are bounded, not total resident memory. Discard
    partial outputs after errors; no network acquisition or filesystem writes.
    """
    if (
        type(rows_per_batch) is not int
        or not 1 <= rows_per_batch <= MAX_BATCH_ROWS
    ):
        raise ValueError("PBS historical batch size must be between 1 and 4096")
    # Runtime boundary also serves untyped callers with missing lineage.
    if not isinstance(parent, SourceReceipt) or not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
        binding, PbsXmlMemberBinding
    ):
        raise TypeError("historical parent receipt and member binding required")
    parent = SourceReceipt.model_validate(parent.model_dump())
    binding = validate_pbs_xml_member_binding(
        binding, archive_payload, member_payload, parent
    )
    schema = _schema(parent, binding)
    bound = {
        "source_id": binding.source.source_id,
        "source_sha256": binding.member_payload.sha256,
        "schema_era": binding.source.catalog_version,
        "receipt_sha256": binding.parent_receipt_sha256,
        "member_binding_sha256": binding.digest(),
        "archive_sha256": binding.archive_payload.sha256,
        "member_path": binding.member_path,
    }
    rows: list[dict[str, Any]] = []
    size = 0
    for ordinal, slot in enumerate(iter_pbs_xml_slots(member_payload)):
        row = {
            **bound,
            "source_field_id": f"{binding.member_payload.sha256}:{slot.path}",
            "source_ordinal": ordinal,
            "record_id": slot.record_id,
            "path": slot.path,
            "schema_path": slot.schema_path,
            "value": slot.value,
            "state": "null" if slot.value is None else "value",
        }
        row_size = len(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode()
        )
        if row_size > MAX_BATCH_BYTES:
            raise ValueError("PBS historical row exceeds batch byte limit")
        if rows and (
            len(rows) >= rows_per_batch or size + row_size > MAX_BATCH_BYTES
        ):
            yield pa.RecordBatch.from_pylist(rows, schema=schema)
            rows, size = [], 0
        rows.append(row)
        size += row_size
    if rows:
        yield pa.RecordBatch.from_pylist(rows, schema=schema)
