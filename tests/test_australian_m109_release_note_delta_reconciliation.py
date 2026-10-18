"""Keep release-page change claims separate from aggregate comparisons."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from scripts.reconcile_mbs_release_note_comparison import (
    build_reconciliation,
)

ROOT = Path(__file__).resolve().parents[1]
NOTES_PATH = (
    ROOT
    / "quality/qualifications/australian-mbs-official-release-change-notes-20261018.json"
)
COMPARISON_PATH = (
    ROOT
    / "quality/qualifications/australian-m109-july-august-predecessor-comparison-20261018.json"
)
REPORT_PATH = (
    ROOT / "quality/qualifications/"
    "australian-m109-release-note-delta-reconciliation-20261018.json"
)


def _inputs() -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    notes_bytes = NOTES_PATH.read_bytes()
    comparison_bytes = COMPARISON_PATH.read_bytes()
    return (
        json.loads(notes_bytes),
        json.loads(comparison_bytes),
        notes_bytes,
        comparison_bytes,
    )


def test_current_release_statement_delta_is_explicit_and_value_free() -> None:
    notes, comparison, notes_bytes, comparison_bytes = _inputs()

    report = build_reconciliation(
        notes=notes,
        comparison=comparison,
        notes_sha256_bytes=notes_bytes,
        comparison_sha256_bytes=comparison_bytes,
    )

    assert report["status"] == "unresolved_observed_delta"
    assert report["comparison"]["changed_record_count"] == 5445
    assert report["comparison"]["added_record_count"] == 1
    assert report["comparison"]["removed_record_count"] == 0
    assert report["official_statement"]["august_new_item_claim_present"] is True
    assert report["official_statement"]["july_release_id"] == (
        "MBS-XML-20260701"
    )
    assert report["official_statement"]["named_item_identity_verified"] is False
    assert report["boundaries"]["source_values_retained"] is False
    assert report["boundaries"]["source_identifiers_emitted"] is False
    assert report["boundaries"]["m109_accepted"] is False
    rendered = json.dumps(report)
    assert "73331" not in rendered
    assert "10001" not in rendered
    assert "10.00" not in rendered
    canonical = dict(report)
    digest = canonical.pop("canonical_sha256")
    byte_count = canonical.pop("canonical_byte_count")
    payload = json.dumps(
        canonical, sort_keys=True, separators=(",", ":")
    ).encode()
    assert digest == hashlib.sha256(payload).hexdigest()
    assert byte_count == len(payload)


def test_zero_changed_rows_still_does_not_verify_named_new_item_identity() -> (
    None
):
    notes, comparison, notes_bytes, comparison_bytes = _inputs()
    comparison["comparison"]["changed_record_count"] = 0
    comparison["comparison"]["changed_field_counts"] = []
    report = build_reconciliation(
        notes=notes,
        comparison=comparison,
        notes_sha256_bytes=notes_bytes,
        comparison_sha256_bytes=comparison_bytes,
    )

    assert (
        report["status"] == "aggregate_shape_matches_named_addition_unverified"
    )
    assert report["official_statement"]["named_item_identity_verified"] is False
    assert report["boundaries"]["m109_accepted"] is False


def test_report_is_reproducible_from_exact_value_free_inputs() -> None:
    notes, comparison, notes_bytes, comparison_bytes = _inputs()
    generated = build_reconciliation(
        notes=notes,
        comparison=comparison,
        notes_sha256_bytes=notes_bytes,
        comparison_sha256_bytes=comparison_bytes,
    )

    assert json.loads(REPORT_PATH.read_text()) == generated


def test_report_rejects_an_unbound_official_predecessor_page() -> None:
    notes, comparison, notes_bytes, comparison_bytes = _inputs()
    july_note = next(
        item
        for item in notes["release_observations"]
        if item["release"] == "MBS July 2026 XML"
    )
    july_note["source_url"] = "https://example.invalid/wrong-page"

    with pytest.raises(ValueError, match="official note pages"):
        build_reconciliation(
            notes=notes,
            comparison=comparison,
            notes_sha256_bytes=notes_bytes,
            comparison_sha256_bytes=comparison_bytes,
        )
