"""Qualify one existing July MBS raw pin for v4 and a hosted reader canary.

This uses only previously assessed source bytes and existing public metadata.
It does not publish, add data, promote a projection or establish a replica.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_m112_pbs_v4_admission as shared
import scripts.qualify_mbs_frozen_primary_history as primary
import scripts.qualify_mbs_frozen_raw_replay as lineage
import scripts.reconcile_mbs_frozen_v3_replays as replays
from scripts.qualify_m112_v4_july2016_admission import (
    run_reader_canary,
    validate_contract,
)

from global_medicines_atlas.federation_admission import (
    TrustedAdmissionProfile,
    admit_closed_contract,
)
from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main,
)
from global_medicines_atlas.federation_receipt_closure import ReceiptRole

ROOT = Path(__file__).resolve().parents[1]
REPO = "edithatogo/global-medicines-atlas"
EVIDENCE_COMMIT = "c427dc839fa92b238a12739d7f3615573868efb3"
SCHEMA_COMMIT = "a5753b1c79ccedd9bb54112bf803882ffc9deb96"
SCHEMA = "contracts/medallion/v4.1/federation.schema.json"
SCHEMA_SHA = "03acfbafd80daf0b8b768f7814dbb29a9bd13e7c9d5d68797b30261da29770c6"
OUTPUT = "quality/qualifications/australian-mbs-july-frozen-v4-20261115/contract.json"
SILVER_PROFILE = "quality/qualifications/australian-mbs-silver-v4-admission-remote-read-20261028-40664169948/metadata/contracts/services.json"
DISCOVERY = "quality/qualifications/australian-m112-v4-discovery-role-evidence-20261020.json"
DIGEST = "quality/qualifications/australian-existing-mbs-digest-20261115/hosted-43687742836/digest-receipt.json"
INPUTS = {
    SILVER_PROFILE: "6d33e261a8480edac398a863c1bbbb05630c5921651967b3994f9d4ebcd84423",
    DISCOVERY: "7ac0aaa104f972663d552f915fbdc35d0817d1e19bb10e5530c023859fbc8556",
    DIGEST: "bbfd25983a89d7aba244a71bd2372b6c23f7d05cc2065a3506bf49e618f08191",
    lineage.LINEAGE_PATH: "0fcb259762fb70eb2fad811d95b2c9396e9497e6a354ed424126e135f39ddbac",
    lineage.V1_PATH: "288072cbfbbaee7efe4f35d8ed84487233da9dc025b5099f6091696456d1921c",
}


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _reference(path: str, sha256: str) -> dict[str, str]:
    return {
        "url": f"https://raw.githubusercontent.com/{REPO}/{EVIDENCE_COMMIT}/{path}",
        "sha256": sha256,
    }


def _one(rows: list[dict[str, Any]], path: str) -> dict[str, Any]:
    matches = [row for row in rows if row["path"] == path]
    _require(len(matches) == 1, "exact July object is not unique")
    return matches[0]


def candidate(root: Path = ROOT) -> tuple[bytes, TrustedAdmissionProfile]:  # ruff: ignore[too-many-locals] -- independently bind each receipt role
    """Construct the exact contract and independent trust from retained evidence."""
    values = {
        path: bounded.read_bound_metadata(root, path, digest)
        for path, digest in INPUTS.items()
    }
    _require(
        hashlib.sha256((root / SCHEMA).read_bytes()).hexdigest() == SCHEMA_SHA,
        "federation schema differs",
    )
    history = primary.build(root)
    crosswalk, v1, _plans = lineage.build(root)
    replay = _one(replays.build(root)["objects"], lineage.JULY)
    provenance = _one(crosswalk["objects"], lineage.JULY)["provenance"]
    target = provenance["target"]
    life = provenance["historical_b1_b2"]
    source_receipt = bounded.read_bound_metadata(
        root, life["source_receipt"]["path"], life["source_receipt"]["sha256"]
    )
    event = bounded.read_bound_metadata(
        root,
        life["acquisition_event"]["path"],
        life["acquisition_event"]["sha256"],
    )
    silver = values[SILVER_PROFILE]
    silver_source = silver["source"]
    digest_receipt = values[DIGEST]
    verified = _one(digest_receipt["objects"], lineage.JULY)
    history_row = _one(history["objects"], lineage.JULY)
    _require(
        values[lineage.LINEAGE_PATH] == crosswalk
        and values[lineage.V1_PATH] == v1
        and history_row["historical_primary_restore"] == "exact_inventory_match"
        and history["primary_memory"]["exact_objects_passed"]
        == primary.MEMORY_OBJECT_COUNT
        and replay["status"] == "passed"
        and all(
            target[key] == replay[key] == verified[key]
            for key in ("dataset", "revision", "path", "sha256", "byte_count")
        )
        and source_receipt["sensitivity"]["data_sensitivity"] == "non_sensitive"
        and source_receipt["payload"]["sha256"] == target["sha256"]
        and event["acquisition_id"]
        == silver_source["acquisition_id"]
        == life["acquisition_id"]
        and silver_source["source_id"] == "au-mbs"
        and silver_source["schema_era"] == life["source_version"]
        and silver_source["comparison_cohort"] == "legacy"
        and silver_source["effective_date"] == "2025-07-01"
        and silver_source["retrieved_at"] == event["retrieved_at"]
        and silver["lineage"]["inputs"][0]["sha256"]
        == life["source_receipt"]["sha256"]
        and digest_receipt["workflow_run"] == "43687742836"
        and digest_receipt["boundaries"]["payload_bytes_persisted_or_emitted"]
        is False,
        "July evidence identity, privacy or source profile differs",
    )
    collection = values[DISCOVERY]["collection"]
    estate = values[DISCOVERY]["estate_registry"]
    _require(
        lineage.DATASET in collection["matching_dataset_members"]
        and any(
            x["repo_id"] == lineage.DATASET and x["access"] == "public"
            for x in estate["entries"]
        ),
        "existing source-archive discovery metadata differs",
    )
    rights = _reference(
        provenance["rights_evidence"]["path"],
        provenance["rights_evidence"]["sha256"],
    )
    inputs = [
        _reference(life[name]["path"], life[name]["sha256"])
        for name in ("source_receipt", "acquisition_event", "b2_manifest")
    ]
    inputs.append(
        _reference(lineage.LINEAGE_PATH, INPUTS[lineage.LINEAGE_PATH])
    )
    v1_ref = _reference(lineage.V1_PATH, INPUTS[lineage.V1_PATH])
    v3_ref = _reference(replay["receipt"]["path"], replay["receipt"]["sha256"])
    verification = _reference(DIGEST, INPUTS[DIGEST])
    historical = {
        "url": history["source_receipt"]["url"],
        "sha256": history["source_receipt"]["sha256"],
    }
    start = datetime.fromisoformat(replay["hosted_workflow"]["started_at"])
    expiry = start + timedelta(minutes=15)
    estate_ref = {
        "url": f"https://huggingface.co/datasets/{estate['dataset']}/resolve/{estate['revision']}/{estate['catalog_path']}",
        "sha256": estate["catalog_sha256"],
    }
    location = {
        "dataset": target["dataset"],
        "revision": target["revision"],
        "path": target["path"],
        "bytes": target["byte_count"],
        "sha256": target["sha256"],
    }
    source = {
        "source_id": "au-mbs",
        "acquisition_id": life["acquisition_id"],
        "layer": "bronze",
        "bronze_stratum": "B2",
        "representation": "raw",
        "schema_era": silver_source["schema_era"],
        "comparison_cohort": silver_source["comparison_cohort"],
        "effective_date": silver_source["effective_date"],
        "retrieved_at": event["retrieved_at"],
    }
    document: dict[str, Any] = {
        "version": "4.1.0",
        "evidence_kind": "live",
        "authority": {
            "producer_repository": REPO,
            "contract_repository": REPO,
            "contract_commit": SCHEMA_COMMIT,
            "schema_sha256": SCHEMA_SHA,
        },
        "source": source,
        "location": {
            **location,
            "private": False,
            "gated": False,
            "xet_hash": None,
            "lfs_oid": None,
        },
        "publication": {
            "origin": "github_actions",
            "workflow": ".github/workflows/australian-source-metadata.yml",
            "run": f"https://github.com/{REPO}/actions/runs/{primary.RUN}",
            "commit": primary.COMMIT,
            "receipt": historical,
        },
        "verification": {
            **location,
            "anonymous": True,
            "clean_room": True,
            "status": "passed",
            "verified_at": datetime
            .fromisoformat(digest_receipt["verified_at"])
            .astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "receipt": verification,
        },
        "rights": {
            "authorization": rights,
            "subject_sha256": target["sha256"],
            "dataset": target["dataset"],
            "path": target["path"],
            "basis": "maintainer_attested_exact_scope_permission_not_independently_reviewed",
            "sensitivity": "non_sensitive",
            "publication": "approved_exact_scope",
        },
        "discovery": {
            "collections": [collection["url"]],
            "estate_entry": estate_ref,
        },
        "lineage": {
            "inputs": inputs,
            "v1_conformance": v1_ref,
            "v2_field_lineage": None,
            "v3_replay": v3_ref,
            "promotion_receipt": None,
            "v2_field_lineage_applicability": "not_applicable_raw_b2",
        },
        "recovery": {
            "role": "primary",
            "independent": False,
            "administrative_domain": "huggingface:" + lineage.DATASET,
            "primary_administrative_domain": "huggingface:" + lineage.DATASET,
            "region": "unverified",
            "primary_region": "unverified",
            "rpo_seconds": None,
            "rto_seconds": None,
            "checksum_inventory": historical,
            "restore_receipt": historical,
            "authorization_receipt": None,
        },
        "cache": {
            "origin": "github_actions",
            "state": "removed",
            "max_bytes": target["byte_count"],
            "created_at": start
            .astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "expires_at": expiry
            .astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "cleanup_receipt": v3_ref,
            "offline_behavior": "fail_closed",
        },
        "consumers": [],
    }
    raw = validate_contract(document, root=root)
    roles = tuple(
        [
            ReceiptRole(role=f"/lineage/inputs/{i}", **ref)
            for i, ref in enumerate(inputs)
        ]
        + [
            ReceiptRole(role="/lineage/v1_conformance", **v1_ref),
            ReceiptRole(role="/lineage/v3_replay", **v3_ref),
        ]
    )
    trusted = TrustedAdmissionProfile(
        producer_repository=REPO,
        contract_repository=REPO,
        contract_commit=SCHEMA_COMMIT,
        schema_sha256=SCHEMA_SHA,
        dataset=target["dataset"],
        revision=target["revision"],
        path=target["path"],
        byte_count=target["byte_count"],
        sha256=target["sha256"],
        source_id="au-mbs",
        acquisition_id=life["acquisition_id"],
        layer="bronze",
        bronze_stratum="B2",
        representation="raw",
        schema_era=silver_source["schema_era"],
        comparison_cohort=silver_source["comparison_cohort"],
        effective_date=silver_source["effective_date"],
        retrieved_at=event["retrieved_at"],
        evidence_kind="live",
        authorization=ReceiptRole(role="/rights/authorization", **rights),
        lineage=roles,
    )
    return raw, trusted


def qualify(*, workflow_commit: str, root: Path = ROOT) -> dict[str, Any]:
    """Perform receipt closure, exact trust admission and a bounded hosted reader."""
    require_hosted_main(workflow_commit)
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    run = os.environ.get("GITHUB_RUN_ID", "")
    _require(
        attempt.isdigit()
        and int(attempt) > 0
        and run.isdigit()
        and int(run) > 0,
        "hosted run identity missing",
    )
    raw, trusted = candidate(root)
    _require((root / OUTPUT).read_bytes() == raw, "July contract is stale")
    closure = shared.receipt_closure(raw, root=root)
    admission = admit_closed_contract(
        raw, closure, schema=(root / SCHEMA).read_bytes(), trusted=trusted
    )
    canary = run_reader_canary(
        raw,
        admission.model_dump(mode="json"),
        workflow_commit=workflow_commit,
        workflow_run_id=run,
        workflow_run_attempt=attempt,
        root=root,
    )
    return {
        "schema_id": "global-medicines-atlas.mbs-july-frozen-v4-admission-reader",
        "schema_version": 1,
        "status": "passed",
        "admission": admission.model_dump(mode="json"),
        "receipt_closure": closure.model_dump(mode="json"),
        "consumer_canary": canary,
        "boundaries": {
            "dataset_added_or_published": False,
            "participant_or_cohort_data_accessed": False,
            "source_values_interpreted": False,
            "independent_recovery_established": False,
            "federation_gate_closed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--workflow-commit")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.verify:
        _require(
            args.workflow_commit and args.report,
            "hosted commit and report required",
        )
        result = qualify(workflow_commit=args.workflow_commit)
        args.report.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("July exact v4 admission and reader canary passed")
        return 0
    raw, _trusted = candidate()
    path = ROOT / OUTPUT
    if args.check:
        _require(
            path.is_file() and path.read_bytes() == raw,
            "July contract is stale",
        )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    print("July v4 candidate validated; no admission or source read")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
