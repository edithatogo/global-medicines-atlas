"""Browser E2E for Atlas as installed from built distributions."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import cast
from urllib.parse import urlencode

import httpx
import pytest
from playwright.sync_api import Page, Response, sync_playwright
from tests.test_mbs_gold_scalar_projection import (
    create_synthetic_trusted_scalar_resolver,
    synthetic_scalar_candidate_parquet,
)
from tests.test_support.synthetic_query_database import (
    create_synthetic_query_database,
)

ROOT = Path(__file__).resolve().parents[1]
SERVER_SOURCE = """
import asyncio
import json
import socket
import sys
from pathlib import Path
from typing import cast
import uvicorn
import global_medicines_atlas
from starlette.applications import Starlette
from starlette.routing import Mount
from global_medicines_atlas.atlas import AtlasQueryService, create_atlas_app
from global_medicines_atlas.atlas import V2AtlasQueryService
from global_medicines_atlas.api import create_app
from global_medicines_atlas.platinum_benefits import BenefitsService
from global_medicines_atlas.platinum_configuration import load_benefits_resolver
from global_medicines_atlas.platinum_v2_api import V2ComparisonService, create_v2_app

sys.path.insert(0, sys.argv[2])
from test_support.atlas_evidence_service import InstalledAtlasEvidenceService

service = InstalledAtlasEvidenceService()
metadata_root = Path(sys.argv[3]) if len(sys.argv) > 3 else None
benefits = None
api_v1_app = None
if metadata_root is not None:
    resolver = load_benefits_resolver(
        trust_file=metadata_root / "trust.json",
        metadata_root=metadata_root,
        schema_file=metadata_root / "schema.json",
    )
    benefits = BenefitsService(
        resolver, cursor_key=b"installed-scalar-fixture-cursor-key"
    )
    api_v1_app = create_app(object(), benefits=benefits)
atlas_app = Starlette(routes=[
    Mount(
        "/v2",
        app=create_atlas_app(
            cast(AtlasQueryService, service),
            v2_service=cast(V2AtlasQueryService, service),
        ),
    ),
    Mount(
        "/",
        app=create_atlas_app(
            cast(AtlasQueryService, service), federated_benefits=benefits
        ),
    ),
])
api_app = create_v2_app(cast(V2ComparisonService, service))

class InstalledArtifactApplication:
    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if path.startswith("/api/v2/"):
            target = api_app
        elif path.startswith("/api/v1/benefits/") and api_v1_app is not None:
            target = api_v1_app
        else:
            target = atlas_app
        await target(scope, receive, send)

