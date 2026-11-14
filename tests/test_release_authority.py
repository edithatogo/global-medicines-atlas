from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import scripts.validate_release_authority as authority_module
from jsonschema.exceptions import ValidationError
from scripts.validate_release_authority import (
    DEFAULT_AUTHORITY,
    STABLE_CONTRACT,
    validate_release_authority,
)


def test_exact_release_candidate_is_authorized() -> None:
    authority = validate_release_authority(
        authority_path=DEFAULT_AUTHORITY,
        tag="v1.0.0rc1",
        release_type="prerelease",
        artifact_scope="software-only",
    )
    assert authority["commit_binding"] == (
        "tag-must-resolve-to-workflow-commit"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tag", "v1.0.0"),
        ("release_type", "release"),
        ("artifact_scope", "software-and-dataset"),
    ],
)
def test_unapproved_release_variation_fails_closed(
    field: str,
    value: str,
) -> None:
    inputs = {
        "tag": "v1.0.0rc1",
        "release_type": "prerelease",
        "artifact_scope": "software-only",
    }
    inputs[field] = value
    with pytest.raises(ValueError, match="not approved"):
        validate_release_authority(
            authority_path=DEFAULT_AUTHORITY,
            **inputs,
        )


def test_missing_approval_evidence_fails_closed(tmp_path: Path) -> None:
    authority = json.loads(DEFAULT_AUTHORITY.read_text(encoding="utf-8"))
    authority["approval_evidence"] = "missing.md"
    path = tmp_path / "authority.json"
    path.write_text(json.dumps(authority), encoding="utf-8")
    with pytest.raises(ValueError, match="evidence is missing"):
        validate_release_authority(
            authority_path=path,
            tag="v1.0.0rc1",
            release_type="prerelease",
            artifact_scope="software-only",
        )


def test_stable_promotion_fails_closed_while_any_gate_is_blocked() -> None:
    contract = json.loads(STABLE_CONTRACT.read_text(encoding="utf-8"))
    assert contract["qualification_state"] == "blocked"
    with pytest.raises(ValueError, match="qualification gates are unresolved"):
        authority_module._validate_conditional_stable_approval(
            tag="v1.0.0",
            release_type="stable",
            artifact_scope="software-only",
        )


def test_exact_scoped_software_v1_is_authorized_without_qualifying_federation() -> (
    None
):
    authority = validate_release_authority(
        authority_path=DEFAULT_AUTHORITY,
        tag="v1.0.0",
        release_type="stable",
        artifact_scope="software-only",
    )
    assert authority["decision_id"] == "D-006-13"
    assert authority["deferred_requirements"] == [
        f"M-{number}" for number in range(105, 113)
    ]
    contract = json.loads(STABLE_CONTRACT.read_text(encoding="utf-8"))
    assert contract["qualification_state"] == "blocked"
    assert contract["unresolved_gate_ids"] == [
        "stable-v1-australian-health-federation"
    ]


def test_scoped_software_v1_requires_the_explicit_new_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        authority_module, "SCOPED_SOFTWARE_APPROVAL", tmp_path / "missing.json"
    )
    with pytest.raises((FileNotFoundError, ValueError)):
        validate_release_authority(
            authority_path=DEFAULT_AUTHORITY,
            tag="v1.0.0",
            release_type="stable",
            artifact_scope="software-only",
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "other_gate_blocked",
        "extra_requirement_blocked",
        "deferred_requirement_reported_complete",
        "missing_requirement",
        "missing_gate",
        "duplicate_gate",
        "unverified_support",
        "unverified_maturity",
        "blocking_risk",
        "unapproved_identity",
        "stale_readiness",
        "allow_dataset_publication",
    ],
)
def test_scoped_software_v1_rejects_other_changes_even_if_rebound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    contract = json.loads(STABLE_CONTRACT.read_text(encoding="utf-8"))
    readiness = json.loads(authority_module.STABLE_READINESS.read_text())
    approval = json.loads(authority_module.SCOPED_SOFTWARE_APPROVAL.read_text())
    if mutation == "other_gate_blocked":
        contract["release_gates"][0]["state"] = "blocked"
    elif mutation == "extra_requirement_blocked":
        contract["requirements"][0]["state"] = "blocked"
        contract["requirements"][0]["blocker_ids"] = [
            authority_module.DEFERRED_FEDERATION_GATE
        ]
    elif mutation == "deferred_requirement_reported_complete":
        item = next(
            r
            for r in contract["requirements"]
            if r["requirement_id"] == "M-105"
        )
        item["state"] = "verified"
        item["blocker_ids"] = []
    elif mutation == "missing_requirement":
        contract["requirements"].pop(0)
    elif mutation == "missing_gate":
        contract["release_gates"].pop(0)
    elif mutation == "duplicate_gate":
        contract["release_gates"][1]["gate_id"] = contract["release_gates"][0][
            "gate_id"
        ]
    elif mutation == "unverified_support":
        contract["support"]["state"] = "blocked"
    elif mutation == "unverified_maturity":
        contract["maturity_dimensions"][0]["state"] = "unverified"
    elif mutation == "blocking_risk":
        contract["residual_risks"][0]["blocking"] = True
        contract["residual_risks"][0]["disposition"] = "unresolved"
    elif mutation == "unapproved_identity":
        contract["publication_identities"][0]["licence_state"] = "unresolved"
    elif mutation == "allow_dataset_publication":
        approval["excluded_authorities"].remove("dataset_publication")

    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    contract_digest = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    readiness["contract"]["sha256"] = (
        "0" * 64 if mutation == "stale_readiness" else contract_digest
    )
    readiness_path = tmp_path / "readiness.json"
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
    approval["bound_evidence"][0]["sha256"] = contract_digest
    approval["bound_evidence"][1]["sha256"] = hashlib.sha256(
        readiness_path.read_bytes()
    ).hexdigest()
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    monkeypatch.setattr(authority_module, "STABLE_CONTRACT", contract_path)
    monkeypatch.setattr(authority_module, "STABLE_READINESS", readiness_path)
    monkeypatch.setattr(
        authority_module, "SCOPED_SOFTWARE_APPROVAL", approval_path
    )

    with pytest.raises((ValidationError, ValueError)):
        validate_release_authority(
            authority_path=DEFAULT_AUTHORITY,
            tag="v1.0.0",
            release_type="stable",
            artifact_scope="software-only",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", True), ("release_action_performed_at_approval", 0)],
)
def test_scoped_software_v1_rejects_type_confusion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    approval = json.loads(authority_module.SCOPED_SOFTWARE_APPROVAL.read_text())
    approval[field] = value
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    monkeypatch.setattr(
        authority_module, "SCOPED_SOFTWARE_APPROVAL", approval_path
    )

    with pytest.raises(ValueError, match="approval or evidence mismatch"):
        validate_release_authority(
            authority_path=DEFAULT_AUTHORITY,
            tag="v1.0.0",
            release_type="stable",
            artifact_scope="software-only",
        )


