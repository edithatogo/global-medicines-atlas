"""Check exact existing MBS identities and PBS privacy metadata.

The optional hosted read hashes only eleven already source-profile-assessed MBS
objects. It retains no payload bytes and is not an admission, reader canary,
independent recovery, new-source acquisition, or dataset publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import UTC, datetime
from http import HTTPStatus
from operator import itemgetter
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

import httpx
import scripts.qualify_australian_existing_object_gates as prior
import scripts.qualify_m112_existing_reimbursement_batch as bounded

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main,
)
from global_medicines_atlas.federation_reader import HOSTS

ROOT = Path(__file__).resolve().parents[1]
QUAL = "quality/qualifications/"
DATASET = "edithatogo/australian-mbs-source-archive"
ARCHIVE_SHA = "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20"
MEMBER_SHA = "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
SCHEMA_SHA = "03acfbafd80daf0b8b768f7814dbb29a9bd13e7c9d5d68797b30261da29770c6"
MBS_COUNT = 11
PBS_COUNT = 1722
PBS_MEMBER_SCHEMA_PATHS = 5163
PBS_PROFILED_ALIASES = 2
PBS_PROFILED_ARCHIVE_BYTES = 11_156_706
SILVER_RESTORE_OBJECTS = 6
MAX_REDIRECTS = 3
READ_TIMEOUT = 90.0
CHUNK_BYTES = 64 * 1024
INPUTS = {
    "prior": (
        QUAL + "australian-existing-mbs-pbs-object-gates-20261115.json",
        "3e30aed422ec437db9f199939ba2ee5863cccaa684ebdaf06641fbcc9895342e",
    ),
    "tree": (
        QUAL + "australian-mbs-exact-tree-observation-20261115.json",
        "a3622c3b3c5f875829c3702e4080473ba3cff02c46ba249107d7c5555578ec43",
    ),
    "old_tree": (
        QUAL + "australian-m112-current-tree-object-inventory-20261004.json",
        "25767e41fb2990dfcda4688a6b30a80eaf60cd6429042aadd8d2c5cce2e730ae",
    ),
    "privacy": prior.INPUTS["privacy"],
    "pbs_links": (
        QUAL + "australian-pbs-m107-existing-archive-crosswalk-20261115.json",
        "5850ad0f315bedf03971c9811f9ac12d9fb9fbaf77e72fd710cbac1d4ce5fcd9",
    ),
    "pbs_schema": (
        QUAL + "pbs-schema-paths-20261022-39667604237.json",
        "6da85f3e3526a52dca7b0f41206b5ec1afde854f89d858ae659867827219408b",
    ),
    "recovery": (
        QUAL
        + "australian-m112-recovery-readiness-20261027/recovery-readiness.json",
        "19926db87fceef4a74914bc2cdc2db0ee4026d9ce5987994ab36b1012f17f2f0",
    ),
    "silver_restore": (
        QUAL
        + "australian-m112-recovery-readiness-20261027/silver-primary-restore.json",
        "b6eb2c45abdf6b039352ecc85e052bca0b95a931aeb95ed0ef1c7c8eee550634",
    ),
}


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result = {(row["dataset"], row["path"]): row for row in rows}
    _require(len(result) == len(rows), "duplicate dataset and path")
    return result


def mbs_readiness(evidence: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Bind eleven exact tree observations without promoting candidate roles."""
    selected = bounded.metadata_rows(evidence["prior"]["mbs_objects"])
    observed = _index(bounded.metadata_rows(evidence["tree"]["objects"]))
    old = _index([
        row
        for row in bounded.metadata_rows(evidence["old_tree"]["observations"])
        if row.get("dataset") == DATASET
    ])
    _require(
        len(selected) == len(observed) == MBS_COUNT
        and evidence["tree"]["boundaries"]
        == {
            "dataset_mutated": False,
            "participant_or_cohort_data_accessed": False,
            "source_or_projection_payload_read": False,
        },
        "MBS tree observation scope differs",
    )
    rows: list[dict[str, Any]] = []
    for item in selected:
        identity = (item["dataset"], item["path"])
        actual = observed[identity]
        expected_endpoint = (
            f"https://huggingface.co/api/datasets/{DATASET}/tree/"
            f"{item['revision']}/{quote(item['path'].rsplit('/', 1)[0], safe='/')}"
            "?limit=100&expand=true"
        )
        _require(
            item["dataset"] == DATASET
            and item["privacy"] == prior.privacy.ASSESSED
            and item["v4_admission"] == "not_established_by_selected_evidence"
            and actual["revision"] == item["revision"]
            and actual["byte_count"] == item["byte_count"]
            and actual["expected_sha256"] == item["sha256"]
            and actual["metadata_endpoint"] == expected_endpoint
            and re.fullmatch(r"[0-9a-f]{40}", actual["git_blob_oid"])
            is not None,
            "MBS exact revision tree identity differs",
        )
        if actual["lfs_sha256"] is None:
            earlier = old[identity]
            _require(
                earlier["candidate_inventory_revision"] == item["revision"]
                and earlier["expected_git_blob_oid"] == actual["git_blob_oid"]
                and earlier["observed_git_blob_oid"] == actual["git_blob_oid"]
                and earlier["expected_bytes"] == item["byte_count"]
                and earlier["observed_bytes"] == item["byte_count"]
                and earlier["git_blob_oid_match"] is True,
                "MBS non-LFS earlier blob identity differs",
            )
            metadata_identity = "git_blob_and_size_match_historical_evidence"
        else:
            _require(
                actual["lfs_sha256"] == item["sha256"],
                "MBS LFS SHA-256 differs",
            )
            metadata_identity = "lfs_sha256_and_size_match"
        rows.append(
            {
                key: item[key]
                for key in (
                    "dataset",
                    "revision",
                    "path",
                    "sha256",
                    "byte_count",
                    "batch",
                    "frozen_member",
                    "privacy",
                    "rights",
                    "lineage",
                    "candidate_v4_roles",
                )
            }
            | {
                "tree_git_blob_oid": actual["git_blob_oid"],
                "tree_metadata_identity": metadata_identity,
                "exact_revision_stream_digest": "not_yet_verified_in_this_report",
                "v4_contract_receipt_closure": "not_established_by_selected_evidence",
                "trusted_v4_admission": "not_established_by_selected_evidence",
                "consumer_canary": "not_established_by_selected_evidence",
                "independent_recovery": "not_established_by_selected_evidence",
            }
        )
    return sorted(rows, key=itemgetter("path"))


