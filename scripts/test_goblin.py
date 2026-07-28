"""Executable Test-Goblin harness for governed Python code."""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_LANES: dict[str, tuple[str, ...]] = {
    "unit": (
        "tests/test_country_adapter_registry.py",
        "tests/test_context_validation.py",
        "tests/test_ecosystem_reuse.py",
        "tests/test_settings.py",
        "tests/test_logging.py",
        "tests/test_source_catalog.py",
        "tests/test_source_receipts.py",
        "tests/test_temporal_coverage.py",
        "tests/test_terminology_resolver.py",
        "tests/test_temporal_evidence.py",
        "tests/test_release_evidence.py",
        "tests/test_release_cli.py",
        "tests/test_version.py",
    ),
    "integration": (
        "tests/test_nz_asset_inventory.py",
        "tests/test_nzulm_fhir_adapter.py",
        "tests/test_us_drugsfda_adapter.py",
        "tests/test_columnar.py",
        "tests/test_source_acquisition.py",
        "tests/test_temporal_snapshots.py",
    ),
    "e2e": ("tests/test_canonical_nz_adapter.py",),
    "smoke": ("tests/test_smoke.py",),
    "property": ("tests/test_nzulm_fhir_properties.py",),
    "edge": ("tests/test_edge_cases.py",),
}
ALL_TESTS = tuple(path for paths in TEST_LANES.values() for path in paths)


def run(command: Sequence[str]) -> None:
    """Run a harness command from the project root and preserve its exit code."""
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def pytest_command(tests: Sequence[str], *extra: str) -> list[str]:
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
    run(pytest_command(ALL_TESTS))


def lane(name: str) -> None:
    """Run one explicit test architecture lane."""
    run(pytest_command(TEST_LANES[name]))


def coverage() -> None:
    """Run the governed suite with branch coverage and the blocking threshold."""
    run(
        pytest_command(
            ALL_TESTS,
            "--cov=global_medicines_atlas",
            "--cov=sources.nz.nzulm_fhir",
            "--cov-branch",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "--cov-fail-under=91",
        )
    )


def routine() -> None:
    """Run the consolidated formatter, linter, and fast routine type gate."""
    run(["uv", "run", "--group", "typing", "ruff", "format", "--check", "."])
    run(["uv", "run", "--group", "typing", "ruff", "check", "."])
    run(["uv", "run", "--group", "typing", "ty", "check"])
    run([sys.executable, "scripts/validate_context.py"])
    run([sys.executable, "scripts/validate_ecosystem.py"])


def strict() -> None:
    """Run basedpyright strict mode as the formal final type gate."""
    run(["uv", "run", "--group", "typing", "basedpyright"])


def package() -> None:
    """Build wheel and source distribution with VCS-derived metadata."""

    run(["uv", "build", "--out-dir", "dist"])


def profile() -> None:
    """Exercise the canonical workload under Scalene and emit an HTML report."""
    run([
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
    ])


def mutation() -> None:
    """Run mutmut where operating-system fork semantics are available."""
    if platform.system() == "Windows":
        raise SystemExit(
            "mutmut 3 requires fork support. Run the mutation profile in WSL "
            "or use the authoritative Linux CI lane."
        )
    run([sys.executable, "-m", "mutmut", "run"])


def gremlins() -> None:
    """Run fast pytest-native mutation testing on frontier data contracts."""
    run(
        pytest_command(
            ("tests/test_columnar.py", "tests/test_settings.py"),
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


def regeneration() -> None:
    """Verify deterministic qualification and release-evidence regeneration."""
    tests = (
        "tests/test_temporal_snapshots.py",
        "tests/test_release_evidence.py",
    )
    run(pytest_command(tests))
    run(pytest_command(tuple(reversed(tests))))


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
            "quick",
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
