"""Join retained MBS B1/B2 records to the frozen M-112 object inventory."""

from __future__ import annotations

import copy
import hashlib
import json
from operator import itemgetter
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
QUAL = ROOT / "quality/qualifications"
BASELINE_PATH = "quality/qualifications/australian-m112-per-object-gate-reconciliation-20261018.json"
TREE_IDENTITY_PATH = "quality/qualifications/australian-m112-current-tree-object-identity-reconciliation-20261004.json"
RAW_B2_PATH = "quality/qualifications/australian-m112-raw-b2-metadata-reconciliation-20261018.json"
UTILISATION_PATH = "quality/qualifications/australian-m112-utilisation-digest-reconciliation-20261004.json"
SOURCE_ARCHIVE_PATH = "quality/qualifications/australian-m112-source-archive-digest-reconciliation-20261004.json"
MANIFEST_JOIN_PATH = (
    "quality/qualifications/australian-m112-manifest-join-audit-20260930.json"
)
FROZEN_INVENTORY_PATH = "quality/qualifications/australian-m112-frozen-object-inventory-20261018.json"
OUTPUT = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261018-retained-joins.json"
)
EXPECTED_DENOMINATOR = 1759
EXPECTED_PATH_MEMBERSHIP_SHA256 = (
    "fe48d50a105a5dc34720d4d0176d28b442d79f4d53b1f10ba738e0745ef0208b"
)
EXPECTED_RAW_PATHS = 1736
EXPECTED_PROJECTIONS = 23
EXPECTED_PRIOR_RAW_DIGEST_JOINS = 22
EXPECTED_NEW_MBS_JULY_JOINS = 4
EXPECTED_MBS_CANDIDATE_PATHS = 6
EXPECTED_MBS_RECEIPT_ROLES = 5
EXPECTED_PRIOR_MBS_CANDIDATE_PATHS = 2
EXPECTED_PRIOR_RAW_TREE_SHA_GAPS = 102
EXPECTED_BASE_COMPLETE_LINEAGES = 2
EXPECTED_CURRENT_COMPLETE_LINEAGES = 6
EXPECTED_PRIOR_EXACT_SOURCE_RIGHTS = 2
MBS_DATASET = "edithatogo/australian-mbs-source-archive"
MBS_CURRENT_REVISION = "40891976f77ee5e7688edceed25c9ac98a77547e"
MBS_METADATA_READBACK_REVISION = "42d73b6facac016f14a335d36d83f1a3b630add8"
_OBJECT_KEY = itemgetter("dataset", "revision", "path")


def _read_json(path: str) -> dict[str, Any]:
    value: object = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast("dict[str, Any]", value)


def _input_binding(path: str) -> dict[str, str]:
    return {
        "path": path,
        "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
    }


def _object_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return cast("tuple[str, str, str]", _OBJECT_KEY(row))


