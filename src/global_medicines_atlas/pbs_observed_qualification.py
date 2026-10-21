"""Exhaustive native restore and role coverage for observed PBS candidates."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator
from typing import Any, cast

import pyarrow as pa
import pyarrow.compute as pc

from .pbs_historical_qualification import (
    _denominator,  # pyright: ignore[reportPrivateUsage] -- shared independent source oracle
    _projection,  # pyright: ignore[reportPrivateUsage] -- shared exhaustive storage/lineage verifier
)
from .pbs_member_identity import (
    PbsXmlMemberBinding,
    validate_pbs_xml_member_binding,
)
from .pbs_observed_domain import (
    INVENTORY_SHA256,
    ObservedDomainProfile,
    iter_observed_historical_value_batches,
)
from .receipts import SourceReceipt


def qualify_observed_values(
    archive: bytes,
    member: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    profile: ObservedDomainProfile,
    *,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, Any]:
    """Require every source slot, exact Parquet/metadata and inventory role counts.

    Output is aggregate candidate evidence only. Native preservation and source
    roles establish no payment meaning, reference resolution or admission.
    """
    binding = validate_pbs_xml_member_binding(binding, archive, member, parent)
    denominator = _denominator(member, progress)
    if denominator["native_fields"] != profile.native_fields:
        raise ValueError("PBS observed profile native denominator differs")
    fields: Counter[str] = Counter()
    entities: Counter[str] = Counter()

    def batches() -> Iterator[pa.RecordBatch]:
        for batch in iter_observed_historical_value_batches(
            archive, member, parent, binding, profile, rows_per_batch=4096
        ):
            roles = cast(
                "list[str]",
                cast(
                    "pa.StringArray", batch.column("mapping_target")
                ).to_pylist(),
            )
            lengths = cast(
                "list[int]",
                pc.list_value_length(
                    cast("pa.Array[Any]", batch.column("native_fields"))
                ).to_pylist(),
            )
            for role, count in zip(roles, lengths, strict=True):
                fields[role] += count
                entities[role] += 1
            yield batch

    projection = _projection(
        batches(),
        binding,
        denominator,
        nested=True,
        progress=progress,
        phase="values",
    )
    if dict(fields) != dict(profile.field_counts):
        raise ValueError("PBS observed profile role coverage differs")
    return {
        "schema_version": 1,
        "qualification": "observed_structural_value_candidates_only",
        "mapping_profile": "pbs-observed-april-2026-structural-v1",
        "inventory_sha256": INVENTORY_SHA256,
        "member_binding_sha256": binding.digest(),
        "native_fields": denominator["native_fields"],
        "native_digest": denominator["native_digest"],
        "role_field_counts": dict(sorted(fields.items())),
        "role_entity_counts": dict(sorted(entities.items())),
        "values": projection,
        "domain_semantics_qualified": False,
        "new_sources": 0,
        "new_admissions": 0,
        "publications": 0,
    }
