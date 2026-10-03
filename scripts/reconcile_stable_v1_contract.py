"""Reconcile stable-v1 qualification with current durable evidence."""

from __future__ import annotations

import hashlib
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
BRONZE_SCOPE_DECISION = (
    "quality/qualifications/bronze-bounded-scope-decision-v1.json"
)
BRONZE_FUTURE_SOURCES = (
    "quality/qualifications/bronze-bounded-scope-future-sources-v1.json"
)
QUALITY_CLOSURE = "quality/qualifications/quality-hardening-closure.json"
AUSTRALIAN_HEALTH_GATE = "stable-v1-australian-health-federation"
SCRAPER_ARCHIVE = "quality/qualifications/scraper-archival-20260906.json"
GRAPH_ARCHIVE = "quality/qualifications/graph-archival-20260906.json"
AUSTRALIAN_ACCEPTANCE = (
    "docs/qualification/australian-health-federation-acceptance.md"
)
DONOR_HISTORY_OBJECT_COUNT = 30
AUSTRALIAN_HEALTH_REQUIREMENTS = {
    "M-105",
    "M-106",
    "M-107",
    "M-108",
    "M-109",
    "M-110",
    "M-111",
    "M-112",
    "M-113",
}

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


def _retain_gate_observation(
    gate: dict[str, Any], updates: dict[str, Any]
) -> None:
    """Add known blockers without erasing adverse observations or receipts."""
    updates["state"] = "blocked" if gate["state"] == "passed" else gate["state"]
    updates["evidence"] = _append_unique(gate["evidence"], updates["evidence"])
    gate.update(updates)


def _renovate_output_observed() -> bool:
    """Return whether the durable closure receipt records bot output."""
    closure = json.loads((ROOT / QUALITY_CLOSURE).read_text(encoding="utf-8"))
    return closure["renovate"]["dashboard_or_first_pr"] == "observed"


def _bronze_bounded_scope_qualified() -> bool:
    """Require the versioned horizon, partition, and evidence counts to agree."""
    report = json.loads((ROOT / BRONZE_MATURITY).read_text(encoding="utf-8"))
    decision = json.loads(
        (ROOT / BRONZE_SCOPE_DECISION).read_text(encoding="utf-8")
    )
    ledger = json.loads(
        (ROOT / BRONZE_FUTURE_SOURCES).read_text(encoding="utf-8")
    )
    inventory = report["completeness_inventory"]
    accounting = ledger["source_accounting"]
    decision_digest = hashlib.sha256(
        (ROOT / BRONZE_SCOPE_DECISION).read_bytes()
    ).hexdigest()
    return bool(
        report["horizon"] == "bronze-bounded-public-scope-v1"
        and report["qualification_state"] == "qualified"
        and report["bronze_mature"] is True
        and inventory["bronze_in_scope_count"]
        == decision["active_scope_source_count"]
        and inventory["full_bronze_source_universe_count"]
        == decision["full_scope_source_count"]
        and inventory["deferred_source_count"]
        == decision["deferred_source_count"]
        and inventory["in_scope_without_landing_or_blocker"] == 0
        and accounting["partition_complete"] is True
        and accounting["deferred_source_count"]
        == decision["deferred_source_count"]
        and ledger["qualification_state"] == report["qualification_state"]
        and ledger["scope_decision"]["sha256"] == decision_digest
        and ledger["boundaries"]["missing_coverage_is_not_negative_evidence"]
        is True
    )


