"""Bind a hosted July MBS admission to the approved frozen delivery ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_mbs_july_frozen_v4 as july

from global_medicines_atlas.federation_admission import admit_closed_contract
from global_medicines_atlas.federation_identity import AdmissionRecord
from global_medicines_atlas.federation_receipt_closure import ReceiptClosure

ROOT = Path(__file__).resolve().parents[1]
PRIOR = "quality/qualifications/australian-m112-effective-raw-delivery-reconciliation-20261028.json"
FROZEN = "quality/qualifications/australian-m112-frozen-object-inventory-20261018.json"
DIRECTORY = "quality/qualifications/australian-mbs-july-frozen-v4-20261115/hosted-43699976886/"
RECEIPT = DIRECTORY + "qualification.json"
ARTIFACT = DIRECTORY + "artifact-manifest.json"
OUTPUT = "quality/qualifications/australian-m112-effective-raw-delivery-reconciliation-20261115.json"
INPUTS = {
    PRIOR: "c556cf596514d7cb69bce0a188f87460ad2746c3afacc559cec8ebd56cd7a3a3",
    FROZEN: "eaa1d84325c7672100398acf8116f0312369ca336d42ed21eee110452d3fefa4",
    RECEIPT: "ebdbb16158ba7e92a765c7e2468b4b60a43774d1e4566db4e1d17792469026c0",
    ARTIFACT: "76d1b0434a7d8f27edb79e66db2d0f6e975d96d1a1cd9f9aa65bee79f6e4cdd9",
}
CONTRACT_SHA = (
    "8c2032a7831b263f2792a9283759a96b9b91875cef8a685f4e010d84051664b9"
)
RUN = 43699976886
JOB = 132768761227
ARTIFACT_ID = 14156300585
COMMIT = "eb379883c4c4e146a41485aa3857cfccb2f72c1c"
APPROVED_COUNT = 1759
PREVIOUS_ADMISSIONS = 14
ROLES = 13
RECEIPTS = 10


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def reconcile(
    prior: dict[str, Any],
    frozen: dict[str, Any],
    receipt: dict[str, Any],
    artifact: dict[str, Any],
    *,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Reject identity drift, duplicate membership and unsupported acceptance."""
    raw, trusted = july.candidate(root)
    _require(
        hashlib.sha256(raw).hexdigest() == CONTRACT_SHA
        and (root / july.OUTPUT).read_bytes() == raw,
        "July candidate contract differs",
    )
    wf = artifact["workflow"]
    _require(
        artifact["schema_id"]
        == "global-medicines-atlas.mbs-july-frozen-v4-artifact"
        and artifact["schema_version"] == 1
        and wf["repository"] == july.REPO
        and wf["run"] == RUN
        and wf["job"] == JOB
        and wf["commit"] == COMMIT
        and wf["attempt"] == 1
        and wf["event"] == "workflow_dispatch"
        and wf["conclusion"] == "success"
        and artifact["artifact"]["id"] == ARTIFACT_ID
        and artifact["artifact"]["name"] == f"mbs-july-frozen-v4-{RUN}-1"
        and artifact["artifact"]["member"] == "mbs-july-frozen-v4.json"
        and artifact["artifact"]["sha256"]
        == "ef6d1b9c7e2a911c1cbfc27d1bc44b841c90d59e160bb1ca3aa32ff1838795ed"
        and artifact["receipt"]["sha256"] == INPUTS[RECEIPT]
        and artifact["receipt"]["path"] == RECEIPT
        and artifact["validation"]
        == {
            "native_artifact_digest_verified": True,
            "zip_crc_verified": True,
            "exact_member_set_verified": True,
            "exact_contract_and_consumer_verified": True,
            "source_values_retained": False,
        },
        "hosted artifact identity differs",
    )
    _require(
        receipt["schema_id"]
        == "global-medicines-atlas.mbs-july-frozen-v4-admission-reader"
        and receipt["schema_version"] == 1
        and receipt["status"] == "passed"
        and receipt["boundaries"]
        == {
            "dataset_added_or_published": False,
            "participant_or_cohort_data_accessed": False,
            "source_values_interpreted": False,
            "independent_recovery_established": False,
            "federation_gate_closed": False,
        },
        "hosted admission boundary differs",
    )
    closure = ReceiptClosure.model_validate(receipt["receipt_closure"])
    _require(
        len(closure.roles) == ROLES and len(closure.receipts) == RECEIPTS,
        "receipt closure denominator differs",
    )
    admission = admit_closed_contract(
        raw, closure, schema=(root / july.SCHEMA).read_bytes(), trusted=trusted
    )
    _require(
        admission == AdmissionRecord.model_validate(receipt["admission"]),
        "hosted admission differs from independent trust",
    )
    consumer = receipt["consumer_canary"]
    observed = consumer["object"]
    _require(
        consumer["schema_id"]
        == "global-medicines-atlas.m112-v4-consumer-canary"
        and consumer["status"] == "passed"
        and consumer["contract_sha256"] == CONTRACT_SHA
        and observed
        == {
            "dataset": admission.dataset,
            "revision": admission.revision,
            "path": admission.path,
            "bytes": admission.byte_count,
            "sha256": admission.sha256,
        }
        and consumer["hosted_workflow"]["repository"] == july.REPO
        and consumer["hosted_workflow"]["commit"] == COMMIT
        and consumer["hosted_workflow"]["run_id"] == RUN
        and consumer["hosted_workflow"]["run_attempt"] == 1
        and consumer["verification"]["origin"] == "remote"
        and consumer["verification"]["remote_digest_match"] is True
        and consumer["verification"]["consumer_stream_digest_match"] is True
        and consumer["verification"]["reader_cache_bytes_after_close"] == 0
        and consumer["verification"]["source_values_or_rows_interpreted"]
        is False
        and consumer["boundaries"]["admission_used"] is True
        and consumer["boundaries"]["public_dataset_mutated"] is False
        and consumer["boundaries"]["source_payload_bytes_retained"] is False
        and consumer["boundaries"]["source_values_or_rows_included"] is False,
        "hosted consumer or privacy boundary differs",
    )
    members = frozen["members"]
    keys = {(item["dataset"], item["path"]) for item in members}
    identity = (admission.dataset, admission.path)
    selected = [
        item for item in members if (item["dataset"], item["path"]) == identity
    ]
    prior_rows = (
        prior["prior_admitted_identities"] + prior["new_admitted_identities"]
    )
    prior_keys = {(item["dataset"], item["path"]) for item in prior_rows}
    counts = prior["effective_counts"]
    _require(
        frozen["scope"]["approved_member_count"]
        == len(members)
        == len(keys)
        == APPROVED_COUNT
        and len(selected) == 1
        and selected[0]["object_class"] == "raw_source_payload"
        and selected[0]["approved_dataset_revision"] == admission.revision
        and counts["frozen_objects"] == APPROVED_COUNT
        and counts["raw_v4_admissions"]
        == counts["raw_admitted_object_reader_canaries"]
        == len(prior_rows)
        == len(prior_keys)
        == PREVIOUS_ADMISSIONS
        and counts["deferred_objects"] == APPROVED_COUNT - PREVIOUS_ADMISSIONS
        and prior_keys <= keys
        and identity not in prior_keys,
        "frozen membership or prior ledger differs",
    )
    total = PREVIOUS_ADMISSIONS + 1
    return {
        "schema_id": "global-medicines-atlas.m112-july-frozen-raw-delivery-reconciliation",
        "schema_version": 1,
        "inputs": {
            path: {"path": path, "sha256": sha} for path, sha in INPUTS.items()
        },
        "effective_counts": {
            "frozen_objects": APPROVED_COUNT,
            "raw_v4_admissions": total,
            "raw_admitted_object_reader_canaries": total,
            "deferred_objects": APPROVED_COUNT - total,
            "frozen_denominator_changed": False,
        },
        "increment": {
            "raw_v4_admissions": 1,
            "raw_admitted_object_reader_canaries": 1,
        },
        "new_admission": {
            "dataset": admission.dataset,
            "path": admission.path,
            "approved_dataset_revision": admission.revision,
            "later_reconciliation_revision": selected[0][
                "current_reconciliation_revision"
            ],
            "sha256": admission.sha256,
            "byte_count": admission.byte_count,
            "contract_sha256": CONTRACT_SHA,
            "workflow_run": RUN,
            "job": JOB,
            "artifact": ARTIFACT_ID,
        },
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
        data[PRIOR], data[FROZEN], data[RECEIPT], data[ARTIFACT], root=root
    )


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
            "effective raw ledger is stale",
        )
    else:
        path.write_bytes(expected)
    print(
        "verified 15 exact raw admissions and reader checks; federation remains open"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
