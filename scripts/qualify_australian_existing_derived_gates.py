"""Check retained Australian derived-object evidence without reading payloads.

This metadata-only packet does not assess unknown source sensitivity, create
admissions, run live canaries, publish data, or establish independent recovery.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from http import HTTPStatus
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded
from scripts.qualify_pbs_reproduced_v4 import validate_publication_receipt

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "quality/qualifications/"
SILVER_DIR = (
    PREFIX
    + "australian-mbs-silver-v4-admission-remote-read-20261028-40664169948/"
)
PBS_DIR = PREFIX + "pbs-reproduced-publication-20261102-41395493749/"
INPUTS = {
    "mbs_scope": (
        PREFIX
        + "australian-mbs-public-august-projection-scope-exception-20261020.json",
        "b8fb9f024cea21f4364db9867c73a44afea61615148b49a7ffd7bfffdf6edac2",
    ),
    "mbs_rights": (
        PREFIX
        + "australian-mbs-august-outside-m112-projection-rights-attestation-20261020.json",
        "dc5a53ffaed82e758bbe918f0615b5158bdbdf65ad41da2193c6c84ba41841c5",
    ),
    "mbs_tree": (
        PREFIX
        + "australian-mbs-august-projection-current-tree-readback-20261028.json",
        "941d85a576523bdf0bfa5a137ebbddac503c939b0fe6f75abe57c6828a6c4c03",
    ),
    "mbs_f9_disposition": (
        PREFIX + "australian-mbs-august-f9f9-prefix-disposition-20261028.json",
        "30f04f37de72252648fe1a4c07c6488024f56c10cec35d810f3e91534155aaf4",
    ),
    "pbs_readiness": (
        PREFIX + "pbs-reproduced-v4-evidence-readiness-20261029.json",
        "d581fb505eca81ea2e984941d53c57218bbafcfc9c2de23a6718caf32ea01946",
    ),
    "pbs_rights": (
        PREFIX
        + "australian-pbs-reproduced-silver-output-rights-attestation-20261029.json",
        "93e0d64ec428ae157e030432e8cce70751df54ec111b9fa11319c74206a3c216",
    ),
    "pbs_manifest": (
        PBS_DIR + "manifest.json",
        "ea753c739af3053a88a691662641c7d6125e29b1ea4dbf4c67792b8b744526f6",
    ),
    "pbs_publication": (
        PBS_DIR + "publication.json",
        "2316c52d97aee8041b104c7b621363b4b1f16f4cb1a073177e902e86acf74294",
    ),
    "pbs_verification": (
        PBS_DIR + "independent-anonymous-verification.json",
        "cd22a66db032b973d33f9f942bb9a9b0d1eff2cf626a73d128a9158813358dd6",
    ),
    "pbs_preparation": (
        PBS_DIR + "preparation.json",
        "a831895ec9d33ff5e51537badec6ceb5ebe4d6b8a0cf4dabff8555ac52702d92",
    ),
    "pbs_package": (
        PBS_DIR + "package-manifest.json",
        "21fe6849ed3116254570207fdaf36b5e9f5f6561f18a7068b8a85b0c3b4456ae",
    ),
    "consumer_manifest": (
        SILVER_DIR + "artifact-manifest.json",
        "e6b73c3c086776a121b8500c06f6b1a4a5e31f7ebc101d3d00968f8d7beff40c",
    ),
    "consumer_receipt": (
        SILVER_DIR + "admission-remote-read.json",
        "b48eedc7de599f646fe4c722b2ac869c6ebbe9935be09f58464d4f7b2ab71b12",
    ),
    "consumer_semantic_manifest": (
        PREFIX + "australian-mbs-silver-semantic-manifest-20261017.json",
        "9ad5e2747949b8b7142819e981241c1f74105b3570d78025e654e780241c5882",
    ),
}
DATASET = "edithatogo/australian-mbs-source-archive"
MBS_REVISION = "b925a8a80b0f90db09513e7ce1378045461b05c0"
MBS_RIGHTS_REVISION = "42d73b6facac016f14a335d36d83f1a3b630add8"
SILVER_REVISION = "3d2d528439bddf6f42e8e700c88917f0960a9f38"
PBS_REVISION = "3995deb3e2a82f09472d6a78020fb13bbbc96056"
PBS_COMMIT = "fc42041037b4ae4133acc1ef361dbb4543df201f"
MBS_OBJECTS = 4
MBS_PRODUCTS = 2
CONSUMER_OBJECTS = 6
CANARY_ROWS = 2
CONSUMER_RUN = 40664169948
CONSUMER_TABLES = frozenset({
    "services",
    "hierarchy",
    "descriptions",
    "fees",
    "benefits",
    "caps",
})


def _canonical_sha(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def _same_object(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(
        left.get(key) == right.get(key)
        for key in ("path", "sha256", "byte_count")
    )


def mbs_candidates(  # ruff: ignore[too-many-locals] -- Keep distinct object and sidecar checks explicit.
    sources: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Bind each outside-inventory MBS object without inferring its privacy."""
    scope, rights, tree = (
        sources[key] for key in ("mbs_scope", "mbs_rights", "mbs_tree")
    )
    if not all((
        scope.get("dataset") == rights.get("dataset") == DATASET,
        scope.get("revision") == rights.get("revision") == MBS_RIGHTS_REVISION,
        tree["dataset"]["id"] == DATASET,
        tree["dataset"]["revision"] == MBS_REVISION,
        rights.get("public_release_rights_attested") is True,
        rights["boundaries"]["v4_admission_or_promotion_authorized"] is False,
        rights["boundaries"]["consumer_canaries_authorized"] is False,
        scope["scope"]["frozen_m112_object_count"] == bounded.FROZEN_OBJECTS,
        scope["scope"]["frozen_inventory_membership_changed"] is False,
    )):
        raise ValueError("MBS scope or rights evidence differs")
    expected = bounded.metadata_index(
        bounded.metadata_rows(scope.get("objects"))
    )
    attested = bounded.metadata_index(
        bounded.metadata_rows(rights.get("authorized_objects"))
    )
    observed = bounded.metadata_index(
        bounded.metadata_rows(tree["readback"]["objects"])
    )
    if (
        len(expected) != MBS_OBJECTS
        or set(expected) != set(attested)
        or set(expected) != set(observed)
    ):
        raise ValueError("MBS four-object identities differ")
    sidecars = {
        row["product_id"]: row
        for row in bounded.metadata_rows(
            tree["readback"]["product_admission_sidecars"]
        )
    }
    products = {
        row["product_id"]: row
        for row in bounded.metadata_rows(scope.get("products"))
    }
    if len(sidecars) != MBS_PRODUCTS or set(sidecars) != set(products):
        raise ValueError("MBS product identities differ")
    f9 = sources["mbs_f9_disposition"]
    deferred_id = f9["disposition"]["product_id"]
    if not all((
        f9["disposition"]["state"] == "deferred_not_admitted",
        deferred_id in sidecars,
        sidecars[deferred_id]["http_status"] == HTTPStatus.NOT_FOUND,
        {row["path"] for row in f9["objects"]}
        == {
            path
            for path, row in expected.items()
            if row["product_id"] == deferred_id
        },
    )):
        raise ValueError("MBS deferred product disposition differs")
    output: list[dict[str, Any]] = []
    for path in sorted(expected):
        row, auth, readback = expected[path], attested[path], observed[path]
        bounded.metadata_identity(row)
        if not all((
            _same_object(row, auth),
            _same_object(row, readback),
            readback.get("lfs_sha256") == row.get("sha256"),
            auth.get("dataset") == DATASET,
            auth.get("revision") == MBS_RIGHTS_REVISION,
            row.get("in_frozen_m112_inventory") is False,
            sidecars[row["product_id"]].get("federation_v4_admission") is False,
        )):
            raise ValueError("MBS candidate object binding differs")
        product_id = row["product_id"]
        sidecar = sidecars[product_id]
        if sidecar["http_status"] == HTTPStatus.OK:
            if (
                sidecar.get("state") != "accepted"
                or sidecar.get("reviewer_status") != "unreviewed"
            ):
                raise ValueError("MBS Bronze sidecar state differs")
            bronze = "accepted_unreviewed_not_v4"
        elif sidecar["http_status"] == HTTPStatus.NOT_FOUND:
            bronze = "sidecar_not_observed_at_pinned_revision"
        else:
            raise ValueError("MBS sidecar observation differs")
        output.append({
            "dataset": DATASET,
            "revision": MBS_REVISION,
            "path": path,
            "sha256": row["sha256"],
            "byte_count": row["byte_count"],
            "product_id": product_id,
            "frozen_m112_member": False,
            "rights": "maintainer_attested_exact_path_digest_at_prior_revision",
            "rights_attestation_revision": MBS_RIGHTS_REVISION,
            "privacy": "not_qualified_in_selected_evidence",
            "bronze_state_at_pinned_revision": bronze,
            "v4_admission": "not_performed",
            "consumer_check": "not_performed",
            "independent_recovery": "not_qualified",
            "payload_read_permitted_by_this_report": False,
        })
    return output


