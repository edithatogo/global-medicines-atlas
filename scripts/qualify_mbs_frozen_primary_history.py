"""Reconcile an existing exact-revision MBS primary restore to frozen objects.

This reads only retained public workflow and inventory metadata. It does not
read or copy a source payload, perform a new restore, or establish a replica.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = "quality/qualifications/australian-mbs-primary-history-20261115/"
RECEIPT = DIRECTORY + "source-metadata-receipt.json"
NATIVE = DIRECTORY + "native-metadata.json"
OUTPUT = DIRECTORY + "reconciliation.json"
BINDING = "quality/qualifications/australian-existing-mbs-digest-binding-20261115.json"
MEMORY = DIRECTORY + "primary-memory-restore.json"
ARTIFACT = DIRECTORY + "primary-memory-artifact.json"
REPLAYS = "quality/qualifications/australian-mbs-frozen-raw-v3-replays-20261115/replay-manifest.json"
INPUTS = {
    RECEIPT: "460189523f9bac2a544b0d420e6bcf1126cca30664f0739019604500afd44c06",
    NATIVE: "309fba514014378ccc8994beb2974241ac8f8b1c09269f852386f1e9ffbbd38f",
    BINDING: "9f1211574b46c18bbb37cf47399c68a8c4197c2bb08f9aaccac96930566ed02f",
    MEMORY: "b3986cf9598c3ff98a7f6a801b7d5a2745b58419e89808e983e8fcc772548958",
    ARTIFACT: "e6aeb4448b88f5ee1f7b1605c91909e9dd0a06f0ec62cd09856abd93be7f5996",
    REPLAYS: "a9b5b8cc2d703f6cb88956717f24e358e990659c816fd129e9ba5473655d32af",
}
REPO = "edithatogo/global-medicines-atlas"
RUN = 36532129354
JOB = 109287941955
COMMIT = "85ad454850dd43814530f4340fa6247776cb4cfc"
REVISION = "243f9ff5498816af6e4d9ae4db60528728f01834"
DATASET = "edithatogo/australian-mbs-source-archive"
COMMENT = 5885067299
RECEIPT_BYTES = 19139
BASELINE_COUNT = 49
OBSERVED_COUNT = 50
SCOPED_COUNT = 11
FROZEN_COUNT = 7
MEMORY_RUN = 43697888963
MEMORY_JOB = 132762367301
MEMORY_ARTIFACT = 14155347435
MEMORY_COMMIT = "c427dc839fa92b238a12739d7f3615573868efb3"
MEMORY_OBJECT_COUNT = 3


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def reconcile(
    receipt: dict[str, Any], native: dict[str, Any], binding: dict[str, Any]
) -> dict[str, Any]:
    """Bind the public Actions inventory receipt to all eleven scoped pins."""
    comment, run, job = native["comment"], native["run"], native["job"]
    _require(
        comment["id"] == COMMENT
        and comment["actor"] == "github-actions[bot]"
        and comment["issue_url"]
        == f"https://api.github.com/repos/{REPO}/issues/340"
        and comment["html_url"]
        == f"https://github.com/{REPO}/issues/340#issuecomment-{COMMENT}"
        and comment["created_at"] == comment["updated_at"]
        and comment["body_sha256"] == INPUTS[RECEIPT]
        and comment["body_bytes"] == RECEIPT_BYTES
        and run["id"] == RUN
        and run["head_sha"] == COMMIT
        and run["head_branch"] == "main"
        and run["event"] == "workflow_dispatch"
        and run["path"] == ".github/workflows/australian-source-metadata.yml"
        and run["status"] == "completed"
        and run["conclusion"] == "success"
        and run["run_attempt"] == 1
        and run["html_url"] == f"https://github.com/{REPO}/actions/runs/{RUN}"
        and job["id"] == JOB
        and job["name"] == "Append and anonymously verify source metadata"
        and job["status"] == "completed"
        and job["conclusion"] == "success"
        and job["verification_step"]
        == {
            "name": "Append only to the pinned source parent and verify anonymously",
            "status": "completed",
            "conclusion": "success",
        },
        "historical Actions identity differs",
    )
    _require(
        receipt["schema_id"] == "global-medicines-atlas.source-metadata-append"
        and receipt["status"] == "anonymously_verified"
        and receipt["dataset"] == DATASET
        and receipt["revision"] == REVISION
        and receipt["private"] is False
        and receipt["gated"] is False
        and receipt["code_commit"] == COMMIT
        and receipt["run_url"] == run["html_url"]
        and receipt["parent_basis"] == "server_enforced_parent_commit",
        "historical archive receipt identity differs",
    )
    baseline, observed = receipt["baseline"], receipt["observed"]
    _require(
        len(baseline) == BASELINE_COUNT
        and len(observed) == OBSERVED_COUNT
        and len({x["path"] for x in baseline}) == BASELINE_COUNT
        and len({x["path"] for x in observed}) == OBSERVED_COUNT
        and all(observed.count(row) == 1 for row in baseline)
        and observed.count(receipt["addition"]) == 1,
        "historical primary inventory differs",
    )
    objects: list[dict[str, Any]] = []
    for row in binding["objects"]:
        identity = {key: row[key] for key in ("path", "sha256", "byte_count")}
        matched = (
            row["dataset"] == DATASET
            and row["revision"] == REVISION
            and baseline.count(identity) == observed.count(identity) == 1
        )
        objects.append({
            **{
                key: row[key]
                for key in (
                    "dataset",
                    "revision",
                    "path",
                    "sha256",
                    "byte_count",
                    "frozen_member",
                )
            },
            "historical_primary_restore": "exact_inventory_match"
            if matched
            else "not_covered_by_this_receipt",
        })
    _require(
        len(objects) == SCOPED_COUNT
        and sum(
            item["historical_primary_restore"] == "exact_inventory_match"
            for item in objects
        )
        == FROZEN_COUNT
        and all(
            (item["historical_primary_restore"] == "exact_inventory_match")
            == item["frozen_member"]
            for item in objects
        ),
        "historical exact-match denominator differs",
    )
    return {
        "schema_id": "global-medicines-atlas.mbs-frozen-primary-history",
        "schema_version": 1,
        "run": RUN,
        "run_commit": COMMIT,
        "observed_at": comment["created_at"],
        "source_receipt": {
            "path": RECEIPT,
            "sha256": INPUTS[RECEIPT],
            "url": comment["html_url"],
        },
        "native_metadata": {"path": NATIVE, "sha256": INPUTS[NATIVE]},
        "historical_code": {
            "snapshot_script_sha256": "1ed417625e2c797452e84a803044a6b70964f48966ddc6db0032f91446039d97",
            "hosted_controller_sha256": "de8ae7f6a167d57e847d8656286d6aa97f360a77938ca1ea8393544c6362a572",
            "workflow_sha256": "5195a17da18c179a59072e5bb1400968c4a719fdf684873c040b8c67100f4cfd",
        },
        "objects": objects,
        "summary": {
            "frozen_exact_matches": 7,
            "outside_objects_not_covered": 4,
            "independent_recovery_established": False,
        },
        "boundaries": {
            "historical_primary_only": True,
            "new_payload_reads": False,
            "source_values_or_rows_retained": False,
            "participant_or_cohort_data_accessed": False,
            "dataset_added_or_published": False,
            "v4_admission_or_consumer_canary": False,
        },
    }


def reconcile_memory(
    receipt: dict[str, Any], artifact: dict[str, Any], replays: dict[str, Any]
) -> dict[str, Any]:
    """Bind the new value-free primary restore to the exact replay scope."""
    _require(
        receipt["schema_id"]
        == "global-medicines-atlas.mbs-frozen-primary-memory-restore"
        and receipt["schema_version"] == 1
        and receipt["workflow_commit"] == MEMORY_COMMIT
        and receipt["workflow_run"] == str(MEMORY_RUN)
        and receipt["workflow_attempt"] == "1"
        and receipt["boundaries"]
        == {
            "primary_copy_only": True,
            "independent_recovery_established": False,
            "participant_or_cohort_data_accessed": False,
            "dataset_added_or_published": False,
            "v4_admission_or_consumer_canary": False,
        }
        and artifact["run"] == MEMORY_RUN
        and artifact["job"] == MEMORY_JOB
        and artifact["artifact"] == MEMORY_ARTIFACT
        and artifact["workflow_commit"] == MEMORY_COMMIT
        and artifact["receipt_sha256"] == INPUTS[MEMORY]
        and artifact["native_artifact_digest_verified"] is True
        and artifact["zip_crc_verified"] is True
        and artifact["exact_member_set_verified"] is True
        and artifact["exact_object_and_boundaries_verified"] is True,
        "primary memory workflow or artifact differs",
    )
    expected = {row["path"]: row for row in replays["objects"]}
    _require(
        len(expected) == len(receipt["objects"]) == MEMORY_OBJECT_COUNT,
        "primary memory object set differs",
    )
    for row in receipt["objects"]:
        path = row["path"]
        _require(path in expected, "primary memory object path differs")
        replay = expected.pop(path)
        _require(
            all(
                row[key] == replay[key]
                for key in (
                    "dataset",
                    "revision",
                    "path",
                    "sha256",
                    "byte_count",
                )
            )
            and row["restore_medium"] == "memory"
            and row["memory_buffer_closed"] is True
            and row["source_values_interpreted_or_emitted"] is False
            and row["source_payload_files_written"] is False,
            "primary memory object or privacy boundary differs",
        )
    _require(not expected, "primary memory object set differs")
    return {
        "run": MEMORY_RUN,
        "job": MEMORY_JOB,
        "receipt": {"path": MEMORY, "sha256": INPUTS[MEMORY]},
        "artifact": {"path": ARTIFACT, "sha256": INPUTS[ARTIFACT]},
        "exact_objects_passed": MEMORY_OBJECT_COUNT,
        "medium": "memory",
        "primary_only": True,
        "independent_recovery_established": False,
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    evidence = {
        path: bounded.read_bound_metadata(root, path, sha)
        for path, sha in INPUTS.items()
    }
    _require(
        hashlib.sha256((root / RECEIPT).read_bytes()).hexdigest()
        == evidence[NATIVE]["comment"]["body_sha256"],
        "historical receipt bytes differ",
    )
    report = reconcile(evidence[RECEIPT], evidence[NATIVE], evidence[BINDING])
    report["primary_memory"] = reconcile_memory(
        evidence[MEMORY], evidence[ARTIFACT], evidence[REPLAYS]
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build()
    expected = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    path = ROOT / OUTPUT
    if args.check:
        _require(
            path.is_file() and path.read_bytes() == expected,
            "primary history report is stale",
        )
    else:
        path.write_bytes(expected)
    print(
        "verified existing primary restore inventory for seven frozen MBS objects"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
