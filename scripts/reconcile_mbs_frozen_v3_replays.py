"""Bind three hosted, value-free MBS replay receipts to their frozen plans."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_mbs_frozen_raw_replay as candidate

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "edithatogo/global-medicines-atlas"
COMMIT = "0c34250f931bc457193eb59da04e9e20107c6600"
DIRECTORY = (
    "quality/qualifications/australian-mbs-frozen-raw-v3-replays-20261115/"
)
OUTPUT = DIRECTORY + "replay-manifest.json"
RUNS: dict[str, dict[str, Any]] = {
    candidate.JULY: {
        "run": 43695553608,
        "job": 132755170167,
        "artifact": 14154158840,
        "artifact_bytes": 1375,
        "artifact_sha256": "09c28fd9546cf7e7e91c42ad4ba7cbb34c98b48cacc7c71bff92df3cdc32f6e0",
        "receipt_bytes": 2598,
        "receipt_sha256": "fd53bcf5d068e3483fd5ff9e482d3664a71c1b1f474aa0c36183030c4eebb0f6",
        "started_at": "2026-11-15T08:39:53Z",
        "completed_at": "2026-11-15T08:40:13Z",
    },
    candidate.AUGUST: {
        "run": 43695688398,
        "job": 132755583096,
        "artifact": 14154545295,
        "artifact_bytes": 1337,
        "artifact_sha256": "5252a752c7e6c37eb8c48ccb32922a16a1dbcace63919d65a5565ebc5a27a7dd",
        "receipt_bytes": 2653,
        "receipt_sha256": "275e45b077a9d798df5483ecbf81b1a1a180c5b550715e4981f327fe5f45b287",
        "started_at": "2026-11-15T08:41:37Z",
        "completed_at": "2026-11-15T08:41:57Z",
    },
    candidate.ALIAS: {
        "run": 43695816820,
        "job": 132755980958,
        "artifact": 14154520708,
        "artifact_bytes": 1365,
        "artifact_sha256": "3b13223feb02bcf078dc87b0fec9786df27f967e7330ae82b8350b4e304d2863",
        "receipt_bytes": 2565,
        "receipt_sha256": "d7b238272b1846f3bc497dc58e0fa7f01ba886061f9d0a10c76b5d9eaa18875d",
        "started_at": "2026-11-15T08:43:19Z",
        "completed_at": "2026-11-15T08:43:39Z",
    },
}


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _receipt_path(run: int) -> str:
    return f"{DIRECTORY}hosted-{run}/replay-receipt.json"


def _registration(snapshot: dict[str, Any], size: int) -> dict[str, Any]:
    return {
        "schema_version": "m112-raw-b2-replay-registration-v1",
        "snapshot_id": snapshot["snapshot_id"],
        "partition_id": snapshot["partition_id"],
        "source_id": snapshot["source_id"],
        "source_version_id": snapshot["source_version_id"],
        "archive_period": snapshot["archive_period"],
        "logical_asset_id": snapshot["logical_asset_id"],
        "payload_sha256": snapshot["payload_sha256"],
        "byte_count": size,
        "metadata_sha256": snapshot["metadata_sha256"],
        "rights_state": snapshot["rights_state"],
        "idempotency_key": snapshot["idempotency_key"],
        "operation": "append_only_idempotent_raw_b2_registration",
        "payload_values_read": False,
    }


def reconcile(
    plans: dict[str, dict[str, Any]], receipts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Check exact identity, replay, run and privacy claims for every path."""
    _require(
        set(plans) == set(receipts) == set(RUNS) == set(candidate.PATHS)
        and all(
            len({run[key] for run in RUNS.values()}) == len(RUNS)
            for key in ("run", "job", "artifact")
        ),
        "frozen MBS replay denominator differs",
    )
    objects: list[dict[str, Any]] = []
    for path in candidate.PATHS:
        run = RUNS[path]
        plan, receipt = plans[path], receipts[path]
        snapshot = plan["snapshots"][0]
        step = plan["replay_plan"]["steps"][0]
        registration = _registration(snapshot, step["expected_byte_count"])
        run_id = run["run"]
        _require(
            receipt["schema_id"]
            == "global-medicines-atlas.m112-v3-replay-execution-receipt"
            and receipt["schema_version"] == 1
            and receipt["status"] == "passed"
            and receipt["candidate_only"] is True
            and receipt["scope"]
            == {
                "dataset": candidate.DATASET,
                "revision": candidate.REVISION,
                "path": path,
                "sha256": snapshot["payload_sha256"],
                "byte_count": step["expected_byte_count"],
            }
            and receipt["replay"]["vocabulary_version"] == "3.0.0"
            and receipt["replay"]["plan_sha256"] == _sha(plan)
            and receipt["replay"]["snapshot_id"] == snapshot["snapshot_id"]
            and receipt["replay"]["partition_id"] == snapshot["partition_id"]
            and receipt["replay"]["registration"] == registration
            and receipt["replay"]["registration_sha256"] == _sha(registration),
            "frozen MBS replay identity or registration differs",
        )
        _require(
            receipt["verification"]
            == {
                "anonymous": True,
                "token_free": True,
                "payload_values_read": False,
                "temporary_source_bytes_removed": True,
                "payload_storage": "never_materialized",
                "digest_method": "bounded_anonymous_stream",
            }
            and receipt["hosted_workflow"]
            == {
                "repository": REPOSITORY,
                "commit": COMMIT,
                "run_id": run_id,
                "run_attempt": 1,
                "run_url": f"https://github.com/{REPOSITORY}/actions/runs/{run_id}",
            }
            and receipt["boundaries"]
            == {
                "v4_admission_performed": False,
                "m112_consumer_canary_performed": False,
                "public_dataset_mutation": False,
                "source_values_or_rows_included": False,
            },
            "frozen MBS replay hosted or privacy boundary differs",
        )
        objects.append({
            "dataset": candidate.DATASET,
            "revision": candidate.REVISION,
            "path": path,
            "sha256": snapshot["payload_sha256"],
            "byte_count": step["expected_byte_count"],
            "status": "passed",
            "plan_sha256": _sha(plan),
            "registration_sha256": _sha(registration),
            "receipt": {
                "path": _receipt_path(run_id),
                "sha256": run["receipt_sha256"],
                "byte_count": run["receipt_bytes"],
            },
            "native_artifact": {
                "id": run["artifact"],
                "name": f"australian-m112-v3-replay-{run_id}-1",
                "member": f"gma-m112-v3-replay-receipt-{run_id}-1.json",
                "sha256": run["artifact_sha256"],
                "byte_count": run["artifact_bytes"],
                "archive_digest_verified": True,
                "zip_crc_verified": True,
                "exact_metadata_member_set_verified": True,
            },
            "hosted_workflow": {
                "run": run_id,
                "job": run["job"],
                "commit": COMMIT,
                "attempt": 1,
                "event": "workflow_dispatch",
                "conclusion": "success",
                "started_at": run["started_at"],
                "completed_at": run["completed_at"],
            },
            "v4_admission": "not_performed",
            "consumer_canary": "not_performed",
            "independent_recovery": "not_established",
        })
    return {
        "schema_id": "global-medicines-atlas.mbs-frozen-v3-replay-manifest",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "objects": objects,
        "summary": {
            "exact_replays_passed": len(objects),
            "new_v4_admissions": 0,
            "new_consumer_canaries": 0,
            "independent_recovery_established": False,
        },
        "boundaries": {
            "source_values_or_rows_emitted": False,
            "source_payload_bytes_persisted": False,
            "participant_or_cohort_data_accessed": False,
            "dataset_added_or_published": False,
            "frozen_inventory_changed": False,
        },
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    """Regenerate the manifest from pinned plans and hosted metadata only."""
    _, _, plans = candidate.build(root)
    receipts: dict[str, dict[str, Any]] = {}
    for path, run in RUNS.items():
        relative = _receipt_path(run["run"])
        body = (root / relative).read_bytes()
        _require(
            len(body) == run["receipt_bytes"], "replay receipt size differs"
        )
        receipts[path] = bounded.read_bound_metadata(
            root, relative, run["receipt_sha256"]
        )
    return reconcile(plans, receipts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    path = ROOT / OUTPUT
    expected = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        _require(
            path.is_file() and path.read_bytes() == expected,
            "replay manifest is stale",
        )
    else:
        path.write_bytes(expected)
    print(f"verified {len(result['objects'])} frozen MBS replay receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
