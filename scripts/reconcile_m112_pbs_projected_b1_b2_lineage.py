"""Bind pinned PBS B1/B2 projection joins to current unreviewed landings.

Only existing, pinned metadata qualifications are read. No source payload is
downloaded or inspected, and producer-owned records are never modified.
"""

from __future__ import annotations

import copy
import hashlib
import json
import operator
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

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
    RetrievalEvidence,
    RightsState,
)

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
BASE = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261019-mbs-bronze-projection-lineage.json"
)
PROJECTED_JOINS = (
    QUAL / "australian-m112-projected-b1-b2-path-joins-20261019.json"
)
OUTPUT = QUAL / "australian-m112-pbs-projected-b1-b2-lineage-20261019.json"
OVERLAY_OUTPUT = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261019-pbs-projected-b1-b2-lineage.json"
)
PRODUCER_REPOSITORY = "edithatogo/reimbursement-atlas"
PRODUCER_REVISION = "a93516ed416118bc51c1db2b71ab540fa4d0fe52"
EXPECTED_OBJECTS = 1703
EXPECTED_ACQUISITIONS = 1702
EXPECTED_PRIOR_RAW_LINEAGES = 22
EXPECTED_PRIOR_PROJECTION_LINEAGES = 10
EXPECTED_DENOMINATOR = 1759
EXPECTED_PROJECTION_COUNT = 23
DECIDED_AT = datetime(2026, 10, 18, 21, 34, 5, tzinfo=UTC)
ACTOR = "global-medicines-atlas:m112-pbs-projected-lineage"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _object(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"expected an object: {context}")
    return cast("dict[str, Any]", value)


