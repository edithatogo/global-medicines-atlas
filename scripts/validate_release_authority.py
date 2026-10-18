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
    expected = {
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
