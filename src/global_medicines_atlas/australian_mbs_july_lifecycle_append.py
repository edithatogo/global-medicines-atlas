"""Exact reviewed contract for the four existing July MBS lifecycle rows."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from .mbs_historical_lifecycle import (
    append_manifest_rows,
    build_historical_mbs_lifecycle,
)

CONTRACT_PATH = (
    "quality/qualifications/"
    "australian-m112-july-metadata-append-contract-20261018.json"
)
SCHEMA_PATH = "schemas/australian-m112-july-metadata-append-contract-v1.json"
READBACK_PATH = (
    "quality/qualifications/"
    "australian-mbs-july-source-sidecar-readback-20261018.json"
)
AUTHORIZATION_PATH = "quality/qualifications/australian-mbs-harvest-publication-authorization.json"
M112_REPORT_PATH = (
    "quality/qualifications/"
    "australian-m112-per-object-gate-reconciliation-20261018.json"
)
EXPECTED_JULY_OBJECT_COUNT = 4


def sha256_bytes(payload: bytes) -> str:
    """Return a lowercase SHA-256 digest."""
    return hashlib.sha256(payload).hexdigest()


def _read_json(payload: bytes, label: str) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object")
    return cast("dict[str, Any]", value)


def _objects(document: dict[str, Any], label: str) -> list[dict[str, Any]]:
    rows = document.get("objects")
    if not isinstance(rows, list):
        raise TypeError(f"{label} must contain an object list")
    result: list[dict[str, Any]] = []
    for row in cast("list[Any]", rows):
        if not isinstance(row, dict):
            raise TypeError(f"{label} contains a non-object row")
        result.append(cast("dict[str, Any]", row))
    return result


def _validate_parent_readback(
    contract: dict[str, Any], readback: dict[str, Any]
) -> None:
    manifest = readback.get("manifest")
    boundaries = readback.get("boundaries")
    if not isinstance(manifest, dict) or not isinstance(boundaries, dict):
        raise TypeError("source readback is missing manifest or boundaries")
    manifest = cast("dict[str, Any]", manifest)
    boundaries = cast("dict[str, Any]", boundaries)
    if readback.get("dataset") != contract["dataset"]:
        raise ValueError("source readback dataset differs")
    if readback.get("revision") != contract["expected_parent_revision"]:
        raise ValueError("source readback revision differs")
    if manifest.get("sha256") != contract["expected_parent_manifest_sha256"]:
        raise ValueError("source readback manifest digest differs")
    if manifest.get("file_count") != contract["expected_parent_file_count"]:
        raise ValueError("source readback manifest count differs")
    if boundaries.get("metadata_only") is not True:
        raise ValueError("source readback is not metadata-only")
    if boundaries.get("raw_payload_bytes_read") is not False:
        raise ValueError("source readback claims raw payload access")


def _validate_object_binding(
    item: dict[str, Any],
    observed: Any,
    report_row: Any,
) -> None:
    if not isinstance(observed, dict) or not isinstance(report_row, dict):
        raise TypeError("M-112 July object is missing from evidence")
    observed = cast("dict[str, Any]", observed)
    report_row = cast("dict[str, Any]", report_row)
    identity = report_row.get("identity")
    sidecar = observed.get("sidecar")
    if not isinstance(identity, dict) or not isinstance(sidecar, dict):
        raise TypeError("M-112 July object evidence has no identity")
    identity = cast("dict[str, Any]", identity)
    sidecar = cast("dict[str, Any]", sidecar)
    _validate_gate_identity(item, identity, report_row)
    _validate_sidecar_identity(item, observed, sidecar)


def _validate_gate_identity(
    item: dict[str, Any], identity: dict[str, Any], report_row: dict[str, Any]
) -> None:
    if report_row.get("approved_denominator_member") is not True:
        raise ValueError("M-112 July object is outside approved denominator")
    if identity.get("git_blob_oid") != item["git_blob_oid"]:
        raise ValueError("M-112 July payload blob identity differs")
    if identity.get("byte_count") != item["bytes"]:
        raise ValueError("M-112 July payload byte count differs")


def _validate_sidecar_identity(
    item: dict[str, Any],
    observed: dict[str, Any],
    sidecar: dict[str, Any],
) -> None:
    if observed.get("archive_blob_oid") != item["git_blob_oid"]:
        raise ValueError("public tree payload identity differs")
    if observed.get("sidecar_path") != item["sidecar_path"]:
        raise ValueError("public sidecar path differs")
    if observed.get("sidecar_blob_oid") != item["sidecar_blob_oid"]:
        raise ValueError("public sidecar blob identity differs")
    if observed.get("sidecar_sha256") != item["sidecar_sha256"]:
        raise ValueError("public sidecar digest differs")
    if observed.get("sidecar_bytes") != item["sidecar_bytes"]:
        raise ValueError("public sidecar size differs")
    if sidecar.get("archive_path") != item["archive_path"]:
        raise ValueError("sidecar raw path differs")
    if sidecar.get("sha256") != item["sha256"]:
        raise ValueError("sidecar payload digest differs")
    if sidecar.get("byte_count") != item["bytes"]:
        raise ValueError("sidecar payload size differs")
    if sidecar.get("category") != item["category"]:
        raise ValueError("sidecar source category differs")
    if sidecar.get("source_url") != item["source_url"]:
        raise ValueError("sidecar source URL differs")
    if sidecar.get("retrieved_at") != item["retrieved_at"]:
        raise ValueError("sidecar acquisition timestamp differs")


def validate_july_contract(
    contract_bytes: bytes,
    schema_bytes: bytes,
    readback_bytes: bytes,
    authorization_bytes: bytes,
    m112_report_bytes: bytes,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Validate all exact identities and authority before creating payloads."""
    contract = _read_json(contract_bytes, "M-112 July contract")
    schema = _read_json(schema_bytes, "M-112 July contract schema")
    readback = _read_json(readback_bytes, "MBS source sidecar readback")
    authorization = _read_json(authorization_bytes, "MBS authorization")
    report = _read_json(m112_report_bytes, "M-112 gate report")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(  # pyright: ignore[reportUnknownMemberType] -- jsonschema validator types are unannotated
        contract
    )

    for key, data in (
        ("source_sidecar_readback", readback_bytes),
        ("authorization", authorization_bytes),
        ("m112_gate_report", m112_report_bytes),
    ):
        if sha256_bytes(data) != contract[key]["sha256"]:
            raise ValueError(f"pinned {key} bytes differ")
    _validate_parent_readback(contract, readback)

    if (
        authorization.get("external_publication_authorized") is not True
        or authorization.get("maintainer_asserted_redistribution_permission")
        is not True
        or authorization.get("dataset") != contract["dataset"]
        or "au-mbs" not in authorization.get("allowed_sources", [])
    ):
        raise ValueError("MBS publication authorization no longer applies")

    report_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for row in _objects(report, "M-112 report"):
        dataset = row.get("dataset")
        path = row.get("path")
        if isinstance(dataset, str) and isinstance(path, str):
            report_rows[dataset, path] = row
    readback_rows: dict[str, dict[str, Any]] = {}
    for row in _objects(readback, "sidecar readback"):
        archive_path = row.get("archive_path")
        if isinstance(archive_path, str):
            readback_rows[archive_path] = row
    objects = cast("list[dict[str, Any]]", contract["objects"])
    if (
        len(objects) != EXPECTED_JULY_OBJECT_COUNT
        or len(readback_rows) != EXPECTED_JULY_OBJECT_COUNT
    ):
        raise ValueError("July cohort denominator differs")
    if set(readback_rows) != {item["archive_path"] for item in objects}:
        raise ValueError("sidecar readback contains an unexpected object")
    for item in objects:
        observed = readback_rows.get(item["archive_path"])
        report_row = report_rows.get((
            contract["dataset"],
            item["archive_path"],
        ))
        _validate_object_binding(item, observed, report_row)
    return contract, readback, authorization


