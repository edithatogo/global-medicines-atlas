"""Contracts for the declarative Test-Goblin inventory and quality budgets."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest

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


def test_collection_profile_uses_manifest_validation(monkeypatch) -> None:
    """Collection loads the marker plugin over the complete manifest."""
    commands: list[list[str]] = []
    monkeypatch.setattr(HARNESS, "run", commands.append)

    HARNESS.validate_collection()

    assert commands[0][3 : 3 + len(HARNESS.ALL_TESTS)] == list(
        HARNESS.ALL_TESTS
    )
    assert "--collect-only" in commands[0]
    assert commands[0][-2:] == ["-p", "scripts.test_goblin"]


def test_collection_assigns_the_manifest_primary_marker() -> None:
    """Unmarked items receive exactly their generated primary marker."""

    class Item:
        path = ROOT / "tests" / "test_smoke.py"
        nodeid = "tests/test_smoke.py::test_example"

        def __init__(self) -> None:
            self.markers: list[SimpleNamespace] = []

        def iter_markers(self):
            return iter(self.markers)

        def add_marker(self, name: str) -> None:
            self.markers.append(SimpleNamespace(name=name))

    item = Item()
    HARNESS.pytest_collection_modifyitems([item])

    assert [marker.name for marker in item.markers] == ["smoke"]


def test_collection_preserves_one_explicit_item_marker() -> None:
    """An explicit item marker may refine its file's fallback lane."""

    class Marker:
        name = "unit"

    class Item:
        path = ROOT / "tests" / "test_smoke.py"
        nodeid = "tests/test_smoke.py::test_example"

        @staticmethod
        def iter_markers():
            return iter([Marker()])

        @staticmethod
        def add_marker(_name: str) -> None:
            raise AssertionError("existing marker must not be replaced")

    HARNESS.pytest_collection_modifyitems([Item()])


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


def test_contract_only_receipt_cannot_be_enforced(tmp_path) -> None:
    """Contract declarations cannot masquerade as measured evidence."""
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps({
            "schema_version": "1.0.0",
            "kind": "mutation",
            "evidence_state": "contract_only",
        })
    )

    with pytest.raises(ValueError, match="requires a measured receipt"):
        HARNESS.validate_quality_receipt(
            receipt, expected_kind="mutation", enforce=True
        )


def test_measured_receipt_requires_observations(tmp_path) -> None:
    """Measured status without measurements fails schema validation."""
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps({
            "schema_version": "1.0.0",
            "kind": "performance",
            "evidence_state": "measured",
        })
    )

    with pytest.raises(jsonschema.ValidationError):
        HARNESS.validate_quality_receipt(
            receipt, expected_kind="performance", enforce=True
        )


def test_coverage_reads_machine_readable_threshold(monkeypatch) -> None:
    """Coverage enforcement consumes the validated budget value."""
    commands: list[list[str]] = []
    monkeypatch.setattr(HARNESS, "run", commands.append)

    HARNESS.coverage()

    assert "--cov-fail-under=91.0" in commands[0]


def test_contract_profile_validates_before_running_pytest(monkeypatch) -> None:
    """The contract profile performs collection but no test execution."""
    commands: list[object] = []
    monkeypatch.setattr(HARNESS, "run", commands.append)

    HARNESS.contracts()

    assert len(commands) == 1
    assert "--collect-only" in commands[0]
