"""Reconcile four existing MBS projections using value-free metadata only.

The report is a dossier, not an output privacy clearance or v4 admission. It
never reads source XML or Parquet, runs consumers, or publishes dataset bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- Fixed historical Git blobs; no shell.
from datetime import datetime
from operator import itemgetter
from pathlib import Path
from typing import Any

import scripts.qualify_australian_existing_derived_gates as existing
import scripts.qualify_australian_schedule_source_privacy as privacy
import scripts.qualify_m112_existing_reimbursement_batch as bounded

ROOT = Path(__file__).resolve().parents[1]
SOURCE_RECORDS = 6046
P7_RECORDS = 165
PRODUCT_OBJECTS = 2
OUTPUT_OBJECTS = 4
V2 = 2
EVIDENCE_DIR = (
    "quality/qualifications/australian-mbs-four-projection-dossiers-20261115/"
)
INPUTS = {
    key: existing.INPUTS[key]
    for key in ("mbs_scope", "mbs_rights", "mbs_tree", "mbs_f9_disposition")
} | {
    "d781_manifest": (
        EVIDENCE_DIR + "d781-manifest.json",
        "92eda66dcdc34902ec88f3d13faeb61c13d09fb4c944ad7a1ef0be8c2ac1a93c",
    ),
    "d781_receipt": (
        EVIDENCE_DIR + "d781-source-receipt.json",
        "24703e52245ac5605618c4d19be1cea4adc71f067e77a411b274be3b21d60bf7",
    ),
    "d781_publication": (
        EVIDENCE_DIR + "d781-publication.json",
        "bf814073f3d3bd4a1ee82d4d066145a827554b7c054244b4cc11eb9e47abb42e",
    ),
    "d781_admission": (
        EVIDENCE_DIR + "d781-admission.json",
        "0b03029faa0f5abcbf245bfea4b3064074d3a665ee464d99e83e5fc9f33b2a4a",
    ),
    "f9f9_manifest": (
        EVIDENCE_DIR + "f9f9-manifest.json",
        "feea0cb0f8179568e99230afc830571293d99aa4f4de04800b6b43fc0e40115f",
    ),
    "f9f9_receipt": (
        EVIDENCE_DIR + "f9f9-source-receipt.json",
        "e741e662dcdf1d64a187af46d8069effe6323b8664cdc90398c4adcb04cad90d",
    ),
    "f9f9_publication": (
        EVIDENCE_DIR + "f9f9-publication.json",
        "b11cde21c5b4bd8595cb9204b3a9bac24efc9065c6d43ae06c300e3217328d24",
    ),
    "workflow": (
        EVIDENCE_DIR + "workflow-readback.json",
        "aa3c3c8114957cd33bb18264e80dc9d3a7d4d4f585de9faff9abcb9b176831a4",
    ),
    "d781_hosted": (
        "quality/qualifications/australian-m112-mbs-hosted-receipt-20261003.json",
        "64dcd866c212f422c188462c49f0e19fc7e0802e7c2e31c6dad360fa2a958918",
    ),
    "f9f9_lifecycle": (
        "quality/qualifications/australian-mbs-bronze-source-receipt-20261004.json",
        "de64938e8ae5b6c0f91c959e7b2eba6b157f1d50fba41cf1705430b861b6a7f4",
    ),
}
PRODUCTS: dict[str, dict[str, Any]] = {
    "d781": {
        "product_id": "d78170f1944e8c209833b86193d403b12553a3932579dc571ff10f8485a6483b",
        "commit": "12e5ca4678e077f8e6bf954aaa780aac83040994",
        "run_id": 37066153375,
        "event": "schedule",
        "acquisition_id": "caa6da91b9a87a5094fc803b378321430bdd9c609b36298c8205747bc7651e81",
        "receipt_id": "mbs-release:7dc24e0ef99669f379678b9fa8d25eaf8700c659b7576984d2c41a582f96fcd8",
        "revision": "40891976f77ee5e7688edceed25c9ac98a77547e",
        "publication_comment": "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5961659754",
    },
    "f9f9": {
        "product_id": "f9f9af5a152ea74c25a617102e3cf271054ef78867ed0eb84fb69822b6767d63",
        "commit": "644f3f6cfd2b76b0866d5ecb90dde397d67a51eb",
        "run_id": 37163925043,
        "event": "workflow_dispatch",
        "acquisition_id": "fd32879190b69ad98cd2f207ec3b70b725ab8f524218f783ec08bf98b7ffcecd",
        "receipt_id": "mbs-release:dab6a3a2793596b485fb6b1825837a13ade8bce04a897b65002c7794a6832cfb",
        "revision": "abdf414cdea0127d3edda6f8af402d1a01139623",
        "publication_comment": "https://github.com/edithatogo/global-medicines-atlas/issues/340#issuecomment-5974855613",
    },
}
COMMON_CODE = {
    "src/global_medicines_atlas/adapters/au_mbs.py": "f874882bb7e0d3675b791e6cc10393595c705f7b2a977dcff1388a0c27862363",
    "src/global_medicines_atlas/adapters/_receipt.py": "afa94ba955c4723b275addb0b55200636aaf82eeaabcd5ac0b23aefcf2684020",
    "src/global_medicines_atlas/mbs_compatibility.py": "3d7a4263a020a7f9569968b3007f5d10a8a52b067154eed67281bd5a52eae111",
}
PRODUCER_CODE = {
    "d781": COMMON_CODE
    | {
        "src/global_medicines_atlas/mbs_release.py": "41b344750a8612f97b3f49f19505523335e2eb4b8808be35a1a8aaaa70814fad",
        "src/global_medicines_atlas/mbs_publication.py": "8c3c3cee1fdbd57535d44ede632a6d3cd0cfe9d5ae4ebb797d00e4c89ac918b8",
        ".github/workflows/australian-mbs-release.yml": "256ab37f805550b761f04866d5765f12cd3c104eca338e9cc5a4b62f98b333ab",
    },
    "f9f9": COMMON_CODE
    | {
        "src/global_medicines_atlas/mbs_release.py": "d59e04b58783912b557dff53ee536a3cbf7d39725ebb2e77d11bedfc29417828",
        "src/global_medicines_atlas/mbs_publication.py": "c59d04968a0bc47d4641779e3c9f9a2718d7af9a1ddba6947eec6650c8c5c2cf",
        ".github/workflows/australian-mbs-release.yml": "7dbf28bfac50b05fa993b8bb939121983d479978b419518405f2742034529ec8",
    },
}
STEPS = frozenset({
    "Bind main head and exact release authorization",
    "Acquire, append and verify using anonymous reads",
    "Remove verified hosted temporary materializations",
    "Require usable admitted data for a successful update",
})


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _validate_run(
    run: dict[str, Any], product: dict[str, Any], receipt: dict[str, Any]
) -> None:
    jobs = bounded.metadata_rows(run.get("jobs"))
    _require(len(jobs) == 1, "producer workflow jobs differ")
    steps = bounded.metadata_rows(jobs[0].get("steps"))
    _require(
        all((
            run.get("run_id") == product["run_id"],
            run.get("commit") == product["commit"],
            run.get("event") == product["event"],
            run.get("status") == jobs[0].get("status") == "completed",
            run.get("conclusion") == jobs[0].get("conclusion") == "success",
            run.get("url")
            == f"https://github.com/edithatogo/global-medicines-atlas/actions/runs/{product['run_id']}",
            len(steps) == len(STEPS),
            frozenset(step.get("name") for step in steps) == STEPS,
            all(step.get("conclusion") == "success" for step in steps),
            _time(run["created_at"])
            <= _time(receipt["temporal"]["retrieved_at"])
            <= _time(run["updated_at"]),
        )),
        "producer workflow binding differs",
    )


def _validate_product(  # ruff: ignore[too-many-locals] -- The separate metadata joins are intentional.
    name: str,
    documents: dict[str, dict[str, Any]],
    scope_product: dict[str, Any],
    run: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    product = PRODUCTS[name]
    manifest = documents[f"{name}_manifest"]
    receipt = documents[f"{name}_receipt"]
    publication = documents[f"{name}_publication"]
    prefix = f"bronze/mbs/releases/2026-08-01/{product['product_id']}"
    manifest_rows = bounded.metadata_rows(manifest.get("objects"))
    by_role = bounded.metadata_index(manifest_rows, key="role")
    selected = [
        row for row in candidates if row["product_id"] == product["product_id"]
    ]
    _require(
        all((
            scope_product.get("product_id") == product["product_id"],
            scope_product.get("manifest_path") == f"{prefix}/manifest.json",
            scope_product.get("manifest_sha256")
            == INPUTS[f"{name}_manifest"][1],
            manifest.get("source_id") == "au-mbs",
            manifest.get("evidence_class") == "live",
            manifest.get("record_count") == SOURCE_RECORDS,
            manifest.get("p7_record_count") == P7_RECORDS,
            manifest.get("data_acquired") is False,
            manifest["contract"]["dataset"] == existing.DATASET,
            manifest["contract"]["source_id"] == "au-mbs",
            manifest["contract"]["effective_date"] == "2026-08-01",
            manifest["contract"]["publication_authorized"] is True,
            len(selected) == PRODUCT_OBJECTS,
            {row["path"] for row in selected}
            == {
                by_role["source_parquet"]["path"],
                by_role["p7_parquet"]["path"],
            },
            by_role["raw"]["path"] == privacy.SOURCE_PATH,
            by_role["raw"]["sha256"] == privacy.SOURCE_SHA,
            by_role["raw"]["bytes"] == privacy.SOURCE_BYTES,
            by_role["source_receipt"]["path"]
            == f"{prefix}/source-receipt.json",
            by_role["source_receipt"]["sha256"] == INPUTS[f"{name}_receipt"][1],
        )),
        "MBS manifest or source binding differs",
    )
    sensitivity = receipt["sensitivity"]
    _require(
        all((
            receipt.get("receipt_id") == product["receipt_id"],
            receipt.get("evidence_class") == "live",
            receipt["source"]["source_id"] == "au-mbs",
            receipt["source"]["catalog_version"] == "2026-08-01",
            receipt["payload"]["sha256"]
            == receipt["temporal"]["content_id"]
            == privacy.SOURCE_SHA,
            receipt["payload"]["byte_count"] == privacy.SOURCE_BYTES,
            receipt["temporal"]["acquisition_id"] == product["acquisition_id"],
            receipt["retrieval"]["uri"] == manifest["contract"]["source_url"],
            receipt["retrieval"]["status"] == "succeeded",
            receipt["retrieval"]["retrieved_at"]
            == receipt["temporal"]["retrieved_at"],
            receipt["retrieval"]["http"]["acquisition_agent_version"].endswith(
                "g" + product["commit"][:9]
            ),
            receipt["rights_state"] == "permitted",
            sensitivity.get("schema_id")
            == "global-medicines-atlas.bronze-sensitivity-classification",
            sensitivity.get("schema_version") == 1,
            sensitivity.get("data_sensitivity") == "non_sensitive",
            sensitivity.get("personal_data") == "none",
            sensitivity.get("publication") == "permitted",
            set(sensitivity.get("reason_codes", []))
            == {"qualified_official_mbs_schedule", "exact_release_approval"},
            receipt["transformation"]["transformation_id"]
            == "raw-acquisition-v1",
            receipt["transformation"]["output_sha256"] == privacy.SOURCE_SHA,
            receipt["transformation"]["output_byte_count"]
            == privacy.SOURCE_BYTES,
        )),
        "MBS source receipt or privacy binding differs",
    )
    _validate_run(run, product, receipt)
    _require(
        all((
            publication.get("schema_id")
            == "global-medicines-atlas.mbs-hosted-publication",
            publication.get("dataset") == existing.DATASET,
            publication.get("manifest_path") == f"{prefix}/manifest.json",
            publication.get("manifest_sha256") == INPUTS[f"{name}_manifest"][1],
            publication.get("workflow_commit") == product["commit"],
            publication.get("workflow_run") == run["url"],
            publication.get("revision") == product["revision"],
            publication.get("anonymous_digest_verification") == "passed",
            publication.get("verified_objects") == len(manifest_rows) + 1,
            publication.get("record_count") == manifest["record_count"],
            publication.get("data_acquired") is True,
            publication.get("temporary_source_bytes_removed") is True,
        )),
        "MBS publication receipt differs",
    )
    if name == "d781":
        admission = documents["d781_admission"]
        hosted = documents["d781_hosted"]
        _require(
            all((
                manifest.get("schema_id")
                == "global-medicines-atlas.mbs-release",
                manifest.get("admission_state") == "accepted",
                by_role["admission"]["sha256"] == INPUTS["d781_admission"][1],
                admission.get("schema_id")
                == "global-medicines-atlas.bronze-admission",
                admission.get("state") == "accepted",
                admission.get("reviewer_status") == "unreviewed",
                admission.get("acquisition_id") == product["acquisition_id"],
                admission.get("content_id") == privacy.SOURCE_SHA,
                admission.get("supersedes_decision_id") is None,
                hosted["admission"]["landed_predecessor_present"] is False,
                hosted["hosted_receipt"]["manifest_sha256"]
                == INPUTS["d781_manifest"][1],
            )),
            "MBS legacy Bronze admission differs",
        )
        bronze = "accepted_unreviewed_predecessor_not_recorded_not_v4"
        raw_lifecycle = "no_landed_predecessor_in_legacy_producer_receipt"
    else:
        lifecycle = documents["f9f9_lifecycle"]
        _require(
            all((
                manifest.get("schema_id")
                == "global-medicines-atlas.mbs-release-v2",
                manifest.get("schema_version") == V2,
                manifest.get("profile_state") == "accepted",
                "admission" not in by_role,
                lifecycle.get("acquisition_id") == product["acquisition_id"],
                lifecycle.get("admission_state") == "accepted",
                lifecycle.get("qualification_scope") == "raw_b1_b2_only",
                lifecycle["hosted_publication"]["workflow_run"] == run["url"],
            )),
            "MBS v2 profile or raw lifecycle differs",
        )
        bronze = "product_sidecar_not_observed_at_pinned_revision"
        raw_lifecycle = "separately_accepted_raw_b1_b2_not_projection_admission"
    result: list[dict[str, Any]] = []
    for candidate in selected:
        role = (
            "p7_parquet"
            if candidate["path"].endswith("/p7.parquet")
            else "source_parquet"
        )
        obj = by_role[role]
        _require(
            all((
                obj["path"]
                == f"{prefix}/{'p7.parquet' if role == 'p7_parquet' else 'source.parquet'}",
                obj["path"] == candidate["path"],
                obj["sha256"] == candidate["sha256"],
                obj["bytes"] == candidate["byte_count"],
                candidate["privacy"] == "not_qualified_in_selected_evidence",
                candidate["v4_admission"] == "not_performed",
            )),
            "MBS projection identity differs",
        )
        result.append({
            **candidate,
            "role": role,
            "status": "dossier_completed_output_gates_blocked",
            "producer_reported_records": manifest[
                "p7_record_count" if role == "p7_parquet" else "record_count"
            ],
            "source_sha256": privacy.SOURCE_SHA,
            "source_receipt_acquisition_id": product["acquisition_id"],
            "source_privacy": "non_sensitive_in_exact_producer_source_receipt",
            "output_privacy": "not_qualified_without_output_specific_evidence",
            "producer_lineage": "manifest_and_historical_producer_code_bound_independent_reproduction_not_performed",
            "historical_primary_digest_verification": "passed_for_manifest_and_its_objects",
            "bronze_state": bronze,
            "raw_lifecycle": raw_lifecycle,
            "producer": name,
            "publication_receipt": f"{name}_publication",
            "manifest": f"{name}_manifest",
            "source_receipt": f"{name}_receipt",
            "remaining": [
                "Qualify exact output-specific privacy and source-to-output lineage without exposing participant or cohort data.",
                "Complete product-specific federation-v4 contract and separate admission decision.",
                "Qualify independent recovery and authorized consumer checks.",
            ],
        })
    return result


def build_report(root: Path = ROOT) -> dict[str, Any]:
    """Build four explicit dispositions from pinned metadata, not payloads."""
    documents = {
        name: bounded.read_bound_metadata(root, *binding)
        for name, binding in INPUTS.items()
    }
    _require(
        documents["mbs_rights"]["boundaries"]["consumer_canaries_authorized"]
        is False,
        "MBS consumer authorization boundary differs",
    )
    candidates = existing.mbs_candidates(documents)
    scope_products = bounded.metadata_index(
        bounded.metadata_rows(documents["mbs_scope"]["products"]),
        key="product_id",
    )
    runs = bounded.metadata_index(
        bounded.metadata_rows(documents["workflow"]["runs"]), key="url"
    )
    _require(
        len(runs) == len(PRODUCTS) == len(scope_products),
        "producer workflow or product count differs",
    )
    dossiers: list[dict[str, Any]] = []
    for name, product in PRODUCTS.items():
        url = f"https://github.com/edithatogo/global-medicines-atlas/actions/runs/{product['run_id']}"
        dossiers.extend(
            _validate_product(
                name,
                documents,
                scope_products[product["product_id"]],
                runs[url],
                candidates,
            )
        )
    _require(
        len(dossiers) == OUTPUT_OBJECTS
        and len({row["path"] for row in dossiers}) == OUTPUT_OBJECTS,
        "four projection dossiers required",
    )
    return {
        "schema_id": "global-medicines-atlas.australian-mbs-four-projection-dossiers",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "inputs": {
            name: {"path": path, "sha256": digest}
            for name, (path, digest) in INPUTS.items()
        },
        "producers": {
            name: {**product, "code_sha256": PRODUCER_CODE[name]}
            for name, product in PRODUCTS.items()
        },
        "dossiers": sorted(dossiers, key=itemgetter("path")),
        "summary": {
            "dossiers_completed": 4,
            "output_privacy_qualified": 0,
            "new_v4_admissions": 0,
            "new_consumer_canaries": 0,
            "independent_recoveries_qualified": 0,
        },
        "limitations": [
            "Producer manifests, historical code and anonymous digest receipts support declared lineage; they do not replace a source-to-output replay or output-specific privacy assessment.",
            "The source-receipt transformation describes raw acquisition, not the Parquet transformation.",
            "Manifest row counts are producer-reported, not measured by this metadata-only check.",
            "The recorded public-release attestation does not authorize v4 admission or consumer canaries; the primary archive is not an independent replica.",
            "The four outputs are outside the frozen M-112 inventory and do not change its admission denominator.",
        ],
        "boundaries": {
            "source_or_projection_payload_read": False,
            "participant_or_cohort_data_accessed": False,
            "dataset_added_or_published": False,
            "rights_conclusion_changed": False,
            "v4_admission_performed": False,
            "consumer_canary_performed": False,
            "frozen_inventory_changed": False,
            "federation_accepted": False,
        },
    }


def check_producer_code(root: Path = ROOT) -> int:
    """Verify the historical code hashes when the local Git history is present."""
    git = shutil.which("git")
    if git is None:
        raise FileNotFoundError(
            "git is required to verify historical producer code"
        )
    count = 0
    for name, files in PRODUCER_CODE.items():
        for path, expected in files.items():
            result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] -- Both commit and path are fixed constants.
                [git, "show", f"{PRODUCTS[name]['commit']}:{path}"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            _require(
                hashlib.sha256(result.stdout).hexdigest() == expected,
                "historical producer code digest differs",
            )
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--report", type=Path)
    group.add_argument("--check", type=Path)
    group.add_argument("--check-producer-code", action="store_true")
    args = parser.parse_args()
    if args.check_producer_code:
        print(
            json.dumps({
                "historical_code_blobs_verified": check_producer_code()
            })
        )
        return 0
    report = build_report()
    if args.report:
        with args.report.open("x", encoding="utf-8") as target:
            json.dump(report, target, indent=2, sort_keys=True)
            target.write("\n")
    elif json.loads(args.check.read_text(encoding="utf-8")) != report:
        raise ValueError("stored MBS projection dossiers differ")
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