def _donor_archive_acceptance_observed() -> bool:
    """Require both approved archives and exact public history restoration."""
    scraper = json.loads((ROOT / SCRAPER_ARCHIVE).read_text(encoding="utf-8"))
    graph = json.loads((ROOT / GRAPH_ARCHIVE).read_text(encoding="utf-8"))
    restored = {
        item["repository"]: item for item in scraper["publication"]["restored"]
    }
    expected = {
        "edithatogo/aus_mbs_pbs_graph": (
            "3993e5e331eb2d3d9e9d354d80e52c684ad26a1e"
        ),
        "edithatogo/aus-health-data-scraper": (
            "009e80544588a956c8922aaab052ee08947e2b30"
        ),
    }
    if set(restored) != set(expected):
        return False
    checks = (
        scraper["repository"] == "edithatogo/aus-health-data-scraper",
        scraper["approval_reference"]
        == "https://github.com/edithatogo/global-medicines-atlas/issues/339#issuecomment-5556212193",
        scraper["archival"]["after"] is True,
        scraper["publication"]["run_conclusion"] == "success",
        scraper["publication"]["current_revision_equals_verified"] is True,
        scraper["publication"]["verified_objects"]
        == DONOR_HISTORY_OBJECT_COUNT,
        graph["repository"] == "edithatogo/aus_mbs_pbs_graph",
        graph["approval_and_execution_receipt"]
        == "https://github.com/edithatogo/global-medicines-atlas/issues/339#issuecomment-5556516869",
        graph["archive_authorized"] is True,
        graph["archived_after"] is True,
        graph["public_revision_current_at_preflight"] is True,
        graph["public_history_revision"] == scraper["publication"]["revision"],
        all(item["clean_restore"] is True for item in restored.values()),
        all(restored[name]["head"] == head for name, head in expected.items()),
        scraper["archival"]["head_before"]
        == expected["edithatogo/aus-health-data-scraper"],
        scraper["archival"]["head_after"]
        == expected["edithatogo/aus-health-data-scraper"],
        scraper["archival"]["retained_branches"]["main"]
        == expected["edithatogo/aus-health-data-scraper"],
        graph["head_before"] == expected["edithatogo/aus_mbs_pbs_graph"],
        graph["head_after"] == expected["edithatogo/aus_mbs_pbs_graph"],
        graph["retained_branches"]["main"]
        == expected["edithatogo/aus_mbs_pbs_graph"],
    )
    return all(checks)


