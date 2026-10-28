"""Stable-v1 qualification contracts fail closed and reuse project authorities."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from scripts import reconcile_stable_v1_contract as reconciliation
from scripts.build_stable_v1_source_maturity import build_projection
from scripts.reconcile_stable_v1_contract import build_contract, build_support

ROOT = Path(__file__).resolve().parents[1]
if TYPE_CHECKING:
    from jsonschema.protocols import Validator

QUALIFICATION_SCHEMA = ROOT / "schemas/stable-v1-qualification-v1.json"
QUALIFICATION = ROOT / "quality/qualifications/stable-v1-contract.json"
CANONICAL_SCHEMA = ROOT / "schemas/canonical-medicine-v2.json"
COMPARISON_SCHEMA = ROOT / "schemas/comparison-validity-v1.json"
REHEARSAL_SCHEMA = ROOT / "schemas/stable-v1-rehearsal-v1.json"
REHEARSAL_PLAN = ROOT / "quality/qualifications/stable-v1-rehearsal-plan.json"
SUPPORT_SCHEMA = ROOT / "schemas/stable-v1-support-readiness-v1.json"
SUPPORT = ROOT / "quality/qualifications/stable-v1-support-readiness.json"
PROMOTION_APPROVAL_SCHEMA = (
    ROOT / "schemas/stable-v1-promotion-approval-v1.json"
)
PROMOTION_APPROVAL = (
    ROOT / "quality/qualifications/stable-v1-promotion-approval-20261018.json"
)
SOURCE_MATURITY_SCHEMA = ROOT / "schemas/stable-v1-source-maturity-v1.json"
SOURCE_MATURITY = ROOT / "quality/qualifications/stable-v1-source-maturity.json"
CONSUMER_SCHEMA = ROOT / "schemas/stable-v1-consumer-compatibility-v1.json"
CONSUMER = ROOT / "quality/qualifications/stable-v1-consumer-compatibility.json"
IDENTITY_SCHEMA = ROOT / "schemas/publication-identity-registry-v1.json"
TRACK = ROOT / "conductor/tracks/stable_v1_qualification_20260729"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(path: Path) -> Validator:
    schema = _load(path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _assert_f9f9_disposition_is_bound(
    report: dict[str, Any], objects: list[dict[str, Any]]
) -> Path:
    path = ROOT / (
        "quality/qualifications/"
        "australian-mbs-august-f9f9-prefix-disposition-20261028.json"
    )
    disposition = _load(path)
    assert disposition["disposition"]["state"] == "deferred_not_admitted"
    assert disposition["disposition"]["product_id"] == (
        "f9f9af5a152ea74c25a617102e3cf271054ef78867ed0eb84fb69822b6767d63"
    )
    assert disposition["evidence"]["dataset"] == report["dataset"]["id"]
    assert disposition["evidence"]["revision"] == report["dataset"]["revision"]
    assert disposition["objects"] == [
        {
            "path": row["path"],
            "sha256": row["sha256"],
            "byte_count": row["byte_count"],
        }
        for row in objects
        if "/f9f9af5a152ea74c25a617102e3cf271054ef78867ed0eb84fb69822b6767d63/"
        in row["path"]
    ]
    references: list[dict[str, str]] = [
        disposition["evidence"][key]
        for key in (
            "current_tree_readback",
            "phase4_reconciliation",
            "scope_exception",
            "rights_attestation",
        )
    ]
    for reference in references:
        evidence_path: Path = ROOT / reference["path"]
        assert (
            reference["sha256"]
            == hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        )
    boundaries = disposition["boundaries"]
    assert boundaries["new_sources"] == 0
    assert boundaries["admission_performed"] is False
    assert boundaries["federation_gate_closed"] is False
    return path


def _assert_current_m112_receipts_are_bound(
    receipt: dict[str, Any],
) -> None:
    role_path = (
        "quality/qualifications/"
        "australian-m112-v4-contract-role-evidence-qualification-20261021.json"
    )
    lineage_path = (
        "quality/qualifications/"
        "australian-m112-per-object-gate-reconciliation-20261019-mbs-util-lineages.json"
    )
    receipts = receipt["current_evidence_reconciliation"]["system_receipts"]
    for path in (role_path, lineage_path):
        evidence_path = ROOT / path
        bound_receipt = next(item for item in receipts if item["path"] == path)
        assert (
            bound_receipt["sha256"]
            == hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        )
    role_receipt = next(item for item in receipts if item["path"] == role_path)
    assert "8 v4 admissions" in role_receipt["consequence"]
    assert "1,751 remain deferred" in role_receipt["consequence"]


def _must_requirement_ids() -> set[str]:
    text = (ROOT / "conductor/requirements.md").read_text(encoding="utf-8")
    must_section = text.split("## Should Have", maxsplit=1)[0]
    return set(re.findall(r"\*\*(M-\d{3})", must_section))


def test_contract_schemas_are_valid_draft_2020_12() -> None:
    for path in (
        QUALIFICATION_SCHEMA,
        CANONICAL_SCHEMA,
        COMPARISON_SCHEMA,
        REHEARSAL_SCHEMA,
        SUPPORT_SCHEMA,
        SOURCE_MATURITY_SCHEMA,
        CONSUMER_SCHEMA,
        IDENTITY_SCHEMA,
    ):
        _validator(path)


def test_consumer_compatibility_contract_is_complete_and_fail_closed() -> None:
    contract = _load(CONSUMER)
    _validator(CONSUMER_SCHEMA).validate(contract)
    assert set(contract["platforms"]) == {"linux", "macos", "windows"}
    assert contract["runners"] == {
        "linux": "ubuntu-24.04",
        "macos": "macos-15",
        "windows": "windows-2025",
    }
    assert set(contract["artifacts"]) == {"wheel", "sdist"}
    assert {
        "metadata",
        "reinstall",
        "openapi_compatibility",
        "core_fallback",
    } <= set(contract["probes"])
    assert contract["state"] == "qualified"


def test_support_readiness_uses_current_verified_python_runtime() -> None:
    support = _load(SUPPORT)
    _validator(SUPPORT_SCHEMA).validate(support)
    runtime = next(
        item
        for item in support["support_boundaries"]
        if item["gate_id"] == "python-315-reference"
    )
    assert runtime["scope"] == "CPython 3.15.1 reference implementation"
    assert runtime["state"] == "passed"
    receipt = ROOT / (
        "quality/qualifications/stable-v1-python-runtime-validation-20261027.md"
    )
    assert str(receipt.relative_to(ROOT)) in runtime["evidence"]
    evidence = receipt.read_text(encoding="utf-8")
    assert "2851255c3bb6e3a4f9b7fc2cd7907cdf01a14bcd" in evidence
    assert "40495426213" in evidence
    assert "Python 3.15.1" in evidence
    assert "Python 3.14 is authoritative" not in evidence
    contract_support = _load(QUALIFICATION)["support"]
    assert any(
        "CPython 3.15.1" in item for item in contract_support["limitations"]
    )
    assert not any(
        "Python 3.14" in item for item in contract_support["limitations"]
    )


def test_frontier_requirements_trace_to_verified_runtime_evidence() -> None:
    projection = _load(QUALIFICATION)
    requirements = {
        item["requirement_id"]: item for item in projection["requirements"]
    }
    expected = {
        "M-085": "canonical_v2.py",
        "M-086": "query_service.py",
        "M-089": "acquisition.py",
        "M-090": "comparison_validity.py",
    }
    for requirement_id, evidence_suffix in expected.items():
        item = requirements[requirement_id]
        assert item["state"] == "verified"
        assert item["blocker_ids"] == []
        assert any(path.endswith(evidence_suffix) for path in item["evidence"])

    identities = requirements["M-088"]
    assert identities["state"] == "verified"
    assert identities["blocker_ids"] == []
    assert any(
        path.endswith("publication-identities.json")
        for path in identities["evidence"]
    )

    protocol = requirements["M-091"]
    assert protocol["state"] == "verified"
    assert protocol["blocker_ids"] == []

    clean_consumer = requirements["M-087"]
    assert clean_consumer["state"] == "verified"
    assert clean_consumer["blocker_ids"] == []


def test_projection_validates_and_traces_every_must_requirement() -> None:
    projection = _load(QUALIFICATION)
    _validator(QUALIFICATION_SCHEMA).validate(projection)

    projected = [item["requirement_id"] for item in projection["requirements"]]
    assert len(projected) == len(set(projected))
    assert set(projected) == _must_requirement_ids()


def test_projection_reuses_authoritative_models_and_catalog() -> None:
    projection = _load(QUALIFICATION)
    authorities = projection["authorities"]
    assert authorities == {
        "requirements": "conductor/requirements.md",
        "maturity_model": "conductor/maturity-model.json",
        "source_catalog": (
            "src/global_medicines_atlas/data/medicine_source_catalog.json"
        ),
        "publication_contract": (
            "src/global_medicines_atlas/publication_contracts.py"
        ),
        "publication_identity_registry": (
            "quality/qualifications/publication-identities.json"
        ),
    }

    maturity = _load(ROOT / authorities["maturity_model"])
    projected_dimensions = {
        item["dimension"] for item in projection["maturity_dimensions"]
    }
    assert projected_dimensions == set(maturity["blocking_dimensions"])

    catalog = _load(ROOT / authorities["source_catalog"])
    assert projection["source_maturity"]["catalog_source_count"] == len(
        catalog["sources"]
    )
    assert projection["source_maturity"]["matrix"] == (
        "quality/qualifications/stable-v1-source-maturity.json"
    )


def test_all_local_evidence_paths_exist() -> None:
    projection = _load(QUALIFICATION)
    evidence_paths: set[str] = set()
    for requirement in projection["requirements"]:
        evidence_paths.update(requirement["evidence"])
    for dimension in projection["maturity_dimensions"]:
        evidence_paths.update(dimension["evidence"])
    evidence_paths.update(projection["support"]["evidence"])
    evidence_paths.add(projection["source_maturity"]["matrix"])
    for risk in projection["residual_risks"]:
        evidence_paths.update(risk["evidence"])
    for gate in projection["release_gates"]:
        evidence_paths.update(gate["evidence"])

    missing = sorted(
        path for path in evidence_paths if not (ROOT / path).is_file()
    )
    assert not missing


def test_stable_v1_status_page_matches_current_bronze_report_provenance() -> (
    None
):
    maturity = _load(ROOT / "quality/qualifications/bronze-maturity.json")
    status_page = (
        ROOT / "docs/qualification/stable-v1-m5-maturity-status.md"
    ).read_text(encoding="utf-8")

    assert maturity["git_commit"] in status_page
    assert "8c830ebdc33c4a3b12c8a34d5d8c8d5b4d9d8fa1" not in status_page


def test_publication_identities_are_unique_and_non_overlapping() -> None:
    identities = _load(QUALIFICATION)["publication_identities"]
    registry = _load(
        ROOT / "quality/qualifications/publication-identities.json"
    )["identities"]
    assert {item["system"] for item in identities} == {
        "github",
        "hugging_face",
        "zenodo",
    }
    assert "osf" not in {item["system"] for item in identities}
    roles = [item["object_role"] for item in identities]
    assert len(roles) == len(set(roles))
    unresolved = [item for item in identities if item["identifier"] is None]
    assert not unresolved
    assert all(item["state"] == "verified" for item in identities)
    assert {
        (item["system"], item["object_role"], item["identifier"])
        for item in identities
    } == {
        (item["system"], item["object_role"], item["identifier"])
        for item in registry
    }


def test_qualification_fails_closed_with_unresolved_gates() -> None:
    projection = _load(QUALIFICATION)
    assert projection["qualification_state"] == "blocked"
    unresolved = {
        gate["gate_id"]
        for gate in projection["release_gates"]
        if gate["state"] != "passed"
    }
    assert set(projection["unresolved_gate_ids"]) == unresolved
    assert unresolved == {"stable-v1-australian-health-federation"}

    gates = {item["gate_id"]: item for item in projection["release_gates"]}
    for gate_id in (
        "stable-v1-canonical-schema-v2",
        "stable-v1-clean-room-rehearsal",
        "stable-v1-comparison-validity",
        "stable-v1-concept-discovery",
        "stable-v1-evidence-unverified",
        "stable-v1-hosted-governance",
        "stable-v1-publication-gates",
        "stable-v1-support-readiness",
    ):
        assert gates[gate_id]["state"] == "passed"
    assert gates["stable-v1-release-approval"]["state"] == "passed"
    assert "v1.0.0rc1" in gates["stable-v1-release-approval"]["description"]
    assert (
        str(PROMOTION_APPROVAL.relative_to(ROOT))
        in gates["stable-v1-release-approval"]["evidence"]
    )

    requirements = {
        item["requirement_id"]: item for item in projection["requirements"]
    }
    blocked_requirements = {
        requirement_id
        for requirement_id, item in requirements.items()
        if item["state"] != "verified"
    }
    assert blocked_requirements == {
        "M-105",
        "M-106",
        "M-107",
        "M-108",
        "M-109",
        "M-110",
        "M-111",
        "M-112",
    }
    assert requirements["M-113"]["state"] == "verified"
    assert requirements["M-113"]["blocker_ids"] == []
    assert gates["stable-v1-australian-health-federation"]["state"] == "blocked"
    assert gates["stable-v1-bronze-current-scope"]["state"] == "passed"
    assert gates["stable-v1-maturity-m5"]["state"] == "passed"

    invalid = copy.deepcopy(projection)
    invalid["qualification_state"] = "qualified"
    with pytest.raises(ValidationError):
        _validator(QUALIFICATION_SCHEMA).validate(invalid)

    invalid["unresolved_gate_ids"] = []
    with pytest.raises(ValidationError):
        _validator(QUALIFICATION_SCHEMA).validate(invalid)


def test_m110_bounded_edge_review_is_bound_without_accepting_m110() -> None:
    projection = build_contract(_load(QUALIFICATION))
    requirement = next(
        item
        for item in projection["requirements"]
        if item["requirement_id"] == "M-110"
    )
    review_path = "quality/qualifications/australian-mbs-gold-same-record-review-20261018.json"
    assessment_path = "quality/qualifications/australian-m110-mbs-july-2025-real-gold-assessment-20261018.json"
    assert requirement["state"] == "blocked"
    assert review_path in requirement["evidence"]
    assert assessment_path in requirement["evidence"]

    review = _load(ROOT / review_path)
    assessment = _load(ROOT / assessment_path)
    assert review["disposition"] == "accepted_candidate_only"
    assert review["reviewed_edge_set"]["edge_count"] == 5989
    assert review["reviewed_edge_set"]["reviewed_state"] == "reviewed_candidate"
    assert review["boundaries"]["m110_overall_accepted"] is False
    assert (
        assessment["evidence"]["gold_edge_review"]["sha256"]
        == review["receipt_sha256"]
    )
    assert assessment["gate_assessment"]["m110_overall"] == (
        "open_other_source_eras_pbs_product_admission_and_federation"
    )


def test_current_m112_role_receipt_is_bound_without_accepting_denominator() -> (
    None
):
    role_path = (
        "quality/qualifications/"
        "australian-m112-v4-contract-role-evidence-qualification-20261021.json"
    )
    lineage_path = (
        "quality/qualifications/"
        "australian-m112-per-object-gate-reconciliation-20261019-mbs-util-lineages.json"
    )
    role_report = _load(ROOT / role_path)
    assert role_report["cohort"]["approved_denominator"] == 1_759
    assert role_report["cohort"]["v4_admissions"] == 8
    assert role_report["cohort"]["consumer_canaries"] == 8
    assert role_report["cohort"]["approved_denominator_changed"] is False
    assert (
        role_report["cohort"]["approved_denominator"]
        - role_report["cohort"]["v4_admissions"]
        == 1_751
    )
    lineage_report = _load(ROOT / lineage_path)
    assert (
        lineage_report["current_b1_b2_lineage_expansion"][
            "new_complete_lineages"
        ]
        == 14
    )
    assert lineage_report["updated_gate_totals"]["preserved_deferrals"] == 1_759

    contract = build_contract(_load(QUALIFICATION))
    requirement = next(
        item
        for item in contract["requirements"]
        if item["requirement_id"] == "M-112"
    )
    gate = next(
        item
        for item in contract["release_gates"]
        if item["gate_id"] == "stable-v1-australian-health-federation"
    )
    assert requirement["state"] == "blocked"
    assert gate["state"] == "blocked"
    assert role_path in requirement["evidence"]
    assert role_path in gate["evidence"]
    assert lineage_path in requirement["evidence"]
    assert lineage_path in gate["evidence"]


def test_current_august_tree_readback_is_bound_without_v4_promotion() -> None:
    readback_path = ROOT / (
        "quality/qualifications/"
        "australian-mbs-august-projection-current-tree-readback-20261028.json"
    )
    report = _load(readback_path)
    assert report["dataset"]["revision"] == (
        "b925a8a80b0f90db09513e7ce1378045461b05c0"
    )
    assert report["dataset"]["public"] is True
    assert report["dataset"]["gated"] is False
    assert report["scope"]["new_sources"] == 0
    assert report["scope"]["frozen_m112_inventory_membership_changed"] is False
    rights_path = ROOT / report["scope"]["rights_attestation"]
    scope_path = ROOT / report["scope"]["scope_exception"]
    rights = _load(rights_path)
    assert (
        report["scope"]["rights_attestation_sha256"]
        == hashlib.sha256(rights_path.read_bytes()).hexdigest()
    )
    assert (
        report["scope"]["scope_exception_sha256"]
        == hashlib.sha256(scope_path.read_bytes()).hexdigest()
    )
    objects = report["readback"]["objects"]
    disposition_path = _assert_f9f9_disposition_is_bound(report, objects)
    assert len(objects) == 4
    assert all(
        row["sha256"] == row["lfs_sha256"]
        and row["byte_count"] > 0
        and len(row["git_blob_oid"]) == 40
        for row in objects
    )
    assert {
        (row["path"], row["sha256"], row["byte_count"]) for row in objects
    } == {
        (row["path"], row["sha256"], row["byte_count"])
        for row in rights["authorized_objects"]
    }
    admissions = {
        row["product_id"]: row
        for row in report["readback"]["product_admission_sidecars"]
    }
    assert (
        admissions[
            "d78170f1944e8c209833b86193d403b12553a3932579dc571ff10f8485a6483b"
        ]["state"]
        == "accepted"
    )
    assert (
        admissions[
            "d78170f1944e8c209833b86193d403b12553a3932579dc571ff10f8485a6483b"
        ]["reviewer_status"]
        == "unreviewed"
    )
    assert (
        admissions[
            "d78170f1944e8c209833b86193d403b12553a3932579dc571ff10f8485a6483b"
        ]["federation_v4_admission"]
        is False
    )
    assert (
        admissions[
            "f9f9af5a152ea74c25a617102e3cf271054ef78867ed0eb84fb69822b6767d63"
        ]["http_status"]
        == 404
    )
    assert (
        report["conclusion"][
            "no_v4_admission_sidecar_observed_under_product_prefixes"
        ]
        is True
    )
    assert report["conclusion"]["publications_performed"] == 0

    projection = build_contract(_load(QUALIFICATION))
    requirement = next(
        item
        for item in projection["requirements"]
        if item["requirement_id"] == "M-108"
    )
    gate = next(
        item
        for item in projection["release_gates"]
        if item["gate_id"] == "stable-v1-australian-health-federation"
    )
    readback_relative = readback_path.relative_to(ROOT).as_posix()
    assert requirement["state"] == "blocked"
    assert readback_relative in requirement["evidence"]
    assert readback_relative in gate["evidence"]
    disposition_relative = disposition_path.relative_to(ROOT).as_posix()
    assert disposition_relative in requirement["evidence"]
    assert disposition_relative in gate["evidence"]
    acceptance = (
        ROOT / "docs/qualification/australian-health-federation-acceptance.md"
    ).read_text(encoding="utf-8")
    m108_row = next(
        line
        for line in acceptance.splitlines()
        if line.startswith("| M-108 public durable data plane |")
    )
    assert readback_relative in m108_row
    assert "f9f9` has no admission sidecar" in m108_row
    assert "explicitly deferred from M-108 admission" in m108_row
    assert "do not complete M-108" in m108_row


def test_current_maintainer_disposition_keeps_m105_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _load(QUALIFICATION)
    reconciled = build_contract(raw)
    requirements = {
        row["requirement_id"]: row for row in reconciled["requirements"]
    }
    assert requirements["M-105"]["state"] == "blocked"
    assert requirements["M-105"]["blocker_ids"] == [
        "stable-v1-australian-health-federation"
    ]
    assert (
        "quality/qualifications/australian-donor-m105-current-disposition-20261023.json"
        in requirements["M-105"]["evidence"]
    )
    assert (
        "quality/qualifications/australian-donor-m105-chronology-waiver-20261018.json"
        in requirements["M-105"]["evidence"]
    )
    disposition = _load(
        ROOT
        / "quality/qualifications/australian-donor-m105-current-disposition-20261023.json"
    )
    assert disposition["decision_id"] == "D-006-12"
    assert disposition["status"] == "blocked"
    assert not disposition["boundaries"]["pre_archive_parity_proof_created"]
    assert not disposition["boundaries"]["new_sources_added"]
    assert not disposition["boundaries"]["outbound_communication_performed"]
    assert all(
        requirements[f"M-{number}"]["state"] == "blocked"
        for number in range(106, 113)
    )
    gates = {row["gate_id"]: row for row in reconciled["release_gates"]}
    assert gates["stable-v1-australian-health-federation"]["state"] == "blocked"

    status_page = (
        ROOT / "docs/qualification/stable-v1-m5-maturity-status.md"
    ).read_text(encoding="utf-8")
    assert "84 verified and 8 blocked requirements" in status_page
    assert "M-105 remains blocked" in status_page

    invalid_waiver = _load(
        ROOT
        / "quality/qualifications/australian-donor-m105-chronology-waiver-20261018.json"
    )
    invalid_waiver["waiver_scope"]["criterion_text_changed"] = True
    path = tmp_path / "invalid-m105-waiver.json"
    path.write_text(json.dumps(invalid_waiver), encoding="utf-8")
    with monkeypatch.context() as patch:
        patch.setattr(reconciliation, "M105_WAIVER", str(path))
        invalid = build_contract(raw)
    invalid_m105 = next(
        row
        for row in invalid["requirements"]
        if row["requirement_id"] == "M-105"
    )
    assert invalid_m105["state"] == "blocked"
    assert (
        "stable-v1-australian-health-federation" in invalid_m105["blocker_ids"]
    )


def test_missing_current_m105_disposition_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        reconciliation,
        "M105_CURRENT_DISPOSITION",
        "quality/qualifications/missing-m105-current-disposition.json",
    )
    result = build_contract(_load(QUALIFICATION))
    m105 = next(
        row
        for row in result["requirements"]
        if row["requirement_id"] == "M-105"
    )
    assert m105["state"] == "blocked"
    assert "stable-v1-australian-health-federation" in m105["blocker_ids"]


@pytest.mark.parametrize("decision_id", ["D-006-12", "D-006-99"])
def test_m105_unblock_requires_a_later_bound_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    decision_id: str,
) -> None:
    disposition = _load(
        ROOT
        / "quality/qualifications/australian-donor-m105-current-disposition-20261023.json"
    )
    disposition["decision_id"] = decision_id
    disposition["status"] = "accepted_after_new_maintainer_decision"
    path = tmp_path / "m105-current-disposition.json"
    path.write_text(json.dumps(disposition), encoding="utf-8")
    monkeypatch.setattr(reconciliation, "M105_CURRENT_DISPOSITION", str(path))

    result = build_contract(_load(QUALIFICATION))
    m105 = next(
        row
        for row in result["requirements"]
        if row["requirement_id"] == "M-105"
    )
    assert m105["state"] == "blocked"
    assert "stable-v1-australian-health-federation" in m105["blocker_ids"]


@pytest.mark.parametrize(
    "mutation",
    [
        "failed_row_state",
        "mismatched_disposition_state",
        "missing_behavior_evidence",
        "source_rights_changed",
        "public_release_approved",
        "stable_release_approved",
        "not_waived_removed",
        "pre_archive_claimed",
    ],
)
def test_m105_waiver_rejects_invalid_dossier_even_with_refreshed_digests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    matrix = _load(
        ROOT / "quality/qualifications/australian-donor-m105-dispositions.json"
    )
    waiver = _load(
        ROOT
        / "quality/qualifications/australian-donor-m105-chronology-waiver-20261018.json"
    )
    rows = [*matrix["baseline"], *matrix["post_baseline_delta"]]
    if mutation == "failed_row_state":
        rows[0]["acceptance_state"] = "failed"
    elif mutation == "mismatched_disposition_state":
        row = next(item for item in rows if item["disposition"] == "adapt")
        row["disposition"] = "retain-legacy"
    elif mutation == "missing_behavior_evidence":
        row = next(item for item in rows if item["disposition"] == "adapt")
        row.pop("parity_evidence")
    elif mutation == "source_rights_changed":
        waiver["boundaries"]["source_rights_changed"] = True
    elif mutation == "public_release_approved":
        waiver["boundaries"]["public_release_approved"] = True
    elif mutation == "stable_release_approved":
        waiver["boundaries"]["stable_release_approved"] = True
    elif mutation == "not_waived_removed":
        waiver["not_waived"].remove(
            "source rights and future-source authorization"
        )
    elif mutation == "pre_archive_claimed":
        waiver["waiver_scope"]["pre_archive_parity_proof_claimed"] = True

    matrix_path = tmp_path / "m105-matrix.json"
    waiver_path = tmp_path / "m105-waiver.json"
    matrix_path.write_text(
        json.dumps(matrix, indent=2) + "\n", encoding="utf-8"
    )
    report = waiver["reassessment"]["disposition_matrix"]
    report["sha256"] = hashlib.sha256(matrix_path.read_bytes()).hexdigest()
    report["baseline_rows_digest"] = hashlib.sha256(
        json.dumps(
            matrix["baseline"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    report["later_rows_digest"] = hashlib.sha256(
        json.dumps(
            matrix["post_baseline_delta"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    waiver_path.write_text(
        json.dumps(waiver, indent=2) + "\n", encoding="utf-8"
    )
    raw = _load(QUALIFICATION)
    with monkeypatch.context() as patch:
        patch.setattr(reconciliation, "M105_WAIVER", str(waiver_path))
        patch.setattr(reconciliation, "M105_DISPOSITIONS", str(matrix_path))
        observed = build_contract(raw)
    invalid_m105 = next(
        row
        for row in observed["requirements"]
        if row["requirement_id"] == "M-105"
    )
    assert invalid_m105["state"] == "blocked"


def test_donor_archival_acceptance_rejects_missing_restore_or_approval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert reconciliation._donor_archive_acceptance_observed()  # pyright: ignore[reportPrivateUsage]
    scraper = _load(ROOT / reconciliation.SCRAPER_ARCHIVE)
    scraper["publication"]["restored"][0]["clean_restore"] = False
    unsafe = tmp_path / "scraper.json"
    unsafe.write_text(json.dumps(scraper), encoding="utf-8")
    with monkeypatch.context() as patch:
        patch.setattr(reconciliation, "SCRAPER_ARCHIVE", str(unsafe))
        assert not reconciliation._donor_archive_acceptance_observed()  # pyright: ignore[reportPrivateUsage]
    graph = _load(ROOT / reconciliation.GRAPH_ARCHIVE)
    graph["archive_authorized"] = False
    unsafe.write_text(json.dumps(graph), encoding="utf-8")
    with monkeypatch.context() as patch:
        patch.setattr(reconciliation, "GRAPH_ARCHIVE", str(unsafe))
        assert not reconciliation._donor_archive_acceptance_observed()  # pyright: ignore[reportPrivateUsage]
    graph = _load(ROOT / reconciliation.GRAPH_ARCHIVE)
    graph["retained_branches"]["main"] = "different-head"
    unsafe.write_text(json.dumps(graph), encoding="utf-8")
    with monkeypatch.context() as patch:
        patch.setattr(reconciliation, "GRAPH_ARCHIVE", str(unsafe))
        assert not reconciliation._donor_archive_acceptance_observed()  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize("state", ["failed", "unverified", "blocked"])
def test_donor_acceptance_preserves_adverse_observations(state: str) -> None:
    raw = _load(QUALIFICATION)
    item = next(
        row for row in raw["requirements"] if row["requirement_id"] == "M-113"
    )
    item["state"] = state
    item["blocker_ids"] = [
        "stable-v1-australian-health-federation",
        "new-evidence-required",
    ]
    observed = next(
        row
        for row in build_contract(raw)["requirements"]
        if row["requirement_id"] == "M-113"
    )
    assert observed["state"] == state
    assert "new-evidence-required" in observed["blocker_ids"]


def test_release_readiness_reconciliation_separates_package_from_release() -> (
    None
):
    approval = _load(PROMOTION_APPROVAL)
    _validator(PROMOTION_APPROVAL_SCHEMA).validate(approval)
    qualification = _load(QUALIFICATION)
    receipt = _load(
        ROOT
        / "quality/qualifications/stable-v1-release-readiness-reconciliation.json"
    )
    assert (
        receipt["qualification_state"] == qualification["qualification_state"]
    )
    contract_path = ROOT / receipt["contract"]["path"]
    assert contract_path.is_relative_to(ROOT)
    assert contract_path == QUALIFICATION
    assert (
        receipt["contract"]["sha256"]
        == hashlib.sha256(contract_path.read_bytes()).hexdigest()
    )
    runtime_receipt_path = ROOT / (
        "quality/qualifications/stable-v1-python-runtime-validation-20261027.md"
    )
    runtime_receipt = next(
        item
        for item in receipt["current_evidence_reconciliation"][
            "system_receipts"
        ]
        if item["path"] == str(runtime_receipt_path.relative_to(ROOT))
    )
    assert (
        runtime_receipt["sha256"]
        == hashlib.sha256(runtime_receipt_path.read_bytes()).hexdigest()
    )
    current_tree_path = ROOT / (
        "quality/qualifications/"
        "australian-mbs-august-projection-current-tree-readback-20261028.json"
    )
    current_tree_receipt = next(
        item
        for item in receipt["current_evidence_reconciliation"][
            "system_receipts"
        ]
        if item["path"] == current_tree_path.relative_to(ROOT).as_posix()
    )
    assert (
        current_tree_receipt["sha256"]
        == hashlib.sha256(current_tree_path.read_bytes()).hexdigest()
    )
    assert "neither is v4-admitted" in current_tree_receipt["consequence"]
    disposition_path = ROOT / (
        "quality/qualifications/"
        "australian-mbs-august-f9f9-prefix-disposition-20261028.json"
    )
    disposition_receipt = next(
        item
        for item in receipt["current_evidence_reconciliation"][
            "system_receipts"
        ]
        if item["path"] == disposition_path.relative_to(ROOT).as_posix()
    )
    assert (
        disposition_receipt["sha256"]
        == hashlib.sha256(disposition_path.read_bytes()).hexdigest()
    )
    assert "deferred_not_admitted" in disposition_receipt["consequence"]
    _assert_current_m112_receipts_are_bound(receipt)
    acceptance_path = ROOT / (
        "docs/qualification/australian-health-federation-acceptance.md"
    )
    acceptance_receipt = next(
        item
        for item in receipt["current_evidence_reconciliation"][
            "system_receipts"
        ]
        if item["path"] == acceptance_path.relative_to(ROOT).as_posix()
    )
    assert (
        acceptance_receipt["sha256"]
        == hashlib.sha256(acceptance_path.read_bytes()).hexdigest()
    )
    acceptance = acceptance_path.read_text(encoding="utf-8")
    m109_row = next(
        line
        for line in acceptance.splitlines()
        if line.startswith("| M-109 Silver |")
    )
    assert "91 verified sheet/header profiles" in m109_row
    assert "728 interpreted header bindings" in m109_row
    assert (
        "310,176,929 non-header values remain `native_unresolved`" in m109_row
    )
    assert "1,194 ambiguous date-shaped cells" in m109_row
    m112_row = next(
        line
        for line in acceptance.splitlines()
        if line.startswith("| M-112 federation v4 |")
    )
    assert "8 exact v4 admissions" in m112_row
    assert "1,751 objects remain deferred" in m112_row
    assert "this is not 14 v4 admissions" in m112_row
    assert "`p7_date_convention_selected=false`" in m109_row
    assert (
        "workbook-era date convention, domain meaning, and temporal comparison remain unqualified"
        in m109_row
    )
    assert receipt["release_performed"] is False
    assert receipt["candidate_package"] == {
        "consumer_verification_guide_complete": True,
        "repository_owned_work_complete": True,
        "signed_stable_release_produced": False,
        "source_prerelease": "v1.0.0rc1",
    }
    assert {item["gate_id"] for item in receipt["unresolved_gates"]} == set(
        qualification["unresolved_gate_ids"]
    )
    assert {item["gate_id"] for item in receipt["unresolved_gates"]} == {
        "stable-v1-australian-health-federation"
    }
    assert receipt["promotion_approval"] == {
        "path": str(PROMOTION_APPROVAL.relative_to(ROOT)),
        "sha256": hashlib.sha256(PROMOTION_APPROVAL.read_bytes()).hexdigest(),
        "status": "approved_conditional",
        "tag": "v1.0.0",
        "artifact_scope": "software-only",
        "conditions": [
            "all_stable_v1_qualification_gates_pass",
            "exact_candidate_artifacts_are_reproduced_and_digest_bound",
            "protected_hosted_checks_and_attestation_verify",
        ],
        "release_action_performed": False,
    }
    assert receipt["separate_non_acceptance_gate"] == {
        "gate_id": "production-disaster-recovery-authority",
        "state": "blocked_external_authority",
    }


def test_pbs_r16_field_state_is_bound_but_federation_gate_stays_blocked() -> (
    None
):
    report_path = ROOT / (
        "quality/qualifications/"
        "pbs-native-silver-field-reconciliation-20261028-r16.json"
    )
    readiness = _load(
        ROOT
        / "quality/qualifications/stable-v1-release-readiness-reconciliation.json"
    )
    stable_contract = _load(QUALIFICATION)
    receipt = next(
        item
        for item in readiness["current_evidence_reconciliation"][
            "system_receipts"
        ]
        if item["path"] == report_path.relative_to(ROOT).as_posix()
    )

    assert (
        receipt["sha256"]
        == hashlib.sha256(report_path.read_bytes()).hexdigest()
    )
    assert "URI targets" in receipt["consequence"]
    assert stable_contract["qualification_state"] == "blocked"
    assert stable_contract["unresolved_gate_ids"] == [
        "stable-v1-australian-health-federation"
    ]


def test_structural_medicine_v2_is_not_temporal_migration_v2() -> None:
    schema = _load(CANONICAL_SCHEMA)
    assert schema["properties"]["schema_id"]["const"] == (
        "global-medicines-atlas.canonical-medicine"
    )
    assert schema["properties"]["schema_version"]["const"] == 2
    assert "temporal assertion migration" in schema["description"]
    assert {
        "substances",
        "products",
        "packages",
        "indications",
        "prices",
        "restrictions",
    }.issubset(schema["required"])


def test_inappropriate_comparison_requires_material_mismatch() -> None:
    comparison: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.comparison-validity",
        "schema_version": 1,
        "left_subject_id": "left",
        "right_subject_id": "right",
        "outcome": "inappropriate_comparison",
        "dimensions": {
            name: {
                "state": "unknown",
                "left_value": None,
                "right_value": None,
                "evidence_ids": [],
            }
            for name in (
                "granularity",
                "indication",
                "population",
                "mapping",
                "normalization",
            )
        },
        "left_evidence_context": {
            "schema_era": None,
            "comparison_cohort": "unknown",
            "entity_granularity": "unknown",
            "review_state": "not_reported",
        },
        "right_evidence_context": {
            "schema_era": None,
            "comparison_cohort": "unknown",
            "entity_granularity": "unknown",
            "review_state": "not_reported",
        },
        "material_mismatches": [],
        "explanation": "Evidence is not comparable.",
        "establishes_medicine_equivalence": False,
        "establishes_substitutability": False,
        "establishes_therapeutic_interchangeability": False,
        "establishes_equal_benefit": False,
    }
    with pytest.raises(ValidationError):
        _validator(COMPARISON_SCHEMA).validate(comparison)

    comparison["material_mismatches"] = ["granularity"]
    _validator(COMPARISON_SCHEMA).validate(comparison)


def test_rehearsal_plan_defines_every_blocking_stable_rehearsal() -> None:
    plan = _load(REHEARSAL_PLAN)
    _validator(REHEARSAL_SCHEMA).validate(plan)
    rehearsals = plan["rehearsals"]
    assert {item["kind"] for item in rehearsals} == {
        "clean_room_reproduction",
        "canonical_schema_migration",
        "canonical_schema_rollback",
        "governed_recovery",
    }
    assert len({item["rehearsal_id"] for item in rehearsals}) == len(rehearsals)
    assert all(item["blocking"] for item in rehearsals)
    assert all(item["state"] != "passed" for item in rehearsals)
    assert all(item["blocker"] for item in rehearsals)


def test_support_readiness_matches_boundaries_and_residual_risks() -> None:
    support = _load(SUPPORT)
    _validator(SUPPORT_SCHEMA).validate(support)
    projection_risks = {
        item["risk_id"]: (item["disposition"], item["blocking"])
        for item in _load(QUALIFICATION)["residual_risks"]
    }
    support_risks = {
        item["risk_id"]: (item["disposition"], item["blocking"])
        for item in support["residual_risks"]
    }
    assert support_risks == projection_risks
    assert support["readiness_state"] == "verified"
    unresolved = {
        item["risk_id"]
        for item in support["residual_risks"]
        if item["blocking"] and item["disposition"] == "unresolved"
    }
    assert unresolved == set()
    production_dr = next(
        item
        for item in support["residual_risks"]
        if item["risk_id"] == "RISK-001"
    )
    assert production_dr["disposition"] == "accepted"
    assert production_dr["blocking"] is False


def test_support_readiness_stays_blocked_for_unresolved_boundary_or_risk() -> (
    None
):
    raw = _load(SUPPORT)
    raw["support_boundaries"][0]["state"] = "unverified"
    assert build_support(raw)["readiness_state"] == "blocked"

    raw = _load(SUPPORT)
    recovery = next(
        item for item in raw["residual_risks"] if item["risk_id"] == "RISK-001"
    )
    recovery.update(disposition="unresolved", blocking=True)
    assert build_support(raw)["readiness_state"] == "blocked"


def test_stable_contract_reconciliation_is_deterministic() -> None:
    contract = _load(QUALIFICATION)
    support = _load(SUPPORT)
    assert build_contract(contract) == contract
    assert build_support(support) == support


@pytest.mark.parametrize(
    "section",
    ["requirements", "maturity_dimensions", "release_gates", "support"],
)
def test_reconciliation_does_not_promote_failed_or_unverified_evidence(
    section: str,
) -> None:
    raw = _load(QUALIFICATION)
    if section == "support":
        raw[section]["state"] = "unverified"
        item = raw[section]
    else:
        item = next(
            row
            for row in raw[section]
            if row["state"] in {"verified", "passed"}
        )
        item["state"] = "failed" if section == "release_gates" else "unverified"
        if section == "maturity_dimensions":
            item["current_level"] = "M1"
        if "blocker_ids" in item:
            item["blocker_ids"] = ["new-evidence-required"]
    item["evidence"] = ["failure-receipt.json"]
    expected = copy.deepcopy(item)
    result = build_contract(raw)
    if section == "support":
        observed = result[section]
    else:
        key = {
            "requirements": "requirement_id",
            "maturity_dimensions": "dimension",
            "release_gates": "gate_id",
        }[section]
        observed = next(row for row in result[section] if row[key] == item[key])
    for key, value in expected.items():
        if key == "evidence":
            assert set(value) <= set(observed[key])
        else:
            assert observed[key] == value


def test_support_reconciliation_does_not_override_failed_documentation() -> (
    None
):
    raw = _load(SUPPORT)
    boundary = next(
        item
        for item in raw["support_boundaries"]
        if item["gate_id"] == "documentation-readiness"
    )
    boundary["state"] = "failed"
    boundary["blocker"] = "new-documentation-failure"
    result = build_support(raw)
    observed = next(
        item
        for item in result["support_boundaries"]
        if item["gate_id"] == "documentation-readiness"
    )
    assert observed["state"] == "failed"
    assert observed["blocker"] == "new-documentation-failure"


@pytest.mark.parametrize("artifact", ["contract", "support"])
def test_reconciliation_preserves_unaccepted_recovery_risk(
    artifact: str,
) -> None:
    raw = _load(QUALIFICATION if artifact == "contract" else SUPPORT)
    risk = next(
        item for item in raw["residual_risks"] if item["risk_id"] == "RISK-001"
    )
    risk.update(
        disposition="unresolved",
        blocking=True,
        evidence=["new-recovery-failure.json"],
    )
    expected = copy.deepcopy(risk)
    result = (
        build_contract(raw) if artifact == "contract" else build_support(raw)
    )
    assert (
        next(
            item
            for item in result["residual_risks"]
            if item["risk_id"] == "RISK-001"
        )
        == expected
    )


@pytest.mark.parametrize(
    "dimension", ["source_coverage", "security_and_supply_chain"]
)
def test_reconciliation_preserves_lower_maturity(dimension: str) -> None:
    raw = _load(QUALIFICATION)
    item = next(
        row
        for row in raw["maturity_dimensions"]
        if row["dimension"] == dimension
    )
    item.update(
        current_level="M0",
        state="unverified",
        blocker_ids=["new-evidence-required"],
    )
    result = build_contract(raw)
    observed = next(
        row
        for row in result["maturity_dimensions"]
        if row["dimension"] == dimension
    )
    assert observed["current_level"] == "M0"
    assert observed["state"] == "unverified"
    assert "new-evidence-required" in observed["blocker_ids"]


def test_reconciliation_rejects_duplicate_gate_outcomes() -> None:
    raw = _load(QUALIFICATION)
    duplicate = copy.deepcopy(raw["release_gates"][0])
    raw["release_gates"][0]["state"] = "failed"
    duplicate["state"] = "passed"
    raw["release_gates"].append(duplicate)
    with pytest.raises(ValueError, match="duplicate"):
        build_contract(raw)


def test_source_maturity_matrix_is_complete_conservative_projection() -> None:
    matrix = _load(SOURCE_MATURITY)
    _validator(SOURCE_MATURITY_SCHEMA).validate(matrix)
    catalog = _load(ROOT / matrix["catalog"])
    source_rows = {item["source_id"]: item for item in matrix["sources"]}
    catalog_rows = {item["source_id"]: item for item in catalog["sources"]}
    assert set(source_rows) == set(catalog_rows)
    assert len(source_rows) == len(matrix["sources"])
    assert matrix["catalog_schema_version"] == catalog["schema_version"]
    assert matrix["matrix_state"] == "verified_projection"
    assert all(
        int(item["maturity_level"][1:]) <= 2 for item in matrix["sources"]
    )
    assert all(item["blocking_gaps"] for item in matrix["sources"])
    assert all(not item["stable_ready"] for item in matrix["jurisdictions"])


def test_source_maturity_projection_is_deterministically_regenerated() -> None:
    catalog = _load(
        ROOT / "src/global_medicines_atlas/data/medicine_source_catalog.json"
    )
    assert build_projection(catalog) == _load(SOURCE_MATURITY)


def test_completed_contract_work_and_phase3a_checkpoint_are_reconciled() -> (
    None
):
    plan = (TRACK / "plan.md").read_text(encoding="utf-8")
    completed_contracts = (
        "Contract canonical medicine schema v2 and migration compatibility",
        "Contract comparison-validity semantics",
        "Contract bounded concept discovery",
    )
    for task in completed_contracts:
        assert f"- [x] Task: {task}" in plan

    phase3a = plan.split(
        "## Phase 3A: Extended verification architecture", maxsplit=1
    )[1]
    assert "- [x] Task: Phase Verification & Checkpoint" in phase3a

    records = [
        json.loads(line)
        for line in (TRACK / "evidence.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    checkpoint = next(
        record
        for record in records
        if record.get("kind")
        == "stable_v1_phase3a_extended_verification_checkpoint"
    )
    assert checkpoint["status"] == "local_reverification_passed"
    assert checkpoint["implementation_commit"] == (
        "ab608543e39aacd2bcab3dd19ac3103283256958"
    )
    assert checkpoint["verification"]["specialized_profiles"] == {
        "contract": "2 passed",
        "metamorphic": "3 passed",
        "simulation": "2 passed",
    }
    assert checkpoint["external_authority_claims"] is False
    assert set(checkpoint["out_of_scope"]) == {
        "live deployment",
        "OSF action",
        "publication action",
        "rights determination",
    }


@pytest.mark.parametrize("requirement_id", ["M-046", "M-095", "M-105"])
def test_reconciliation_retains_additional_known_requirement_blockers(
    requirement_id: str,
) -> None:
    raw = _load(QUALIFICATION)
    item = next(
        row
        for row in raw["requirements"]
        if row["requirement_id"] == requirement_id
    )
    item["blocker_ids"].append("new-evidence-required")
    result = build_contract(raw)
    observed = next(
        row
        for row in result["requirements"]
        if row["requirement_id"] == requirement_id
    )
    assert "new-evidence-required" in observed["blocker_ids"]


@pytest.mark.parametrize(
    "gate_id",
    [
        "stable-v1-release-approval",
        "stable-v1-maturity-m5",
        "stable-v1-bronze-current-scope",
        "renovate-output-verification",
    ],
)
@pytest.mark.parametrize("state", ["failed", "unverified"])
def test_reconciliation_retains_special_gate_observations(
    gate_id: str, state: str
) -> None:
    raw = _load(QUALIFICATION)
    gate = next(
        row for row in raw["release_gates"] if row["gate_id"] == gate_id
    )
    gate.update(state=state, evidence=["fresh-failure.json"])
    result = build_contract(raw)
    observed = next(
        row for row in result["release_gates"] if row["gate_id"] == gate_id
    )
    assert observed["state"] == state
    assert "fresh-failure.json" in observed["evidence"]
