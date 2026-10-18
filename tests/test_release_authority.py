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
