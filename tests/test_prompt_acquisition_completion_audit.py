"""The 36 acquisition prompts remain tied to observable live evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from scripts.build_prompt_acquisition_completion_audit import build

from global_medicines_atlas.source_expansion import expansion_tracks

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "quality/qualifications/prompt-acquisition-completion-audit.json"
QUEUE = ROOT / "quality/qualifications/bronze-source-landing-queue.json"
MEASURED = ROOT / "quality/qualifications/stable-v1-measured-coverage.json"
SCHEMA = ROOT / "schemas/prompt-acquisition-completion-audit-v1.json"


def _audit() -> dict[str, Any]:
    return json.loads(AUDIT.read_text(encoding="utf-8"))


def test_audit_is_generated_from_all_36_locked_prompts() -> None:
    audit = _audit()
    tracks = expansion_tracks()
    assert audit == build()
    validator: Any = Draft202012Validator(
        json.loads(SCHEMA.read_text(encoding="utf-8"))
    )
    validator.validate(audit)
    assert audit["prompt_count"] == len(tracks) == 36
    assert [entry["prompt_id"] for entry in audit["prompts"]] == list(
        range(1, 37)
    )
    assert {
        entry["prompt_id"]: entry["source_ids"] for entry in audit["prompts"]
    } == {track.track_id: list(track.source_ids) for track in tracks}


def test_live_qualification_is_counted_without_claiming_prompt_completion() -> (
    None
):
    audit = _audit()
    measured = json.loads(MEASURED.read_text(encoding="utf-8"))["body"]
    assert measured["totals"]["live_qualified_sources"] == 0
    assert audit["live_qualified_source_count"] == 5
    assert audit["live_complete_prompt_count"] == 0
    assert audit["program_completion"] == "incomplete_live_acquisition"
    assert all(not entry["live_complete"] for entry in audit["prompts"])
    assert all(
        entry["sources_without_live_evidence"] for entry in audit["prompts"]
    )
    assert all(
        set(entry["fixture_qualified_source_ids"]).isdisjoint(
            entry["live_qualified_source_ids"]
        )
        for entry in audit["prompts"]
    )
    live = {
        source_id
        for entry in audit["prompts"]
        for source_id in entry["live_qualified_source_ids"]
    }
    assert live == {
        "us-openfda-enforcement",
        "us-openfda-faers",
        "us-openfda-ndc",
        "us-openfda-nsde",
    }


def test_every_prompt_source_has_exactly_one_current_queue_state() -> None:
    audit = _audit()
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    current = {item["source_id"]: item["state"] for item in queue["items"]}
    for entry in audit["prompts"]:
        assert entry["source_count"] == len(entry["source_ids"])
        assert entry["queue_states"] == {
            source_id: current.get(source_id, "derived_reconciliation_output")
            for source_id in entry["source_ids"]
        }
        assert (
            sum(entry["queue_state_counts"].values()) == entry["source_count"]
        )


def test_blockers_are_actionable_and_reconciliation_stays_incomplete() -> None:
    audit = _audit()
    assert audit["queue_state_counts"] == {
        "credentialed_and_excluded": 18,
        "landed_and_evidenced": 16,
        "manual_only_documented_acquisition": 93,
        "not_yet_implemented": 0,
        "rights_blocked": 45,
        "superseded_by_reused_source": 0,
        "temporarily_unavailable": 0,
    }
    for entry in audit["prompts"]:
        assert entry["next_actions"]
        assert "catalogue_complete" not in entry["completion_state"]
        if "landed_and_evidenced" in entry["queue_states"].values():
            assert "fixture_only_is_not_live" in entry["blocker_categories"]
    reconciliation = audit["prompts"][-1]
    assert reconciliation["prompt_id"] == 36
    assert reconciliation["completion_state"] == (
        "reconciliation_generated_but_live_program_incomplete"
    )
