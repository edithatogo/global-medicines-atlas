"""Qualify digest-bound transient PBS inputs within one hosted workflow run."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from .pbs_historical_qualification import qualify_pbs_historical_projections
from .pbs_hosted_qualification import (
    ARCHIVE,
    DATASET,
    MANIFEST,
    MEMBER,
    RECEIPT,
    REVISION,
)
from .pbs_member_identity import (
    PbsXmlMemberBinding,
    validate_pbs_xml_member_binding,
)
from .pbs_reference_shards import qualify_reference_shard
from .receipts import SourceReceipt

PHASES = ("native", "domain", "entities", "dates")


def _context(exact_commit: str, preparation: dict[str, Any]) -> dict[str, str]:
    values = {
        "workflow_commit": os.environ.get("GITHUB_SHA", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
    }
    checks = (
        os.environ.get("GITHUB_REF") == "refs/heads/main",
        re.fullmatch(r"[0-9a-f]{40}", exact_commit) is not None,
        values["workflow_commit"] == exact_commit,
        preparation.get("workflow_commit") == exact_commit,
        preparation.get("preparation_run_id") == values["run_id"],
        preparation.get("preparation_run_attempt") == values["run_attempt"],
    )
    if not all(checks):
        raise ValueError("PBS prepared qualification context changed")
    return values


def _read_manifest(path: Path, purpose: str) -> dict[str, Any]:
    raw: object = json.loads(path.read_bytes())
    if not isinstance(raw, dict):
        raise TypeError("PBS prepared input manifest is invalid")
    manifest = cast("dict[str, Any]", raw)
    if not all((
        manifest.get("schema_version") == 1,
        manifest.get("purpose") == purpose,
        manifest.get("dataset") == DATASET,
        manifest.get("revision") == REVISION,
        manifest.get("publication_performed") is False,
        manifest.get("evidence_truth") is False,
    )):
        raise ValueError("PBS prepared input manifest is invalid")
    return manifest


def _payload(path: Path, record: object) -> bytes:
    if not isinstance(record, dict):
        raise TypeError("PBS prepared input pin is invalid")
    record = cast("dict[str, Any]", record)
    payload = path.read_bytes()
    if record != {
        "path": path.name,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
    }:
        raise ValueError("PBS prepared input digest changed")
    return payload


def _report(
    context: dict[str, str], qualification: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "passed",
        **context,
        "dataset": DATASET,
        "revision": REVISION,
        "manifest_sha256": MANIFEST.sha256,
        "source_receipt_file_sha256": RECEIPT.sha256,
        "archive_path": ARCHIVE.path,
        "member_path": MEMBER.path,
        "member_retrieval": "extracted-from-verified-archive",
        "anonymous_public_checks": 2,
        "public_objects": {
            name: asdict(pin)
            for name, pin in (
                ("manifest", MANIFEST),
                ("source_receipt", RECEIPT),
                ("archive", ARCHIVE),
                ("member", MEMBER),
            )
        },
        "qualification": qualification,
        "publication_performed": False,
    }


def qualify_prepared_phase(
    directory: Path, exact_commit: str, projection: str
) -> dict[str, Any]:
    """Verify transient raw inputs and qualify one non-reference phase."""
    if projection not in PHASES:
        raise ValueError("unknown PBS prepared projection")
    manifest = _read_manifest(
        directory / "phase-manifest.json",
        "transient-same-run-pbs-qualification-input",
    )
    context = _context(exact_commit, manifest)
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise TypeError("PBS prepared input manifest is invalid")
    files = cast("dict[str, Any]", files)
    archive = _payload(directory / "archive.zip", files.get("archive"))
    member = _payload(directory / "member.xml", files.get("member"))
    receipt_bytes = _payload(
        directory / "source-receipt.json", files.get("source_receipt")
    )
    if (
        hashlib.sha256(archive).hexdigest() != ARCHIVE.sha256
        or len(archive) != ARCHIVE.byte_count
        or hashlib.sha256(member).hexdigest() != MEMBER.sha256
        or len(member) != MEMBER.byte_count
        or hashlib.sha256(receipt_bytes).hexdigest() != RECEIPT.sha256
    ):
        raise ValueError("PBS prepared public pin changed")
    parent = SourceReceipt.model_validate_json(receipt_bytes)
    binding = PbsXmlMemberBinding.model_validate(manifest.get("binding"))
    binding = validate_pbs_xml_member_binding(binding, archive, member, parent)
    qualification = qualify_pbs_historical_projections(
        archive, member, parent, binding, projection=projection
    )
    return _report(context, qualification)


def qualify_prepared_reference(
    directory: Path, exact_commit: str, shard_index: int
) -> dict[str, Any]:
    """Verify same-run identity and qualify one prepared reference window."""
    manifest = _read_manifest(
        directory / "reference-manifest.json",
        "transient-same-run-reference-qualification-input",
    )
    context = _context(exact_commit, manifest)
    qualification = qualify_reference_shard(directory, shard_index=shard_index)
    return _report(context, qualification)