def build_july_metadata_additions(
    contract: dict[str, Any],
    readback: dict[str, Any],
    authorization: dict[str, Any],
    *,
    anonymous_digests: dict[str, tuple[str, int]],
    decided_at: datetime,
) -> dict[str, bytes]:
    """Build deterministic B1/B2 metadata only after raw digest checks."""
    contract_objects = cast("list[dict[str, Any]]", contract["objects"])
    rows = {
        row["archive_path"]: row
        for row in _objects(readback, "sidecar readback")
    }
    if set(anonymous_digests) != {
        item["archive_path"] for item in contract_objects
    }:
        raise ValueError("anonymous verification cohort differs")
    additions: dict[str, bytes] = {}
    for item in contract_objects:
        digest, size = anonymous_digests[item["archive_path"]]
        if digest != item["sha256"] or size != item["bytes"]:
            raise ValueError("anonymous payload identity differs")
        row = rows[item["archive_path"]]
        bundle = build_historical_mbs_lifecycle(
            row["sidecar"],
            authorization=authorization,
            authorization_commit=contract["authorization"]["reference_commit"],
            archive_revision=contract["expected_parent_revision"],
            observed_sha256=digest,
            observed_byte_count=size,
            decided_at=decided_at,
        )
        overlap = additions.keys() & bundle.keys()
        if overlap:
            raise ValueError("duplicate lifecycle metadata paths")
        additions.update(bundle)
    return dict(sorted(additions.items()))


def build_updated_manifest(
    manifest_bytes: bytes,
    additions: dict[str, bytes],
    *,
    generated_at: datetime,
    expected_sha256: str,
    expected_file_count: int,
) -> bytes:
    """Verify the pinned manifest then append only the new metadata rows."""
    if sha256_bytes(manifest_bytes) != expected_sha256:
        raise ValueError("parent root manifest digest differs")
    manifest = _read_json(manifest_bytes, "MBS root manifest")
    if manifest.get("file_count") != expected_file_count:
        raise ValueError("parent root manifest file count differs")
    return append_manifest_rows(manifest, additions, generated_at=generated_at)
