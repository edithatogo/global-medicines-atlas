#!/usr/bin/env python3
"""Reconcile an official MBS release note with an aggregate-only comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
NOTES_PATH = ROOT / (
    "quality/qualifications/"
    "australian-mbs-official-release-change-notes-20261018.json"
)
COMPARISON_PATH = ROOT / (
    "quality/qualifications/"
    "australian-m109-july-august-predecessor-comparison-20261018.json"
)
OUTPUT_PATH = ROOT / (
    "quality/qualifications/"
    "australian-m109-release-note-delta-reconciliation-20261018.json"
)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return cast("dict[str, Any]", value)


def _release_note(notes: dict[str, Any], release_name: str) -> dict[str, Any]:
    observations = notes.get("release_observations")
    if not isinstance(observations, list):
        raise TypeError("release observations must be a list")
    observation_values = cast("list[object]", observations)
    matches: list[dict[str, Any]] = []
    for item in observation_values:
        observation = _mapping(item, "release observation")
        if observation.get("release") == release_name:
            matches.append(observation)
    if len(matches) != 1:
        raise ValueError("release observation must be unique")
    return matches[0]


def _comparison_release(
    comparison: dict[str, Any], source_era: str
) -> dict[str, Any]:
    releases = comparison.get("releases")
    if not isinstance(releases, list):
        raise TypeError("comparison releases must be a list")
    release_values = cast("list[object]", releases)
    matches: list[dict[str, Any]] = []
    for item in release_values:
        release = _mapping(item, "comparison release")
        if release.get("source_era") == source_era:
            matches.append(release)
    if len(matches) != 1:
        raise ValueError("comparison release must be unique")
    return matches[0]


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def build_reconciliation(  # ruff: ignore[too-many-locals] - validate one bounded evidence pair
    *,
    notes: object,
    comparison: object,
    notes_sha256_bytes: bytes,
    comparison_sha256_bytes: bytes,
) -> dict[str, Any]:
    """Bind official release statements to value-free aggregate evidence."""
    note_report = _mapping(notes, "official release notes")
    comparison_report = _mapping(comparison, "predecessor comparison")
    if (
        note_report.get("schema_id")
        != "global-medicines-atlas.australian-mbs-official-release-change-notes"
        or note_report.get("schema_version") != 1
    ):
        raise ValueError("official release notes schema is unsupported")
    if (
        comparison_report.get("schema_id")
        != "global-medicines-atlas.mbs-predecessor-comparison"
        or comparison_report.get("schema_version") != 1
        or comparison_report.get("status") != "aggregate_comparison_complete"
    ):
        raise ValueError("predecessor comparison is unsupported or incomplete")

    july_note = _release_note(note_report, "MBS July 2026 XML")
    august_note = _release_note(note_report, "MBS August 2026 XML")
    july_release = _comparison_release(comparison_report, "2026-07-01")
    august_release = _comparison_release(comparison_report, "2026-08-01")
    if july_note.get("release_date") != "2026-05-28" or august_note.get(
        "unchanged_from_release_date"
    ) != july_note.get("release_date"):
        raise ValueError("official predecessor release date is not bound")
    if july_note.get("source_url") != july_release.get(
        "official_download_page"
    ) or august_note.get("source_url") != august_release.get(
        "official_download_page"
    ):
        raise ValueError("official note pages do not match comparison releases")
    if (
        july_note.get("xml_filename") != "MBS-XML-20260701.XML"
        or august_note.get("xml_filename") != "MBS-XML-20260801.XML"
        or august_note.get("change_class")
        != "new_item_with_no_further_change_from_prior_published_release"
        or not isinstance(august_note.get("new_item_code"), str)
    ):
        raise ValueError("official release claim is incomplete")

    raw_counts = _mapping(
        comparison_report.get("comparison"), "comparison counts"
    )
    added = _nonnegative_int(
        raw_counts.get("added_record_count"), "added count"
    )
    removed = _nonnegative_int(
        raw_counts.get("removed_record_count"), "removed count"
    )
    changed = _nonnegative_int(
        raw_counts.get("changed_record_count"), "changed count"
    )
    matched = _nonnegative_int(
        raw_counts.get("matched_record_count"), "matched count"
    )
    raw_fields = raw_counts.get("changed_field_counts")
    if not isinstance(raw_fields, list):
        raise TypeError("changed field counts must be a list")
    field_values = cast("list[object]", raw_fields)
    field_counts: list[dict[str, Any]] = []
    for value in field_values:
        field = _mapping(value, "changed field count")
        name = field.get("native_field")
        if not isinstance(name, str) or not name:
            raise ValueError("changed field must have a native field name")
        field_counts.append({
            "native_field": name,
            "count": _nonnegative_int(field.get("count"), name),
        })

    status = (
        "aggregate_shape_matches_named_addition_unverified"
        if added == 1 and removed == 0 and changed == 0
        else "unresolved_observed_delta"
    )
    report: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.australian-m109-release-note-delta-reconciliation",
        "schema_version": 1,
        "requirement": "M-109",
        "status": status,
        "inputs": {
            "official_release_notes": {
                "path": NOTES_PATH.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(notes_sha256_bytes).hexdigest(),
            },
            "predecessor_comparison": {
                "path": COMPARISON_PATH.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(comparison_sha256_bytes).hexdigest(),
                "exact_commit": comparison_report.get("exact_commit"),
                "july_archive_revision": july_release.get("archive_revision"),
                "august_archive_revision": august_release.get(
                    "archive_revision"
                ),
            },
        },
        "official_statement": {
            "july_release_id": july_release.get("release_id"),
            "july_release_date": july_note["release_date"],
            "august_release_id": august_release.get("release_id"),
            "august_new_item_claim_present": True,
            "august_unchanged_from_release_date": august_note[
                "unchanged_from_release_date"
            ],
            "named_item_identity_verified": False,
        },
        "comparison": {
            "matched_record_count": matched,
            "added_record_count": added,
            "removed_record_count": removed,
            "changed_record_count": changed,
            "changed_field_counts": field_counts,
        },
        "interpretation": (
            "The official August page claims one named new item and no other XML "
            "changes from the July release published 28 May. The aggregate "
            "comparison reports the counts above but does not retain identities "
            "or field values. The discrepancy remains unresolved; no field "
            "meaning or release equivalence is inferred."
        ),
        "boundaries": {
            "source_values_retained": False,
            "source_identifiers_emitted": False,
            "source_payloads_requested_by_this_reconciliation": False,
            "rights_changed": False,
            "field_semantics_accepted": False,
            "m109_accepted": False,
        },
    }
    canonical = json.dumps(
        report, sort_keys=True, separators=(",", ":")
    ).encode()
    report["canonical_sha256"] = hashlib.sha256(canonical).hexdigest()
    report["canonical_byte_count"] = len(canonical)
    return report


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    return _mapping(value, path.name), raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notes", type=Path, default=NOTES_PATH)
    parser.add_argument("--comparison", type=Path, default=COMPARISON_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    notes, notes_bytes = _read_json(args.notes)
    comparison, comparison_bytes = _read_json(args.comparison)
    report = build_reconciliation(
        notes=notes,
        comparison=comparison,
        notes_sha256_bytes=notes_bytes,
        comparison_sha256_bytes=comparison_bytes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
