"""The 36 acquisition prompts remain tied to observable live evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from scripts import build_prompt_acquisition_completion_audit as audit_mod
from scripts.build_prompt_acquisition_completion_audit import build

from global_medicines_atlas.source_expansion import expansion_tracks

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "quality/qualifications/prompt-acquisition-completion-audit.json"
QUEUE = ROOT / "quality/qualifications/bronze-source-landing-queue.json"
MEASURED = ROOT / "quality/qualifications/stable-v1-measured-coverage.json"
SCHEMA = ROOT / "schemas/prompt-acquisition-completion-audit-v1.json"
RECORD_QUALIFICATION = (
    ROOT / "quality/qualifications/us-live-bronze-records-20260820.json"
)


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


def test_live_qualification_completes_only_the_verified_nsde_prompt() -> None:
    audit = _audit()
    measured = json.loads(MEASURED.read_text(encoding="utf-8"))["body"]
    assert measured["totals"]["live_qualified_sources"] == 0
    assert audit["live_qualified_source_count"] == 6
    assert audit["live_complete_prompt_count"] == 1
    assert audit["program_completion"] == "incomplete_live_acquisition"
    complete = [entry for entry in audit["prompts"] if entry["live_complete"]]
    assert [entry["prompt_id"] for entry in complete] == [19]
    assert complete[0]["live_qualified_source_ids"] == [
        "us-fda-nsde",
        "us-openfda-nsde",
    ]
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
        "us-fda-nsde",
    }

    orange = audit["prompts"][15]
    assert orange["prompt_id"] == 16
    assert orange["live_complete"] is False
    assert orange["live_qualified_source_ids"] == []


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


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda raw: raw.update(evidence_class="synthetic_fixture_only"),
            "wrong evidence class",
        ),
        (
            lambda raw: raw["prompt_audit_qualified_source_ids"].append(
                "us-fda-orange-book"
            ),
            "exceeds reviewed source scope",
        ),
        (
            lambda raw: raw.update(recovered_source_record_projection_count=7),
            "byte-identical clean-room recovery",
        ),
        (
            lambda raw: raw.update(
                source_record_parquet_pairs_byte_identical=7
            ),
            "byte-identical clean-room recovery",
        ),
        (
            lambda raw: raw.update(record_products=[]),
            "lacks a nonempty record product",
        ),
        (
            lambda raw: raw.update(external_publication_performed=True),
            "internal-only boundary",
        ),
        (
            lambda raw: raw.update(public_release_authorized=True),
            "internal-only boundary",
        ),
        (
            lambda raw: raw.update(coverage_complete=True),
            "internal-only boundary",
        ),
    ],
)
def test_record_qualification_fails_closed_on_scope_or_evidence_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
    message: str,
) -> None:
    raw = json.loads(RECORD_QUALIFICATION.read_bytes())
    mutate(raw)
    unsafe = tmp_path / "unsafe-record-qualification.json"
    unsafe.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(audit_mod, "US_RECORD_QUALIFICATION", unsafe)

    with pytest.raises(ValueError, match=message):
        audit_mod._qualified_us_record_sources()


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
        if entry["live_complete"]:
            assert entry["next_actions"] == []
        else:
            assert entry["next_actions"]
        assert "catalogue_complete" not in entry["completion_state"]
        if "landed_and_evidenced" in entry["queue_states"].values():
            assert "fixture_only_is_not_live" in entry["blocker_categories"]
    reconciliation = audit["prompts"][-1]
    assert reconciliation["prompt_id"] == 36
    assert reconciliation["completion_state"] == (
        "reconciliation_generated_but_live_program_incomplete"
    )
