"""Bounded native BSD/RVG layout metadata without source value disclosure."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from typing import Any

from .mbs_sidecar_inventory import BoundSidecar
from .parser_safety import ParserPolicy, iter_xml_events

MAX_BYTES = 1024 * 1024
MAX_RECORDS = 100000
MAX_COLUMNS = 4096
MAX_PATHS = 4096
MAX_REPORT_BYTES = 256 * 1024


def _encoded(value: Any) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n"
    ).encode()


def _csv(payload: bytes) -> dict[str, Any]:
    digest = hashlib.sha256()
    records = fields = empty = 0
    widths: Counter[int] = Counter()
    with io.TextIOWrapper(
        io.BytesIO(payload), encoding="utf-8-sig", newline=""
    ) as stream:
        for ordinal, row in enumerate(csv.reader(stream, strict=True), 1):
            if ordinal > MAX_RECORDS or len(row) > MAX_COLUMNS:
                raise ValueError(
                    "MBS sidecar CSV record or column bound exceeded"
                )
            records += 1
            widths[len(row)] += 1
            for column, value in enumerate(row, 1):
                digest.update(_encoded([ordinal, column, value]))
                fields += 1
                empty += not value
    return {
        "records": records,
        "native_fields": fields,
        "empty_fields": empty,
        "record_width_counts": dict(sorted(widths.items())),
        "native_fields_sha256": digest.hexdigest(),
        "encoding": "utf-8-sig",
        "header_semantics": "unqualified",
        "first_record_retained": True,
    }


def _pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _xml(payload: bytes) -> dict[str, Any]:
    digest = hashlib.sha256()
    stack: list[tuple[str, str, Counter[str]]] = []
    paths: Counter[str] = Counter()
    elements = fields = nulls = 0
    policy = ParserPolicy(
        max_bytes=MAX_BYTES,
        max_xml_elements=MAX_RECORDS,
        max_xml_text_bytes=MAX_BYTES,
    )
    for event, element, parent in iter_xml_events(payload, policy=policy):
        if event == "start":
            name = _pointer(element.tag)
            if stack:
                stack[-1][2][name] += 1
                record = f"{stack[-1][0]}/{name}/{stack[-1][2][name]}"
                schema = f"{stack[-1][1]}/{name}"
            else:
                record, schema = f"/{name}/1", f"/{name}"
            stack.append((record, schema, Counter()))
            elements += 1
            continue
        record, schema, _ = stack.pop()
        slots = [("text", element.text), ("tail", element.tail)]
        slots.extend(
            ("attributes/" + _pointer(name), value)
            for name, value in sorted(element.attrib.items())
        )
        for slot, value in slots:
            path = f"{schema}/{slot}"
            if path not in paths and len(paths) >= MAX_PATHS:
                raise ValueError("MBS sidecar XML path bound exceeded")
            paths[path] += 1
            fields += 1
            nulls += value is None
            digest.update(
                _encoded([
                    record,
                    slot,
                    value,
                    "null" if value is None else "value",
                ])
            )
        if parent is not None:
            parent.remove(element)
        element.clear()
    return {
        "elements": elements,
        "native_fields": fields,
        "null_fields": nulls,
        "schema_path_counts": dict(sorted(paths.items())),
        "native_fields_sha256": digest.hexdigest(),
        "field_semantics": "unqualified",
    }


def _text(payload: bytes) -> dict[str, Any]:
    endings: Counter[str] = Counter()
    delimiters: Counter[str] = Counter()
    digest = hashlib.sha256()
    count = total = 0
    for line in payload.splitlines(keepends=True):
        count += 1
        if count > MAX_RECORDS:
            raise ValueError("MBS sidecar native line bound exceeded")
        total += len(line)
        ending = (
            "CRLF"
            if line.endswith(b"\r\n")
            else "LF"
            if line.endswith(b"\n")
            else "CR"
            if line.endswith(b"\r")
            else "none"
        )
        endings[ending] += 1
        for name, token in (("tab", b"\t"), ("comma", b","), ("pipe", b"|")):
            delimiters[name] += line.count(token)
        digest.update(len(line).to_bytes(8, "big") + line)
    try:
        payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        utf8 = False
    else:
        utf8 = True
    return {
        "native_records": count,
        "native_line_bytes": total,
        "line_endings": dict(sorted(endings.items())),
        "delimiter_occurrences": dict(sorted(delimiters.items())),
        "native_lines_sha256": digest.hexdigest(),
        "utf8_valid": utf8,
        "column_semantics": "unqualified",
    }


def profile_sidecar(payload: bytes, source: BoundSidecar) -> dict[str, Any]:
    """Inventory all native records; do not select headers, dates or meanings.

    Real source execution belongs on protected exact-main hosted runners.
    Native values contribute only to hashes and counters. A failed limit rejects
    the entire report rather than truncating paths, fields, records or bytes.
    """
    if (
        not 0 < len(payload) <= MAX_BYTES
        or len(payload) != source.byte_count
        or hashlib.sha256(payload).hexdigest() != source.sha256
    ):
        raise ValueError("MBS sidecar payload identity or byte bound differs")
    routes = {"csv": _csv, "xml": _xml, "text": _text}
    if source.format not in routes:
        raise ValueError("MBS sidecar native format unsupported")
    report = {
        "schema_id": "global-medicines-atlas.mbs-sidecar-native-layout",
        "schema_version": 1,
        "source_path": source.source_path,
        "source_sha256": source.sha256,
        "source_bytes": source.byte_count,
        "acquisition_id": source.acquisition_id,
        "original_metadata_sha256": {
            pin.role: pin.sha256 for pin in source.metadata
        },
        "layout": routes[source.format](payload),
        "native_values_emitted": False,
        "typed_output_qualified": False,
        "new_admissions": 0,
        "publications": 0,
    }
    if len(_encoded(report)) > MAX_REPORT_BYTES:
        raise ValueError("MBS sidecar aggregate report bound exceeded")
    return report
