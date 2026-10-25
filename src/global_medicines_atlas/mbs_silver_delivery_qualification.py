"""Qualify existing July MBS Silver objects without publishing or adding sources."""

from __future__ import annotations

import hashlib
import io
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pyarrow as pa
import pyarrow.parquet as pq
from jsonschema import Draft202012Validator

from .australian_source_contracts import TargetTable, mbs_field_contracts
from .mbs_silver import iter_mbs_silver_batches
from .mbs_source_silver_parity import (
    DATASET,
    EXPECTED_ROWS,
    MBS_SILVER_OBJECTS,
    SOURCE_OBJECT_BYTES,
    SOURCE_OBJECT_PATH,
    SOURCE_OBJECT_SHA256,
    SOURCE_RECEIPT_SHA256,
    SOURCE_URI,
)
from .receipts import SourceReceipt

PREFIX = "quality/qualifications/"
PINS = {
    f"{PREFIX}australian-mbs-v4-candidate-2025-07/manifest.json": "bbdb1bdac49fc1a7f8399ca02cf52a9b0e3a1fbc31e472e3957f1d278ab39a59",
    f"{PREFIX}australian-mbs-silver-semantic-manifest-20261017.json": "9ad5e2747949b8b7142819e981241c1f74105b3570d78025e654e780241c5882",
    f"{PREFIX}australian-m112-july-mbs-silver-lineage-reviewed-20261019.json": "d64612270ed9d392cac47981732142c890c295a48fbec29a0bedb2b408c88273",
    f"{PREFIX}australian-mbs-v4-public-release-rights-attestation-20261019.json": "28c8c66a20498bf2a426b0ab922d0eff81d3b226a9610ac84d81db687bd7d327",
}
RECEIPT_PATH = "quality/bronze/receipts/au-mbs/bbd662119ebebfdf08baf14c0b15c0dd5c93465910fd4f5309f37ecd37a82b8d.json"
SCOPE = "Exact July 2025 source-native Silver fields; no current-status, payable-benefit, clinical, cross-era, or Gold relationship assertion."
OBJECT_COUNT = 6
Fetch = Callable[[str, int], bytes]


def digest(value: object) -> str:
    """Hash deterministic aggregate evidence, never return native values."""
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
    ).hexdigest()


def verify_payload(payload: bytes, size: int, sha256: str) -> None:
    """Reject a different immutable object before interpreting it."""
    if len(payload) != size or hashlib.sha256(payload).hexdigest() != sha256:
        raise ValueError("pinned object byte count or digest differs")


def compare_table(
    source: bytes, receipt: SourceReceipt, published: bytes, name: str
) -> dict[str, Any]:
    """Compare current replay with published arrays, retaining only aggregates."""
    expected = MBS_SILVER_OBJECTS[name]
    verify_payload(published, expected.byte_count, expected.sha256)
    with io.BytesIO(published) as stream:
        candidate = pq.read_table(stream)  # pyright: ignore[reportUnknownMemberType]
    replay = pa.Table.from_batches(
        tuple(
            iter_mbs_silver_batches(
                source,
                receipt,
                table=cast("TargetTable", name),
                date_format="mbs-dmy",
            )
        )
    )
    schema_equal = replay.schema.equals(candidate.schema, check_metadata=False)
    values_equal = schema_equal and replay.equals(
        candidate, check_metadata=False
    )
    native_equal = replay.column_names == candidate.column_names
    if native_equal:
        for field in mbs_field_contracts():
            if field.target_table == name:
                for old, new in zip(
                    candidate[field.native_name].to_pylist(),
                    replay[field.native_name].to_pylist(),
                    strict=True,
                ):
                    if old is None or new is None:
                        native_equal = False
                        continue
                    if any(
                        old[key] != new[key]
                        for key in ("native_state", "native_value")
                    ):
                        native_equal = False
    replay_hash = digest(replay.to_pylist())
    repeated = pa.Table.from_batches(
        tuple(
            iter_mbs_silver_batches(
                source,
                receipt,
                table=cast("TargetTable", name),
                date_format="mbs-dmy",
                rows_per_batch=257,
            )
        )
    )
    deterministic = replay_hash == digest(repeated.to_pylist())
    if not deterministic:
        raise ValueError("MBS replay differs across batch sizes")
    return {
        "table": name,
        "path": expected.path,
        "sha256": expected.sha256,
        "byte_count": expected.byte_count,
        "row_count": candidate.num_rows,
        "field_count": candidate.num_columns,
        "schema_equal": schema_equal,
        "row_values_equal": values_equal,
        "native_values_preserved": native_equal,
        "deterministic_replay": deterministic,
        "replay_sha256": replay_hash,
        "passed": values_equal
        and native_equal
        and deterministic
        and candidate.num_rows == EXPECTED_ROWS,
    }


