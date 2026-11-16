"""PBS metadata triage preserves the member and privacy boundaries."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import scripts.qualify_pbs_acquisition_privacy_coverage as coverage
import scripts.qualify_pbs_member_privacy_triage as triage
import scripts.qualify_pbs_schema_privacy_context as qualification
from scripts.qualify_m112_existing_reimbursement_batch import (
    read_bound_metadata,
)


@pytest.fixture(scope="module")
def evidence() -> dict[str, dict[str, Any]]:
    return {
        key: read_bound_metadata(qualification.ROOT, *ref)
        for key, ref in qualification.INPUTS.items()
    }


def test_schema_context_is_member_scoped_and_does_not_clear_privacy() -> None:
    result = qualification.build()
    april = result["april_2026"]
    assert april["member_schema_paths"] == 5_163
    assert april["patient_related_context_counts"] == {
        "RDF": 7,
        "prescribing-texts-list": 22,
        "previous-list": 91,
        "schedule": 104,
    }
    assert april["contact_related_context_counts"] == {
        "organisations-list": 22,
        "previous-list": 22,
    }
    assert april["generic_xml_id_path_contexts"] == {
        "patient_element": 2,
        "maximum_patient_charge_descendant": 6,
    }
    assert april["selected_explicit_identifier_label_count"] == 0
    assert len(april["archive_aliases"]) == 2
    assert all(
        row["privacy"] == qualification.UNKNOWN
        for row in april["archive_aliases"]
    )
    assert result["september_2025_api"]["recorded_csv_members"] == 33
    assert result["september_2025_api"]["member_names_with_review_tokens"] == 8
    assert result["september_2025_api"]["privacy"] == qualification.UNKNOWN
    assert not any(result["boundaries"].values())


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("schema_digest", "schema identity"),
        ("duplicate_path", "schema identity"),
        ("alias_disposition", "schema identity"),
        ("alias_identity", "schema identity"),
        ("read_gate", "schema identity"),
        ("api_member", "API metadata"),
        ("api_revision", "API metadata"),
        ("api_sensitivity", "API metadata"),
    ],
)
def test_misbound_metadata_or_changed_gate_fails_closed(
    evidence: dict[str, dict[str, Any]], mutation: str, message: str
) -> None:
    altered = copy.deepcopy(evidence)
    if mutation == "schema_digest":
        altered["schema"]["member_sha256"] = "0" * 64
    elif mutation == "duplicate_path":
        altered["schema"]["paths"][1]["schema_path"] = altered["schema"][
            "paths"
        ][0]["schema_path"]
    elif mutation == "alias_disposition":
        next(
            x
            for x in altered["privacy"]["objects"]
            if x["sha256"] == qualification.ARCHIVE_SHA
        )["privacy"] = "cleared"
    elif mutation == "alias_identity":
        next(
            x
            for x in altered["privacy"]["objects"]
            if x["sha256"] == qualification.ARCHIVE_SHA
        )["revision"] = "0" * 40
    elif mutation == "read_gate":
        altered["readiness"]["pbs_privacy"][
            "unassessed_payload_reads_permitted"
        ] = True
    elif mutation == "api_member":
        altered["api"]["pbs_schedule_api"]["members"].pop()
    elif mutation == "api_revision":
        next(
            x
            for x in altered["privacy"]["objects"]
            if x["sha256"] == qualification.SCHEDULE_CSV_SHA
        )["revision"] = "0" * 40
    else:
        altered["api_event"]["sensitivity"]["personal_data"] = "none"
    with pytest.raises(ValueError, match=message):
        qualification.reconcile(altered)


@pytest.fixture(scope="module")
def triage_evidence() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = triage.ROOT
    return (
        triage.bounded.read_bound_metadata(
            root, *triage.context.INPUTS["privacy"]
        ),
        triage.bounded.read_bound_metadata(root, *triage.context.INPUTS["api"]),
        triage.bounded.read_bound_metadata(root, *triage.CONTEXT),
    )


def test_all_members_and_objects_remain_unassessed() -> None:
    result = triage.build()
    inventory = result["unassessed_inventory"]
    assert inventory["objects"] == 1722
    assert inventory["distinct_digest_and_size_pairs"] == 1721
    assert inventory["paths_in_duplicate_group"] == 2
    assert inventory["privacy_clearances"] == 0
    archive = result["september_2025_archive"]
    assert len(archive["members"]) == 33
    assert archive["members_with_review_labels"] == 8
    assert all(
        row["privacy"] == triage.context.UNKNOWN for row in archive["members"]
    )
    assert all(
        row["member_digest_available"] is False for row in archive["members"]
    )
    assert any(not row["filename_review_labels"] for row in archive["members"])
    assert not any(result["boundaries"].values())


@pytest.mark.parametrize(
    "mutation",
    ["object_clearance", "wrong_archive", "member_removed", "read_gate"],
)
def test_wrong_identity_or_unsafe_privacy_change_fails_closed(
    triage_evidence: tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
    mutation: str,
) -> None:
    privacy, api, previous = copy.deepcopy(triage_evidence)
    if mutation == "object_clearance":
        row = next(
            r
            for r in privacy["objects"]
            if r["sha256"] == triage.context.SCHEDULE_CSV_SHA
        )
        row["privacy"] = "cleared"
    elif mutation == "wrong_archive":
        api["pbs_schedule_api"]["sha256"] = "0" * 64
    elif mutation == "member_removed":
        api["pbs_schedule_api"]["members"].pop()
    else:
        previous["boundaries"]["unassessed_payload_reads_authorized"] = True
    with pytest.raises(
        ValueError, match="PBS member or privacy inventory differs"
    ):
        triage.reconcile(privacy, api, previous)


def test_acquisition_events_are_unknown_and_do_not_clear_any_path() -> None:
    result = coverage.build()
    assert result["event_manifest"]["file_count"] == 1702
    assert result["matched"]["paths"] == 1703
    assert result["matched"]["distinct_sha256_values"] == 1702
    assert result["matched"]["event_sensitivity"] == "unknown"
    assert result["matched"]["event_personal_data"] == "unknown"
    assert result["unmatched_in_scoped_event_directory"]["paths"] == 19
    assert result["boundaries"]["privacy_clearances_added"] == 0
    assert not any(result["boundaries"].values())


def test_acquisition_event_privacy_change_requires_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(coverage, "EXPECTED_EVENTS", 1)
    event_dir = tmp_path / coverage.EVENT_DIRECTORY
    event_dir.mkdir(parents=True)
    original = next((coverage.ROOT / coverage.EVENT_DIRECTORY).glob("*.json"))
    event = json.loads(original.read_bytes())
    event["sensitivity"]["personal_data"] = "none"
    (event_dir / original.name).write_text(json.dumps(event))
    with pytest.raises(ValueError, match="recorded privacy state differs"):
        coverage._events(tmp_path)  # pyright: ignore[reportPrivateUsage]
