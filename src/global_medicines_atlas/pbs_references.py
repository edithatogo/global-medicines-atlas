"""Literal PBS identifiers and unresolved source-reference diagnostics."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from typing import Any

import pyarrow as pa

from .adapters.au_pbs import PBS_V3_NAMESPACE, RDF_NAMESPACE
from .pbs_entities import iter_pbs_entity_batches
from .receipts import SourceReceipt

MAX_INDEX_ENTRIES = 100_000
MAX_INDEX_BYTES = 16 * 1024 * 1024
MAX_BATCH_BYTES = 8 * 1024 * 1024
_PBS = f"{{{PBS_V3_NAMESPACE}}}"
type ReferenceIndex = dict[tuple[str, str], tuple[Counter[str | None], int]]


def _size(value: object) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    )


def _attribute(row: dict[str, Any], name: str) -> tuple[str | None, str]:
    suffix = "/attributes/" + name.replace("~", "~0").replace("/", "~1")
    for field in row["native_fields"]:
        if field["path"] == field["record_id"] + suffix:
            return field["value"], field["state"]
    return None, "missing_field"


def _contract(row: dict[str, Any]) -> dict[str, Any]:
    kind = "unmapped"
    value, state = None, "not_applicable"
    resource, resource_state = None, "not_applicable"
    if row["item_occurrence_id"] == row["entity_id"]:
        kind, value, state = (
            "item_xml_id",
            row["native_xml_id"],
            row["xml_id_state"],
        )
    elif row["native_name"] == _PBS + "code":
        if row["mapping_target"] == "amt_references":
            kind = "amt_reference"
            resource, resource_state = _attribute(
                row, f"{{{RDF_NAMESPACE}}}resource"
            )
        elif row["mapping_target"] == "classifications" and _attribute(
            row, "type"
        ) == ("ATC", "value"):
            kind = "atc_reference"
        if kind != "unmapped":
            value, state = row["native_text"], row["text_state"]
    return {
        "contract_kind": kind,
        "reference_value": value,
        "reference_value_state": state,
        "reference_resource": resource,
        "reference_resource_state": resource_state,
    }


def _index(payload: bytes, receipt: SourceReceipt, size: int) -> ReferenceIndex:
    index: ReferenceIndex = {}
    entries = encoded_bytes = 0
    for batch in iter_pbs_entity_batches(payload, receipt, rows_per_batch=size):
        for row in batch.to_pylist():
            contract = _contract(row)
            value = contract["reference_value"]
            if value is None or value == "":  # ruff: ignore[compare-to-empty-string] -- preserve whitespace-only literals
                continue
            key = (contract["contract_kind"], value)
            resource = contract["reference_resource"]
            counts, targets = index.get(key, (Counter(), 0))
            if resource not in counts:
                entries += 1
                encoded_bytes += _size((key, resource))
                if (
                    entries > MAX_INDEX_ENTRIES
                    or encoded_bytes > MAX_INDEX_BYTES
                ):
                    raise ValueError(
                        "PBS reference index exceeds entry/byte limit"
                    )
                if resource is not None and resource != "":  # ruff: ignore[compare-to-empty-string] -- literal target presence
                    targets += 1
            counts[resource] += 1
            index[key] = (counts, targets)
    return index


def _diagnostics(
    contract: dict[str, Any], index: ReferenceIndex
) -> dict[str, Any]:
    kind, value = contract["contract_kind"], contract["reference_value"]
    resource = contract["reference_resource"]
    counts, targets = index.get((kind, value), (Counter(), 0))
    occurrences = counts[resource]
    if kind == "unmapped":
        diagnostic = "unmapped"
    elif value is None:
        diagnostic = "missing_value"
    elif value == "":  # ruff: ignore[compare-to-empty-string] -- native blank differs from missing
        diagnostic = "empty_value"
    elif kind == "item_xml_id":
        diagnostic = (
            "duplicate_source_literal"
            if occurrences > 1
            else "unique_source_literal"
        )
    elif kind == "amt_reference" and resource is None:
        diagnostic = "missing_target"
    elif kind == "amt_reference" and resource == "":  # ruff: ignore[compare-to-empty-string] -- native blank differs from missing
        diagnostic = "empty_target"
    elif targets > 1:
        diagnostic = "ambiguous_source_targets"
    else:
        diagnostic = "unresolved"
    return {
        **contract,
        "occurrence_count": occurrences,
        "distinct_resource_count": targets,
        "diagnostic": diagnostic,
    }


def _schema(native: pa.Schema) -> pa.Schema:
    fields: list[pa.Field[pa.DataType]] = list(native)
    fields.extend(
        pa.field(name, pa.string(), nullable=nullable)
        for name, nullable in (
            ("contract_kind", False),
            ("reference_value", True),
            ("reference_value_state", False),
            ("reference_resource", True),
            ("reference_resource_state", False),
            ("diagnostic", False),
        )
    )
    fields.extend(
        pa.field(name, pa.int64(), nullable=False)
        for name in ("occurrence_count", "distinct_resource_count")
    )
    metadata = dict(native.metadata or {})
    metadata.update({
        b"schema_name": b"global-medicines-atlas.pbs-silver.references",
        b"reference_profile": b"pbs-adapter-literal-references-v1",
        b"reference_resolution": b"not-performed",
        b"diagnostic_scope": b"exact-literals-within-one-source-payload",
    })
    return pa.schema(fields).with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType]


def iter_pbs_reference_batches(
    payload: bytes, receipt: SourceReceipt, *, rows_per_batch: int = 1024
) -> Iterator[pa.RecordBatch]:
    """Retain every entity and annotate fixture-supported literal references.

    Two bounded entity passes detect forward duplicates/conflicting resources.
    The entry/encoded-byte index is bounded, not an exact resident-memory cap.
    No URI resolution, identifier normalization, vocabulary validation, semantic
    equivalence or status assertion occurs. Unknown entities remain unmapped.
    Consumers must discard partial output after any validation/budget error.
    """
    index = _index(payload, receipt, rows_per_batch)
    rows: list[dict[str, Any]] = []
    size = 0
    schema: pa.Schema | None = None
    for batch in iter_pbs_entity_batches(
        payload, receipt, rows_per_batch=rows_per_batch
    ):
        if schema is None:
            schema = _schema(batch.schema)
        for entity in batch.to_pylist():
            row = {**entity, **_diagnostics(_contract(entity), index)}
            row_size = _size(row)
            if row_size > MAX_BATCH_BYTES:
                raise ValueError("PBS reference row exceeds batch byte limit")
            if rows and (
                len(rows) >= rows_per_batch or size + row_size > MAX_BATCH_BYTES
            ):
                yield pa.RecordBatch.from_pylist(rows, schema=schema)
                rows, size = [], 0
            rows.append(row)
            size += row_size
    if rows:
        yield pa.RecordBatch.from_pylist(rows, schema=schema)
