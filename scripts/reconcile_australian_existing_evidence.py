"""Reconcile existing Australian admission, privacy and recovery evidence offline.

Only hash-bound repository metadata is read. This does not clear privacy, close
receipt bytes, admit an object, inspect a payload, or establish independent recovery.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from operator import itemgetter
from pathlib import Path
from typing import Any

import scripts.prepare_mbs_august_projection_admission as preparation
import scripts.qualify_m112_existing_reimbursement_batch as bounded

ROOT = Path(__file__).resolve().parents[1]
Q = "quality/qualifications/"
OUTPUT = Q + "australian-existing-evidence-closure-20261116.json"
INPUTS = {
    "dossiers": (
        preparation.OUTPUT,
        "1aee87122b0062e297645480312c4462aa1f097e0c866c2f9bb672c3ef673ecf",
    ),
    "privacy": (
        Q + "australian-existing-archive-privacy-batch-20261115.json",
        "7ab592f48583def8fb05b814d442b394463b3703caf978e885a1d96961029ec8",
    ),
    "pbs_links": (
        Q + "australian-pbs-m107-existing-archive-crosswalk-20261115.json",
        "5850ad0f315bedf03971c9811f9ac12d9fb9fbaf77e72fd710cbac1d4ce5fcd9",
    ),
    "pbs_coverage": (
        Q + "australian-pbs-acquisition-privacy-coverage-20261115.json",
        "a59046ce6d88de32b954fcbc97f360937e4e240deb95349cd4a1fd3292b21ed2",
    ),
    "pbs_provenance": (
        Q + "australian-pbs-unmatched-provenance-20261116.json",
        "cf311f72d259b3b228ed7aac7294ea13f6f539e077b46be5d408c0f2f3991cd5",
    ),
    "member_triage": (
        Q + "australian-pbs-member-privacy-triage-20261115.json",
        "2f043b8e21d2a9d28b375f3e27c7cae0468ae0f50a52fd43dcd88754a4f0c98b",
    ),
    "schema_context": (
        Q + "australian-pbs-schema-privacy-context-20261115.json",
        "4a629204fc3810ea8e3d3de5e29f304e8cdecaf9ecbb4889ece6ca43db360209",
    ),
    "primary_history": (
        Q + "australian-mbs-primary-history-20261115/reconciliation.json",
        "2f66de3dd1532fc22f9da0b973981d677f9ebb4f03a4c5482e93dfad8b3dbc43",
    ),
    "outside_dossiers": (
        Q + "australian-mbs-four-projection-dossiers-20261115.json",
        "0b3e7c53204695148b5b563e4bb7024cad421cc6cfa6ebf2c56f31af3a291d1e",
    ),
    "consumer": (
        Q + "australian-mbs-august-bounded-semantics-consumers-20261116.json",
        "476af6eb4b28a9a7328a77bf0809d960fee62789a4be7dbc8b702586af42cd58",
    ),
}
SCHEMA = "contracts/medallion/v4.1/federation.schema.json"
SCHEMA_SHA = "03acfbafd80daf0b8b768f7814dbb29a9bd13e7c9d5d68797b30261da29770c6"
UNKNOWN = "blocked_unknown_or_unqualified_privacy"
IDENTITY = ("dataset", "revision", "path", "sha256", "byte_count")
PBS_PATHS = 1722
PBS_LINKS = 316
PBS_MATCHED_LINKS = 312
PBS_CANDIDATE_OCCURRENCES = 313
PBS_DISTINCT_PATHS = 312
MBS_PROJECTIONS = 8
MBS_OUTSIDE = 4
MBS_REPLICA_REQUIRED = 2
PBS_EVENT_MATCHES = 1703
PBS_PREVIOUS_UNMATCHED = 19
PBS_API_MEMBERS = 33
PBS_PROFILED_ALIASES = 2
PBS_SCHEMA_PATHS = 5163


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _ref(name: str) -> dict[str, str]:
    path, digest = INPUTS[name]
    return {"path": path, "sha256": digest}


def _by_path(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output = {row["path"]: row for row in rows}
    _require(len(output) == len(rows), "duplicate path identity")
    return output


def projection_roles(e: dict[str, Any]) -> list[dict[str, Any]]:
    """Bind each prepared projection to historical restore and publication evidence."""
    dossiers = _by_path(e["dossiers"]["objects"])
    history = _by_path(e["primary_history"]["objects"])
    outside = _by_path(e["outside_dossiers"]["dossiers"])
    probes = _by_path(e["consumer"]["consumers"]["objects"])
    _require(
        len(dossiers) == MBS_PROJECTIONS
        and len(outside) == MBS_OUTSIDE
        and set(probes) == set(dossiers)
        and e["consumer"]["consumers"]["probe_kind"]
        == "synthetic_identity_only"
        and e["primary_history"]["summary"]["independent_recovery_established"]
        is False
        and e["primary_history"]["boundaries"]["historical_primary_only"]
        is True
        and e["consumer"]["boundaries"][
            "actual_admission_or_payload_consumer_canary"
        ]
        is False,
        "projection evidence scope differs",
    )
    output: list[dict[str, Any]] = []
    for path, item in sorted(dossiers.items()):
        prior = history.get(path)
        if prior is None:
            raise ValueError(
                "projection missing from historical restore reconciliation"
            )
        _require(
            all(prior[key] == item[key] for key in IDENTITY)
            and all(probes[path][key] == item[key] for key in IDENTITY)
            and probes[path]["prior_silver_admissions_rejected"] is True
            and probes[path]["rekeyed_silver_identity_rejected"] is True
            and prior["frozen_member"] is item["frozen_member"]
            and item["admission_ready"] is False
            and item["actual_admission"] == "not_performed"
            and item["privacy"]["scope"]
            == "source_profile_not_exhaustive_output_clearance"
            and item["lineage"]["field_semantics_accepted"] is False
            and item["independent_recovery_established"] is False,
            "projection identity or disposition differs",
        )
        frozen = item["frozen_member"]
        expected_history = (
            "exact_inventory_match" if frozen else "not_covered_by_this_receipt"
        )
        _require(
            prior["historical_primary_restore"] == expected_history,
            "primary restore scope differs",
        )
        prior_publication: dict[str, Any] | None = None
        if not frozen:
            older = outside.get(path)
            if older is None:
                raise ValueError(
                    "outside projection missing from prior dossier"
                )
            _require(
                all(older[key] == item[key] for key in IDENTITY)
                and older["producer"] == item["producer"]
                and older["historical_primary_digest_verification"]
                == "passed_for_manifest_and_its_objects"
                and older["output_privacy"]
                == "not_qualified_without_output_specific_evidence",
                "outside publication or privacy scope differs",
            )
            name = older["publication_receipt"]
            manifest_name = older["manifest"]
            publication = e["outside_references"][name]
            manifest = e["outside_references"][manifest_name]
            match = [
                entry for entry in manifest["objects"] if entry["path"] == path
            ]
            _require(
                len(match) == 1
                and match[0]["sha256"] == item["sha256"]
                and match[0]["bytes"] == item["byte_count"]
                and publication["manifest_sha256"]
                == e["outside_dossiers"]["inputs"][manifest_name]["sha256"]
                and publication["anonymous_digest_verification"] == "passed"
                and publication["workflow_commit"]
                == item["draft_components"]["producer_commit"],
                "outside publication identity differs",
            )
            prior_publication = {
                "receipt": e["outside_dossiers"]["inputs"][name],
                "manifest": e["outside_dossiers"]["inputs"][manifest_name],
                "historical_revision": publication["revision"],
                "workflow_run": publication["workflow_run"],
                "current_revision_evidence": item["draft_components"][
                    "verified_digest_receipt"
                ],
            }
        output.append({
            **{key: item[key] for key in IDENTITY},
            "producer": item["producer"],
            "frozen_member": frozen,
            "evidence_roles": {
                "source_lineage": {
                    "status": "source_event_b2_reference_and_receipt_bound",
                    "event": item["draft_components"]["source_event"],
                    "b2_reference": item["draft_components"][
                        "source_b2_reference"
                    ],
                    "receipt": item["draft_components"]["source_receipt"],
                    "reconstructed_later": item["draft_components"][
                        "source_metadata_reconstructed_later"
                    ],
                },
                "verification": {
                    "status": "prior_exact_revision_digest_receipt_not_v4_closure",
                    "evidence": item["draft_components"][
                        "verified_digest_receipt"
                    ],
                },
                "publication": {
                    "status": "historical_publication_bound_not_current_v4_role"
                    if prior_publication
                    else "prior_primary_inventory_not_original_publication",
                    "historical_outside_publication": prior_publication,
                },
                "rights": {
                    "status": item["rights"]["scope"],
                    "evidence": item["rights"]["evidence"],
                    "outside_attestation_is_prior_revision": item["rights"][
                        "outside_attestation_is_prior_revision"
                    ],
                },
                "privacy": {
                    "status": "output_not_cleared",
                    "source_profile": item["privacy"]["status"],
                    "evidence": item["privacy"]["evidence"],
                },
                "v1_conformance": "projection_specific_role_not_qualified",
                "v2_field_lineage": {
                    "status": "identity_bound_structural_candidate_not_v4_closure",
                    "evidence": item["lineage"]["field_lineage"],
                    "records": item["lineage"]["field_records"],
                },
                "v3_replay": {
                    "status": "registration_metadata_only_not_payload_replay",
                    "evidence": item["lineage"]["replay"],
                    "historical_reproduction": item["lineage"][
                        "historical_reproduction"
                    ],
                },
                "discovery": "exact_v4_role_not_qualified",
                "recovery": {
                    "historical_primary_restore": expected_history,
                    "evidence": _ref("primary_history"),
                    "independent_replica_established": False,
                    "replica_required_before_admission": item[
                        "independent_replica_required_before_admission"
                    ],
                },
                "cache": "exact_v4_role_not_qualified",
                "consumer": {
                    "offline_unadmitted_refusal": item["consumer"][
                        "unadmitted_reader_refusal"
                    ],
                    "actual_payload_canary": item["consumer"][
                        "actual_payload_canary"
                    ],
                    "evidence": _ref("consumer"),
                },
            },
            "contract_receipt_closure": "not_performed",
            "independently_trusted_admission": "not_performed",
        })
    _require(
        sum(row["frozen_member"] for row in output) == MBS_OUTSIDE
        and sum(
            row["evidence_roles"]["recovery"][
                "replica_required_before_admission"
            ]
            for row in output
        )
        == MBS_REPLICA_REQUIRED,
        "projection cohort differs",
    )
    return output


def pbs_schedule_privacy(
    privacy: dict[str, Any],
    crosswalk: dict[str, Any],
    context: dict[str, Any],
    member_triage: dict[str, Any],
) -> dict[str, Any]:
    """Join official-link candidates to privacy-blocked paths without clearing them."""
    rows = [
        row
        for row in privacy["objects"]
        if row["batch"].startswith(("pbs_", "reimbursement_"))
        and row["privacy"] == UNKNOWN
    ]
    by_identity = {tuple(row[key] for key in IDENTITY): row for row in rows}
    _require(
        len(rows) == len(by_identity) == PBS_PATHS, "PBS privacy cohort differs"
    )
    linked: dict[tuple[Any, ...], dict[str, Any]] = {}
    candidate_occurrences = 0
    matched_links = 0
    for link in crosswalk["links"]:
        candidates = link["candidates"]
        if link["identity_status"] == "unresolved":
            _require(not candidates, "unresolved link has candidates")
            continue
        _require(
            link["identity_status"] == "matched_exact_source_url"
            and candidates,
            "PBS link status differs",
        )
        matched_links += 1
        for candidate in candidates:
            candidate_occurrences += 1
            identity = tuple(candidate[key] for key in IDENTITY)
            item = by_identity.get(identity)
            if item is None:
                raise ValueError(
                    "PBS official link and privacy identity differ"
                )
            _require(
                candidate["payload_read_qualified"] is False
                and candidate["v4_admission"] == "not_performed"
                and item["privacy"] == UNKNOWN,
                "PBS privacy gate differs",
            )
            observed = candidate.get("observed_sensitivity")
            if candidate["dataset"] == "edithatogo/reimbursement-atlas":
                _require(
                    observed
                    == {
                        "data_sensitivity": "unknown",
                        "personal_data": "unknown",
                        "publication": "review_required",
                    },
                    "PBS source sensitivity metadata differs",
                )
            else:
                _require(
                    candidate["dataset"]
                    == "edithatogo/australian-pbs-source-archive"
                    and observed is None
                    and candidate.get("rights_conflict")
                    == "receipt_permitted_claim_source_ledger_unknown",
                    "PBS source privacy or rights context differs",
                )
            record = linked.setdefault(
                identity,
                {
                    **{key: item[key] for key in IDENTITY},
                    "batch": item["batch"],
                    "privacy": UNKNOWN,
                    "official_link_occurrences": [],
                    "payload_read_qualified": False,
                },
            )
            record["official_link_occurrences"].append({
                "url": link["url"],
                "format": link["format"],
                "effective_date": link["effective_date"],
                "identity_evidence": candidate["identity_evidence"],
                "prior_privacy_gate": candidate["privacy_gate"],
                "prior_sensitivity_metadata": candidate.get(
                    "observed_sensitivity"
                ),
                "prior_rights_conflict": candidate.get("rights_conflict"),
            })
    _require(
        len(crosswalk["links"]) == PBS_LINKS
        and matched_links == PBS_MATCHED_LINKS
        and candidate_occurrences == PBS_CANDIDATE_OCCURRENCES
        and len(linked) == PBS_DISTINCT_PATHS,
        "PBS official-link denominator differs",
    )
    april = context["april_2026"]
    aliases = {
        tuple(row[key] for key in IDENTITY) for row in april["archive_aliases"]
    }
    api = member_triage["september_2025_archive"]
    api_identity = tuple(api["identity"][key] for key in IDENTITY)
    _require(
        len(aliases) == PBS_PROFILED_ALIASES
        and aliases <= linked.keys()
        and april["member_schema_paths"] == PBS_SCHEMA_PATHS
        and api_identity in linked
        and len(api["members"]) == PBS_API_MEMBERS
        and all(row["privacy"] == UNKNOWN for row in api["members"])
        and context["boundaries"]["archive_privacy_cleared"] is False,
        "PBS member context identity differs",
    )
    for identity in aliases:
        linked[identity]["review_context"] = {
            "scope": "one_xml_member_schema_paths_not_complete_archive_values",
            "schema_paths": april["member_schema_paths"],
            "evidence": _ref("schema_context"),
        }
    linked[api_identity]["review_context"] = {
        "scope": "member_filenames_only_not_content",
        "members": len(api["members"]),
        "names_with_review_labels": api["members_with_review_labels"],
        "evidence": _ref("member_triage"),
    }
    return {
        "unassessed_cohort_paths": len(rows),
        "matched_link_occurrences": matched_links,
        "matched_candidate_occurrences": candidate_occurrences,
        "exact_linked_paths": len(linked),
        "remaining_paths_not_in_this_link_join": len(rows) - len(linked),
        "path_datasets": dict(
            sorted(Counter(row["dataset"] for row in linked.values()).items())
        ),
        "identity_scope": "exact_dataset_revision_path_digest_and_byte_count",
        "april_archive_aliases_with_one_member_schema_context": len(aliases),
        "september_api_archives_with_filename_triage": 1,
        "unmatched_does_not_mean_unpublished_or_no_other_evidence": True,
        "privacy_clearances_added": 0,
        "objects": sorted(linked.values(), key=itemgetter("dataset", "path")),
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    """Build a bounded report from retained, digest-pinned metadata."""
    evidence = {
        name: bounded.read_bound_metadata(root, *binding)
        for name, binding in INPUTS.items()
    }
    _require(
        preparation.build(root) == evidence["dossiers"],
        "prior projection preparation differs",
    )
    _require(
        hashlib.sha256((root / SCHEMA).read_bytes()).hexdigest() == SCHEMA_SHA,
        "v4 schema differs",
    )
    outside = evidence["outside_dossiers"]
    evidence["outside_references"] = {
        key: bounded.read_bound_metadata(root, ref["path"], ref["sha256"])
        for key, ref in outside["inputs"].items()
        if key
        in {
            "d781_publication",
            "d781_manifest",
            "f9f9_publication",
            "f9f9_manifest",
        }
    }
    _require(
        len(evidence["outside_references"]) == MBS_OUTSIDE,
        "outside references missing",
    )
    _require(
        evidence["pbs_coverage"]["matched"]["paths"] == PBS_EVENT_MATCHES
        and evidence["pbs_provenance"]["summary"]["prior_unmatched_paths"]
        == PBS_PREVIOUS_UNMATCHED
        and evidence["pbs_provenance"]["summary"]["privacy_clearances_added"]
        == 0
        and len(evidence["member_triage"]["september_2025_archive"]["members"])
        == PBS_API_MEMBERS,
        "PBS prior evidence scope differs",
    )
    return {
        "schema_id": "global-medicines-atlas.australian-existing-evidence-closure",
        "schema_version": 1,
        "recorded_on": "2026-11-16",
        "inputs": {name: _ref(name) for name in INPUTS},
        "v4_schema": {"path": SCHEMA, "sha256": SCHEMA_SHA},
        "mbs_projections": projection_roles(evidence),
        "pbs_schedule_privacy": pbs_schedule_privacy(
            evidence["privacy"],
            evidence["pbs_links"],
            evidence["schema_context"],
            evidence["member_triage"],
        ),
        "recovery": {
            "four_frozen_projection_identities_in_historical_primary_restore": 4,
            "four_outside_projections_not_covered_by_that_receipt": 4,
            "independent_recovery_established": False,
            "prior_restore_replayed_in_this_work": False,
        },
        "boundaries": {
            "participant_or_cohort_data_accessed": False,
            "source_or_projection_payload_read": False,
            "dataset_acquired_or_published": False,
            "privacy_or_rights_decision_changed": False,
            "v4_receipt_closure_or_admission_performed": False,
            "actual_consumer_canary_performed": False,
            "independent_recovery_established": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), sort_keys=True, indent=2) + "\n").encode()
    path = ROOT / OUTPUT
    if args.check:
        _require(
            path.is_file() and path.read_bytes() == raw,
            "existing-evidence report differs",
        )
    else:
        path.write_bytes(raw)
    print(
        "Reconciled retained admission, privacy and recovery metadata; no payload read"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
