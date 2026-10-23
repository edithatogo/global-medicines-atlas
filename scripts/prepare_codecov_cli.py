"""Download and verify the pinned Codecov Linux CLI release binary."""

from __future__ import annotations

import argparse
import hashlib
import platform
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed argv
import urllib.request
from pathlib import Path

# ruff: file-ignore[subprocess-without-shell-equals-true] - fixed executable and argv

CODECOV_CLI_VERSION = "11.3.1"
CODECOV_ASSET_NAME = "codecovcli_linux"
CODECOV_ASSET_URL = (
    "https://github.com/codecov/codecov-cli/releases/download/v11.3.1/"
    + CODECOV_ASSET_NAME
)
CODECOV_ASSET_SHA256 = (
    "ca1d64196d2d34771084afe76ea657d581bf628e31d993ff8e52ea09cc88a56d"
)
CODECOV_ASSET_SIZE = 10_402_464


def prepare(binary_directory: Path) -> Path:
    """Verify and install the exact Linux x86-64 release asset locally."""
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        raise RuntimeError("Pinned Codecov CLI binary requires Linux x86-64")
    with urllib.request.urlopen(CODECOV_ASSET_URL, timeout=60) as response:
        binary = response.read(CODECOV_ASSET_SIZE + 1)
    if len(binary) != CODECOV_ASSET_SIZE:
        raise ValueError(
            "Codecov CLI release size differs from its pinned value"
        )
    if hashlib.sha256(binary).hexdigest() != CODECOV_ASSET_SHA256:
        raise ValueError(
            "Codecov CLI release digest differs from its pinned value"
        )

    binary_directory.mkdir(parents=True, exist_ok=True)
    executable = binary_directory / "codecovcli"
    executable.write_bytes(binary)
    executable.chmod(0o755)
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            check=True,
            capture_output=True,
            shell=False,
            text=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        executable.unlink(missing_ok=True)
        raise RuntimeError("Verified Codecov CLI could not be started") from exc
    if CODECOV_CLI_VERSION not in result.stdout + result.stderr:
        executable.unlink(missing_ok=True)
        raise RuntimeError("Verified Codecov CLI reports an unexpected version")
    return executable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary-directory", type=Path, required=True)
    args = parser.parse_args()
    executable = prepare(args.binary_directory)
    print(f"Verified Codecov CLI {CODECOV_CLI_VERSION} is ready for upload")
    print(executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
