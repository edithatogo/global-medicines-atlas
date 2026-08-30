"""Historical reference/date candidates with mandatory original lineage."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyarrow as pa

# Private transforms are intentionally not public stream-admission APIs.
from .pbs_dates import _date_batches  # pyright: ignore[reportPrivateUsage]
from .pbs_historical_projections import iter_pbs_historical_entity_batches
from .pbs_member_identity import PbsXmlMemberBinding
from .pbs_references import (
    _reference_batches,  # pyright: ignore[reportPrivateUsage]
)
from .receipts import SourceReceipt


def iter_pbs_historical_reference_batches(
    archive_payload: bytes,
    member_payload: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    *,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Annotate literal references in two fully validated historical passes.

    Both streams are constructed here from the same four inputs. Callers cannot
    supply an entity factory or unvalidated stream. Each pass revalidates the
    original parent/archive/member/binding; schema plus full identity metadata
    must agree across passes. Original source identity and all top-level/nested
    lineage survive. Index/row/encoded-byte bounds and literal unresolved or
    ambiguous semantics are unchanged; no vocabulary resolution or admission.
    Discard partial output after any error, including later identity drift.
    """
    yield from _reference_batches(
        iter_pbs_historical_entity_batches(
            archive_payload,
            member_payload,
            parent,
            binding,
            rows_per_batch=rows_per_batch,
        ),
        iter_pbs_historical_entity_batches(
            archive_payload,
            member_payload,
            parent,
            binding,
            rows_per_batch=rows_per_batch,
        ),
        rows_per_batch,
    )


def iter_pbs_historical_date_batches(
    archive_payload: bytes,
    member_payload: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    *,
    date_profile: str | None = None,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Preserve historical date slots with conversion unselected by default.

    Mandatory historical validation precedes output. The opt-in calendar-date
    candidate profile does not qualify a real source era or infer current status,
    precedence, intervals, timezone, entitlement or admission. Every native
    field and original parent/archive/member binding remains intact. Shared
    XML/ZIP/entity and encoded-output bounds apply, not total resident memory.
    Discard partial output after errors; no acquisition or publication occurs.
    """
    yield from _date_batches(
        iter_pbs_historical_entity_batches(
            archive_payload,
            member_payload,
            parent,
            binding,
            rows_per_batch=rows_per_batch,
        ),
        date_profile,
        rows_per_batch,
    )
