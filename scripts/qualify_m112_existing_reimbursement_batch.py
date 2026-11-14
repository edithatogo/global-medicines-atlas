"""Reconcile frozen public-archive metadata without reading source payloads.

This is a readiness report, not a v4 admission or a privacy clearance. Every
object retains its own identity, attestation and lineage references. No object
with unknown or unqualified sensitivity is handed to a consumer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from operator import itemgetter
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from global_medicines_atlas.strict_json import unique_json_object

ROOT = Path(__file__).resolve().parents[1]
DATASET = "edithatogo/reimbursement-atlas"
REVISION = "8e062578f14e12cf3238700a93946339da9c5d88"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_JSON_BYTES = 12 * 1024 * 1024
FROZEN_OBJECTS = 1_759
PRIOR_ADMISSIONS = 14
DEFERRED_OBJECTS = 1_745
REIMBURSEMENT_OBJECTS = 1_719
RAW_OBJECTS = 1_707
PROJECTION_OBJECTS = 12
OTHER_FROZEN_OBJECTS = 26
PRIOR_MBS_SILVER_OBJECTS = 6
PARTITION_SOURCE = "data/derived/medallion/medallion_artifacts.jsonl"
PARTITION_SOURCE_SHA256 = (
    "67fc5ec969875ef505a5a830311b8d3454b83ffcd48649194790c7722869a6cd"
)
PARTITION_SOURCE_BYTES = 18_087
PARTITION_SOURCE_ROWS = 22
PARTITION_ROWS = {"silver": 17, "gold": 2, "platinum": 3}
INPUTS = {
    "frozen": (
        "quality/qualifications/australian-m112-frozen-object-inventory-20261018.json",
        "eaa1d84325c7672100398acf8116f0312369ca336d42ed21eee110452d3fefa4",
    ),
    "effective": (
        "quality/qualifications/australian-m112-effective-raw-delivery-reconciliation-20261028.json",
        "c556cf596514d7cb69bce0a188f87460ad2746c3afacc559cec8ebd56cd7a3a3",
    ),
    "overlay": (
        "quality/qualifications/australian-m112-per-object-gate-reconciliation-20261019-reimbursement-medallion-projection-lineage.json",
        "278f7e72b098eb89453e3e42542ba3ee4fff6a5fd02726f3473e8e3d75333a7d",
    ),
    "rights": (
        "quality/qualifications/australian-m112-current-rights-reconciliation-20261021-2.json",
        "6905351d9dae194699f33d91054048664b27daf1bcced7dcfc16aa5d15977f86",
    ),
    "raw_permission": (
        "quality/qualifications/reimbursement-atlas-pbs-raw-permission-20260831.json",
        "0817123492cfe20858f86b3ec14c92539081a647b17dd6933d2d2ff8c266d098",
    ),
    "projection_attestation": (
        "quality/qualifications/australian-reimbursement-atlas-medallion-rights-attestation-20261020.json",
        "f781278ad4af0102f66078439897f7ac326cd59e25a43d48a1c4a97ffe682fbe",
    ),
    "raw_lineage": (
        "quality/qualifications/australian-m112-pbs-projected-b1-b2-lineage-20261019.json",
        "aa4a0df6df4ec723e7b65f55379f47ae7912e4777a6b9d3bb3454c1accf3a16f",
    ),
    "pdf_lineage": (
        "quality/qualifications/australian-m112-pbs-pdf-archive-lineage-20261019.json",
        "b0196e9639fe86d5cf21dae2240bc7c3d6ad0983f8435aa0d55d32538f4c3486",
    ),
    "projection_lineage": (
        "quality/qualifications/australian-m112-reimbursement-medallion-projection-lineage-20261019.json",
        "a9146e11c71f3d031135dc395d84589497a4aa50e9e10f15acbca08498fc7f97",
    ),
    "mbs_silver_consumers": (
        "quality/qualifications/australian-mbs-silver-v4-admission-remote-read-20261028-40664169948/admission-remote-read.json",
        "b48eedc7de599f646fe4c722b2ac869c6ebbe9935be09f58464d4f7b2ab71b12",
    ),
}


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("expected an evidence object")
    return cast("dict[str, Any]", value)


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise TypeError("expected an evidence list")
    return [_object(item) for item in cast("list[object]", value)]


def _read_bound(root: Path, relative: str, digest: str) -> dict[str, Any]:
    """Read only a digest-bound repository JSON metadata file."""
    path = Path(relative)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.suffix != ".json"
        or not relative.startswith((
            "quality/qualifications/",
            "quality/bronze/",
        ))
        or not SHA256.fullmatch(digest)
    ):
        raise ValueError("invalid metadata reference")
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("metadata reference contains a symlink")
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError("metadata reference escapes repository")
    with current.open("rb") as source:
        body = source.read(MAX_JSON_BYTES + 1)
    if len(body) > MAX_JSON_BYTES or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError("metadata reference digest differs")
    return _object(json.loads(body, object_pairs_hook=unique_json_object))


def _index(
    rows: list[dict[str, Any]], *, key: str = "path"
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        path = row.get(key)
        if not isinstance(path, str) or not path or path in result:
            raise ValueError("duplicate or invalid evidence path")
        result[path] = row
    return result


def _identity(row: dict[str, Any]) -> tuple[str, int]:
    digest, size = row.get("sha256"), row.get("byte_count")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ValueError("invalid object digest")
    if type(size) is not int or size <= 0:
        raise ValueError("invalid object size")
    return digest, size


def _validate_metadata_records(
    root: Path,
    lineage: dict[str, Any],
    bindings: dict[str, Any],
    *,
    digest: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Verify existing B1/B2 and landed metadata; never read a payload."""
    references: dict[str, str] = {}
    records: dict[str, dict[str, Any]] = {}
    for role in (
        "acquisition_event_path",
        "b2_manifest_path",
        "landed_admission_path",
    ):
        path = lineage.get(role)
        if not isinstance(path, str) or not isinstance(bindings.get(path), str):
            raise TypeError("missing object metadata binding")
        expected = cast("str", bindings[path])
        records[role] = _read_bound(root, path, expected)
        references[role] = path
        references[role.replace("_path", "_sha256")] = expected
    event = records["acquisition_event_path"]
    b2 = records["b2_manifest_path"]
    landed = records["landed_admission_path"]
    acquisition_id = event.get("acquisition_id")
    rows = _rows(b2.get("rows"))
    if not all((
        event.get("schema_id")
        == "global-medicines-atlas.bronze-acquisition-event",
        event.get("payload_sha256") == digest,
        event.get("content_id") == digest,
        isinstance(acquisition_id, str) and bool(acquisition_id),
        b2.get("schema_id")
        == "global-medicines-atlas.b2-raw-evidence-manifest",
        b2.get("authoritative") is True,
        b2.get("row_count") == 1,
        len(rows) == 1,
        landed.get("schema_id") == "global-medicines-atlas.bronze-admission",
        landed.get("state") == "landed",
        landed.get("reviewer_status") == "unreviewed",
        landed.get("acquisition_id") == acquisition_id,
        landed.get("content_id") == digest,
    )):
        raise ValueError("B1/B2 or landed identity differs")
    b2_row = rows[0]
    if not all((
        b2_row.get("content_id") == digest,
        b2_row.get("acquisition_id") == acquisition_id,
        b2_row.get("kind") == "source_payload",
        b2_row.get("state") == "external_reference_only",
        b2_row.get("payload_contents_in_metadata") is False,
    )):
        raise ValueError("B2 metadata identity differs")
    sensitivity = _object(event.get("sensitivity"))
    observed = {
        "data_sensitivity": "unknown",
        "personal_data": "unknown",
        "publication": "review_required",
    }
    if any(sensitivity.get(key) != value for key, value in observed.items()):
        raise ValueError("source sensitivity metadata differs")
    return references, observed