def qualify_delivery(  # ruff: ignore[too-many-locals,too-many-statements] - bounded six-object roles
    root: Path, fetch: Fetch, *, producer_commit: str
) -> dict[str, dict[str, Any]]:
    """Evaluate exact roles with fresh primary reads, eviction and restoration.

    The supplied transport must be anonymous and bounded. Only aggregate JSON
    reports are returned. A replay mismatch blocks Silver promotion.
    """
    if re.fullmatch(r"[0-9a-f]{40}", producer_commit) is None:
        raise ValueError("producer commit must be a full Git identity")
    created_at = datetime.now(UTC).isoformat()
    docs: dict[str, dict[str, Any]] = {}
    for path, pin in PINS.items():
        raw = (root / path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != pin:
            raise ValueError("qualification input document digest differs")
        docs[path] = json.loads(raw)
    manifest, semantics, lineage, rights = docs.values()
    expected = {
        obj.path: (obj.byte_count, obj.sha256)
        for obj in MBS_SILVER_OBJECTS.values()
    }
    for items in (
        manifest["objects"],
        lineage["outputs"],
        rights["authorized_objects"],
    ):
        actual = {
            item["path"]: (item["byte_count"], item["sha256"])
            for item in items
            if item["path"].endswith(".parquet")
        }
        if actual != expected:
            raise ValueError("exact six-object evidence set differs")
    if (
        rights.get("public_release_authorized") is not True
        or semantics["source_identity"]["source_sha256"] != SOURCE_OBJECT_SHA256
    ):
        raise ValueError("rights or semantic evidence differs")
    receipt = SourceReceipt.model_validate_json(
        (root / RECEIPT_PATH).read_bytes()
    )
    if receipt.digest() != SOURCE_RECEIPT_SHA256:
        raise ValueError("B1 receipt digest differs")
    source = fetch(SOURCE_URI, SOURCE_OBJECT_BYTES)
    verify_payload(source, SOURCE_OBJECT_BYTES, SOURCE_OBJECT_SHA256)
    revision = rights["dataset_identity"]["revision"]
    cache: dict[str, bytes] = {}
    comparisons: list[dict[str, Any]] = []
    restoration: list[dict[str, Any]] = []
    for name, obj in MBS_SILVER_OBJECTS.items():
        url = f"https://huggingface.co/datasets/{DATASET}/resolve/{revision}/{obj.path}"
        cache[name] = fetch(url, obj.byte_count)
        comparisons.append(compare_table(source, receipt, cache[name], name))
        del cache[name]
        restored = fetch(url, obj.byte_count)
        verify_payload(restored, obj.byte_count, obj.sha256)
        restored_at = datetime.now(UTC).isoformat()
        restoration.append({
            "restored_at": restored_at,
            "path": obj.path,
            "sha256": obj.sha256,
            "byte_count": len(restored),
            "cache_entry_absent_before_restore": name not in cache,
            "restored_from_primary": True,
        })
        del restored
    passed = all(row["passed"] for row in comparisons)
    rights_id = PINS[
        f"{PREFIX}australian-mbs-v4-public-release-rights-attestation-20261019.json"
    ]
    rights_decision = {
        "decision_id": rights_id,
        "status": "approved",
        "scope": SCOPE,
        "reason_codes": [
            "exact_six_maintainer_attestation_instrument_not_independently_reviewed"
        ],
    }
    gates = [
        "exact_identity",
        "reviewed_lineage",
        "exact_output_rights",
        "qualified_source_era",
        "native_preservation",
        "deterministic_replay",
        "published_value_parity",
        "primary_restore",
        "memory_cache_eviction",
    ]
    passed_gates = (
        gates
        if passed
        else [
            gate
            for gate in gates
            if gate
            not in {
                "published_value_parity",
                "native_preservation",
                "deterministic_replay",
            }
        ]
    )
    artifacts: list[dict[str, Any]] = []
    promotions: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for name, obj in MBS_SILVER_OBJECTS.items():
        artifacts.append({
            "artifact_id": obj.path,
            "layer": "silver",
            "sha256": obj.sha256,
            "lineage": {
                "input_artifact_ids": [SOURCE_OBJECT_PATH],
                "input_sha256": [SOURCE_OBJECT_SHA256],
            },
            "rights_decision": rights_decision,
            "promotion_status": "approved_within_scope"
            if passed
            else "blocked",
        })
        promotions.append({
            "decision_id": f"mbs-july-silver:{name}",
            "subject_artifact_id": obj.path,
            "from_layer": "bronze_b2",
            "to_layer": "silver",
            "input_sha256": [SOURCE_OBJECT_SHA256],
            "required_gate_ids": gates,
            "passed_gate_ids": passed_gates,
            "rights_decision": rights_decision,
            "status": "approved" if passed else "blocked",
            "fail_closed": True,
            "reason_codes": [
                "all_required_gates_passed"
                if passed
                else "replay_or_preservation_failed"
            ],
        })
        for field in mbs_field_contracts():
            if field.target_table == name:
                record = {
                    "source_dataset": SOURCE_OBJECT_PATH,
                    "source_field": f"/MBS_XML/Data/{field.native_name}",
                    "transformation_id": "mbs-source-native-silver:mbs-dmy:v1",
                    "output_dataset": obj.path,
                    "output_field": field.native_name,
                    "code_version": f"git:{manifest['producer_commit']}",
                    "input_sha256": SOURCE_OBJECT_SHA256,
                    "output_sha256": obj.sha256,
                    "rights_decision_id": rights_id,
                }
                records.append({"record_id": digest(record), **record})
    v1 = {
        "vocabulary_version": "1.0.0",
        "repository": "global-medicines-atlas",
        "artifacts": artifacts,
        "promotion_decisions": promotions,
    }
    v2 = {"vocabulary_version": "2.0.0", "records": records}
    contract = {
        "contract_id": "au-mbs:2025-07:exact-silver-replay:v1",
        "source_id": "au-mbs",
        "partition_identity": [
            "source_id",
            "archive_period",
            "logical_asset_id",
        ],
        "snapshot_identity": [
            "partition_id",
            "payload_sha256",
            "metadata_sha256",
        ],
        "idempotency_rule": "partition_and_snapshot_sha256",
        "late_arrival_rule": "append_then_replay_partition",
        "correction_rule": "new_snapshot_never_overwrite",
        "supersession_rule": "explicit_acyclic_predecessor",
        "replay_order": ["partition_id", "correction_sequence", "snapshot_id"],
        "deterministic_output_rule": "canonical_json_sha256",
        "missing_payload_rule": "metadata_only_fail_closed",
    }
    partition = digest(["au-mbs", "2025-07", SOURCE_OBJECT_PATH])
    metadata = digest(PINS)
    snapshot = digest([partition, SOURCE_OBJECT_SHA256, metadata])
    steps = [
        {
            "table": row["table"],
            "replay_sha256": row["replay_sha256"],
            "published_value_parity": row["row_values_equal"],
        }
        for row in comparisons
    ]
    v3 = {
        "vocabulary_version": "3.0.0",
        "contracts": [contract],
        "snapshots": [
            {
                "snapshot_id": snapshot,
                "source_id": "au-mbs",
                "source_version_id": "2025-07-version-3",
                "partition_id": partition,
                "partition_value": "au-mbs/2025-07/exact-six-silver",
                "logical_asset_id": digest(SOURCE_OBJECT_PATH),
                "source_url": SOURCE_URI,
                "archive_period": "2025-07",
                "observation_status": "acquired",
                "payload_sha256": SOURCE_OBJECT_SHA256,
                "metadata_sha256": metadata,
                "idempotency_key": digest([partition, snapshot]),
                "correction_sequence": 0,
                "supersedes_snapshot_id": None,
                "late_arriving": False,
                "replay_eligible": True,
                "rights_state": receipt.rights_state.value,
            }
        ],
        "replay_plan": {
            "schema_version": "historical-replay-plan-v1",
            "deterministic": True,
            "eligible_snapshot_count": 1,
            "steps": steps,
            "plan_sha256": digest(steps),
        },
    }
    reports: dict[str, dict[str, Any]] = {
        "v1-conformance": v1,
        "v2-field-lineage": v2,
        "v3-backfill-replay": v3,
    }
    for name, path in (
        ("v1-conformance", "v1/medallion-conformance.schema.json"),
        ("v2-field-lineage", "v2/field-lineage.schema.json"),
        ("v3-backfill-replay", "v3/backfill-replay.schema.json"),
    ):
        Draft202012Validator(
            json.loads((root / "contracts/medallion" / path).read_text())
        ).validate(reports[name])  # pyright: ignore[reportUnknownMemberType]
    validate_role_semantics(v1, v2, v3)
    reports["silver-promotion"] = {
        "status": "approved_within_scope" if passed else "blocked",
        "scope": SCOPE,
        "promotion_decisions": promotions,
        "tables": comparisons,
    }
    reports["primary-restore"] = {
        "status": "passed",
        "objects": restoration,
        "created_at": created_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "object_count": 6,
    }
    reports["cache-cleanup"] = {
        "status": "passed",
        "cache_kind": "explicit_in_memory_object_cache",
        "created_at": created_at,
        "expires_at": datetime.now(UTC).isoformat(),
        "evicted_paths": [obj.path for obj in MBS_SILVER_OBJECTS.values()],
        "remaining_entries": len(cache),
        "source_payload_written_to_disk": False,
        "disk_cache_exercised": False,
    }
    reports["qualification"] = {
        "schema_id": "global-medicines-atlas.mbs-silver-delivery-qualification",
        "schema_version": 1,
        "status": "passed" if passed else "blocked",
        "producer_commit": producer_commit,
        "replay_code_commit": producer_commit,
        "published_producer_commit": manifest["producer_commit"],
        "input_documents": PINS,
        "source_sha256": SOURCE_OBJECT_SHA256,
        "tables": comparisons,
        "role_report_sha256": {
            name: digest(report) for name, report in reports.items()
        },
        "scope": SCOPE,
        "admission_performed": False,
        "publication_performed": False,
        "source_values_included": False,
    }
    return reports


def validate_role_semantics(
    v1: dict[str, Any], v2: dict[str, Any], v3: dict[str, Any]
) -> None:
    """Enforce checksum, subject, gate and replay relations beyond schemas.

    Mirrors the v1 adjacent-promotion checks retained by medallion contract
    conformance, and requires all exact six output/native-field mappings.
    """
    artifacts = {item["artifact_id"]: item for item in v1["artifacts"]}
    if (
        len(artifacts) != OBJECT_COUNT
        or len(v1["promotion_decisions"]) != OBJECT_COUNT
    ):
        raise ValueError("six-object v1 denominator differs")
    for decision in v1["promotion_decisions"]:
        subject = artifacts.get(decision["subject_artifact_id"])
        if (
            subject is None
            or subject["layer"] != decision["to_layer"]
            or (decision["from_layer"], decision["to_layer"])
            != ("bronze_b2", "silver")
        ):
            raise ValueError("v1 subject or adjacent transition differs")
        if set(subject["lineage"]["input_sha256"]) != set(
            decision["input_sha256"]
        ):
            raise ValueError("v1 lineage checksum differs")
        if decision["status"] == "approved" and (
            set(decision["required_gate_ids"])
            - set(decision["passed_gate_ids"])
            or decision["rights_decision"]["status"] != "approved"
            or subject["promotion_status"] != "approved_within_scope"
        ):
            raise ValueError("v1 required approval gate missing")
    expected_fields = {
        (MBS_SILVER_OBJECTS[field.target_table].path, field.native_name)
        for field in mbs_field_contracts()
    }
    if (
        len(v2["records"]) != len(expected_fields)
        or {
            (record["output_dataset"], record["output_field"])
            for record in v2["records"]
        }
        != expected_fields
    ):
        raise ValueError("v2 native field denominator differs")
    for record in v2["records"]:
        if (
            record["input_sha256"] != SOURCE_OBJECT_SHA256
            or record["output_sha256"]
            != artifacts[record["output_dataset"]]["sha256"]
            or record["record_id"]
            != digest({
                key: value
                for key, value in record.items()
                if key != "record_id"
            })
        ):
            raise ValueError("v2 identity or record digest differs")
    plan = v3["replay_plan"]
    snapshots = v3["snapshots"]
    if (
        plan["plan_sha256"] != digest(plan["steps"])
        or len(plan["steps"]) != OBJECT_COUNT
        or plan["eligible_snapshot_count"]
        != sum(snapshot["replay_eligible"] for snapshot in snapshots)
    ):
        raise ValueError("v3 replay plan digest or denominator differs")
    for snapshot in snapshots:
        if snapshot["snapshot_id"] != digest([
            snapshot["partition_id"],
            snapshot["payload_sha256"],
            snapshot["metadata_sha256"],
        ]) or snapshot["idempotency_key"] != digest([
            snapshot["partition_id"],
            snapshot["snapshot_id"],
        ]):
            raise ValueError("v3 snapshot or idempotency digest differs")
