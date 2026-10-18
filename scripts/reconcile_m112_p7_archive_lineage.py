"""Record the frozen P7 workbook's archive-boundary B1/B2 lineage."""

from __future__ import annotations

import copy
import hashlib
import json
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
from global_medicines_atlas.mbs_p7_receipt_reconciliation import (
    ARCHIVE_MEMBER_PATH,
    ARCHIVE_URI,
    SOURCE_BYTES,
    SOURCE_ID,
    SOURCE_SHA256,
    reconstruct_p7_storage_source_receipt,
)
from global_medicines_atlas.receipts import (
    AcquisitionEvent,
    SensitivityClassification,
    require_temporal,
)

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
BASE = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261019-mbs-util-lineages.json"
)
P7_STORAGE = QUAL / "mbs-p7-storage-receipt-reconciliation-20261003.json"
P7_STORAGE_SOURCE = QUAL / "mbs-workbook-storage-20260830.json"
PUBLIC_ARCHIVE = QUAL / "australian-mbs-public-huggingface-20260829.json"
OUTPUT = QUAL / "australian-m112-p7-archive-lineage-20261019.json"
OVERLAY_OUTPUT = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261019-p7-archive-lineage.json"
)
DATASET = "edithatogo/australian-mbs-source-archive"
INVENTORY_REVISION = "40891976f77ee5e7688edceed25c9ac98a77547e"
ARCHIVE_REVISION = "4d1dae488ac43522f20e8320a8b2a56bf9138341"
READBACK_AT = "2026-10-18T17:21:35Z"
READBACK_FINAL_URI = (
    "https://huggingface.co/api/resolve-cache/datasets/edithatogo/"
    "australian-mbs-source-archive/4d1dae488ac43522f20e8320a8b2a56bf9138341/"
    "raw%2Fmbs%2Flegacy%2F2024-07%2FMBS-2024.07-Group-P7-Genetics.xlsx?"
    "%2Fdatasets%2Fedithatogo%2Faustralian-mbs-source-archive%2Fresolve%2F"
    "4d1dae488ac43522f20e8320a8b2a56bf9138341%2Fraw%2Fmbs%2Flegacy%2F"
    "2024-07%2FMBS-2024.07-Group-P7-Genetics.xlsx=&etag=%22"
    "a9d302b8a278f9e65659a1f5da09ded21723a239%22"
)
ADMISSION_AT = datetime(2026, 10, 18, 17, 57, 4, tzinfo=UTC)
EXPECTED_DENOMINATOR = 1759
EXPECTED_PRIOR_COMPLETE = 20
EXPECTED_COMPLETE = 21


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


