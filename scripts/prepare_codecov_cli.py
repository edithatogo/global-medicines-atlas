"""Download, verify and install the pinned Codecov CLI wheel for CI uploads."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed CI tools and argv
import sys
import urllib.request
from pathlib import Path

# ruff: file-ignore[subprocess-without-shell-equals-true] - fixed arguments, no shell

CODECOV_CLI_VERSION = "11.3.1"
CODECOV_WHEEL_NAME = "codecov_cli-11.3.1-py3-none-any.whl"
CODECOV_WHEEL_URL = (
    "https://files.pythonhosted.org/packages/c1/6e/57c684d5f97f6b3d552b6c40b22743965eec109a00739fa075753accb6bd/"
    + CODECOV_WHEEL_NAME
)
CODECOV_WHEEL_SHA256 = (
    "69e2521a4904e15cc87e4bb71ad1ddcfa6a48f1340ec28a2419ed94c723c027d"
)
CODECOV_WHEEL_SIZE = 92_828
CODECOV_REPOSITORY = "https://github.com/codecov/codecov-cli"
MAX_WHEEL_BYTES = 1_000_000


def _tool_path(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"Required CI tool is unavailable: {name}")
    return path


def _write_pinned_wheel(wheel_path: Path) -> None:
    with urllib.request.urlopen(CODECOV_WHEEL_URL, timeout=30) as response:
        wheel = response.read(MAX_WHEEL_BYTES + 1)
    if len(wheel) != CODECOV_WHEEL_SIZE or len(wheel) > MAX_WHEEL_BYTES:
        raise ValueError("Codecov CLI wheel size differs from its pinned value")
    if hashlib.sha256(wheel).hexdigest() != CODECOV_WHEEL_SHA256:
        raise ValueError(
            "Codecov CLI wheel digest differs from its pinned value"
        )
    wheel_path.write_bytes(wheel)


def _verify_wheel(wheel_path: Path, verifier: str) -> None:
    subprocess.run(
        [
            verifier,
            "verify",
            "pypi",
            "--repository",
            CODECOV_REPOSITORY,
            str(wheel_path),
        ],
        check=True,
        timeout=60,
    )


def _install_wheel(wheel_path: Path, python_executable: Path, uv: str) -> None:
    subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(python_executable),
            "--no-deps",
            str(wheel_path),
        ],
        check=True,
        timeout=60,
    )


def prepare(
    wheel_directory: Path,
    *,
    python_executable: Path,
) -> Path:
    """Verify the exact PyPI publisher attestation before installing its wheel."""
    verifier = _tool_path("pypi-attestations")
    uv = _tool_path("uv")
    wheel_directory.mkdir(parents=True, exist_ok=True)
    wheel_path = wheel_directory / CODECOV_WHEEL_NAME

    try:
        _write_pinned_wheel(wheel_path)
        _verify_wheel(wheel_path, verifier)
        _install_wheel(wheel_path, python_executable, uv)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Codecov CLI verification or installation failed"
        ) from exc
    finally:
        wheel_path.unlink(missing_ok=True)

    return python_executable.parent / "codecovcli"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-directory", type=Path, required=True)
    args = parser.parse_args()
    executable = prepare(
        args.wheel_directory,
        python_executable=Path(sys.executable),
    )
    if not executable.is_file():
        raise RuntimeError("Verified Codecov CLI entry point was not installed")
    print(f"Verified Codecov CLI {CODECOV_CLI_VERSION} is ready for upload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
