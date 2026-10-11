"""Browser E2E for Atlas as installed from built distributions."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import sync_playwright

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
from global_medicines_atlas.atlas import AtlasQueryService, create_atlas_app

app = create_atlas_app(cast(AtlasQueryService, object()))
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
        [str(_python_in(environment)), str(runner), str(ready)],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        server = _wait_for_server(process, ready)
        package_path = Path(server["package_path"])
        assert package_path.is_relative_to(environment.resolve())

        requested: list[str] = []
        responses: dict[str, int] = {}
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.on("request", lambda request: requested.append(request.url))
            page.on(
                "response",
                lambda response: responses.update({
                    response.url.split("?", maxsplit=1)[0]: response.status
                }),
            )
            try:
                response = page.goto(server["url"], wait_until="networkidle")
                assert response is not None
                assert response.status == 200
                assert page.get_by_role(
                    "heading", name="Global Medicines Atlas"
                ).is_visible()
                assert any(
                    url.endswith("/static/atlas.css") for url in responses
                )
                assert any(
                    url.endswith("/static/atlas-autocomplete.js")
                    for url in responses
                )
                assert all(url.startswith(server["url"]) for url in requested)
            finally:
                browser.close()
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
    """Both installed artifacts serve packaged Atlas pages and assets."""
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
