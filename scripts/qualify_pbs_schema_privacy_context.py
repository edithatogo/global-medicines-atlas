"""Assess retained PBS schema labels without reading unassessed payloads.

The report is a lexical, member-scoped triage aid. It never clears privacy,
infers participant counts, interprets values, or authorizes payload reads.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded

ROOT = Path(__file__).resolve().parents[1]
QUAL = "quality/qualifications/"
OUTPUT = QUAL + "australian-pbs-schema-privacy-context-20261115.json"
ARCHIVE_SHA = "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20"
MEMBER_SHA = "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
SCHEDULE_CSV_SHA = (
    "60ade25f04a6451239587ac546c34390099b231036349b3a4eaf28409eefdf59"
)
UNKNOWN = "blocked_unknown_or_unqualified_privacy"
REIMBURSEMENT = "edithatogo/reimbursement-atlas"
REIMBURSEMENT_REVISION = "8e062578f14e12cf3238700a93946339da9c5d88"
ARCHIVE_IDENTITIES = frozenset({
    (
        "edithatogo/australian-pbs-source-archive",
        "48fd7345fb09277bb5b85644dba72804633a2abb",
        "raw/2026-04-01/2026-04-01-XML-V3.zip",
    ),
    (
        REIMBURSEMENT,
        REIMBURSEMENT_REVISION,
        (
            "raw/pbs/payloads/au_pbs_structured_6f905abc167f052d/"
            "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20.zip"
        ),
    ),
})
SCHEMA_PATHS = 5_163
ARCHIVE_ALIASES = 2
ARCHIVE_BYTES = 11_156_706
GENERIC_ID_PATHS = 8
API_MEMBERS = 33
INPUTS = {
    "schema": (
        QUAL + "pbs-schema-paths-20261022-39667604237.json",
        "6da85f3e3526a52dca7b0f41206b5ec1afde854f89d858ae659867827219408b",
    ),
    "privacy": (
        QUAL + "australian-existing-archive-privacy-batch-20261115.json",
        "7ab592f48583def8fb05b814d442b394463b3703caf978e885a1d96961029ec8",
    ),
    "readiness": (
        QUAL + "australian-existing-v4-privacy-readiness-20261115.json",
        "84f76a2187830bf1e0949261df739f6eae45fb39f9c58750d7cdce09d4875d39",
    ),
    "api": (
        QUAL + "australian-public-archive-reconciliation-20261113.json",
        "f7883925fe095e46b184690e966101b10b8dcec2326e03d93cb5b18c1e3b5fcf",
    ),
    "api_event": (
        (
            "quality/bronze/imported-acquisitions/au-pbs/"
            "93bf599c49a0c71eceec49b25c3355130d587d14c57337826fa23e5458be7e21.json"
        ),
        "d6ecb3a3e011c2501e6ebcb2e8b9eb37f8c54f152c1c4e412f453e02bc7d4d9f",
    ),
}
PATIENT = re.compile(r"person|patient|individual|beneficiar", re.IGNORECASE)
CONTACT = re.compile(r"e.?mail|phone|address|contact", re.IGNORECASE)
SPECIFIC_ID = re.compile(
    r"(?:^|[-_/])(?:patient[-_]id|participant[-_]id|medicare[-_]number|"
    r"date[-_]of[-_]birth|birth[-_]date|dob)(?:$|[-_/])",
    re.IGNORECASE,
)
API_REVIEW_LABEL = re.compile(
    r"patient|person|participant|claim|prescrib|organi[sz]ation|copayment",
    re.IGNORECASE,
)


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _plain_path(path: str) -> str:
    """Remove namespace braces, preserving element and attribute names."""
    _require(path.startswith("/") and "}" in path, "schema path format differs")
    return re.sub(r"\{[^}]*\}", "", path)


def _context(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    _require(len(parts) > 1 and parts[0] == "root", "schema root differs")
    return parts[1]


def _counts(paths: list[str], pattern: re.Pattern[str]) -> dict[str, int]:
    counts = Counter(_context(path) for path in paths if pattern.search(path))
    return dict(sorted(counts.items()))


def reconcile(e: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Return aggregate contexts and preserve every existing privacy block."""
    schema = e["schema"]
    rows = bounded.metadata_rows(schema["paths"])
    paths = [_plain_path(row["schema_path"]) for row in rows]
    privacy = bounded.metadata_rows(e["privacy"]["objects"])
    aliases = [row for row in privacy if row["sha256"] == ARCHIVE_SHA]
    prior = e["readiness"]["pbs_privacy"]
    _require(
        schema["archive_sha256"] == ARCHIVE_SHA
        and schema["member_sha256"] == MEMBER_SHA
        and schema["native_values_emitted"] is False
        and len(paths) == schema["unique_schema_paths"] == SCHEMA_PATHS
        and len({row["schema_path"] for row in rows}) == len(paths)
        and len(aliases)
        == prior["archive_aliases_with_one_profiled_xml_member"]
        == ARCHIVE_ALIASES
        and frozenset(
            (row["dataset"], row["revision"], row["path"]) for row in aliases
        )
        == ARCHIVE_IDENTITIES
        and all(
            row["byte_count"] == ARCHIVE_BYTES and row["privacy"] == UNKNOWN
            for row in aliases
        )
        and prior["unassessed_payload_reads_permitted"] is False
        and prior["new_privacy_clearances"] == 0,
        "PBS schema identity, alias set or privacy gate differs",
    )
    patient = _counts(paths, PATIENT)
    contact = _counts(paths, CONTACT)
    specific = sum(bool(SPECIFIC_ID.search(path)) for path in paths)
    # Co-occurrence of an XML id attribute and a patient-related ancestor is
    # a generic structural marker; it is not a patient identifier conclusion.
    generic_id = [
        path
        for path in paths
        if PATIENT.search(path) and path.endswith("/attributes/id")
    ]
    _require(
        sum(patient.values())
        == prior["schema_paths_with_patient_or_person_tokens"]
        and len(generic_id) == GENERIC_ID_PATHS,
        "PBS retained lexical context differs",
    )
    generic_contexts = {
        "patient_element": sum(
            path.endswith("/patient/attributes/id") for path in generic_id
        ),
        "maximum_patient_charge_descendant": sum(
            "/maximum-patient-charge/" in path for path in generic_id
        ),
    }
    _require(
        sum(generic_contexts.values()) == len(generic_id),
        "PBS generic XML identifier contexts differ",
    )
    api = e["api"]["pbs_schedule_api"]
    api_rows = [row for row in privacy if row["sha256"] == SCHEDULE_CSV_SHA]
    event = e["api_event"]
    members = api["members"]
    _require(
        len(api_rows) == 1
        and len(members) == len(set(members)) == API_MEMBERS
        and all(
            isinstance(name, str)
            and name.startswith("tables_as_csv/")
            and name.endswith(".csv")
            for name in members
        )
        and api["sha256"]
        == event["content_id"]
        == event["payload_sha256"]
        == SCHEDULE_CSV_SHA
        and api["bytes"] == api_rows[0]["byte_count"]
        and api["path"] == api_rows[0]["path"]
        and api["dataset"] == api_rows[0]["dataset"] == REIMBURSEMENT
        and api_rows[0]["revision"] == REIMBURSEMENT_REVISION
        and api["acquisition_receipt"] == INPUTS["api_event"][0]
        and event["source_id"] == "au_pbs"
        and event["retrieval"]["status"] == "succeeded"
        and api_rows[0]["privacy"] == UNKNOWN
        and event["sensitivity"]["data_sensitivity"] == "unknown"
        and event["sensitivity"]["personal_data"] == "unknown"
        and event["sensitivity"]["publication"] == "review_required",
        "September PBS API metadata or privacy gate differs",
    )
    return {
        "schema_id": "global-medicines-atlas.pbs-schema-privacy-context",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "inputs": {
            key: {"path": value[0], "sha256": value[1]}
            for key, value in INPUTS.items()
        },
        "april_2026": {
            "archive_sha256": ARCHIVE_SHA,
            "member_sha256": MEMBER_SHA,
            "archive_aliases": [
                {
                    key: row[key]
                    for key in (
                        "dataset",
                        "revision",
                        "path",
                        "sha256",
                        "byte_count",
                        "privacy",
                    )
                }
                for row in aliases
            ],
            "member_schema_paths": len(paths),
            "patient_related_context_counts": patient,
            "contact_related_context_counts": contact,
            "patient_related_ancestor_with_generic_xml_id_context_counts": dict(
                sorted(Counter(_context(p) for p in generic_id).items())
            ),
            "generic_xml_id_path_contexts": generic_contexts,
            "selected_explicit_identifier_label_count": specific,
        },
        "september_2025_api": {
            "dataset": api_rows[0]["dataset"],
            "revision": api_rows[0]["revision"],
            "path": api_rows[0]["path"],
            "sha256": SCHEDULE_CSV_SHA,
            "byte_count": api_rows[0]["byte_count"],
            "recorded_csv_members": len(members),
            "member_names_with_review_tokens": sum(
                bool(API_REVIEW_LABEL.search(name)) for name in members
            ),
            "privacy": UNKNOWN,
        },
        "boundaries": {
            "source_values_or_unassessed_payloads_read": False,
            "participant_or_cohort_data_accessed": False,
            "schema_path_matches_interpreted_as_people_or_identifiers": False,
            "selected_lexical_markers_are_exhaustive": False,
            "archive_privacy_cleared": False,
            "unassessed_payload_reads_authorized": False,
            "dataset_added_or_published": False,
        },
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    return reconcile({
        key: bounded.read_bound_metadata(root, *ref)
        for key, ref in INPUTS.items()
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    path = ROOT / OUTPUT
    expected = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.check:
        _require(
            path.is_file() and path.read_bytes() == expected,
            "PBS privacy context is stale",
        )
    else:
        path.write_bytes(expected)
    print("PBS schema metadata checked; privacy remains unassessed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