def pbs_privacy_readiness(
    evidence: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Join existing official-link and native-schema metadata, without values."""
    privacy_rows = bounded.metadata_rows(evidence["privacy"]["objects"])
    selected = [row for row in privacy_rows if row["batch"] in prior.PBS_GROUPS]
    schedule = _index([
        row for row in selected if row["batch"].startswith("pbs_schedule_")
    ])
    _require(
        len(selected) == PBS_COUNT
        and len(schedule) == bounded.RAW_OBJECTS
        and all(row["privacy"] == prior.privacy.UNKNOWN for row in selected),
        "PBS privacy disposition differs",
    )
    matched: dict[tuple[str, str], str] = {}
    for link in evidence["pbs_links"]["links"]:
        for candidate in link["candidates"]:
            identity = (candidate["dataset"], candidate["path"])
            if identity not in schedule:
                continue
            row = schedule[identity]
            _require(
                candidate["revision"] == row["revision"]
                and candidate["sha256"] == row["sha256"]
                and candidate["byte_count"] == row["byte_count"]
                and candidate["payload_read_qualified"] is False,
                "PBS official-link identity differs",
            )
            previous = matched.setdefault(identity, link["format"])
            _require(previous == link["format"], "PBS link format differs")
    schema = evidence["pbs_schema"]
    paths = bounded.metadata_rows(schema["paths"])
    _require(
        schema["archive_sha256"] == ARCHIVE_SHA
        and schema["member_sha256"] == MEMBER_SHA
        and schema["unique_schema_paths"]
        == len(paths)
        == PBS_MEMBER_SCHEMA_PATHS
        and schema["native_values_emitted"] is False,
        "PBS member schema inventory differs",
    )
    aliases = [row for row in selected if row["sha256"] == ARCHIVE_SHA]
    _require(
        len(aliases) == PBS_PROFILED_ALIASES
        and all(
            row["byte_count"] == PBS_PROFILED_ARCHIVE_BYTES for row in aliases
        ),
        "PBS profiled archive aliases differ",
    )
    patient_paths = sum(
        bool(
            re.search(
                r"person|patient|individual|beneficiar",
                r["schema_path"],
                re.IGNORECASE,
            )
        )
        for r in paths
    )
    contact_paths = sum(
        bool(
            re.search(r"e.?mail|phone|address", r["schema_path"], re.IGNORECASE)
        )
        for r in paths
    )
    return {
        "unassessed_pbs_related_or_reimbursement_objects": len(selected),
        "schedule_objects": len(schedule),
        "schedule_objects_with_exact_official_link_metadata": len(matched),
        "official_link_formats": dict(
            sorted(Counter(matched.values()).items())
        ),
        "archive_aliases_with_one_profiled_xml_member": len(aliases),
        "profiled_member_sha256": MEMBER_SHA,
        "profiled_member_unique_schema_paths": len(paths),
        "schema_paths_with_patient_or_person_tokens": patient_paths,
        "schema_paths_with_contact_tokens": contact_paths,
        "schema_path_inventory_is_value_or_archive_privacy_clearance": False,
        "new_privacy_clearances": 0,
        "unassessed_payload_reads_permitted": False,
    }


def recovery_readiness(
    evidence: dict[str, dict[str, Any]], objects: list[dict[str, Any]]
) -> dict[str, Any]:
    """Distinguish two retained primary restores from this exact MBS cohort."""
    recovery = evidence["recovery"]
    silver = evidence["silver_restore"]
    binding = recovery["evidence"]["silver_product_primary_restore"]
    _require(
        recovery["status"].endswith("independent_recovery_blocked")
        and binding["path"] == INPUTS["silver_restore"][0]
        and binding["sha256"] == INPUTS["silver_restore"][1]
        and recovery["scope"]["additional_public_product_cohort"]["dataset"]
        == DATASET
        and silver["status"] == "passed"
        and silver["object_count"]
        == len(silver["objects"])
        == SILVER_RESTORE_OBJECTS
        and all(
            row["restored_from_primary"] is True for row in silver["objects"]
        ),
        "existing primary recovery evidence differs",
    )
    target_paths = {row["path"] for row in objects}
    silver_matches = target_paths.intersection(
        row["path"] for row in silver["objects"]
    )
    _require(
        not silver_matches,
        "prior Silver restore unexpectedly includes a target",
    )
    primary_dataset = recovery["scope"]["dataset"]
    _require(
        primary_dataset != DATASET, "prior primary restore dataset differs"
    )
    return {
        "prior_raw_primary_restore_dataset": primary_dataset,
        "prior_silver_primary_restore_objects": len(silver["objects"]),
        "selected_paths_in_prior_silver_restore": len(silver_matches),
        "selected_exact_revision_primary_restore_established": False,
        "independent_recovery_established": False,
        "observation_scope": "selected_existing_recovery_receipts_only",
    }


def build_report(root: Path = ROOT) -> dict[str, Any]:
    """Build the pre-hosted, value-free readiness and privacy report."""
    evidence = {
        name: bounded.read_bound_metadata(root, *binding)
        for name, binding in INPUTS.items()
    }
    _require(
        prior.build_report(root) == evidence["prior"], "prior report differs"
    )
    schema = root / "contracts/medallion/v4.1/federation.schema.json"
    _require(
        hashlib.sha256(schema.read_bytes()).hexdigest() == SCHEMA_SHA,
        "v4 schema differs",
    )
    objects = mbs_readiness(evidence)
    return {
        "schema_id": "global-medicines-atlas.australian-existing-v4-privacy-readiness",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "inputs": {
            k: {"path": v[0], "sha256": v[1]} for k, v in INPUTS.items()
        },
        "v4_schema_sha256": SCHEMA_SHA,
        "mbs_objects": objects,
        "recovery": recovery_readiness(evidence, objects),
        "pbs_privacy": pbs_privacy_readiness(evidence),
        "boundaries": {
            "dataset_added_or_published": False,
            "participant_or_cohort_data_accessed": False,
            "source_or_projection_payload_read": False,
            "v4_admission_performed": False,
            "independent_recovery_established": False,
        },
    }


def _allowed_url(url: str) -> None:
    parsed = urlsplit(url)
    _require(
        parsed.scheme == "https"
        and parsed.hostname in HOSTS
        and parsed.username is None
        and parsed.password is None
        and parsed.port in {None, 443}
        and not parsed.fragment,
        "unapproved hosted digest destination",
    )


def stream_digest(
    client: httpx.Client, url: str, *, expected_sha256: str, expected_bytes: int
) -> dict[str, Any]:
    """Hash a bounded stream without persisting or emitting payload bytes."""
    deadline = time.monotonic() + READ_TIMEOUT
    for _ in range(MAX_REDIRECTS + 1):
        _allowed_url(url)
        _require(time.monotonic() <= deadline, "hosted digest timed out")
        client.cookies.clear()
        with client.stream("GET", url) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                _require(location is not None, "redirect has no location")
                url = urljoin(url, str(location))
                continue
            _require(
                response.status_code == HTTPStatus.OK,
                "hosted digest HTTP failure",
            )
            _require(
                response.headers.get("content-encoding", "identity")
                == "identity",
                "hosted digest content encoding differs",
            )
            digest = hashlib.sha256()
            size = 0
            for chunk in response.iter_bytes(CHUNK_BYTES):
                size += len(chunk)
                _require(
                    size <= expected_bytes, "hosted digest exceeded byte bound"
                )
                _require(
                    time.monotonic() <= deadline, "hosted digest timed out"
                )
                digest.update(chunk)
            _require(
                size == expected_bytes
                and digest.hexdigest() == expected_sha256,
                "hosted digest or byte count differs",
            )
            return {"sha256": digest.hexdigest(), "byte_count": size}
    raise ValueError("hosted digest redirect limit exceeded")


def hosted_verify(report: dict[str, Any], *, commit: str) -> dict[str, Any]:
    """Verify the exact classified MBS identities on a dispatched main run."""
    require_hosted_main(commit)
    _require(report == build_report(), "hosted MBS evidence differs")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    _require(
        re.fullmatch(r"[1-9][0-9]*", attempt) is not None, "missing run attempt"
    )
    rows = report["mbs_objects"]
    _require(len(rows) == MBS_COUNT, "hosted MBS scope differs")
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=READ_TIMEOUT,
        max_attempts=1,
        max_redirects=MAX_REDIRECTS,
    )
    checked: list[dict[str, Any]] = []
    with httpx.Client(
        transport=BoundIPAddressTransport(policy=policy),
        trust_env=False,
        follow_redirects=False,
        timeout=READ_TIMEOUT,
        headers={"Accept-Encoding": "identity"},
    ) as client:
        try:
            for row in rows:
                _require(
                    row["privacy"] == prior.privacy.ASSESSED,
                    "MBS privacy differs",
                )
                url = (
                    f"https://huggingface.co/datasets/{row['dataset']}/resolve/"
                    f"{row['revision']}/{quote(row['path'], safe='/')}"
                )
                digest = stream_digest(
                    client,
                    url,
                    expected_sha256=row["sha256"],
                    expected_bytes=row["byte_count"],
                )
                checked.append({
                    "dataset": row["dataset"],
                    "revision": row["revision"],
                    "path": row["path"],
                    **digest,
                })
        except httpx.HTTPError:
            raise ValueError("hosted digest transport failed") from None
    return {
        "schema_id": "global-medicines-atlas.australian-existing-mbs-hosted-digest",
        "schema_version": 1,
        "workflow_commit": commit,
        "workflow_run": os.environ["GITHUB_RUN_ID"],
        "workflow_attempt": attempt,
        "verified_at": datetime.now(UTC).isoformat(),
        "objects": checked,
        "boundaries": {
            "dataset_added_or_published": False,
            "participant_or_cohort_data_accessed": False,
            "payload_bytes_persisted_or_emitted": False,
            "v4_admission_or_consumer_canary": False,
            "independent_recovery_established": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", type=Path)
    action.add_argument("--build", type=Path)
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--workflow-commit")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report()
    if args.check:
        _require(
            json.loads(args.check.read_text(encoding="utf-8")) == report,
            "report differs",
        )
    elif args.build:
        with args.build.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    else:
        commit = args.workflow_commit
        output = args.output
        if not isinstance(commit, str) or not isinstance(output, Path):
            raise ValueError("hosted output and commit required")
        require_hosted_main(commit)
        runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
        _require(
            output.resolve().is_relative_to(runner_temp),
            "hosted output must remain in runner temp",
        )
        receipt = hosted_verify(report, commit=commit)
        with output.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(
        json.dumps(
            {
                "mbs_objects": len(report["mbs_objects"]),
                "pbs": report["pbs_privacy"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
