"""Join retained PBS link and archive metadata without reading payloads.

The result is an identity crosswalk, not a privacy assessment, a new rights
decision, a v4 admission, or proof that any unjoined object is absent.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import scripts.qualify_m112_existing_reimbursement_batch as prior

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    "links": (
        "quality/qualifications/australian-pbs-m107-link-crosswalk-20261018.json",
        "4614d529de0f290319757520b95cea004a2d271e18e2f67a5c1350370e5b127d",
    ),
    "rights": (
        "quality/qualifications/australian-m112-current-rights-reconciliation-20261021-2.json",
        "6905351d9dae194699f33d91054048664b27daf1bcced7dcfc16aa5d15977f86",
    ),
    "batch": (
        "quality/qualifications/australian-m112-reimbursement-batch-readiness-20261115.json",
        "0969afcd6152cd73f5ff53f28ccb6fb9315090a71ba302ebbee74efaf32db4f5",
    ),
    "observation": (
        "quality/qualifications/australian-pbs-m107-four-link-metadata-20261115.json",
        "c998c62d491dba5395b762c4fcbd639049d57b7a1fd9d43f52366c0246f2b2bc",
    ),
}
SOURCE_ARCHIVE = "edithatogo/australian-pbs-source-archive"
UNKNOWN_SENSITIVITY = {
    "data_sensitivity": "unknown",
    "personal_data": "unknown",
    "publication": "review_required",
}
EXPECTED_TREES = {
    (
        "edithatogo/reimbursement-atlas",
        "8c75366a5d5fbf72cdde1d9f83e6f1cbaef7a338",
    ),
    (
        "edithatogo/australian-pbs-source-archive",
        "3995deb3e2a82f09472d6a78020fb13bbbc96056",
    ),
    (
        "edithatogo/australian-pbs-utilisation-archive",
        "ba60e1d18b81e4af3cae50bc9fbfe719406fa5f3",
    ),
}


def _source_url(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("invalid official URL")
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or parts.netloc != "www.pbs.gov.au"
        or not parts.path.startswith("/publication/schedule/")
        or parts.fragment
    ):
        raise ValueError("invalid official URL")
    return value


def _candidate_index(
    rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    identities: set[tuple[str, str]] = set()
    for row in rows:
        url = _source_url(row.get("source_locator"))
        dataset, path = row.get("dataset"), row.get("path")
        if not isinstance(dataset, str) or not isinstance(path, str):
            raise TypeError("invalid archive identity")
        identity = (dataset, path)
        if identity in identities:
            raise ValueError("duplicate archive identity")
        identities.add(identity)
        prior.metadata_identity(row)
        by_url[url].append(row)
    return by_url


def _validate_b1_event(event: dict[str, Any], *, url: str, digest: str) -> None:
    retrieval = prior.metadata_object(event.get("retrieval"))
    if (
        retrieval.get("uri") != url
        or retrieval.get("status") != "succeeded"
        or event.get("payload_sha256") != digest
    ):
        raise ValueError("official URL or B1 payload identity differs")


def _reimbursement_candidate(
    root: Path, row: dict[str, Any], batch_row: dict[str, Any], *, url: str
) -> dict[str, Any]:
    digest, size = prior.metadata_identity(row)
    if not all((
        row.get("dataset") == prior.DATASET,
        row.get("source_locator") == url,
        row.get("lineage_complete") is True,
        row.get("v4_admission") is False,
        row.get("consumer_canary") is False,
        batch_row.get("dataset") == row.get("dataset"),
        batch_row.get("path") == row.get("path"),
        prior.metadata_identity(batch_row) == (digest, size),
        batch_row.get("revision") == prior.REVISION,
        batch_row.get("representation") == "raw_source_payload",
        batch_row.get("privacy_gate")
        == "blocked_no_source_specific_sensitivity_assessment",
        batch_row.get("observed_sensitivity") == UNKNOWN_SENSITIVITY,
        batch_row.get("ready_for_payload_read") is False,
        batch_row.get("v4_admission") == "not_performed",
        batch_row.get("consumer_check") == "not_performed_privacy_gate_blocked",
    )):
        raise ValueError("archive identity or privacy gate differs")
    metadata = prior.metadata_object(batch_row.get("metadata_references"))
    roles = (
        "acquisition_event_path",
        "b2_manifest_path",
        "landed_admission_path",
    )
    lineage = {role: metadata.get(role) for role in roles}
    bindings = {
        metadata[role]: metadata[role.replace("_path", "_sha256")]
        for role in roles
    }
    references, sensitivity = prior.validate_metadata_records(
        root, lineage, bindings, digest=digest
    )
    event = prior.read_bound_metadata(
        root,
        references["acquisition_event_path"],
        references["acquisition_event_sha256"],
    )
    _validate_b1_event(event, url=url, digest=digest)
    return {
        "dataset": row["dataset"],
        "revision": batch_row["revision"],
        "path": row["path"],
        "sha256": digest,
        "byte_count": size,
        "identity_evidence": "exact_official_url_and_digest_bound_b1_b2_landed_metadata",
        "metadata_references": references,
        "rights_evidence": batch_row["rights_evidence"],
        "observed_sensitivity": sensitivity,
        "privacy_gate": batch_row["privacy_gate"],
        "payload_read_qualified": False,
        "v4_admission": "not_performed",
        "consumer_check": "not_performed_privacy_gate_blocked",
    }


def _known_candidate(
    row: dict[str, Any], other: dict[str, Any], link: dict[str, Any]
) -> dict[str, Any]:
    digest, size = prior.metadata_identity(row)
    binding = prior.metadata_object(link.get("source_receipt_binding"))
    archive = prior.metadata_object(binding.get("archive"))
    if not all((
        row.get("dataset") == SOURCE_ARCHIVE,
        row.get("source_locator")
        == link.get("url")
        == binding.get("official_url"),
        binding.get("status") == "exact_official_url_to_b1_receipt_metadata",
        binding.get("dataset") == row.get("dataset") == other.get("dataset"),
        binding.get("revision") == other.get("frozen_revision"),
        archive.get("path") == row.get("path") == other.get("path"),
        prior.metadata_identity(archive)
        == prior.metadata_identity(other)
        == (digest, size),
        row.get("lineage_complete") is True,
        row.get("v4_admission") is False,
        row.get("consumer_canary") is False,
        other.get("current_payload_read") == "not_performed",
        other.get("current_raw_v4_admission") == "not_performed",
        binding.get("rights_reconciliation_status")
        == "receipt_permitted_claim_source_ledger_unknown",
    )):
        raise ValueError("previously known source archive evidence differs")
    return {
        "dataset": row["dataset"],
        "revision": binding["revision"],
        "path": row["path"],
        "sha256": digest,
        "byte_count": size,
        "identity_evidence": binding["status"],
        "rights_conflict": binding["rights_reconciliation_status"],
        "historical_rights_state": other["historical_rights_state"],
        "privacy_gate": "not_qualified_in_selected_evidence",
        "payload_read_qualified": False,
        "v4_admission": "not_performed",
        "consumer_check": "not_performed",
    }


def _probe_index(observation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    probe = prior.metadata_object(observation.get("publisher_probe"))
    if not all((
        probe.get("method") == "HEAD",
        probe.get("redirects_followed") is False,
        probe.get("response_bodies_read") is False,
        all(
            value is False
            for value in prior.metadata_object(
                observation.get("boundaries")
            ).values()
        ),
    )):
        raise ValueError("publisher observation boundary differs")
    rows = prior.metadata_rows(probe.get("objects"))
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        url = _source_url(row.get("url"))
        if (
            url in result
            or row.get("status") != HTTPStatus.OK
            or type(row.get("declared_bytes")) is not int
            or row["declared_bytes"] <= 0
            or row.get("content_type") != "application/zip"
        ):
            raise ValueError("publisher observation differs")
        result[url] = row
    scans = prior.metadata_rows(observation.get("anonymous_archive_tree_scans"))
    if (
        len(scans) != len(EXPECTED_TREES)
        or {(row.get("dataset"), row.get("revision")) for row in scans}
        != EXPECTED_TREES
        or any(
            row.get("exact_basename_matches") != 0
            or row.get("same_declared_size_matches") != 0
            for row in scans
        )
    ):
        raise ValueError("archive tree observation differs")
    return result


def build_report(root: Path = ROOT) -> dict[str, Any]:  # ruff: ignore[too-many-locals] -- Explicit bounded joins preserve separate evidence roles.
    """Verify pinned metadata and preserve each official link occurrence."""
    sources = {
        name: prior.read_bound_metadata(root, *ref)
        for name, ref in INPUTS.items()
    }
    links = prior.metadata_rows(sources["links"].get("links"))
    rights = prior.metadata_object(
        sources["rights"].get("pbs_raw_redistribution_permission")
    )
    candidates = _candidate_index(prior.metadata_rows(rights.get("objects")))
    batch = prior.metadata_rows(sources["batch"].get("objects"))
    batch_by_path = prior.metadata_index(batch)
    other = prior.metadata_rows(sources["batch"].get("other_frozen_objects"))
    other_by_identity = {(row["dataset"], row["path"]): row for row in other}
    if len(other_by_identity) != len(other):
        raise ValueError("duplicate frozen object")
    probes = _probe_index(sources["observation"])
    results: list[dict[str, Any]] = []
    cache: dict[tuple[str, str], dict[str, Any]] = {}
    for link in links:
        url = _source_url(link.get("url"))
        matches: list[dict[str, Any]] = []
        for row in candidates.get(url, []):
            key = (row["dataset"], row["path"])
            if key not in cache:
                if row["dataset"] == prior.DATASET:
                    cache[key] = _reimbursement_candidate(
                        root, row, batch_by_path[row["path"]], url=url
                    )
                elif row["dataset"] == SOURCE_ARCHIVE:
                    cache[key] = _known_candidate(
                        row, other_by_identity[key], link
                    )
                else:
                    raise ValueError("unexpected archive candidate")
            matches.append(cache[key])
        if (
            len(matches) > 1
            and len({(x["sha256"], x["byte_count"]) for x in matches}) != 1
        ):
            raise ValueError("conflicting archive candidates")
        results.append({
            "year_page": link["year_page"],
            "effective_date": link["effective_date"],
            "label": link["label"],
            "format": link["format"],
            "url": url,
            "historical_status": link["archive_identity_status"],
            "identity_status": "matched_exact_source_url"
            if matches
            else "unresolved",
            "candidates": matches,
            "publisher_head_observation": probes.get(url)
            if not matches
            else None,
        })
    unmatched = [row for row in results if not row["candidates"]]
    if {row["url"] for row in unmatched} != set(probes):
        raise ValueError("unmatched links and observations differ")
    newly = [
        row
        for row in results
        if row["candidates"]
        and row["historical_status"] == "unresolved_link_to_archive_identity"
    ]
    matched = [row for row in results if row["candidates"]]
    summary = {
        "official_link_occurrences": len(results),
        "previously_unresolved_occurrences": sum(
            row["historical_status"] == "unresolved_link_to_archive_identity"
            for row in results
        ),
        "newly_matched_occurrences": len(newly),
        "newly_matched_distinct_urls": len({row["url"] for row in newly}),
        "newly_matched_distinct_archive_paths": len({
            (candidate["dataset"], candidate["path"])
            for row in newly
            for candidate in row["candidates"]
        }),
        "matched_occurrences": len(matched),
        "matched_distinct_urls": len({row["url"] for row in matched}),
        "matched_distinct_archive_paths": len(cache),
        "matched_reimbursement_b1_records": sum(
            key[0] == prior.DATASET for key in cache
        ),
        "unmatched_occurrences": len(unmatched),
        "new_unique_admissions": 0,
    }
    expected = (316, 315, 311, 310, 310, 312, 311, 312, 311, 4)
    if tuple(summary.values())[:-1] != expected:
        raise ValueError("pinned crosswalk scope differs")
    return {
        "schema_id": "global-medicines-atlas.pbs-m107-existing-archive-crosswalk",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "inputs": {
            name: {"path": path, "sha256": digest}
            for name, (path, digest) in INPUTS.items()
        },
        "result": summary,
        "interpretation": [
            "Exact URL and retained B1/B2 metadata join archive identities; they do not confer privacy, semantic, rights or v4 admission clearance.",
            "The publisher HEAD and three pinned tree searches are observations, not proof of absence or byte identity; tree response bodies were not retained.",
            "The previously known April 2026 source archive and its reimbursement mirror remain distinct objects with separate rights and privacy states.",
        ],
        "boundaries": {
            "source_payload_read": False,
            "individual_participant_or_cohort_data_accessed": False,
            "dataset_published_or_modified": False,
            "new_rights_decision": False,
            "v4_admission_performed": False,
            "federation_requirement_accepted": False,
        },
        "links": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--report", type=Path)
    output.add_argument("--check", type=Path)
    args = parser.parse_args()
    report = build_report()
    if args.report:
        with args.report.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    elif json.loads(args.check.read_text(encoding="utf-8")) != report:
        raise ValueError("stored crosswalk differs from retained evidence")
    print(json.dumps(report["result"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
