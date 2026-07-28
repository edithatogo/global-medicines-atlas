"""Shared receipt validation for first-party source adapters."""

from __future__ import annotations

from ..models import Provenance
from ..receipts import SourceReceipt


def provenance_from_receipt(
    receipt: SourceReceipt,
    payload: bytes,
    *,
    source_id: str,
    jurisdiction: str,
    transformation: str,
) -> Provenance:
    """Validate source bytes and return canonical provenance."""
    if receipt.source.source_id != source_id:
        raise ValueError(f"Expected source_id {source_id!r}")
    if receipt.source.jurisdiction != jurisdiction:
        raise ValueError(f"Expected jurisdiction {jurisdiction!r}")
    if not receipt.payload.matches(payload):
        raise ValueError("Receipt payload evidence does not match source bytes")
    return Provenance(
        source_id=receipt.source.source_id,
        source_uri=str(receipt.retrieval.uri),
        retrieved_at=receipt.retrieval.retrieved_at,
        effective_at=receipt.effective_from,
        source_sha256=receipt.payload.sha256,
        source_version=receipt.source.catalog_version,
        transformation=transformation,
    )
