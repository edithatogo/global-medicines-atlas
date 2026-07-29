"""Contracts for the declarative Test-Goblin inventory and quality budgets."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "test_goblin_harness", ROOT / "scripts" / "test_goblin.py"
)
assert SPEC is not None
assert SPEC.loader is not None
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


def test_primary_lane_inventory_is_complete_and_unique() -> None:
    """Every test module has one, and only one, primary execution lane."""
    inventory = HARNESS.validate_test_inventory()

    assert inventory == tuple(
        sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "tests").glob("test_*.py")
        )
    )
    assert len(inventory) == len(set(inventory))


def test_quality_budgets_are_machine_readable_contracts() -> None:
    """Numeric thresholds exist without claiming uncollected measurements."""
    budgets = HARNESS.load_quality_budgets()
    schema = json.loads((ROOT / "quality" / "budgets.schema.json").read_text())

    jsonschema.validate(budgets, schema)
    assert budgets["evidence_state"] == "contract_only"
    assert budgets["coverage"]["line_percent"]["minimum"] > 90
    assert budgets["mutation"]["score_percent"]["minimum"] > 0
    assert budgets["latency"]["p95_ms"]["maximum"] > 0
    assert budgets["throughput"]["records_per_second"]["minimum"] > 0
    assert budgets["cpu"]["seconds"]["maximum"] > 0
    assert budgets["memory"]["peak_mib"]["maximum"] > 0
    assert budgets["allocation"]["peak_mib"]["maximum"] > 0


def test_contract_profile_validates_before_running_pytest(monkeypatch) -> None:
    """The cheap contract profile performs no test or benchmark execution."""
    commands: list[object] = []
    monkeypatch.setattr(HARNESS, "run", commands.append)

    HARNESS.contracts()

    assert commands == []
