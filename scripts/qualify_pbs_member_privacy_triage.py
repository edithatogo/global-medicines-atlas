"""Triage existing PBS metadata without reading unassessed payloads.

Filename tokens and digest/size grouping guide later review; neither establishes
content, privacy clearance, rights, admission or permission to read a payload.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TypedDict

import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_pbs_schema_privacy_context as context

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    "quality/qualifications/australian-pbs-member-privacy-triage-20261115.json"
)
CONTEXT = (
    "quality/qualifications/australian-pbs-schema-privacy-context-20261115.json",
    "4a629204fc3810ea8e3d3de5e29f304e8cdecaf9ecbb4889ece6ca43db360209",
)
EXPECTED_OBJECTS = 1722
EXPECTED_DISTINCT_CONTENTS = 1721
EXPECTED_DUPLICATE_PATHS = 2
LABELS = {
    "patient_or_person": re.compile(
        r"patient|person|participant", re.IGNORECASE
    ),
    "claims": re.compile(r"claim", re.IGNORECASE),
    "prescribing": re.compile(r"prescrib", re.IGNORECASE),
    "organisation": re.compile(r"organi[sz]ation", re.IGNORECASE),
    "copayment": re.compile(r"copayment", re.IGNORECASE),
}


class MemberTriage(TypedDict):
    name: str
    filename_review_labels: list[str]
    member_digest_available: bool
    privacy: str


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def reconcile(
    privacy: dict[str, Any], api: dict[str, Any], previous: dict[str, Any]
) -> dict[str, Any]:
    """Bind the exact archive inventory and preserve every privacy block."""
    rows = [
        row
        for row in bounded.metadata_rows(privacy["objects"])
        if row["batch"].startswith(("pbs_", "reimbursement_"))
        and row["privacy"] == context.UNKNOWN
    ]
    identities = {(r["dataset"], r["revision"], r["path"]) for r in rows}
    content_groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(
        list
    )
    for row in rows:
        digest, size = bounded.metadata_identity(row)
        content_groups[digest, size].append(row)
    duplicate_groups = [
        group for group in content_groups.values() if len(group) > 1
    ]
    api_metadata = api["pbs_schedule_api"]
    members = api_metadata["members"]
    selected = [
        row for row in rows if row["sha256"] == context.SCHEDULE_CSV_SHA
    ]
    _require(
        len(rows) == len(identities) == EXPECTED_OBJECTS
        and len(content_groups) == EXPECTED_DISTINCT_CONTENTS
        and len(duplicate_groups) == 1
        and len(duplicate_groups[0]) == EXPECTED_DUPLICATE_PATHS
        and {row["sha256"] for row in duplicate_groups[0]}
        == {context.ARCHIVE_SHA}
        and len(selected) == 1
        and all(
            selected[0][key] == api_metadata[key]
            for key in ("dataset", "path", "sha256")
        )
        and selected[0]["revision"] == context.REIMBURSEMENT_REVISION
        and selected[0]["byte_count"] == api_metadata["bytes"]
        and len(members) == len(set(members)) == context.API_MEMBERS
        and all(
            isinstance(name, str)
            and name.startswith("tables_as_csv/")
            and name.endswith(".csv")
            for name in members
        )
        and previous["september_2025_api"]["privacy"] == context.UNKNOWN
        and previous["boundaries"]["archive_privacy_cleared"] is False
        and previous["boundaries"]["unassessed_payload_reads_authorized"]
        is False,
        "PBS member or privacy inventory differs",
    )
    member_rows: list[MemberTriage] = []
    for name in sorted(members):
        flags = sorted(
            label for label, pattern in LABELS.items() if pattern.search(name)
        )
        member_rows.append({
            "name": name,
            "filename_review_labels": flags,
            "member_digest_available": False,
            "privacy": context.UNKNOWN,
        })
    flagged = sum(bool(row["filename_review_labels"]) for row in member_rows)
    _require(
        flagged
        == previous["september_2025_api"]["member_names_with_review_tokens"],
        "PBS filename triage differs from prior lexical screen",
    )
    return {
        "schema_id": "global-medicines-atlas.pbs-member-privacy-triage",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "inputs": {
            "privacy": {
                "path": context.INPUTS["privacy"][0],
                "sha256": context.INPUTS["privacy"][1],
            },
            "api": {
                "path": context.INPUTS["api"][0],
                "sha256": context.INPUTS["api"][1],
            },
            "prior_context": {"path": CONTEXT[0], "sha256": CONTEXT[1]},
        },
        "unassessed_inventory": {
            "objects": len(rows),
            "distinct_digest_and_size_pairs": len(content_groups),
            "same_digest_size_groups_with_multiple_paths": len(
                duplicate_groups
            ),
            "paths_in_duplicate_group": len(duplicate_groups[0]),
            "batches": dict(
                sorted(Counter(row["batch"] for row in rows).items())
            ),
            "privacy_clearances": 0,
        },
        "september_2025_archive": {
            "identity": {
                key: selected[0][key]
                for key in (
                    "dataset",
                    "revision",
                    "path",
                    "sha256",
                    "byte_count",
                )
            },
            "members": member_rows,
            "members_with_review_labels": flagged,
            "filename_label_counts": dict(
                sorted(
                    Counter(
                        flag
                        for row in member_rows
                        for flag in row["filename_review_labels"]
                    ).items()
                )
            ),
            "privacy": context.UNKNOWN,
        },
        "boundaries": {
            "filename_labels_are_privacy_decisions": False,
            "unlabelled_members_are_cleared": False,
            "digest_size_grouping_is_a_privacy_decision": False,
            "unassessed_payload_read": False,
            "participant_or_cohort_data_accessed": False,
            "dataset_added_or_published": False,
        },
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    privacy = bounded.read_bound_metadata(root, *context.INPUTS["privacy"])
    api = bounded.read_bound_metadata(root, *context.INPUTS["api"])
    previous = bounded.read_bound_metadata(root, *CONTEXT)
    _require(previous == context.build(root), "prior PBS context is stale")
    return reconcile(privacy, api, previous)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = (json.dumps(build(), indent=2, sort_keys=True) + "\n").encode()
    path = ROOT / OUTPUT
    if args.check:
        _require(
            path.is_file() and path.read_bytes() == expected,
            "PBS triage is stale",
        )
    else:
        path.write_bytes(expected)
    print("PBS member metadata triaged; privacy remains unassessed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