def build_contract(  # ruff: ignore[too-many-branches,too-many-statements]
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Reconcile known blockers without promoting supplied evidence states.

    Historical implementation references are not fresh validation receipts.
    Failed or unverified observations must survive regeneration unchanged.
    """
    contract = deepcopy(raw)
    renovate_observed = _renovate_output_observed()
    bronze_scope_qualified = _bronze_bounded_scope_qualified()
    for requirement in contract["requirements"]:
        requirement_id = requirement["requirement_id"]
        if requirement_id == "M-046":
            requirement["evidence"] = _append_unique(
                requirement["evidence"], [QUALITY_CLOSURE]
            )
            if renovate_observed:
                requirement["state"] = "verified"
                requirement["blocker_ids"] = [
                    blocker
                    for blocker in requirement["blocker_ids"]
                    if blocker != "renovate-output-verification"
                ]
            else:
                requirement["state"] = "blocked"
                requirement["blocker_ids"] = _append_unique(
                    requirement["blocker_ids"], ["renovate-output-verification"]
                )
        elif requirement_id == "M-095":
            other_blockers = set(requirement["blocker_ids"]) - {
                "stable-v1-bronze-current-scope"
            }
            if (
                bronze_scope_qualified
                and not other_blockers
                and requirement["state"] not in {"failed", "unverified"}
            ):
                requirement["state"] = "verified"
                requirement["blocker_ids"] = [
                    blocker
                    for blocker in requirement["blocker_ids"]
                    if blocker != "stable-v1-bronze-current-scope"
                ]
            else:
                requirement["state"] = "blocked"
                requirement["blocker_ids"] = _append_unique(
                    requirement["blocker_ids"],
                    ["stable-v1-bronze-current-scope"],
                )
            requirement["evidence"] = _append_unique(
                requirement["evidence"],
                [
                    BRONZE_PLAN,
                    BRONZE_MATURITY,
                    BRONZE_SCOPE_DECISION,
                    BRONZE_FUTURE_SOURCES,
                ],
            )
        elif requirement_id == "M-113":
            adverse = requirement["state"] in {"failed", "unverified"}
            other_blockers = set(requirement["blocker_ids"]) - {
                AUSTRALIAN_HEALTH_GATE
            }
            if adverse:
                continue
            if other_blockers:
                requirement["state"] = "blocked"
            elif _donor_archive_acceptance_observed():
                requirement["state"] = "verified"
                requirement["blocker_ids"] = []
                requirement["evidence"] = _append_unique(
                    requirement["evidence"],
                    [SCRAPER_ARCHIVE, GRAPH_ARCHIVE, AUSTRALIAN_ACCEPTANCE],
                )
            else:
                requirement["state"] = "blocked"
                requirement["blocker_ids"] = _append_unique(
                    requirement["blocker_ids"], [AUSTRALIAN_HEALTH_GATE]
                )
        elif requirement_id in AUSTRALIAN_HEALTH_REQUIREMENTS:
            requirement["state"] = "blocked"
            requirement["blocker_ids"] = _append_unique(
                requirement["blocker_ids"], [AUSTRALIAN_HEALTH_GATE]
            )
        elif requirement["evidence"] == ["conductor/requirements.md"]:
            requirement["evidence"] = _append_unique(
                requirement["evidence"], [STABLE_LEDGER]
            )

    for dimension in contract["maturity_dimensions"]:
        name = dimension["dimension"]
        if name == "source_coverage":
            adverse = dimension["state"] in {"failed", "unverified"}
            other_blockers = set(dimension["blocker_ids"]) - {
                "stable-v1-bronze-current-scope"
            }
            if bronze_scope_qualified and not adverse and not other_blockers:
                dimension["current_level"] = "M5"
                dimension["state"] = "verified"
                dimension["blocker_ids"] = [
                    blocker
                    for blocker in dimension["blocker_ids"]
                    if blocker != "stable-v1-bronze-current-scope"
                ]
            else:
                dimension["current_level"] = min(
                    dimension["current_level"], "M4"
                )
                if dimension["state"] == "verified":
                    dimension["state"] = "partial"
                dimension["blocker_ids"] = _append_unique(
                    dimension["blocker_ids"], ["stable-v1-bronze-current-scope"]
                )
            dimension["evidence"] = _append_unique(
                dimension["evidence"],
                [
                    BRONZE_PLAN,
                    BRONZE_MATURITY,
                    BRONZE_SCOPE_DECISION,
                    BRONZE_FUTURE_SOURCES,
                ],
            )
        elif name == "security_and_supply_chain":
            dimension["evidence"] = _append_unique(
                dimension["evidence"], [QUALITY_CLOSURE]
            )
            if renovate_observed and dimension["state"] != "unverified":
                dimension["current_level"] = "M5"
                dimension["state"] = "verified"
                dimension["blocker_ids"] = [
                    blocker
                    for blocker in dimension["blocker_ids"]
                    if blocker != "renovate-output-verification"
                ]
            else:
                dimension["current_level"] = min(
                    dimension["current_level"], "M4"
                )
                if dimension["state"] == "verified":
                    dimension["state"] = "partial"
                dimension["blocker_ids"] = _append_unique(
                    dimension["blocker_ids"], ["renovate-output-verification"]
                )
        else:
            dimension["evidence"] = _append_unique(
                dimension["evidence"], [INDEPENDENT_REPRODUCTION, STABLE_LEDGER]
            )

    contract["support"]["evidence"] = _append_unique(
        contract["support"]["evidence"], ["SUPPORT.md", "SECURITY.md"]
    )

    for risk in contract["residual_risks"]:
        if risk["risk_id"] == "RISK-002":
            risk.update({
                "description": (
                    "Renovate's Dependency Dashboard is observed at issue #491."
                    if renovate_observed
                    else "Maintainer-confirmed Renovate activation has not produced "
                    "an observable Dependency Dashboard or update pull request."
                ),
                "disposition": "mitigated"
                if renovate_observed
                else "unresolved",
                "blocking": not renovate_observed,
                "evidence": [QUALITY_CLOSURE],
            })

    gates = {gate["gate_id"]: gate for gate in contract["release_gates"]}
    if len(gates) != len(contract["release_gates"]):
        raise ValueError("duplicate release gate identifiers")
    for gate_id, evidence in TECHNICAL_GATE_EVIDENCE.items():
        gate = gates[gate_id]
        gate["evidence"] = _append_unique(gate["evidence"], evidence)
    gates[AUSTRALIAN_HEALTH_GATE]["evidence"] = _append_unique(
        gates[AUSTRALIAN_HEALTH_GATE]["evidence"],
        [AUSTRALIAN_ACCEPTANCE, SCRAPER_ARCHIVE, GRAPH_ARCHIVE],
    )

    source_gate_id = (
        "stable-v1-source-maturity"
        if "stable-v1-source-maturity" in gates
        else "stable-v1-bronze-current-scope"
    )
    source_gate = gates.pop(source_gate_id)
    source_gate.update({
        "gate_id": "stable-v1-bronze-current-scope",
        "description": (
            "Complete Bronze evidence for the maintainer-approved bounded public "
            "horizon while retaining the full catalogue universe and deferred ledger."
        ),
        "state": (
            source_gate["state"]
            if source_gate["state"] in {"failed", "unverified"}
            else "passed"
            if bronze_scope_qualified
            else "blocked"
        ),
        "evidence": _append_unique(
            source_gate["evidence"],
            [
                BRONZE_PLAN,
                BRONZE_MATURITY,
                BRONZE_SCOPE_DECISION,
                BRONZE_FUTURE_SOURCES,
            ],
        ),
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
        "state": (
            "passed"
            if renovate_observed
            and renovate_gate["state"] not in {"failed", "unverified"}
            else renovate_gate["state"]
        ),
        "evidence": _append_unique(
            renovate_gate["evidence"], [QUALITY_CLOSURE]
        ),
    })

    _retain_gate_observation(
        gates["stable-v1-release-approval"],
        {
            "description": (
                "Obtain explicit approval for final stable v1 promotion; the existing "
                "v1.0.0rc1 authority is prerelease-only."
            ),
            "state": "blocked",
            "evidence": [
                "quality/qualifications/release-authority-v1.0.0rc1.json",
                "quality/qualifications/stable-v1-release-provenance-receipt.json",
            ],
        },
    )
    maturity_gate = gates["stable-v1-maturity-m5"]
    dimensions_ready = all(
        dimension["current_level"] == "M5"
        and dimension["state"] == "verified"
        and not dimension["blocker_ids"]
        for dimension in contract["maturity_dimensions"]
    )
    maturity_gate.update({
        "description": (
            "Verify every maturity dimension at M5 after bounded Bronze source "
            "coverage and Renovate output verification complete."
        ),
        "state": (
            maturity_gate["state"]
            if maturity_gate["state"] in {"failed", "unverified"}
            else "passed"
            if dimensions_ready
            else "blocked"
        ),
        "evidence": _append_unique(
            maturity_gate["evidence"],
            [
                "conductor/maturity-model.json",
                BRONZE_PLAN,
                BRONZE_MATURITY,
                BRONZE_SCOPE_DECISION,
                BRONZE_FUTURE_SOURCES,
                QUALITY_CLOSURE,
            ],
        ),
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
    renovate_observed = _renovate_output_observed()
    for boundary in support["support_boundaries"]:
        if boundary["gate_id"] == "documentation-readiness":
            boundary["evidence"] = _append_unique(
                boundary["evidence"], ["SUPPORT.md", "SECURITY.md"]
            )
    for risk in support["residual_risks"]:
        if risk["risk_id"] == "RISK-002":
            risk.update({
                "description": (
                    "Renovate's Dependency Dashboard is observed at issue #491."
                    if renovate_observed
                    else "Maintainer-confirmed Renovate activation has not produced "
                    "an observable Dependency Dashboard or update pull request."
                ),
                "disposition": "mitigated"
                if renovate_observed
                else "unresolved",
                "blocking": not renovate_observed,
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