def _raw_record(
    root: Path,
    *,
    path: str,
    frozen: dict[str, Any],
    overlay: dict[str, Any],
    rights: dict[str, Any],
    lineage: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    digest, size = _identity(rights)
    observed = _object(overlay.get("identity"))
    if not all((
        frozen.get("object_class") == "raw_source_payload",
        frozen.get("dataset") == DATASET,
        overlay.get("dataset") == DATASET,
        rights.get("dataset") == DATASET,
        lineage.get("dataset") == DATASET,
        overlay.get("candidate_class") == "raw_source_payload",
        path.startswith("raw/pbs/payloads/"),
        overlay.get("revision") == REVISION,
        observed.get("sha256") == digest,
        observed.get("byte_count") == size,
        lineage.get("revision") == REVISION,
        lineage.get("content_sha256") == digest,
        lineage.get("byte_count") == size,
        rights.get("v4_admission") is False,
        rights.get("consumer_canary") is False,
        lineage.get("v4_admission") is False,
        lineage.get("consumer_canary") is False,
    )):
        raise ValueError("raw object identity or historical gate differs")
    locator = rights.get("source_locator")
    parsed = urlsplit(locator) if isinstance(locator, str) else None
    producer = lineage.get("producer_b1")
    recorded = (
        _object(producer).get("source_locator")
        if producer is not None
        else _object(lineage.get("producer_archive_variant_receipt")).get(
            "official_source_url"
        )
    )
    if not (
        parsed is not None
        and parsed.scheme == "https"
        and parsed.netloc == "www.pbs.gov.au"
        and parsed.path.startswith("/publication/schedule/")
        and locator == recorded
        and rights.get("format") in {"pdf", "zip", "csv"}
        and Path(path).suffix.lower() == f".{rights['format']}"
    ):
        raise ValueError("raw source profile differs")
    local = _object(lineage.get("local_records", lineage))
    references, sensitivity = _validate_metadata_records(
        root, local, _object(report.get("output_bindings")), digest=digest
    )
    return {
        "dataset": DATASET,
        "revision": REVISION,
        "path": path,
        "sha256": digest,
        "byte_count": size,
        "representation": "raw_source_payload",
        "rights_evidence": "owner_attested_raw_redistribution_permission",
        "lineage_evidence": "linked_b1_b2_and_landed_unreviewed_metadata",
        "metadata_references": references,
        "observed_sensitivity": sensitivity,
        "privacy_gate": "blocked_no_source_specific_sensitivity_assessment",
        "v4_admission": "not_performed",
        "consumer_check": "not_performed_privacy_gate_blocked",
        "ready_for_payload_read": False,
    }


def _projection_record(
    *,
    path: str,
    frozen: dict[str, Any],
    overlay: dict[str, Any],
    rights: dict[str, Any],
    lineage: dict[str, Any],
) -> dict[str, Any]:
    digest, size = _identity(rights)
    observed = _object(overlay.get("identity"))
    if not all((
        frozen.get("object_class") == "existing_data_projection",
        frozen.get("dataset") == DATASET,
        overlay.get("dataset") == DATASET,
        rights.get("dataset") == DATASET,
        overlay.get("candidate_class") == "existing_data_projection",
        path.startswith("data/medallion/"),
        overlay.get("revision") == REVISION,
        observed.get("sha256") == digest,
        observed.get("byte_count") == size,
        lineage.get("dataset_sha256") == digest,
        lineage.get("dataset_byte_count") == size,
        lineage.get("b1_b2_lineage_complete") is True,
    )):
        raise ValueError("projection identity or lineage differs")
    relation = lineage.get("projection_relation")
    if relation == "byte_identical_to_exact_producer_source_path":
        if not all((
            lineage.get("producer_source_sha256") == digest,
            lineage.get("producer_source_byte_count") == size,
            isinstance(lineage.get("producer_source_path"), str),
        )):
            raise ValueError("byte-identical projection lineage differs")
        lineage_evidence = "byte_identical_producer_projection_metadata_linked"
    elif relation == "exact_layer_partition_of_medallion_artifacts":
        layer = lineage.get("config_name")
        if not isinstance(layer, str) or layer not in PARTITION_ROWS:
            raise ValueError("partition projection layer differs")
        if not all((
            path == f"data/medallion/{layer}/data.jsonl",
            lineage.get("producer_source_path") == PARTITION_SOURCE,
            lineage.get("producer_source_sha256") == PARTITION_SOURCE_SHA256,
            lineage.get("producer_source_byte_count") == PARTITION_SOURCE_BYTES,
            lineage.get("producer_source_row_count") == PARTITION_SOURCE_ROWS,
            lineage.get("row_count") == PARTITION_ROWS.get(layer),
        )):
            raise ValueError("partition projection lineage differs")
        lineage_evidence = "exact_layer_partition_metadata_linked"
    else:
        raise ValueError("unsupported projection relation")
    return {
        "dataset": DATASET,
        "revision": REVISION,
        "path": path,
        "sha256": digest,
        "byte_count": size,
        "representation": "existing_data_projection",
        "rights_evidence": "maintainer_attested_exact_projection_rights",
        "lineage_evidence": lineage_evidence,
        "metadata_references": {},
        "observed_sensitivity": None,
        "privacy_gate": "blocked_no_source_specific_sensitivity_assessment",
        "v4_admission": "not_performed",
        "consumer_check": "not_performed_privacy_gate_blocked",
        "ready_for_payload_read": False,
    }


def _other_frozen_records(
    members: list[dict[str, Any]],
    overlays: list[dict[str, Any]],
    admitted: set[tuple[str, str]],
    silver: dict[str, Any],
) -> list[dict[str, Any]]:
    """Reconcile the remaining frozen metadata without reading payloads.

    The six prior MBS Silver consumer receipts are at an independently
    qualified immutable revision. Their raw-ledger deferral remains unchanged.
    """
    candidates = {
        (row["dataset"], row["path"]): row
        for row in members
        if row.get("dataset") != DATASET
        and (row["dataset"], row["path"]) not in admitted
    }
    if len(candidates) != OTHER_FROZEN_OBJECTS:
        raise ValueError("other frozen membership differs")
    canary = _object(silver.get("consumer_canary"))
    boundaries = _object(silver.get("boundaries"))
    if not all((
        silver.get("status") == "passed",
        silver.get("verified_object_count") == PRIOR_MBS_SILVER_OBJECTS,
        silver.get("dataset") == "edithatogo/australian-mbs-source-archive",
        canary.get("status") == "passed",
        canary.get("request_count") == PRIOR_MBS_SILVER_OBJECTS,
        boundaries.get("candidate_product_profiles_admitted") is True,
        boundaries.get("consumer_canaries") is True,
        boundaries.get("source_values_included") is False,
        boundaries.get("external_publication_performed") is False,
        boundaries.get("new_sources_added") is False,
        boundaries.get("m112_federation_acceptance") is False,
    )):
        raise ValueError("historical MBS Silver consumer evidence differs")
    silver_by_path = _index(_rows(silver.get("objects")))
    if len(silver_by_path) != PRIOR_MBS_SILVER_OBJECTS:
        raise ValueError("historical MBS Silver membership differs")
    selected = [
        row
        for row in overlays
        if (row.get("dataset"), row.get("path")) in candidates
    ]
    if len(selected) != OTHER_FROZEN_OBJECTS:
        raise ValueError("other frozen overlay differs")
    result: list[dict[str, Any]] = []
    found_silver: set[str] = set()
    for row in selected:
        dataset, path = row["dataset"], row["path"]
        member = candidates[dataset, path]
        digest, size = _identity(_object(row.get("identity")))
        if not all((
            row.get("revision")
            == member.get("current_reconciliation_revision"),
            row.get("candidate_class") == member.get("object_class"),
            _object(row.get("b1_b2_lineage")).get("complete") is True,
            row.get("v4_admission") is False,
            row.get("consumer_canary") is False,
        )):
            raise ValueError("other historical gate metadata differs")
        rights = _object(row.get("rights")).get("state")
        if not isinstance(rights, str) or not rights:
            raise ValueError("other historical rights metadata missing")
        previous = silver_by_path.get(path)
        prior_consumer = None
        if previous is not None:
            if not all((
                dataset == silver.get("dataset"),
                previous.get("sha256") == digest,
                previous.get("byte_count") == size,
                _object(previous.get("admission_record")).get("revision")
                == silver.get("revision"),
            )):
                raise ValueError("prior MBS Silver identity differs")
            found_silver.add(path)
            prior_consumer = {
                "status": "passed",
                "qualified_revision": silver["revision"],
                "evidence_input": "mbs_silver_consumers",
                "scope": "prior_separate_silver_profile_not_raw_ledger",
            }
        result.append({
            "dataset": dataset,
            "frozen_revision": member["approved_dataset_revision"],
            "metadata_reconciliation_revision": row["revision"],
            "path": path,
            "sha256": digest,
            "byte_count": size,
            "representation": row["candidate_class"],
            "historical_lineage_complete": True,
            "historical_rights_state": rights,
            "prior_separate_silver_consumer": prior_consumer,
            "current_payload_read": "not_performed",
            "current_raw_v4_admission": "not_performed",
        })
    if found_silver != set(silver_by_path):
        raise ValueError("historical MBS Silver paths not reconciled")
    return sorted(result, key=itemgetter("dataset", "path"))


def build_report(root: Path = ROOT) -> dict[str, Any]:  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements] -- preserve exact independent joins
    """Join each frozen object to retained evidence without admitting it."""
    docs = {
        name: _read_bound(root, path, digest)
        for name, (path, digest) in INPUTS.items()
    }
    frozen = docs["frozen"]
    effective = docs["effective"]
    overlay = docs["overlay"]
    rights = docs["rights"]
    permission = docs["raw_permission"]
    attestation = docs["projection_attestation"]
    counts = _object(effective.get("effective_counts"))
    if not all((
        _object(frozen.get("scope")).get("approved_member_count")
        == FROZEN_OBJECTS,
        counts.get("frozen_objects") == FROZEN_OBJECTS,
        counts.get("raw_v4_admissions") == PRIOR_ADMISSIONS,
        counts.get("raw_admitted_object_reader_canaries") == PRIOR_ADMISSIONS,
        counts.get("deferred_objects") == DEFERRED_OBJECTS,
        counts.get("frozen_denominator_changed") is False,
        permission.get("source_id") == "au_pbs",
        permission.get("permission_status") == "active",
        permission.get("decision") == "allow_raw_redistribution",
        permission.get("permission_basis") == "owner_attestation",
        attestation.get("dataset") == DATASET,
        attestation.get("revision") == REVISION,
        attestation.get("public_redistribution_rights_attested") is True,
        _object(attestation.get("boundaries")).get(
            "v4_admission_or_promotion_authorized"
        )
        is False,
    )):
        raise ValueError("frozen inventory or existing authority differs")
    members = _rows(frozen.get("members"))
    overlay_rows = _rows(overlay.get("objects"))
    frozen_all = {(row["dataset"], row["path"]) for row in members}
    if (
        len(members) != FROZEN_OBJECTS
        or len(frozen_all) != FROZEN_OBJECTS
        or len(overlay_rows) != FROZEN_OBJECTS
    ):
        raise ValueError("frozen membership is not unique")
    if {(row["dataset"], row["path"]) for row in overlay_rows} != frozen_all:
        raise ValueError("overlay membership differs")
    admitted = {
        (row["dataset"], row["path"])
        for row in _rows(effective.get("prior_admitted_identities"))
        + _rows(effective.get("new_admitted_identities"))
    }
    if len(admitted) != PRIOR_ADMISSIONS or not admitted <= frozen_all:
        raise ValueError("prior admitted identities differ")
    chosen = [row for row in members if row.get("dataset") == DATASET]
    if len(chosen) != REIMBURSEMENT_OBJECTS or any(
        row.get("approved_dataset_revision") != REVISION for row in chosen
    ):
        raise ValueError("reimbursement scope or revision differs")
    selected = _index(chosen)
    if any((DATASET, path) in admitted for path in selected):
        raise ValueError("candidate is already in admitted raw ledger")
    overlays = _index([
        row for row in overlay_rows if row.get("dataset") == DATASET
    ])
    rights_group = _object(rights.get("pbs_raw_redistribution_permission"))
    if not all((
        rights_group.get("permission_sha256") == INPUTS["raw_permission"][1],
        rights_group.get("project_publication_authorized_by_this_record")
        is False,
        _object(rights_group.get("source_owner_permission")).get(
            "publisher_permission_document_verified"
        )
        is False,
    )):
        raise ValueError("retained raw permission boundary differs")
    raw_rights = _index([
        row
        for row in _rows(rights_group.get("objects"))
        if row.get("dataset") == DATASET
    ])
    projection_rights = _index(_rows(attestation.get("authorized_objects")))
    if (
        len(raw_rights) != RAW_OBJECTS
        or len(projection_rights) != PROJECTION_OBJECTS
    ):
        raise ValueError("exact attestation membership differs")
    if set(raw_rights) & set(projection_rights) or set(raw_rights) | set(
        projection_rights
    ) != set(selected):
        raise ValueError("rights do not cover the exact selected paths")
    raw_reports = [docs["raw_lineage"], docs["pdf_lineage"]]
    raw_lineages: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for report in raw_reports:
        for row in _rows(report.get("objects")):
            if row.get("dataset") != DATASET:
                continue
            path = row.get("path")
            if not isinstance(path, str) or path in raw_lineages:
                raise ValueError("duplicate raw lineage path")
            raw_lineages[path] = (row, report)
    projections = _index(
        _rows(docs["projection_lineage"].get("objects")), key="dataset_path"
    )
    if set(raw_lineages) != set(raw_rights) or set(projections) != set(
        projection_rights
    ):
        raise ValueError("lineage membership differs from selected rights")
    records: list[dict[str, Any]] = []
    for path in sorted(selected):
        if path in raw_rights:
            lineage, report = raw_lineages[path]
            record = _raw_record(
                root,
                path=path,
                frozen=selected[path],
                overlay=overlays[path],
                rights=raw_rights[path],
                lineage=lineage,
                report=report,
            )
        else:
            record = _projection_record(
                path=path,
                frozen=selected[path],
                overlay=overlays[path],
                rights=projection_rights[path],
                lineage=projections[path],
            )
        records.append(record)
    other_records = _other_frozen_records(
        members, overlay_rows, admitted, docs["mbs_silver_consumers"]
    )
    counts_by_representation = Counter(row["representation"] for row in records)
    return {
        "schema_id": "global-medicines-atlas.m112-existing-reimbursement-batch-readiness",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "evidence_inputs": {
            name: {"path": path, "sha256": digest}
            for name, (path, digest) in INPUTS.items()
        },
        "scope": {
            "frozen_objects": 1759,
            "prior_raw_admissions": 14,
            "prior_raw_canaries": 14,
            "deferred_objects": 1745,
            "selected_reimbursement_objects": len(records),
            "raw_objects": counts_by_representation["raw_source_payload"],
            "projection_objects": counts_by_representation[
                "existing_data_projection"
            ],
            "other_raw_ledger_deferred_objects": len(other_records),
        },
        "result": {
            "metadata_identity_rights_lineage_joined": len(records),
            "raw_source_sensitivity_unknown": sum(
                row["representation"] == "raw_source_payload"
                and row["observed_sensitivity"]["data_sensitivity"] == "unknown"
                for row in records
            ),
            "projection_sensitivity_not_qualified": counts_by_representation[
                "existing_data_projection"
            ],
            "ready_for_payload_read": sum(
                row["ready_for_payload_read"] for row in records
            ),
            "new_admissions": 0,
            "consumer_checks_on_selected_objects": 0,
            "other_metadata_rows_reconciled": len(other_records),
            "other_prior_separate_mbs_silver_consumer_receipts": sum(
                row["prior_separate_silver_consumer"] is not None
                for row in other_records
            ),
        },
        "objects": records,
        "other_frozen_objects": other_records,
        "boundaries": {
            "source_payload_bytes_read": False,
            "source_values_or_rows_emitted": False,
            "individual_participant_or_cohort_data_accessed": False,
            "new_sources_or_datasets": False,
            "publication_or_rights_decision": False,
            "v4_admission_performed": False,
            "independent_recovery_qualified": False,
            "federation_accepted": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = build_report()
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(report["result"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
