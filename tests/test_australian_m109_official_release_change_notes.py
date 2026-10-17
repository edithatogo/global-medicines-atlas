"""Keep MBS release-change evidence separate from schema qualification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

REPORT = Path(
    "quality/qualifications/australian-mbs-official-release-change-notes-20261018.json"
)
FIELD_GUIDE_REPORT = Path(
    "quality/qualifications/australian-mbs-field-guide-semantic-history-20261018.json"
)
REGISTER = Path("docs/qualification/australian-m109-source-era-register.md")


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_official_release_notes_bind_dates_and_corrections_without_inference() -> (
    None
):
    report = _json(REPORT)
    assert report["schema_id"] == (
        "global-medicines-atlas.australian-mbs-official-release-change-notes"
    )
    assert (
        report["status"]
        == "release_changes_observed_semantic_mapping_unqualified"
    )

    observations = cast("list[dict[str, Any]]", report["release_observations"])
    assert len(observations) == 3
    assert all(
        observation["source_payload_requested"] is False
        and observation["source_payload_read"] is False
        for observation in observations
    )
    assert all(
        observation["source_url"].startswith("https://www.mbsonline.gov.au/")
        for observation in observations
    )

    march, july, august = observations
    assert march["xml_filename"] == "MBS-XML-20260301-version 2.XML"
    assert march["release_date"] == "2026-02-10"
    assert march["effective_date"] == "2026-03-01"
    assert march["corrected_item_codes"] == [
        "2484",
        "2485",
        "2486",
        "2487",
        "2488",
        "2489",
        "2490",
        "2491",
        "2492",
        "2493",
        "2494",
        "2495",
    ]
    assert march["column_labels"] == ["Y", "AB", "AC"]
    assert march["xml_element_mapping"] == "not established by the release page"

    assert july["xml_filename"] == "MBS-XML-20260701.XML"
    assert july["release_date"] == "2026-05-28"
    assert july["effective_date"] == "2026-07-01"
    assert july["corrected_item_codes"] == [
        "5200",
        "5203",
        "5207",
        "5208",
        "5209",
    ]
    assert (
        "Schedule Fee and corresponding 100% benefit"
        in july["source_statement"]
    )

    assert august["xml_filename"] == "MBS-XML-20260801.XML"
    assert august["release_date"] == "2026-07-29"
    assert august["effective_date"] == "2026-08-01"
    assert august["new_item_code"] == "73331"
    assert august["unchanged_from_release_date"] == "2026-05-28"

    limits = cast("dict[str, Any]", report["qualification_boundaries"])
    assert limits["field_guide_conflict_resolved"] is False
    assert limits["xml_element_mapping_selected"] is False
    assert limits["release_semantics_qualified"] is False
    assert limits["rights_decision_changed"] is False
    assert limits["m109_accepted"] is False

    existing = _json(FIELD_GUIDE_REPORT)
    assert existing["status"] == (
        "documented_wording_delta_and_source_conflict_observed_history_gap_open"
    )
    documentation = REGISTER.read_text(encoding="utf-8")
    assert (
        "australian-mbs-official-release-change-notes-20261018.json"
        in documentation
    )
