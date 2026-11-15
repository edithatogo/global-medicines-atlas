"""Replay eight existing MBS projection registrations from metadata only.

This does not regenerate Parquet or read its bytes. Historical regeneration
evidence remains separate, including the later writer-footer limitation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import scripts.qualify_m112_v3_replay as v3
import scripts.qualify_mbs_august_projection_field_lineage as lineage
import scripts.reconcile_mbs_august_projection_sources as reconstructed
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = (
    "quality/qualifications/australian-mbs-august-projection-v3-20261115"
)
REPORT = f"{DIRECTORY}/metadata-replay.json"
HISTORIC = {
    "6bc9": (
        "f5626f2deb09f4301989480f112ec117ccad9efafc54c04d161100d6c5ca08e1",
        "f0539528fff8f48781554e83ff3520579efc9a61daa04c5ca14d75e835bbacba",
        "c195af67842ed7005c836a08a49ca1e65bb3ca957399323a51da6dff58d72b42",
    ),
    "f9f9": (
        "fd32879190b69ad98cd2f207ec3b70b725ab8f524218f783ec08bf98b7ffcecd",
        "0473edd93fe9c2781701116febbd68a0c68262b74be5b4de52409d5c52570d30",
        "4104bc85b891dd489e94378c40129870ef98f087c0e28862feb759a3723501fb",
    ),
}


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _hash(value: object) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def _file_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sources(root: Path) -> dict[str, dict[str, Any]]:
    generated = reconstructed.build(root)
    report = json.loads(generated[reconstructed.REPORT])
    records: dict[str, dict[str, Any]] = {}
    for row in report["records"]:
        records[row["producer"]] = {
            "acquisition_id": row["acquisition_id"],
            "event": row["reconstructed_event"],
            "b2": row["later_b2_reference"],
            "reconstructed_now": True,
        }
    for name, (acquisition, event_sha, b2_sha) in HISTORIC.items():
        event = f"quality/bronze/acquisitions/au-mbs/{acquisition}.json"
        b2 = f"quality/bronze/raw-evidence/au-mbs/{acquisition}/manifest.json"
        records[name] = {
            "acquisition_id": acquisition,
            "event": {"path": event, "sha256": event_sha},
            "b2": {"path": b2, "sha256": b2_sha},
            "reconstructed_now": False,
        }
    for name, item in records.items():
        loaded: dict[str, Any] = {}
        for role in ("event", "b2"):
            ref = item[role]
            raw = (root / ref["path"]).read_bytes()
            _require(
                _file_hash(raw) == ref["sha256"],
                "source metadata digest differs",
            )
            loaded[role] = json.loads(raw)
        event, rows = loaded["event"], loaded["b2"]["rows"]
        _require(
            event["acquisition_id"] == item["acquisition_id"]
            and event["content_id"]
            == event["payload_sha256"]
            == lineage.SOURCE_SHA
            and event["source_id"] == "au-mbs"
            and len(rows) == 1
            and rows[0]["acquisition_id"] == item["acquisition_id"]
            and rows[0]["content_id"] == lineage.SOURCE_SHA
            and rows[0]["state"] == "external_reference_only"
            and name in lineage.PRODUCERS,
            "source acquisition or B2 reference differs",
        )
        item["retrieved_at"] = event["retrieved_at"]
    return records


def _plan(
    root: Path, row: dict[str, Any], source: dict[str, Any], v2_sha: str
) -> dict[str, Any]:
    identity = {key: row[key] for key in ("dataset", "revision", "path")}
    logical = _hash(identity)
    period = "schedule-release:2026-08-01"
    partition = _hash(["au-mbs", period, logical])
    metadata = {
        "projection": identity
        | {"sha256": row["sha256"], "byte_count": row["byte_count"]},
        "source_sha256": lineage.SOURCE_SHA,
        "acquisition_id": source["acquisition_id"],
        "source_event": source["event"],
        "source_b2": source["b2"],
        "source_receipt": row["source_receipt"],
        "field_lineage_sha256": v2_sha,
        "producer_commit": row["producer_commit"],
        "reproduction": row["reproduction"],
        "reproduction_evidence": {
            "path": lineage.INPUTS[
                "frozen_replay" if row["frozen_member"] else "outside_replay"
            ][0],
            "sha256": lineage.INPUTS[
                "frozen_replay" if row["frozen_member"] else "outside_replay"
            ][1],
        },
        "rights_evidence": row["rights_evidence"],
    }
    metadata_sha = _hash(metadata)
    snapshot_id = _hash([partition, row["sha256"], metadata_sha])
    snapshot = {
        "snapshot_id": snapshot_id,
        "source_id": "au-mbs",
        "source_version_id": "2026-08-01",
        "partition_id": partition,
        "partition_value": f"{row['dataset']}@{row['revision']}:{row['path']}",
        "logical_asset_id": logical,
        "source_url": f"https://huggingface.co/datasets/{row['dataset']}/resolve/{row['revision']}/{row['path']}",
        "archive_period": period,
        "observation_status": "acquired",
        "payload_sha256": row["sha256"],
        "metadata_sha256": metadata_sha,
        "idempotency_key": _hash([partition, snapshot_id]),
        "correction_sequence": 0,
        "supersedes_snapshot_id": None,
        "late_arriving": False,
        "replay_eligible": True,
        "rights_state": "maintainer_attested_exact_scope_not_independently_reviewed",
    }
    plan = v3.build_replay_document(snapshot, row["byte_count"], root=root)
    step = plan["replay_plan"]["steps"][0]
    step["action"] = (
        "rebuild_projection_snapshot_registration_from_retained_metadata"
    )
    step["hosted_replay_status"] = "not_requested_local_metadata_only"
    plan_content = {
        key: value
        for key, value in plan["replay_plan"].items()
        if key != "plan_sha256"
    }
    plan["replay_plan"]["plan_sha256"] = _hash(plan_content)
    Draft202012Validator(
        json.loads((root / v3.V3_SCHEMA).read_bytes())
    ).validate(plan)  # pyright: ignore[reportUnknownMemberType]
    return {"plan": plan, "metadata": metadata}


def _register(plan: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    snapshot = plan["snapshots"][0]
    step = plan["replay_plan"]["steps"][0]
    _require(
        snapshot["metadata_sha256"] == _hash(metadata)
        and snapshot["snapshot_id"]
        == _hash([
            snapshot["partition_id"],
            snapshot["payload_sha256"],
            snapshot["metadata_sha256"],
        ])
        and snapshot["idempotency_key"]
        == _hash([snapshot["partition_id"], snapshot["snapshot_id"]])
        and step["expected_payload_sha256"] == snapshot["payload_sha256"]
        and step["expected_byte_count"] == metadata["projection"]["byte_count"]
        and step["action"]
        == "rebuild_projection_snapshot_registration_from_retained_metadata",
        "projection registration identity differs",
    )
    return {
        "snapshot_id": snapshot["snapshot_id"],
        "partition_id": snapshot["partition_id"],
        "idempotency_key": snapshot["idempotency_key"],
        "projection": metadata["projection"],
        "source_sha256": metadata["source_sha256"],
        "metadata_sha256": snapshot["metadata_sha256"],
    }


def build(root: Path = ROOT) -> dict[str, bytes]:
    """Replay metadata registrations twice, without source or output reads."""
    vocabulary, crosswalk = lineage.build(root)
    v2_sha = _file_hash(_bytes(vocabulary))
    _require(v2_sha == crosswalk["v2_lineage"]["sha256"], "v2 lineage differs")
    sources = _sources(root)
    outputs: dict[str, bytes] = {}
    rows: list[dict[str, Any]] = []
    for row in crosswalk["objects"]:
        names = [
            name
            for name, producer in lineage.PRODUCERS.items()
            if producer["id"] in row["path"]
        ]
        _require(len(names) == 1, "projection producer is not unique")
        name = names[0]
        packet = _plan(root, row, sources[name], v2_sha)
        first = _register(packet["plan"], packet["metadata"])
        second = _register(packet["plan"], packet["metadata"])
        _require(first == second, "metadata registration is not deterministic")
        slug = "p7" if row["path"].endswith("/p7.parquet") else "source"
        path = f"{DIRECTORY}/{name}-{slug}-plan.json"
        outputs[path] = _bytes(packet["plan"])
        rows.append({
            "path": row["path"],
            "dataset": row["dataset"],
            "revision": row["revision"],
            "sha256": row["sha256"],
            "byte_count": row["byte_count"],
            "producer": name,
            "source": sources[name],
            "plan": {"path": path, "sha256": _file_hash(outputs[path])},
            "registration_sha256": _hash(first),
            "historical_reproduction": row["reproduction"],
            "independent_replica_required_before_admission": name == "f9f9",
        })
    _require(
        len(rows) == lineage.OBJECT_COUNT, "projection replay count differs"
    )
    outputs[REPORT] = _bytes({
        "schema_id": "global-medicines-atlas.mbs-august-projection-metadata-replay",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "objects": rows,
        "registration_replay": "passed_twice_in_memory_from_retained_metadata",
        "historical_projection_reproduction_performed_by_this_replay": False,
        "boundaries": {
            "source_or_projection_payload_read": False,
            "participant_or_cohort_data_accessed": False,
            "v4_admission_or_consumer_check": False,
            "independent_replica_established": False,
            "dataset_acquired_or_published": False,
        },
    })
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for relative, raw in build().items():
        path = ROOT / relative
        if args.check:
            _require(
                path.is_file() and path.read_bytes() == raw,
                f"stale: {relative}",
            )
        else:
            _require(
                not path.exists() or path.read_bytes() == raw,
                f"immutable conflict: {relative}",
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    print(
        "Eight metadata registrations replayed; no payload, admission or replica"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
