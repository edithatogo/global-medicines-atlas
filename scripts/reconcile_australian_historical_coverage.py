"""Reconcile retained Australian archive and publisher-index metadata offline.

The caller supplies previously captured Hub manifest/tree metadata. This tool
never requests or reads a source payload and does not infer period completeness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from operator import itemgetter
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded

from global_medicines_atlas.strict_json import unique_json_object

ROOT = Path(__file__).resolve().parents[1]
Q = "quality/qualifications/"
OUTPUT = Q + "australian-historical-coverage-reconciliation-20261116.json"
PBS_DATASET = "edithatogo/australian-pbs-utilisation-archive"
PBS_REVISION = "ba60e1d18b81e4af3cae50bc9fbfe719406fa5f3"
MBS_DATASET = "edithatogo/australian-mbs-source-archive"
MBS_OLD = "da83cad9116e2f9a5b927be7b080e9a5e5ea6998"
MBS_CURRENT = "b925a8a80b0f90db09513e7ce1378045461b05c0"
MBS_UTILISATION = "edithatogo/australian-mbs-utilisation-archive"
MBS_UTILISATION_REVISION = "05342df7dd2f92fe6e85e28e8add9bf3f43d0389"
REIMBURSEMENT_REVISION = "8c75366a5d5fbf72cdde1d9f83e6f1cbaef7a338"
PBS_API_MEMBERS = 33
KEY_OBJECTS = 11
PBS_DISCOVERED = 505
PBS_ADDITIONAL_AUTHORIZED = 120
PBS_PAYLOAD_PATHS = 508
PBS_MULTI_PATH_RESOURCES = 3
MBS_XML_LINKS = 82
MBS_XML_PAGES = 41
MBS_PDF_YEAR_LINKS = 119
MBS_PDF_PREVIOUS_LINKS = 105
MBS_PDF_DISTINCT_URLS = 218
PBS_SCHEDULE_LINKS = 316
PBS_SCHEDULE_MATCHES = 312
PBS_SCHEDULE_UNMATCHED = 4
MEDICARE_ANNUAL_YEARS = 17
DERIVED_WORKBOOK_OUTPUTS = 91
MEMBER_DIGESTS = (
    "137c650b41ad1278b06619c35a81fa748a805562ab91ebb837d22a4ae81a362f",
    "c82be4b3afb26507b2295df24a02807aa413a3d660ae8331d844bbd58572d9fd",
    "764c2fa382fc400b7f2708e81faf595e868eece73c157e68a2b458d07411b053",
    "67e6f64a3e2b83c0b1dd1de3eaa985c607ffb342400576d4172c8ae5162deb3d",
    "8bcd70f416c6aa0a0d19243f4d5d627785e8766d1b82258ecc90e57f09b8a3ff",
    "bdd5747a13cb59e92f996cf61c93e873bc0ec5fa4713ca34e635cea5814ac26e",
)
INPUTS = {
    "pbs_discovery": (
        Q + "australian-pbs-backfill-discovery-20261105.json",
        "74a585d398df8345b5389919ad29766f2a40213ba200910447695f24f095f0bb",
    ),
    "pbs_authorized": (
        Q + "australian-pbs-backfill-authorized-resources-20261105.json",
        "952ddcbda4edcb16a38999cae899283fc56ac5d6b4076e4a1d711f9da21179e6",
    ),
    "archive_comparison": (
        Q + "australian-public-archive-reconciliation-20261113.json",
        "f7883925fe095e46b184690e966101b10b8dcec2326e03d93cb5b18c1e3b5fcf",
    ),
    "archive_receipt": (
        Q
        + "australian-federation-existing-archive-reconciliation-20261115.json",
        "56a5ce1467b8ecabd0ef6dbad744145087fb2138c9c277250764d3025f38610b",
    ),
    "aihw_publication": (
        Q + "aihw-atc2-publication-20261114-43565582684.json",
        "52629a8adfe4bd73dfb63b535ca9f81774245735a843d676aebec24a19926f10",
    ),
    "aihw_contract": (
        Q + "aihw-pbs-atc2-monthly-public-20261113.json",
        "60212130806bd5d75481fcc94635ad78fc05d11379140f58166509175140fcf2",
    ),
    "mbs_index": (
        Q + "australian-mbs-official-index-reconciliation-20261017.json",
        "9f6ac27b6d967e704c90ac2105ea1e8e22a0a6ea750e4157f596e8ebd4a606dd",
    ),
    "annual": (
        Q + "mbs-annual-public-workbook-qualification-20261115.json",
        "0e1ee83e51cddd913a6b8955b5149738024f7a7de27e82eb495e2b8e113a1194",
    ),
    "age": (
        Q + "mbs-dec1993-age-band-reconciliation.json",
        "f56dde2971f8dfdae54cadbd5b08e283379532e66823ce9594ace20e273120d3",
    ),
    "atc_teaching": (
        Q + "historical-atc2-attribution-20261106.json",
        "90dc95b1c30dbb5661dbcb0a1851e8ec4217da8fdeb6e42523fda70791a683b7",
    ),
    "pbs_schedule": (
        Q + "australian-pbs-m107-existing-archive-crosswalk-20261115.json",
        "5850ad0f315bedf03971c9811f9ac12d9fb9fbaf77e72fd710cbac1d4ce5fcd9",
    ),
    "workbook_cohort": (
        Q
        + "mbs-historical-workbook-cohort-20261023-39724026209-39891918206.json",
        "3bbcc74fee209cee521ce6ee85ef87f3ed13df2d202cb1f96effb02274b48546",
    ),
    "historical_pdf": (
        Q + "australian-mbs-m107-historical-pdf-crosswalk-20261018.json",
        "a7432dc5764027556e7e7c7a219ccd9698cf76cef770b7b9e714a081c4e6aa36",
    ),
    "previous_downloads": (
        Q + "australian-mbs-m107-previous-downloads-crosswalk-20261018.json",
        "4292131db8eee9d96d5b5b6ccc599fad953a9fe54cb6c7b2871e2872aafe1fc0",
    ),
    "aihw_historical": (
        Q + "remaining-public-archives-20261106.json",
        "296fb3f89bcbd4b9f6bc411e45f6a7a8e8113376518b479b219095e865425d24",
    ),
} | {
    f"mbs_member_{index}": (
        Q + f"mbs-historical-archive-members-{index}-20261022-39678641506.json",
        digest,
    )
    for index, digest in enumerate(MEMBER_DIGESTS)
}


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _index(
    rows: list[dict[str, Any]], key: str = "path"
) -> dict[str, dict[str, Any]]:
    result = {row[key]: row for row in rows}
    _require(len(rows) == len(result), "duplicate metadata identity")
    return result


def _tree_check(
    entry: dict[str, Any], tree: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    item = tree.get(entry["path"])
    if item is None:
        raise ValueError("archive tree object missing")
    _require(
        type(entry["bytes"]) is int
        and entry["bytes"] >= 0
        and item["size"] == entry["bytes"]
        and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) is not None
        and re.fullmatch(r"[0-9a-f]{40}", item["git_oid"]) is not None,
        "archive tree identity differs",
    )
    lfs = item["lfs_sha256"]
    _require(
        lfs is None or lfs == entry["sha256"], "archive LFS digest differs"
    )
    return {
        "git_oid": item["git_oid"],
        "method": "lfs_sha256_and_size" if lfs else "git_blob_and_size",
    }


def match_pbs_resources(
    resources: list[dict[str, Any]],
    manifest: list[dict[str, Any]],
    tree_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join discovered resources to manifest payloads, sidecars and tree metadata."""
    files = _index(manifest)
    tree = _index(tree_rows)
    _require(
        len({row["url"] for row in resources}) == len(resources)
        and len({row["archive_path"] for row in resources}) == len(resources),
        "duplicate discovery identity",
    )
    results: list[dict[str, Any]] = []
    used: set[str] = set()
    for resource in resources:
        prefix, filename = resource["archive_path"].rsplit("/", 1)
        _require(
            filename == resource["filename"] and prefix.startswith("raw/pbs/"),
            "discovery path differs",
        )
        candidates = [
            item
            for item in manifest
            if item["kind"] == "raw_payload"
            and item["source_id"] == resource["source_id"]
            and item["path"]
            in {
                resource["archive_path"],
                f"{prefix}/versions/{item['sha256']}/{filename}",
            }
        ]
        _require(candidates, "discovered resource unmatched in manifest")
        matches: list[dict[str, Any]] = []
        for item in sorted(candidates, key=itemgetter("path")):
            receipt_path = "bronze/" + item["path"][4:] + ".receipt.json"
            receipt = files.get(receipt_path)
            if receipt is None:
                raise ValueError("paired receipt missing")
            _require(
                receipt["kind"] == "b1_receipt"
                and receipt["source_id"] == item["source_id"],
                "paired receipt missing or differs",
            )
            payload_check = _tree_check(item, tree)
            receipt_check = _tree_check(receipt, tree)
            _require(
                item["path"] not in used and receipt_path not in used,
                "archive object mapped twice",
            )
            used.update((item["path"], receipt_path))
            matches.append({
                "path": item["path"],
                "sha256": item["sha256"],
                "byte_count": item["bytes"],
                "payload_git_oid": payload_check["git_oid"],
                "payload_tree_check": payload_check["method"],
                "receipt_path": receipt_path,
                "receipt_sha256": receipt["sha256"],
                "receipt_bytes": receipt["bytes"],
                "receipt_git_oid": receipt_check["git_oid"],
                "receipt_tree_check": receipt_check["method"],
                "receipt_content_checked": False,
            })
        results.append({
            "source_id": resource["source_id"],
            "category": resource["category"],
            "url": resource["url"],
            "period_label": resource["period_label"],
            "discovered_archive_path": resource["archive_path"],
            "match_status": "matched_manifest_and_tree",
            "matches": matches,
        })
    _require(set(tree) == used, "selected archive tree set differs")
    return results


