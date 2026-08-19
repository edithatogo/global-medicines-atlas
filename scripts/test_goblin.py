"""Executable Test-Goblin harness for governed Python code."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

import jsonschema
import yaml

from global_medicines_atlas.quality_baselines import (
    MutationObservations,
    load_phase3_baselines,
    mutation_regressed,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUALITY_BUDGETS_PATH = PROJECT_ROOT / "quality" / "budgets.json"
QUALITY_BUDGETS_SCHEMA_PATH = PROJECT_ROOT / "quality" / "budgets.schema.json"
QUALITY_RECEIPT_SCHEMA_PATH = (
    PROJECT_ROOT / "quality" / "evidence-receipt.schema.json"
)
TOOL_VERSIONS_PATH = PROJECT_ROOT / "quality" / "tool-versions.json"
PHASE3_BASELINES_PATH = PROJECT_ROOT / "quality" / "baselines" / "phase3.json"
WORKFLOWS_PATH = PROJECT_ROOT / ".github" / "workflows"
CODECOV_PATH = PROJECT_ROOT / "codecov.yml"
PRIMARY_LANES = frozenset({
    "unit",
    "integration",
    "e2e",
    "smoke",
    "property",
    "edge",
})


class MarkerLike(Protocol):
    """Minimal marker shape consumed by the collection validator."""

    name: str


class ItemLike(Protocol):
    """Minimal pytest item shape consumed by the collection validator."""

    path: object
    nodeid: str

    def iter_markers(self) -> Sequence[MarkerLike]:
        """Return attached markers."""
        ...

    def add_marker(self, marker: str) -> None:
        """Attach a generated primary marker."""
        ...


TEST_LANES: dict[str, tuple[str, ...]] = {
    "unit": (
        "tests/test_academic_preregistration.py",
        "tests/test_academic_analysis_plan.py",
        "tests/test_academic_protocol.py",
        "tests/test_conductor_github_sync.py",
        "tests/test_country_adapter_registry.py",
        "tests/test_context_validation.py",
        "tests/test_medallion_datahouse_contract.py",
        "tests/test_ecosystem_reuse.py",
        "tests/test_reuse_gate.py",
        "tests/test_temporal_identity.py",
        "tests/test_bronze_landing.py",
        "tests/test_openlineage_projection.py",
        "tests/test_iceberg_ready.py",
        "tests/test_settings.py",
        "tests/test_logging.py",
        "tests/test_matching_models.py",
        "tests/test_matching_evaluation.py",
        "tests/test_matching_normalization.py",
        "tests/test_matching_identifiers.py",
        "tests/test_matching_lexical.py",
        "tests/test_matching_features.py",
        "tests/test_matching_policy.py",
        "tests/test_review_queue.py",
        "tests/test_rxnorm_lineage.py",
        "tests/test_matching_release.py",
        "tests/test_product_contracts.py",
        "tests/test_product_release.py",
        "tests/test_product_security.py",
        "tests/test_protected_evidence.py",
        "tests/test_quality_baselines.py",
        "tests/test_product_performance.py",
        "tests/test_source_catalog.py",
        "tests/test_source_census.py",
        "tests/test_source_profiles.py",
        "tests/test_repository_governance.py",
        "tests/test_operational_track_evidence.py",
        "tests/test_stable_v1_qualification_contract.py",
        "tests/test_stable_v1_monitoring.py",
        "tests/test_stable_v1_documentation.py",
        "tests/test_stable_v1_hosted_governance.py",
        "tests/test_openapi_semantic.py",
        "tests/test_canonical_v2_runtime.py",
        "tests/test_comparison_validity.py",
        "tests/test_concept_discovery_contracts.py",
        "tests/test_documentation_contracts.py",
        "tests/test_ingestor_contracts.py",
        "tests/test_javascript_style.py",
        "tests/test_source_parity.py",
        "tests/test_country_publication_gate.py",
        "tests/test_source_health.py",
        "tests/test_source_rights_disposition.py",
        "tests/test_source_receipts.py",
        "tests/test_temporal_coverage.py",
        "tests/test_terminology_resolver.py",
        "tests/test_temporal_evidence.py",
        "tests/test_release_evidence.py",
        "tests/test_release_cli.py",
        "tests/test_release_workflow.py",
        "tests/test_publication_contracts.py",
        "tests/test_publication_identity_registry.py",
        "tests/test_release_authority.py",
        "tests/test_release_metadata.py",
        "tests/test_release_qualification.py",
        "tests/test_stable_v1_release_candidate.py",
        "tests/test_contract_testing.py",
        "tests/test_v07_fixture_production_qualification.py",
        "tests/test_version.py",
        "tests/test_test_goblin_harness.py",
    ),
    "integration": (
        "tests/test_nz_asset_inventory.py",
        "tests/test_nz_consolidation.py",
        "tests/test_nz_fixture_indexes.py",
        "tests/test_nzmedicines_history_restoration.py",
        "tests/test_nzulm_fhir_adapter.py",
        "tests/test_us_drugsfda_adapter.py",
        "tests/test_us_acquisition.py",
        "tests/test_us_cms_partd_adapter.py",
        "tests/test_first_party_adapters.py",
        "tests/test_global_fixture_adapters.py",
        "tests/test_matching_pipeline.py",
        "tests/test_matching_rxnorm.py",
        "tests/test_semantic_retrieval.py",
        "tests/test_matching_indexes.py",
        "tests/test_matching_index_regeneration.py",
        "tests/test_matching_columnar.py",
        "tests/test_matching_review_queue_generation.py",
        "tests/test_matching_benchmarks.py",
        "tests/test_matching_engine_parity.py",
        "tests/test_mojo_qualification.py",
        "tests/test_query_service.py",
        "tests/test_concept_query_service.py",
        "tests/test_concept_api.py",
        "tests/test_concept_cli.py",
        "tests/test_consumer_qualification.py",
        "tests/test_product_api.py",
        "tests/test_product_cli.py",
        "tests/test_canada_native_adapters.py",
        "tests/test_eu_uk_native_adapters.py",
        "tests/test_japan_native_adapters.py",
        "tests/test_columnar.py",
        "tests/test_source_acquisition.py",
        "tests/test_temporal_snapshots.py",
        "tests/test_publication_package.py",
        "tests/test_stable_v1_publication_metadata.py",
        "tests/test_stable_v1_release_candidate_reproducibility.py",
        "tests/test_publication_transport.py",
        "tests/test_data_layer_archive.py",
        "tests/test_clean_room_rehearsal.py",
        "tests/test_performance_workload.py",
        "tests/test_recovery.py",
        "tests/test_recovery_rehearsal.py",
        "tests/test_operational_exercises.py",
        "tests/test_stable_v1_incident_rehearsal.py",
        "tests/test_stable_v1_rehearsal.py",
        "tests/test_canonical_v2_cohorts.py",
        "tests/test_stable_v1_measured_coverage.py",
        "tests/test_deterministic_simulation.py",
    ),
    "e2e": (
        "tests/test_canonical_nz_adapter.py",
        "tests/test_country_comparison_e2e.py",
        "tests/test_matching_e2e.py",
        "tests/test_atlas_e2e.py",
        "tests/test_atlas_discovery_e2e.py",
        "tests/test_stable_v1_e2e_qualification.py",
    ),
    "smoke": (
        "tests/test_smoke.py",
        "tests/test_core_without_semantic_extra.py",
    ),
    "property": (
        "tests/test_nzulm_fhir_properties.py",
        "tests/test_matching_properties.py",
        "tests/test_concept_discovery_properties.py",
        "tests/test_comparison_validity_properties.py",
        "tests/test_metamorphic_testing.py",
    ),
    "edge": (
        "tests/test_edge_cases.py",
        "tests/test_matching_adversarial.py",
        "tests/test_atlas_accessibility.py",
        "tests/test_archive_safety.py",
        "tests/test_data_integrity.py",
        "tests/test_parser_safety.py",
    ),
}

SPECIALIZED_TEST_PROFILES: dict[str, tuple[str, ...]] = {
    "metamorphic": ("tests/test_metamorphic_testing.py",),
    "contract": ("tests/test_contract_testing.py",),
    "simulation": ("tests/test_deterministic_simulation.py",),
}


def validate_test_inventory() -> tuple[str, ...]:
    """Return the complete inventory or fail on missing/duplicate primary lanes."""
    assigned = [path for paths in TEST_LANES.values() for path in paths]
    discovered = sorted(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in (PROJECT_ROOT / "tests").glob("test_*.py")
    )
    duplicates = sorted({path for path in assigned if assigned.count(path) > 1})
    missing = sorted(set(discovered) - set(assigned))
    unknown = sorted(set(assigned) - set(discovered))
    problems: list[str] = []
    if duplicates:
        problems.append(f"duplicate primary lanes: {duplicates}")
    if missing:
        problems.append(f"unassigned tests: {missing}")
    if unknown:
        problems.append(f"unknown tests: {unknown}")
    if problems:
        raise ValueError("; ".join(problems))
    return tuple(discovered)


def load_quality_budgets() -> dict[str, object]:
    """Load numeric promotion contracts without manufacturing observations."""
    document = json.loads(QUALITY_BUDGETS_PATH.read_text(encoding="utf-8"))
    schema = json.loads(QUALITY_BUDGETS_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(  # pyright: ignore[reportUnknownMemberType]
        document, schema
    )
    return document


def validate_ci_contracts() -> dict[str, list[str]]:
    """Validate lane execution and independently visible Codecov contexts."""
    workflow = (WORKFLOWS_PATH / "test-goblin.yml").read_text(encoding="utf-8")
    codecov = CODECOV_PATH.read_text(encoding="utf-8")
    lane_match = re.search(r"lane:\s*\[([^\]]+)\]", workflow)
    if lane_match is None:
        raise ValueError("test workflow has no explicit lane matrix")
    lanes = sorted(
        value.strip()
        for value in lane_match.group(1).split(",")
        if value.strip()
    )
    expected = sorted(PRIMARY_LANES)
    if lanes != expected:
        raise ValueError(f"CI lanes differ from harness: {lanes} != {expected}")
    if 'TEST_GOBLIN_COVERAGE: "1"' not in workflow:
        raise ValueError("lane-specific coverage is not enabled")
    if "flags: ${{ matrix.lane }}" not in workflow:
        raise ValueError("Codecov upload is not bound to the lane")
    coverage_flags = sorted(
        flag
        for flag in PRIMARY_LANES
        if re.search(rf"(?m)^\s{{2}}{re.escape(flag)}:\s*$", codecov)
    )
    if coverage_flags != expected:
        raise ValueError(
            f"Codecov flags differ from harness: {coverage_flags} != {expected}"
        )
    return {"lanes": lanes, "coverage_flags": coverage_flags}


def validate_action_pins() -> list[str]:
    """Return external actions after rejecting every mutable reference."""
    actions: list[str] = []
    for workflow_path in workflow_paths():
        document = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        for action in recursive_values(document, key="uses"):
            if not isinstance(action, str):
                raise TypeError(
                    f"{display_path(workflow_path)} has a non-string uses value"
                )
            if action.startswith("./"):
                continue
            if re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", action) is None:
                raise ValueError(
                    f"{display_path(workflow_path)} uses mutable "
                    f"action reference {action}"
                )
            actions.append(action)
    if not actions:
        raise ValueError("no external GitHub Actions found")
    return actions


def display_path(path: Path) -> str:
    """Return a stable project-relative path where possible."""
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def workflow_paths() -> tuple[Path, ...]:
    """Return active root workflows; vendored migration history is inert."""
    return tuple(
        sorted((
            *WORKFLOWS_PATH.glob("*.yml"),
            *WORKFLOWS_PATH.glob("*.yaml"),
        ))
    )


def recursive_values(value: object, *, key: str) -> list[object]:
    """Collect values for one mapping key at arbitrary YAML depth."""
    found: list[object] = []
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        for current_key, current_value in mapping.items():
            if current_key == key:
                found.append(current_value)
            found.extend(recursive_values(current_value, key=key))
    elif isinstance(value, list):
        for item in cast("list[object]", value):
            found.extend(recursive_values(item, key=key))
    return found


def _workflow_documents() -> dict[Path, object]:
    return {
        path: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in workflow_paths()
    }


def _require_exact_occurrences(
    documents: dict[Path, object],
    *,
    key: str,
    expected: str,
    label: str,
) -> None:
    occurrences = [
        (path, value)
        for path, document in documents.items()
        for value in recursive_values(document, key=key)
    ]
    if not occurrences:
        raise ValueError(f"no governed {label} occurrences found")
    drift = [
        f"{display_path(path)}={value!r}"
        for path, value in occurrences
        if value != expected
    ]
    if drift:
        raise ValueError(f"governed {label} differs from {expected!r}: {drift}")


def _validate_setup_versions(
    documents: dict[Path, object],
    versions: dict[str, str],
    workflow_text: str,
) -> None:
    setup_versions = [
        str(value)
        for document_value in documents.values()
        for value in recursive_values(document_value, key="version")
    ]
    if not setup_versions or any(
        value != versions["uv"] for value in setup_versions
    ):
        raise ValueError(
            f"setup-uv versions differ from governed uv {versions['uv']}: "
            f"{setup_versions}"
        )
    pixi_versions = [
        str(value)
        for document_value in documents.values()
        for value in recursive_values(document_value, key="pixi-version")
    ]
    expected_pixi = f"v{versions['pixi']}"
    if pixi_versions != [expected_pixi]:
        raise ValueError(
            f"setup-pixi versions differ from {expected_pixi}: {pixi_versions}"
        )
    python_occurrences = re.findall(
        r"--python\s+(\d+\.\d+\.\d+)", workflow_text
    )
    if not python_occurrences or any(
        value != versions["python"] for value in python_occurrences
    ):
        raise ValueError(
            "workflow Python versions differ from governed Python "
            f"{versions['python']}: {python_occurrences}"
        )
    python_file = (
        (PROJECT_ROOT / ".python-version").read_text(encoding="utf-8").strip()
    )
    if python_file != versions["python"]:
        raise ValueError(".python-version differs from governed Python")


def _validate_runners(
    documents: dict[Path, object], versions: dict[str, str]
) -> None:
    occurrences = [
        value
        for document in documents.values()
        for value in recursive_values(document, key="runs-on")
    ]
    matrix_expression = "${{ matrix.runner }}"
    allowed = {versions["runner"], matrix_expression}
    drift = [value for value in occurrences if value not in allowed]
    if not occurrences or drift:
        raise ValueError(f"workflow runners are not governed: {drift}")

    contract = json.loads(
        (
            PROJECT_ROOT
            / "quality/qualifications/stable-v1-consumer-compatibility.json"
        ).read_text(encoding="utf-8")
    )
    contracted = set(cast("dict[str, str]", contract["runners"]).values())
    workflow = cast(
        "dict[str, Any]",
        documents[WORKFLOWS_PATH / "test-goblin.yml"],
    )
    jobs = cast("dict[str, Any]", workflow["jobs"])
    consumer = cast("dict[str, Any]", jobs["consumer-compatibility"])
    strategy = cast("dict[str, Any]", consumer["strategy"])
    matrix = cast("dict[str, Any]", strategy["matrix"])
    included = cast("list[dict[str, str]]", matrix["include"])
    observed = {item["runner"] for item in included}
    if observed != contracted:
        raise ValueError(
            f"consumer runner matrix differs from contract: {observed}"
        )


def _validate_gitleaks_contract(
    documents: dict[Path, object],
    versions: dict[str, str],
    checksums: dict[str, str],
) -> None:
    expected_values = {
        "ACTIONLINT_VERSION": versions["actionlint"],
        "GITLEAKS_VERSION": versions["gitleaks"],
        "GITLEAKS_ASSET": checksums["gitleaks_asset"],
        "GITLEAKS_SHA256": checksums["gitleaks_linux_x64"],
    }
    for key, expected in expected_values.items():
        _require_exact_occurrences(
            documents,
            key=key,
            expected=expected,
            label=key,
        )
    expected_asset = f"gitleaks_{versions['gitleaks']}_linux_x64.tar.gz"
    if checksums["gitleaks_asset"] != expected_asset:
        raise ValueError(
            "Gitleaks version, platform and asset name are incoherent"
        )


def _validate_mojo_contract(versions: dict[str, str]) -> None:
    pixi = (PROJECT_ROOT / "pixi.toml").read_text(encoding="utf-8")
    mojo_requirement = f'mojo = "=={versions["mojo"]}"'
    if mojo_requirement not in pixi:
        raise ValueError("Pixi Mojo requirement differs from governed version")
    lock = (PROJECT_ROOT / "pixi.lock").read_text(encoding="utf-8")
    locked_mojo = f"/mojo-{versions['mojo']}-release.conda"
    if locked_mojo not in lock:
        raise ValueError("Pixi lock differs from governed Mojo resolution")
    channel = f"https://conda.modular.com/{versions['mojo_channel']}"
    if channel not in pixi:
        raise ValueError("Pixi Mojo channel differs from governed channel")


def validate_tool_versions() -> dict[str, str]:
    """Validate all governed tool occurrences and locked Mojo identity."""
    document = json.loads(TOOL_VERSIONS_PATH.read_text(encoding="utf-8"))
    schema = json.loads(
        (PROJECT_ROOT / "quality" / "tool-versions.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.validate(document, schema)  # pyright: ignore[reportUnknownMemberType]
    versions = cast(
        "dict[str, str]",
        document["versions"],
    )
    checksums = cast("dict[str, str]", document["checksums"])
    documents = _workflow_documents()
    workflow_text = "\n".join(
        path.read_text(encoding="utf-8") for path in workflow_paths()
    )
    _validate_runners(documents, versions)
    _validate_setup_versions(documents, versions, workflow_text)
    _validate_gitleaks_contract(documents, versions, checksums)
    _validate_mojo_contract(versions)
    return versions


def git_commit() -> str:
    """Return the exact commit bound to a durable quality receipt."""
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git is required to bind quality receipts")
    completed = subprocess.run(
        [executable, "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _generated_at() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    instant = (
        datetime.fromtimestamp(int(epoch), tz=UTC)
        if epoch is not None
        else datetime.now(tz=UTC)
    )
    return instant.isoformat().replace("+00:00", "Z")


def write_quality_receipt(
    *,
    kind: str,
    observations: dict[str, float],
    output_path: Path,
    artifacts: Sequence[Path],
    command: Sequence[str],
) -> dict[str, Any]:
    """Write measured evidence bound to the commit and exact artifact bytes."""
    receipt: dict[str, Any] = {
        "schema_version": "1.0.0",
        "kind": kind,
        "evidence_state": "measured",
        "commit": git_commit(),
        "generated_at": _generated_at(),
        "command": list(command),
        "observations": observations,
        "artifacts": [
            {
                "path": artifact.as_posix(),
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "size_bytes": artifact.stat().st_size,
            }
            for artifact in artifacts
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    validate_quality_receipt(output_path, expected_kind=kind, enforce=True)
    return receipt


ALL_TESTS = validate_test_inventory()


def primary_lane_for_path(path: Path) -> str:
    """Resolve one manifest lane for a collected test path."""
    relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    matches = [name for name, paths in TEST_LANES.items() if relative in paths]
    if len(matches) != 1:
        raise ValueError(
            f"{relative} must have exactly one manifest lane; got {matches}"
        )
    return matches[0]


def pytest_collection_modifyitems(
    items: list[ItemLike],
) -> None:
    """Ensure each item has exactly one explicit or generated primary lane."""
    problems: list[str] = []
    for item in items:
        expected = primary_lane_for_path(Path(str(item.path)))
        existing = {
            marker.name
            for marker in item.iter_markers()
            if marker.name in PRIMARY_LANES
        }
        if not existing:
            item.add_marker(expected)
            existing = {expected}
        if len(existing) != 1:
            problems.append(
                f"{item.nodeid}: expected one primary lane, "
                f"found {sorted(existing)}"
            )
    if problems:
        raise ValueError(
            "primary lane marker validation failed:\n" + "\n".join(problems)
        )


def validate_collection() -> None:
    """Collect all tests with generated marker/manifest validation enabled."""
    run(
        build_pytest_command(
            ALL_TESTS,
            "--collect-only",
            "-p",
            "scripts.test_goblin",
        )
    )


def validate_quality_receipt(
    receipt_path: Path,
    *,
    expected_kind: str,
    enforce: bool,
) -> dict[str, Any]:
    """Validate a quality receipt and optionally require measured evidence."""
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    schema = json.loads(QUALITY_RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(  # pyright: ignore[reportUnknownMemberType]
        receipt, schema
    )
    if receipt["kind"] != expected_kind:
        raise ValueError(
            f"expected {expected_kind} receipt, got {receipt['kind']}"
        )
    if enforce and receipt["evidence_state"] != "measured":
        raise ValueError(
            f"{expected_kind} evidence remains contract_only; "
            "promotion enforcement requires a measured receipt"
        )
    return receipt


def enforce_optional_receipt(kind: str) -> None:
    """Enforce a supplied measured receipt without inventing an observation."""
    variable = f"TEST_GOBLIN_{kind.upper()}_RECEIPT"
    configured = os.environ.get(variable)
    if configured is None:
        return
    validate_quality_receipt(Path(configured), expected_kind=kind, enforce=True)


def contracts() -> None:
    """Validate cheap inventory and budget contracts without executing evidence."""
    validate_test_inventory()
    load_quality_budgets()
    validate_ci_contracts()
    validate_action_pins()
    validate_tool_versions()
    validate_collection()


def run(command: Sequence[str]) -> None:
    """Run a harness command from the project root and preserve its exit code."""
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def build_pytest_command(tests: Sequence[str], *extra: str) -> list[str]:
    """Build a pytest command using the active Python 3.14 environment."""
    return [
        sys.executable,
        "-m",
        "pytest",
        *tests,
        "-q",
        *extra,
    ]


def quick() -> None:
    """Run examples, properties, negative controls, and randomized ordering."""
    run(build_pytest_command(ALL_TESTS))


def lane(name: str) -> None:
    """Run one explicit test architecture lane."""
    extra: tuple[str, ...] = ()
    if os.environ.get("TEST_GOBLIN_COVERAGE") == "1":
        extra = (
            "--cov=global_medicines_atlas",
            "--cov=sources.nz.nzulm_fhir",
            "--cov-branch",
            "--cov-context=test",
            f"--cov-report=xml:coverage-{name}.xml",
            # A lane report is intentionally partial. The blocking repository
            # threshold is enforced once by the aggregate coverage profile.
            "--cov-fail-under=0",
        )
    run(build_pytest_command(TEST_LANES[name], *extra))


def coverage() -> None:
    """Run the governed suite with branch coverage and the blocking threshold."""
    budgets = load_quality_budgets()
    coverage_budget = cast("dict[str, object]", budgets["coverage"])
    line_percent = cast("dict[str, float]", coverage_budget["line_percent"])
    minimum = line_percent["minimum"]
    run(
        build_pytest_command(
            ALL_TESTS,
            "--cov=global_medicines_atlas",
            "--cov=sources.nz.nzulm_fhir",
            "--cov-branch",
            "--cov-report=term-missing",
            "--cov-report=xml",
            f"--cov-fail-under={minimum}",
        )
    )


def routine() -> None:
    """Run the consolidated formatter, linter, and fast routine type gate."""
    run(["uv", "run", "--group", "typing", "ruff", "format", "--check", "."])
    run(["uv", "run", "--group", "typing", "ruff", "check", "."])
    run(["uv", "run", "--group", "typing", "ty", "check"])
    run([sys.executable, "scripts/validate_context.py"])
    run([sys.executable, "scripts/validate_ecosystem.py"])
    run([sys.executable, "scripts/validate_javascript_style.py"])


def strict() -> None:
    """Run basedpyright strict mode as the formal final type gate."""
    run(["uv", "run", "--group", "typing", "basedpyright"])


def package() -> None:
    """Qualify clean wheel and source-distribution consumers."""

    run([sys.executable, "scripts/qualify_clean_consumer.py"])


def profile() -> None:
    """Exercise the canonical workload under Scalene and emit an HTML report."""
    command = [
        "uv",
        "run",
        "--group",
        "profiling",
        "scalene",
        "run",
        "--cpu-only",
        "--profile-all",
        "--outfile",
        "scalene-profile.json",
        "scripts/profile_smoke.py",
    ]
    started = time.perf_counter()
    run(command)
    elapsed_seconds = time.perf_counter() - started
    write_quality_receipt(
        kind="performance",
        observations={"elapsed_seconds": elapsed_seconds},
        output_path=PROJECT_ROOT
        / "build"
        / "quality-receipts"
        / "profile.json",
        artifacts=[PROJECT_ROOT / "scalene-profile.json"],
        command=command,
    )
    enforce_optional_receipt("performance")


def mutation() -> None:
    """Run mutmut where operating-system fork semantics are available."""
    if platform.system() == "Windows":
        raise SystemExit(
            "mutmut 3 requires fork support. Run the mutation profile in WSL "
            "or use the authoritative Linux CI lane."
        )
    for relative in (
        "scripts",
        "schemas",
        "contracts",
        "quality/qualifications",
    ):
        (PROJECT_ROOT / "mutants" / relative).mkdir(
            parents=True,
            exist_ok=True,
        )
    command = [sys.executable, "-m", "mutmut", "run"]
    run(command)
    export_command = [
        sys.executable,
        "-m",
        "mutmut",
        "export-cicd-stats",
    ]
    run(export_command)
    artifact = PROJECT_ROOT / "mutants" / "mutmut-cicd-stats.json"
    observations = load_mutmut_observations(artifact)
    results_command = [sys.executable, "-m", "mutmut", "results"]
    results = subprocess.run(
        results_command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if results.returncode:
        raise SystemExit(results.returncode)
    survivor_report = PROJECT_ROOT / "mutants" / "survivors.txt"
    survivor_report.write_text(results.stdout, encoding="utf-8")
    mutation_budget = cast(
        "dict[str, dict[str, dict[str, float]]]",
        load_quality_budgets(),
    )["mutation"]["score_percent"]["minimum"]
    observations["promotion_minimum_percent"] = mutation_budget
    observations["promotion_target_met"] = float(
        observations["score_percent"] >= mutation_budget
    )
    write_quality_receipt(
        kind="mutation",
        observations=observations,
        output_path=PROJECT_ROOT
        / "build"
        / "quality-receipts"
        / "mutation.json",
        artifacts=[artifact, survivor_report],
        command=command,
    )
    enforce_mutation_baseline(observations)
    enforce_optional_receipt("mutation")


def load_mutmut_observations(path: Path) -> dict[str, float]:
    """Load authoritative numeric counts exported by Mutmut itself."""
    if not path.is_file():
        raise ValueError("Mutmut did not emit authoritative CI/CD statistics")
    raw = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "killed",
        "survived",
        "total",
        "no_tests",
        "skipped",
        "suspicious",
        "timeout",
        "check_was_interrupted_by_user",
        "segfault",
    }
    if set(raw) != expected:
        raise ValueError(f"unexpected Mutmut statistics fields: {sorted(raw)}")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in raw.values()
    ):
        raise ValueError("Mutmut statistics must be non-negative integers")
    if raw["total"] <= 0:
        raise ValueError("Mutmut statistics contain no generated mutants")
    observations = {
        key: float(value) for key, value in cast("dict[str, int]", raw).items()
    }
    observations["untested"] = observations.pop("no_tests")
    denominator = observations["total"] - observations["skipped"]
    observations["score_percent"] = observations["killed"] / denominator * 100
    return observations


def enforce_mutation_baseline(observations: dict[str, float]) -> None:
    """Reject mutation regressions while preserving the independent target."""

    baseline = load_phase3_baselines(PHASE3_BASELINES_PATH).mutation
    killed = int(observations["killed"])
    survived = int(observations["survived"])
    current = MutationObservations(
        killed=killed,
        survived=survived,
        untested=int(observations.get("untested", 0)),
        skipped=int(observations.get("skipped", 0)),
        suspicious=int(observations.get("suspicious", 0)),
        timeout=int(observations.get("timeout", 0)),
        interrupted=int(observations.get("check_was_interrupted_by_user", 0)),
        segfault=int(observations.get("segfault", 0)),
        total=int(observations.get("total", killed + survived)),
        score_percent=observations["score_percent"],
    )
    if mutation_regressed(baseline, current):
        raise ValueError(
            "mutation survivor debt regressed from the immutable baseline"
        )


def gremlins() -> None:
    """Run fast pytest-native mutation testing on frontier data contracts."""
    run(
        build_pytest_command(
            (
                "tests/test_country_publication_gate.py",
                "tests/test_source_parity.py",
                "tests/test_source_health.py",
                "tests/test_us_drugsfda_adapter.py",
                "tests/test_us_acquisition.py",
                "tests/test_us_cms_partd_adapter.py",
                "tests/test_matching_pipeline.py",
                "tests/test_matching_evaluation.py",
                "tests/test_matching_normalization.py",
                "tests/test_matching_policy.py",
                "tests/test_matching_release.py",
                "tests/test_review_queue.py",
                "tests/test_product_contracts.py",
                "tests/test_query_service.py",
                "tests/test_product_api.py",
                "tests/test_product_cli.py",
                "tests/test_atlas_accessibility.py",
                "tests/test_atlas_e2e.py",
                "tests/test_product_security.py",
                "tests/test_product_performance.py",
                "tests/test_product_release.py",
            ),
            "--gremlins",
            "--gremlin-executor=subprocess",
        )
    )


def dependencies() -> None:
    """Test declared contracts against newest resolvable dependencies."""
    run([
        "uv",
        "run",
        "--group",
        "edge",
        "edgetest",
        "-c",
        "pyproject.toml",
        "--environment",
        "contracts",
    ])
    run([
        "uv",
        "run",
        "--group",
        "edge",
        "edgetest",
        "-c",
        "pyproject.toml",
        "--environment",
        "columnar",
    ])
    run([
        "uv",
        "run",
        "--group",
        "edge",
        "edgetest",
        "-c",
        "pyproject.toml",
        "--environment",
        "product",
    ])


def regeneration() -> None:
    """Verify deterministic qualification and release-evidence regeneration."""
    tests = (
        "tests/test_nz_asset_inventory.py",
        "tests/test_nz_consolidation.py",
        "tests/test_nz_fixture_indexes.py",
        "tests/test_nzmedicines_history_restoration.py",
        "tests/test_conductor_github_sync.py",
        "tests/test_temporal_snapshots.py",
        "tests/test_release_evidence.py",
        "tests/test_stable_v1_hosted_governance.py",
    )
    run(build_pytest_command(tests))
    run(build_pytest_command(tuple(reversed(tests))))
    run([sys.executable, "scripts/qualify_openapi_client.py"])
    run([sys.executable, "scripts/qualify_stable_v1_hosted_governance.py"])


def security() -> None:
    """Audit workflow and dependency supply-chain state and emit an SBOM."""
    (PROJECT_ROOT / "build").mkdir(exist_ok=True)
    run(["uv", "run", "--group", "security", "zizmor", "--pedantic", ".github"])
    run(["uv", "run", "--group", "security", "pip-audit"])
    run([
        "uv",
        "run",
        "--group",
        "security",
        "cyclonedx-py",
        "environment",
        "--output-file",
        "build/sbom.cdx.json",
    ])


def main() -> None:  # ruff: ignore[too-many-branches]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "profile",
        choices=(
            *TEST_LANES,
            *SPECIALIZED_TEST_PROFILES,
            "quick",
            "contracts",
            "coverage",
            "routine",
            "strict",
            "package",
            "mutation",
            "gremlins",
            "dependencies",
            "regeneration",
            "security",
            "profile",
            "full",
        ),
        default="quick",
        nargs="?",
    )
    selected_profile = parser.parse_args().profile
    if selected_profile in TEST_LANES:
        lane(selected_profile)
    elif selected_profile in SPECIALIZED_TEST_PROFILES:
        run(build_pytest_command(SPECIALIZED_TEST_PROFILES[selected_profile]))
    elif selected_profile == "contracts":
        contracts()
    elif selected_profile == "quick":
        quick()
    elif selected_profile == "coverage":
        coverage()
    elif selected_profile == "mutation":
        mutation()
    elif selected_profile == "gremlins":
        gremlins()
    elif selected_profile == "dependencies":
        dependencies()
    elif selected_profile == "regeneration":
        regeneration()
    elif selected_profile == "security":
        security()
    elif selected_profile == "routine":
        routine()
    elif selected_profile == "strict":
        strict()
    elif selected_profile == "package":
        package()
    elif selected_profile == "profile":
        profile()
    else:
        routine()
        strict()
        package()
        coverage()
        mutation()
        gremlins()
        regeneration()
        profile()
        security()


if __name__ == "__main__":
    main()