def build_report() -> dict[str, Any]:
    """Verify the exact frozen P7 row and bind its archive retrieval roles."""

    base = _read(BASE)
    if (
        base["scope"]["approved_denominator"] != EXPECTED_DENOMINATOR
        or base["updated_gate_totals"]["complete_raw_b1_b2_lineage"]
        != EXPECTED_PRIOR_COMPLETE
        or base["scope"]["denominator_changed"] is not False
    ):
        raise ValueError("M-112 frozen inventory or lineage baseline changed")
    rows = base["objects"]
    matches = [
        row
        for row in rows
        if row["dataset"] == DATASET
        and row["revision"] == INVENTORY_REVISION
        and row["path"] == ARCHIVE_MEMBER_PATH
    ]
    if len(matches) != 1:
        raise ValueError("frozen P7 inventory member is absent or duplicated")
    row = matches[0]
    if (
        row["candidate_class"] != "raw_source_payload"
        or row["approved_denominator_member"] is not True
        or row["identity"]["sha256"] != SOURCE_SHA256
        or row["identity"]["byte_count"] != SOURCE_BYTES
        or row["b1_b2_lineage"]["complete"] is not False
    ):
        raise ValueError("frozen P7 identity or prior lineage state changed")

    receipt = reconstruct_p7_storage_source_receipt(ROOT)
    temporal = require_temporal(receipt.temporal)
    if (
        receipt.digest() != _read(P7_STORAGE)["recorded_receipt_sha256"]
        or temporal.content_id != SOURCE_SHA256
        or receipt.payload.byte_count != SOURCE_BYTES
        or str(receipt.retrieval.uri) != ARCHIVE_URI
    ):
        raise ValueError("historical P7 archive receipt binding changed")

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
    b2_row = build_raw_evidence_reference_from_acquisition(
        event,
        external_reference=ARCHIVE_URI,
        kind=RawEvidenceKind.PAYLOAD,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    b2 = RawEvidenceManifest.from_rows((b2_row,))
    admission = create_admission_decision(
        acquisition_id=event.acquisition_id,
        content_id=event.content_id,
        state=BronzeAdmissionState.LANDED,
        reason_codes=(
            "archive_boundary_retrieval_only",
            "source_origin_acquisition_unverified",
            "source_date_semantics_unqualified",
        ),
        reviewer_status="unreviewed",
        actor="global-medicines-atlas:m112-lineage-reconciliation",
        decided_at=ADMISSION_AT,
    )
    receipt_path = (
        Path("quality/bronze/receipts")
        / SOURCE_ID
        / f"{event.acquisition_id}.json"
    )
    event_path = (
        Path("quality/bronze/acquisitions")
        / SOURCE_ID
        / f"{event.acquisition_id}.json"
    )
    b2_path = (
        Path("quality/bronze/raw-evidence")
        / SOURCE_ID
        / event.acquisition_id
        / "manifest.json"
    )
    admission_path = (
        Path("quality/bronze/admissions")
        / SOURCE_ID
        / event.acquisition_id
        / f"{admission.decision_id}.json"
    )
    outputs = {
        receipt_path.as_posix(): _write_bound(
            receipt_path, receipt.canonical_json()
        ),
        event_path.as_posix(): _write_bound(event_path, event.canonical_json()),
        b2_path.as_posix(): _write_bound(b2_path, b2.canonical_json()),
        admission_path.as_posix(): _write_bound(
            admission_path,
            admission.model_dump_json().encode("utf-8") + b"\n",
        ),
    }
    return {
        "schema_id": "global-medicines-atlas.m112-p7-archive-lineage",
        "schema_version": 1,
        "observed_at": "2026-10-19",
        "status": "archive_boundary_b1_b2_lineage_recorded_landed_unreviewed",
        "inventory": {
            "dataset": DATASET,
            "revision": INVENTORY_REVISION,
            "path": ARCHIVE_MEMBER_PATH,
            "sha256": SOURCE_SHA256,
            "byte_count": SOURCE_BYTES,
            "approved_denominator_member": True,
            "membership_sha256": base["approved_path_membership_sha256"],
        },
        "archive_retrieval": {
            "dataset": DATASET,
            "revision": ARCHIVE_REVISION,
            "path": ARCHIVE_MEMBER_PATH,
            "uri": ARCHIVE_URI,
            "final_uri": READBACK_FINAL_URI,
            "observed_at": READBACK_AT,
            "http_status": 200,
            "streamed_byte_count": SOURCE_BYTES,
            "streamed_sha256": SOURCE_SHA256,
            "payload_values_inspected": False,
            "payload_persisted_locally": False,
        },
        "lineage": {
            "source_receipt_path": receipt_path.as_posix(),
            "source_receipt_sha256": receipt.digest(),
            "acquisition_event_path": event_path.as_posix(),
            "acquisition_id": event.acquisition_id,
            "b2_manifest_path": b2_path.as_posix(),
            "b2_manifest_sha256": outputs[b2_path.as_posix()],
            "landed_admission_path": admission_path.as_posix(),
            "landed_admission_sha256": outputs[admission_path.as_posix()],
            "admission_state": admission.state.value,
            "reviewer_status": admission.reviewer_status,
            "rights_state_inherited_from_historical_receipt": receipt.rights_state.value,
        },
        "input_bindings": {
            BASE.as_posix(): _sha(BASE),
            P7_STORAGE.as_posix(): _sha(P7_STORAGE),
            P7_STORAGE_SOURCE.as_posix(): _sha(P7_STORAGE_SOURCE),
            PUBLIC_ARCHIVE.as_posix(): _sha(PUBLIC_ARCHIVE),
        },
        "implementation": {
            "path": "scripts/reconcile_m112_p7_archive_lineage.py",
            "sha256": _sha(
                Path("scripts/reconcile_m112_p7_archive_lineage.py")
            ),
            "source_receipt_helper": {
                "path": "src/global_medicines_atlas/mbs_p7_receipt_reconciliation.py",
                "sha256": _sha(
                    Path(
                        "src/global_medicines_atlas/mbs_p7_receipt_reconciliation.py"
                    )
                ),
            },
        },
        "output_bindings": outputs,
        "scope_limits": {
            "archive_boundary_acquisition_only": True,
            "source_origin_acquisition_evidenced": False,
            "source_date_semantics_qualified": False,
            "rights_or_licensing_conclusion_added": False,
            "derived_table_rights_concluded": False,
            "processing_admission_performed": False,
            "v4_admission_performed": False,
            "consumer_canary_performed": False,
            "new_source_or_dataset_added": False,
            "frozen_inventory_changed": False,
        },
    }


def update_overlay(qualification: dict[str, Any]) -> dict[str, Any]:
    """Update only the P7 lineage row in the frozen per-object overlay."""

    report = copy.deepcopy(_read(BASE))
    target = next(
        row
        for row in report["objects"]
        if row["dataset"] == DATASET
        and row["revision"] == INVENTORY_REVISION
        and row["path"] == ARCHIVE_MEMBER_PATH
    )
    if target["b1_b2_lineage"]["complete"] is not False:
        raise ValueError("P7 lineage row is no longer incomplete")
    target["b1_b2_lineage"] = {
        "complete": True,
        "state": (
            "B1/B2 lineage is bound for the pinned public archive retrieval: "
            "historical source receipt, acquisition event, external-reference-only "
            "B2 manifest, and landed unreviewed admission match the frozen path, "
            "revision, digest, and byte count. This does not establish the "
            "workbook's original source-origin acquisition, qualify its date "
            "semantics, or admit it for processing or v4."
        ),
        "evidence": {
            "qualification_path": OUTPUT.as_posix(),
            "qualification_sha256": _sha(OUTPUT),
            "source_receipt_path": qualification["lineage"][
                "source_receipt_path"
            ],
            "acquisition_event_path": qualification["lineage"][
                "acquisition_event_path"
            ],
            "b2_manifest_path": qualification["lineage"]["b2_manifest_path"],
            "b2_manifest_sha256": qualification["lineage"][
                "b2_manifest_sha256"
            ],
            "landed_admission_path": qualification["lineage"][
                "landed_admission_path"
            ],
            "landed_admission_sha256": qualification["lineage"][
                "landed_admission_sha256"
            ],
            "anonymous_archive_readback": qualification["archive_retrieval"],
        },
        "acquisition_id": qualification["lineage"]["acquisition_id"],
        "source_revision": INVENTORY_REVISION,
        "archive_revision": ARCHIVE_REVISION,
        "content_sha256": SOURCE_SHA256,
        "byte_count": SOURCE_BYTES,
        "admission_state": "landed",
        "reviewer_status": "unreviewed",
    }
    report["observed_at"] = "2026-10-19"
    report["purpose"] = (
        "Preserve the approved 1,759-object inventory while recording archive-"
        "boundary B1/B2 lineage for the exact July 2024 P7 workbook object."
    )
    report["updated_gate_totals"]["complete_raw_b1_b2_lineage"] += 1
    report["updated_gate_totals"]["complete_raw_b1_b2_lineage_paths"] += 1
    report["p7_archive_lineage_expansion"] = {
        "prior_complete_lineages": EXPECTED_PRIOR_COMPLETE,
        "new_complete_lineages": 1,
        "complete_lineages_after_expansion": EXPECTED_COMPLETE,
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
        raise ValueError("P7 lineage changed a separate M-112 gate")
    return report


def main() -> None:
    report = build_report()
    output = ROOT / OUTPUT
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    overlay = update_overlay(report)
    (ROOT / OVERLAY_OUTPUT).write_text(
        json.dumps(overlay, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT.as_posix())
    print(OVERLAY_OUTPUT.as_posix())


if __name__ == "__main__":
    main()
