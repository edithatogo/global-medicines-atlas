"""Contracts for durable operational-hardening evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).parents[1]
TRACK = ROOT / "conductor" / "archive" / "operational_hardening_20260729"


def _evidence() -> dict[str, dict[str, Any]]:
    records = [
        cast(
            "dict[str, Any]",
            json.loads(line),
        )
        for line in (TRACK / "evidence.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    return {
        cast("str", record["kind"]): record
        for record in records
        if isinstance(record.get("kind"), str)
    }


def test_hosted_operational_and_governance_evidence_is_durable() -> None:
    evidence = _evidence()
    exercise = evidence["operational_exercise_qualification"]
    governance = evidence["hosted_governance_reconciliation"]

    assert exercise["status"] == "hosted_pass_non_production"
    assert exercise["verification"]["required_checks"] == "26 passed"
    assert exercise["artifact"]["sha256"] == (
        "8a8da00d3bdd4c24b3548868be049e7577e05e2339e6aceb57970d19bab76e1f"
    )
    assert governance["verification"]["labels"]["manifest_present"] == 20
    assert governance["verification"]["project"]["backfilled_issues"] == [
        36,
        37,
        38,
        39,
        40,
        41,
        42,
        43,
    ]
    assert governance["limitations"]


def test_completed_tasks_remain_explicitly_bounded() -> None:
    plan = (TRACK / "plan.md").read_text(encoding="utf-8")

    assert "- [x] Task: Run threat model, load, soak, Scalene" in plan
    assert "- [x] Task: Verify hosted rulesets, security settings" in plan
    assert "explicitly denying production qualification" in plan
    assert "Renovate App activation remains an explicit" in plan


def test_v08_qualification_clears_numeric_gate_without_external_claims() -> (
    None
):
    qualification = cast(
        "dict[str, Any]",
        json.loads(
            (ROOT / "quality" / "qualifications" / "v08.json").read_text(
                encoding="utf-8"
            )
        ),
    )

    mutation = cast("dict[str, Any]", qualification["mutation"])
    assert qualification["status"] == "qualified"
    assert mutation["score_percent"] >= mutation["minimum_percent"]
    assert mutation["survived"] <= 381
    assert qualification["publication_authorized"] is False
    assert qualification["production_disaster_recovery_qualified"] is False
    assert qualification["renovate_app_activation_verified"] is False
