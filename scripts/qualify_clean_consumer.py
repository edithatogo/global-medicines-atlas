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
TOOL_VERSIONS = ROOT / "quality/tool-versions.json"
EXPECTED_ARTIFACTS = 2


def _expected_python_version() -> str:
    document = json.loads(TOOL_VERSIONS.read_text(encoding="utf-8"))
    version = document["versions"]["python"]
    if not isinstance(version, str) or not version:
        raise ValueError("the governed Python runtime is not recorded")
    return version


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
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        output = completed.stderr.strip() or completed.stdout.strip()
        diagnostic = output.splitlines()[-1] if output else "no output"
        raise RuntimeError(
            f"{command[0]} failed ({completed.returncode}): {diagnostic}"
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
import platform
from pathlib import Path
from typing import cast
from global_medicines_atlas import __version__
from global_medicines_atlas.api import create_app
from global_medicines_atlas.consumer_qualification import (
    assert_openapi_compatible, installed_package_identity,
)
from global_medicines_atlas.query_service import ReadOnlyQueryService
identity = installed_package_identity()
assert platform.python_version() == __PYTHON_VERSION__
app = create_app(cast(ReadOnlyQueryService, object()))
schema = app.openapi()
baseline = json.loads(Path(__BASELINE__).read_text(encoding='utf-8'))
assert_openapi_compatible(baseline, schema)
assert __version__ == identity.version
assert importlib.util.find_spec('jsonschema') is None
assert importlib.util.find_spec('lancedb') is None
print(json.dumps({'metadata': identity.__dict__, 'openapi_paths': len(schema['paths']), 'api': 'passed', 'core_fallback': 'passed'}, sort_keys=True))
"""
    return template.replace("__BASELINE__", repr(str(BASELINE))).replace(
        "__PYTHON_VERSION__", repr(_expected_python_version())
    )


def _v2_cli_probe(database: Path) -> str:
    """Exercise installed v2 CLI commands against a local synthetic fixture."""
    template = """
import json
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, __TESTS__)
from test_support.synthetic_query_database import create_synthetic_query_database
database = Path(__DATABASE__)
create_synthetic_query_database(database)
scripts = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
cli = scripts / ("global-medicines-atlas.exe" if os.name == "nt" else "global-medicines-atlas")
environment = {
    "GMA_CURSOR_SECRET": "consumer-probe-" + "synthetic-secret-long-enough",
    "PATH": os.environ.get("PATH", ""),
}
if os.name == "nt":
    environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
common = [
    "--database", str(database),
    "--valid-at", "2026-10-06T12:00:00+00:00",
    "--observed-at", "2026-10-06T12:00:00+00:00",
]
dimensions = (
    "service_benefit", "funding", "regulatory", "formulary", "terminology",
)
comparison = subprocess.run([
    str(cli), "v2-comparison", *common,
    "--concept-id", "rx:1",
    "--jurisdiction", "NZ", "--jurisdiction", "AU",
    *(argument for dimension in dimensions for argument in ("--dimension", dimension)),
], cwd=database.parent, check=False, capture_output=True, text=True, env=environment)
assert comparison.returncode == 0, comparison.stderr
payload = json.loads(comparison.stdout)
assert payload["metadata"]["api_version"] == "v2"
conclusions = payload["conclusions"]
assert len(conclusions) == len(dimensions) * 2
assert {item["dimension"] for item in conclusions} == set(dimensions)
assert any(
    item["jurisdiction"] == "NZ"
    and item["dimension"] == "regulatory"
    and item["state"] == "confirmed"
    for item in conclusions
)
assert any(
    item["jurisdiction"] == "AU"
    and item["dimension"] == "funding"
    and item["state"] == "not_covered"
    for item in conclusions
)
assert "validity" not in payload
evidence = subprocess.run([
    str(cli), "v2-evidence", *common,
    "--concept-id", "rx:1", "--jurisdiction", "NZ",
    "--dimension", "regulatory",
], cwd=database.parent, check=False, capture_output=True, text=True, env=environment)
assert evidence.returncode == 0, evidence.stderr
evidence_payload = json.loads(evidence.stdout)
assert evidence_payload["metadata"]["api_version"] == "v2"
assert evidence_payload["metadata"]["page"]["returned"] == 1
assert evidence_payload["evidence"][0]["dimension"] == "regulatory"
assert not comparison.stderr
assert not evidence.stderr
print(json.dumps({"v2_comparison": "passed", "v2_evidence": "passed"}, sort_keys=True))
"""
    return template.replace("__TESTS__", repr(str(ROOT / "tests"))).replace(
        "__DATABASE__", repr(str(database))
    )


def _research_export_probe(archive: Path) -> str:
    """Verify a pipeline-produced Platinum archive in an installed package."""
    template = """
