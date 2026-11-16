"""Check existing-evidence joins without accessing archive payloads."""

from __future__ import annotations

import copy
import json
import socket
from pathlib import Path
from typing import Any

import pytest
import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.reconcile_australian_existing_evidence as reconciliation
from jsonschema import Draft202012Validator, FormatChecker

from global_medicines_atlas.federation import validate_federation_semantics


def _evidence() -> dict[str, Any]:
    evidence = {
        name: bounded.read_bound_metadata(reconciliation.ROOT, *binding)
        for name, binding in reconciliation.INPUTS.items()
    }
    references = evidence["outside_dossiers"]["inputs"]
    evidence["outside_references"] = {
        key: bounded.read_bound_metadata(
            reconciliation.ROOT, ref["path"], ref["sha256"]
        )
        for key, ref in references.items()
        if key
        in {
            "d781_publication",
            "d781_manifest",
            "f9f9_publication",
            "f9f9_manifest",
        }
    }
    return evidence


def test_existing_dossiers_bind_primary_restore_and_keep_gates_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_network(*_args: object, **_kwargs: object) -> None:
        pytest.fail("existing evidence must not access the network")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    report = reconciliation.build()
    saved = json.loads(Path(reconciliation.OUTPUT).read_text(encoding="utf-8"))
    assert report == saved
    rows = report["mbs_projections"]
    assert len(rows) == 8
    assert (
        sum(
            row["evidence_roles"]["recovery"]["historical_primary_restore"]
            == "exact_inventory_match"
            for row in rows
        )
        == 4
    )
    assert (
        sum(
            row["evidence_roles"]["recovery"][
                "replica_required_before_admission"
            ]
            for row in rows
        )
        == 2
    )
    assert all(
        row["evidence_roles"]["privacy"]["status"] == "output_not_cleared"
        and row["independently_trusted_admission"] == "not_performed"
        and row["evidence_roles"]["consumer"]["actual_payload_canary"]
        == "not_performed"
        for row in rows
    )
    assert not any(report["boundaries"].values())


def test_pbs_exact_link_join_keeps_all_objects_unassessed() -> None:
    e = _evidence()
    joined = reconciliation.pbs_schedule_privacy(
        e["privacy"], e["pbs_links"], e["schema_context"], e["member_triage"]
    )
    assert joined["unassessed_cohort_paths"] == 1722
    assert joined["matched_link_occurrences"] == 312
    assert joined["matched_candidate_occurrences"] == 313
    assert joined["exact_linked_paths"] == 312
    assert joined["remaining_paths_not_in_this_link_join"] == 1410
    assert joined["april_archive_aliases_with_one_member_schema_context"] == 2
    assert joined["september_api_archives_with_filename_triage"] == 1
    assert joined["path_datasets"] == {
        "edithatogo/australian-pbs-source-archive": 1,
        "edithatogo/reimbursement-atlas": 311,
    }
    assert all(
        row["privacy"] == reconciliation.UNKNOWN
        and row["payload_read_qualified"] is False
        for row in joined["objects"]
    )


def test_synthetic_bronze_projection_requires_lineage_and_privacy() -> None:
    schema = json.loads(Path(reconciliation.SCHEMA).read_bytes())
    fixture = Path("contracts/medallion/v4.1/fixtures/valid-raw-b2.json")
    document = json.loads(fixture.read_bytes())
    receipt = document["lineage"]["v1_conformance"]
    document["source"]["representation"] = "projection"
    document["lineage"].update(
        inputs=[receipt],
        v2_field_lineage=receipt,
        v2_field_lineage_applicability="provided",
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    assert validator.is_valid(document)
    validate_federation_semantics(document)
    without_field_lineage = copy.deepcopy(document)
    without_field_lineage["lineage"].update(
        v2_field_lineage=None,
        v2_field_lineage_applicability="not_applicable_raw_b2",
    )
    assert not validator.is_valid(without_field_lineage)
    without_v1 = copy.deepcopy(document)
    del without_v1["lineage"]["v1_conformance"]
    assert not validator.is_valid(without_v1)
    unknown_privacy = copy.deepcopy(document)
    unknown_privacy["rights"]["sensitivity"] = "unknown"
    assert not validator.is_valid(unknown_privacy)


@pytest.mark.parametrize(
    "mutation",
    ["digest", "read_allowed", "privacy", "member_identity", "sensitivity"],
)
def test_pbs_join_rejects_identity_or_privacy_changes(mutation: str) -> None:
    e = _evidence()
    privacy = copy.deepcopy(e["privacy"])
    links = copy.deepcopy(e["pbs_links"])
    candidate = next(
        candidate for link in links["links"] for candidate in link["candidates"]
    )
    if mutation == "digest":
        candidate["sha256"] = "0" * 64
    elif mutation == "read_allowed":
        candidate["payload_read_qualified"] = True
    elif mutation == "privacy":
        row = next(
            row
            for row in privacy["objects"]
            if all(
                row[key] == candidate[key] for key in reconciliation.IDENTITY
            )
        )
        row["privacy"] = "non_sensitive"
    elif mutation == "member_identity":
        e["member_triage"]["september_2025_archive"]["identity"]["sha256"] = (
            "0" * 64
        )
    else:
        candidate["observed_sensitivity"]["personal_data"] = "no"
    with pytest.raises(ValueError, match="differ"):
        reconciliation.pbs_schedule_privacy(
            privacy, links, e["schema_context"], e["member_triage"]
        )


@pytest.mark.parametrize(
    "mutation", ["restore_identity", "independence", "probe", "publication"]
)
def test_projection_roles_reject_substituted_evidence(mutation: str) -> None:
    e = _evidence()
    if mutation == "restore_identity":
        e["primary_history"]["objects"][0]["sha256"] = "0" * 64
    elif mutation == "independence":
        e["primary_history"]["summary"]["independent_recovery_established"] = (
            True
        )
    elif mutation == "probe":
        e["consumer"]["consumers"]["objects"][0][
            "rekeyed_silver_identity_rejected"
        ] = False
    else:
        e["outside_references"]["d781_publication"]["workflow_commit"] = (
            "0" * 40
        )
    with pytest.raises(ValueError, match="differs"):
        reconciliation.projection_roles(e)