def _fully_qualified_contract_fixture() -> dict[str, Any]:
    contract = json.loads(STABLE_CONTRACT.read_text(encoding="utf-8"))
    contract["qualification_state"] = "qualified"
    contract["unresolved_gate_ids"] = []
    for requirement in contract["requirements"]:
        requirement["state"] = "verified"
        requirement["blocker_ids"] = []
    for dimension in contract["maturity_dimensions"]:
        dimension["current_level"] = "M5"
        dimension["state"] = "verified"
        dimension["blocker_ids"] = []
    contract["source_maturity"]["assignment_state"] = "verified"
    contract["source_maturity"]["documentation_readiness_state"] = "verified"
    contract["support"]["state"] = "verified"
    for risk in contract["residual_risks"]:
        if risk["disposition"] == "unresolved":
            risk["disposition"] = "mitigated"
            risk["blocking"] = False
    for identity in contract["publication_identities"]:
        identity["state"] = "verified"
        if identity["licence_state"] == "unresolved":
            identity["licence_state"] = "approved"
    for gate in contract["release_gates"]:
        gate["state"] = "passed"
    return contract


@pytest.mark.parametrize("readiness_state", ["current", "stale"])
def test_stable_promotion_requires_digest_bound_fully_qualified_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    readiness_state: str,
) -> None:
    approval_path = tmp_path / "approval.json"
    approval_path.write_bytes(authority_module.STABLE_APPROVAL.read_bytes())
    schema_path = tmp_path / "approval-schema.json"
    schema_path.write_bytes(
        authority_module.STABLE_APPROVAL_SCHEMA.read_bytes()
    )
    contract = _fully_qualified_contract_fixture()
    contract_path = tmp_path / "contract.json"
    contract_bytes = json.dumps(contract, sort_keys=True).encode()
    contract_path.write_bytes(contract_bytes)
    approval_digest = hashlib.sha256(approval_path.read_bytes()).hexdigest()
    readiness_path = tmp_path / "readiness.json"
    readiness_path.write_text(
        json.dumps({
            "schema_id": "global-medicines-atlas.stable-v1-release-readiness-reconciliation",
            "schema_version": 1,
            "qualification_state": "qualified",
            "release_performed": False,
            "contract": {
                "path": "quality/qualifications/stable-v1-contract.json",
                "sha256": hashlib.sha256(contract_bytes).hexdigest(),
            },
            "unresolved_gates": [],
            "promotion_approval": {
                "path": "quality/qualifications/stable-v1-promotion-approval-20261018.json",
                "sha256": approval_digest,
                "status": "approved_conditional",
                "tag": "v1.0.0",
                "artifact_scope": "software-only",
                "conditions": json.loads(approval_path.read_text())[
                    "conditions"
                ],
                "release_action_performed": False,
            },
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(authority_module, "STABLE_APPROVAL", approval_path)
    monkeypatch.setattr(authority_module, "STABLE_APPROVAL_SCHEMA", schema_path)
    monkeypatch.setattr(authority_module, "STABLE_CONTRACT", contract_path)
    monkeypatch.setattr(authority_module, "STABLE_READINESS", readiness_path)

    if readiness_state == "stale":
        readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
        readiness["promotion_approval"]["sha256"] = "0" * 64
        readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
        with pytest.raises(ValueError, match="readiness receipt is stale"):
            validate_release_authority(
                authority_path=DEFAULT_AUTHORITY,
                tag="v1.0.0",
                release_type="stable",
                artifact_scope="software-only",
            )
        return

    approval = validate_release_authority(
        authority_path=DEFAULT_AUTHORITY,
        tag="v1.0.0",
        release_type="stable",
        artifact_scope="software-only",
    )

    assert approval["approval_status"] == "approved_conditional"


@pytest.mark.parametrize("mutation", ["empty", "missing", "duplicate"])
def test_stable_promotion_rejects_incomplete_or_duplicate_gate_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    contract = _fully_qualified_contract_fixture()
    gates = contract["release_gates"]
    if mutation == "empty":
        contract["release_gates"] = []
    elif mutation == "missing":
        gates.pop()
    else:
        gates[1]["gate_id"] = gates[0]["gate_id"]
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    monkeypatch.setattr(authority_module, "STABLE_CONTRACT", contract_path)

    with pytest.raises((ValidationError, ValueError)):
        validate_release_authority(
            authority_path=DEFAULT_AUTHORITY,
            tag="v1.0.0",
            release_type="stable",
            artifact_scope="software-only",
        )
