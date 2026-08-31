"""Bounded offline checks of declared MBS profiles, never admission."""

from __future__ import annotations

import json
from typing import cast

import pyarrow as pa

from . import mbs_schema_profile as profiles
from .australian_source_contracts import TargetTable
from .mbs_schema_profile import MbsSchemaProfileDeclaration
from .receipts import SourceReceipt

MAX_BATCH_ROWS = 4096
MAX_BATCH_BYTES = 16 * 1024 * 1024
MAX_METADATA_BYTES = 256 * 1024
MAX_METADATA_ENTRIES = 64


def _flat_object(raw: bytes) -> None:  # ruff: ignore[too-many-branches] - bounded lexical preflight
    """Reject nesting before JSON parsing; strings may contain brackets."""
    if not raw or len(raw) > profiles.MAX_DECLARATION_BYTES:
        raise ValueError
    quoted = escaped = False
    opened = closed = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == ord("\\"):
                escaped = True
            elif byte == ord('"'):
                quoted = False
        elif byte == ord('"'):
            quoted = True
        elif byte == ord("{"):
            if opened:
                raise ValueError
            opened = True
        elif byte == ord("}"):
            if not opened or closed:
                raise ValueError
            closed = True
        elif byte in {ord("["), ord("]")}:
            raise ValueError
    if not opened or not closed or quoted:
        raise ValueError


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def read_mbs_schema_profile(
    batch: pa.RecordBatch,
    receipt: SourceReceipt,
    *,
    table: TargetTable,
    expected_profile: str,
) -> MbsSchemaProfileDeclaration:
    """Check one already-decoded batch against caller-supplied identities.

    Empty batches still require all schema/metadata/receipt bindings. A result
    is only a declaration: it proves neither row completeness nor authenticity,
    qualified source structure, rights, publication or federation admission.
    Inputs are unchanged. No Parquet decoding, filesystem or network is used.

    Raises:
        ValueError: Any bound, declaration or batch identity check fails.
    """
    try:
        return _read(batch, receipt, table, expected_profile)
    except ValueError, TypeError, AttributeError, KeyError, OverflowError:
        raise ValueError("invalid MBS schema profile") from None


def _read(
    batch: object,
    receipt: SourceReceipt,
    table: TargetTable,
    expected_profile: object,
) -> MbsSchemaProfileDeclaration:
    if type(expected_profile) is not str:
        raise TypeError
    if not isinstance(batch, pa.RecordBatch):
        raise TypeError
    if batch.num_rows > MAX_BATCH_ROWS or batch.nbytes > MAX_BATCH_BYTES:
        raise ValueError
    metadata = dict(batch.schema.metadata or {})
    if (
        len(metadata) > MAX_METADATA_ENTRIES
        or sum(len(key) + len(value) for key, value in metadata.items())
        > MAX_METADATA_BYTES
    ):
        raise ValueError
    namespaces = [
        key for key in metadata if key.startswith(b"gma.mbs.schema_profile.")
    ]
    if namespaces != [profiles.DECLARATION_METADATA_KEY]:
        raise ValueError
    raw = metadata.pop(profiles.DECLARATION_METADATA_KEY)
    _flat_object(raw)
    parsed: object = json.loads(raw, object_pairs_hook=_unique)
    if not isinstance(parsed, dict):
        raise TypeError
    document = cast("dict[str, object]", parsed)
    if (
        set(document) != set(MbsSchemaProfileDeclaration.model_fields)
        or type(document.get("schema_version")) is not int
    ):
        raise ValueError
    declaration = MbsSchemaProfileDeclaration.model_validate(document)
    if declaration.comparison_schema_profile != expected_profile:
        raise ValueError
    receipt = SourceReceipt.model_validate(receipt.model_dump(warnings=False))
    # Share producer checks without altering the existing producer API.
    encoded = profiles._encoded_declaration(declaration, receipt)  # pyright: ignore[reportPrivateUsage]
    profiles._annotate(  # pyright: ignore[reportPrivateUsage]
        batch.replace_schema_metadata(metadata), table, declaration, encoded
    )
    return declaration
