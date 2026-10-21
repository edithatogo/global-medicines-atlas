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


def schema_inventory_limits(binding: PbsXmlMemberBinding) -> dict[str, Any]:
    """Keep default limits; scope the larger profile to one retained source."""
    pinned = (
        binding.source.source_id == "au-pbs-historical-xml"
        and binding.source.catalog_version == "2026-04-01"
        and binding.archive_payload.sha256
        == "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20"
        and binding.member_payload.sha256
        == "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
        and binding.member_path == "sch-2026-04-01-r1.xml"
    )
    return {
        "profile": "pbs-april-2026-schema-paths-v2"
        if pinned
        else "pbs-schema-paths-v1",
        "paths": 65536 if pinned else MAX_SCHEMA_PATHS,
        "path_bytes": 16384 if pinned else MAX_SCHEMA_PATH_BYTES,
        "total_path_bytes": 16 * 1024**2,
        "inventory_bytes": 32 * 1024**2 if pinned else MAX_INVENTORY_BYTES,
        "expected_native_fields": 18208758 if pinned else None,
    }


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
    limits = schema_inventory_limits(binding)
    paths: dict[str, Counter[str]] = {}
    fields = total_path_bytes = max_path_bytes = 0
    original_limits_exceeded: set[str] = set()
    for slot in iter_pbs_xml_slots(member):
        path = slot.schema_path
        path_bytes = len(path.encode())
        max_path_bytes = max(max_path_bytes, path_bytes)
        if path_bytes > MAX_SCHEMA_PATH_BYTES:
            original_limits_exceeded.add("path_bytes")
        if path_bytes > limits["path_bytes"]:
            raise ValueError("PBS schema inventory path byte limit exceeded")
        if path not in paths:
            if len(paths) >= limits["paths"]:
                raise ValueError(
                    "PBS schema inventory path count limit exceeded"
                )
            total_path_bytes += path_bytes
            if total_path_bytes > limits["total_path_bytes"]:
                raise ValueError(
                    "PBS schema inventory total path byte limit exceeded"
                )
            paths[path] = Counter()
            if len(paths) > MAX_SCHEMA_PATHS:
                original_limits_exceeded.add("path_count")
        paths[path]["null" if slot.value is None else "value"] += 1
        fields += 1
        if progress is not None and fields % CHECKPOINT_FIELDS == 0:
            progress("schema-inventory", 0, fields)
    if (
        limits["expected_native_fields"] is not None
        and fields != limits["expected_native_fields"]
    ):
        raise ValueError(
            "PBS schema inventory qualified source denominator differs"
        )
    report = {
        "limits": limits,
        "observed_max_path_bytes": max_path_bytes,
        "observed_total_path_bytes": total_path_bytes,
        "original_v1_limits_exceeded": sorted(original_limits_exceeded),
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
        original_limits_exceeded.add("inventory_bytes")
        report["original_v1_limits_exceeded"] = sorted(original_limits_exceeded)
    if (
        len(json.dumps(report, sort_keys=True, separators=(",", ":")).encode())
        > limits["inventory_bytes"]
    ):
        raise ValueError("PBS schema inventory aggregate byte limit exceeded")
    if progress is not None:
        progress("schema-inventory", 0, fields)
    return report
