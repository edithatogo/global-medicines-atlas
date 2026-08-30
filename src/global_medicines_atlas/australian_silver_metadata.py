"""Credential-safe provenance metadata shared by Australian projections."""

from .bronze_acquisition_metadata import redact_retrieval_location
from .receipts import SourceReceipt


def receipt_projection_metadata(receipt: SourceReceipt) -> dict[bytes, bytes]:
    """Retain exact receipt identity, never the credential-bearing document."""
    digest = receipt.digest()
    return {
        b"source_receipt_sha256": digest.encode(),
        b"source_receipt_locator": f"sha256:{digest}".encode(),
        b"source_uri": redact_retrieval_location(
            str(receipt.retrieval.uri)
        ).encode(),
        b"retrieved_at": receipt.retrieval.retrieved_at.isoformat().encode(),
        b"rights_state": receipt.rights_state.value.encode(),
        b"evidence_class": receipt.evidence_class.value.encode(),
    }
