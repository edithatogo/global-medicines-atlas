"""Check existing-evidence joins without accessing archive payloads."""

from __future__ import annotations

import copy
import json
import socket
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_mbs_august_projection_field_lineage as lineage
import scripts.qualify_mbs_frozen_projection_roles as roles
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


def test_frozen_projection_roles_reproduce_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_network(*_args: object, **_kwargs: object) -> None:
        pytest.fail("role assessment must not access the network")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    checked_commits: list[str] = []

    def record_code(_root: Path, commit: str, _files: dict[str, str]) -> None:
        checked_commits.append(commit)

    # Hosted unit checkouts are shallow; the real blobs are verified by the
    # separate local --check, while this test exercises the metadata joins.
    monkeypatch.setattr(roles, "check_code", record_code)
    outputs = roles.build()
    assert checked_commits.count(roles.PBS_COMMIT) == 1
    assert len(checked_commits) == 5
    assert outputs == {roles.REPORT: Path(roles.REPORT).read_bytes()}
    report = json.loads(outputs[roles.REPORT])
    assert (
        report["v1_source_receipt"]["semantic_errors"]
        == ["target_layer_mismatch"] * 3
    )
    assert len(report["objects"]) == 4
    assert all(
        item["v2"]["matching_records"] == 85
        and item["v3"]["scope"] == "metadata_registration_only"
        and item["v3"]["plan_bytes_retained"] is False
        and item["privacy"] == "unknown_output_values_not_screened"
        and item["admission"] == "not_performed"
        for item in report["objects"]
    )
    pbs = report["pbs_reproduced_silver"]
    assert pbs["retained_native_core_includes_value"] is True
    assert pbs["privacy"] == "unknown_output_values_not_screened"
    assert not any(report["boundaries"].values())


def test_v1_semantics_detects_inconsistent_subject_and_approval() -> None:
    fixture = json.loads(
        Path("contracts/medallion/v1/fixtures/valid.json").read_bytes()
    )
    assert roles.semantic_errors(fixture) == []
    altered = copy.deepcopy(fixture)
    altered["artifacts"][0]["layer"] = "bronze_b2"
    assert "target_layer_mismatch" in roles.semantic_errors(altered)
    altered = copy.deepcopy(fixture)
    altered["promotion_decisions"][0]["passed_gate_ids"] = []
    assert "approval_gate_missing" in roles.semantic_errors(altered)
    altered = copy.deepcopy(fixture)
    altered["promotion_decisions"][0]["input_sha256"] = ["0" * 64]
    assert "lineage_checksum_mismatch" in roles.semantic_errors(altered)


def test_projection_roles_reject_mutated_v2_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = lineage.build

    def altered(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        vocabulary, crosswalk = original(root)
        vocabulary["records"][0]["output_sha256"] = "0" * 64
        return vocabulary, crosswalk

    monkeypatch.setattr(lineage, "build", altered)
    with pytest.raises(ValueError, match="v2 bytes differ"):
        roles.build()


def test_pbs_assessment_rejects_wrong_output_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = roles.checked_json

    def altered(root: Path, name: str, digest: str) -> dict[str, Any]:
        value = original(root, name, digest)
        if name == roles.PBS_READY:
            value["output"]["parquet_sha256"] = "0" * 64
        return value

    monkeypatch.setattr(roles, "checked_json", altered)
    with pytest.raises(
        ValueError, match="PBS output or source identity differs"
    ):
        roles.pbs_assessment(roles.ROOT)


def test_code_blob_digest_check_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(roles.shutil, "which", lambda _name: "/usr/bin/git")
    monkeypatch.setattr(
        roles.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=b"synthetic code"),
    )
    digest = roles.sha(b"synthetic code")
    roles.check_code(roles.ROOT, "synthetic-commit", {"synthetic.py": digest})
    with pytest.raises(ValueError, match="producer code digest differs"):
        roles.check_code(
            roles.ROOT, "synthetic-commit", {"synthetic.py": "0" * 64}
        )


def test_projection_roles_reject_mutated_v3_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = roles.replay._plan  # pyright: ignore[reportPrivateUsage]

    def altered(*args: Any, **kwargs: Any) -> dict[str, Any]:
        packet = original(*args, **kwargs)
        packet["plan"]["replay_plan"]["plan_sha256"] = "0" * 64
        return packet

    monkeypatch.setattr(roles, "check_code", lambda *_args: None)
    monkeypatch.setattr(roles.replay, "_plan", altered)
    with pytest.raises(ValueError, match="v3 plan or object identity differs"):
        roles.build()


def test_v1_alone_cannot_qualify_a_b2_projection() -> None:
    document = json.loads(
        Path("contracts/medallion/v1/fixtures/valid.json").read_bytes()
    )
    path = "bronze/example/projection.parquet"
    assert "projection_subject_absent" in roles.projection_v1_errors(
        document, path
    )
    document["artifacts"][0]["artifact_id"] = path
    document["artifacts"][0]["layer"] = "bronze_b2"
    document["promotion_decisions"][0]["subject_artifact_id"] = path
    assert (
        "v1_bronze_b2_lacks_representation_discriminator"
        in roles.projection_v1_errors(document, path)
    )
