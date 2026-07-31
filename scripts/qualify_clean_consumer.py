"""Qualify built distributions from clean consumer environments."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "contracts/openapi-v1.json"
EXPECTED_ARTIFACTS = 2


def _run(command: list[str], *, environment: Path | None = None) -> str:
    executable = command[0]
    if environment is not None:
        scripts = environment / (
            "Scripts" if sys.platform == "win32" else "bin"
        )
        executable = str(
            scripts
            / (
                "python.exe"
                if command[0] == "python" and sys.platform == "win32"
                else command[0]
            )
        )
    completed = subprocess.run(
        [executable, *command[1:]],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _consumer_probe() -> str:
    template = """
import json
import importlib.util
from pathlib import Path
from typing import cast
from global_medicines_atlas import __version__
from global_medicines_atlas.api import create_app
from global_medicines_atlas.consumer_qualification import (
    assert_openapi_compatible, installed_package_identity,
)
from global_medicines_atlas.query_service import ReadOnlyQueryService
identity = installed_package_identity()
app = create_app(cast(ReadOnlyQueryService, object()))
schema = app.openapi()
baseline = json.loads(Path(__BASELINE__).read_text(encoding='utf-8'))
assert_openapi_compatible(baseline, schema)
assert __version__ == identity.version
assert importlib.util.find_spec('lancedb') is None
print(json.dumps({'metadata': identity.__dict__, 'openapi_paths': len(schema['paths']), 'api': 'passed', 'core_fallback': 'passed'}, sort_keys=True))
"""
    return template.replace("__BASELINE__", repr(str(BASELINE)))


def qualify(output: Path) -> dict[str, Any]:
    """Build, install, reinstall, probe, and write a platform receipt."""
    dist = ROOT / "build/consumer-dist"
    if dist.exists():
        shutil.rmtree(dist)
    _run(["uv", "build", "--out-dir", str(dist)])
    artifacts = sorted((*dist.glob("*.whl"), *dist.glob("*.tar.gz")))
    if len(artifacts) != EXPECTED_ARTIFACTS:
        raise RuntimeError(
            "exactly one wheel and one source archive are required"
        )
    results: list[dict[str, Any]] = []
    for artifact in artifacts:
        with tempfile.TemporaryDirectory(prefix="gma-consumer-") as temporary:
            environment = Path(temporary) / "venv"
            _run(["uv", "venv", "--python", "3.14", str(environment)])
            _run([
                "uv",
                "pip",
                "install",
                "--python",
                str(environment),
                str(artifact),
            ])
            probe = json.loads(
                _run(
                    ["python", "-c", _consumer_probe()], environment=environment
                )
            )
            _run(["global-medicines-atlas", "--help"], environment=environment)
            _run([
                "uv",
                "pip",
                "install",
                "--python",
                str(environment),
                "--reinstall",
                str(artifact),
            ])
            _run(
                ["python", "-c", "import global_medicines_atlas"],
                environment=environment,
            )
            results.append({
                "artifact": artifact.name,
                "sha256": _sha256(artifact),
                "probe": probe,
                "cli": "passed",
                "reinstall": "passed",
            })
    receipt = {
        "schema_version": 1,
        "platform": platform.system().lower(),
        "machine": platform.machine().lower(),
        "python": platform.python_version(),
        "artifacts": results,
        "state": "passed",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/quality-receipts/consumer.json"),
    )
    args = parser.parse_args()
    print(json.dumps(qualify(args.output), sort_keys=True))


if __name__ == "__main__":
    main()
