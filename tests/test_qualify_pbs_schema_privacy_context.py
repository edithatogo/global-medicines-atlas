"""PBS metadata triage preserves the member and privacy boundaries."""

from __future__ import annotations

import copy
from typing import Any

import pytest
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
