"""Reconcile stable-v1 qualification with current durable evidence."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "quality/qualifications/stable-v1-contract.json"
SUPPORT = ROOT / "quality/qualifications/stable-v1-support-readiness.json"

STABLE_LEDGER = (
    "conductor/tracks/stable_v1_qualification_20260729/evidence.jsonl"
)
INDEPENDENT_REPRODUCTION = (
    "quality/qualifications/stable-v1-independent-reproduction-20260803.json"
)
BRONZE_PLAN = "conductor/tracks/bronze_medallion_completion_20260819/plan.md"
BRONZE_MATURITY = "quality/qualifications/bronze-maturity.json"
QUALITY_CLOSURE = "quality/qualifications/quality-hardening-closure.json"
PRODUCTION_DR = (
    "quality/qualifications/stable-v1-production-dr-authority-blocker.json"
)

TECHNICAL_GATE_EVIDENCE = {
    "stable-v1-canonical-schema-v2": [
        "schemas/canonical-medicine-v2.json",
        "src/global_medicines_atlas/canonical_v2.py",
        "tests/test_canonical_v2_runtime.py",
        INDEPENDENT_REPRODUCTION,
    ],
    "stable-v1-comparison-validity": [
        "schemas/comparison-validity-v1.json",
        "src/global_medicines_atlas/comparison_validity.py",
        "tests/test_comparison_validity.py",
        "tests/test_comparison_validity_properties.py",
    ],
    "stable-v1-concept-discovery": [
        "src/global_medicines_atlas/query_service.py",
        "src/global_medicines_atlas/api.py",
        "src/global_medicines_atlas/cli.py",
        "src/global_medicines_atlas/atlas.py",
        "tests/test_concept_query_service.py",
        "tests/test_atlas_discovery_e2e.py",
    ],
    "stable-v1-clean-room-rehearsal": [
        "quality/qualifications/stable-v1-rehearsal-plan.json",
        INDEPENDENT_REPRODUCTION,
    ],
    "stable-v1-support-readiness": [
        "SUPPORT.md",
        "SECURITY.md",
        "docs/operations/README.md",
        "quality/qualifications/stable-v1-support-readiness.json",
        "quality/qualifications/stable-v1-consumer-compatibility.json",
    ],
    "stable-v1-hosted-governance": [
        "quality/qualifications/stable-v1-hosted-governance.json",
        ".github/workflows/security-context.yml",
        ".github/workflows/test-goblin.yml",
    ],
    "stable-v1-publication-gates": [
        "src/global_medicines_atlas/publication_contracts.py",
        "docs/governance/licensing-decision.md",
        "quality/qualifications/data-layer-archive-receipt.json",
    ],
    "stable-v1-evidence-unverified": [STABLE_LEDGER],
}


def _append_unique(items: list[str], additions: list[str]) -> list[str]:
    return list(dict.fromkeys([*items, *additions]))


def build_contract(  # ruff: ignore[too-many-branches,too-many-statements]
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Return the current fail-closed software-release qualification."""
    contract = deepcopy(raw)
    for requirement in contract["requirements"]:
        requirement_id = requirement["requirement_id"]
        if requirement_id == "M-046":
            requirement["state"] = "blocked"
            requirement["blocker_ids"] = ["renovate-output-verification"]
            requirement["evidence"] = _append_unique(
                requirement["evidence"], [QUALITY_CLOSURE]
            )
        elif requirement_id == "M-095":
            requirement["state"] = "blocked"
            requirement["blocker_ids"] = ["stable-v1-bronze-current-scope"]
            requirement["evidence"] = _append_unique(
                requirement["evidence"], [BRONZE_PLAN, BRONZE_MATURITY]
            )
        else:
            requirement["state"] = "verified"
            requirement["blocker_ids"] = []
            if requirement["evidence"] == ["conductor/requirements.md"]:
                requirement["evidence"] = _append_unique(
                    requirement["evidence"], [STABLE_LEDGER]
                )

    for dimension in contract["maturity_dimensions"]:
        name = dimension["dimension"]
        if name == "source_coverage":
            dimension["current_level"] = "M4"
            dimension["state"] = "partial"
            dimension["blocker_ids"] = ["stable-v1-bronze-current-scope"]
            dimension["evidence"] = _append_unique(
                dimension["evidence"], [BRONZE_PLAN, BRONZE_MATURITY]
            )
        elif name == "security_and_supply_chain":
            dimension["current_level"] = "M4"
            dimension["state"] = "partial"
            dimension["blocker_ids"] = ["renovate-output-verification"]
            dimension["evidence"] = _append_unique(
                dimension["evidence"], [QUALITY_CLOSURE]
            )
        else:
            dimension["current_level"] = "M5"
            dimension["state"] = "verified"
            dimension["blocker_ids"] = []
            dimension["evidence"] = _append_unique(
                dimension["evidence"], [INDEPENDENT_REPRODUCTION, STABLE_LEDGER]
            )

    contract["support"]["state"] = "verified"
    contract["support"]["evidence"] = _append_unique(
        contract["support"]["evidence"], ["SUPPORT.md", "SECURITY.md"]
    )

    for risk in contract["residual_risks"]:
        if risk["risk_id"] == "RISK-001":
            risk.update({
                "description": (
                    "Production backup storage, RPO, RTO and crash consistency "
                    "remain unqualified and are outside the software-only stable "
                    "release scope."
                ),
                "disposition": "accepted",
                "blocking": False,
                "evidence": [PRODUCTION_DR],
            })
        elif risk["risk_id"] == "RISK-002":
            risk.update({
                "description": (
                    "Maintainer-confirmed Renovate activation has not produced "
                    "an observable Dependency Dashboard or update pull request."
                ),
                "disposition": "unresolved",
                "blocking": True,
                "evidence": [QUALITY_CLOSURE],
            })

    gates = {gate["gate_id"]: gate for gate in contract["release_gates"]}
    for gate_id, evidence in TECHNICAL_GATE_EVIDENCE.items():
        gate = gates[gate_id]
        gate["state"] = "passed"
        gate["evidence"] = evidence

    source_gate_id = (
        "stable-v1-source-maturity"
        if "stable-v1-source-maturity" in gates
        else "stable-v1-bronze-current-scope"
    )
    source_gate = gates.pop(source_gate_id)
    source_gate.update({
        "gate_id": "stable-v1-bronze-current-scope",
        "description": (
            "Complete Bronze landing evidence for the current public/no-credential "
            "scope without treating catalogue blockers as landed sources."
        ),
        "state": "blocked",
        "evidence": [BRONZE_PLAN, BRONZE_MATURITY],
    })

    renovate_gate_id = (
        "renovate-app-activation"
        if "renovate-app-activation" in gates
        else "renovate-output-verification"
    )
    renovate_gate = gates.pop(renovate_gate_id)
    renovate_gate.update({
        "gate_id": "renovate-output-verification",
        "description": (
            "Observe a Renovate Dependency Dashboard or first update pull request "
            "after maintainer-confirmed App activation."
        ),
        "state": "blocked",
        "evidence": [QUALITY_CLOSURE],
    })

    gates["stable-v1-release-approval"].update({
        "description": (
            "Obtain explicit approval for final stable v1 promotion; the existing "
            "v1.0.0rc1 authority is prerelease-only."
        ),
        "state": "blocked",
        "evidence": [
            "quality/qualifications/release-authority-v1.0.0rc1.json",
            "quality/qualifications/stable-v1-release-provenance-receipt.json",
        ],
    })
    gates["stable-v1-maturity-m5"].update({
        "description": (
            "Verify every blocking maturity dimension at M5 after Bronze scope "
            "and Renovate output verification complete."
        ),
        "state": "blocked",
        "evidence": [
            "conductor/maturity-model.json",
            BRONZE_PLAN,
            QUALITY_CLOSURE,
        ],
    })
    contract["release_gates"] = [
        *gates.values(),
        source_gate,
        renovate_gate,
    ]
    contract["unresolved_gate_ids"] = sorted(
        gate["gate_id"]
        for gate in contract["release_gates"]
        if gate["state"] != "passed"
    )
    contract["qualification_state"] = "blocked"
    return contract