def _rows(value: object, context: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise TypeError(f"expected object rows: {context}")
    return [_object(item, context) for item in cast("list[object]", value)]


def _read(path: Path) -> dict[str, Any]:
    return _object(
        json.loads((ROOT / path).read_text(encoding="utf-8")), str(path)
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _producer_event_id(value: str, content_sha256: str) -> str:
    if not value.startswith("event:"):
        raise ValueError("producer B1 event id is not namespaced")
    event_id = value.removeprefix("event:")
    if not SHA256.fullmatch(event_id) or event_id == content_sha256:
        raise ValueError("producer B1 event id does not bind a distinct event")
    return event_id


def _validate_frozen_identity(
    row: dict[str, Any], target: dict[str, Any]
) -> str:
    digest = row.get("sha256")
    byte_count = row.get("byte_count")
    identity = target["identity"]
    frozen_gate_matches = all((
        target["candidate_class"] == "raw_source_payload",
        target["approved_denominator_member"] is True,
        target["b1_b2_lineage"]["complete"] is False,
        target["disposition"] == "deferred_not_admitted",
        target["v4_admission"] is False,
        target["consumer_canary"] is False,
        identity["sha256"] == digest,
        identity["byte_count"] == byte_count,
        isinstance(digest, str) and SHA256.fullmatch(digest) is not None,
        isinstance(byte_count, int),
    ))
    if not frozen_gate_matches:
        raise ValueError(
            "frozen PBS object identity or independent gates changed"
        )
    if not all((
        row.get("b1_source_id") == "au_pbs",
        row.get("b1_acquisition_id") == f"sha256:{digest}",
        row.get("b1_b2_lineage_complete_before_receipt_audit") is False,
        row.get("disposition") == "projection_join_candidate_only",
        row.get("unresolved_roles") == ["persisted landed-admission history"],
    )):
        raise ValueError("PBS B1/B2 projection role disposition changed")
    return cast("str", digest)


def _validate_receipt_projection(row: dict[str, Any]) -> None:
    receipt = _object(
        row.get("source_receipt_binding"), "source receipt binding"
    )
    paths = {
        "data/derived/historical_sources/historical_source_downloads.jsonl",
        "data/derived/historical_sources/pbs_archive_v1/historical_source_downloads.jsonl",
        "data/derived/historical_sources/pbs_structured_archive_v1/historical_source_downloads.jsonl",
    }
    receipt_sha = receipt.get("receipt_record_sha256")
    checks = (
        receipt.get("evidence_kind")
        == "producer_historical_source_download_receipt_projection",
        receipt.get("receipt_projection_path") in paths,
        isinstance(receipt_sha, str),
        isinstance(receipt_sha, str)
        and SHA256.fullmatch(receipt_sha) is not None,
    )
    if not all(checks):
        raise ValueError(
            "PBS source receipt projection reference is incomplete"
        )


def _validate_source_acquisition(row: dict[str, Any]) -> str:
    locator = row.get("b1_source_locator")
    parsed = urlsplit(locator) if isinstance(locator, str) else None
    checks = (
        parsed is not None,
        parsed is not None and parsed.scheme == "https",
        parsed is not None and parsed.hostname == "www.pbs.gov.au",
        bool(row.get("b1_source_version_id")),
        bool(row.get("b1_retrieved_at")),
    )
    if not all(checks):
        raise ValueError("PBS source acquisition metadata is incomplete")
    return cast("str", row.get("b1_event_id"))


def _validate_b2_projection(row: dict[str, Any], digest: str) -> None:
    if not all((
        row.get("b2_evidence_id") == f"evidence:sha256:{digest}",
        row.get("b2_immutable_locator") == f"sha256:{digest}",
        row.get("b2_projection_linked") is True,
    )):
        raise ValueError(
            "PBS B2 projection identity does not match the payload"
        )


def projection_key(row: dict[str, Any]) -> tuple[str, str, str]:
    values = (row.get("dataset"), row.get("revision"), row.get("path"))
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError("PBS projection join lacks a complete object key")
    return cast("tuple[str, str, str]", values)


def _validate_projection_row(
    row: dict[str, Any],
    frozen: dict[tuple[str, str, str], dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    key = projection_key(row)
    target = frozen.get(key)
    if target is None:
        raise ValueError("PBS projection join is outside the frozen inventory")
    digest = _validate_frozen_identity(row, target)
    _validate_receipt_projection(row)
    event_id = _producer_event_id(_validate_source_acquisition(row), digest)
    _validate_b2_projection(row, digest)
    return target, event_id


def build_report() -> tuple[dict[str, Any], dict[Path, bytes], dict[str, Any]]:  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements] -- keep the exact 1,703-path projection-to-record expansion auditable and fail closed in one pass
    """Create local B1/B2 reference and landed records from exact projections."""
    base = _read(BASE)
    projected = _read(PROJECTED_JOINS)
    baseline_matches = all((
        base["scope"]["approved_denominator"] == EXPECTED_DENOMINATOR,
        base["updated_gate_totals"]["complete_raw_b1_b2_lineage"]
        == EXPECTED_PRIOR_RAW_LINEAGES,
        base["updated_gate_totals"]["complete_projection_lineage"]
        == EXPECTED_PRIOR_PROJECTION_LINEAGES,
        base["scope"]["denominator_changed"] is False,
        projected["source_receipt_readback"]["producer_repository"]
        == PRODUCER_REPOSITORY,
        projected["source_receipt_readback"]["producer_repository_revision"]
        == PRODUCER_REVISION,
        projected["source_receipt_readback"][
            "projection_matches_still_missing_persisted_landed_admission_history"
        ]
        == EXPECTED_OBJECTS,
    ))
    if not baseline_matches:
        raise ValueError("M-112 baseline or pinned producer scope changed")

    frozen_rows = _rows(base["objects"], "frozen M-112 objects")
    frozen = {
        (row["dataset"], row["revision"], row["path"]): row
        for row in frozen_rows
    }
    if len(frozen) != EXPECTED_DENOMINATOR:
        raise ValueError("frozen inventory is not unique and complete")
    projection_rows = [
        row
        for row in _rows(
            projected["projection_matches"], "PBS projection matches"
        )
        if row.get("b1_source_id") == "au_pbs"
    ]
    if len(projection_rows) != EXPECTED_OBJECTS:
        raise ValueError("PBS projection join denominator changed")

    grouped: dict[str, list[tuple[dict[str, Any], dict[str, Any], str]]] = {}
    seen_paths: set[tuple[str, str, str]] = set()
    for row in projection_rows:
        target, event_id = _validate_projection_row(row, frozen)
        key = (row["dataset"], row["revision"], row["path"])
        if key in seen_paths:
            raise ValueError("duplicate PBS path projection join")
        seen_paths.add(key)
        grouped.setdefault(event_id, []).append((row, target, event_id))
    if len(grouped) != EXPECTED_ACQUISITIONS:
        raise ValueError("PBS path aliases or acquisition count changed")

    outputs: dict[Path, bytes] = {}
    report_objects: list[dict[str, Any]] = []
    output_bindings: dict[str, str] = {}
    for event_id, members in sorted(grouped.items()):
        first, _, _ = members[0]
        digest = first["sha256"]
        if any(
            row["sha256"] != digest
            or row["b1_source_version_id"] != first["b1_source_version_id"]
            or row["b1_source_locator"] != first["b1_source_locator"]
            or row["b1_retrieved_at"] != first["b1_retrieved_at"]
            or row["b2_immutable_locator"] != first["b2_immutable_locator"]
            for row, _, _ in members
        ):
            raise ValueError(
                "one producer event maps to conflicting PBS identities"
            )
        retrieved_at = datetime.fromisoformat(first["b1_retrieved_at"])
        event = AcquisitionEvent(
            acquisition_id=event_id,
            content_id=digest,
            source_id="au_pbs",
            source_version=first["b1_source_version_id"],
            retrieved_at=retrieved_at,
            payload_sha256=digest,
            retrieval=RetrievalEvidence(
                uri=AnyUrl(first["b1_source_locator"]),
                retrieved_at=retrieved_at,
                acquisition_method=AcquisitionMethod.DOWNLOAD,
                status=AcquisitionStatus.SUCCEEDED,
            ),
            rights_state=RightsState.UNKNOWN,
            evidence_class=EvidenceClass.HISTORICAL,
        )
        acquisition_path = Path(
            f"quality/bronze/imported-acquisitions/au-pbs/{event_id}.json"
        )
        acquisition_bytes = event.canonical_json() + b"\n"
        outputs[acquisition_path] = acquisition_bytes

        b2_record = RawEvidenceRecord(
            source_id="au_pbs",
            acquisition_id=event_id,
            content_id=digest,
            kind=RawEvidenceKind.PAYLOAD,
            state=RawEvidenceState.EXTERNAL_REFERENCE_ONLY,
            external_reference=first["b2_immutable_locator"],
            payload_contents_in_metadata=False,
        )
        b2_manifest = RawEvidenceManifest.from_rows((b2_record,))
        b2_path = Path(
            f"quality/bronze/raw-evidence/au-pbs/{event_id}/manifest.json"
        )
        b2_bytes = b2_manifest.canonical_json()
        outputs[b2_path] = b2_bytes

        validations = [
            ValidationResult(
                check_id="producer-b1-b2-projection-join",
                passed=True,
                message=(
                    f"producer:{PRODUCER_REPOSITORY}@{PRODUCER_REVISION};"
                    f"b1_event_id:event:{event_id};"
                    f"b2_evidence_id:evidence:sha256:{digest};"
                    f"b2_locator:sha256:{digest}"
                ),
            ),
        ]
        for row, _, _ in sorted(members, key=lambda item: item[0]["path"]):
            validations.append(
                ValidationResult(
                    check_id="frozen-pbs-object-identity",
                    passed=True,
                    message=(
                        f"dataset:{row['dataset']};revision:{row['revision']};"
                        f"path:{row['path']};sha256:{digest};"
                        f"bytes:{row['byte_count']}"
                    ),
                )
            )
        decision = create_admission_decision(
            acquisition_id=event_id,
            content_id=digest,
            state=BronzeAdmissionState.LANDED,
            reason_codes=("m112_existing_pbs_lineage_bound",),
            validation_results=tuple(validations),
            reviewer_status="unreviewed",
            actor=ACTOR,
            decided_at=DECIDED_AT,
        )
        admission_path = Path(
            f"quality/bronze/admissions/au-pbs/{event_id}/"
            f"{decision.decision_id}.json"
        )
        admission_bytes = (
            decision.model_dump_json(exclude_none=False).encode() + b"\n"
        )
        outputs[admission_path] = admission_bytes
        for path, body in (
            (acquisition_path, acquisition_bytes),
            (b2_path, b2_bytes),
            (admission_path, admission_bytes),
        ):
            output_bindings[path.as_posix()] = hashlib.sha256(body).hexdigest()

        for row, target, _ in members:
            receipt = row["source_receipt_binding"]
            report_objects.append({
                "dataset": row["dataset"],
                "revision": row["revision"],
                "path": row["path"],
                "content_sha256": digest,
                "byte_count": row["byte_count"],
                "identity_evidence": {
                    "sha256_evidence": target["identity"]["sha256_evidence"],
                    "qualification_path": target["identity"]["digest_evidence"][
                        "path"
                    ]
                    if target["identity"].get("digest_evidence")
                    else target["identity"]["tree_inventory_evidence"]["path"],
                },
                "source_receipt_projection": {
                    "repository": PRODUCER_REPOSITORY,
                    "revision": PRODUCER_REVISION,
                    "path": receipt["receipt_projection_path"],
                    "record_sha256": receipt["receipt_record_sha256"],
                },
                "producer_b1": {
                    "acquisition_id": row["b1_acquisition_id"],
                    "event_id": row["b1_event_id"],
                    "source_id": row["b1_source_id"],
                    "source_version_id": row["b1_source_version_id"],
                    "source_locator": row["b1_source_locator"],
                    "retrieved_at": row["b1_retrieved_at"],
                },
                "producer_b2": {
                    "evidence_id": row["b2_evidence_id"],
                    "immutable_locator": row["b2_immutable_locator"],
                    "fixity_verified_at": row["b2_fixity_verified_at"],
                },
                "local_records": {
                    "acquisition_event_path": acquisition_path.as_posix(),
                    "b2_manifest_path": b2_path.as_posix(),
                    "b2_manifest_sha256": output_bindings[b2_path.as_posix()],
                    "landed_admission_path": admission_path.as_posix(),
                    "landed_admission_sha256": output_bindings[
                        admission_path.as_posix()
                    ],
                },
                "lineage_complete": True,
                "reviewer_status": "unreviewed",
                "processing_admission": False,
                "rights_concluded": False,
                "v4_admission": False,
                "consumer_canary": False,
            })

    report_objects.sort(key=operator.itemgetter("dataset", "path"))
    if (
        len(report_objects) != EXPECTED_OBJECTS
        or len(outputs) != EXPECTED_ACQUISITIONS * 3
    ):
        raise ValueError("PBS lineage output denominator changed")

    input_bindings = {
        path.as_posix(): _sha256(path) for path in (BASE, PROJECTED_JOINS)
    }
    report = {
        "schema_id": "global-medicines-atlas.m112-pbs-projected-b1-b2-lineage",
        "schema_version": 1,
        "recorded_at": DECIDED_AT.isoformat().replace("+00:00", "Z"),
        "status": "1703_frozen_pbs_raw_paths_landed_unreviewed",
        "scope": {
            "producer_repository": PRODUCER_REPOSITORY,
            "producer_revision": PRODUCER_REVISION,
            "frozen_inventory_objects": EXPECTED_DENOMINATOR,
            "objects": len(report_objects),
            "unique_acquisition_events": len(grouped),
            "source_receipt_projection_joins": len(report_objects),
            "lineages_completed": len(report_objects),
            "all_objects_remain_deferred": True,
            "processing_admission": False,
            "v4_admission": False,
            "consumer_canaries": False,
        },
        "input_bindings": input_bindings,
        "output_bindings": dict(sorted(output_bindings.items())),
        "objects": report_objects,
        "boundaries": {
            "new_sources_added": False,
            "frozen_denominator_changed": False,
            "source_payload_bytes_read": False,
            "source_payload_bytes_retained_locally": False,
            "source_payload_values_inspected": False,
            "producer_b1_b2_or_source_owner_records_modified": False,
            "rights_or_licensing_conclusion_added": False,
            "source_owner_records_modified": False,
            "processing_admission_performed": False,
            "v4_admission_performed": False,
            "consumer_canary_performed": False,
        },
    }
    overlay = copy.deepcopy(base)
    report_path = OUTPUT.as_posix()
    report_bytes = (
        json.dumps(report, ensure_ascii=False, indent=2).encode() + b"\n"
    )
    report_sha = hashlib.sha256(report_bytes).hexdigest()
    for lineage in report_objects:
        key = (lineage["dataset"], lineage["revision"], lineage["path"])
        target = next(
            row
            for row in overlay["objects"]
            if (row["dataset"], row["revision"], row["path"]) == key
        )
        target["b1_b2_lineage"] = {
            "complete": True,
            "state": "complete: pinned producer B1 source receipt/acquisition and B2 references join to a current unreviewed local landed record",
            "evidence": {"path": report_path, "sha256": report_sha},
        }
    totals = overlay["updated_gate_totals"]
    totals["complete_raw_b1_b2_lineage"] += EXPECTED_OBJECTS
    totals["complete_raw_b1_b2_lineage_paths"] += EXPECTED_OBJECTS
    totals["complete_b1_b2_lineage_objects"] += EXPECTED_OBJECTS
    overlay["lineage_counts_after_expansion"] = {
        "complete_raw_lineages": totals["complete_raw_b1_b2_lineage"],
        "incomplete_raw_lineages": EXPECTED_DENOMINATOR
        - EXPECTED_PROJECTION_COUNT
        - totals["complete_raw_b1_b2_lineage"],
        "complete_projection_lineages": totals["complete_projection_lineage"],
        "incomplete_projection_lineages": EXPECTED_PROJECTION_COUNT
        - totals["complete_projection_lineage"],
        "complete_lineage_objects": totals["complete_b1_b2_lineage_objects"],
        "inventory_objects": EXPECTED_DENOMINATOR,
    }
    overlay["current_b1_b2_lineage_expansion"] = {
        "prior_complete_raw_lineages": EXPECTED_PRIOR_RAW_LINEAGES,
        "new_complete_raw_lineages": EXPECTED_OBJECTS,
        "complete_raw_lineages_after_expansion": totals[
            "complete_raw_b1_b2_lineage"
        ],
        "objects": report_objects,
        "input_bindings": input_bindings,
        "qualification": {"path": report_path, "sha256": report_sha},
        "boundaries": report["boundaries"],
    }
    return report, outputs, overlay


def _write_append_only(path: Path, body: bytes) -> None:
    destination = ROOT / path
    if destination.exists():
        if destination.read_bytes() != body:
            raise ValueError(f"append-only evidence differs: {path}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(body)


def main() -> None:
    report, outputs, overlay = build_report()
    report_bytes = (
        json.dumps(report, ensure_ascii=False, indent=2).encode() + b"\n"
    )
    overlay_bytes = (
        json.dumps(overlay, ensure_ascii=False, separators=(",", ":")).encode()
        + b"\n"
    )
    for path, body in outputs.items():
        _write_append_only(path, body)
    _write_append_only(OUTPUT, report_bytes)
    _write_append_only(OVERLAY_OUTPUT, overlay_bytes)
    print(
        json.dumps(
            {
                "qualification": OUTPUT.as_posix(),
                "overlay": OVERLAY_OUTPUT.as_posix(),
                "objects": len(report["objects"]),
                "unique_acquisition_events": report["scope"][
                    "unique_acquisition_events"
                ],
                "local_records": len(outputs),
                "complete_raw_lineages_after": overlay["updated_gate_totals"][
                    "complete_raw_b1_b2_lineage"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