import hashlib
import json
from pathlib import Path
from global_medicines_atlas.research_export_package import (
    verify_research_export_package,
)
archive_path = Path(__ARCHIVE__)
assert archive_path.is_file() and not archive_path.is_symlink()
with archive_path.open('rb') as archive_file:
    archive = archive_file.read(8 * 1024 * 1024 + 1)
assert len(archive) <= 8 * 1024 * 1024
verified = verify_research_export_package(archive)
rebuilt = verified.archive_bytes()
assert rebuilt == archive
print(json.dumps({
    'research_export': 'passed',
    'research_export_sha256': hashlib.sha256(rebuilt).hexdigest(),
    'research_export_bytes': len(rebuilt),
}, sort_keys=True))
"""
    return template.replace("__ARCHIVE__", repr(str(archive)))


def _atlas_probe() -> str:
    """Exercise Atlas templates and assets after installing federation extra."""
    return """
import asyncio
import json
import httpx
from typing import cast
from global_medicines_atlas.atlas import AtlasQueryService, create_atlas_app
atlas = create_atlas_app(cast(AtlasQueryService, object()))
async def request_atlas():
    transport = httpx.ASGITransport(app=atlas)
    async with httpx.AsyncClient(transport=transport, base_url='http://atlas') as client:
        return await client.get('/'), await client.get('/static/atlas.css')
page, stylesheet = asyncio.run(request_atlas())
assert page.status_code == 200
assert 'Global Medicines Atlas' in page.text
assert '/static/atlas.css' in page.text
assert stylesheet.status_code == 200
assert '--ink:' in stylesheet.text
print(json.dumps({'atlas_page': 'passed', 'atlas_static_asset': 'passed'}, sort_keys=True))
"""


def qualify(
    output: Path, *, research_export: Path | None = None
) -> dict[str, Any]:
    """Build, install, reinstall, probe, and write a platform receipt."""
    if research_export is not None:
        if research_export.is_symlink():
            raise ValueError("research export must be a bounded regular file")
        research_export = research_export.resolve(strict=True)
        if (
            not research_export.is_file()
            or research_export.stat().st_size > 8 * 1024 * 1024
        ):
            raise ValueError("research export must be a bounded regular file")
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
    python_version = _expected_python_version()
    for artifact in artifacts:
        with tempfile.TemporaryDirectory(prefix="gma-consumer-") as temporary:
            environment = Path(temporary) / "venv"
            _run(["uv", "venv", "--python", python_version, str(environment)])
            observed_python = _run(
                [
                    "python",
                    "-c",
                    "import platform; print(platform.python_version())",
                ],
                environment=environment,
            )
            if observed_python != python_version:
                raise RuntimeError(
                    f"consumer runtime requires Python {python_version}, "
                    f"got {observed_python}"
                )
            _run([
                "uv",
                "pip",
                "install",
                "--python",
                str(environment),
                str(artifact),
            ])
            core_probe = json.loads(
                _run(
                    ["python", "-c", _consumer_probe()], environment=environment
                )
            )
            _run(["global-medicines-atlas", "--help"], environment=environment)
            v2_cli_probe = json.loads(
                _run(
                    [
                        "python",
                        "-c",
                        _v2_cli_probe(
                            Path(temporary) / "synthetic-atlas.duckdb"
                        ),
                    ],
                    environment=environment,
                )
            )
            research_export_probe: dict[str, Any] = {}
            if research_export is not None:
                research_export_probe = json.loads(
                    _run(
                        [
                            "python",
                            "-c",
                            _research_export_probe(research_export),
                        ],
                        environment=environment,
                    )
                )
            _run([
                "uv",
                "pip",
                "install",
                "--python",
                str(environment),
                f"{artifact}[federation]",
            ])
            atlas_probe = json.loads(
                _run(["python", "-c", _atlas_probe()], environment=environment)
            )
            probe = {
                **core_probe,
                **atlas_probe,
                **research_export_probe,
            }
            _run([
                "uv",
                "pip",
                "install",
                "--python",
                str(environment),
                "--reinstall",
                f"{artifact}[federation]",
            ])
            _run(
                ["python", "-c", "import global_medicines_atlas"],
                environment=environment,
            )
            results.append({
                "artifact": artifact.name,
                "consumer_python": observed_python,
                "sha256": _sha256(artifact),
                "probe": {**probe, **v2_cli_probe},
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
    parser.add_argument(
        "--research-export",
        type=Path,
        help=(
            "verify this bounded Platinum export in each installed "
            "wheel and source-distribution environment"
        ),
    )
    args = parser.parse_args()
    print(
        json.dumps(
            qualify(args.output, research_export=args.research_export),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
