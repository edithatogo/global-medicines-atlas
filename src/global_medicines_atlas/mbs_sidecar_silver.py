"""Bounded source-faithful sidecar records with explicit unresolved meanings."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict
from typing import Any

import pyarrow as pa

from .mbs_sidecar_inventory import BoundSidecar
from .mbs_sidecar_layout import MAX_BYTES, MAX_RECORDS, profile_sidecar
from .parser_safety import ParserPolicy, iter_xml_events

MAX_BATCH_ROWS = 4096
MAX_BATCH_BYTES = 8 * 1024 * 1024


def _encoded(value: Any) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n"
    ).encode()


def _field(
    record: str,
    schema: str,
    slot: str,
    value: str | None,
    column: int | None = None,
    *,
    xml: bool = False,
) -> dict[str, Any]:
    return {
        "path": f"{record}/{slot}",
        "schema_path": f"{schema}/{slot}",
        "slot_name": slot,
        "column": column,
        "value": value,
        "state": "null"
        if value is None
        else "value"
        if value or xml
        else "empty",
    }


def _record(
    ordinal: int,
    record: str,
    fields: list[dict[str, Any]],
    *,
    parent: str | None = None,
    ending: str | None = None,
) -> dict[str, Any]:
    return {
        "record_ordinal": ordinal,
        "record_id": record,
        "parent_record_id": parent,
        "native_fields": fields,
        "line_ending": ending,
        "interpretation_state": "native_unresolved",
    }


def _csv(payload: bytes) -> Iterator[dict[str, Any]]:
    with io.TextIOWrapper(
        io.BytesIO(payload), encoding="utf-8-sig", newline=""
    ) as stream:
        for ordinal, cells in enumerate(csv.reader(stream, strict=True), 1):
            record = f"/csv/record/{ordinal}"
            yield _record(
                ordinal,
                record,
                [
                    _field(
                        record, "/csv/record", f"column/{column}", value, column
                    )
                    for column, value in enumerate(cells, 1)
                ],
            )


def _pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _xml(payload: bytes) -> Iterator[dict[str, Any]]:
    stack: list[tuple[str, str, Counter[str]]] = []
    ordinal = 0
    for event, element, parent in iter_xml_events(
        payload,
        policy=ParserPolicy(
            max_bytes=MAX_BYTES,
            max_xml_elements=MAX_RECORDS,
            max_xml_text_bytes=MAX_BYTES,
        ),
    ):
        if event == "start":
            name = _pointer(element.tag)
            if stack:
                stack[-1][2][name] += 1
                record, schema = (
                    f"{stack[-1][0]}/{name}/{stack[-1][2][name]}",
                    f"{stack[-1][1]}/{name}",
                )
            else:
                record, schema = f"/{name}/1", f"/{name}"
            stack.append((record, schema, Counter()))
            continue
        record, schema, _ = stack.pop()
        ordinal += 1
        slots = [("text", element.text), ("tail", element.tail)]
        slots.extend(
            ("attributes/" + _pointer(name), value)
            for name, value in sorted(element.attrib.items())
        )
        yield _record(
            ordinal,
            record,
            [
                _field(record, schema, slot, value, xml=True)
                for slot, value in slots
            ],
            parent=stack[-1][0] if stack else None,
        )
        if parent is not None:
            parent.remove(element)
        element.clear()


def _text(payload: bytes) -> Iterator[dict[str, Any]]:
    for ordinal, raw in enumerate(payload.splitlines(keepends=True), 1):
        ending = (
            b"\r\n"
            if raw.endswith(b"\r\n")
            else b"\n"
            if raw.endswith(b"\n")
            else b"\r"
            if raw.endswith(b"\r")
            else b""
        )
        content = raw[: -len(ending)] if ending else raw
        record = f"/text/record/{ordinal}"
        cells = content.decode("utf-8").split("\t")
        yield _record(
            ordinal,
            record,
            [
                _field(
                    record, "/text/record", f"segment/{column}", value, column
                )
                for column, value in enumerate(cells, 1)
            ],
            ending=ending.decode(),
        )


def sidecar_schema(source: BoundSidecar) -> pa.Schema:
    """Typed lexical records; no header selection or numeric/date inference."""
    native = pa.struct([
        pa.field("ordinal", pa.int64(), nullable=False),
        pa.field("field_id", pa.string(), nullable=False),
        *(
            pa.field(name, pa.string(), nullable=False)
            for name in ("path", "schema_path", "slot_name", "state")
        ),
        pa.field("column", pa.int32()),
        pa.field("value", pa.string()),
    ])
    schema = pa.schema([
        pa.field("source_sha256", pa.string(), nullable=False),
        pa.field("acquisition_id", pa.string(), nullable=False),
        pa.field("record_ordinal", pa.int64(), nullable=False),
        pa.field("record_id", pa.string(), nullable=False),
        pa.field("parent_record_id", pa.string()),
        pa.field("native_fields", pa.list_(native), nullable=False),
        pa.field("line_ending", pa.string()),
        pa.field("interpretation_state", pa.string(), nullable=False),
    ])
    metadata = {
        b"schema_name": b"global-medicines-atlas.mbs-sidecar.native-records",
        b"source_binding": _encoded(asdict(source)),
        b"qualification": b"candidate",
        b"conversion": b"none",
        b"header_semantics": b"unqualified",
        b"date_interpretation": b"unqualified",
        b"numeric_interpretation": b"unqualified",
        b"text_segmentation": b"literal-tabs-only",
        b"patient_rates": b"unavailable",
    }
    return schema.with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType] -- Arrow schema metadata stub


def _account(row: dict[str, Any], kind: str, digest: Any) -> None:
    if kind == "text":
        raw = (
            "\t".join(field["value"] for field in row["native_fields"])
            + row["line_ending"]
        ).encode()
        digest.update(len(raw).to_bytes(8, "big") + raw)
        return
    for field in row["native_fields"]:
        value = (
            [row["record_ordinal"], field["column"], field["value"]]
            if kind == "csv"
            else [
                row["record_id"],
                field["slot_name"],
                field["value"],
                field["state"],
            ]
        )
        digest.update(_encoded(value))


def iter_sidecar_batches(
    payload: bytes, source: BoundSidecar, *, rows_per_batch: int = 1024
) -> Iterator[pa.RecordBatch]:
    """Retain all records including header candidates, empty rows and XML nodes.

    Existing source identity and parser limits are verified before output. Full
    exhaustion must match the independent native-layout digest and denominator.
    Discard partial outputs on failure. Encoded batch bounds are not a claim of
    a total resident-memory bound. This creates no rights or admission decision.
    """
    if (
        type(rows_per_batch) is not int
        or not 1 <= rows_per_batch <= MAX_BATCH_ROWS
    ):
        raise ValueError("MBS sidecar batch row bound differs")
    layout = profile_sidecar(payload, source)["layout"]
    if source.format == "text" and not layout["utf8_valid"]:
        raise ValueError("MBS sidecar text encoding is unqualified")
    schema = sidecar_schema(source)
    routes = {"csv": _csv, "xml": _xml, "text": _text}
    records = fields = size = 0
    pending: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    for row in routes[source.format](payload):
        records += 1
        for field in row["native_fields"]:
            field.update({
                "ordinal": fields,
                "field_id": f"{source.sha256}:{field['path']}",
            })
            fields += 1
        row.update({
            "source_sha256": source.sha256,
            "acquisition_id": source.acquisition_id,
        })
        _account(row, source.format, digest)
        row_bytes = len(_encoded(row))
        if row_bytes > MAX_BATCH_BYTES:
            raise ValueError("MBS sidecar record byte bound exceeded")
        if pending and (
            len(pending) >= rows_per_batch or size + row_bytes > MAX_BATCH_BYTES
        ):
            yield pa.RecordBatch.from_pylist(pending, schema=schema)
            pending, size = [], 0
        pending.append(row)
        size += row_bytes
    expected_records = (
        layout["records"]
        if source.format == "csv"
        else layout["elements"]
        if source.format == "xml"
        else layout["native_records"]
    )
    expected_digest = layout.get(
        "native_fields_sha256", layout.get("native_lines_sha256")
    )
    if (
        records != expected_records
        or digest.hexdigest() != expected_digest
        or (source.format != "text" and fields != layout["native_fields"])
    ):
        raise ValueError("MBS sidecar complete native parity differs")
    if pending:
        yield pa.RecordBatch.from_pylist(pending, schema=schema)
