"""Prepare value-free drafts for eight existing MBS projection admissions.

Only digest-pinned repository metadata is read. Draft components are neither
v4 contracts nor admissions, and do not authorize data access or publication.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_mbs_august_projection_field_lineage as lineage

ROOT = Path(__file__).resolve().parents[1]
Q = "quality/qualifications/"
OUTPUT = (
    Q + "australian-mbs-august-projection-admission-preparation-20261116.json"
)
INPUTS = {
    "lineage": (
        lineage.REPORT,
        "e880ccded4e51b0eae7bfd9f4370824eebb3d6d8efa91bed1167a4289e8fe1f6",
    ),
    "v2": (
        lineage.OUTPUT,
        "4e5ce6ce699aa1d84f2a6ad28ee2b552b6bd62ba9e93db3fd886576e8dcd76f6",
    ),
    "replay": (
        Q + "australian-mbs-august-projection-v3-20261115/metadata-replay.json",
        "264295cc3697f81058af6fd1a62e007bc73761b6fb1ac1b3bbb4614277d5e006",
    ),
    "consumer": (
        Q + "australian-mbs-august-projection-consumer-preflight-20261115.json",
        "71909266466947122cb5c799565266982b6327eebc54e3212a06ed8badaa2a70",
    ),
    "privacy": (
        Q + "australian-existing-archive-privacy-batch-20261115.json",
        "7ab592f48583def8fb05b814d442b394463b3703caf978e885a1d96961029ec8",
    ),
    "digest": lineage.INPUTS["digest_receipt"],
    "disposition": (
        Q + "australian-mbs-august-f9f9-prefix-disposition-20261028.json",
        "30f04f37de72252648fe1a4c07c6488024f56c10cec35d810f3e91534155aaf4",
    ),
}
IDENTITY = ("dataset", "revision", "path", "sha256", "byte_count")
FROZEN_COUNT = 4
REPLICA_COUNT = 2
OUTSIDE_ATTESTED_REVISION = "42d73b6facac016f14a335d36d83f1a3b630add8"


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _ref(name: str) -> dict[str, str]:
    path, digest = INPUTS[name]
    return {"path": path, "sha256": digest}


def load(root: Path = ROOT) -> dict[str, Any]:
    """Load pinned reports and their referenced, bounded JSON metadata only."""
    evidence: dict[str, Any] = {
        name: bounded.read_bound_metadata(root, *ref)
        for name, ref in INPUTS.items()
    }
    references: dict[str, dict[str, Any]] = {}
    paths: dict[str, str] = {}
    rows = evidence["lineage"]["objects"]
    plans = evidence["replay"]["objects"]
    for ref in [
        *(
            row[key]
            for row in rows
            for key in ("source_receipt", "rights_evidence")
        ),
        *(row["source"][key] for row in plans for key in ("event", "b2")),
    ]:
        path, digest = ref["path"], ref["sha256"]
        _require(
            path not in paths or paths[path] == digest,
            "conflicting metadata reference",
        )
        if path not in references:
            references[path] = bounded.read_bound_metadata(root, path, digest)
            paths[path] = digest
    evidence["referenced"] = references
    return evidence


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {row["path"]: row for row in rows}
    _require(len(result) == len(rows), "duplicate metadata path")
    return result


def reconcile(evidence: dict[str, Any]) -> dict[str, Any]:  # ruff: ignore[too-many-locals,too-many-statements] -- check each independent evidence role
    """Join independent receipts by the complete object identity, fail closed."""
    fields = _index(evidence["lineage"]["objects"])
    _require(len(fields) == lineage.OBJECT_COUNT, "projection count differs")
    paths = set(fields)
    expected_paths = {
        f"bronze/mbs/releases/2026-08-01/{producer['id']}/{filename}"
        for producer in lineage.PRODUCERS.values()
        for filename in ("p7.parquet", "source.parquet")
    }
    _require(paths == expected_paths, "projection paths differ")
    indexes: dict[str, dict[str, dict[str, Any]]] = {}
    for name in ("digest", "replay", "consumer", "privacy"):
        selected = [
            row for row in evidence[name]["objects"] if row["path"] in paths
        ]
        indexes[name] = _index(selected)
        _require(set(indexes[name]) == paths, f"{name} object set differs")
    _require(
        evidence["lineage"]["v2_lineage"]["sha256"] == INPUTS["v2"][1],
        "field lineage reference differs",
    )
    _require(
        evidence["consumer"]["field_lineage_sha256"] == INPUTS["v2"][1]
        and evidence["consumer"]["metadata_replay_sha256"]
        == INPUTS["replay"][1],
        "preflight reference differs",
    )
    _require(
        evidence["replay"]["registration_replay"]
        == "passed_twice_in_memory_from_retained_metadata"
        and evidence["replay"][
            "historical_projection_reproduction_performed_by_this_replay"
        ]
        is False,
        "replay scope differs",
    )
    _require(
        evidence["digest"]["workflow_run"] == "43687742836",
        "digest run differs",
    )
    disposition = evidence["disposition"]
    _require(
        disposition["disposition"]["state"] == "deferred_not_admitted"
        and disposition["evidence"]["dataset"] == lineage.DATASET
        and disposition["evidence"]["revision"] == lineage.OUTSIDE_REVISION,
        "f9f9 disposition differs",
    )
    required_replica = _index(disposition["objects"])
    _require(
        len(required_replica) == REPLICA_COUNT,
        "replica disposition count differs",
    )
    records = evidence["v2"]["records"]
    _require(
        len(records) == lineage.OBJECT_COUNT * lineage.RECORDS_PER_OBJECT,
        "field record count differs",
    )
    _require(
        len({record["record_id"] for record in records}) == len(records),
        "field record identities differ",
    )
    _require(
        {record["output_dataset"] for record in records} == paths,
        "field output set differs",
    )
    rows: list[dict[str, Any]] = []
    for path, item in sorted(fields.items()):
        for name, index in indexes.items():
            _require(
                all(item[key] == index[path][key] for key in IDENTITY),
                f"{name} identity differs",
            )
        plan, privacy, consumer = (
            indexes[name][path] for name in ("replay", "privacy", "consumer")
        )
        producers = [
            (name, producer)
            for name, producer in lineage.PRODUCERS.items()
            if f"/{producer['id']}/" in path
        ]
        _require(len(producers) == 1, "producer identity differs")
        name, producer = producers[0]
        frozen = producer["frozen"]
        _require(
            item["dataset"] == lineage.DATASET
            and item["revision"]
            == (lineage.FROZEN_REVISION if frozen else lineage.OUTSIDE_REVISION)
            and item["frozen_member"] is frozen
            and privacy["frozen_member"] is frozen
            and plan["producer"] == name
            and item["producer_commit"] == producer["commit"],
            "producer or frozen membership differs",
        )
        _require(
            privacy["privacy"] == "source_profile_assessed_non_sensitive",
            "privacy status differs",
        )
        replica = name == "f9f9"
        _require(
            plan["independent_replica_required_before_admission"] is replica
            and consumer["independent_replica_required_before_admission"]
            is replica
            and (path in required_replica) is replica,
            "replica prerequisite differs",
        )
        if replica:
            _require(
                all(
                    item[key] == required_replica[path][key]
                    for key in ("path", "sha256", "byte_count")
                ),
                "replica subject differs",
            )
        _require(
            consumer["synthetic_v4_shape_and_consumer_identity"] == "passed"
            and consumer["reader_refuses_without_admission"] == "passed"
            and consumer["production_contract"] == "not_created"
            and consumer["actual_v4_admission"] == "not_performed"
            and consumer["actual_payload_consumer_canary"] == "not_performed",
            "consumer preflight differs",
        )
        _require(
            item["reproduction"]
            == plan["historical_reproduction"]
            == (
                "exact_bytes_reproduced_in_memory_at_prior_revision"
                if frozen
                else "footer_adjusted_reproduction_not_historical_writer"
            )
            and item["field_lineage_records"] == lineage.RECORDS_PER_OBJECT
            and item["field_semantics_accepted"] is False
            and item["v4_admission"] == "not_performed",
            "lineage scope differs",
        )
        source = plan["source"]
        _require(
            source["reconstructed_now"] is (name in {"99fa", "d781"}),
            "source reconstruction chronology differs",
        )
        metadata = evidence["referenced"]
        event = metadata[source["event"]["path"]]
        b2 = metadata[source["b2"]["path"]]["rows"]
        receipt = metadata[item["source_receipt"]["path"]]
        _require(
            event["acquisition_id"] == source["acquisition_id"]
            and event["source_id"] == "au-mbs"
            and event["content_id"]
            == event["payload_sha256"]
            == lineage.SOURCE_SHA
            and event["retrieved_at"] == source["retrieved_at"]
            and len(b2) == 1
            and b2[0]["acquisition_id"] == source["acquisition_id"]
            and b2[0]["content_id"] == lineage.SOURCE_SHA
            and b2[0]["state"] == "external_reference_only"
            and receipt["payload"]["sha256"] == lineage.SOURCE_SHA
            and receipt["payload"]["byte_count"] == lineage.SOURCE_BYTES
            and receipt["retrieval"]["retrieved_at"] == source["retrieved_at"],
            "source metadata differs",
        )
        rights = metadata[item["rights_evidence"]["path"]]
        authorized = _index(rights["authorized_objects"])
        _require(
            rights["dataset"] == lineage.DATASET
            and rights["public_release_rights_attested"] is True
            and rights["boundaries"]["v4_admission_or_promotion_authorized"]
            is False
            and path in authorized
            and all(
                item[key] == authorized[path][key]
                for key in ("path", "sha256", "byte_count")
            ),
            "rights scope differs",
        )
        if not frozen:
            _require(
                authorized[path]["dataset"] == lineage.DATASET
                and authorized[path]["revision"] == OUTSIDE_ATTESTED_REVISION,
                "outside rights chronology differs",
            )
        relevant = [
            record for record in records if record["output_dataset"] == path
        ]
        _require(
            len(relevant) == lineage.RECORDS_PER_OBJECT
            and all(
                record["output_sha256"] == item["sha256"]
                and record["input_sha256"] == lineage.SOURCE_SHA
                and record["source_dataset"] == lineage.SOURCE
                and record["rights_decision_id"]
                == item["rights_evidence"]["sha256"]
                and record["code_version"] == f"git:{producer['commit']}"
                for record in relevant
            ),
            "field lineage identity differs",
        )
        remaining = [
            "Assess output-specific privacy and the limited reproduction evidence for the intended admission.",
            "Resolve a supported v1 conformance reference for the projection and qualify v2 and metadata-only v3 evidence for their v4 roles.",
            "Bind and validate publication, verification, discovery, recovery and cache roles in a real v4 contract; close receipt bytes and configure independent trust.",
            "Obtain the separate admission decision; perform any authorized bounded payload consumer canary only after admission.",
        ]
        if replica:
            remaining.insert(
                0,
                "Establish independently verifiable replica evidence for this exact product before admission.",
            )
        rows.append({
            "dataset": item["dataset"],
            "revision": item["revision"],
            "path": path,
            "sha256": item["sha256"],
            "byte_count": item["byte_count"],
            "frozen_member": frozen,
            "producer": name,
            "draft_components": {
                "source_id": "au-mbs",
                "acquisition_id": source["acquisition_id"],
                "source_sha256": lineage.SOURCE_SHA,
                "source_byte_count": lineage.SOURCE_BYTES,
                "source_retrieved_at": source["retrieved_at"],
                "source_metadata_reconstructed_later": source[
                    "reconstructed_now"
                ],
                "source_event": source["event"],
                "source_b2_reference": source["b2"],
                "source_receipt": item["source_receipt"],
                "producer_commit": producer["commit"],
                "producer_code_sha256": item["producer_code_sha256"],
                "verified_digest_receipt": _ref("digest"),
                "verified_at": evidence["digest"]["verified_at"],
            },
            "privacy": {
                "status": privacy["privacy"],
                "scope": "source_profile_not_exhaustive_output_clearance",
                "evidence": _ref("privacy"),
            },
            "rights": {
                "evidence": item["rights_evidence"],
                "scope": "maintainer_attested_public_release_not_admission_or_consumer",
                "independent_instrument_review": False,
                "outside_attestation_is_prior_revision": not frozen,
                "outside_attested_revision": (
                    OUTSIDE_ATTESTED_REVISION if not frozen else None
                ),
            },
            "lineage": {
                "field_records": len(relevant),
                "field_lineage": _ref("v2"),
                "field_semantics_accepted": False,
                "replay": _ref("replay"),
                "replay_scope": "registration_metadata_only",
                "historical_reproduction": item["reproduction"],
            },
            "consumer": {
                "synthetic_preflight": _ref("consumer"),
                "unadmitted_reader_refusal": "passed",
                "actual_payload_canary": "not_performed",
            },
            "independent_replica_required_before_admission": replica,
            "independent_recovery_established": False,
            "remaining": remaining,
            "admission_ready": False,
            "actual_admission": "not_performed",
        })
    _require(
        sum(row["frozen_member"] for row in rows) == FROZEN_COUNT
        and sum(
            row["independent_replica_required_before_admission"] for row in rows
        )
        == REPLICA_COUNT,
        "cohort distribution differs",
    )
    return {
        "schema_id": "global-medicines-atlas.mbs-august-projection-admission-preparation",
        "schema_version": 1,
        "recorded_on": "2026-11-16",
        "kind": "draft_components_not_v4_contracts_or_admissions",
        "inputs": {name: _ref(name) for name in INPUTS},
        "objects": rows,
        "boundaries": {
            "source_or_projection_payload_read": False,
            "participant_or_cohort_data_accessed": False,
            "dataset_acquired_or_published": False,
            "rights_or_privacy_decision_changed": False,
            "v4_contract_receipt_closure_or_admission_performed": False,
            "actual_consumer_canary_performed": False,
            "independent_recovery_established": False,
            "frozen_inventory_changed": False,
        },
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    return reconcile(load(root))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), sort_keys=True, indent=2) + "\n").encode()
    path = ROOT / OUTPUT
    if args.check:
        _require(
            path.is_file() and path.read_bytes() == raw,
            "admission preparation is stale",
        )
    else:
        path.write_bytes(raw)
    print(
        "Prepared eight draft metadata dossiers; no admission or payload read"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