def pbs_candidate(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Resolve the old public-location blocker while preserving all other gates."""
    ready, rights, manifest = (
        sources[key] for key in ("pbs_readiness", "pbs_rights", "pbs_manifest")
    )
    publication = sources["pbs_publication"]
    raw = json.dumps(publication).encode()
    validated = validate_publication_receipt(
        raw, workflow_commit=PBS_COMMIT, run_id="41395493749", run_attempt="1"
    )
    verification, preparation, package = (
        sources[key]
        for key in ("pbs_verification", "pbs_preparation", "pbs_package")
    )
    output, authorized = ready["output"], rights["authorized_output"]
    if not all((
        ready.get("status") == "candidate_evidence_matched_not_admitted",
        ready["evidence"]["prior_field_state_receipt_names_prior_output"]
        is True,
        ready["evidence"]["independent_builds_use_same_algorithm"] is True,
        rights.get("public_release_rights_attested") is True,
        rights["boundaries"]["instrument_independently_reviewed"] is False,
        output["id"]
        == authorized["output_id"]
        == manifest["output_id"]
        == preparation["output_id"]
        == package["output_id"],
        output["parquet_sha256"]
        == authorized["parquet_sha256"]
        == manifest["parquet_sha256"]
        == validated["sha256"]
        == verification["sha256"]
        == package["parquet"]["sha256"],
        output["parquet_bytes"]
        == authorized["parquet_bytes"]
        == validated["bytes"]
        == verification["bytes"]
        == package["parquet"]["bytes"],
        output["native_core_sha256"]
        == authorized["native_core_sha256"]
        == preparation["native_core_sha256"]
        == package["coverage"]["native_core_sha256"],
        output["source_member_sha256"]
        == authorized["member_sha256"]
        == preparation["source_member_sha256"]
        == package["member_binding"]["member_payload"]["sha256"],
        validated["dataset"] == verification["dataset"] == manifest["dataset"],
        validated["revision"]
        == verification["revision"]
        == manifest["revision"]
        == PBS_REVISION,
        validated["path"] == verification["path"],
        verification["account_authentication_used"] is False,
        verification["local_payload_retained"] is False,
        verification["verification"] == "independent_streaming_sha256",
        manifest["status"] == "authenticated_not_admitted",
        manifest["files"]["publication.json"] == INPUTS["pbs_publication"][1],
        manifest["files"]["preparation.json"] == INPUTS["pbs_preparation"][1],
        manifest["files"]["package-manifest.json"] == INPUTS["pbs_package"][1],
        manifest["v4_admission_performed"] is False,
        manifest["consumer_canaries_run"] is False,
    )):
        raise ValueError("PBS candidate evidence differs")
    return {
        "dataset": validated["dataset"],
        "revision": PBS_REVISION,
        "path": validated["path"],
        "sha256": validated["sha256"],
        "byte_count": validated["bytes"],
        "output_id": output["id"],
        "public_location": "prior_hosted_and_anonymous_digest_verification_passed",
        "prior_missing_location_note": "superseded_for_this_exact_output_only",
        "rights": "maintainer_attested_exact_output_instrument_not_independently_reviewed",
        "privacy": "not_qualified_in_selected_evidence",
        "field_state": "prior_receipt_names_different_output",
        "independent_builds": "two_executions_same_algorithm",
        "v4_admission": "not_performed",
        "consumer_check": "not_performed",
        "independent_recovery": "not_qualified",
        "payload_read_permitted_by_this_report": False,
    }


def checked_consumers(  # ruff: ignore[too-many-locals] -- Validate each independently bound evidence role.
    root: Path,
    receipt: dict[str, Any],
    manifest: dict[str, Any],
    source_semantics: dict[str, Any],
) -> list[dict[str, Any]]:
    """Revalidate six previously admitted MBS contracts and historical canaries."""
    if not all((
        receipt.get("status") == "passed",
        receipt.get("dataset") == DATASET,
        receipt.get("revision") == SILVER_REVISION,
        receipt.get("verified_object_count") == CONSUMER_OBJECTS,
        receipt["boundaries"]["source_values_included"] is False,
        receipt["boundaries"]["new_sources_added"] is False,
        receipt["boundaries"]["external_publication_performed"] is False,
        manifest["workflow"]["run_id"] == CONSUMER_RUN,
        manifest["validation"]["hosted_workflow_conclusion"] == "success",
        source_semantics.get("status")
        == "qualified_exact_source_era_semantics",
        source_semantics["public_dataset_identity"]["dataset"] == DATASET,
        source_semantics["public_dataset_identity"]["current_revision"]
        == SILVER_REVISION,
    )):
        raise ValueError("MBS consumer receipt boundary differs")
    canary = receipt["consumer_canary"]
    if not all((
        canary.get("status") == "passed",
        canary.get("request_count") == CONSUMER_OBJECTS,
        canary.get("browser_qualification") == "passed",
        canary.get("source_completeness") == "not_established",
        canary.get("surface_request_counts")
        == dict.fromkeys(
            ("api", "atlas", "cli_json", "cli_jsonl"), CONSUMER_OBJECTS
        ),
    )):
        raise ValueError("MBS consumer canary summary differs")
    reports = bounded.metadata_index(
        bounded.metadata_rows(manifest.get("reports"))
    )
    objects = bounded.metadata_rows(receipt.get("objects"))
    reads = bounded.metadata_rows(receipt.get("remote_reads"))
    evidence = bounded.metadata_rows(canary.get("evidence"))
    semantic_tables = {
        row["name"]: row
        for row in bounded.metadata_rows(source_semantics.get("tables"))
    }
    if not (
        len(objects)
        == len(reads)
        == len(evidence)
        == len(semantic_tables)
        == CONSUMER_OBJECTS
    ):
        raise ValueError("MBS consumer denominator differs")
    output: list[dict[str, Any]] = []
    for obj, read, check in zip(objects, reads, evidence, strict=True):
        name = obj["table"]
        if name not in CONSUMER_TABLES or name not in semantic_tables:
            raise ValueError("unexpected MBS consumer table")
        contract_name = f"metadata/contracts/{name}.json"
        semantic_name = f"metadata/semantics/{name}.json"
        contract = bounded.read_bound_metadata(
            root, SILVER_DIR + contract_name, reports[contract_name]["sha256"]
        )
        bounded.read_bound_metadata(
            root, SILVER_DIR + semantic_name, reports[semantic_name]["sha256"]
        )
        location, rights, admitted = (
            contract["location"],
            contract["rights"],
            obj["admission_record"],
        )
        semantic = semantic_tables[name]
        request_hashes = {
            _canonical_sha({
                "resource_id": obj["resource_id"],
                "columns": [field["native_name"] + "__native_value"],
                "limit": CANARY_ROWS,
            })
            for field in bounded.metadata_rows(semantic["native_fields"])
        }
        expected_sha, expected_bytes = (
            semantic["sha256"],
            semantic["byte_count"],
        )
        if not all((
            obj["path"] == semantic["path"],
            obj["sha256"] == expected_sha,
            obj["byte_count"] == expected_bytes,
            reports[contract_name]["sha256"]
            == obj["contract_sha256"]
            == admitted["contract_sha256"]
            == read["contract_sha256"],
            reports[semantic_name]["sha256"] == obj["semantic_sha256"],
            location["dataset"]
            == admitted["dataset"]
            == rights["dataset"]
            == DATASET,
            location["revision"] == admitted["revision"] == SILVER_REVISION,
            location["path"]
            == admitted["path"]
            == rights["path"]
            == obj["path"],
            location["sha256"]
            == admitted["sha256"]
            == rights["subject_sha256"]
            == read["object_sha256"]
            == expected_sha,
            location["bytes"]
            == admitted["byte_count"]
            == read["byte_count"]
            == expected_bytes,
            location["private"] is False,
            location["gated"] is False,
            rights["sensitivity"] == "non_sensitive",
            rights["publication"] == "approved_exact_scope",
            admitted["layer"] == "silver",
            admitted["representation"] == "projection",
            read["resource_id"] == obj["resource_id"],
            read["status"] == "passed",
            read["origin"] == "remote",
            check["request_sha256"] in request_hashes,
            check["api_http_status"]
            == check["atlas_http_status"]
            == check["browser"]["http_status"]
            == HTTPStatus.OK,
            check["cli_exit_code"] == check["export_exit_code"] == 0,
            check["row_count"]
            == check["export_row_count"]
            == check["atlas_rendered_row_count"]
            == check["browser"]["row_count"]
            == CANARY_ROWS,
        )):
            raise ValueError(
                "MBS consumer object, privacy or canary evidence differs"
            )
        output.append({
            "table": name,
            "resource_id": obj["resource_id"],
            "dataset": DATASET,
            "revision": SILVER_REVISION,
            "path": obj["path"],
            "sha256": expected_sha,
            "byte_count": expected_bytes,
            "contract_sha256": obj["contract_sha256"],
            "privacy": "non_sensitive_in_exact_previously_admitted_contract",
            "admission": "previously_admitted_candidate_product",
            "consumer_check": "previous_historical_hosted_five_surface_canary_passed",
            "consumer_request_sha256": check["request_sha256"],
        })
    if {row["table"] for row in output} != set(CONSUMER_TABLES):
        raise ValueError("duplicate or missing MBS consumer table")
    return output


def build_report(root: Path = ROOT) -> dict[str, Any]:
    """Build a reproducible value-free readiness and prior-consumer packet."""
    source = {
        name: bounded.read_bound_metadata(root, *binding)
        for name, binding in INPUTS.items()
    }
    mbs = mbs_candidates(source)
    pbs = pbs_candidate(source)
    consumers = checked_consumers(
        root,
        source["consumer_receipt"],
        source["consumer_manifest"],
        source["consumer_semantic_manifest"],
    )
    return {
        "schema_id": "global-medicines-atlas.australian-existing-derived-gate-check",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "inputs": {
            name: {"path": path, "sha256": digest}
            for name, (path, digest) in INPUTS.items()
        },
        "result": {
            "mbs_outside_frozen_candidates": len(mbs),
            "pbs_silver_candidates": 1,
            "candidate_privacy_qualified_by_this_check": 0,
            "new_admissions": 0,
            "new_live_consumer_canaries": 0,
            "previous_mbs_silver_consumer_objects_revalidated": len(consumers),
        },
        "mbs_candidates": mbs,
        "pbs_candidate": pbs,
        "prior_mbs_consumer_objects": consumers,
        "limits": [
            "An attested public-release permission is not v4 admission or a new privacy assessment.",
            "The six consumer outcomes are historical retained receipts, not fresh live runs or new unique admissions.",
            "An anonymous digest check from the primary Hub is not an administratively independent recovery replica.",
        ],
        "boundaries": {
            "source_payload_read": False,
            "individual_participant_or_cohort_data_accessed": False,
            "dataset_published_or_modified": False,
            "rights_scope_changed": False,
            "v4_admission_performed": False,
            "federation_accepted": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--report", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args()
    report = build_report()
    if args.report:
        with args.report.open("x", encoding="utf-8") as target:
            json.dump(report, target, indent=2, sort_keys=True)
            target.write("\n")
    elif json.loads(args.check.read_text(encoding="utf-8")) != report:
        raise ValueError("stored derived-gate report differs")
    print(json.dumps(report["result"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
