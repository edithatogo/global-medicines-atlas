"""Bind three frozen MBS raw objects to historical lineage and replay plans.

All inputs and outputs are metadata. The earlier B2 references are preserved;
an exact-revision digest observation establishes byte identity, not a rewritten
acquisition or an admission. No source values are read by this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_m112_v1_conformance as v1
import scripts.qualify_m112_v3_replay as v3
import scripts.reconcile_australian_mbs_exact_digest as exact
from scripts.mbs_frozen_raw_identity import (
    ALIAS,
    AUGUST,
    DATASET,
    JULY,
    PATHS,
    REVISION,
)

ROOT = Path(__file__).resolve().parents[1]
QUAL = "quality/qualifications/"
SLUGS = {JULY: "july", AUGUST: "august", ALIAS: "august-alias"}
JULY_ACQUISITION = (
    "bbd662119ebebfdf08baf14c0b15c0dd5c93465910fd4f5309f37ecd37a82b8d"
)
AUGUST_ACQUISITION = (
    "fd32879190b69ad98cd2f207ec3b70b725ab8f524218f783ec08bf98b7ffcecd"
)
OUTPUT = QUAL + "australian-mbs-frozen-raw-lineage-20261115/"
V1_PATH = OUTPUT + "v1-conformance.json"
LINEAGE_PATH = OUTPUT + "lineage-crosswalk.json"

INPUTS = {
    "digest": (
        QUAL + "australian-existing-mbs-digest-binding-20261115.json",
        "9f1211574b46c18bbb37cf47399c68a8c4197c2bb08f9aaccac96930566ed02f",
    ),
    "gates": (
        QUAL + "australian-existing-mbs-pbs-object-gates-20261115.json",
        "3e30aed422ec437db9f199939ba2ee5863cccaa684ebdaf06641fbcc9895342e",
    ),
    "july_lineage": (
        QUAL + "australian-m112-july-mbs-source-lineage-20261019.json",
        "c8c90ff24235725bf9733f099f9ace7a5163a1ce6bf9abd409a0313fba5bf525",
    ),
    "august_lineage": (
        QUAL + "australian-m112-mbs-lifecycle-crosswalk-20261004.json",
        "7a4c9d171b5fe82ab71e90ec7a80578d569f2645951dadf79689d364f71cf7ef",
    ),
    "july_rights": (
        QUAL + "australian-mbs-six-raw-object-rights-attestation-20261020.json",
        "79f3cd76786fbb13ef5607085ee97a69a21bb361b52025f886256093dd5e4f3d",
    ),
    "august_rights": (
        QUAL + "australian-mbs-harvest-publication-authorization.json",
        "0fdc4d147d637c679ba0cc3eb165642974e533bb3ba044c99ee01f86127eb41b",
    ),
    "august_roles": (
        QUAL
        + "australian-m112-v4-contract-role-evidence-qualification-20261021.json",
        "9ae96773ed19b1ec0795340aef1d341dbeeb0f8961ca7f231af633618ca21781",
    ),
    "july_receipt": (
        f"quality/bronze/receipts/au-mbs/{JULY_ACQUISITION}.json",
        "cbb89dde7e24e790440b7aa3ec70ff8a580801d49b5f0b8839290f63bd64819c",
    ),
    "july_event": (
        f"quality/bronze/acquisitions/au-mbs/{JULY_ACQUISITION}.json",
        "e99c0153a57e0b46cf9dfd2c03520aa9ca9aa97415b5d20920c5e8191aa086f9",
    ),
    "july_b2": (
        f"quality/bronze/raw-evidence/au-mbs/{JULY_ACQUISITION}/manifest.json",
        "f691e810787291ed00135d2d5ebf85124510cbd59862d2fffa627d53458dc6a4",
    ),
    "august_receipt": (
        f"quality/bronze/receipts/au-mbs/{AUGUST_ACQUISITION}.json",
        "14fb98f49eb4e92dc467c0781a1cbd8a3409994b28059922783558235e97b21a",
    ),
    "august_event": (
        f"quality/bronze/acquisitions/au-mbs/{AUGUST_ACQUISITION}.json",
        "0473edd93fe9c2781701116febbd68a0c68262b74be5b4de52409d5c52570d30",
    ),
    "august_b2": (
        f"quality/bronze/raw-evidence/au-mbs/{AUGUST_ACQUISITION}/manifest.json",
        "4104bc85b891dd489e94378c40129870ef98f087c0e28862feb759a3723501fb",
    ),
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


def _ref(name: str) -> dict[str, str]:
    path, sha256 = INPUTS[name]
    return {"path": path, "sha256": sha256}


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    selected = [row for row in rows if row.get("path") in PATHS]
    result = {row["path"]: row for row in selected}
    _require(
        len(selected) == len(result) == len(PATHS), "raw MBS path set differs"
    )
    return result


def _validate_lifecycle(
    evidence: dict[str, dict[str, Any]],
    row: dict[str, Any],
    *,
    period: str,
) -> dict[str, Any]:
    receipt = evidence[f"{period}_receipt"]
    event = evidence[f"{period}_event"]
    manifest = evidence[f"{period}_b2"]
    acquisition = JULY_ACQUISITION if period == "july" else AUGUST_ACQUISITION
    rows = manifest["rows"]
    historical = (
        evidence["july_lineage"]["archive_object"]["uri"]
        if period == "july"
        else evidence["august_lineage"]["canonical_bronze_lifecycle"][
            "raw_reference"
        ]
    )
    _require(
        len(rows) == 1
        and manifest["authoritative"] is True
        and receipt["payload"]["sha256"] == row["sha256"]
        and receipt["payload"]["byte_count"] == row["byte_count"]
        and receipt["temporal"]["acquisition_id"] == acquisition
        and receipt["source"]["source_id"] == "au-mbs"
        and receipt["retrieval"]["status"] == "succeeded"
        and receipt["sensitivity"]["data_sensitivity"] == "non_sensitive"
        and event["acquisition_id"] == acquisition
        and event["source_id"] == "au-mbs"
        and event["content_id"] == event["payload_sha256"] == row["sha256"]
        and event["source_version"] == receipt["source"]["catalog_version"]
        and event["retrieval"]["status"] == "succeeded"
        and event["retrieval"]["uri"] == receipt["retrieval"]["uri"]
        and rows[0]["acquisition_id"] == acquisition
        and rows[0]["source_id"] == "au-mbs"
        and rows[0]["content_id"] == row["sha256"]
        and rows[0]["external_reference"] == historical
        and rows[0]["state"] == "external_reference_only"
        and rows[0]["stratum"] == "B2"
        and rows[0]["source_native_bytes_immutable"] is True,
        "historical MBS B1/B2 lifecycle differs",
    )
    return {
        "acquisition_id": acquisition,
        "source_url": event["retrieval"]["uri"],
        "source_version": event["source_version"],
        "original_b2_reference": historical,
        "source_receipt": _ref(f"{period}_receipt"),
        "acquisition_event": _ref(f"{period}_event"),
        "b2_manifest": _ref(f"{period}_b2"),
    }


def _validate_rights(
    evidence: dict[str, dict[str, Any]], row: dict[str, Any], *, period: str
) -> str:
    if period == "july":
        rights = evidence["july_rights"]
        matches = [x for x in rights["authorized_objects"] if x["path"] == JULY]
        _require(
            rights["dataset_identity"]["dataset"] == DATASET
            and rights["decision"]["public_release_rights_attested"] is True
            and rights["boundaries"]["admission_or_consumer_canary_authorized"]
            is False
            and len(matches) == 1
            and all(
                matches[0][key] == row[key]
                for key in ("path", "sha256", "byte_count")
            ),
            "July exact public-release attestation differs",
        )
        return "maintainer_attested_exact_scope_permission_not_independently_reviewed"
    rights = evidence["august_rights"]
    selected = [
        x
        for x in evidence["august_roles"]["objects"]
        if x.get("path") in {AUGUST, ALIAS}
    ]
    roles = {x["path"]: x for x in selected}
    _require(
        len(selected) == len(roles) == len({AUGUST, ALIAS})
        and set(roles) == {AUGUST, ALIAS},
        "August role evidence path set differs",
    )
    role = roles[row["path"]]
    _require(
        rights["dataset"] == DATASET
        and rights["external_publication_authorized"] is True
        and rights["maintainer_asserted_redistribution_permission"] is True
        and "monthly_schedule_xml" in rights["categories"]
        and role["dataset"] == DATASET
        and role["sha256"] == row["sha256"]
        and role["bytes"] == row["byte_count"]
        and role["rights_decision"] == _ref("august_rights")
        and role["rights_state"] == "authorized_exact_source_release_permitted",
        "August exact source-release evidence differs",
    )
    return "existing_exact_source_release_authorization"


def reconcile(evidence: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Join exact frozen identities to immutable historical B1/B2 metadata."""
    digest = evidence["digest"]
    _require(
        digest["workflow_run"] == exact.RUN_ID
        and digest["summary"]["exact_revision_stream_digests_passed"]
        == exact.OBJECT_COUNT,
        "MBS digest receipt identity differs",
    )
    verified = _index(digest["objects"])
    gates = _index(evidence["gates"]["mbs_objects"])
    july = evidence["july_lineage"]
    august = evidence["august_lineage"]
    _require(
        july["inventory"]["approved_denominator_member"] is True
        and july["archive_object"]["path"] == JULY
        and july["archive_object"]["dataset"] == DATASET
        and july["lineage"]["acquisition_id"] == JULY_ACQUISITION
        and august["scope"]["dataset"] == DATASET
        and set(august["scope"]["paths"]) == {AUGUST, ALIAS}
        and august["canonical_bronze_lifecycle"]["acquisition_id"]
        == AUGUST_ACQUISITION
        and august["reconciliation"]["local_b1_b2_lifecycle_complete"] is True
        and august["reconciliation"]["producer_archive_records_rewritten"]
        is False,
        "MBS historical lineage scope differs",
    )
    result: list[dict[str, Any]] = []
    for path in PATHS:
        observed, gate = verified[path], gates[path]
        _require(
            observed["dataset"] == gate["dataset"] == DATASET
            and observed["revision"] == gate["revision"] == REVISION
            and observed["frozen_member"] is gate["frozen_member"] is True
            and observed["batch"] == "mbs_exact_classified_raw"
            and observed["exact_revision_stream_digest"] == "passed"
            and gate["privacy"] == "source_profile_assessed_non_sensitive"
            and all(
                observed[key] == gate[key]
                for key in ("path", "sha256", "byte_count")
            ),
            "MBS frozen identity, digest or privacy differs",
        )
        period = "july" if path == JULY else "august"
        if period == "july":
            _require(
                all(
                    july["archive_object"][key] == observed[key]
                    for key in ("sha256", "byte_count")
                ),
                "July archive identity differs",
            )
        else:
            source = august["canonical_bronze_lifecycle"]
            _require(
                source["content_sha256"] == observed["sha256"]
                and source["byte_count"] == observed["byte_count"],
                "August alias content differs",
            )
        lifecycle = _validate_lifecycle(evidence, observed, period=period)
        rights_basis = _validate_rights(evidence, observed, period=period)
        provenance = {
            "target": {
                key: observed[key]
                for key in (
                    "dataset",
                    "revision",
                    "path",
                    "sha256",
                    "byte_count",
                )
            },
            "historical_b1_b2": lifecycle,
            "lineage_evidence": _ref(f"{period}_lineage"),
            "rights_evidence": _ref(f"{period}_rights"),
            "exact_digest_evidence": _ref("digest"),
            "alias_of_historical_b2_path": path == ALIAS,
            "reference_join": "same_source_digest_and_byte_count_not_rewritten_history",
        }
        result.append({
            "path": path,
            "provenance": provenance,
            "provenance_sha256": _sha(provenance),
            "rights_basis": rights_basis,
            "v4_admission": "not_performed",
            "consumer_canary": "not_performed",
        })
    return result


