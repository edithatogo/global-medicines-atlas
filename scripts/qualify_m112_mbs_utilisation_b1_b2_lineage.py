"""Record current landed B1/B2 links for the frozen MBS utilisation cohort."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionState,
    ValidationResult,
    create_admission_decision,
)
from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceKind,
    RawEvidenceManifest,
    build_raw_evidence_reference_from_acquisition,
)
from global_medicines_atlas.receipts import (
    AcquisitionEvent,
    SourceReceipt,
)

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
DATASET = "edithatogo/australian-mbs-utilisation-archive"
REVISION = "dee9a5b0580dfe394474dc26b372559462e157e7"
READBACK_PATH = (
    QUAL
    / "australian-mbs-utilisation-immutable-readback-evidence-20261018.json"
)
RECEIPTS_PATH = (
    QUAL / "australian-m112-historical-source-receipts-20261017.json"
)
ACQUISITIONS_PATH = (
    QUAL / "australian-mbs-utilisation-acquisition-import-20261004.json"
)
RAW_REFERENCES_PATH = (
    QUAL / "australian-mbs-utilisation-raw-reference-import-20261004.json"
)
RAW_EVIDENCE_PATH = Path(
    "quality/bronze/imported-raw-evidence/australian-mbs-utilisation-20261017.json"
)
FROZEN_INVENTORY_PATH = (
    QUAL / "australian-m112-frozen-object-inventory-20261018.json"
)
BASELINE_GATE_PATH = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261018-retained-joins.json"
)
OUTPUT_PATH = QUAL / "australian-mbs-utilisation-landed-lineage-20261019.json"
DECIDED_AT = datetime.fromisoformat("2026-10-18T16:45:09+00:00")
EXPECTED_OBJECTS = 14
ANONYMOUS_READBACK_URL = (
    "https://github.com/edithatogo/global-medicines-atlas/"
    "issues/340#issuecomment-5978580543"
)
ACTOR = "global-medicines-atlas:m112-historical-mbs-utilisation-lineage"


def _json(path: Path) -> dict[str, Any]:
    value: object = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return cast("dict[str, Any]", value)


def _sha256(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _write_append_only(path: Path, body: bytes) -> str:
    destination = ROOT / path
    if destination.exists() and destination.read_bytes() != body:
        raise ValueError(f"append-only evidence already differs: {path}")
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
    return hashlib.sha256(body).hexdigest()


def build_report() -> tuple[dict[str, Any], dict[Path, bytes]]:  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements] -- keep the exact 14-object receipt/B2/admission join auditable in one fail-closed qualification
    """Join exact retained inputs and create unreviewed landed records only."""
    readback = _json(READBACK_PATH)
    receipts_report = _json(RECEIPTS_PATH)
    acquisitions_report = _json(ACQUISITIONS_PATH)
    raw_reference_report = _json(RAW_REFERENCES_PATH)
    imported_b2 = _json(RAW_EVIDENCE_PATH)
    frozen = _json(FROZEN_INVENTORY_PATH)
    baseline_gate = _json(BASELINE_GATE_PATH)

    readback_source = readback["source"]
    if (
        readback["status"]
        != "historical_immutable_revision_anonymous_readback_verified"
        or readback["count"] != EXPECTED_OBJECTS
        or len(readback["objects"]) != EXPECTED_OBJECTS
    ):
        raise ValueError("MBS utilisation anonymous readback scope changed")
    if any((
        readback_source["dataset"] != DATASET,
        readback_source["source_revision"] != REVISION,
        readback_source["status"] != "anonymously_verified",
        readback_source["private"] is not False,
        readback_source["readback_comment_url"] != ANONYMOUS_READBACK_URL,
    )):
        raise ValueError("MBS utilisation anonymous readback scope changed")
    if (
        receipts_report["counts"]["historical_canonical_source_receipts"]
        != EXPECTED_OBJECTS
        or receipts_report["counts"]["admission_histories"] != 0
    ):
        raise ValueError("historical receipt cohort or baseline changed")
    if (
        len(acquisitions_report["records"]) != EXPECTED_OBJECTS
        or raw_reference_report["count"] != EXPECTED_OBJECTS
        or imported_b2["row_count"] != EXPECTED_OBJECTS
        or imported_b2["authoritative"] is not True
    ):
        raise ValueError("MBS utilisation B1/B2 import scope changed")

    receipt_rows = {
        row["acquisition_id"]: row for row in receipts_report["outputs"]
    }
    acquisition_rows = {
        row["acquisition_id"]: row for row in acquisitions_report["records"]
    }
    readback_rows = {row["path"]: row for row in readback["objects"]}
    reference_by_acquisition: dict[str, dict[str, Any]] = {}
    for row in raw_reference_report["records"]:
        reference_value = _json(Path(row["path"]))
        reference_by_acquisition[
            reference_value["acquisition_event"]["acquisition_id"]
        ] = reference_value
    imported_b2_rows = {
        row["acquisition_id"]: row for row in imported_b2["rows"]
    }
    frozen_paths = {(row["dataset"], row["path"]) for row in frozen["members"]}
    baseline_rows = {
        (row["dataset"], row["path"]): row for row in baseline_gate["objects"]
    }
    if any(
        len(index) != EXPECTED_OBJECTS
        for index in (
            receipt_rows,
            acquisition_rows,
            readback_rows,
            imported_b2_rows,
            reference_by_acquisition,
        )
    ):
        raise ValueError("MBS utilisation join keys are not unique")

    outputs: dict[Path, bytes] = {}
    object_rows: list[dict[str, Any]] = []
    for acquisition_id, acquisition_row in sorted(acquisition_rows.items()):
        receipt_row = receipt_rows.get(acquisition_id)
        b2_row = imported_b2_rows.get(acquisition_id)
        if receipt_row is None or b2_row is None:
            raise ValueError("receipt, acquisition, and B2 keys differ")
        receipt_path = Path(receipt_row["path"])
        receipt = SourceReceipt.model_validate_json(
            (ROOT / receipt_path).read_bytes()
        )
        event_path = Path(acquisition_row["event_path"])
        event = AcquisitionEvent.model_validate_json(
            (ROOT / event_path).read_bytes()
        )
        reference = reference_by_acquisition.get(acquisition_id)
        source_ref = acquisition_row["b2_raw_reference"]
        proof = readback_rows.get(source_ref["path"])
        inventory_key = (DATASET, source_ref["path"])
        inventory_row = baseline_rows.get(inventory_key)
        temporal = receipt.temporal
        if temporal is None or proof is None or reference is None:
            raise ValueError("MBS utilisation source roles are incomplete")
        if inventory_row is None or inventory_key not in frozen_paths:
            raise ValueError("MBS utilisation path is outside frozen inventory")
        identity_matches = all((
            receipt.evidence_class.value == "historical",
            receipt.rights_state.value == "permitted",
            temporal.acquisition_id == acquisition_id,
            temporal.content_id == source_ref["sha256"],
            event.acquisition_id == temporal.acquisition_id,
            event.content_id == temporal.content_id,
            event.payload_sha256 == receipt.payload.sha256,
            event.retrieved_at == receipt.retrieval.retrieved_at,
            event.source_id == receipt.source.source_id,
            event.retrieval == receipt.retrieval,
            acquisition_row["path"] == source_ref["path"],
            source_ref["dataset"] == DATASET,
            source_ref["revision"] == REVISION,
            proof["sha256"] == source_ref["sha256"],
            proof["byte_count"] == source_ref["byte_count"],
            reference["raw_reference"]["sha256"] == source_ref["sha256"],
            reference["raw_reference"]["byte_count"]
            == source_ref["byte_count"],
            reference["raw_reference"]["url"] == source_ref["url"],
            reference["raw_reference"]["anonymous_digest_evidence"]
            == ANONYMOUS_READBACK_URL,
            reference["unknown_evidence"]["admission_history"] is None,
            b2_row["content_id"] == event.content_id,
            b2_row["external_reference"] == source_ref["url"],
            b2_row["state"] == "external_reference_only",
            inventory_key in frozen_paths,
            inventory_row["revision"] == REVISION,
            inventory_row["candidate_class"] == "raw_source_payload",
        ))
        if not identity_matches:
            raise ValueError(
                f"MBS utilisation evidence differs: {source_ref['path']}"
            )

        b2_record = build_raw_evidence_reference_from_acquisition(
            event,
            external_reference=source_ref["url"],
            kind=RawEvidenceKind.PAYLOAD,
        )
        b2_manifest = RawEvidenceManifest.from_rows((b2_record,))
        b2_path = Path(
            f"quality/bronze/raw-evidence/{event.source_id}/"
            f"{acquisition_id}/manifest.json"
        )
        b2_bytes = b2_manifest.canonical_json()
        b2_sha = hashlib.sha256(b2_bytes).hexdigest()
        b2_destination = ROOT / b2_path
        if b2_destination.exists() and b2_destination.read_bytes() != b2_bytes:
            raise ValueError(f"append-only B2 manifest differs: {b2_path}")
        outputs[b2_path] = b2_bytes

        decision = create_admission_decision(
            acquisition_id=acquisition_id,
            content_id=source_ref["sha256"],
            state=BronzeAdmissionState.LANDED,
            reason_codes=("m112_existing_raw_object_anonymously_verified",),
            validation_results=(
                ValidationResult(
                    check_id="anonymous-raw-sha256",
                    passed=True,
                    message=(
                        f"revision:{REVISION};path:{source_ref['path']};"
                        f"sha256:{source_ref['sha256']};evidence:{ANONYMOUS_READBACK_URL}"
                    ),
                ),
                ValidationResult(
                    check_id="anonymous-raw-byte-count",
                    passed=True,
                    message=(
                        f"revision:{REVISION};path:{source_ref['path']};"
                        f"bytes:{source_ref['byte_count']};evidence:{ANONYMOUS_READBACK_URL}"
                    ),
                ),
            ),
            reviewer_status="unreviewed",
            actor=ACTOR,
            decided_at=DECIDED_AT,
        )
        admission_path = Path(
            f"quality/bronze/admissions/{event.source_id}/{acquisition_id}/"
            f"{decision.decision_id}.json"
        )
        admission_bytes = (
            decision.model_dump_json(exclude_none=False).encode() + b"\n"
        )
        admission_destination = ROOT / admission_path
        existing_admissions = set(admission_destination.parent.glob("*.json"))
        if existing_admissions - {admission_destination}:
            raise ValueError(
                f"unexpected prior MBS utilisation admission: {admission_path}"
            )
        if (
            admission_destination.exists()
            and admission_destination.read_bytes() != admission_bytes
        ):
            raise ValueError(f"append-only admission differs: {admission_path}")
        outputs[admission_path] = admission_bytes
        object_rows.append({
            "dataset": DATASET,
            "revision": REVISION,
            "path": source_ref["path"],
            "source_id": event.source_id,
            "acquisition_id": acquisition_id,
            "content_sha256": source_ref["sha256"],
            "byte_count": source_ref["byte_count"],
            "source_receipt_path": receipt_path.as_posix(),
            "acquisition_event_path": event_path.as_posix(),
            "b2_manifest_path": b2_path.as_posix(),
            "b2_manifest_sha256": b2_sha,
            "landed_admission_path": admission_path.as_posix(),
            "landed_admission_sha256": hashlib.sha256(
                admission_bytes
            ).hexdigest(),
            "anonymous_digest_evidence": ANONYMOUS_READBACK_URL,
            "lineage_complete": True,
            "reviewer_status": decision.reviewer_status,
            "admission_state": decision.state.value,
            "v4_admission": False,
            "consumer_canary": False,
        })

    if (
        len(object_rows) != EXPECTED_OBJECTS
        or len(outputs) != EXPECTED_OBJECTS * 2
    ):
        raise ValueError("expected one B2 manifest and landed event per object")
    inputs = (
        READBACK_PATH,
        RECEIPTS_PATH,
        ACQUISITIONS_PATH,
        RAW_REFERENCES_PATH,
        RAW_EVIDENCE_PATH,
        FROZEN_INVENTORY_PATH,
        BASELINE_GATE_PATH,
    )
    report = {
        "schema_id": "global-medicines-atlas.mbs-utilisation-landed-lineage",
        "schema_version": 1,
        "recorded_at": DECIDED_AT.isoformat().replace("+00:00", "Z"),
        "status": "fourteen_frozen_mbs_b1_b2_lineages_landed_unreviewed",
        "scope": {
            "dataset": DATASET,
            "revision": REVISION,
            "frozen_inventory_member_count": EXPECTED_OBJECTS,
            "lineages_completed": len(object_rows),
            "processing_admission": False,
            "v4_admission": False,
            "consumer_canaries": False,
        },
        "input_bindings": {path.as_posix(): _sha256(path) for path in inputs},
        "anonymous_readback": readback["source"],
        "objects": object_rows,
        "boundaries": {
            "new_sources_added": False,
            "frozen_denominator_changed": False,
            "source_payload_bytes_retained_locally": False,
            "source_payload_values_inspected": False,
            "historical_records_rewritten": False,
            "rights_or_licensing_conclusion_added": False,
            "processing_admission_performed": False,
            "v4_admission_performed": False,
            "consumer_canary_performed": False,
        },
    }
    return report, outputs


def main() -> None:
    report, outputs = build_report()
    written = {
        path.as_posix(): _write_append_only(path, body)
        for path, body in sorted(
            outputs.items(), key=lambda item: item[0].as_posix()
        )
    }
    report["output_bindings"] = written
    output_bytes = (
        json.dumps(report, ensure_ascii=False, indent=2).encode() + b"\n"
    )
    destination = ROOT / OUTPUT_PATH
    if destination.exists() and destination.read_bytes() != output_bytes:
        raise ValueError(
            f"append-only lineage qualification differs: {OUTPUT_PATH}"
        )
    if not destination.exists():
        destination.write_bytes(output_bytes)
    print(
        json.dumps(
            {
                "qualification": OUTPUT_PATH.as_posix(),
                "objects": len(report["objects"]),
                "artifacts": len(written),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
