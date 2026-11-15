"""Bind hosted exact-revision MBS digest observations to v4 candidates.

The receipt is metadata only. It does not close contract receipt roles, admit
objects, run a consumer canary, or establish independent recovery.
"""

from __future__ import annotations

import argparse
import json
from operator import itemgetter
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = (
    "quality/qualifications/australian-existing-mbs-digest-20261115/"
    "hosted-43687742836/"
)
INPUTS = {
    "readiness": (
        "quality/qualifications/australian-existing-v4-privacy-readiness-20261115.json",
        "84f76a2187830bf1e0949261df739f6eae45fb39f9c58750d7cdce09d4875d39",
    ),
    "receipt": (
        DIRECTORY + "digest-receipt.json",
        "bbfd25983a89d7aba244a71bd2372b6c23f7d05cc2065a3506bf49e618f08191",
    ),
    "artifact": (
        DIRECTORY + "artifact-manifest.json",
        "944b26b5762ca83b8e2578d40acf64b58a52566aee0b74818ce5b71803f4d04e",
    ),
}
COMMIT = "1a63753104b87f0ad929dd977f0c24ae14fe839f"
RUN_ID = 43687742836
JOB_ID = 132731666837
ARTIFACT_ID = 14150709884
ARTIFACT_SHA = (
    "050686e57bcee70b2fa9017ce40c690405dfe9119669ed5395f6a23fc1125119"
)
ARTIFACT_BYTES = 1400
RECEIPT_BYTES = 4533
OBJECT_COUNT = 11
FROZEN_COUNT = 7


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result = {(row["dataset"], row["path"]): row for row in rows}
    _require(len(result) == len(rows), "duplicate exact-object identity")
    return result


def reconcile(evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Validate native-run provenance and join each independently pinned identity."""
    readiness, receipt, artifact = (
        evidence["readiness"],
        evidence["receipt"],
        evidence["artifact"],
    )
    _require(
        receipt["schema_id"]
        == "global-medicines-atlas.australian-existing-mbs-hosted-digest"
        and receipt["workflow_commit"] == COMMIT
        and receipt["workflow_run"] == str(RUN_ID)
        and receipt["workflow_attempt"] == "1"
        and receipt["boundaries"]
        == {
            "dataset_added_or_published": False,
            "participant_or_cohort_data_accessed": False,
            "payload_bytes_persisted_or_emitted": False,
            "v4_admission_or_consumer_canary": False,
            "independent_recovery_established": False,
        },
        "hosted digest run identity or boundary differs",
    )
    _require(
        artifact["schema_id"]
        == "global-medicines-atlas.australian-existing-mbs-digest-artifact"
        and artifact["artifact"]["id"] == ARTIFACT_ID
        and artifact["artifact"]["sha256"] == ARTIFACT_SHA
        and artifact["artifact"]["size_bytes"] == ARTIFACT_BYTES
        and artifact["artifact"]["name"]
        == "australian-existing-mbs-exact-digest-43687742836-1"
        and artifact["report"]["path"] == "digest-receipt.json"
        and artifact["report"]["sha256"] == INPUTS["receipt"][1]
        and artifact["report"]["size_bytes"] == RECEIPT_BYTES
        and artifact["workflow"]
        == {
            "event": "workflow_dispatch",
            "head_sha": COMMIT,
            "job_id": JOB_ID,
            "run_attempt": 1,
            "run_id": RUN_ID,
            "url": f"https://github.com/edithatogo/global-medicines-atlas/actions/runs/{RUN_ID}",
        }
        and artifact["validation"]
        == {
            "artifact_sha256_verified": True,
            "zip_crc_verified": True,
            "exact_metadata_member_set": True,
            "hosted_workflow_conclusion": "success",
            "source_values_included": False,
            "dataset_publication": False,
            "new_admissions": 0,
        },
        "hosted digest artifact provenance differs",
    )
    expected = _index(bounded.metadata_rows(readiness["mbs_objects"]))
    observed = _index(bounded.metadata_rows(receipt["objects"]))
    _require(
        len(expected) == len(observed) == OBJECT_COUNT
        and expected.keys() == observed.keys(),
        "hosted digest object set differs",
    )
    rows: list[dict[str, Any]] = []
    for identity, source in expected.items():
        actual = observed[identity]
        _require(
            all(
                actual[key] == source[key]
                for key in (
                    "dataset",
                    "revision",
                    "path",
                    "sha256",
                    "byte_count",
                )
            ),
            "hosted digest exact revision or payload identity differs",
        )
        rows.append({
            **{
                key: source[key]
                for key in (
                    "dataset",
                    "revision",
                    "path",
                    "sha256",
                    "byte_count",
                    "frozen_member",
                    "batch",
                )
            },
            "exact_revision_stream_digest": "passed",
            "v4_verification_evidence": "available_unbound_to_contract",
            "v4_contract_receipt_closure": "not_performed",
            "trusted_v4_admission": "not_performed",
            "consumer_canary": "not_performed",
            "independent_recovery": "not_established",
        })
    _require(
        sum(row["frozen_member"] for row in rows) == FROZEN_COUNT,
        "frozen cohort differs",
    )
    return {
        "schema_id": "global-medicines-atlas.australian-existing-mbs-digest-binding",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "inputs": {
            k: {"path": v[0], "sha256": v[1]} for k, v in INPUTS.items()
        },
        "workflow_run": RUN_ID,
        "objects": sorted(rows, key=itemgetter("path")),
        "summary": {
            "exact_revision_stream_digests_passed": len(rows),
            "frozen_objects": FROZEN_COUNT,
            "outside_frozen_objects": OBJECT_COUNT - FROZEN_COUNT,
            "new_v4_admissions": 0,
            "new_consumer_canaries": 0,
            "independent_recovery_established": False,
            "pbs_privacy_clearances": readiness["pbs_privacy"][
                "new_privacy_clearances"
            ],
        },
        "boundaries": {
            "dataset_added_or_published": False,
            "participant_or_cohort_data_accessed": False,
            "payload_bytes_persisted_or_emitted": False,
            "frozen_inventory_changed": False,
        },
    }


def build_report(root: Path = ROOT) -> dict[str, Any]:
    """Read only digest-bound metadata and produce an object-level binding."""
    return reconcile({
        name: bounded.read_bound_metadata(root, *binding)
        for name, binding in INPUTS.items()
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args()
    report = build_report()
    if args.build:
        with args.build.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    elif json.loads(args.check.read_text(encoding="utf-8")) != report:
        raise ValueError("stored exact digest binding differs")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
