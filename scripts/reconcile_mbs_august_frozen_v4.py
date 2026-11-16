"""Reconcile two hosted August MBS raw readers to the frozen ledger.

This consumes only bound public-safe receipts and inventories. It does not read
source payloads, mutate an archive, claim independent recovery or accept the
Australian federation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_mbs_august_frozen_v4 as august
import scripts.reconcile_mbs_july_frozen_v4 as july

from global_medicines_atlas.federation_admission import admit_closed_contract
from global_medicines_atlas.federation_identity import AdmissionRecord
from global_medicines_atlas.federation_receipt_closure import ReceiptClosure

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = "quality/qualifications/australian-mbs-august-frozen-v4-20261115/hosted-43705630353/"
RECEIPT = DIRECTORY + "qualification.json"
ARTIFACT = DIRECTORY + "artifact-manifest.json"
OUTPUT = "quality/qualifications/australian-m112-effective-raw-delivery-reconciliation-20261115-august.json"
INPUTS = {
    july.PRIOR: july.INPUTS[july.PRIOR],
    july.FROZEN: july.INPUTS[july.FROZEN],
    july.OUTPUT: "1578dfe8dd32ab769ec56dc702dc05bdf88e5b41cfa0eec8ef573c1b77539b13",
    RECEIPT: "42b38094fe116f9aaaadf1a88264a95a3ca8c0b3102dacb10d333897adf9ff29",
    ARTIFACT: "1ab584f262d9ca1b35fdf640da2f14bf0b4b7b9f7fd77c42fb64913a251246c2",
}
RUN = 43705630353
JOB = 132785965334
ARTIFACT_ID = 14158262195
COMMIT = "5f0a373664f28c629822d7174b1045a067158b73"
ARCHIVE_SHA = "66fe072df5aff6ec551c6a23a799293327d99ea697237a091f1f9b54613864a6"
ARCHIVE_BYTES = 2955
RECEIPT_BYTES = 25534
FROZEN_COUNT = 1759
PRIOR_COUNT = 15
NEW_COUNT = 2
ROLES = 14
RECEIPTS = 11


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_artifact(artifact: dict[str, Any]) -> None:
    wf, archive, receipt = (
        artifact[k] for k in ("workflow", "artifact", "receipt")
    )
    _require(
        artifact["schema_id"]
        == "global-medicines-atlas.mbs-august-frozen-v4-artifact"
        and artifact["schema_version"] == 1
        and wf["repository"] == august.shared.REPO
        and wf["run"] == RUN
        and wf["job"] == JOB
        and wf["commit"] == COMMIT
        and wf["attempt"] == 1
        and wf["event"] == "workflow_dispatch"
        and wf["conclusion"] == "success"
        and archive["id"] == ARTIFACT_ID
        and archive["name"] == f"mbs-august-frozen-v4-{RUN}-1"
        and archive["member"] == "mbs-august-frozen-v4.json"
        and archive["sha256"] == ARCHIVE_SHA
        and archive["byte_count"] == ARCHIVE_BYTES
        and receipt["path"] == RECEIPT
        and receipt["sha256"] == INPUTS[RECEIPT]
        and receipt["byte_count"] == RECEIPT_BYTES
        and artifact["validation"]
        == {
            "native_artifact_digest_verified": True,
            "zip_crc_verified": True,
            "exact_member_set_verified": True,
            "exact_contracts_and_consumers_verified": True,
            "source_values_retained": False,
        },
        "August hosted artifact identity differs",
    )


def _validate_object(row: dict[str, Any], root: Path) -> AdmissionRecord:
    path = row["path"]
    _require(path in august.OUTPUTS, "August hosted path differs")
    raw, trusted = august.shared.candidate(root, path=path)
    _require(
        (root / august.OUTPUTS[path]).read_bytes() == raw
        and hashlib.sha256(raw).hexdigest() == row["contract_sha256"],
        "August contract differs",
    )
    closure = ReceiptClosure.model_validate(row["receipt_closure"])
    _require(
        len(closure.roles) == ROLES and len(closure.receipts) == RECEIPTS,
        "August receipt closure denominator differs",
    )
    admission = admit_closed_contract(
        raw,
        closure,
        schema=(root / august.shared.SCHEMA).read_bytes(),
        trusted=trusted,
    )
    _require(
        admission == AdmissionRecord.model_validate(row["admission"]),
        "August independent admission differs",
    )
    consumer = row["consumer_canary"]
    w, v, b = (
        consumer["hosted_workflow"],
        consumer["verification"],
        consumer["boundaries"],
    )
    _require(
        consumer["schema_id"]
        == "global-medicines-atlas.m112-v4-consumer-canary"
        and consumer["status"] == "passed"
        and consumer["contract_sha256"] == admission.contract_sha256
        and consumer["object"]
        == {
            "dataset": admission.dataset,
            "revision": admission.revision,
            "path": admission.path,
            "bytes": admission.byte_count,
            "sha256": admission.sha256,
        }
        and w["repository"] == august.shared.REPO
        and w["commit"] == COMMIT
        and w["run_id"] == RUN
        and w["run_attempt"] == 1
        and v["origin"] == "remote"
        and v["remote_digest_match"] is True
        and v["consumer_stream_digest_match"] is True
        and v["reader_cache_bytes_after_close"] == 0
        and v["source_values_or_rows_interpreted"] is False
        and b["admission_used"] is True
        and b["public_dataset_mutated"] is False
        and b["source_payload_bytes_retained"] is False
        and b["source_values_or_rows_included"] is False,
        "August hosted consumer or privacy boundary differs",
    )
    return admission


def reconcile(
    older: dict[str, Any],
    frozen: dict[str, Any],
    previous: dict[str, Any],
    receipt: dict[str, Any],
    artifact: dict[str, Any],
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Verify both distinct paths and preserve the approved frozen denominator."""
    _validate_artifact(artifact)
    _require(
        previous == july.build(root)
        and receipt["schema_id"]
        == "global-medicines-atlas.mbs-august-frozen-v4-admission-reader"
        and receipt["schema_version"] == 1
        and receipt["status"] == "passed"
        and receipt["source_profile"]
        == {
            "comparison_cohort_scope": "later_member_of_documented_july_august_2026_pair",
            "schema_era_meaning": "source_release_revision",
            "field_semantics_accepted": False,
            "latest_schedule_claimed": False,
        }
        and receipt["boundaries"]
        == {
            "dataset_added_or_published": False,
            "participant_or_cohort_data_accessed": False,
            "source_values_interpreted": False,
            "independent_recovery_established": False,
            "federation_gate_closed": False,
        }
        and [row["path"] for row in receipt["objects"]] == list(august.OUTPUTS),
        "August hosted qualification boundary differs",
    )
    admissions = [_validate_object(row, root) for row in receipt["objects"]]
    members = frozen["members"]
    by_key = {(row["dataset"], row["path"]): row for row in members}
    prior = (
        older["prior_admitted_identities"]
        + older["new_admitted_identities"]
        + [previous["new_admission"]]
    )
    prior_keys = {(row["dataset"], row["path"]) for row in prior}
    counts = previous["effective_counts"]
    selected = [(row.dataset, row.path) for row in admissions]
    _require(
        frozen["scope"]["approved_member_count"]
        == len(members)
        == len(by_key)
        == FROZEN_COUNT
        and counts["frozen_objects"] == FROZEN_COUNT
        and counts["raw_v4_admissions"]
        == counts["raw_admitted_object_reader_canaries"]
        == len(prior)
        == len(prior_keys)
        == PRIOR_COUNT
        and counts["deferred_objects"] == FROZEN_COUNT - PRIOR_COUNT
        and prior_keys <= by_key.keys()
        and len(selected) == len(set(selected)) == NEW_COUNT
        and not prior_keys.intersection(selected)
        and all(
            key in by_key
            and by_key[key]["object_class"] == "raw_source_payload"
            and by_key[key]["approved_dataset_revision"] == admission.revision
            for key, admission in zip(selected, admissions, strict=True)
        ),
        "August frozen membership or prior ledger differs",
    )
    result: list[dict[str, Any]] = []
    for admission in admissions:
        member = by_key[admission.dataset, admission.path]
        result.append({
            "dataset": admission.dataset,
            "path": admission.path,
            "approved_dataset_revision": admission.revision,
            "later_reconciliation_revision": member[
                "current_reconciliation_revision"
            ],
            "sha256": admission.sha256,
            "byte_count": admission.byte_count,
            "contract_sha256": admission.contract_sha256,
            "workflow_run": RUN,
            "job": JOB,
            "artifact": ARTIFACT_ID,
        })
    total = PRIOR_COUNT + NEW_COUNT
    return {
        "schema_id": "global-medicines-atlas.m112-august-frozen-raw-delivery-reconciliation",
        "schema_version": 1,
        "inputs": {
            path: {"path": path, "sha256": sha} for path, sha in INPUTS.items()
        },
        "effective_counts": {
            "frozen_objects": FROZEN_COUNT,
            "raw_v4_admissions": total,
            "raw_admitted_object_reader_canaries": total,
            "deferred_objects": FROZEN_COUNT - total,
            "frozen_denominator_changed": False,
        },
        "increment": {
            "raw_v4_admissions": NEW_COUNT,
            "raw_admitted_object_reader_canaries": NEW_COUNT,
        },
        "new_admissions": result,
        "boundaries": {
            "dataset_added_or_published": False,
            "participant_or_cohort_data_accessed": False,
            "source_values_retained_or_interpreted": False,
            "independent_recovery_established": False,
            "federation_gate_closed": False,
        },
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    data = {
        path: bounded.read_bound_metadata(root, path, digest)
        for path, digest in INPUTS.items()
    }
    return reconcile(
        data[july.PRIOR],
        data[july.FROZEN],
        data[july.OUTPUT],
        data[RECEIPT],
        data[ARTIFACT],
        root=root,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = (json.dumps(build(), indent=2, sort_keys=True) + "\n").encode()
    path = ROOT / OUTPUT
    if args.check:
        _require(
            path.is_file() and path.read_bytes() == expected,
            "August ledger is stale",
        )
    else:
        path.write_bytes(expected)
    print(
        "verified 17 exact raw admissions and reader checks; federation remains open"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
