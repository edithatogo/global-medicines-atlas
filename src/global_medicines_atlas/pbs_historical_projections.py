"""Historical PBS structural candidates over mandatory validated lineage."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pyarrow as pa

# Internal transforms are deliberately not public batch-admission APIs.
from .pbs_domain import _domain_batches  # pyright: ignore[reportPrivateUsage]
from .pbs_entities import _entity_batches  # pyright: ignore[reportPrivateUsage]
from .pbs_historical_silver import iter_pbs_historical_silver_batches
from .pbs_member_identity import PbsXmlMemberBinding
from .receipts import SourceReceipt


def iter_pbs_historical_domain_batches(
    archive_payload: bytes,
    member_payload: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    *,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Map historical native slots only after full archive/member validation.

    Retain all native values, unknowns and binding columns. Structural families
    use the same candidate profile as ordinary PBS, without aliasing sources,
    fabricating receipts or qualifying source eras. Native XML/ZIP and encoded
    row bounds apply; mapping adds a bounded number of path-sized strings.
    This is not a bound on total resident memory. Discard partial output after
    errors; no acquisition, publication, interpretation or admission occurs.
    """
    yield from _domain_batches(
        iter_pbs_historical_silver_batches(
            archive_payload,
            member_payload,
            parent,
            binding,
            rows_per_batch=rows_per_batch,
        )
    )


def iter_pbs_historical_entity_batches(
    archive_payload: bytes,
    member_payload: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    *,
    rows_per_batch: int = 1024,
) -> Iterator[pa.RecordBatch]:
    """Group validated historical occurrences with complete nested lineage.

    Parent B1, archive B2, member and binding identities remain both top-level
    columns and intact native fields; safe metadata preserves the full binding.
    Duplicate IDs, empty elements, unknown namespaces and mixed text survive.
    Shared entity field/encoded-byte and output row/encoded-byte bounds apply,
    in addition to historical native bounds. No date profile is selected.
    This candidate route is not real-corpus qualification or public delivery.
    """
    yield from _entity_batches(
        iter_pbs_historical_domain_batches(
            archive_payload,
            member_payload,
            parent,
            binding,
            rows_per_batch=rows_per_batch,
        ),
        rows_per_batch,
    )
