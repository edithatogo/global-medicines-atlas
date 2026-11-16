"""Bind unmatched PBS privacy paths to retained, value-free provenance.

Only digest-bound repository metadata is read. A lineage, rights attestation,
or historical publication receipt is not a privacy assessment or admission.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from operator import itemgetter
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_pbs_schema_privacy_context as privacy

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    "quality/qualifications/australian-pbs-unmatched-provenance-20261116.json"
)
INPUTS = {
    "coverage": (
        "quality/qualifications/australian-pbs-acquisition-privacy-coverage-20261115.json",
        "a59046ce6d88de32b954fcbc97f360937e4e240deb95349cd4a1fd3292b21ed2",
    ),
    "inventory": privacy.INPUTS["privacy"],
    "readiness": (
        "quality/qualifications/australian-m112-reimbursement-batch-readiness-20261115.json",
        "0969afcd6152cd73f5ff53f28ccb6fb9315090a71ba302ebbee74efaf32db4f5",
    ),
    "pdf": (
        "quality/qualifications/australian-m112-pbs-pdf-archive-lineage-20261019.json",
        "b0196e9639fe86d5cf21dae2240bc7c3d6ad0983f8435aa0d55d32538f4c3486",
    ),
    "projection": (
        "quality/qualifications/australian-m112-reimbursement-medallion-projection-lineage-20261019.json",
        "a9146e11c71f3d031135dc395d84589497a4aa50e9e10f15acbca08498fc7f97",
    ),
    "projection_readback": (
        "quality/qualifications/australian-m112-projection-identity-readback-20261018.json",
        "03f41ee24ba1ac04ad76e63480ddd71c7b3cb01df72cbb05bc91db803a136ddd",
    ),
    "bronze_rights": (
        "quality/qualifications/australian-pbs-bronze-projection-rights-attestation-20261020.json",
        "c1a66decf1b601c6a1da90971cca52258310d8b44bc3dac92006f6be8a6d0cbe",
    ),
    "silver_readiness": (
        "quality/qualifications/pbs-reproduced-v4-evidence-readiness-20261029.json",
        "d581fb505eca81ea2e984941d53c57218bbafcfc9c2de23a6718caf32ea01946",
    ),
    "silver_rights": (
        "quality/qualifications/australian-pbs-reproduced-silver-output-rights-attestation-20261029.json",
        "93e0d64ec428ae157e030432e8cce70751df54ec111b9fa11319c74206a3c216",
    ),
    "publication": (
        "quality/qualifications/pbs-reproduced-publication-20261102-41395493749/publication.json",
        "2316c52d97aee8041b104c7b621363b4b1f16f4cb1a073177e902e86acf74294",
    ),
}
PDF_DIRECTORY = "quality/bronze/imported-acquisitions/au-pbs-archive/"
IDENTITY_KEYS = ("dataset", "revision", "path", "sha256", "byte_count")
BYTE_IDENTICAL = "byte_identical_to_exact_producer_source_path"
LAYER_PARTITION = "exact_layer_partition_of_medallion_artifacts"
PREVIOUS_MATCHED_PATHS = 1703
UNMATCHED_PATHS = 19
ARCHIVED_PDF_EVENTS = 5
FROZEN_PATHS = 18


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _identity(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row.get(key) for key in IDENTITY_KEYS)


def _by_path(
    rows: list[dict[str, Any]], key: str = "path"
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        path = row.get(key)
        if not isinstance(path, str) or not path or path in result:
            raise ValueError("duplicate or invalid evidence path")
        result[path] = row
    return result


def load_inputs(root: Path = ROOT) -> dict[str, Any]:
    """Load only the approved, hash-bound JSON metadata inputs and five events."""
    docs = {
        name: bounded.read_bound_metadata(root, path, digest)
        for name, (path, digest) in INPUTS.items()
    }
    events: dict[str, dict[str, Any]] = {}
    bindings = docs["pdf"]["output_bindings"]
    for row in docs["pdf"]["objects"]:
        ref = row["acquisition_event_path"]
        acquisition_id = row["acquisition_id"]
        _require(
            ref == f"{PDF_DIRECTORY}{acquisition_id}.json"
            and ref in bindings
            and ref not in events,
            "archived PDF event reference differs",
        )
        events[ref] = bounded.read_bound_metadata(root, ref, bindings[ref])
    docs["events"] = events
    return docs


def _pdf_record(
    row: dict[str, Any], docs: dict[str, Any], ready: dict[str, Any]
) -> dict[str, Any]:
    lineages = _by_path(docs["pdf"]["objects"])
    lineage = lineages.get(row["path"], {})
    ref = lineage.get("acquisition_event_path")
    event = docs["events"].get(ref, {})
    sensitivity = event.get("sensitivity", {})
    retrieval = event.get("retrieval", {})
    http = retrieval.get("http", {})
    _require(
        (
            lineage.get("dataset"),
            lineage.get("revision"),
            lineage.get("path"),
            lineage.get("content_sha256"),
            lineage.get("byte_count"),
        )
        == _identity(row)
        and ref == f"{PDF_DIRECTORY}{lineage.get('acquisition_id')}.json"
        and ready.get("metadata_references", {}).get("acquisition_event_path")
        == ref
        and ready.get("metadata_references", {}).get("acquisition_event_sha256")
        == docs["pdf"]["output_bindings"].get(ref)
        and event.get("schema_id")
        == "global-medicines-atlas.bronze-acquisition-event"
        and event.get("acquisition_id") == lineage.get("acquisition_id")
        and event.get("source_id") == lineage.get("source_id")
        and event.get("content_id")
        == event.get("payload_sha256")
        == row["sha256"]
        and retrieval.get("status") == "succeeded"
        and http.get("observed_byte_length") == row["byte_count"]
        and sensitivity.get("data_sensitivity") == "unknown"
        and sensitivity.get("personal_data") == "unknown"
        and sensitivity.get("publication") == "review_required"
        and lineage.get("reviewer_status") == "unreviewed",
        "archived PDF provenance or privacy differs",
    )
    return {
        "kind": "archived_pdf_acquisition_event",
        "event": {"path": ref, "sha256": docs["pdf"]["output_bindings"][ref]},
        "event_sensitivity": "unknown",
        "event_personal_data": "unknown",
        "landed_reviewer_status": "unreviewed",
    }


def _projection_record(
    row: dict[str, Any], docs: dict[str, Any]
) -> dict[str, Any]:
    report = docs["projection"]
    scope = report["scope"]
    line = _by_path(report["objects"], "dataset_path").get(row["path"], {})
    readback_report = docs["projection_readback"]
    readback = _by_path(readback_report["objects"]).get(row["path"], {})
    relation = line.get("projection_relation")
    _require(
        scope.get("dataset")
        == readback_report["scope"].get("dataset")
        == row["dataset"]
        and scope.get("dataset_revision")
        == readback_report["scope"].get("revision")
        == row["revision"]
        and line.get("dataset_sha256")
        == readback.get("sha256")
        == row["sha256"]
        and line.get("dataset_byte_count")
        == readback.get("byte_count")
        == row["byte_count"]
        and readback.get("anonymous_readback") is True
        and line.get("b1_b2_lineage_complete") is True
        and isinstance(line.get("producer_source_path"), str)
        and relation in {BYTE_IDENTICAL, LAYER_PARTITION},
        "reimbursement projection identity or lineage differs",
    )
    if relation == BYTE_IDENTICAL:
        _require(
            row["batch"] == "reimbursement_projection_byte_identical_unassessed"
            and line.get("producer_source_sha256") == row["sha256"]
            and line.get("producer_source_byte_count") == row["byte_count"],
            "byte-identical projection source differs",
        )
        kind = "reimbursement_byte_identical_projection"
    else:
        config_name = line.get("config_name")
        if not isinstance(config_name, str):
            raise ValueError("layer partition source differs")
        _require(
            row["batch"]
            == "reimbursement_projection_layer_partition_unassessed"
            and line.get("producer_source_path") == bounded.PARTITION_SOURCE
            and line.get("producer_source_sha256")
            == bounded.PARTITION_SOURCE_SHA256
            and line.get("producer_source_byte_count")
            == bounded.PARTITION_SOURCE_BYTES
            and line.get("producer_source_row_count")
            == bounded.PARTITION_SOURCE_ROWS
            and line.get("row_count")
            == bounded.PARTITION_ROWS.get(config_name),
            "layer partition source differs",
        )
        kind = "reimbursement_layer_partition"
    return {
        "kind": kind,
        "producer_revision": scope["producer_revision"],
        "producer_source_path": line["producer_source_path"],
        "producer_source_sha256": line["producer_source_sha256"],
        "producer_source_byte_count": line["producer_source_byte_count"],
        "relationship": relation,
    }


def _bronze_record(row: dict[str, Any], docs: dict[str, Any]) -> dict[str, Any]:
    line = docs["projection"]["pbs_source_parquet_lineage"]
    attestation = docs["bronze_rights"]
    scope = attestation["scope"]
    _require(
        (
            line.get("dataset"),
            line.get("revision"),
            line.get("projection_path"),
            line.get("projection_sha256"),
            line.get("projection_byte_count"),
        )
        == _identity(row)
        and _identity(scope) == _identity(row)
        and line.get("lineage_complete") is True
        and attestation.get("public_release_rights_attested") is True
        and attestation.get("permission_instrument_existence_and_applicability")
        == "maintainer_attested_not_independently_reviewed_or_located"
        and attestation["boundaries"].get("v4_admission_performed") is False,
        "PBS Bronze identity, lineage or attestation differs",
    )
    return {
        "kind": "pbs_bronze_projection",
        "source_archive_sha256": line["source_of_truth_sha256"],
        "historical_rights": "exact_output_maintainer_attested_instrument_not_independently_reviewed",
    }


def _silver_record(row: dict[str, Any], docs: dict[str, Any]) -> dict[str, Any]:
    report = docs["silver_readiness"]
    output = report["output"]
    evidence = report["evidence"]
    rights = docs["silver_rights"]
    authorized = rights["authorized_output"]
    publication = docs["publication"]
    _require(
        (
            publication.get("dataset"),
            publication.get("revision"),
            publication.get("path"),
            publication.get("sha256"),
            publication.get("bytes"),
        )
        == _identity(row)
        and publication.get("status")
        == "anonymous_verification_passed_not_admitted"
        and publication.get("anonymous_digest_verification") == "passed"
        and publication.get("v4_admission_performed") is False
        and output.get("parquet_sha256")
        == authorized.get("parquet_sha256")
        == row["sha256"]
        and output.get("parquet_bytes")
        == authorized.get("parquet_bytes")
        == row["byte_count"]
        and output.get("id") == authorized.get("output_id")
        and authorized.get("dataset") == row["dataset"]
        and output.get("source_member_sha256")
        == authorized.get("member_sha256")
        and authorized.get("archive_sha256")
        == docs["projection"]["pbs_source_parquet_lineage"][
            "source_of_truth_sha256"
        ]
        and rights.get("public_release_rights_attested") is True
        and rights.get("permission_instrument_existence_and_applicability")
        == "maintainer_attested_not_independently_reviewed_or_located"
        and report.get("status") == "candidate_evidence_matched_not_admitted"
        and evidence.get("two_independent_builds_match") is True
        and evidence.get("independent_builds_use_same_algorithm") is True
        and evidence.get("prior_field_state_receipt_names_prior_output")
        is True,
        "PBS Silver identity, publication or lineage differs",
    )
    return {
        "kind": "pbs_reproduced_silver",
        "source_archive_sha256": authorized["archive_sha256"],
        "source_member_sha256": authorized["member_sha256"],
        "two_builds_same_algorithm": True,
        "prior_field_state_receipt_names_prior_output": True,
        "historical_rights": "exact_output_maintainer_attested_instrument_not_independently_reviewed",
        "historical_publication": "anonymous_digest_verified_not_v4_admitted",
    }


def reconcile(docs: dict[str, Any]) -> dict[str, Any]:
    """Join the exact 19 prior unmatched paths without clearing privacy."""
    coverage = docs["coverage"]
    rows = bounded.metadata_rows(
        coverage["unmatched_in_scoped_event_directory"]["identities"]
    )
    inventory = _by_path(bounded.metadata_rows(docs["inventory"]["objects"]))
    _require(
        coverage.get("schema_id")
        == "global-medicines-atlas.pbs-acquisition-privacy-coverage"
        and coverage["matched"]["paths"] == PREVIOUS_MATCHED_PATHS
        and coverage["unmatched_in_scoped_event_directory"]["paths"]
        == len(rows)
        == UNMATCHED_PATHS
        and coverage["boundaries"]["privacy_clearances_added"] == 0
        and len(_by_path(rows)) == UNMATCHED_PATHS
        and len(docs["events"]) == ARCHIVED_PDF_EVENTS,
        "PBS unmatched inventory differs",
    )
    ready = _by_path(bounded.metadata_rows(docs["readiness"]["objects"]))
    other = _by_path(
        bounded.metadata_rows(docs["readiness"]["other_frozen_objects"])
    )
    result: list[dict[str, Any]] = []
    for row in sorted(rows, key=itemgetter("dataset", "path")):
        old = inventory.get(row["path"], {})
        _require(
            _identity(old) == _identity(row)
            and old.get("batch") == row["batch"]
            and old.get("privacy") == privacy.UNKNOWN,
            "PBS privacy inventory identity or disposition differs",
        )
        batch = row["batch"]
        _require(
            old.get("frozen_member")
            is (batch != "pbs_reproduced_silver_unassessed"),
            "PBS provenance frozen membership differs",
        )
        if batch == "pbs_schedule_archived_pdf_unassessed" or batch.startswith(
            "reimbursement_projection_"
        ):
            item = ready.get(row["path"], {})
            _require(
                _identity(item) == _identity(row)
                and item.get("privacy_gate")
                == "blocked_no_source_specific_sensitivity_assessment"
                and item.get("ready_for_payload_read") is False,
                "historical readiness identity or privacy gate differs",
            )
            detail = (
                _pdf_record(row, docs, item)
                if batch == "pbs_schedule_archived_pdf_unassessed"
                else _projection_record(row, docs)
            )
        elif batch == "pbs_frozen_projection_unassessed":
            item = other.get(row["path"], {})
            _require(
                (
                    item.get("dataset"),
                    item.get("metadata_reconciliation_revision"),
                    item.get("path"),
                    item.get("sha256"),
                    item.get("byte_count"),
                )
                == _identity(row),
                "historical PBS Bronze readiness identity differs",
            )
            detail = _bronze_record(row, docs)
        elif batch == "pbs_reproduced_silver_unassessed":
            detail = _silver_record(row, docs)
        else:
            raise ValueError("unexpected unmatched PBS batch")
        result.append({
            **{key: row[key] for key in IDENTITY_KEYS},
            "batch": batch,
            "frozen_member": old["frozen_member"],
            **detail,
            "privacy": privacy.UNKNOWN,
            "ready_for_payload_read": False,
        })
    kinds = Counter(row["kind"] for row in result)
    expected = {
        "archived_pdf_acquisition_event": 5,
        "reimbursement_byte_identical_projection": 9,
        "reimbursement_layer_partition": 3,
        "pbs_bronze_projection": 1,
        "pbs_reproduced_silver": 1,
    }
    _require(dict(kinds) == expected, "PBS provenance cohort differs")
    frozen_paths = sum(row["frozen_member"] is True for row in result)
    _require(
        frozen_paths == FROZEN_PATHS
        and all(isinstance(row["frozen_member"], bool) for row in result),
        "PBS provenance frozen membership differs",
    )
    return {
        "schema_id": "global-medicines-atlas.pbs-unmatched-provenance",
        "schema_version": 1,
        "recorded_on": "2026-11-16",
        "inputs": {
            name: {"path": path, "sha256": digest}
            for name, (path, digest) in INPUTS.items()
        },
        "summary": {
            "prior_unmatched_paths": len(result),
            "frozen_paths": frozen_paths,
            "outside_frozen_paths": len(result) - frozen_paths,
            "archived_pdf_acquisition_events": kinds[
                "archived_pdf_acquisition_event"
            ],
            "byte_identical_reimbursement_projections": kinds[
                "reimbursement_byte_identical_projection"
            ],
            "reimbursement_layer_partitions": kinds[
                "reimbursement_layer_partition"
            ],
            "pbs_bronze_projections": kinds["pbs_bronze_projection"],
            "pbs_reproduced_silver_outputs": kinds["pbs_reproduced_silver"],
            "privacy_clearances_added": 0,
        },
        "objects": result,
        "boundaries": {
            "source_or_projection_payload_read": False,
            "participant_or_cohort_data_accessed": False,
            "dataset_acquired_or_published": False,
            "new_rights_or_privacy_decision": False,
            "v4_admission_or_consumer_canary": False,
            "frozen_inventory_changed": False,
        },
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    return reconcile(load_inputs(root))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    body = (json.dumps(build(), sort_keys=True, indent=2) + "\n").encode()
    path = ROOT / OUTPUT
    if args.check:
        _require(
            path.is_file() and path.read_bytes() == body,
            "PBS provenance report is stale",
        )
    else:
        path.write_bytes(body)
    print("PBS provenance metadata reconciled; privacy remains unassessed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
