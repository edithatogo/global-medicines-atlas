"""Contracts for the declarative Test-Goblin inventory and quality budgets."""

from __future__ import annotations

import importlib.util
import json
import re
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


def test_ci_contracts_cover_every_lane_and_codecov_context() -> None:
    """CI and Codecov expose one independently observable context per lane."""
    result = HARNESS.validate_ci_contracts()

    assert result["lanes"] == sorted(HARNESS.PRIMARY_LANES)
    assert result["coverage_flags"] == sorted(HARNESS.PRIMARY_LANES)


def test_every_external_action_is_pinned_to_a_commit() -> None:
    """Mutable action tags cannot enter governed workflow execution."""
    actions = HARNESS.validate_action_pins()

    assert actions
    assert all(
        re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", action) for action in actions
    )


def test_action_pin_validation_covers_yaml_reusable_workflows(
    tmp_path, monkeypatch
) -> None:
    """Job-level reusable workflows in .yaml files cannot evade pinning."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "reusable.yaml").write_text(
        "jobs:\n  shared:\n    uses: owner/repo/.github/workflows/ci.yml@main\n"
    )
    monkeypatch.setattr(HARNESS, "WORKFLOWS_PATH", workflows)

    with pytest.raises(ValueError, match="mutable action reference"):
        HARNESS.validate_action_pins()


def test_action_pin_validation_recurses_through_job_and_step_uses(
    tmp_path, monkeypatch
) -> None:
    """Both reusable jobs and ordinary steps are discovered structurally."""
    digest = "a" * 40
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "all.yml").write_text(
        "jobs:\n"
        "  shared:\n"
        f"    uses: owner/repo/.github/workflows/ci.yml@{digest}\n"
        "  steps:\n"
        "    steps:\n"
        f"      - uses: owner/action@{digest}\n"
    )
    monkeypatch.setattr(HARNESS, "WORKFLOWS_PATH", workflows)

    assert len(HARNESS.validate_action_pins()) == 2


def test_tool_versions_match_governed_workflow_literals() -> None:
    """Workflow setup literals remain aligned with one governed manifest."""
    versions = HARNESS.validate_tool_versions()

    assert versions["python"] == "3.14.6"
    assert versions["uv"] == "0.11.29"
    assert versions["pixi"] == "0.73.0"
    assert versions["gitleaks"] == "8.30.1"
    assert versions["mojo"] == "1.0.0b3.dev2026072806"
    assert versions["runner"] == "ubuntu-24.04"


def test_governed_occurrence_validation_rejects_one_stale_runner() -> None:
    """One correct occurrence cannot hide drift elsewhere."""
    documents = {
        ROOT / "first.yml": {"jobs": {"a": {"runs-on": "ubuntu-24.04"}}},
        ROOT / "second.yaml": {"jobs": {"b": {"runs-on": "ubuntu-latest"}}},
    }

    with pytest.raises(ValueError, match=r"second\.yaml"):
        HARNESS._require_exact_occurrences(
            documents,
            key="runs-on",
            expected="ubuntu-24.04",
            label="runner",
        )


def test_measured_receipt_records_artifact_identity(
    tmp_path, monkeypatch
) -> None:
    """Measured evidence is durable and bound to the exact output bytes."""
    artifact = tmp_path / "profile.json"
    artifact.write_bytes(b'{"elapsed_seconds":1.25}\n')
    output = tmp_path / "receipt.json"
    monkeypatch.setattr(HARNESS, "git_commit", lambda: "a" * 40)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")

    receipt = HARNESS.write_quality_receipt(
        kind="performance",
        observations={"elapsed_seconds": 1.25},
        output_path=output,
        artifacts=[artifact],
        command=["scalene", "run"],
    )

    validated = HARNESS.validate_quality_receipt(
        output, expected_kind="performance", enforce=True
    )
    assert validated == receipt
    assert receipt["artifacts"][0]["path"] == artifact.as_posix()
    assert receipt["artifacts"][0]["sha256"] == (
        "eff0c2ee96cc14abfc22d9f8d0ce1a7cfe076363a5b21fd6ba406241a73b77e2"
    )


def test_lane_coverage_uses_unique_context(monkeypatch) -> None:
    """Each primary lane can emit a uniquely named coverage document."""
    commands: list[list[str]] = []
    monkeypatch.setattr(HARNESS, "run", commands.append)
    monkeypatch.setenv("TEST_GOBLIN_COVERAGE", "1")

    HARNESS.lane("property")

    assert "--cov-report=xml:coverage-property.xml" in commands[0]
    assert "--cov-context=test" in commands[0]


def test_supply_chain_manages_tool_literals_and_scans_history() -> None:
    """Dependency automation and leak detection cover governed non-PEP tools."""
    renovate = json.loads((ROOT / "renovate.json").read_text())
    managers = renovate["customManagers"]
    managed = "\n".join(
        expression
        for manager in managers
        for expression in manager["matchStrings"]
    )
    security = (
        ROOT / ".github" / "workflows" / "security-context.yml"
    ).read_text()

    for tool in (
        "python",
        "uv",
        "pixi",
        "actionlint",
        "gitleaks",
    ):
        assert f'"{tool}":' in managed
    assert (
        'mojo = "==1.0.0b3.dev2026072806"' in (ROOT / "pixi.toml").read_text()
    )
    assert "fetch-depth: 0" in security
    assert "./gitleaks git --redact" in security
    assert "GITLEAKS_SHA256:" in security
    assert "GITLEAKS_ASSET:" in security


def test_mutmut_observations_come_from_authoritative_export(
    tmp_path,
) -> None:
    """The receipt consumes Mutmut's numeric export without invented counts."""
    artifact = tmp_path / "mutmut-cicd-stats.json"
    artifact.write_text(
        json.dumps({
            "killed": 7,
            "survived": 2,
            "total": 12,
            "no_tests": 1,
            "skipped": 1,
            "suspicious": 0,
            "timeout": 1,
            "check_was_interrupted_by_user": 0,
            "segfault": 0,
        })
    )

    observations = HARNESS.load_mutmut_observations(artifact)

    assert observations["killed"] == 7
    assert observations["survived"] == 2
    assert observations["untested"] == 1
    assert observations["total"] == 12


def test_mutmut_observations_reject_missing_or_non_numeric_results(
    tmp_path,
) -> None:
    """A successful lane cannot fabricate evidence from absent/bad output."""
    missing = tmp_path / "missing.json"
    with pytest.raises(ValueError, match="did not emit"):
        HARNESS.load_mutmut_observations(missing)

    malformed = tmp_path / "bad.json"
    malformed.write_text(json.dumps({"killed": True}))
    with pytest.raises(ValueError, match="unexpected Mutmut"):
        HARNESS.load_mutmut_observations(malformed)
