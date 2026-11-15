"""Reconcile retained PBS acquisition classifications to an existing inventory.

Only repository metadata is read. Matching SHA-256 values are not privacy
clearance, size verification, rights transfer or authorization for payload use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from operator import itemgetter
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_pbs_member_privacy_triage as triage
import scripts.qualify_pbs_schema_privacy_context as context

ROOT = Path(__file__).resolve().parents[1]
EVENT_DIRECTORY = Path("quality/bronze/imported-acquisitions/au-pbs")
OUTPUT = "quality/qualifications/australian-pbs-acquisition-privacy-coverage-20261115.json"
EXPECTED_EVENTS = 1702
EXPECTED_MATCHED_PATHS = 1703
EXPECTED_UNMATCHED_PATHS = 19
EVENT_SCHEMA_VERSION = 3


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _events(
    root: Path,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    files = sorted((root / EVENT_DIRECTORY).glob("*.json"))
    _require(
        len(files) == EXPECTED_EVENTS, "PBS acquisition event count differs"
    )
    by_content: dict[str, dict[str, Any]] = {}
    manifest: list[dict[str, str]] = []
    for path in files:
        raw = path.read_bytes()
        event = json.loads(raw)
        digest = event["payload_sha256"]
        _require(
            event["schema_id"]
            == "global-medicines-atlas.bronze-acquisition-event"
            and event["schema_version"] == EVENT_SCHEMA_VERSION
            and event["evidence_class"] == "historical"
            and event["source_id"] == "au_pbs"
            and event["acquisition_id"] == path.stem
            and event["content_id"] == digest
            and event["retrieval"]["status"] == "succeeded"
            and event["sensitivity"]["data_sensitivity"] == "unknown"
            and event["sensitivity"]["personal_data"] == "unknown"
            and event["sensitivity"]["publication"] == "review_required"
            and digest not in by_content,
            "PBS event identity or recorded privacy state differs",
        )
        by_content[digest] = event
        manifest.append({
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha(raw),
        })
    return by_content, manifest


def reconcile(
    inventory: dict[str, Any],
    events: dict[str, dict[str, Any]],
    manifest: list[dict[str, str]],
) -> dict[str, Any]:
    """Summarize an exact digest-only join and preserve all privacy blocks."""
    rows = [
        row
        for row in bounded.metadata_rows(inventory["objects"])
        if row["batch"].startswith(("pbs_", "reimbursement_"))
        and row["privacy"] == context.UNKNOWN
    ]
    matched = [row for row in rows if row["sha256"] in events]
    unmatched = [row for row in rows if row["sha256"] not in events]
    _require(
        len(rows) == triage.EXPECTED_OBJECTS
        and len(matched) == EXPECTED_MATCHED_PATHS
        and len(unmatched) == EXPECTED_UNMATCHED_PATHS
        and len({row["sha256"] for row in matched})
        == len(events)
        == EXPECTED_EVENTS
        and len(manifest) == EXPECTED_EVENTS,
        "PBS acquisition privacy coverage differs",
    )
    return {
        "schema_id": "global-medicines-atlas.pbs-acquisition-privacy-coverage",
        "schema_version": 1,
        "recorded_on": "2026-11-15",
        "inventory": {
            "path": context.INPUTS["privacy"][0],
            "sha256": context.INPUTS["privacy"][1],
        },
        "event_manifest": {
            "directory": EVENT_DIRECTORY.as_posix(),
            "file_count": len(manifest),
            "sorted_path_and_file_sha256_manifest_sha256": _sha(
                _canonical(manifest)
            ),
        },
        "matched": {
            "paths": len(matched),
            "distinct_sha256_values": len(events),
            "batches": dict(
                sorted(Counter(row["batch"] for row in matched).items())
            ),
            "event_sensitivity": "unknown",
            "event_personal_data": "unknown",
            "event_publication": "review_required",
            "join": "sha256_only_event_does_not_supply_byte_count",
        },
        "unmatched_in_scoped_event_directory": {
            "paths": len(unmatched),
            "batches": dict(
                sorted(Counter(row["batch"] for row in unmatched).items())
            ),
            "identities": [
                {
                    key: row[key]
                    for key in (
                        "dataset",
                        "revision",
                        "path",
                        "sha256",
                        "byte_count",
                        "batch",
                    )
                }
                for row in sorted(unmatched, key=itemgetter("dataset", "path"))
            ],
        },
        "boundaries": {
            "matched_events_establish_non_sensitive_content": False,
            "unmatched_means_no_evidence_anywhere": False,
            "privacy_clearances_added": 0,
            "unassessed_payload_or_participant_data_read": False,
            "dataset_acquired_or_published": False,
        },
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    inventory = bounded.read_bound_metadata(root, *context.INPUTS["privacy"])
    events, manifest = _events(root)
    return reconcile(inventory, events, manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), sort_keys=True, indent=2) + "\n").encode()
    path = ROOT / OUTPUT
    if args.check:
        _require(
            path.is_file() and path.read_bytes() == raw, "PBS coverage is stale"
        )
    else:
        path.write_bytes(raw)
    print(
        "PBS acquisition privacy metadata reconciled; all paths remain unassessed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
