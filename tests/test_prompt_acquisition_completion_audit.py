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
NDC_QUALIFICATION = (
    ROOT / "quality/qualifications/ndc-directory-live-corpus-20260821.json"
)
REMS_QUALIFICATION = (
    ROOT / "quality/qualifications/fda-rems-live-corpus-20260821.json"
)
FAERS_QUALIFICATION = (
    ROOT / "quality/qualifications/faers-live-corpus-20260821.json"
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


def test_live_qualification_completes_verified_prompts() -> None:
    audit = _audit()
    measured = json.loads(MEASURED.read_text(encoding="utf-8"))["body"]
    assert measured["totals"]["live_qualified_sources"] == 0
    assert audit["live_qualified_source_count"] == 11
    assert audit["live_complete_prompt_count"] == 6
    assert audit["program_completion"] == "incomplete_live_acquisition"
    complete = [entry for entry in audit["prompts"] if entry["live_complete"]]
    assert [entry["prompt_id"] for entry in complete] == [
        12,
        13,
        15,
        17,
        19,
        25,
    ]
    assert complete[0]["live_qualified_source_ids"] == [
        "us-fda-faers",
        "us-openfda-faers",
    ]
    assert complete[1]["live_qualified_source_ids"] == [
        "us-openfda-enforcement",
        "us-fda-recalls-notices",
    ]
    assert complete[2]["live_qualified_source_ids"] == ["us-fda-rems"]
    assert complete[3]["live_qualified_source_ids"] == [
        "us-openfda-ndc",
        "us-fda-ndc-directory",
    ]
    assert complete[4]["live_qualified_source_ids"] == [
        "us-fda-nsde",
        "us-openfda-nsde",
    ]
    assert complete[5]["live_qualified_source_ids"] == ["eu-union-register"]
    fixture_and_live = {
        source_id
        for entry in audit["prompts"]
        for source_id in set(entry["fixture_qualified_source_ids"])
        & set(entry["live_qualified_source_ids"])
    }
    assert fixture_and_live == {"eu-union-register"}
    live = {
        source_id
        for entry in audit["prompts"]
        for source_id in entry["live_qualified_source_ids"]
    }
    assert live == {
        "eu-union-register",
        "us-openfda-enforcement",
        "us-openfda-faers",
        "us-openfda-ndc",
        "us-openfda-nsde",
        "us-fda-ndc-directory",
        "us-fda-faers",
        "us-fda-nsde",
        "us-fda-rems",
        "us-fda-recalls-notices",
    }

    orange = audit["prompts"][15]
    assert orange["prompt_id"] == 16
    assert orange["live_complete"] is False
    assert orange["live_qualified_source_ids"] == []
    assert orange["queue_states"] == {
        "us-fda-orange-book": "temporarily_unavailable"
    }
    assert orange["blocker_categories"] == ["temporarily_unavailable"]
    assert orange["next_actions"] == [
        "record a dated availability observation and retry without treating absence as negative evidence"
    ]


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


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda raw: raw.update(current_bulk_surface_complete=False),
            "reviewed scope",
        ),
        (
            lambda raw: raw.update(historical_snapshot_coverage_claimed=True),
            "reviewed scope",
        ),
        (
            lambda raw: raw.update(acquisition_failed_count=1),
            "incomplete acquisition",
        ),
        (
            lambda raw: raw.update(recovered_source_record_projection_count=4),
            "lack recovery evidence",
        ),
        (
            lambda raw: raw.update(archive_checksum_verified=False),
            "lack recovery evidence",
        ),
        (
            lambda raw: raw["prompt_audit_qualified_source_ids"].append(
                "us-fda-orange-book"
            ),
            "exceeds reviewed source scope",
        ),
    ],
)
def test_ndc_qualification_fails_closed_on_scope_or_evidence_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
    message: str,
) -> None:
    raw = json.loads(NDC_QUALIFICATION.read_bytes())
    mutate(raw)
    unsafe = tmp_path / "unsafe-ndc-qualification.json"
    unsafe.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(audit_mod, "NDC_RECORD_QUALIFICATION", unsafe)

    with pytest.raises(ValueError, match=message):
        audit_mod._qualified_ndc_record_sources()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda raw: raw.update(prompt_complete=False),
            "reviewed scope",
        ),
        (
            lambda raw: raw.update(current_documents_acquired=826),
            "document coverage",
        ),
        (
            lambda raw: raw["unavailable_documents"][0].update(
                observed_http_status=503
            ),
            "document coverage",
        ),
        (
            lambda raw: raw.update(
                source_record_parquet_pairs_byte_identical=3
            ),
            "lack recovery evidence",
        ),
        (
            lambda raw: raw["prompt_audit_qualified_source_ids"].append(
                "us-fda-orange-book"
            ),
            "exceeds reviewed source scope",
        ),
    ],
)
def test_rems_qualification_fails_closed_on_scope_or_evidence_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
    message: str,
) -> None:
    raw = json.loads(REMS_QUALIFICATION.read_bytes())
    mutate(raw)
    unsafe = tmp_path / "unsafe-rems-qualification.json"
    unsafe.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(audit_mod, "REMS_RECORD_QUALIFICATION", unsafe)

    with pytest.raises(ValueError, match=message):
        audit_mod._qualified_rems_record_sources()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda raw: raw.update(evidence_class="synthetic_fixture_only"),
            "wrong evidence class",
        ),
        (
            lambda raw: raw.update(internal_retention_authorized=False),
            "internal-only boundary",
        ),
        (
            lambda raw: raw.update(public_release_authorized=True),
            "internal-only boundary",
        ),
        (
            lambda raw: raw.update(quarter_coverage_complete=False),
            "incomplete quarter coverage",
        ),
        (
            lambda raw: raw.update(last_release="2026-Q1"),
            "incomplete quarter coverage",
        ),
        (
            lambda raw: raw.update(release_failed_count=1),
            "incomplete acquisition",
        ),
        (
            lambda raw: raw.update(recovered_source_record_projection_count=89),
            "lack recovery evidence",
        ),
        (
            lambda raw: raw.update(archive_checksum_verified=False),
            "lack recovery evidence",
        ),
        (
            lambda raw: raw["prompt_audit_qualified_source_ids"].append(
                "us-fda-orange-book"
            ),
            "exceeds reviewed source scope",
        ),
    ],
)
def test_faers_qualification_fails_closed_on_scope_or_evidence_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
    message: str,
) -> None:
    raw = json.loads(FAERS_QUALIFICATION.read_bytes())
    mutate(raw)
    unsafe = tmp_path / "unsafe-faers-qualification.json"
    unsafe.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(audit_mod, "FAERS_RECORD_QUALIFICATION", unsafe)

    with pytest.raises(ValueError, match=message):
        audit_mod._qualified_faers_record_sources()


def test_blockers_are_actionable_and_reconciliation_stays_incomplete() -> None:
    audit = _audit()
    assert audit["queue_state_counts"] == {
        "credentialed_and_excluded": 18,
        "landed_and_evidenced": 21,
        "manual_only_documented_acquisition": 91,
        "not_yet_implemented": 0,
        "rights_blocked": 41,
        "superseded_by_reused_source": 0,
        "temporarily_unavailable": 1,
    }
    for entry in audit["prompts"]:
        if entry["live_complete"]:
            assert entry["next_actions"] == []
        else:
            assert entry["next_actions"]
        assert "catalogue_complete" not in entry["completion_state"]
        missing_states = {
            entry["queue_states"][source_id]
            for source_id in entry["sources_without_live_evidence"]
        }
        if "landed_and_evidenced" in missing_states:
            assert "fixture_only_is_not_live" in entry["blocker_categories"]
    reconciliation = audit["prompts"][-1]
    assert reconciliation["prompt_id"] == 36
    assert reconciliation["completion_state"] == (
        "reconciliation_generated_but_live_program_incomplete"
    )
