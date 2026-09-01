"""Fail-closed aggregation for independent historical PBS projection shards."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, cast

PROJECTIONS = ("native", "domain", "entities", "references", "dates")
PHASE_PROJECTIONS = ("native", "domain", "entities", "dates")
DATASET = "edithatogo/australian-pbs-source-archive"
REVISION = "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7"
ANONYMOUS_PUBLIC_CHECKS = 2
MAX_REFERENCE_SHARDS = 64
_SHARED_REPORT_KEYS = (
    "workflow_commit",
    "dataset",
    "revision",
    "manifest_sha256",
    "source_receipt_file_sha256",
    "archive_path",
    "member_path",
)
_SHARED_QUALIFICATION_KEYS = (
    "source_id",
    "parent_receipt_sha256",
    "archive_sha256",
    "member_sha256",
    "member_binding_sha256",
    "native_fields",
    "elements",
    "native_digest",
    "date_profile",
    "domain_semantics_qualified",
)


def _invalid() -> ValueError:
    return ValueError("PBS qualification shards are incomplete or inconsistent")


def _projection(
    report: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    qualification = report.get("qualification")
    if not isinstance(qualification, dict):
        raise _invalid()
    qualification = cast("dict[str, Any]", qualification)
    name = qualification.get("projection_shard")
    projections = qualification.get("projections")
    if not all((
        name in PROJECTIONS,
        report.get("status") == "passed",
        report.get("publication_performed") is False,
        qualification.get("publication_performed") is False,
        isinstance(projections, dict),
        report.get("anonymous_public_checks") == ANONYMOUS_PUBLIC_CHECKS,
    )) or not isinstance(projections, dict):
        raise _invalid()
    projections = cast("dict[str, Any]", projections)
    if tuple(projections) != (name,):
        raise _invalid()
    projection = projections[cast("str", name)]
    if not isinstance(projection, dict):
        raise _invalid()
    return cast("str", name), qualification, cast("dict[str, Any]", projection)


def aggregate_shards(  # ruff: ignore[too-many-branches]
    reports: object, *, expected_commit: str | None = None
) -> dict[str, Any]:
    """Bind phase receipts and gap-free reference windows to one identity."""
    if not isinstance(reports, list):
        raise _invalid()
    values = cast("list[object]", reports)
    if len(values) < len(PROJECTIONS):
        raise _invalid()
    phases: dict[str, dict[str, Any]] = {}
    references: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    normalized: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for value in values:
        if not isinstance(value, dict):
            raise _invalid()
        report = cast("dict[str, Any]", value)
        name, qualification, projection = _projection(report)
        normalized.append((report, qualification))
        if name == "references":
            references.append((report, qualification, projection))
        elif name in phases:
            raise _invalid()
        else:
            phases[name] = report
    if tuple(sorted(phases, key=PHASE_PROJECTIONS.index)) != PHASE_PROJECTIONS:
        raise _invalid()
    first, first_qualification = normalized[0]
    if (
        first.get("dataset") != DATASET
        or first.get("revision") != REVISION
        or (
            expected_commit is not None
            and first.get("workflow_commit") != expected_commit
        )
    ):
        raise _invalid()
    for report, qualification in normalized:
        if any(
            report.get(key) != first.get(key) for key in _SHARED_REPORT_KEYS
        ):
            raise _invalid()
        if any(
            qualification.get(key) != first_qualification.get(key)
            for key in _SHARED_QUALIFICATION_KEYS
        ):
            raise _invalid()
    phase_outputs: dict[str, dict[str, Any]] = {}
    for name, report in phases.items():
        _, qualification, projection = _projection(report)
        expected_rows = qualification.get(
            "native_fields" if name in {"native", "domain"} else "elements"
        )
        if (
            projection.get("rows") != expected_rows
            or projection.get("native_fields")
            != qualification.get("native_fields")
            or projection.get("native_digest")
            != qualification.get("native_digest")
            or projection.get("parquet_roundtrip_verified") is not True
        ):
            raise _invalid()
        phase_outputs[name] = projection
    reference_output, reference_windows = _aggregate_references(
        references, first_qualification
    )
    projections = {
        name: reference_output if name == "references" else phase_outputs[name]
        for name in PROJECTIONS
    }
    qualification = {
        key: first_qualification[key]
        for key in (
            "schema_version",
            "qualification",
            *_SHARED_QUALIFICATION_KEYS,
        )
    }
    qualification.update({
        "projections": projections,
        "reference_windows": reference_windows,
        "publication_performed": False,
    })
    return {
        "schema_version": 1,
        "status": "passed",
        **{key: first[key] for key in _SHARED_REPORT_KEYS},
        "projection_shards": list(PROJECTIONS),
        "shard_run_ids": [report.get("run_id") for report, _ in normalized],
        "qualification": qualification,
        "publication_performed": False,
    }


def _aggregate_references(  # ruff: ignore[too-many-branches]
    references: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
    shared: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not references:
        raise _invalid()
    windows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for _report, qualification, projection in references:
        window = qualification.get("reference_window")
        if not isinstance(window, dict):
            raise _invalid()
        window = cast("dict[str, Any]", window)
        digest = projection.get("native_digest")
        if (
            projection.get("native_digest_scope") != "ordered-window"
            or projection.get("parquet_roundtrip_verified") is not True
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            raise _invalid()
        windows.append((window, projection))
    windows.sort(key=lambda item: item[0].get("index", -1))
    count = len(windows)
    total = shared.get("elements")
    if type(total) is not int or total < 1 or count > MAX_REFERENCE_SHARDS:
        raise _invalid()
    cursor = native_fields = 0
    digest_manifest: list[dict[str, Any]] = []
    numeric_totals: dict[str, int] = {}
    for index, (window, projection) in enumerate(windows):
        start = total * index // count
        stop = total * (index + 1) // count
        if (
            window
            != {
                "index": index,
                "count": count,
                "start_row": start,
                "stop_row": stop,
                "total_rows": total,
            }
            or cursor != start
        ):
            raise _invalid()
        cursor = stop
        if projection.get("rows") != stop - start:
            raise _invalid()
        fields = projection.get("native_fields")
        if type(fields) is not int or fields < 0:
            raise _invalid()
        native_fields += fields
        for key, value in projection.items():
            if key in {"rows", "native_fields"}:
                continue
            if key.endswith("_rows") and type(value) is int:
                numeric_totals[key] = numeric_totals.get(key, 0) + value
        digest_manifest.append({
            "start_row": start,
            "stop_row": stop,
            "native_digest": projection["native_digest"],
        })
    if cursor != total or native_fields != shared.get("native_fields"):
        raise _invalid()
    manifest_bytes = json.dumps(
        digest_manifest, sort_keys=True, separators=(",", ":")
    ).encode()
    return (
        {
            "rows": total,
            "native_fields": native_fields,
            **numeric_totals,
            "native_digest": shared["native_digest"],
            "native_digest_scope": "source-denominator-plus-ordered-windows",
            "reference_window_digest_sha256": hashlib.sha256(
                manifest_bytes
            ).hexdigest(),
            "parquet_roundtrip_verified": True,
        },
        digest_manifest,
    )
