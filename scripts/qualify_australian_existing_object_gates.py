"""Reconcile existing MBS gates and PBS privacy metadata without payload reads.

This value-free report checks retained evidence only. It does not change a
rights conclusion, qualify unknown sensitivity, create a v4 admission, run a
consumer or publish data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from operator import itemgetter
from pathlib import Path
from typing import Any

import scripts.qualify_australian_existing_derived_gates as derived
import scripts.qualify_australian_privacy_batch as privacy
import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_mbs_four_projection_dossiers as dossiers

ROOT = Path(__file__).resolve().parents[1]
DATASET = "edithatogo/australian-mbs-source-archive"
JULY_DIGEST = privacy.JULY_SHA
AUGUST_DIGEST = privacy.source_privacy.SOURCE_SHA
MBS_OBJECTS = 11
PBS_RELATED_OBJECTS = 1722
PBS_SCREENED_OBJECTS = 6
FROZEN_GROUPS = {"mbs_exact_classified_raw", "mbs_frozen_exact_replay"}
OUTSIDE_GROUP = "mbs_outside_footer_adjusted_replay"
PBS_GROUPS = {
    "pbs_schedule_pdf_unassessed",
    "pbs_schedule_archived_pdf_unassessed",
    "pbs_schedule_zip_unassessed",
    "pbs_schedule_csv_unassessed",
    "pbs_frozen_raw_unassessed",
    "pbs_frozen_projection_unassessed",
    "pbs_reproduced_silver_unassessed",
    "reimbursement_projection_byte_identical_unassessed",
    "reimbursement_projection_layer_partition_unassessed",
}
INPUTS = {
    "privacy": (
        "quality/qualifications/australian-existing-archive-privacy-batch-20261115.json",
        "7ab592f48583def8fb05b814d442b394463b3703caf978e885a1d96961029ec8",
    ),
    "reimbursement": privacy.EVIDENCE["reimbursement"],
    "frozen": bounded.INPUTS["frozen"],
    "overlay": bounded.INPUTS["overlay"],
    "rights": bounded.INPUTS["rights"],
    "effective": bounded.INPUTS["effective"],
    "outside_dossiers": privacy.EVIDENCE["outside_dossiers"],
    "outside_rights": derived.INPUTS["mbs_rights"],
    "frozen_rights": (
        "quality/qualifications/australian-mbs-august-bronze-rights-attestation-20261020.json",
        "8c1fe64099098ebe6e34ffe0409415d799e1a4c7c57382218fbfcfd52e0dbb24",
    ),
    "july_rights": (
        "quality/qualifications/australian-mbs-six-raw-object-rights-attestation-20261020.json",
        "79f3cd76786fbb13ef5607085ee97a69a21bb361b52025f886256093dd5e4f3d",
    ),
    "august_source_rights": (
        "quality/qualifications/australian-mbs-harvest-publication-authorization.json",
        "0fdc4d147d637c679ba0cc3eb165642974e533bb3ba044c99ee01f86127eb41b",
    ),
    "august_roles": (
        "quality/qualifications/australian-m112-v4-contract-role-evidence-qualification-20261021.json",
        "9ae96773ed19b1ec0795340aef1d341dbeeb0f8961ca7f231af633618ca21781",
    ),
    "july_candidate": (
        "quality/qualifications/australian-m112-2025-mbs-v4-receipt-readback-20261004.json",
        "9b2c5c0023c9e055cfd043e546d754efb5e2f8b51a0c107dffe7c36f3e56880e",
    ),
    "pbs_qualified": (
        "quality/qualifications/australian-m112-pbs-utilisation-role-readiness-20261028.json",
        "fb680271214008a850416151529a51933b16cb8b1521ec156c360872cd46d4b2",
    ),
    "pbs_screen": (
        "quality/qualifications/australian-pbs-utilisation-private-pattern-screen-20261021.json",
        "43c1c2a80adb86bb215dbd2340645fee1ce20d4c17a2a0545c9134c2d4c86f33",
    ),
    "csv_header_context": (
        "quality/qualifications/australian-pbs-dos-sensitive-header-context-20261021.json",
        "a5046bae17eb24a63e286f0c083ca0a2269c997bc2918b7fe3bf97324ee40654",
    ),
    "workbook_marker_context": (
        "quality/qualifications/australian-pbs-expenditure-marker-context-screen-20261021.json",
        "150c92ae5a2e488243b3bb324651ba946593246b548eb17c25694c7f0de149a1",
    ),
    "summary_header_context": (
        "quality/qualifications/australian-pbs-utilisation-summary-workbook-header-resolution-20261021.json",
        "f717d2bda385a1dc7080b3493de9430998172146c03b5f8252f21e6f61ae71dd",
    ),
}


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result = {(row["dataset"], row["path"]): row for row in rows}
    _require(len(result) == len(rows), "duplicate dataset/path identity")
    return result


def _same_bytes(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left.get("path") == right.get("path")
        and left.get("sha256") == right.get("sha256")
        and left.get("byte_count") == right.get("byte_count")
    )


def _attestation_objects(
    doc: dict[str, Any], *, expected_count: int
) -> dict[str, dict[str, Any]]:
    rows = bounded.metadata_rows(doc.get("authorized_objects"))
    by_path = bounded.metadata_index(rows)
    _require(len(by_path) == expected_count, "rights attestation scope differs")
    return by_path


def reconcile_mbs(  # ruff: ignore[too-many-locals,too-many-statements] -- Keep independent evidence roles explicit.
    e: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join the eleven exact MBS identities to independent retained gates."""
    selected = [
        row
        for row in bounded.metadata_rows(e["privacy"]["objects"])
        if row["batch"] in FROZEN_GROUPS | {OUTSIDE_GROUP}
    ]
    groups = Counter(row["batch"] for row in selected)
    _require(
        groups
        == {
            "mbs_exact_classified_raw": 3,
            "mbs_frozen_exact_replay": 4,
            OUTSIDE_GROUP: 4,
        }
        and len(_index(selected)) == MBS_OBJECTS
        and all(
            row["dataset"] == DATASET and row["privacy"] == privacy.ASSESSED
            for row in selected
        ),
        "MBS assessed identity set differs",
    )
    overlay = _index(bounded.metadata_rows(e["overlay"]["objects"]))
    members = _index(bounded.metadata_rows(e["frozen"]["members"]))
    other = _index(
        bounded.metadata_rows(e["reimbursement"]["other_frozen_objects"])
    )
    outside = _index(bounded.metadata_rows(e["outside_dossiers"]["dossiers"]))
    frozen_rights = _attestation_objects(e["frozen_rights"], expected_count=4)
    july_rights = _attestation_objects(e["july_rights"], expected_count=6)
    outside_rights = _attestation_objects(e["outside_rights"], expected_count=4)
    frozen_rights_readback = e["rights"]["august_2026_mbs_bronze_projections"]
    july_rights_readback = e["rights"]["mbs_raw_object_rights_attestation"]
    _require(
        frozen_rights_readback["attestation_path"] == INPUTS["frozen_rights"][0]
        and frozen_rights_readback["attestation_sha256"]
        == INPUTS["frozen_rights"][1]
        and july_rights_readback["attestation_path"] == INPUTS["july_rights"][0]
        and july_rights_readback["attestation_sha256"]
        == INPUTS["july_rights"][1],
        "MBS rights readback binding differs",
    )
    frozen_readback = bounded.metadata_index(
        bounded.metadata_rows(frozen_rights_readback["objects"])
    )
    july_readback = bounded.metadata_index(
        bounded.metadata_rows(july_rights_readback["objects"])
    )
    _require(
        e["frozen_rights"]["public_release_rights_attested"] is True
        and e["outside_rights"]["public_release_rights_attested"] is True
        and e["july_rights"]["decision"]["public_release_rights_attested"]
        is True
        and e["august_source_rights"]["external_publication_authorized"] is True
        and e["august_source_rights"][
            "maintainer_asserted_redistribution_permission"
        ]
        is True
        and e["august_source_rights"]["dataset"] == DATASET
        and e["frozen_rights"]["dataset"] == DATASET
        and e["outside_rights"]["dataset"] == DATASET
        and e["july_rights"]["dataset_identity"]["dataset"] == DATASET
        and "monthly_schedule_xml" in e["august_source_rights"]["categories"]
        and e["frozen_rights"]["boundaries"][
            "v4_admission_or_promotion_authorized"
        ]
        is False
        and e["frozen_rights"]["boundaries"]["consumer_canaries_authorized"]
        is False
        and e["outside_rights"]["boundaries"][
            "v4_admission_or_promotion_authorized"
        ]
        is False
        and e["outside_rights"]["boundaries"]["consumer_canaries_authorized"]
        is False
        and e["july_rights"]["boundaries"][
            "admission_or_consumer_canary_authorized"
        ]
        is False,
        "MBS rights or separate authorization boundary differs",
    )
    admitted = (
        e["effective"]["prior_admitted_identities"]
        + e["effective"]["new_admitted_identities"]
    )
    _require(
        len(admitted) == bounded.PRIOR_ADMISSIONS,
        "raw admission ledger differs",
    )
    admitted_paths = {(row["dataset"], row["path"]) for row in admitted}
    _require(
        not admitted_paths.intersection(_index(selected)),
        "selected object unexpectedly appears in raw admission ledger",
    )
    roles = _index(bounded.metadata_rows(e["august_roles"]["objects"]))
    results: list[dict[str, Any]] = []
    for row in selected:
        identity = (row["dataset"], row["path"])
        batch = row["batch"]
        candidate: dict[str, Any] | None = None
        rights_revision: str | None = None
        if row["frozen_member"]:
            member, previous, crosswalk = (
                members[identity],
                overlay[identity],
                other[identity],
            )
            lineage_revision = previous["revision"]
            _require(
                member["approved_dataset_revision"] == row["revision"]
                and crosswalk["frozen_revision"] == row["revision"]
                and crosswalk["metadata_reconciliation_revision"]
                == previous["revision"]
                and _same_bytes(row, crosswalk)
                and _same_bytes(
                    row, {"path": previous["path"], **previous["identity"]}
                )
                and previous["b1_b2_lineage"]["complete"] is True
                and previous["v4_admission"] is False
                and previous["consumer_canary"] is False,
                "frozen MBS identity or lineage differs",
            )
            if batch == "mbs_frozen_exact_replay":
                _require(
                    _same_bytes(row, frozen_rights[row["path"]])
                    and _same_bytes(row, frozen_readback[row["path"]])
                    and frozen_readback[row["path"]]["lineage_complete"]
                    is True,
                    "frozen projection rights differ",
                )
                rights = "maintainer_attested_exact_frozen_projection"
                lineage = "source_bound_exact_replay"
            elif row["sha256"] == JULY_DIGEST:
                _require(
                    _same_bytes(row, july_rights[row["path"]])
                    and _same_bytes(row, july_readback[row["path"]]),
                    "July raw rights differ",
                )
                _require(
                    e["july_candidate"]["source_identity"]["source_sha256"]
                    == JULY_DIGEST
                    and e["july_candidate"]["boundaries"][
                        "v4_admission_performed"
                    ]
                    is False,
                    "July candidate source binding differs",
                )
                rights = "maintainer_attested_exact_raw_object"
                lineage = "source_receipt_b1_b2_landed_unreviewed"
            else:
                _require(
                    row["sha256"] == AUGUST_DIGEST
                    and previous["rights"]["state"]
                    == "authorized_exact_source_release_permitted"
                    and previous["rights"]["decision_evidence"]
                    == {
                        "path": INPUTS["august_source_rights"][0],
                        "sha256": INPUTS["august_source_rights"][1],
                    },
                    "August raw rights binding differs",
                )
                role = roles[identity]
                _require(
                    role["sha256"] == row["sha256"]
                    and role["bytes"] == row["byte_count"]
                    and role["revision"] != row["revision"]
                    and role["v4_admission_eligible"] is False,
                    "August v4 candidate identity differs",
                )
                candidate = {
                    "revision": role["revision"],
                    "role_states": role["contract_role_states"],
                    "state": "candidate_unbound_at_different_revision",
                }
                rights = "existing_exact_source_release_permission"
                lineage = "source_b1_b2_lifecycle_and_alias_evidence"
        else:
            prior = outside[identity]
            attested = outside_rights[row["path"]]
            rights_revision = attested["revision"]
            lineage_revision = e["outside_dossiers"]["producers"][
                prior["producer"]
            ]["revision"]
            _require(
                _same_bytes(row, prior)
                and _same_bytes(row, attested)
                and attested["dataset"] == row["dataset"]
                and attested["revision"] == e["outside_rights"]["revision"]
                and row["revision"] == prior["revision"]
                and prior["rights_attestation_revision"] == attested["revision"]
                and prior["v4_admission"] == "not_performed"
                and prior["consumer_check"] == "not_performed",
                "outside MBS identity, rights or gate differs",
            )
            rights = "maintainer_attested_exact_object_at_prior_revision"
            lineage = "producer_evidence_and_footer_adjusted_replay"
        results.append({
            **{
                key: row[key]
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
            "privacy": row["privacy"],
            "rights": rights,
            "rights_attestation_revision": rights_revision,
            "lineage": lineage,
            "lineage_evidence_revision": lineage_revision,
            "candidate_v4_roles": candidate,
            "raw_v4_ledger_membership": "not_among_14_recorded_raw_admissions",
            "v4_admission": "not_established_by_selected_evidence",
            "consumer_canary": "not_established_for_this_object",
            "independent_recovery": "not_established_by_this_reconciliation",
        })
    return sorted(results, key=itemgetter("dataset", "path"))


def _screen_contexts(
    evidence: dict[str, dict[str, Any]], qualified: dict[str, Any]
) -> dict[str, dict[str, dict[str, Any]]]:
    contexts: dict[str, dict[str, dict[str, Any]]] = {}
    for name in (
        "csv_header_context",
        "workbook_marker_context",
        "summary_header_context",
    ):
        document = evidence[name]
        _require(
            qualified["inputs"][name]
            == {"path": INPUTS[name][0], "sha256": INPUTS[name][1]}
            and document["dataset"] == evidence["pbs_screen"]["dataset"]
            and document["revision"] == evidence["pbs_screen"]["revision"]
            and document["boundaries"]["source_bytes_persisted_locally"]
            is False,
            "PBS prior context binding differs",
        )
        value_flag = (
            "source_data_values_or_rows_emitted"
            if name == "summary_header_context"
            else "source_values_emitted"
        )
        _require(
            document["boundaries"][value_flag] is False,
            "PBS prior context includes source values",
        )
        rows = (
            [document["object"]]
            if name == "summary_header_context"
            else bounded.metadata_rows(document["objects"])
        )
        contexts[name] = bounded.metadata_index(rows)
    return contexts


def _screen_resolved(
    row: dict[str, Any],
    screened: dict[str, dict[str, Any]],
    contexts: dict[str, dict[str, dict[str, Any]]],
) -> bool:
    screen = screened[row["path"]]
    roles = row["sensitivity_assessment"]["evidence_roles"]
    if (
        "private_pattern_screen" not in roles
        or screen["email_like_cell_values"] != 0
    ):
        return False
    if any(
        name != "private_pattern_screen"
        and (
            name not in contexts
            or row["path"] not in contexts[name]
            or not _same_bytes(row, contexts[name][row["path"]])
        )
        for name in roles
    ):
        return False
    if screen["screen_state"] == "no_email_or_sensitive_field_label_pattern":
        return screen["sensitive_header_or_label_hits"] == 0
    return (
        screen["screen_state"] == "review_required"
        and screen["sensitive_header_or_label_hits"] > 0
        and "csv_header_context" in roles
    )


def reconcile_pbs(  # ruff: ignore[too-many-locals] -- Preserve exact source and projection joins.
    e: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compare unassessed PBS-related metadata with six exact prior screens."""
    rows = [
        row for row in e["privacy"]["objects"] if row["batch"] in PBS_GROUPS
    ]
    groups = Counter(row["batch"] for row in rows)
    _require(
        len(rows) == PBS_RELATED_OBJECTS
        and len(_index(rows)) == PBS_RELATED_OBJECTS
        and all(row["privacy"] == privacy.UNKNOWN for row in rows),
        "PBS-related privacy scope differs",
    )
    raw = [
        row
        for row in e["reimbursement"]["objects"]
        if row["representation"] == "raw_source_payload"
    ]
    raw_index = _index(raw)
    schedule = [row for row in rows if row["batch"].startswith("pbs_schedule_")]
    _require(
        len(schedule) == len(raw_index) == bounded.RAW_OBJECTS
        and len({
            row["metadata_references"]["acquisition_event_path"] for row in raw
        })
        == bounded.RAW_OBJECTS
        and all(
            _same_bytes(row, raw_index[row["dataset"], row["path"]])
            and row["revision"]
            == raw_index[row["dataset"], row["path"]]["revision"]
            and raw_index[row["dataset"], row["path"]]["observed_sensitivity"]
            == {
                "data_sensitivity": "unknown",
                "personal_data": "unknown",
                "publication": "review_required",
            }
            for row in schedule
        ),
        "PBS schedule B1 sensitivity or identity differs",
    )
    projections = [
        row
        for row in e["reimbursement"]["objects"]
        if row["representation"] == "existing_data_projection"
    ]
    projections_by_identity = _index(projections)
    selected_projections = [
        row
        for row in rows
        if row["batch"].startswith("reimbursement_projection_")
    ]
    _require(
        len(projections)
        == len(selected_projections)
        == bounded.PROJECTION_OBJECTS
        and all(
            _same_bytes(
                row, projections_by_identity[row["dataset"], row["path"]]
            )
            and row["revision"]
            == projections_by_identity[row["dataset"], row["path"]]["revision"]
            and projections_by_identity[row["dataset"], row["path"]][
                "privacy_gate"
            ]
            == "blocked_no_source_specific_sensitivity_assessment"
            and projections_by_identity[row["dataset"], row["path"]][
                "ready_for_payload_read"
            ]
            is False
            for row in selected_projections
        ),
        "reimbursement projection privacy identity differs",
    )
    qualified, screen = e["pbs_qualified"], e["pbs_screen"]
    _require(
        qualified["inputs"]["private_pattern_screen"]
        == {"path": INPUTS["pbs_screen"][0], "sha256": INPUTS["pbs_screen"][1]}
        and qualified["scope"]["objects"]
        == screen["scope"]["object_count"]
        == PBS_SCREENED_OBJECTS
        and screen["scope"]["source_values_emitted"] is False
        and screen["scope"]["source_bytes_persisted_locally"] is False,
        "PBS prior screen scope differs",
    )
    screened = bounded.metadata_index(bounded.metadata_rows(screen["objects"]))
    known = bounded.metadata_rows(qualified["objects"])
    contexts = _screen_contexts(e, qualified)
    _require(
        len(known) == len(screened) == PBS_SCREENED_OBJECTS
        and qualified["objects"][0]["dataset"] == screen["dataset"]
        and all(
            row["dataset"] == screen["dataset"]
            and row["revision"] == screen["revision"]
            and row["path"] in screened
            and _same_bytes(row, screened[row["path"]])
            and row["sensitivity_assessment"]["data_sensitivity"]
            == "non_sensitive"
            and row["sensitivity_assessment"][
                "exhaustive_personal_data_clearance"
            ]
            is False
            and _screen_resolved(row, screened, contexts)
            and screened[row["path"]]["source_values_emitted"] is False
            for row in known
        ),
        "PBS prior screened objects differ",
    )
    known_content = {(row["sha256"], row["byte_count"]) for row in known}
    matches = [
        row
        for row in rows
        if (row["sha256"], row["byte_count"]) in known_content
    ]
    identities = sorted(
        (
            row["dataset"],
            row["revision"],
            row["path"],
            row["sha256"],
            row["byte_count"],
        )
        for row in rows
    )
    encoded = json.dumps(
        identities, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return {
        "unassessed_objects": len(rows),
        "groups": dict(sorted(groups.items())),
        "selected_identity_sha256": hashlib.sha256(encoded).hexdigest(),
        "schedule_b1_records_unknown": len(raw),
        "schedule_distinct_digest_size_pairs": len({
            (row["sha256"], row["byte_count"]) for row in schedule
        }),
        "separately_qualified_utilisation_objects": len(known),
        "same_digest_and_size_candidates": len(matches),
        "matching_candidates_gain_privacy_clearance": False,
        "newly_assessed_non_sensitive": 0,
        "unassessed_payload_reads_permitted": False,
    }


def build_report(root: Path = ROOT) -> dict[str, Any]:
    """Build a digest-bound metadata-only readiness report."""
    evidence = {
        name: bounded.read_bound_metadata(root, *binding)
        for name, binding in INPUTS.items()
    }
    _require(
        privacy.build_report(root) == evidence["privacy"],
        "privacy packet differs",
    )
    _require(
        bounded.build_report(root) == evidence["reimbursement"],
        "reimbursement packet differs",
    )
    _require(
        dossiers.build_report(root) == evidence["outside_dossiers"],
        "outside dossier packet differs",
    )
    mbs = reconcile_mbs(evidence)
    pbs = reconcile_pbs(evidence)
    return {
        "schema_id": "global-medicines-atlas.australian-existing-object-gate-check",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "inputs": {
            name: {"path": value[0], "sha256": value[1]}
            for name, value in INPUTS.items()
        },
        "mbs_objects": mbs,
        "pbs_metadata": pbs,
        "boundaries": {
            "participant_or_cohort_data_accessed": False,
            "source_or_projection_payload_read": False,
            "dataset_added_or_published": False,
            "rights_conclusion_changed": False,
            "v4_admission_performed": False,
            "consumer_canary_performed": False,
            "independent_recovery_established": False,
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
        raise ValueError("stored existing-object gate report differs")
    print(
        json.dumps(
            {
                "mbs_objects_checked": len(report["mbs_objects"]),
                **report["pbs_metadata"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
