"""Project exact PBS utilisation receipt joins into local B1/B2 lineage."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
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
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    RetrievalEvidence,
    RightsState,
    acquisition_event_id_for,
)

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
DATASET = "edithatogo/australian-pbs-utilisation-archive"
REVISION = "9f1d53cd50eea251b326da42a96f3ac72ebce97a"
AUDIT_PATH = QUAL / "australian-m112-receipt-sidecar-join-audit-20260930.json"
READBACK_PATH = (
    QUAL / "australian-pbs-utilisation-receipt-sidecar-readback-20261019.json"
)
FROZEN_PATH = QUAL / "australian-m112-frozen-object-inventory-20261018.json"
BASE_PATH = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261019-pbs-projected-b1-b2-lineage.json"
)
DIGEST_REPORT_PATH = (
    QUAL / "australian-m112-utilisation-digest-reconciliation-20261004.json"
)
OUTPUT_PATH = QUAL / "australian-pbs-utilisation-landed-lineage-20261019.json"
EXPECTED_OBJECTS = 6
HTTP_OK = 200
DECIDED_AT = datetime(2026, 10, 18, 22, 37, 23, tzinfo=UTC)
ACTOR = "global-medicines-atlas:m112-pbs-utilisation-lineage"


def read_json(path: Path) -> dict[str, Any]:
    value: object = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return cast("dict[str, Any]", value)


def _sha256(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode()
        + b"\n"
    )


def build_report() -> tuple[dict[str, Any], dict[Path, bytes]]:  # ruff: ignore[too-many-statements,too-many-locals] -- keep the exact six-object receipt, digest, and gate join auditable in one fail-closed pass
    """Build six unreviewed lineage records from pinned receipt metadata."""
    audit = read_json(AUDIT_PATH)
    readback = read_json(READBACK_PATH)
    frozen_report = read_json(FROZEN_PATH)
    baseline = read_json(BASE_PATH)
    digest_report = read_json(DIGEST_REPORT_PATH)

    audit_row = next(
        (row for row in audit["datasets"] if row["dataset"] == DATASET), None
    )
    if audit_row is None or not all((
        audit_row["revision"] == REVISION,
        audit_row["raw_manifest_rows"] == EXPECTED_OBJECTS,
        audit_row["receipt_sidecar_count"] == EXPECTED_OBJECTS,
        audit_row["joined_sidecar_count"] == EXPECTED_OBJECTS,
        audit_row["unmatched_sidecars"] == [],
        audit_row["all_manifest_fields_match"] is True,
        audit_row["sidecars_contain_rights_decision"] is False,
        audit_row["authorization_scope_match"]
        if "authorization_scope_match" in audit_row
        else audit_row["objects_outside_authorized_source_category_or_domains"]
        == 0,
    )):
        raise ValueError("PBS utilisation receipt-sidecar audit scope changed")

    if not all((
        readback.get("schema_id")
        == "global-medicines-atlas.pbs-utilisation-receipt-sidecar-readback",
        readback.get("dataset") == DATASET,
        readback.get("revision") == REVISION,
        readback.get("anonymous") is True,
        len(readback.get("objects", [])) == EXPECTED_OBJECTS,
        readback.get("source_payload_bytes_read") is False,
        readback.get("source_payload_values_read") is False,
    )):
        raise ValueError("PBS utilisation sidecar readback scope changed")

    frozen = {
        (row["dataset"], row["approved_dataset_revision"], row["path"]): row
        for row in frozen_report["members"]
    }
    gate = {
        (row["dataset"], row["revision"], row["path"]): row
        for row in baseline["objects"]
    }
    audit_objects = {row["path"]: row for row in audit_row["joined_objects"]}
    readback_objects = {row["path"]: row for row in readback["objects"]}
    digest_objects = {
        row["path"]: row
        for row in digest_report["verified_objects"]
        if row["dataset"] == DATASET
    }
    if not all(
        len(index) == EXPECTED_OBJECTS
        for index in (audit_objects, readback_objects, digest_objects)
    ):
        raise ValueError("PBS utilisation receipt join keys are not unique")

    output: dict[Path, bytes] = {}
    rows: list[dict[str, Any]] = []
    for path, audit_object in sorted(audit_objects.items()):
        receipt = readback_objects.get(path)
        identity = digest_objects.get(path)
        key = (DATASET, REVISION, path)
        frozen_row = frozen.get(key)
        gate_row = gate.get(key)
        if (
            receipt is None
            or identity is None
            or frozen_row is None
            or gate_row is None
        ):
            raise ValueError(
                f"PBS utilisation path lacks exact evidence: {path}"
            )
        checks = all((
            receipt["http_status"] == HTTP_OK,
            receipt["receipt_path"] == audit_object["receipt_path"],
            receipt["receipt_sha256"] == audit_object["receipt_sha256"],
            receipt["source_id"] == audit_object["source_id"],
            receipt["category"] == audit_object["category"],
            audit_object["authorized_source_id"] is True,
            audit_object["authorized_category"] is True,
            audit_object["source_domain_authorized"] is True,
            audit_object["final_domain_authorized"] is True,
            audit_object["authorization_scope_match"] is True,
            receipt["archive_path"] == path,
            receipt["sha256"]
            == audit_object["sha256"]
            == identity["sha256"]
            == gate_row["identity"]["sha256"],
            receipt["byte_count"]
            == audit_object["byte_count"]
            == identity["byte_count"]
            == gate_row["identity"]["byte_count"],
            frozen_row["object_class"] == "raw_source_payload",
            gate_row["identity"]["anonymous_digest_readback"] is True,
            gate_row["identity"]["git_blob_and_size_match"] is True,
            receipt["rights_state_field_present"] is False,
            identity["matched_hosted_verified_manifest"] is True,
            gate_row["candidate_class"] == "raw_source_payload",
            gate_row["b1_b2_lineage"]["complete"] is False,
            gate_row["v4_admission"] is False,
            gate_row["consumer_canary"] is False,
            gate_row["disposition"] == "deferred_not_admitted",
        ))
        if not checks:
            raise ValueError(
                f"PBS utilisation receipt identity or gates differ: {path}"
            )

        source_id = receipt["source_id"]
        source_url = receipt["source_url"]
        retrieved_at = datetime.fromisoformat(receipt["retrieved_at"])
        source_version = receipt["period_label"]
        acquisition_id = acquisition_event_id_for(
            source_id=source_id,
            payload_sha256=receipt["sha256"],
            retrieved_at=retrieved_at,
            source_version=source_version,
            original_uri=source_url,
        )
        event = AcquisitionEvent(
            acquisition_id=acquisition_id,
            content_id=receipt["sha256"],
            source_id=source_id,
            source_version=source_version,
            retrieved_at=retrieved_at,
            payload_sha256=receipt["sha256"],
            rights_state=RightsState.UNKNOWN,
            evidence_class=EvidenceClass.HISTORICAL,
            retrieval=RetrievalEvidence(
                uri=source_url,
                retrieved_at=retrieved_at,
                acquisition_method=AcquisitionMethod.DOWNLOAD,
                status=AcquisitionStatus.SUCCEEDED,
            ),
        )
        event_path = Path(
            f"quality/bronze/imported-acquisitions/{source_id}/{acquisition_id}.json"
        )
        event_bytes = event.canonical_json() + b"\n"
        output[event_path] = event_bytes

        pinned_url = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{path}"
        b2 = build_raw_evidence_reference_from_acquisition(
            event, external_reference=pinned_url, kind=RawEvidenceKind.PAYLOAD
        )
        manifest = RawEvidenceManifest.from_rows((b2,))
        b2_path = Path(
            f"quality/bronze/raw-evidence/{source_id}/{acquisition_id}/manifest.json"
        )
        b2_bytes = manifest.canonical_json()
        output[b2_path] = b2_bytes

        decision = create_admission_decision(
            acquisition_id=acquisition_id,
            content_id=receipt["sha256"],
            state=BronzeAdmissionState.LANDED,
            reason_codes=(
                "m112_existing_pbs_utilisation_raw_object_anonymously_verified",
            ),
            validation_results=(
                ValidationResult(
                    check_id="anonymous-raw-sha256",
                    passed=True,
                    message=f"revision:{REVISION};path:{path};sha256:{receipt['sha256']};evidence:{readback['readback_url']}",
                ),
                ValidationResult(
                    check_id="anonymous-raw-byte-count",
                    passed=True,
                    message=f"revision:{REVISION};path:{path};bytes:{receipt['byte_count']};evidence:{readback['readback_url']}",
                ),
            ),
            reviewer_status="unreviewed",
            actor=ACTOR,
            decided_at=DECIDED_AT,
        )
        admission_path = Path(
            f"quality/bronze/admissions/{source_id}/{acquisition_id}/{decision.decision_id}.json"
        )
        admission_bytes = (
            decision.model_dump_json(exclude_none=False).encode() + b"\n"
        )
        output[admission_path] = admission_bytes
        rows.append({
            "dataset": DATASET,
            "revision": REVISION,
            "path": path,
            "source_id": source_id,
            "category": receipt["category"],
            "receipt_path": receipt["receipt_path"],
            "receipt_sha256": receipt["receipt_sha256"],
            "receipt_bytes": receipt["receipt_bytes"],
            "acquisition_id": acquisition_id,
            "content_sha256": receipt["sha256"],
            "byte_count": receipt["byte_count"],
            "source_url": source_url,
            "pinned_b2_reference": pinned_url,
            "acquisition_event_path": event_path.as_posix(),
            "b2_manifest_path": b2_path.as_posix(),
            "b2_manifest_sha256": hashlib.sha256(b2_bytes).hexdigest(),
            "landed_admission_path": admission_path.as_posix(),
            "landed_admission_sha256": hashlib.sha256(
                admission_bytes
            ).hexdigest(),
            "lineage_complete": True,
            "reviewer_status": "unreviewed",
            "rights_state": "unknown",
            "v4_admission": False,
            "consumer_canary": False,
        })

    inputs = (
        AUDIT_PATH,
        READBACK_PATH,
        FROZEN_PATH,
        BASE_PATH,
        DIGEST_REPORT_PATH,
    )
    report = {
        "schema_id": "global-medicines-atlas.pbs-utilisation-landed-lineage",
        "schema_version": 1,
        "recorded_at": DECIDED_AT.isoformat().replace("+00:00", "Z"),
        "status": "six_frozen_pbs_utilisation_b1_b2_lineages_landed_unreviewed",
        "scope": {
            "dataset": DATASET,
            "revision": REVISION,
            "frozen_inventory_member_count": EXPECTED_OBJECTS,
            "lineages_completed": len(rows),
            "rights_concluded": False,
            "v4_admission": False,
            "consumer_canaries": False,
        },
        "input_bindings": {path.as_posix(): _sha256(path) for path in inputs},
        "objects": rows,
        "output_bindings": {
            path.as_posix(): hashlib.sha256(body).hexdigest()
            for path, body in sorted(
                output.items(), key=lambda item: item[0].as_posix()
            )
        },
        "boundaries": {
            "new_sources_added": False,
            "frozen_denominator_changed": False,
            "source_payload_bytes_read": False,
            "source_payload_bytes_retained": False,
            "source_payload_values_inspected": False,
            "rights_or_licensing_conclusion_added": False,
            "v4_admission_performed": False,
            "consumer_canary_performed": False,
        },
    }
    if len(rows) != EXPECTED_OBJECTS or len(output) != EXPECTED_OBJECTS * 3:
        raise ValueError("PBS utilisation lineage output scope changed")
    return report, output


def main() -> None:
    report, outputs = build_report()
    for path, body in sorted(
        outputs.items(), key=lambda item: item[0].as_posix()
    ):
        destination = ROOT / path
        if destination.exists() and destination.read_bytes() != body:
            raise ValueError(f"append-only evidence differs: {path}")
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(body)
    destination = ROOT / OUTPUT_PATH
    body = _canonical(report)
    if destination.exists() and destination.read_bytes() != body:
        raise ValueError(f"append-only qualification differs: {OUTPUT_PATH}")
    if not destination.exists():
        destination.write_bytes(body)
    print(
        json.dumps(
            {
                "qualification": OUTPUT_PATH.as_posix(),
                "objects": len(report["objects"]),
                "artifacts": len(outputs),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
