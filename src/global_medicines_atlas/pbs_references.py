"""Literal PBS identifiers and unresolved source-reference diagnostics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from itertools import pairwise
from typing import Any, cast

import orjson
import pyarrow as pa
import pyarrow.compute as pc

from .adapters.au_pbs import PBS_V3_NAMESPACE, RDF_NAMESPACE
from .pbs_entities import iter_pbs_entity_batches
from .receipts import SourceReceipt

MAX_INDEX_ENTRIES = 100_000
MAX_INDEX_BYTES = 16 * 1024 * 1024
MAX_BATCH_BYTES = 8 * 1024 * 1024
_PBS = f"{{{PBS_V3_NAMESPACE}}}"
type ReferenceIndex = dict[tuple[str, str], tuple[Counter[str | None], int]]


def _size(value: object) -> int:
    return len(orjson.dumps(value))


def _attribute(row: dict[str, Any], name: str) -> tuple[str | None, str]:
    suffix = "/attributes/" + name.replace("~", "~0").replace("/", "~1")
    for field in row["native_fields"]:
        if field["path"] == field["record_id"] + suffix:
            return field["value"], field["state"]
    return None, "missing_field"


def _contract(  # pyright: ignore[reportUnusedFunction] -- retained parity oracle
    row: dict[str, Any],
) -> dict[str, Any]:
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


def _index(
    batches: Iterator[pa.RecordBatch],
) -> tuple[ReferenceIndex, pa.Schema | None]:
    index: ReferenceIndex = {}
    identity: pa.Schema | None = None
    entries = encoded_bytes = 0
    for batch in batches:
        if identity is None:
            identity = batch.schema
        elif not batch.schema.equals(identity, check_metadata=True):
            raise ValueError("PBS reference input identity changed")
        for contract in _columnar_contracts(batch):
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
    return index, identity


def _columnar_contracts(batch: pa.RecordBatch) -> Iterator[dict[str, Any]]:
    """Read reference candidates without materialising complete entity rows."""
    names = (
        "entity_id",
        "item_occurrence_id",
        "native_name",
        "mapping_target",
        "native_xml_id",
        "xml_id_state",
        "native_text",
        "text_state",
    )
    columns: dict[str, list[Any]] = {
        name: cast(
            "list[Any]",
            batch.column(batch.schema.get_field_index(name)).to_pylist(),
        )
        for name in names
    }
    nested = cast(
        "pa.ListArray[Any]",
        batch.column(batch.schema.get_field_index("native_fields")),
    )
    offsets = cast("list[int]", nested.offsets.to_pylist())
    flattened = cast("pa.StructArray", pc.list_flatten(nested))
    fields: dict[str, list[Any]] = {
        name: cast(
            "list[Any]",
            flattened.field(name).to_pylist(),  # pyright: ignore[reportUnknownMemberType]
        )
        for name in ("record_id", "path", "value", "state")
    }
    rdf_resource = f"{{{RDF_NAMESPACE}}}resource"
    for row_number, (start, stop) in enumerate(pairwise(offsets)):
        kind = "unmapped"
        value, state = None, "not_applicable"
        resource, resource_state = None, "not_applicable"
        if (
            columns["item_occurrence_id"][row_number]
            == columns["entity_id"][row_number]
        ):
            kind = "item_xml_id"
            value = columns["native_xml_id"][row_number]
            state = columns["xml_id_state"][row_number]
        elif columns["native_name"][row_number] == _PBS + "code":
            mapping = columns["mapping_target"][row_number]
            record_id = fields["record_id"][start]
            attributes = {
                path[len(record_id) + len("/attributes/") :]: (
                    fields["value"][position],
                    fields["state"][position],
                )
                for position, path in enumerate(
                    fields["path"][start:stop], start
                )
                if path.startswith(record_id + "/attributes/")
            }
            if mapping == "amt_references":
                kind = "amt_reference"
                resource, resource_state = attributes.get(
                    rdf_resource.replace("~", "~0").replace("/", "~1"),
                    (None, "missing_field"),
                )
            elif mapping == "classifications" and attributes.get("type") == (
                "ATC",
                "value",
            ):
                kind = "atc_reference"
            if kind != "unmapped":
                value = columns["native_text"][row_number]
                state = columns["text_state"][row_number]
        yield {
            "contract_kind": kind,
            "reference_value": value,
            "reference_value_state": state,
            "reference_resource": resource,
            "reference_resource_state": resource_state,
        }


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
    yield from _reference_batches(
        iter_pbs_entity_batches(
            payload, receipt, rows_per_batch=rows_per_batch
        ),
        iter_pbs_entity_batches(
            payload, receipt, rows_per_batch=rows_per_batch
        ),
        rows_per_batch,
    )


def _reference_batches(
    index_batches: Iterator[pa.RecordBatch],
    output_batches: Iterator[pa.RecordBatch],
    rows_per_batch: int,
) -> Iterator[pa.RecordBatch]:
    """Annotate two trusted same-input streams; reject schema/identity drift."""
    index, identity = _index(index_batches)
    pieces: list[pa.RecordBatch] = []
    rows = 0
    size = 0
    schema: pa.Schema | None = None

    def assembled(
        output_schema: pa.Schema, output_pieces: list[pa.RecordBatch]
    ) -> pa.RecordBatch:
        table = pa.Table.from_batches(
            output_pieces, schema=output_schema
        ).combine_chunks()
        return table.to_batches()[0]

    for batch in output_batches:
        if identity is None or not batch.schema.equals(
            identity, check_metadata=True
        ):
            raise ValueError("PBS reference cross-pass identity changed")
        if schema is None:
            schema = _schema(batch.schema)
        diagnostics = [
            _diagnostics(contract, index)
            for contract in _columnar_contracts(batch)
        ]
        diagnostic_names = tuple(schema.names[len(batch.schema.names) :])
        output = pa.RecordBatch.from_arrays(  # pyright: ignore[reportUnknownMemberType]
            [
                *batch.columns,  # pyright: ignore[reportUnknownMemberType]
                *(
                    pa.array(
                        [item[name] for item in diagnostics],
                        type=schema.field(name).type,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                    )
                    for name in diagnostic_names
                ),
            ],
            schema=schema,
        )
        start = 0
        for position, (entity, diagnostic) in enumerate(
            zip(batch.to_pylist(), diagnostics, strict=True)
        ):
            row_size = _size(entity) + _size(diagnostic) - 1
            if row_size > MAX_BATCH_BYTES:
                raise ValueError("PBS reference row exceeds batch byte limit")
            if rows and (
                rows >= rows_per_batch or size + row_size > MAX_BATCH_BYTES
            ):
                if position > start:
                    pieces.append(output.slice(start, position - start))
                yield assembled(schema, pieces)
                pieces, rows, size = [], 0, 0
                start = position
            rows += 1
            size += row_size
        if start < batch.num_rows:
            pieces.append(output.slice(start))
    if pieces:
        yield assembled(cast("pa.Schema", schema), pieces)
