"""Fail-closed aggregation for independent historical PBS projection shards."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, cast

from .pbs_hosted_qualification import (
    ARCHIVE,
    DATASET,
    MANIFEST,
    MEMBER,
    RECEIPT,
    REVISION,
    PinnedFile,
)

PROJECTIONS = ("native", "domain", "entities", "references", "dates")
PHASE_PROJECTIONS = ("native", "domain", "entities", "dates")
ANONYMOUS_PUBLIC_CHECKS = 2
MAX_REFERENCE_SHARDS = 64
PARENT_RECEIPT_SHA256 = (
    "3a8dfd676043f39549bff8c8f966814bca70a59245a0038ea287d44e049ff33d"
)
MEMBER_BINDING_SHA256 = (
    "5bc111736f76cee651a73be99b37f5921b2924e53428b0c0f8ae45964943c4f2"
)
_COUNTER_KEYS = (
    "rows",
    "native_fields",
    "unmapped_rows",
    "duplicate_literal_rows",
    "ambiguous_reference_rows",
    "unresolved_reference_rows",
    "date_unselected_rows",
)
_PROJECTION_KEYS = (
    *_COUNTER_KEYS,
    "native_digest",
    "parquet_roundtrip_verified",
)
_REFERENCE_PROJECTION_KEYS = (*_PROJECTION_KEYS, "native_digest_scope")
_SHARED_REPORT_KEYS = (
    "workflow_commit",
    "dataset",
    "revision",
    "manifest_sha256",
    "source_receipt_file_sha256",
    "archive_path",
    "member_path",
    "member_retrieval",
)


def _sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
    )


def _valid_projection_schema(name: str, projection: dict[str, Any]) -> bool:
    expected = (
        _REFERENCE_PROJECTION_KEYS if name == "references" else _PROJECTION_KEYS
    )
    return (
        tuple(projection) == expected
        and all(
            type(projection[key]) is int and projection[key] >= 0
            for key in _COUNTER_KEYS
        )
        and _sha256(projection["native_digest"])
        and projection["parquet_roundtrip_verified"] is True
        and (
            name != "references"
            or projection["native_digest_scope"] == "ordered-window"
        )
    )


def _valid_public_objects(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    objects = cast("dict[str, object]", value)
    if tuple(objects) != (
        "manifest",
        "source_receipt",
        "archive",
        "member",
    ):
        return False
    pins: dict[str, PinnedFile] = {
        "manifest": MANIFEST,
        "source_receipt": RECEIPT,
        "archive": ARCHIVE,
        "member": MEMBER,
    }
    return all(
        objects.get(name)
        == {
            "path": pin.path,
            "sha256": pin.sha256,
            "byte_count": pin.byte_count,
        }
        for name, pin in pins.items()
    )


def _valid_identity(
    report: dict[str, Any], qualification: dict[str, Any]
) -> bool:
    expected_report = {
        "dataset": DATASET,
        "revision": REVISION,
        "manifest_sha256": MANIFEST.sha256,
        "source_receipt_file_sha256": RECEIPT.sha256,
        "archive_path": ARCHIVE.path,
        "member_path": MEMBER.path,
        "member_retrieval": "extracted-from-verified-archive",
    }
    expected_qualification = {
        "schema_version": 1,
        "qualification": "structural_storage_candidate_only",
        "source_id": "au-pbs-historical-xml",
        "parent_receipt_sha256": PARENT_RECEIPT_SHA256,
        "archive_sha256": ARCHIVE.sha256,
        "member_sha256": MEMBER.sha256,
        "member_binding_sha256": MEMBER_BINDING_SHA256,
        "date_profile": "not-selected",
        "domain_semantics_qualified": False,
    }
    native_fields = qualification.get("native_fields")
    elements = qualification.get("elements")
    counters_valid = (
        type(native_fields) is int
        and native_fields > 0
        and type(elements) is int
        and elements > 0
    )
    return all((
        all(report.get(key) == value for key, value in expected_report.items()),
        all(
            qualification.get(key) == value
            for key, value in expected_qualification.items()
        ),
        _valid_public_objects(report.get("public_objects")),
        isinstance(report.get("workflow_commit"), str),
        re.fullmatch(r"[0-9a-f]{40}", report["workflow_commit"]) is not None,
        type(report.get("anonymous_public_checks")) is int,
        report.get("anonymous_public_checks") == ANONYMOUS_PUBLIC_CHECKS,
        counters_valid,
        _sha256(qualification.get("native_digest")),
    ))


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
    if not isinstance(projection, dict) or not _valid_projection_schema(
        cast("str", name), cast("dict[str, Any]", projection)
    ):
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
    if not _valid_identity(first, first_qualification) or (
        expected_commit is not None
        and first.get("workflow_commit") != expected_commit
    ):
        raise _invalid()
    for report, qualification in normalized:
        if not _valid_public_objects(report.get("public_objects")):
            raise _invalid()
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


def _aggregate_references(  # ruff: ignore[too-many-locals]
    references: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
    shared: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not references:
        raise _invalid()
    windows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    preparation_manifest_sha256: str | None = None
    for _report, qualification, projection in references:
        window = qualification.get("reference_window")
        if not isinstance(window, dict):
            raise _invalid()
        window = cast("dict[str, Any]", window)
        digest = projection.get("native_digest")
        manifest_digest = qualification.get("preparation_manifest_sha256")
        expected_projection = qualification.get("expected_reference_projection")
        if not isinstance(expected_projection, dict):
            raise _invalid()
        expected_projection = cast("dict[str, Any]", expected_projection)
        checks = (
            _sha256(digest),
            _sha256(manifest_digest),
            not any(
                projection.get(key) != expected_projection.get(key)
                for key in ("rows", "native_fields", "native_digest")
            ),
            not (
                preparation_manifest_sha256 is not None
                and manifest_digest != preparation_manifest_sha256
            ),
        )
        if not all(checks):
            raise _invalid()
        preparation_manifest_sha256 = cast("str", manifest_digest)
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
        for key in _COUNTER_KEYS[2:]:
            numeric_totals[key] = numeric_totals.get(key, 0) + projection[key]
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
            "preparation_manifest_sha256": preparation_manifest_sha256,
            "parquet_roundtrip_verified": True,
        },
        digest_manifest,
    )
