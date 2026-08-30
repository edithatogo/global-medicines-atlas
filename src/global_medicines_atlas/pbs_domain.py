"""Conservative PBS fixture-established structural table destinations."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pyarrow as pa

from .adapters.au_pbs import (
    DCTERMS_NAMESPACE,
    DOCBOOK_NAMESPACE,
    PBS_V3_NAMESPACE,
)
from .pbs_silver import iter_pbs_silver_batches
from .receipts import SourceReceipt

_PBS = f"{{{PBS_V3_NAMESPACE}}}"
_DB = f"{{{DOCBOOK_NAMESPACE}}}"
_DCT = f"{{{DCTERMS_NAMESPACE}}}"
_ADDITIONS = (
    pa.field("mapping_target", pa.string(), nullable=False),
    pa.field("mapping_status", pa.string(), nullable=False),
    pa.field("item_occurrence_id", pa.string()),
)


def _item_target(suffix: tuple[str, ...]) -> str:
    if not suffix:
        return "items"
    if suffix == (_PBS + "block-container",) or (
        suffix[:2] == (_PBS + "block-container", _DB + "para")
        and all(name.startswith(_DB) for name in suffix[2:])
    ):
        return "presentations"
    if suffix == (_PBS + "restrictions",) or (
        suffix[:2] == (_PBS + "restrictions", _PBS + "restriction")
        and all(name.startswith(_DB) for name in suffix[2:])
    ):
        return "restrictions"
    reference = (
        _PBS + "drug-references-list",
        _PBS + "mp-reference",
        _PBS + "code",
    )
    if len(suffix) <= len(reference) and suffix == reference[: len(suffix)]:
        return "amt_references"
    if suffix in {
        (_PBS + "classification",),
        (_PBS + "classification", _PBS + "code"),
    }:
        return "classifications"
    return "unmapped"


def _mapping(row: dict[str, Any]) -> dict[str, str | None]:
    # These paths come only from the existing native inventory, not a caller.
    # Split before unescaping: namespace URI slashes are pointer-escaped.
    parts = row["record_id"].split("/")
    names = tuple(
        part.replace("~1", "/").replace("~0", "~") for part in parts[1::2]
    )
    target = "unmapped"
    item_index: int | None = None
    if names[:2] == (_PBS + "schedule", _PBS + "pharmaceutical-item"):
        item_index = 1
    elif names[:3] == (
        _PBS + "root",
        _PBS + "pharmaceutical-items-list",
        _PBS + "pharmaceutical-item",
    ):
        item_index = 2
    item_id = None
    if item_index is not None:
        anchor = "/".join(parts[: 2 * item_index + 3])
        item_id = f"{row['source_sha256']}:{anchor}"
        target = _item_target(names[item_index + 1 :])
    elif len(names) == 1 or names in {
        (_PBS + "root", _PBS + "schedule"),
        (_PBS + "root", _PBS + "info"),
        (_PBS + "root", _PBS + "info", _DCT + "valid"),
    }:
        target = "schedules"
    elif names == (_PBS + "root", _PBS + "pharmaceutical-items-list"):
        target = "items"
    return {
        "mapping_target": target,
        "mapping_status": "unmapped"
        if target == "unmapped"
        else "source_structure",
        "item_occurrence_id": item_id,
    }


def iter_pbs_domain_batches(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Annotate all native slots with structural families and item lineage.

    No slot is removed or converted. Table destinations describe source structure,
    not eligibility, regulatory approval or vocabulary meaning. Classification
    codes retain their native type attributes; this API does not label every code
    ATC. Unrecognised paths, including price fields not covered by the existing
    adapter fixture contract, remain unmapped. Bounded parsing/batching and safe
    B1/B2 metadata are inherited from the native candidate layer.
    """
    yield from _domain_batches(
        iter_pbs_silver_batches(payload, receipt, rows_per_batch=rows_per_batch)
    )


def _domain_batches(
    batches: Iterator[pa.RecordBatch],
) -> Iterator[pa.RecordBatch]:
    """Map an internally validated native stream without changing its lineage."""
    for batch in batches:
        schema = batch.schema
        for field in _ADDITIONS:
            schema = schema.append(field)  # pyright: ignore[reportUnknownMemberType]
        metadata = dict(schema.metadata or {})
        metadata.update({
            b"schema_name": b"global-medicines-atlas.pbs-silver.domain-fields",
            b"mapping_profile": b"pbs-adapter-structural-v1",
        })
        schema = schema.with_metadata(metadata)  # pyright: ignore[reportUnknownMemberType]
        rows = [{**row, **_mapping(row)} for row in batch.to_pylist()]
        yield pa.RecordBatch.from_pylist(rows, schema=schema)
