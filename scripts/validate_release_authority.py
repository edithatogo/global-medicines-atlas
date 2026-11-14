"""Validate one exact, independently approved release action."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTHORITY = (
    ROOT / "quality/qualifications/release-authority-v1.0.0rc1.json"
)
SCHEMA = ROOT / "schemas/release-authority-v1.json"
STABLE_APPROVAL = (
    ROOT / "quality/qualifications/stable-v1-promotion-approval-20261018.json"
)
STABLE_APPROVAL_SCHEMA = ROOT / "schemas/stable-v1-promotion-approval-v1.json"
STABLE_CONTRACT = ROOT / "quality/qualifications/stable-v1-contract.json"
STABLE_CONTRACT_SCHEMA = ROOT / "schemas/stable-v1-qualification-v1.json"
STABLE_READINESS = (
    ROOT
    / "quality/qualifications/stable-v1-release-readiness-reconciliation.json"
)
SCOPED_SOFTWARE_APPROVAL = (
    ROOT / "quality/qualifications/scoped-software-v1-approval-20261114.json"
)
DEFERRED_FEDERATION_GATE = "stable-v1-australian-health-federation"
DEFERRED_FEDERATION_REQUIREMENTS = tuple(
    f"M-{number}" for number in range(105, 113)
)
SCOPED_REQUIREMENT_INVENTORY_SHA256 = (
    "16c33074ce9c4518df4ea42eaddd81fb48b83a43b1a2e74af5abe3e51322cac5"
)
REQUIRED_STABLE_GATE_IDS = frozenset({
    "stable-v1-canonical-schema-v2",
    "stable-v1-comparison-validity",
    "stable-v1-concept-discovery",
    "stable-v1-clean-wheel",
    "stable-v1-optional-semantic-boundary",
    "stable-v1-clean-room-rehearsal",
    "stable-v1-support-readiness",
    "stable-v1-hosted-governance",
    "stable-v1-publication-identities",
    "stable-v1-publication-gates",
    "stable-v1-licence-approval",
    "stable-v1-australian-health-federation",
    "stable-v1-release-approval",
    "stable-v1-maturity-m5",
    "stable-v1-evidence-unverified",
    "stable-v1-bronze-current-scope",
    "renovate-output-verification",
})


def validate_release_authority(
    *,
    authority_path: Path,
    tag: str,
    release_type: str,
    artifact_scope: str,
) -> dict[str, object]:
    """Fail unless runtime inputs equal the exact approved release contract."""

    if tag == "v1.0.0" and release_type == "stable":
        contract = json.loads(STABLE_CONTRACT.read_text(encoding="utf-8"))
        if contract.get("qualification_state") == "blocked":
            return _validate_scoped_software_approval(
                tag=tag,
                release_type=release_type,
                artifact_scope=artifact_scope,
            )
        return _validate_conditional_stable_approval(
            tag=tag,
            release_type=release_type,
            artifact_scope=artifact_scope,
        )

    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(authority)  # pyright: ignore[reportUnknownMemberType]
    expected: dict[str, Any] = {
        "approved_tag": tag,
        "release_type": release_type,
        "artifact_scope": artifact_scope,
    }
    mismatches = [
        name
        for name, observed in expected.items()
        if authority[name] != observed
    ]
    if mismatches:
        raise ValueError(
            "release action is not approved: " + ", ".join(mismatches)
        )
    evidence = ROOT / str(authority["approval_evidence"])
    if not evidence.is_file():
        raise ValueError("release approval evidence is missing")
    return authority


def _validate_scoped_software_approval(
    *, tag: str, release_type: str, artifact_scope: str
) -> dict[str, object]:
    """Allow the exact approved software release without accepting federation."""
    approval = json.loads(SCOPED_SOFTWARE_APPROVAL.read_text(encoding="utf-8"))
    bound_evidence = [
        {
            "path": "quality/qualifications/stable-v1-contract.json",
            "sha256": hashlib.sha256(STABLE_CONTRACT.read_bytes()).hexdigest(),
        },
        {
            "path": "quality/qualifications/stable-v1-release-readiness-reconciliation.json",
            "sha256": hashlib.sha256(STABLE_READINESS.read_bytes()).hexdigest(),
        },
        {
            "path": "quality/qualifications/stable-v1-promotion-approval-20261018.json",
            "sha256": hashlib.sha256(STABLE_APPROVAL.read_bytes()).hexdigest(),
        },
    ]
    expected: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.scoped-software-v1-approval",
        "schema_version": 1,
        "decision_id": "D-006-13",
        "approval_status": "approved",
        "approved_by": "sole_maintainer",
        "approved_at": "2026-11-14",
        "release": {
            "tag": tag,
            "release_type": release_type,
            "artifact_scope": artifact_scope,
            "commit_binding": "tag-must-resolve-to-exact-hosted-workflow-commit",
        },
        "deferred_gate": DEFERRED_FEDERATION_GATE,
        "requirement_inventory_sha256": SCOPED_REQUIREMENT_INVENTORY_SHA256,
        "deferred_requirements": list(DEFERRED_FEDERATION_REQUIREMENTS),
        "bound_evidence": bound_evidence,
        "conditions": [
            "all_nondeferred_stable_v1_gates_pass",
            "exact_candidate_artifacts_are_reproduced_and_digest_bound",
            "protected_hosted_checks_and_attestation_verify",
        ],
        "approval_evidence": {
            "source": "direct_maintainer_instruction_in_current_conversation",
            "maintainer_statement": (
                "Release a scoped software-only v1.0.0 (Recommended): defer "
                "those requirements without marking them complete, retain privacy "
                "and software security checks, and publish only the software."
            ),
        },
        "excluded_authorities": [
            "new_source_acquisition",
            "dataset_publication",
            "participant_and_cohort_data_publication",
            "source_rights_changes",
            "production_deployment",
            "production_disaster_recovery",
            "acceptance_of_deferred_requirements",
        ],
        "release_action_performed_at_approval": False,
    }
    if (
        (tag, release_type, artifact_scope)
        != (
            "v1.0.0",
            "stable",
            "software-only",
        )
        or approval != expected
        or (
            type(approval.get("schema_version")) is not int
            or approval.get("release_action_performed_at_approval") is not False
        )
    ):
        raise ValueError(
            "scoped software release approval or evidence mismatch"
        )
    _validate_scoped_evidence(bound_evidence)
    return approval


def _validate_scoped_evidence(bound_evidence: list[dict[str, str]]) -> None:
    """Require the complete original contract, with only the approved deferral."""
    contract = json.loads(STABLE_CONTRACT.read_text(encoding="utf-8"))
    contract_schema = json.loads(
        STABLE_CONTRACT_SCHEMA.read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator(
        contract_schema, format_checker=FormatChecker()
    ).validate(contract)  # pyright: ignore[reportUnknownMemberType]
    gates = contract["release_gates"]
    gate_ids = [gate["gate_id"] for gate in gates]
    if (
        contract["qualification_state"] != "blocked"
        or contract["unresolved_gate_ids"] != [DEFERRED_FEDERATION_GATE]
        or len(gate_ids) != len(set(gate_ids))
        or frozenset(gate_ids) != REQUIRED_STABLE_GATE_IDS
        or any(
            gate["state"]
            != (
                "blocked"
                if gate["gate_id"] == DEFERRED_FEDERATION_GATE
                else "passed"
            )
            for gate in gates
        )
    ):
        raise ValueError(
            "scoped software release gates are unresolved or changed"
        )
    requirements = contract["requirements"]
    requirement_ids = [item["requirement_id"] for item in requirements]
    inventory_digest = hashlib.sha256(
        "\n".join(sorted(requirement_ids)).encode("utf-8")
    ).hexdigest()
    if (
        len(requirement_ids) != len(set(requirement_ids))
        or inventory_digest != SCOPED_REQUIREMENT_INVENTORY_SHA256
        or any(
            (
                item["state"] != "blocked"
                or item["blocker_ids"] != [DEFERRED_FEDERATION_GATE]
            )
            if item["requirement_id"] in DEFERRED_FEDERATION_REQUIREMENTS
            else (item["state"] != "verified" or item["blocker_ids"])
            for item in requirements
        )
        or not set(DEFERRED_FEDERATION_REQUIREMENTS).issubset(requirement_ids)
    ):
        raise ValueError("scoped software requirement states are incomplete")
    maturity_ready = all(
        item["current_level"] == "M5"
        and item["state"] == "verified"
        and not item["blocker_ids"]
        for item in contract["maturity_dimensions"]
    )
    source_ready = (
        contract["source_maturity"]["assignment_state"] == "verified"
        and contract["source_maturity"]["documentation_readiness_state"]
        == "verified"
    )
    risks_ready = not any(
        risk["blocking"] and risk["disposition"] == "unresolved"
        for risk in contract["residual_risks"]
    )
    identities_ready = all(
        identity["state"] == "verified"
        and identity["licence_state"] in {"approved", "not_applicable"}
        for identity in contract["publication_identities"]
    )
    if not all((
        maturity_ready,
        source_ready,
        contract["support"]["state"] == "verified",
        risks_ready,
        identities_ready,
    )):
        raise ValueError("scoped software qualification remains incomplete")
    readiness: dict[str, Any] = json.loads(
        STABLE_READINESS.read_text(encoding="utf-8")
    )
    readiness_checks: tuple[bool, ...] = (
        readiness["qualification_state"] == "blocked",
        readiness["release_performed"] is False,
        readiness["contract"] == bound_evidence[0],
        readiness["unresolved_gates"]
        == [
            {
                "gate_id": DEFERRED_FEDERATION_GATE,
                "kind": "dependent_repository_tracks",
                "state": "blocked",
            }
        ],
        readiness["promotion_approval"]["sha256"]
        == bound_evidence[2]["sha256"],
        readiness["promotion_approval"]["release_action_performed"] is False,
    )
    if not all(readiness_checks):
        raise ValueError("scoped software readiness evidence is stale")


def _validate_conditional_stable_approval(
    *,
    tag: str,
    release_type: str,
    artifact_scope: str,
) -> dict[str, object]:
    """Allow stable qualification only after approval and every gate pass."""
    approval = json.loads(STABLE_APPROVAL.read_text(encoding="utf-8"))
    schema = json.loads(STABLE_APPROVAL_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(approval)  # pyright: ignore[reportUnknownMemberType]
    expected = {
        "tag": tag,
        "release_type": release_type,
        "artifact_scope": artifact_scope,
    }
    observed = {
        "tag": approval["release"]["tag"],
        "release_type": approval["release"]["release_type"],
        "artifact_scope": approval["release"]["artifact_scope"],
    }
    mismatches = [key for key in expected if observed[key] != expected[key]]
    if mismatches:
        raise ValueError(
            "stable promotion is not approved: " + ", ".join(mismatches)
        )

    contract = json.loads(STABLE_CONTRACT.read_text(encoding="utf-8"))
    contract_schema = json.loads(
        STABLE_CONTRACT_SCHEMA.read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator(
        contract_schema,
        format_checker=FormatChecker(),
    ).validate(contract)  # pyright: ignore[reportUnknownMemberType]
    gate_ids = [gate["gate_id"] for gate in contract["release_gates"]]
    all_gates_passed = all(
        gate["state"] == "passed" for gate in contract["release_gates"]
    )
    if (
        contract["qualification_state"] != "qualified"
        or contract["unresolved_gate_ids"]
        or len(gate_ids) != len(set(gate_ids))
        or frozenset(gate_ids) != REQUIRED_STABLE_GATE_IDS
        or not all_gates_passed
    ):
        raise ValueError("stable promotion qualification gates are unresolved")

    readiness = json.loads(STABLE_READINESS.read_text(encoding="utf-8"))
    expected_approval_digest = hashlib.sha256(
        STABLE_APPROVAL.read_bytes()
    ).hexdigest()
    expected_readiness: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.stable-v1-release-readiness-reconciliation",
        "schema_version": 1,
        "qualification_state": "qualified",
        "release_performed": False,
        "contract": {
            "path": "quality/qualifications/stable-v1-contract.json",
            "sha256": hashlib.sha256(STABLE_CONTRACT.read_bytes()).hexdigest(),
        },
        "unresolved_gates": [],
        "promotion_approval": {
            "path": "quality/qualifications/stable-v1-promotion-approval-20261018.json",
            "sha256": expected_approval_digest,
            "status": "approved_conditional",
            "tag": tag,
            "artifact_scope": artifact_scope,
            "conditions": approval["conditions"],
            "release_action_performed": False,
        },
    }
    if any(
        readiness.get(key) != expected
        for key, expected in expected_readiness.items()
    ):
        raise ValueError(
            "stable promotion readiness receipt is stale or unresolved"
        )
    if approval["release_action_performed"]:
        raise ValueError("stable promotion approval has already been consumed")
    return approval


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--release-type", required=True)
    parser.add_argument("--artifact-scope", required=True)
    args = parser.parse_args(argv)
    authority = validate_release_authority(
        authority_path=args.authority,
        tag=args.tag,
        release_type=args.release_type,
        artifact_scope=args.artifact_scope,
    )
    print(json.dumps(authority, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