def match_mbs_resources(
    resources: list[dict[str, Any]],
    current: list[dict[str, Any]],
    previous: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compare existing MBS XML and receipt Git identities at two revisions."""
    now, old = _index(current), _index(previous)
    used: set[str] = set()
    output: list[dict[str, Any]] = []
    for resource in resources:
        pairs = resource["matching_archive_receipts"]
        _require(
            resource["current_archive_receipt"] is True and len(pairs) == 1,
            "MBS source receipt differs",
        )
        pair = pairs[0]
        for field in ("archive_path", "receipt_path"):
            object_path = pair[field]
            _require(
                object_path not in used
                and object_path in now
                and object_path in old,
                "MBS tree object missing or duplicated",
            )
            a, b = now[object_path], old[object_path]
            _require(
                a["size"] == b["size"]
                and a["git_oid"] == b["git_oid"]
                and re.fullmatch(r"[0-9a-f]{40}", a["git_oid"]) is not None
                and a["lfs_sha256"] == b["lfs_sha256"]
                and (
                    a["lfs_sha256"] is None
                    or field != "archive_path"
                    or a["lfs_sha256"] == pair["payload_sha256"]
                ),
                "MBS tree identity differs",
            )
            used.add(object_path)
        output.append({
            "source_url": resource["source_url"],
            "page_label": resource["page_label"],
            "archive_path": pair["archive_path"],
            "receipt_path": pair["receipt_path"],
            "receipt_recorded_payload_sha256": pair["payload_sha256"],
            "payload_git_oid": now[pair["archive_path"]]["git_oid"],
            "payload_bytes": now[pair["archive_path"]]["size"],
            "receipt_git_oid": now[pair["receipt_path"]]["git_oid"],
            "same_git_objects_and_sizes_at_both_revisions": True,
        })
    _require(set(now) == set(old) == used, "MBS tree cohort differs")
    return output


def _read_json(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    _require(len(raw) <= bounded.MAX_JSON_BYTES, "metadata byte limit exceeded")
    result = json.loads(raw, object_pairs_hook=unique_json_object)
    _require(isinstance(result, dict), "metadata object differs")
    return result


def _key_objects(
    e: dict[str, Any], snapshot: dict[str, Any]
) -> list[dict[str, Any]]:
    """Bind eleven selected tree observations to pre-existing exact receipts."""
    expected: list[dict[str, Any]] = []
    for index in range(len(MEMBER_DIGESTS)):
        result = e[f"mbs_member_{index}"]["result"]
        _require(
            result["container_integrity_verified"] is True
            and result["native_values_or_names_emitted"] is False,
            "MBS archive member evidence differs",
        )
        expected.append({
            "dataset": MBS_UTILISATION,
            "revision": MBS_UTILISATION_REVISION,
            "path": result["source_path"],
            "sha256": result["source_sha256"],
            "size": result["source_bytes"],
        })
    annual = e["annual"]["source"]
    _require(
        annual["dataset"] == MBS_UTILISATION
        and annual["revision"] == MBS_UTILISATION_REVISION,
        "annual workbook identity differs",
    )
    expected.append({
        "dataset": annual["dataset"],
        "revision": annual["revision"],
        "path": annual["raw_path"],
        "sha256": annual["sha256"],
        "size": annual["byte_count"],
    })
    archived = e["archive_comparison"]["pbs_atc2_utilisation"]
    for key in ("teaching_csv", "aihw_historical_workbook"):
        item = archived[key]
        _require(
            item["dataset"] == PBS_DATASET,
            "PBS historical object dataset differs",
        )
        expected.append({
            "dataset": PBS_DATASET,
            "revision": PBS_REVISION,
            "path": item["path"],
            "sha256": item["sha256"],
            "size": item["bytes"],
        })
    monthly = e["aihw_contract"]["archives"]["pbs"]["files"][0]
    expected.append({
        "dataset": PBS_DATASET,
        "revision": PBS_REVISION,
        "path": monthly["resource"]["archive_path"],
        "sha256": monthly["sha256"],
        "size": monthly["bytes"],
    })
    schedule = e["archive_comparison"]["pbs_schedule_api"]
    _require(
        schedule["revision"] == REIMBURSEMENT_REVISION
        and len(schedule["members"]) == PBS_API_MEMBERS,
        "PBS API snapshot differs",
    )
    expected.append({
        "dataset": schedule["dataset"],
        "revision": schedule["revision"],
        "path": schedule["path"],
        "sha256": schedule["sha256"],
        "size": schedule["bytes"],
    })
    actual = _index(snapshot["objects"])
    _require(
        len(expected) == len(actual) == KEY_OBJECTS
        and {item["path"] for item in expected} == set(actual),
        "key object set differs",
    )
    output: list[dict[str, Any]] = []
    for item in expected:
        observed = actual[item["path"]]
        _require(
            all(
                observed[key] == item[key]
                for key in ("dataset", "revision", "path", "sha256", "size")
            )
            and re.fullmatch(r"[0-9a-f]{40}", observed["git_oid"]) is not None,
            "key object identity differs",
        )
        lfs = observed["lfs_sha256"]
        if lfs is None:
            _require(
                item["path"] == archived["teaching_csv"]["path"]
                and snapshot["teaching_prior_revision"]
                == archived["teaching_csv"]["revision"]
                and snapshot["teaching_prior_git_oid"] == observed["git_oid"],
                "historical teaching blob differs",
            )
        else:
            _require(lfs == item["sha256"], "key object LFS digest differs")
        output.append(
            item
            | {
                "git_oid": observed["git_oid"],
                "tree_check": "lfs_sha256_and_size"
                if lfs
                else "same_git_blob_and_size_as_prior_revision",
            }
        )
    return output


def screen_derived_delta(
    changed: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> None:
    """Reject a possible newly published output using the prior screen's rules."""
    output_ids = {item["output_id"] for item in candidates}
    digests = {item["parquet_sha256"] for item in candidates}
    sizes = {item["parquet_bytes"] for item in candidates}
    _require(
        len(output_ids) == len(digests) == len(candidates)
        and all(re.fullmatch(r"[0-9a-f]{64}", value) for value in output_ids)
        and all(re.fullmatch(r"[0-9a-f]{64}", value) for value in digests)
        and all(type(value) is int and value > 0 for value in sizes)
        and len({item["path"] for item in changed}) == len(changed),
        "historical output or tree delta identities differ",
    )
    for item in changed:
        object_path = item["path"]
        _require(
            isinstance(object_path, str)
            and bool(object_path)
            and re.fullmatch(r"[0-9a-f]{40}", item["git_oid"]) is not None
            and type(item["size"]) is int
            and item["size"] >= 0
            and (
                item["lfs_sha256"] is None
                or re.fullmatch(r"[0-9a-f]{64}", item["lfs_sha256"]) is not None
            ),
            "tree delta object metadata differs",
        )
        _require(
            not any(output_id in object_path for output_id in output_ids)
            and item["lfs_sha256"] not in digests
            and not (
                object_path.endswith(".parquet")
                and item["lfs_sha256"] is None
                and item["size"] in sizes
            ),
            "possible historical workbook output in tree delta",
        )


def reconcile_derived_refresh(
    e: dict[str, Any], snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Carry forward the prior seven-tree search only across checked deltas."""
    previous = e["archive_comparison"]["mbs_historical_workbooks"]
    candidates = list(
        e["workbook_cohort"]["candidate_outputs_by_group"].values()
    )
    repositories = snapshot["repositories"]
    by_dataset = _index(repositories, key="dataset")
    _require(
        len(candidates)
        == e["workbook_cohort"]["unique_output_ids"]
        == DERIVED_WORKBOOK_OUTPUTS
        and previous["generated_parquets"] == DERIVED_WORKBOOK_OUTPUTS
        and previous["matching_public_generated_parquets"] == 0
        and set(by_dataset) == set(previous["searched_revisions"]),
        "historical output cohort differs",
    )
    monthly = e["archive_receipt"]["aihw_monthly_atc2"]
    expected_changes = {
        PBS_DATASET: {
            "manifest.json",
            monthly["raw_path"],
            monthly["receipt_path"],
        },
        "edithatogo/global-medicines-atlas-catalogue": {"README.md"},
    }
    for dataset, row in by_dataset.items():
        _require(
            row["previous_revision"] == previous["searched_revisions"][dataset]
            and re.fullmatch(r"[0-9a-f]{40}", row["current_revision"])
            is not None
            and row["unchanged"]
            is (row["current_revision"] == row["previous_revision"])
            and not row["removed"]
            and {item["path"] for item in row["changed_or_added"]}
            == expected_changes.get(dataset, set()),
            "historical search revision or delta differs",
        )
        screen_derived_delta(row["changed_or_added"], candidates)
    _require(
        by_dataset[PBS_DATASET]["current_revision"] == PBS_REVISION,
        "PBS historical search revision differs",
    )
    return {
        "candidate_outputs": len(candidates),
        "prior_seven_tree_matches": 0,
        "current_repositories": repositories,
        "new_possible_matches_in_checked_deltas": 0,
        "scope": "unchanged_prior_search_plus_exact_tree_deltas_not_a_global_absence_claim",
    }


def build(metadata_dir: Path, root: Path = ROOT) -> dict[str, Any]:  # ruff: ignore[too-many-locals] -- bind independent archive scopes
    """Build one value-free report from retained evidence and captured metadata."""
    e = {
        name: bounded.read_bound_metadata(root, *ref)
        for name, ref in INPUTS.items()
    }
    manifest_raw = (metadata_dir / "pbs-manifest.json").read_bytes()
    _require(
        len(manifest_raw) <= bounded.MAX_JSON_BYTES,
        "manifest byte limit exceeded",
    )
    manifest = json.loads(manifest_raw, object_pairs_hook=unique_json_object)
    receipt = e["archive_receipt"]["aihw_monthly_atc2"]
    canonical = json.dumps(
        manifest, sort_keys=True, separators=(",", ":")
    ).encode()
    _require(
        manifest["dataset"] == PBS_DATASET
        and manifest["file_count"]
        == len(manifest["files"])
        == receipt["manifest_file_count"]
        and hashlib.sha256(manifest_raw).hexdigest()
        == receipt["manifest_raw_bytes_sha256"]
        and hashlib.sha256(canonical).hexdigest()
        == receipt["manifest_canonical_sorted_compact_json_sha256"]
        == e["aihw_publication"]["manifest_sha256"]
        and e["aihw_publication"]["revision"] == PBS_REVISION,
        "PBS manifest receipt differs",
    )
    pbs_tree = _read_json(metadata_dir / "pbs-tree.json")
    _require(
        pbs_tree["dataset"] == PBS_DATASET
        and pbs_tree["revision"] == PBS_REVISION,
        "PBS tree revision differs",
    )
    resources = e["pbs_discovery"]["resources"]
    authorized = e["pbs_authorized"]["resources"]
    by_url = {row["url"]: row for row in resources}
    _require(
        len(resources) == len(by_url) == PBS_DISCOVERED
        and len(authorized)
        == len({row["url"] for row in authorized})
        == PBS_ADDITIONAL_AUTHORIZED
        and all(by_url.get(row["url"]) == row for row in authorized),
        "PBS discovery or authorization cohort differs",
    )
    pbs = match_pbs_resources(resources, manifest["files"], pbs_tree["objects"])
    categories = Counter(row["category"] for row in pbs)
    objects = [item for row in pbs for item in row["matches"]]
    _require(
        len(objects) == PBS_PAYLOAD_PATHS
        and sum(len(row["matches"]) > 1 for row in pbs)
        == PBS_MULTI_PATH_RESOURCES,
        "PBS matched object count differs",
    )
    multiple_paths = [row for row in pbs if len(row["matches"]) > 1]
    multiple_contents = sum(
        len({item["sha256"] for item in row["matches"]}) > 1
        for row in multiple_paths
    )
    mbs_old = _read_json(metadata_dir / "mbs-schedule-old-tree.json")
    mbs_now = _read_json(metadata_dir / "mbs-schedule-tree.json")
    _require(
        mbs_old["dataset"] == mbs_now["dataset"] == MBS_DATASET
        and mbs_old["revision"] == MBS_OLD
        and mbs_now["revision"] == MBS_CURRENT,
        "MBS archive revision differs",
    )
    index = e["mbs_index"]["monthly_schedule_xml_index_reconciliation"]
    _require(
        index["listed_xml_link_count"]
        == index["receipt_matched_count"]
        == len(index["resources"])
        == MBS_XML_LINKS
        and index["page_count"] == MBS_XML_PAGES,
        "MBS index cohort differs",
    )
    mbs = match_mbs_resources(
        index["resources"], mbs_now["objects"], mbs_old["objects"]
    )
    keys = _key_objects(
        e, _read_json(metadata_dir / "coverage-key-objects.json")
    )
    derived_refresh = reconcile_derived_refresh(
        e, _read_json(metadata_dir / "seven-tree-refresh.json")
    )
    historical_pdf = e["historical_pdf"]["links"]
    previous_pdf = e["previous_downloads"]["links"]
    pdf_urls = {row["source_url"] for row in historical_pdf + previous_pdf}
    _require(
        len(historical_pdf) == MBS_PDF_YEAR_LINKS
        and len(previous_pdf) == MBS_PDF_PREVIOUS_LINKS
        and len(pdf_urls) == MBS_PDF_DISTINCT_URLS,
        "MBS PDF inventory differs",
    )
    schedule = e["pbs_schedule"]
    unmatched = [
        row
        for row in schedule["links"]
        if row["identity_status"] == "unresolved"
    ]
    _require(
        schedule["result"]["official_link_occurrences"] == PBS_SCHEDULE_LINKS
        and schedule["result"]["matched_occurrences"] == PBS_SCHEDULE_MATCHES
        and len(unmatched)
        == schedule["result"]["unmatched_occurrences"]
        == PBS_SCHEDULE_UNMATCHED,
        "PBS schedule crosswalk differs",
    )
    annual = e["annual"]["profile"]["financial_year_labels"]
    _require(
        annual[0] == "2009-10"
        and annual[-1] == "2025-26"
        and len(annual) == MEDICARE_ANNUAL_YEARS,
        "annual workbook year labels differ",
    )
    age = e["age"]
    _require(
        age["scope"]["processing_month"] == "1993-12"
        and age["source_integrity"]["participant_files_accessed"] is False
        and age["disposition"]
        == "three_value_matches_confirmed; native_age_label_inconsistency_recorded",
        "1993 age comparison differs",
    )
    teaching = e["atc_teaching"]
    _require(
        teaching["coverage"]["date_min"] == "1991-07-01"
        and teaching["coverage"]["date_max"] == "2008-06-01"
        and "fill_gaps" in teaching["zero_caveat"],
        "ATC teaching scope differs",
    )
    monthly = e["aihw_contract"]["archives"]["pbs"]["files"][0]
    historical = [
        item
        for item in e["aihw_historical"]["deferred_public_files"]
        if item["sha256"]
        == e["archive_comparison"]["pbs_atc2_utilisation"][
            "aihw_historical_workbook"
        ]["sha256"]
    ]
    _require(
        len(historical) == 1
        and "May 2002 to Jan 2015" in historical[0]["resource"]["period_label"],
        "AIHW historical period differs",
    )
    return {
        "schema_id": "global-medicines-atlas.australian-historical-coverage-reconciliation",
        "schema_version": 1,
        "observed_on": "2026-11-16",
        "inputs": {
            name: {"path": ref[0], "sha256": ref[1]}
            for name, ref in INPUTS.items()
        },
        "pbs_utilisation": {
            "dataset": PBS_DATASET,
            "revision": PBS_REVISION,
            "manifest_raw_sha256": receipt["manifest_raw_bytes_sha256"],
            "manifest_canonical_sha256": receipt[
                "manifest_canonical_sorted_compact_json_sha256"
            ],
            "last_run_status_scope": "one_ATC2_append_not_full_historical_coverage",
            "discovered_resources": len(pbs),
            "authorized_additional_subset": len(authorized),
            "matched_resources": len(pbs),
            "matched_payload_paths": len(objects),
            "paired_receipts": len(objects),
            "categories": dict(sorted(categories.items())),
            "multiple_path_resources": sum(
                len(row["matches"]) > 1 for row in pbs
            ),
            "multiple_path_resources_with_distinct_digests": multiple_contents,
            "multiple_path_resources_with_one_digest": len(multiple_paths)
            - multiple_contents,
            "payload_lfs_digest_checks": sum(
                item["payload_tree_check"] == "lfs_sha256_and_size"
                for item in objects
            ),
            "payload_git_blob_size_checks": sum(
                item["payload_tree_check"] == "git_blob_and_size"
                for item in objects
            ),
            "resources": pbs,
        },
        "mbs_schedule": {
            "dataset": MBS_DATASET,
            "previous_revision": MBS_OLD,
            "current_revision": MBS_CURRENT,
            "indexed_xml_links": len(mbs),
            "indexed_pages": index["page_count"],
            "same_payload_and_receipt_git_objects_at_both_revisions": len(mbs),
            "resources": mbs,
        },
        "selected_archive_objects": keys,
        "historical_workbook_output_search": derived_refresh,
        "period_boundaries": {
            "mbs_historical_zip_labels": "1993-2015; labelled archives, not proven continuous quarters",
            "december_1993": "specific item/month comparison; workbook >85 cutoff remains unconfirmed",
            "annual_medicare_native_financial_years": [annual[0], annual[-1]],
            "pbs_teaching_month_labels": [
                teaching["coverage"]["date_min"],
                teaching["coverage"]["date_max"],
            ],
            "pbs_teaching_zero_caveat": "upstream gap-filled zeros are not independent evidence of zero utilisation",
            "aihw_historical_workbook": "May 2002 to January 2015; historical supplementary tables",
            "aihw_monthly_zip": monthly["resource"]["period_label"],
            "periods_are_not_interchangeable": True,
        },
        "open_coverage": {
            "pbs_schedule_link_occurrences": 316,
            "pbs_schedule_matched_occurrences": 312,
            "pbs_schedule_unmatched": [
                {"effective_date": row["effective_date"], "label": row["label"]}
                for row in unmatched
            ],
            "historical_mbs_pdf_link_occurrences": len(historical_pdf)
            + len(previous_pdf),
            "historical_mbs_pdf_distinct_urls": len(pdf_urls),
            "pdf_scope": "index_observation_only_not_retrieval_or_rights",
            "expected_historical_period_denominator": "not_established",
            "m107": "blocked",
        },
        "limits": [
            "Matches use retained source IDs, archive paths, manifest entries and tree metadata; receipt contents were not re-read.",
            "For Git-only objects, the tree checks Git blob identity and size, not a fresh SHA-256 of payload bytes.",
            "Periods are source labels or earlier qualified observations; archive presence does not prove continuity, semantic equivalence, currentness or privacy clearance.",
            "The existing admission, rights and independent recovery decisions remain separate.",
        ],
        "boundaries": {
            "source_or_projection_payload_read": False,
            "participant_or_cohort_data_accessed": False,
            "dataset_acquired_or_published": False,
            "rights_or_privacy_decision_changed": False,
            "v4_admission_or_consumer_canary": False,
            "historical_completeness_accepted": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-dir", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (
        json.dumps(build(args.metadata_dir), sort_keys=True, indent=2) + "\n"
    ).encode()
    path = ROOT / OUTPUT
    if args.check:
        _require(
            path.is_file() and path.read_bytes() == raw,
            "historical coverage report differs",
        )
    else:
        path.write_bytes(raw)
    print("Reconciled retained PBS and MBS coverage metadata; no payload read")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
