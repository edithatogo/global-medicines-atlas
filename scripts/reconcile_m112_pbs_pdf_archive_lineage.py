"""Bind the five frozen PBS archive PDFs to exact new B1/B2 records."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from operator import itemgetter
from pathlib import Path
from typing import Any, cast

from pydantic import AnyUrl

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionState,
    ValidationResult,
    create_admission_decision,
)
from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceKind,
    RawEvidenceManifest,
    RawEvidenceRecord,
    RawEvidenceState,
)
from global_medicines_atlas.receipts import (
    AcquisitionEvent,
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    HttpRetrievalEvidence,
    RetrievalEvidence,
    RightsState,
    acquisition_event_id_for,
)

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
BASE = QUAL / (
    "australian-m112-per-object-gate-reconciliation-20261019-"
    "pbs-utilisation-lineage.json"
)
READBACK = QUAL / "australian-m112-pbs-pdf-archive-readback-20261019.json"
OUTPUT = QUAL / "australian-m112-pbs-pdf-archive-lineage-20261019.json"
OVERLAY_OUTPUT = QUAL / (
    "australian-m112-per-object-gate-reconciliation-20261019-"
    "pbs-pdf-archive-lineage.json"
)
DATASET = "edithatogo/reimbursement-atlas"
REVISION = "8e062578f14e12cf3238700a93946339da9c5d88"
OWNER_REPOSITORY = "edithatogo/reimbursement-atlas"
OWNER_REVISION = "083be8aa4ff0f8d8e6df5c5d8242f7783be149de"
OWNER_METADATA_PATH = (
    "data/derived/publication/pbs_provenance/pbs_archive_variants.jsonl"
)
EXPECTED_DENOMINATOR = 1759
EXPECTED_PRIOR_RAW = 1731
EXPECTED_PRIOR_PROJECTIONS = 10
EXPECTED_PRIOR_TOTAL = 1741
EXPECTED_ADDITIONS = 5
EXPECTED_COMPLETE_RAW = 1736
EXPECTED_COMPLETE_TOTAL = 1746
EXPECTED_INCOMPLETE_PROJECTIONS = 13
ADMISSION_AT = datetime(2026, 10, 19, 0, 10, 38, tzinfo=UTC)
ACTOR = "global-medicines-atlas:m112-pbs-pdf-archive-lineage"
HTTP_OK = 200
ARCHIVE_TIMESTAMP_LENGTH = 14
SHA256_HEX_LENGTH = 64


def _object(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {context}")
    return cast("dict[str, Any]", value)


def _read(path: Path) -> dict[str, Any]:
    return _object(
        json.loads((ROOT / path).read_text(encoding="utf-8")), str(path)
    )


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


def build_report() -> tuple[dict[str, Any], dict[Path, bytes], dict[str, Any]]:  # ruff: ignore[too-many-statements,too-many-locals] -- keep exact frozen-object, receipt, retrieval, B1/B2, admission and cumulative-gate bindings in one auditable pass
    """Validate exact archive readbacks and build reference-only lineage."""
    base = _read(BASE)
    readback = _read(READBACK)
    totals = base["updated_gate_totals"]
    scope = base["scope"]
    if not all((
        scope["approved_denominator"] == EXPECTED_DENOMINATOR,
        scope["denominator_changed"] is False,
        totals["complete_raw_b1_b2_lineage"] == EXPECTED_PRIOR_RAW,
        totals["complete_projection_lineage"] == EXPECTED_PRIOR_PROJECTIONS,
        totals["complete_b1_b2_lineage_objects"] == EXPECTED_PRIOR_TOTAL,
        totals["v4_admissions"] == 0,
        totals["consumer_canaries"] == 0,
        readback["inventory"]["dataset"] == DATASET,
        readback["inventory"]["revision"] == REVISION,
        readback["inventory"]["frozen_denominator"] == EXPECTED_DENOMINATOR,
        readback["inventory"]["base_sha256"] == _sha(BASE),
        readback["source_owner_metadata"]["repository"] == OWNER_REPOSITORY,
        readback["source_owner_metadata"]["revision"] == OWNER_REVISION,
        readback["source_owner_metadata"]["path"] == OWNER_METADATA_PATH,
        readback["anonymous"] is True,
        len(readback["objects"]) == EXPECTED_ADDITIONS,
    )):
        raise ValueError("PBS PDF readback or M-112 baseline changed")

    frozen = {
        (row["dataset"], row["revision"], row["path"]): row
        for row in base["objects"]
    }
    if len(frozen) != EXPECTED_DENOMINATOR:
        raise ValueError("M-112 frozen inventory is not unique")

    artifacts: dict[Path, bytes] = {}
    output_bindings: dict[str, str] = {}
    report_objects: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in readback["objects"]:
        key = (item["dataset"], item["revision"], item["path"])
        target = frozen.get(key)
        receipt = _object(
            item.get("producer_archive_variant_receipt"),
            "producer archive variant receipt",
        )
        sha = cast("str", item.get("sha256_observed"))
        byte_count = cast("int", item.get("byte_count_observed"))
        read_at = datetime.fromisoformat(item["retrieved_at"])
        replay_uri = cast("str", receipt.get("archive_replay_url"))
        archive_timestamp = cast("str", receipt.get("archive_timestamp"))
        source_id = cast("str", receipt.get("source_id"))
        if key in seen:
            raise ValueError("duplicate PBS PDF inventory member")
        seen.add(key)
        if target is None or not all((
            key[0] == DATASET,
            key[1] == REVISION,
            target["candidate_class"] == "raw_source_payload",
            target["approved_denominator_member"] is True,
            target["disposition"] == "deferred_not_admitted",
            target["b1_b2_lineage"]["complete"] is False,
            target["v4_admission"] is False,
            target["consumer_canary"] is False,
            target["identity"]["sha256"] == item["sha256_expected"] == sha,
            target["identity"]["byte_count"]
            == item["byte_count_expected"]
            == byte_count,
            item["http_status"] == HTTP_OK,
            item["content_length"] == str(byte_count),
            item["final_host"] == "web.archive.org",
            item["payload_persisted_locally"] is False,
            item["payload_values_inspected"] is False,
            receipt.get("checksum_sha256") == sha,
            receipt.get("byte_size") == byte_count,
            receipt.get("raw_redistribution_status")
            == "blocked_pending_explicit_permission",
            source_id.startswith("au_pbs_archive_"),
            len(archive_timestamp) == ARCHIVE_TIMESTAMP_LENGTH,
            replay_uri.startswith("https://web.archive.org/"),
            item["producer_record_sha256"]
            and len(item["producer_record_sha256"]) == SHA256_HEX_LENGTH,
            isinstance(item.get("producer_record_jsonl"), str)
            and hashlib.sha256(
                item["producer_record_jsonl"].encode("utf-8")
            ).hexdigest()
            == item["producer_record_sha256"],
            {
                key: json.loads(item["producer_record_jsonl"])[key]
                for key in receipt
            }
            == receipt,
            read_at.tzinfo is not None,
        )):
            raise ValueError(
                "PBS PDF readback or source receipt binding changed"
            )

        acquisition_id = acquisition_event_id_for(
            source_id=source_id,
            payload_sha256=sha,
            retrieved_at=read_at,
            source_version=archive_timestamp,
            original_uri=replay_uri,
        )
        event = AcquisitionEvent(
            acquisition_id=acquisition_id,
            content_id=sha,
            source_id=source_id,
            source_version=archive_timestamp,
            retrieved_at=read_at,
            payload_sha256=sha,
            retrieval=RetrievalEvidence(
                uri=AnyUrl(replay_uri),
                retrieved_at=read_at,
                acquisition_method=AcquisitionMethod.DOWNLOAD,
                status=AcquisitionStatus.SUCCEEDED,
                http=HttpRetrievalEvidence(
                    original_uri=AnyUrl(replay_uri),
                    http_method="GET",
                    http_status=HTTP_OK,
                    content_length=byte_count,
                    observed_byte_length=byte_count,
                    source_native_version=archive_timestamp,
                    acquisition_agent_version="m112-pbs-pdf-archive-readback-v1",
                ),
            ),
            rights_state=RightsState.UNKNOWN,
            evidence_class=EvidenceClass.HISTORICAL,
        )
        event_path = Path(
            f"quality/bronze/imported-acquisitions/au-pbs-archive/{acquisition_id}.json"
        )
        event_bytes = event.canonical_json() + b"\n"
        artifacts[event_path] = event_bytes

        b2_row = RawEvidenceRecord(
            source_id=source_id,
            acquisition_id=acquisition_id,
            content_id=sha,
            kind=RawEvidenceKind.PAYLOAD,
            state=RawEvidenceState.EXTERNAL_REFERENCE_ONLY,
            external_reference=replay_uri,
            payload_contents_in_metadata=False,
        )
        b2_manifest = RawEvidenceManifest.from_rows((b2_row,))
        b2_path = Path(
            f"quality/bronze/raw-evidence/au-pbs-archive/{acquisition_id}/manifest.json"
        )
        b2_bytes = b2_manifest.canonical_json()
        artifacts[b2_path] = b2_bytes

        admission = create_admission_decision(
            acquisition_id=acquisition_id,
            content_id=sha,
            state=BronzeAdmissionState.LANDED,
            reason_codes=(
                "exact_existing_archive_variant_retrieved",
                "rights_unresolved",
                "unreviewed_not_admitted_to_processing",
            ),
            validation_results=(
                ValidationResult(
                    check_id="exact-source-digest-and-size",
                    passed=True,
                    message="streamed SHA-256 and byte count match the frozen member and producer receipt",
                ),
            ),
            reviewer_status="unreviewed",
            actor=ACTOR,
            decided_at=ADMISSION_AT,
        )
        admission_path = Path(
            "quality/bronze/admissions/au-pbs-archive/"
            f"{acquisition_id}/{admission.decision_id}.json"
        )
        admission_bytes = admission.model_dump_json().encode("utf-8") + b"\n"
        artifacts[admission_path] = admission_bytes

        output_bindings[event_path.as_posix()] = hashlib.sha256(
            event_bytes
        ).hexdigest()
        output_bindings[b2_path.as_posix()] = hashlib.sha256(
            b2_bytes
        ).hexdigest()
        output_bindings[admission_path.as_posix()] = hashlib.sha256(
            admission_bytes
        ).hexdigest()
        report_objects.append({
            "dataset": key[0],
            "revision": key[1],
            "path": key[2],
            "content_sha256": sha,
            "byte_count": byte_count,
            "producer_archive_variant_receipt": receipt,
            "producer_record_sha256": item["producer_record_sha256"],
            "retrieval": {
                "uri": replay_uri,
                "retrieved_at": read_at.isoformat().replace("+00:00", "Z"),
                "http_status": HTTP_OK,
                "content_length": byte_count,
                "sha256": sha,
                "byte_count": byte_count,
                "payload_persisted_locally": False,
                "payload_values_inspected": False,
            },
            "source_id": source_id,
            "source_version": archive_timestamp,
            "rights_state": "unknown",
            "acquisition_id": acquisition_id,
            "acquisition_event_path": event_path.as_posix(),
            "b2_manifest_path": b2_path.as_posix(),
            "b2_manifest_sha256": output_bindings[b2_path.as_posix()],
            "landed_admission_path": admission_path.as_posix(),
            "landed_admission_sha256": output_bindings[
                admission_path.as_posix()
            ],
            "admission_state": admission.state.value,
            "reviewer_status": admission.reviewer_status,
            "v4_admission": False,
            "consumer_canary": False,
        })

    if len(report_objects) != EXPECTED_ADDITIONS:
        raise ValueError("PBS PDF lineage count changed")
    streamed_bytes = sum(row["byte_count"] for row in report_objects)
    observed_at = readback["recorded_at"]
    lineage = cast(
        "dict[str, Any]",
        {
            "schema_id": "global-medicines-atlas.m112-pbs-pdf-archive-lineage",
            "schema_version": 1,
            "recorded_at": observed_at,
            "status": "five_exact_pbs_archive_pdf_lineages_landed_unreviewed",
            "scope": {
                "dataset": DATASET,
                "revision": REVISION,
                "frozen_inventory_member_count": EXPECTED_ADDITIONS,
                "lineages_completed": EXPECTED_ADDITIONS,
                "rights_concluded": False,
                "v4_admission": False,
                "consumer_canaries": False,
            },
            "source_owner_metadata": readback["source_owner_metadata"],
            "readback_evidence_path": READBACK.as_posix(),
            "readback_evidence_sha256": _sha(READBACK),
            "objects": sorted(report_objects, key=itemgetter("path")),
            "output_bindings": output_bindings,
            "boundaries": {
                "approved_denominator_changed": False,
                "new_source_or_dataset_added": False,
                "source_owner_repository_modified": False,
                "source_payload_bytes_streamed": streamed_bytes,
                "source_payload_bytes_persisted": False,
                "source_payload_values_inspected": False,
                "rights_or_licensing_conclusion_added": False,
                "all_landed_admissions_unreviewed": True,
                "v4_admissions": 0,
                "consumer_canaries": 0,
            },
        },
    )
    result = copy.deepcopy(base)
    lineage_sha = hashlib.sha256(
        json.dumps(lineage, ensure_ascii=False, indent=2).encode() + b"\n"
    ).hexdigest()
    result["purpose"] = (
        "Preserve the frozen 1,759-object inventory while binding five exact "
        "PBS archive PDF variants to new retrieval-timed B1 events, "
        "reference-only B2 records, and unreviewed landed decisions."
    )
    result["observed_at"] = observed_at
    result["boundaries"].update({
        "source_payload_bytes_read_this_run": True,
        "source_payload_bytes_streamed_this_run": streamed_bytes,
        "source_payload_bytes_persisted_this_run": False,
        "source_payload_values_inspected_this_run": False,
        "projection_bytes_streamed_this_run": 0,
        "rights_or_licensing_conclusion_added": False,
        "source_owner_pbs_m107_and_july_derivative_modified": False,
    })
    for item in lineage["objects"]:
        key = (item["dataset"], item["revision"], item["path"])
        target = next(
            row
            for row in result["objects"]
            if (row["dataset"], row["revision"], row["path"]) == key
        )
        target["b1_b2_lineage"] = {
            "complete": True,
            "state": "exact existing archive receipt plus retrieval-timed B1 event, immutable external-reference B2, and unreviewed landed decision; rights unresolved",
            "evidence": {
                "path": OUTPUT.as_posix(),
                "sha256": lineage_sha,
                "object_path": item["path"],
                "content_sha256": item["content_sha256"],
            },
        }

    updated = result["updated_gate_totals"]
    updated["complete_raw_b1_b2_lineage"] += EXPECTED_ADDITIONS
    updated["complete_raw_b1_b2_lineage_paths"] += EXPECTED_ADDITIONS
    updated["complete_b1_b2_lineage_objects"] += EXPECTED_ADDITIONS
    result["lineage_counts_after_expansion"]["complete_raw_lineages"] += (
        EXPECTED_ADDITIONS
    )
    result["lineage_counts_after_expansion"]["incomplete_raw_lineages"] -= (
        EXPECTED_ADDITIONS
    )
    result["lineage_counts_after_expansion"]["complete_lineage_objects"] += (
        EXPECTED_ADDITIONS
    )
    result["pbs_pdf_archive_lineage_increment"] = {
        "qualification_path": OUTPUT.as_posix(),
        "qualification_sha256": lineage_sha,
        "readback_evidence_path": READBACK.as_posix(),
        "readback_evidence_sha256": _sha(READBACK),
        "new_complete_raw_lineages": EXPECTED_ADDITIONS,
        "complete_raw_lineages_after_expansion": updated[
            "complete_raw_b1_b2_lineage"
        ],
        "complete_lineage_objects_after_expansion": updated[
            "complete_b1_b2_lineage_objects"
        ],
        "source_payload_bytes_streamed": streamed_bytes,
        "rights_concluded": False,
        "v4_admissions": 0,
        "consumer_canaries": 0,
    }
    result["evidence_inputs"].append({
        "path": READBACK.as_posix(),
        "sha256": _sha(READBACK),
    })
    if not all((
        updated["complete_raw_b1_b2_lineage"] == EXPECTED_COMPLETE_RAW,
        updated["complete_projection_lineage"] == EXPECTED_PRIOR_PROJECTIONS,
        updated["complete_b1_b2_lineage_objects"] == EXPECTED_COMPLETE_TOTAL,
        result["lineage_counts_after_expansion"]["incomplete_raw_lineages"]
        == 0,
        result["lineage_counts_after_expansion"][
            "incomplete_projection_lineages"
        ]
        == EXPECTED_INCOMPLETE_PROJECTIONS,
        updated["preserved_deferrals"] == EXPECTED_DENOMINATOR,
        updated["v4_admissions"] == 0,
        updated["consumer_canaries"] == 0,
    )):
        raise ValueError("cumulative M-112 lineage totals changed unexpectedly")
    return lineage, artifacts, result


def main() -> None:
    lineage, artifacts, overlay = build_report()
    for path, body in artifacts.items():
        _write_bound(path, body)
    lineage_body = (
        json.dumps(lineage, ensure_ascii=False, indent=2).encode() + b"\n"
    )
    _write_bound(OUTPUT, lineage_body)
    lineage_sha = hashlib.sha256(lineage_body).hexdigest()
    overlay["pbs_pdf_archive_lineage_increment"]["qualification_sha256"] = (
        lineage_sha
    )
    overlay_body = (
        json.dumps(overlay, ensure_ascii=False, indent=2).encode() + b"\n"
    )
    _write_bound(OVERLAY_OUTPUT, overlay_body)
    print(
        json.dumps(
            {
                "qualification": OUTPUT.as_posix(),
                "qualification_sha256": lineage_sha,
                "overlay": OVERLAY_OUTPUT.as_posix(),
                "complete_raw": overlay["updated_gate_totals"][
                    "complete_raw_b1_b2_lineage"
                ],
                "complete_total": overlay["updated_gate_totals"][
                    "complete_b1_b2_lineage_objects"
                ],
                "incomplete_projection_lineages": overlay[
                    "lineage_counts_after_expansion"
                ]["incomplete_projection_lineages"],
                "rights_concluded": False,
                "v4_admissions": 0,
                "consumer_canaries": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