def load(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    evidence = {
        name: bounded.read_bound_metadata(root, *ref)
        for name, ref in INPUTS.items()
    }
    _require(
        evidence["digest"] == exact.build_report(root),
        "retained digest binding differs",
    )
    return evidence


def build(
    root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    """Build candidate-only v1 and per-object v3 documents."""
    rows = reconcile(load(root))
    candidates: list[dict[str, Any]] = []
    plans: dict[str, dict[str, Any]] = {}
    for item in rows:
        provenance = item["provenance"]
        target = provenance["target"]
        lifecycle = provenance["historical_b1_b2"]
        candidates.append({
            **target,
            "acquisition_id": lifecycle["acquisition_id"],
            "rights_state": item["rights_basis"],
            "anonymous_digest_readback": True,
            "contract_role_states": {"lineage.inputs": "qualified_b1_b2_only"},
            "rights_decision": provenance["rights_evidence"],
            "lineage_evidence": provenance["lineage_evidence"],
            "digest_evidence": provenance["exact_digest_evidence"],
        })
        logical = _sha({
            key: target[key] for key in ("dataset", "revision", "path")
        })
        archive_period = f"filename-derived:{Path(target['path']).name}"
        partition = _sha(["au-mbs", archive_period, logical])
        snapshot_id = _sha([
            partition,
            target["sha256"],
            item["provenance_sha256"],
        ])
        snapshot = {
            "snapshot_id": snapshot_id,
            "source_id": "au-mbs",
            "source_version_id": lifecycle["source_version"],
            "partition_id": partition,
            "partition_value": f"{DATASET}@{REVISION}:{target['path']}",
            "logical_asset_id": logical,
            "source_url": lifecycle["source_url"],
            "archive_period": archive_period,
            "observation_status": "acquired",
            "payload_sha256": target["sha256"],
            "metadata_sha256": item["provenance_sha256"],
            "idempotency_key": _sha([partition, snapshot_id]),
            "correction_sequence": 0,
            "supersedes_snapshot_id": None,
            "late_arriving": False,
            "replay_eligible": True,
            "rights_state": item["rights_basis"],
        }
        plans[target["path"]] = v3.build_replay_document(
            snapshot, target["byte_count"], root=root
        )
    bases = {row["rights_basis"]: row["rights_basis"] for row in rows}
    v1_document = v1._build_document(root, candidates, rights_basis=bases)  # pyright: ignore[reportPrivateUsage]
    crosswalk = {
        "schema_id": "global-medicines-atlas.mbs-frozen-raw-lineage-crosswalk",
        "schema_version": 1,
        "inputs": {key: _ref(key) for key in INPUTS},
        "objects": rows,
        "boundaries": {
            "source_values_read": False,
            "historical_acquisition_rewritten": False,
            "replay_executed": False,
            "v4_admission_or_consumer_canary": False,
            "dataset_added_or_published": False,
        },
    }
    return crosswalk, v1_document, plans


def _bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    crosswalk, conformance, plans = build()
    outputs = {LINEAGE_PATH: crosswalk, V1_PATH: conformance} | {
        OUTPUT + f"v3-plan-{SLUGS[path]}.json": plan
        for path, plan in plans.items()
    }
    for relative, document in outputs.items():
        path = ROOT / relative
        expected = _bytes(document)
        if args.check:
            _require(
                path.is_file() and path.read_bytes() == expected,
                f"stale candidate: {relative}",
            )
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
    print(
        f"verified {len(plans)} candidate raw MBS replay plans; no replay or admission"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