def build_support(raw: dict[str, Any]) -> dict[str, Any]:
    """Return support readiness with production and Renovate boundaries split."""
    support = deepcopy(raw)
    for boundary in support["support_boundaries"]:
        if boundary["gate_id"] == "documentation-readiness":
            boundary["state"] = "passed"
            boundary["evidence"] = _append_unique(
                boundary["evidence"], ["SUPPORT.md", "SECURITY.md"]
            )
            boundary["blocker"] = None
    for risk in support["residual_risks"]:
        if risk["risk_id"] == "RISK-001":
            risk.update({
                "description": (
                    "Production backup storage, RPO, RTO and crash consistency "
                    "remain unqualified and are outside the software-only stable "
                    "release scope."
                ),
                "disposition": "accepted",
                "blocking": False,
                "gate_id": "production-dr-authority",
                "evidence": [PRODUCTION_DR],
            })
        elif risk["risk_id"] == "RISK-002":
            risk.update({
                "description": (
                    "Maintainer-confirmed Renovate activation has not produced "
                    "an observable Dependency Dashboard or update pull request."
                ),
                "disposition": "unresolved",
                "blocking": True,
                "gate_id": "renovate-output-verification",
                "evidence": [QUALITY_CLOSURE],
            })
    support["readiness_state"] = "blocked"
    return support


def main() -> None:
    contract = build_contract(json.loads(CONTRACT.read_text(encoding="utf-8")))
    support = build_support(json.loads(SUPPORT.read_text(encoding="utf-8")))
    CONTRACT.write_text(
        json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    SUPPORT.write_text(
        json.dumps(support, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
