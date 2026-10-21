"""Bounded PBS native schema-path counts, without source values or role claims."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from typing import Any

from .pbs_member_identity import (
    PbsXmlMemberBinding,
    validate_pbs_xml_member_binding,
)
from .pbs_xml_slots import iter_pbs_xml_slots
from .receipts import SourceReceipt

MAX_SCHEMA_PATHS = 4096
MAX_SCHEMA_PATH_BYTES = 4096
MAX_INVENTORY_BYTES = 1024 * 1024
CHECKPOINT_FIELDS = 65536


def profile_schema_paths(
    archive: bytes,
    member: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    *,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, Any]:
    """Count the full source slot denominator by namespace-preserving schema path.

    Paths are constructed from expanded element/attribute names and text/tail
    slot labels by the source parser; occurrence numbers and values are omitted.
    Exceeding a limit rejects the entire inventory rather than truncating it.
    """
    binding = validate_pbs_xml_member_binding(binding, archive, member, parent)
    paths: dict[str, Counter[str]] = {}
    fields = 0
    for slot in iter_pbs_xml_slots(member):
        path = slot.schema_path
        if len(path.encode()) > MAX_SCHEMA_PATH_BYTES:
            raise ValueError("PBS schema inventory path byte limit exceeded")
        if path not in paths:
            if len(paths) >= MAX_SCHEMA_PATHS:
                raise ValueError(
                    "PBS schema inventory path count limit exceeded"
                )
            paths[path] = Counter()
        paths[path]["null" if slot.value is None else "value"] += 1
        fields += 1
        if progress is not None and fields % CHECKPOINT_FIELDS == 0:
            progress("schema-inventory", 0, fields)
    report = {
        "schema_id": "global-medicines-atlas.pbs-native-schema-path-inventory",
        "schema_version": 1,
        "parent_receipt_sha256": parent.digest(),
        "archive_sha256": binding.archive_payload.sha256,
        "member_sha256": binding.member_payload.sha256,
        "member_binding_sha256": binding.digest(),
        "member_path": binding.member_path,
        "native_fields": fields,
        "unique_schema_paths": len(paths),
        "paths": [
            {
                "schema_path": path,
                "native_fields": sum(counts.values()),
                "null_fields": counts["null"],
                "value_fields": counts["value"],
            }
            for path, counts in sorted(paths.items())
        ],
        "native_values_emitted": False,
        "domain_semantics_qualified": False,
        "new_sources": 0,
        "new_admissions": 0,
        "publications": 0,
    }
    if (
        len(json.dumps(report, sort_keys=True, separators=(",", ":")).encode())
        > MAX_INVENTORY_BYTES
    ):
        raise ValueError("PBS schema inventory aggregate byte limit exceeded")
    if progress is not None:
        progress("schema-inventory", 0, fields)
    return report
