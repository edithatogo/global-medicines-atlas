"""Bind the frozen July 2025 MBS raw object to its existing receipt."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionState,
    create_admission_decision,
)
from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceKind,
    RawEvidenceManifest,
    build_raw_evidence_reference_from_acquisition,
)
from global_medicines_atlas.receipts import (
    AcquisitionEvent,
    SensitivityClassification,
    SourceReceipt,
    TemporalIdentity,
    require_temporal,
)

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
BASE = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261019-p7-archive-lineage.json"
)
CURRENT_TREE = (
    QUAL
    / "australian-m112-current-tree-object-identity-reconciliation-20261004.json"
)
PUBLIC_ARCHIVE = QUAL / "australian-mbs-public-huggingface-20260829.json"
V4_READBACK = (
    QUAL / "australian-m112-2025-mbs-v4-receipt-readback-20261004.json"
)
V4_MANIFEST = QUAL / "australian-mbs-v4-candidate-2025-07/manifest.json"
SOURCE_ID = "au-mbs"
DATASET = "edithatogo/australian-mbs-source-archive"
INVENTORY_REVISION = "40891976f77ee5e7688edceed25c9ac98a77547e"
ARCHIVE_REVISION = "4d1dae488ac43522f20e8320a8b2a56bf9138341"
SOURCE_PATH = "raw/mbs/2025-07/MBS-XML-20250701-Version-3.XML"
SOURCE_SHA256 = (
    "db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556"
)
SOURCE_BYTES = 8_194_522
SOURCE_RECEIPT_SHA256 = (
    "c8c3e3baeee4c08dba1a944c19652ec184d90de850968fc4d6a124747d994e03"
)
SOURCE_RECEIPT = Path(
    "quality/bronze/receipts/au-mbs/"
    "bbd662119ebebfdf08baf14c0b15c0dd5c93465910fd4f5309f37ecd37a82b8d.json"
)
ACQUISITION_ID = (
    "bbd662119ebebfdf08baf14c0b15c0dd5c93465910fd4f5309f37ecd37a82b8d"
)
ARCHIVE_URI = (
    "https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/resolve/"
    f"{ARCHIVE_REVISION}/{SOURCE_PATH}"
)
OUTPUT = QUAL / "australian-m112-july-mbs-source-lineage-20261019.json"
OVERLAY_OUTPUT = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261019-july-mbs-source-lineage.json"
)
OBSERVED_AT = "2026-10-19T04:28:01+10:00"
ADMISSION_AT = datetime(2026, 10, 18, 18, 28, 1, tzinfo=UTC)
EXPECTED_DENOMINATOR = 1759
EXPECTED_PRIOR_COMPLETE = 21
EXPECTED_COMPLETE = 22


def _read(path: Path) -> dict[str, Any]:
    value: object = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast("dict[str, Any]", value)


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _write_bound(path: Path, payload: bytes) -> str:
    target = ROOT / path
    if target.exists():
        if target.read_bytes() != payload:
            raise ValueError(f"immutable evidence conflict: {path}")
        return hashlib.sha256(payload).hexdigest()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class _LineageArtifacts:
    """Materialized role files and their stable evidence bindings."""

    event_path: Path
    b2_path: Path
    admission_path: Path
    acquisition_id: str
    receipt_digest: str
    b2_digest: str
    admission_digest: str
    admission_state: str
    reviewer_status: str
    rights_state: str
    output_bindings: dict[str, str]


def _require_frozen_row(base: dict[str, Any]) -> dict[str, Any]:
    if not all((
        base["updated_gate_totals"]["approved_denominator"]
        == EXPECTED_DENOMINATOR,
        base["updated_gate_totals"]["complete_raw_b1_b2_lineage"]
        == EXPECTED_PRIOR_COMPLETE,
        base["updated_gate_totals"]["preserved_deferrals"]
        == EXPECTED_DENOMINATOR,
    )):
        raise ValueError("M-112 baseline or independent gates changed")
    matches = [
        row
        for row in base["objects"]
        if row["dataset"] == DATASET
        and row["revision"] == INVENTORY_REVISION
        and row["path"] == SOURCE_PATH
    ]
    if len(matches) != 1:
        raise ValueError("frozen July MBS source path is absent or duplicated")
    row = matches[0]
    identity = row["identity"]
    if not all((
        row["candidate_class"] == "raw_source_payload",
        row["approved_denominator_member"] is True,
        identity["sha256"] == SOURCE_SHA256,
        identity["byte_count"] == SOURCE_BYTES,
        identity["anonymous_digest_readback"] is True,
        row["b1_b2_lineage"]["complete"] is False,
    )):
        raise ValueError("frozen July MBS identity or prior lineage changed")
    return row


def _validate_public_archive_binding() -> None:
    archive = _read(PUBLIC_ARCHIVE)
    exact_payloads = [
        item
        for item in archive["raw_payloads"]
        if item.get("source_id") == SOURCE_ID
        and item.get("path") == SOURCE_PATH
        and item.get("sha256") == SOURCE_SHA256
        and item.get("bytes") == SOURCE_BYTES
    ]
    if len(exact_payloads) != 1:
        raise ValueError(
            "pinned public archive does not uniquely bind July MBS"
        )


def _load_verified_receipt() -> tuple[SourceReceipt, TemporalIdentity]:
    receipt = SourceReceipt.model_validate_json(
        (ROOT / SOURCE_RECEIPT).read_bytes()
    )
    temporal = require_temporal(receipt.temporal)
    if not all((
        receipt.digest() == SOURCE_RECEIPT_SHA256,
        temporal.acquisition_id == ACQUISITION_ID,
        temporal.content_id == SOURCE_SHA256,
        receipt.payload.byte_count == SOURCE_BYTES,
        str(receipt.retrieval.uri) == ARCHIVE_URI,
        receipt.rights_state.value == "permitted",
    )):
        raise ValueError("existing July MBS source receipt binding changed")

    source = _read(V4_MANIFEST)["source"]
    if not all((
        source["receipt_sha256"] == SOURCE_RECEIPT_SHA256,
        source["sha256"] == SOURCE_SHA256,
        source["source_path"] == SOURCE_PATH,
        source["source_revision"] == temporal.source_version,
    )):
        raise ValueError("July MBS manifest receipt binding changed")

    readback = _read(V4_READBACK)
    if not all((
        readback["source_identity"]["canonical_receipt_sha256"]
        == SOURCE_RECEIPT_SHA256,
        readback["source_identity"]["source_sha256"] == SOURCE_SHA256,
        readback["remote_readback"]["revision"] == INVENTORY_REVISION,
    )):
        raise ValueError("anonymous metadata readback identity changed")
    return receipt, temporal


def _write_lineage_artifacts(
    receipt: SourceReceipt, temporal: TemporalIdentity
) -> _LineageArtifacts:
    event = AcquisitionEvent(
        acquisition_id=temporal.acquisition_id,
        content_id=SOURCE_SHA256,
        source_id=SOURCE_ID,
        source_version=temporal.source_version,
        retrieved_at=receipt.retrieval.retrieved_at,
        source_published_at=temporal.source_published_at,
        source_effective_at=temporal.source_effective_at,
        valid_from=temporal.valid_from,
        valid_to=temporal.valid_to,
        payload_sha256=SOURCE_SHA256,
        source=receipt.source,
        retrieval=receipt.retrieval,
        reuse=receipt.reuse,
        rights_state=receipt.rights_state,
        rights_reference=receipt.rights_reference,
        rights_policy=receipt.rights_policy,
        evidence_class=receipt.evidence_class,
        sensitivity=receipt.sensitivity or SensitivityClassification(),
    )
    raw_row = build_raw_evidence_reference_from_acquisition(
        event,
        external_reference=ARCHIVE_URI,
        kind=RawEvidenceKind.PAYLOAD,
        media_type="application/xml",
    )
    b2 = RawEvidenceManifest.from_rows((raw_row,))
    admission = create_admission_decision(
        acquisition_id=event.acquisition_id,
        content_id=event.content_id,
        state=BronzeAdmissionState.LANDED,
        reason_codes=(
            "pinned_public_archive_retrieval_only",
            "source_date_semantics_not_requalified",
            "v4_admission_not_performed",
        ),
        reviewer_status="unreviewed",
        actor="global-medicines-atlas:m112-lineage-reconciliation",
        decided_at=ADMISSION_AT,
    )
    event_path = (
        Path("quality/bronze/acquisitions/au-mbs") / f"{ACQUISITION_ID}.json"
    )
    b2_path = (
        Path("quality/bronze/raw-evidence/au-mbs")
        / ACQUISITION_ID
        / "manifest.json"
    )
    admission_path = (
        Path("quality/bronze/admissions/au-mbs")
        / ACQUISITION_ID
        / f"{admission.decision_id}.json"
    )
    outputs = {
        event_path.as_posix(): _write_bound(event_path, event.canonical_json()),
        b2_path.as_posix(): _write_bound(b2_path, b2.canonical_json()),
        admission_path.as_posix(): _write_bound(
            admission_path, admission.model_dump_json().encode("utf-8") + b"\n"
        ),
    }
    return _LineageArtifacts(
        event_path=event_path,
        b2_path=b2_path,
        admission_path=admission_path,
        acquisition_id=event.acquisition_id,
        receipt_digest=receipt.digest(),
        b2_digest=outputs[b2_path.as_posix()],
        admission_digest=outputs[admission_path.as_posix()],
        admission_state=admission.state.value,
        reviewer_status=admission.reviewer_status,
        rights_state=receipt.rights_state.value,
        output_bindings=outputs,
    )


def build_report() -> dict[str, Any]:
    """Validate current identity, public archive binding, and existing receipt."""

    base = _read(BASE)
    _require_frozen_row(base)
    _validate_public_archive_binding()
    receipt, temporal = _load_verified_receipt()
    artifacts = _write_lineage_artifacts(receipt, temporal)
    return {
        "schema_id": "global-medicines-atlas.m112-july-mbs-source-lineage",
        "schema_version": 1,
        "observed_at": OBSERVED_AT,
        "status": "existing_july_mbs_receipt_bound_to_landed_unreviewed_b1_b2_lineage",
        "inventory": {
            "dataset": DATASET,
            "revision": INVENTORY_REVISION,
            "path": SOURCE_PATH,
            "sha256": SOURCE_SHA256,
            "byte_count": SOURCE_BYTES,
            "approved_denominator_member": True,
            "membership_sha256": base["approved_path_membership_sha256"],
        },
        "archive_object": {
            "dataset": DATASET,
            "revision": ARCHIVE_REVISION,
            "path": SOURCE_PATH,
            "uri": ARCHIVE_URI,
            "sha256": SOURCE_SHA256,
            "byte_count": SOURCE_BYTES,
            "matched_unique_public_archive_inventory_row": True,
            "payload_requested_or_inspected": False,
            "payload_persisted_locally": False,
        },
        "lineage": {
            "source_receipt_path": SOURCE_RECEIPT.as_posix(),
            "source_receipt_sha256": artifacts.receipt_digest,
            "acquisition_event_path": artifacts.event_path.as_posix(),
            "acquisition_id": artifacts.acquisition_id,
            "b2_manifest_path": artifacts.b2_path.as_posix(),
            "b2_manifest_sha256": artifacts.b2_digest,
            "landed_admission_path": artifacts.admission_path.as_posix(),
            "landed_admission_sha256": artifacts.admission_digest,
            "admission_state": artifacts.admission_state,
            "reviewer_status": artifacts.reviewer_status,
            "rights_state_inherited_from_existing_source_receipt": artifacts.rights_state,
        },
        "input_bindings": {
            path.as_posix(): _sha(path)
            for path in (
                BASE,
                CURRENT_TREE,
                PUBLIC_ARCHIVE,
                V4_READBACK,
                V4_MANIFEST,
                SOURCE_RECEIPT,
            )
        },
        "implementation": {
            "path": "scripts/reconcile_m112_july_mbs_source_lineage.py",
            "sha256": _sha(
                Path("scripts/reconcile_m112_july_mbs_source_lineage.py")
            ),
        },
        "output_bindings": artifacts.output_bindings,
        "scope_limits": {
            "new_source_or_dataset_added": False,
            "frozen_inventory_changed": False,
            "rights_or_licensing_conclusion_added": False,
            "per_object_rights_gate_closed": False,
            "source_date_semantics_requalified": False,
            "processing_admission_performed": False,
            "v4_admission_performed": False,
            "consumer_canary_performed": False,
            "source_payload_bytes_requested_or_inspected": False,
        },
    }


def update_overlay(qualification: dict[str, Any]) -> dict[str, Any]:
    """Update only the July 2025 raw MBS row in the approved overlay."""

    report = copy.deepcopy(_read(BASE))
    target = next(
        row
        for row in report["objects"]
        if row["dataset"] == DATASET
        and row["revision"] == INVENTORY_REVISION
        and row["path"] == SOURCE_PATH
    )
    if target["b1_b2_lineage"]["complete"] is not False:
        raise ValueError("July 2025 MBS lineage row is no longer incomplete")
    target["b1_b2_lineage"] = {
        "complete": True,
        "state": (
            "Existing source receipt, acquisition event, external-reference-only "
            "B2 manifest, and landed unreviewed admission are bound to the frozen "
            "July 2025 MBS raw path, revision, digest, and byte count. This does "
            "not change the separate per-object rights gate, qualify source-date "
            "semantics, or admit the object for v4 or consumer use."
        ),
        "evidence": {
            "qualification_path": OUTPUT.as_posix(),
            "qualification_sha256": _sha(OUTPUT),
            **qualification["lineage"],
            "archive_object": qualification["archive_object"],
        },
        "acquisition_id": qualification["lineage"]["acquisition_id"],
        "source_revision": INVENTORY_REVISION,
        "archive_revision": ARCHIVE_REVISION,
        "content_sha256": SOURCE_SHA256,
        "byte_count": SOURCE_BYTES,
        "admission_state": "landed",
        "reviewer_status": "unreviewed",
    }
    report["observed_at"] = OBSERVED_AT
    report["purpose"] = (
        "Preserve the approved 1,759-object inventory while binding the existing "
        "July 2025 MBS source receipt to its exact frozen raw path and B1/B2 roles."
    )
    report["updated_gate_totals"]["complete_raw_b1_b2_lineage"] += 1
    report["updated_gate_totals"]["complete_raw_b1_b2_lineage_paths"] += 1
    report["july_2025_mbs_source_lineage_expansion"] = {
        "prior_complete_lineages": EXPECTED_PRIOR_COMPLETE,
        "new_complete_lineages": 1,
        "complete_lineages_after_expansion": EXPECTED_COMPLETE,
        "new_exact_receipt_acquisition_path_joins": 1,
        "cumulative_exact_receipt_acquisition_path_joins": 27,
        "qualification_path": OUTPUT.as_posix(),
        "qualification_sha256": _sha(OUTPUT),
        "scope_limits": qualification["scope_limits"],
    }
    if (
        report["updated_gate_totals"]["approved_denominator"]
        != EXPECTED_DENOMINATOR
        or report["updated_gate_totals"]["complete_raw_b1_b2_lineage"]
        != EXPECTED_COMPLETE
        or report["updated_gate_totals"]["v4_admissions"] != 0
        or report["updated_gate_totals"]["consumer_canaries"] != 0
        or report["updated_gate_totals"]["preserved_deferrals"]
        != EXPECTED_DENOMINATOR
    ):
        raise ValueError("July MBS lineage changed an independent M-112 gate")
    return report


def main() -> None:
    report = build_report()
    _write_bound(
        OUTPUT,
        json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
        + b"\n",
    )
    overlay = update_overlay(report)
    _write_bound(
        OVERLAY_OUTPUT,
        json.dumps(overlay, ensure_ascii=False, indent=2).encode("utf-8")
        + b"\n",
    )
    print(OUTPUT.as_posix())
    print(OVERLAY_OUTPUT.as_posix())


if __name__ == "__main__":
    main()
