"""Executable Test-Goblin harness for governed Python code."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import platform
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOVERNED_TESTS = (
    "tests/test_nzulm_fhir_adapter.py",
    "tests/test_nzulm_fhir_properties.py",
)


def run(command: Sequence[str]) -> None:
    """Run a harness command from the project root and preserve its exit code."""

    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def pytest_command(*extra: str) -> list[str]:
    """Build a pytest command using the active Python 3.14 environment."""

    return [
        sys.executable,
        "-m",
        "pytest",
        *GOVERNED_TESTS,
        "-q",
        *extra,
    ]


def quick() -> None:
    """Run examples, properties, negative controls, and randomized ordering."""

    run(pytest_command())


def coverage() -> None:
    """Run the governed suite with branch coverage and the blocking threshold."""

    run(
        pytest_command(
            "--cov=sources.nz.nzulm_fhir",
            "--cov-branch",
            "--cov-report=term-missing",
            "--cov-report=xml",
            "--cov-fail-under=91",
        )
    )


def mutation() -> None:
    """Run mutmut where operating-system fork semantics are available."""

    if platform.system() == "Windows":
        raise SystemExit(
            "mutmut 3 requires fork support. Run the mutation profile in WSL "
            "or use the authoritative Linux CI lane."
        )
    run([sys.executable, "-m", "mutmut", "run"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "profile",
        choices=("quick", "coverage", "mutation", "full"),
        default="quick",
        nargs="?",
    )
    profile = parser.parse_args().profile
    if profile == "quick":
        quick()
    elif profile == "coverage":
        coverage()
    elif profile == "mutation":
        mutation()
    else:
        coverage()
        mutation()


if __name__ == "__main__":
    main()
