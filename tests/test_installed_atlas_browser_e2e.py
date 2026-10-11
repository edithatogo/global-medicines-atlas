"""Browser E2E for Atlas as installed from built distributions."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest
from playwright.sync_api import Page, Response, sync_playwright

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
from global_medicines_atlas.platinum_v2_api import V2ComparisonService, create_v2_app

sys.path.insert(0, sys.argv[2])
from test_support.atlas_evidence_service import InstalledAtlasEvidenceService

service = InstalledAtlasEvidenceService()
atlas_app = Starlette(routes=[
    Mount(
        "/v2",
        app=create_atlas_app(
            cast(AtlasQueryService, service),
            v2_service=cast(V2AtlasQueryService, service),
        ),
    ),
    Mount("/", app=create_atlas_app(cast(AtlasQueryService, service))),
])
api_app = create_v2_app(cast(V2ComparisonService, service))

class InstalledArtifactApplication:
    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        target = api_app if path.startswith("/api/v2/") else atlas_app
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


def _exercise_artifact(artifact: Path, root: Path, uv: str) -> None:
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
    ready = root / f"{artifact.name}.ready.json"
    runner = root / f"{artifact.name}.server.py"
    runner.write_text(SERVER_SOURCE, encoding="utf-8")
    process = subprocess.Popen(
        [
            str(_python_in(environment)),
            str(runner),
            str(ready),
            str(ROOT / "tests"),
        ],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        server = _wait_for_server(process, ready)
        package_path = Path(server["package_path"])
        assert package_path.is_relative_to(environment.resolve())
        _exercise_browser(server["url"])
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
    for artifact in artifacts:
        try:
            _exercise_artifact(artifact, tmp_path, uv)
        except Exception as error:
            raise AssertionError(
                f"installed browser journey failed for {artifact.name}"
            ) from error