def _denominator_digest(objects: list[dict[str, Any]]) -> str:
    rows = sorted(_object_key(row) for row in objects)
    body = "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        for row in rows
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _path_membership_digest(objects: list[dict[str, Any]]) -> str:
    keys = sorted((row["dataset"], row["path"]) for row in objects)
    body = "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        for row in keys
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def build_report() -> dict[str, Any]:  # ruff: ignore[too-many-locals,too-many-branches,too-many-statements] -- keep each retained-evidence gate auditable in one deterministic qualification
    """Build a small evidence overlay and updated 1,759-row inventory."""
    baseline = _read_json(BASELINE_PATH)
    frozen_inventory = _read_json(FROZEN_INVENTORY_PATH)
    tree_identity = _read_json(TREE_IDENTITY_PATH)
    raw_b2 = _read_json(RAW_B2_PATH)
    utilisation = _read_json(UTILISATION_PATH)
    source_archive = _read_json(SOURCE_ARCHIVE_PATH)
    manifest_join = _read_json(MANIFEST_JOIN_PATH)

    source_objects = cast("list[dict[str, Any]]", baseline["objects"])
    if len(source_objects) != EXPECTED_DENOMINATOR:
        raise ValueError("the frozen M-112 denominator changed")
    denominator_digest = _denominator_digest(source_objects)
    path_membership_digest = _path_membership_digest(source_objects)
    frozen_path_keys = {
        (row["dataset"], row["path"])
        for row in cast("list[dict[str, Any]]", frozen_inventory["members"])
    }
    if (
        path_membership_digest != EXPECTED_PATH_MEMBERSHIP_SHA256
        or frozen_inventory["scope"]["path_membership_sha256"]
        != EXPECTED_PATH_MEMBERSHIP_SHA256
        or frozen_path_keys
        != {(row["dataset"], row["path"]) for row in source_objects}
    ):
        raise ValueError("the frozen M-112 path membership changed")
    baseline_complete_lineages = sum(
        row["b1_b2_lineage"]["complete"] for row in source_objects
    )
    if baseline_complete_lineages != EXPECTED_BASE_COMPLETE_LINEAGES:
        raise ValueError("the base B1/B2 lineage count changed")
    rows = copy.deepcopy(source_objects)
    rows_by_key = {_object_key(row): row for row in rows}
    if len(rows_by_key) != EXPECTED_DENOMINATOR:
        raise ValueError("the frozen M-112 object keys are not unique")
    if baseline["scope"]["approved_raw_paths"] != EXPECTED_RAW_PATHS or (
        baseline["scope"]["approved_projection_paths"] != EXPECTED_PROJECTIONS
    ):
        raise ValueError("the approved M-112 source strata changed")

    prior_objects = [
        *cast("list[dict[str, Any]]", utilisation["verified_objects"]),
        *cast("list[dict[str, Any]]", source_archive["verified_objects"]),
    ]
    prior_keys = {
        (row["dataset"], row["revision"], row["path"]) for row in prior_objects
    }
    if len(prior_objects) != EXPECTED_PRIOR_RAW_DIGEST_JOINS or len(
        prior_keys
    ) != len(prior_objects):
        raise ValueError("the previous 22 raw digest/path match set changed")

    tree_section = tree_identity["additional_anonymous_raw_byte_hashes"]
    tree_dataset = tree_section["dataset"]
    tree_revision = tree_section["revision"]
    tree_objects = cast("list[dict[str, Any]]", tree_section["objects"])
    tree_by_path = {row["path"]: row for row in tree_objects}
    if (
        tree_revision != MBS_CURRENT_REVISION
        or len(tree_by_path) != EXPECTED_NEW_MBS_JULY_JOINS
    ):
        raise ValueError("the retained current-revision MBS hash set changed")

    candidate_objects = cast("list[dict[str, Any]]", raw_b2["candidate_paths"])
    candidate_by_path = {
        row["path"]: row
        for row in candidate_objects
        if row["dataset"] == MBS_DATASET
    }
    role_rows = cast(
        "list[dict[str, Any]]",
        raw_b2["metadata_bindings"]["july_path_level_b1_b2_joins"],
    )
    role_by_path = {row["path"]: row for row in role_rows}
    if (
        len(candidate_objects) != EXPECTED_MBS_CANDIDATE_PATHS
        or len(role_by_path) != EXPECTED_NEW_MBS_JULY_JOINS
    ):
        raise ValueError("the retained six-path MBS candidate set changed")

    input_bindings = {
        path: _input_binding(path)
        for path in (
            BASELINE_PATH,
            TREE_IDENTITY_PATH,
            RAW_B2_PATH,
            UTILISATION_PATH,
            SOURCE_ARCHIVE_PATH,
            MANIFEST_JOIN_PATH,
            FROZEN_INVENTORY_PATH,
        )
    }
    new_joins: list[dict[str, Any]] = []
    for path, role_row in sorted(role_by_path.items()):
        candidate = candidate_by_path[path]
        tree_row = tree_by_path[path]
        dataset_revision = tree_row["revision"]
        current_key = (MBS_DATASET, dataset_revision, path)
        inventory_row = rows_by_key.get(current_key)
        if inventory_row is None:
            raise ValueError(
                "MBS source object is not in the frozen denominator"
            )
        if current_key in prior_keys:
            raise ValueError("new July MBS join overlaps the prior 22 paths")

        sha256 = candidate["sha256"]
        byte_count = candidate["bytes"]
        role_matches = cast("dict[str, bool]", role_row["role_matches"])
        identity_claims_match = all((
            candidate["revision"] == MBS_METADATA_READBACK_REVISION,
            tree_dataset == MBS_DATASET,
            tree_row["revision"] == MBS_CURRENT_REVISION,
            tree_row["expected_bytes"] == byte_count,
            tree_row["observed_bytes"] == byte_count,
            tree_row["expected_sha256"] == sha256,
            tree_row["observed_sha256"] == sha256,
            tree_row["sha256_match"] is True,
            role_row["bytes"] == byte_count,
            role_row["sha256"] == sha256,
            all(value is True for value in role_matches.values()),
            len(role_matches) == EXPECTED_MBS_RECEIPT_ROLES,
            inventory_row["candidate_class"] == "raw_source_payload",
            inventory_row["identity"]["byte_count"] == byte_count,
        ))
        if not identity_claims_match:
            raise ValueError(
                "retained MBS object identities or B1/B2 roles differ"
            )

        identity = inventory_row["identity"]
        identity["sha256"] = sha256
        identity["sha256_evidence"] = "anonymous_digest_readback"
        identity["anonymous_digest_readback"] = True
        identity["digest_evidence"] = input_bindings[TREE_IDENTITY_PATH]

        inventory_row["b1_b2_lineage"] = {
            "complete": True,
            "state": (
                "Current-revision raw object digest and byte count match the "
                "retained anonymous hash; the same path and content digest "
                "join to the July B1/B2 source receipt, acquisition, B2 "
                "reference, and landed unreviewed admission. The metadata "
                "receipt revision is retained separately from the current "
                "producer revision. This does not admit the object to v4."
            ),
            "evidence": input_bindings[RAW_B2_PATH],
            "current_tree_evidence": input_bindings[TREE_IDENTITY_PATH],
            "metadata_receipt_revision": candidate["revision"],
            "current_dataset_revision": dataset_revision,
            "acquisition_id": role_row["acquisition_id"],
            "b2_locator_revision": role_row["b2_locator_revision"],
            "receipt_roles": role_matches,
        }
        if inventory_row["v4_admission"] or inventory_row["consumer_canary"]:
            raise ValueError("an existing M-112 candidate was already promoted")
        inventory_row["preserved_deferral_group"] = (
            "au-mbs-july-2026-raw-object-paths"
        )
        inventory_row["rights"]["state"] = (
            "Maintainer authorization covers the source/category/domain; "
            "exact per-object authorization and reuse disposition remain "
            "unresolved. Complete B1/B2 lineage is recorded separately and "
            "does not establish rights or v4 eligibility."
        )
        new_joins.append({
            "dataset": MBS_DATASET,
            "dataset_revision": dataset_revision,
            "metadata_receipt_revision": candidate["revision"],
            "path": path,
            "byte_count": byte_count,
            "sha256": sha256,
            "same_path_byte_count_and_sha256": True,
            "preserved_denominator_member": True,
            "acquisition_id": role_row["acquisition_id"],
            "b2_locator_revision": role_row["b2_locator_revision"],
            "all_b1_b2_roles_match": True,
            "receipt_roles": role_matches,
            "v4_admission": False,
            "consumer_canary": False,
        })

    if len(new_joins) != EXPECTED_NEW_MBS_JULY_JOINS:
        raise ValueError("expected four new exact MBS raw-object joins")
    prior_mbs_candidate_paths = [
        row for row in candidate_objects if row["path"] not in role_by_path
    ]
    if len(prior_mbs_candidate_paths) != EXPECTED_PRIOR_MBS_CANDIDATE_PATHS:
        raise ValueError("the two August MBS candidate paths changed")
    alias_evidence = tree_identity["digest_coverage"]["alias"]
    alias_path = alias_evidence["path"]
    canonical_path = alias_evidence["sha256_evidence_path"]
    canonical_already_joined = False
    alias_already_bound = False
    for candidate in prior_mbs_candidate_paths:
        key = (
            candidate["dataset"],
            candidate["revision"],
            candidate["path"],
        )
        inventory_row = rows_by_key.get(key)
        if inventory_row is None:
            raise ValueError(
                "an August MBS candidate is outside the denominator"
            )
        if (
            candidate["bytes"] != inventory_row["identity"]["byte_count"]
            or candidate["sha256"] != inventory_row["identity"]["sha256"]
            or inventory_row["b1_b2_lineage"]["complete"] is not True
        ):
            raise ValueError(
                "an August MBS candidate no longer joins its receipt"
            )
        if candidate["path"] == canonical_path:
            if key not in prior_keys:
                raise ValueError(
                    "canonical August path left the prior 22 joins"
                )
            canonical_already_joined = True
        elif candidate["path"] == alias_path:
            if key in prior_keys:
                raise ValueError(
                    "the August alias was counted as a receipt path"
                )
            if (
                inventory_row["identity"]["git_blob_oid"]
                != alias_evidence["same_current_git_blob_oid"]
                or inventory_row["identity"]["byte_count"]
                != alias_evidence["same_byte_count"]
                or candidate["sha256"]
                != alias_evidence["sha256_from_verified_path"]
            ):
                raise ValueError("the August alias identity binding changed")
            alias_already_bound = True
        else:
            raise ValueError("unexpected August MBS candidate path")
    if not canonical_already_joined or not alias_already_bound:
        raise ValueError(
            "the canonical and alias August paths were not distinguished"
        )
    candidate_path_results = [
        {
            "dataset": row["dataset"],
            "candidate_revision": row["revision"],
            "path": row["path"],
            "status": (
                "verified_new_b1_b2_receipt_join"
                if row["path"] in role_by_path
                else "preexisting_same_content_alias"
                if row["path"] == alias_path
                else "preexisting_canonical_b1_b2_join"
            ),
        }
        for row in candidate_objects
    ]
    cumulative_keys = prior_keys | {
        (join["dataset"], join["dataset_revision"], join["path"])
        for join in new_joins
    }
    if len(cumulative_keys) != EXPECTED_PRIOR_RAW_DIGEST_JOINS + len(new_joins):
        raise ValueError("the cumulative raw-object join keys are not unique")

    complete_lineages = sum(row["b1_b2_lineage"]["complete"] for row in rows)
    exact_source_rights = baseline["aggregate_gates"][
        "paths_with_exact_source_release_rights"
    ]
    tree_gaps = tree_identity["digest_coverage"]
    scope = copy.deepcopy(baseline["scope"])

    manifest_observations = cast(
        "list[dict[str, Any]]", manifest_join["manifest_observations"]
    )
    prior_missing_sha = sum(
        row["tree_sha256_unavailable_count"] for row in manifest_observations
    ) + sum(
        len(row["candidate_paths_missing_from_manifest"])
        for row in manifest_observations
    )
    if prior_missing_sha != EXPECTED_PRIOR_RAW_TREE_SHA_GAPS:
        raise ValueError("the prior 102 raw tree-SHA gap count changed")
    remaining_raw_without_sha = tree_gaps[
        "remaining_non_lfs_raw_paths_without_digest_evidence"
    ]
    remaining_projection_without_sha = tree_gaps[
        "remaining_projection_paths_without_digest_evidence"
    ]
    recovered_tree_gap_count = prior_missing_sha - remaining_raw_without_sha

    report = {
        "schema_id": "global-medicines-atlas.m112-retained-evidence-object-joins",
        "schema_version": 1,
        "observed_at": "2026-10-18",
        "purpose": (
            "Join four retained July MBS B1/B2 receipt chains to their "
            "same-path, same-size, same-SHA objects at the frozen current "
            "producer revision without changing the approved denominator."
        ),
        "scope": scope,
        "denominator_object_id_sha256": denominator_digest,
        "approved_path_membership_sha256": path_membership_digest,
        "evidence_inputs": list(input_bindings.values()),
        "retained_evidence_join_increment": {
            "denominator_object_count": len(rows),
            "denominator_object_id_sha256": denominator_digest,
            "approved_path_membership_sha256": path_membership_digest,
            "prior_raw_digest_path_joins": len(prior_keys),
            "new_exact_raw_digest_path_matches": len(new_joins),
            "new_exact_b1_b2_receipt_joins": len(new_joins),
            "cumulative_exact_raw_digest_path_joins": len(cumulative_keys),
            "raw_paths_outside_digest_join_subset": EXPECTED_RAW_PATHS
            - len(cumulative_keys),
            "prior_complete_b1_b2_lineage_paths": EXPECTED_BASE_COMPLETE_LINEAGES,
            "new_complete_b1_b2_lineage_paths": len(new_joins),
            "cumulative_complete_b1_b2_lineage_paths": complete_lineages,
            "existing_same_content_alias_path_bindings": 1,
            "cumulative_raw_path_identity_bindings": len(cumulative_keys) + 1,
            "candidate_path_disposition": {
                "verified_new_join": 4,
                "already_joined_canonical": 1,
                "same_content_alias_already_bound": 1,
                "unmatched": 0,
                "incompatible_role": 0,
            },
            "candidate_path_results": candidate_path_results,
            "unmatched_records": [],
            "incompatible_role_records": [],
            "raw_path_records_outside_exact_digest_join_subset": (
                EXPECTED_RAW_PATHS - len(cumulative_keys)
            ),
            "outside_subset_interpretation": (
                "These 1,710 raw paths are not among the 26 exact prior-plus-new "
                "digest/path matches summarized here. This digest-match subset "
                "is not a B1/B2 receipt count: two path lineages were complete "
                "before this increment and four are added here. Per-object "
                "identity, rights, and lineage states remain in the preserved "
                "1,759-member inventory."
            ),
            "existing_alias_binding": {
                "path": alias_path,
                "canonical_path": canonical_path,
                "sha256": alias_evidence["sha256_from_verified_path"],
                "byte_count": alias_evidence["same_byte_count"],
                "same_git_blob_oid": alias_evidence[
                    "same_current_git_blob_oid"
                ],
                "independent_b1_b2_acquisition_count": 0,
                "interpretation": "path-specific content identity is already bound through the canonical payload; it is not counted as a new source receipt join",
            },
            "new_joins": new_joins,
            "tree_sha_gap_reconciliation": {
                "prior_raw_tree_sha_unavailable": prior_missing_sha,
                "current_raw_paths_without_direct_or_alias_sha256": (
                    remaining_raw_without_sha
                ),
                "raw_paths_resolved_by_existing_non_lfs_or_alias_evidence": (
                    recovered_tree_gap_count
                ),
                "new_july_mbs_hashes_included_in_current_inventory": len(
                    new_joins
                ),
                "projection_paths_without_direct_or_alias_sha256": (
                    remaining_projection_without_sha
                ),
                "interpretation": (
                    "The older 102 count measures missing current-tree LFS "
                    "SHA values among raw paths. The current evidence adds "
                    "existing hosted non-LFS and same-Git-object bindings; "
                    "92 raw paths still lack direct or alias SHA evidence. "
                    "Twelve projection paths remain separately unbound."
                ),
            },
        },
        "updated_gate_totals": {
            "approved_denominator": len(rows),
            "raw_paths": EXPECTED_RAW_PATHS,
            "projection_paths": EXPECTED_PROJECTIONS,
            "complete_raw_b1_b2_lineage": complete_lineages,
            "exact_raw_digest_path_joins": len(cumulative_keys),
            "complete_raw_b1_b2_lineage_paths": complete_lineages,
            "including_existing_same_content_alias": len(cumulative_keys) + 1,
            "exact_source_release_rights": exact_source_rights,
            "v4_admissions": 0,
            "consumer_canaries": 0,
            "preserved_deferrals": scope["preserved_deferrals"],
            "raw_paths_without_direct_or_alias_sha256": (
                remaining_raw_without_sha
            ),
            "projection_paths_without_direct_or_alias_sha256": (
                remaining_projection_without_sha
            ),
        },
        "boundaries": {
            "denominator_changed": False,
            "source_payload_bytes_read_this_run": False,
            "new_source_or_dataset_added": False,
            "rights_or_licensing_conclusion_added": False,
            "v4_admission_performed": False,
            "consumer_canary_performed": False,
            "all_denominator_deferrals_preserved": True,
            "source_owner_pbs_m107_and_july_derivative_modified": False,
        },
        "objects": rows,
    }
    if (
        len(rows) != EXPECTED_DENOMINATOR
        or len({_object_key(row) for row in rows}) != EXPECTED_DENOMINATOR
        or _denominator_digest(rows) != denominator_digest
        or exact_source_rights != EXPECTED_PRIOR_EXACT_SOURCE_RIGHTS
        or complete_lineages != EXPECTED_CURRENT_COMPLETE_LINEAGES
    ):
        raise ValueError("the retained-evidence overlay changed an invariant")
    return report


def main() -> None:
    OUTPUT.write_text(
        json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