app = InstalledArtifactApplication()
listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listener.bind(("127.0.0.1", 0))
listener.listen(128)
ready = Path(sys.argv[1])
ready.write_text(json.dumps({
    "url": f"http://127.0.0.1:{listener.getsockname()[1]}",
    "package_path": str(Path(global_medicines_atlas.__file__).resolve()),
}), encoding="utf-8")
server = uvicorn.Server(uvicorn.Config(
    app, lifespan="off", access_log=False, log_level="error",
))
asyncio.run(server.serve(sockets=[listener]))
"""


def _run(command: list[str]) -> None:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise RuntimeError(f"{command[0]} failed ({completed.returncode})")


def _python_in(environment: Path) -> Path:
    if sys.platform == "win32":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _cli_in(environment: Path) -> Path:
    if sys.platform == "win32":
        return environment / "Scripts" / "global-medicines-atlas.exe"
    return environment / "bin" / "global-medicines-atlas"


def _exercise_v2_cli(environment: Path, database: Path) -> None:
    """Exercise v2 query output from the installed wheel or source archive."""
    common = [
        "--database",
        str(database),
        "--valid-at",
        "2026-10-06T12:00:00+00:00",
        "--observed-at",
        "2026-10-06T12:00:00+00:00",
    ]
    dimensions = (
        "service_benefit",
        "funding",
        "regulatory",
        "formulary",
        "terminology",
    )
    cli_environment = {
        "GMA_CURSOR_SECRET": (
            "installed-cli-" + "synthetic-secret-long-enough"
        ),
        "PATH": os.environ.get("PATH", ""),
    }
    if sys.platform == "win32":
        cli_environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    comparison = subprocess.run(
        [
            str(_cli_in(environment)),
            "v2-comparison",
            *common,
            "--concept-id",
            "rx:1",
            "--jurisdiction",
            "NZ",
            "--jurisdiction",
            "AU",
            *(
                argument
                for dimension in dimensions
                for argument in ("--dimension", dimension)
            ),
        ],
        cwd=database.parent,
        check=False,
        capture_output=True,
        text=True,
        env=cli_environment,
    )
    assert comparison.returncode == 0, comparison.stderr
    payload = json.loads(comparison.stdout)
    assert payload["metadata"]["api_version"] == "v2"
    conclusions = payload["conclusions"]
    assert len(conclusions) == len(dimensions) * 2
    assert {item["dimension"] for item in conclusions} == set(dimensions)
    assert all(
        item["state"]
        in {
            "unknown",
            "confirmed",
            "inferred",
            "not_covered",
            "conflicting",
            "not_applicable",
        }
        for item in conclusions
    )
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

    evidence = subprocess.run(
        [
            str(_cli_in(environment)),
            "v2-evidence",
            *common,
            "--concept-id",
            "rx:1",
            "--jurisdiction",
            "NZ",
            "--dimension",
            "regulatory",
        ],
        cwd=database.parent,
        check=False,
        capture_output=True,
        text=True,
        env=cli_environment,
    )
    assert evidence.returncode == 0, evidence.stderr
    evidence_payload = json.loads(evidence.stdout)
    assert evidence_payload["metadata"]["api_version"] == "v2"
    assert evidence_payload["metadata"]["page"]["returned"] == 1
    assert evidence_payload["evidence"][0]["dimension"] == "regulatory"
    assert not comparison.stderr
    assert not evidence.stderr


def _scalar_fixture(
    metadata_root: Path,
    *,
    field_name: str,
    values: list[str],
    operator: str,
    filter_value: object,
    expected: str,
) -> tuple[Path, str, str, str, str, str]:
    """Create exact synthetic scalar trust metadata for installed consumers."""
    payload, value_column = synthetic_scalar_candidate_parquet(
        field_name, values
    )
    resolver, resource_id, path = create_synthetic_trusted_scalar_resolver(
        payload, metadata_root=metadata_root
    )
    resolver.close()
    payload_path = metadata_root / "fixture.parquet"
    payload_path.write_bytes(payload)
    (metadata_root / "sitecustomize.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "import httpx\n"
        "from global_medicines_atlas import federation_reader\n"
        "payload = Path(os.environ['GMA_INSTALLED_SCALAR_FIXTURE']).read_bytes()\n"
        "revision = 'a' * 40\n"
        f"object_path = {path!r}\n"
        "def handle(request):\n"
        "    assert request.url.host == 'huggingface.co'\n"
        "    if '/api/datasets/' in request.url.path:\n"
        "        return httpx.Response(200, json={'sha': revision, 'private': False, 'gated': False})\n"
        "    if request.url.path.endswith('/' + object_path):\n"
        "        return httpx.Response(200, content=payload)\n"
        "    return httpx.Response(404)\n"
        "def transport(*, policy):\n"
        "    assert 'huggingface.co' in policy.allowed_hosts\n"
        "    return httpx.MockTransport(handle)\n"
        "federation_reader.BoundIPAddressTransport = transport\n",
        encoding="utf-8",
    )
    filters = json.dumps(
        [{"column": value_column, "operator": operator, "value": filter_value}],
        separators=(",", ":"),
    )
    return payload_path, value_column, resource_id, path, filters, expected


def _exercise_scalar_cli(
    environment: Path,
    metadata_root: Path,
    value_column: str,
    resource_id: str,
    path: str,
    filters: str,
    expected: str,
    cli_environment: dict[str, str],
) -> dict[str, object]:
    cli_environment["PATH"] = os.environ.get("PATH", "")
    result = subprocess.run(
        [
            str(_cli_in(environment)),
            "benefits",
            resource_id,
            "--trust-file",
            str(metadata_root / "trust.json"),
            "--metadata-root",
            str(metadata_root),
            "--schema-file",
            str(metadata_root / "schema.json"),
            "--column",
            "source_record_id",
            "--column",
            value_column,
            "--limit",
            "2",
            "--filters-json",
            filters,
        ],
        cwd=metadata_root,
        check=False,
        capture_output=True,
        text=True,
        env=cli_environment,
    )
    assert result.returncode == 0, result.stderr
    page = json.loads(result.stdout)
    assert page["status"] == "available"
    assert page["identity"]["path"] == path
    assert page["identity"]["comparison_cohort"] == "synthetic"
    assert page["coverage_state"] == "not_declared"
    assert page["review_state"] == "not_declared"
    assert page["rows"] == [
        {
            "source_record_id": "au-mbs:3::2025-07-0",
            value_column: expected,
        }
    ]

    jsonl_result = subprocess.run(
        [
            str(_cli_in(environment)),
            "benefits",
            resource_id,
            "--trust-file",
            str(metadata_root / "trust.json"),
            "--metadata-root",
            str(metadata_root),
            "--schema-file",
            str(metadata_root / "schema.json"),
            "--column",
            "source_record_id",
            "--column",
            value_column,
            "--limit",
            "1",
            "--format",
            "jsonl",
            "--max-rows",
            "2",
        ],
        cwd=metadata_root,
        check=False,
        capture_output=True,
        text=True,
        env=cli_environment,
    )
    assert jsonl_result.returncode == 0, jsonl_result.stderr
    jsonl_lines = [
        json.loads(line) for line in jsonl_result.stdout.splitlines()
    ]
    assert len(jsonl_lines) == 3
    assert [
        line["record"]["source_record_id"] for line in jsonl_lines[:-1]
    ] == [
        "au-mbs:3::2025-07-0",
        "au-mbs:3::2025-07-1",
    ]
    assert jsonl_lines[0]["record"][value_column] == expected
    assert all(line["type"] == "record" for line in jsonl_lines[:-1])
    assert all(line["identity"]["path"] == path for line in jsonl_lines[:-1])
    assert all(len(line["receipt_sha256"]) == 64 for line in jsonl_lines[:-1])
    assert jsonl_lines[-1]["type"] == "summary"
    assert jsonl_lines[-1]["row_count"] == 2
    assert jsonl_lines[-1]["page_count"] == 2
    assert jsonl_lines[-1]["source_completeness"] == "not_established"
    return page


def _exercise_scalar_api_and_browser(
    server_url: str,
    value_column: str,
    resource_id: str,
    path: str,
    payload_sha256: str,
    filters: str,
    expected: str,
) -> None:
    response = httpx.get(
        f"{server_url}/api/v1/benefits/{resource_id}",
        params=[
            ("columns", "source_record_id"),
            ("columns", value_column),
            ("limit", "2"),
            ("filters", filters),
        ],
        timeout=5,
    )
    assert response.status_code == 200, response.text
    api_page = response.json()
    assert api_page["status"] == "available"
    assert api_page["identity"]["path"] == path
    assert api_page["identity"]["object_sha256"] == payload_sha256
    assert api_page["identity"]["comparison_cohort"] == "synthetic"
    assert api_page["rows"] == [
        {
            "source_record_id": "au-mbs:3::2025-07-0",
            value_column: expected,
        }
    ]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            query = urlencode({
                "resource_id": resource_id,
                "columns": f"source_record_id,{value_column}",
                "limit": 2,
                "filters": filters,
            })
            browser_response = page.goto(
                f"{server_url}/federated/benefits?{query}",
                wait_until="networkidle",
            )
            assert browser_response is not None
            assert browser_response.status == 200
            assert page.get_by_role(
                "heading", name="Exact evidence identity"
            ).is_visible()
            assert page.get_by_text(path, exact=True).is_visible()
            assert page.get_by_text(payload_sha256, exact=True).is_visible()
            rows = page.get_by_role(
                "region", name="Federated evidence rows"
            ).locator("tbody tr")
            assert rows.count() == 1
            row = rows.first.inner_text()
            assert "au-mbs:3::2025-07-0" in row
            assert expected in row
            text = page.locator("main").inner_text()
            assert "Comparison cohort" in text
            assert "synthetic" in text
            assert "Coverage is not declared here" in text
            assert "Review state" in text
            assert "not declared" in text
        finally:
            browser.close()
    assert api_page["rows"][0][value_column] == expected


def _wait_for_server(
    process: subprocess.Popen[bytes], ready: Path
) -> dict[str, str]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("installed Atlas server exited before readiness")
        if ready.exists():
            server = json.loads(ready.read_text(encoding="utf-8"))
            try:
                response = httpx.get(server["url"], timeout=1)
                if response.status_code == 200:
                    return server
            except httpx.HTTPError:
                pass
        time.sleep(0.05)
    raise RuntimeError("installed Atlas server did not become ready")


def _exercise_browser(server_url: str) -> None:
    requested: list[str] = []
    responses: dict[str, list[int]] = {}

    def record_response(response: Response) -> None:
        url = response.url.split("?", maxsplit=1)[0]
        responses.setdefault(url, []).append(response.status)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.on("request", lambda request: requested.append(request.url))
        page.on("response", record_response)
        try:
            search_query = urlencode({
                "concept_search": "example",
                "jurisdiction": "NZ",
                "valid_at": "2026-10-06T12:00:00+00:00",
                "observed_at": "2026-10-06T12:00:00+00:00",
            })
            response = page.goto(
                f"{server_url}/?{search_query}", wait_until="networkidle"
            )
            assert response is not None
            assert response.status == 200
            assert page.get_by_role(
                "heading", name="Medicine search results"
            ).is_visible()
            candidate = page.locator(".search-results a")
            assert candidate.count() == 1
            assert "rx:fixture" in candidate.inner_text()
            candidate.click()
            assert page.get_by_role(
                "heading", name="Comparison results for Example medicine"
            ).is_visible()
            card = page.locator("article[data-state='unknown']")
            assert card.count() == 1
            card_text = card.inner_text().casefold()
            assert "not evidence of a negative" in card_text
            assert "no source assertion" in card_text
            assert not any(
                negative in card_text
                for negative in ("not covered", "not approved", "not funded")
            )
            card.get_by_text("Review source evidence").click()
            assert card.get_by_role(
                "link", name="Synthetic public evidence"
            ).is_visible()
            coverage = page.locator("table tbody tr")
            assert coverage.count() == 1
            assert "Status: Unknown" in coverage.inner_text()
            assert "denominator unknown" in coverage.inner_text()
            assert "%" not in coverage.inner_text()
            assert 200 in responses[f"{server_url}/static/atlas.css"]
            assert (
                200 in responses[f"{server_url}/static/atlas-autocomplete.js"]
            )
            assert all(url.startswith(server_url) for url in requested)
            _exercise_v2_browser(page, server_url, requested)
        finally:
            browser.close()


def _exercise_v2_browser(
    page: Page, server_url: str, requested: list[str]
) -> None:
    v2_query = urlencode({
        "concept_id": "rx:fixture",
        "jurisdiction": "AU",
        "valid_at": "2026-10-06T12:00:00+00:00",
        "observed_at": "2026-10-06T12:00:00+00:00",
    })
    response = page.goto(
        f"{server_url}/v2/?{v2_query}", wait_until="networkidle"
    )
    assert response is not None
    assert response.status == 200
    assert page.get_by_role(
        "heading", name="Comparison results for Example medicine"
    ).is_visible()
    cards = page.locator("article[data-state='unknown']")
    assert cards.count() == 5
    for dimension in (
        "service_benefit",
        "funding",
        "regulatory",
        "formulary",
        "terminology",
    ):
        card = page.locator("article").filter(
            has=page.get_by_role("heading", name=f"AU — {dimension}")
        )
        assert card.count() == 1
        assert "No source assertion" in card.inner_text()
        assert "not evidence of a negative" in card.inner_text()
        assert not any(
            negative in card.inner_text().casefold()
            for negative in ("not covered", "not approved", "not funded")
        )
    assert page.get_by_text("fixture-v2").count() == 5
    assert not page.locator("table tbody tr").count()
    assert all(url.startswith(server_url) for url in requested)
    _exercise_v2_api(server_url)


def _exercise_v2_api(server_url: str) -> None:
    dimensions = (
        "service_benefit",
        "funding",
        "regulatory",
        "formulary",
        "terminology",
    )
    response = httpx.get(
        f"{server_url}/api/v2/comparisons",
        params=[
            ("concept_id", "rx:fixture"),
            ("jurisdictions", "AU"),
            *(("dimensions", dimension) for dimension in dimensions),
            ("valid_at", "2026-10-06T12:00:00+00:00"),
            ("observed_at", "2026-10-06T12:00:00+00:00"),
        ],
        headers={"accept": "application/json"},
        timeout=5,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["api_version"] == "v2"
    conclusions = payload["conclusions"]
    assert len(conclusions) == len(dimensions)
    assert {item["dimension"] for item in conclusions} == set(dimensions)
    for item in conclusions:
        assert item["state"] == "unknown"
        assert item["status_code"] is None
        assert "No source assertion" in item["terminology"]["native_label"]
        assert item["uncertainty"]["level"] == "unknown"
    evidence_response = httpx.get(
        f"{server_url}/api/v2/evidence",
        params={
            "concept_id": "rx:fixture",
            "jurisdiction": "AU",
            "dimension": "service_benefit",
            "valid_at": "2026-10-06T12:00:00+00:00",
            "observed_at": "2026-10-06T12:00:00+00:00",
        },
        headers={"accept": "application/json"},
        timeout=5,
    )
    assert evidence_response.status_code == 200
    evidence_payload = evidence_response.json()
    assert evidence_payload["metadata"]["api_version"] == "v2"
    assert evidence_payload["metadata"]["page"]["returned"] == 0
    assert evidence_payload["evidence"] == []


def _exercise_artifact(  # ruff: ignore[too-many-locals] -- keep the installed wheel/sdist lifecycle and exact fixture boundary together
    artifact: Path,
    root: Path,
    uv: str,
    database: Path,
    scalar_fixtures: tuple[tuple[Path, str, str, str, str, str], ...],
) -> None:
    environment = root / f"venv-{artifact.suffix.lstrip('.')}"
    _run([uv, "venv", "--python", str(sys.executable), str(environment)])
    _run([
        uv,
        "pip",
        "install",
        "--python",
        str(_python_in(environment)),
        f"{artifact}[federation]",
        "uvicorn>=0.54,<0.55",
    ])
    _exercise_v2_cli(environment, database)
    runner = root / f"{artifact.name}.server.py"
    runner.write_text(SERVER_SOURCE, encoding="utf-8")
    for index, fixture in enumerate(scalar_fixtures):
        payload_path, value_column, resource_id, path, filters, expected = (
            fixture
        )
        metadata_root = payload_path.parent
        cli_environment = {
            "GMA_CURSOR_SECRET": "installed-cli-synthetic-cursor-key-32",
            "GMA_INSTALLED_SCALAR_FIXTURE": str(payload_path),
            "PYTHONPATH": str(metadata_root),
        }
        if sys.platform == "win32":
            cli_environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        cli_page = _exercise_scalar_cli(
            environment,
            metadata_root,
            value_column,
            resource_id,
            path,
            filters,
            expected,
            cli_environment,
        )
        ready = root / f"{artifact.name}-{index}.ready.json"
        server_environment = os.environ.copy()
        server_environment.update(cli_environment)
        process = subprocess.Popen(
            [
                str(_python_in(environment)),
                str(runner),
                str(ready),
                str(ROOT / "tests"),
                str(metadata_root),
            ],
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=server_environment,
        )
        try:
            server = _wait_for_server(process, ready)
            package_path = Path(server["package_path"])
            assert package_path.is_relative_to(environment.resolve())
            if index == 0:
                _exercise_browser(server["url"])
            _exercise_scalar_api_and_browser(
                server["url"],
                value_column,
                resource_id,
                path,
                hashlib.sha256(payload_path.read_bytes()).hexdigest(),
                filters,
                expected,
            )
            identity = cast("dict[str, object]", cli_page["identity"])
            assert identity["path"] == path
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.mark.e2e
@pytest.mark.timeout(300)
def test_installed_atlas_wheel_and_sdist_render_in_loopback_chromium(
    tmp_path: Path,
) -> None:
    """Both installed artifacts render synthetic Atlas evidence in Chromium."""
    uv = shutil.which("uv")
    assert uv is not None
    distribution_dir = tmp_path / "dist"
    _run([uv, "build", "--out-dir", str(distribution_dir)])
    artifacts = sorted((
        *distribution_dir.glob("*.whl"),
        *distribution_dir.glob("*.tar.gz"),
    ))
    assert len(artifacts) == 2
    database = create_synthetic_query_database(
        tmp_path / "synthetic-atlas.duckdb"
    )
    scalar_fixtures = (
        _scalar_fixture(
            tmp_path / "scalar-decimal",
            field_name="Benefit100",
            values=["10.25", "2.75"],
            operator=">=",
            filter_value=10.00,
            expected="10.250000000",
        ),
        _scalar_fixture(
            tmp_path / "scalar-date",
            field_name="BenefitStartDate",
            values=["2025-07-01", "2025-08-01"],
            operator="=",
            filter_value={"type": "date", "value": "2025-07-01"},
            expected="2025-07-01",
        ),
    )
    for artifact in artifacts:
        try:
            _exercise_artifact(
                artifact, tmp_path, uv, database, scalar_fixtures
            )
        except Exception as error:
            raise AssertionError(
                f"installed browser journey failed for {artifact.name}"
            ) from error
