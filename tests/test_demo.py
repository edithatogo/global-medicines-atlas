from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from global_medicines_atlas import cli, demo
from global_medicines_atlas.cli import app as cli_app
from global_medicines_atlas.demo import (
    DEMO_DATA_MODE,
    DEMO_NOTICE,
    create_demo_app,
    create_demo_database,
)


def test_demo_exercises_landing_api_and_atlas(tmp_path: Path) -> None:
    database = create_demo_database(tmp_path / "demo.duckdb")
    client = TestClient(create_demo_app(database))

    landing = client.get("/")
    assert landing.status_code == 200
    assert DEMO_NOTICE in landing.text
    assert landing.headers["x-gma-data-mode"] == DEMO_DATA_MODE
    assert client.get("/api/v1/docs").status_code == 200

    api = client.get(
        "/api/v1/comparisons",
        params=[
            ("concept_id", "rx:demo-medicine"),
            ("jurisdictions", "NZ"),
            ("jurisdictions", "AU"),
            ("valid_at", "2026-07-29T00:00:00Z"),
            ("observed_at", "2026-07-29T00:00:00Z"),
        ],
    )
    assert api.status_code == 200, api.text
    assert api.headers["x-gma-data-mode"] == DEMO_DATA_MODE
    assert {item["jurisdiction"] for item in api.json()["conclusions"]} == {
        "NZ",
        "AU",
    }

    atlas = client.get(
        "/atlas/",
        params=[
            ("concept_id", "rx:demo-medicine"),
            ("jurisdiction", "NZ"),
            ("jurisdiction", "AU"),
            ("valid_at", "2026-07-29T00:00:00Z"),
            ("observed_at", "2026-07-29T00:00:00Z"),
        ],
    )
    assert atlas.status_code == 200
    assert atlas.headers["x-gma-data-mode"] == DEMO_DATA_MODE
    assert DEMO_NOTICE in atlas.text
    assert "rx:demo-medicine" in atlas.text


def test_demo_database_refuses_to_overwrite(tmp_path: Path) -> None:
    database = create_demo_database(tmp_path / "demo.duckdb")
    original = database.read_bytes()

    with pytest.raises(FileExistsError):
        create_demo_database(database)

    assert database.read_bytes() == original


def test_demo_command_binds_only_to_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, str, int]] = []

    def fake_run(
        application: object, *, host: str, port: int, log_level: str
    ) -> None:
        assert log_level == "warning"
        calls.append((application, host, port))

    monkeypatch.setattr("uvicorn.run", fake_run)
    result = CliRunner().invoke(cli_app, ["demo", "--port", "9876"])

    assert result.exit_code == 0, result.output
    assert "Synthetic fixture data only" in result.output
    assert len(calls) == 1
    assert calls[0][1:] == ("127.0.0.1", 9876)


def test_demo_command_reports_missing_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = cli.importlib.import_module

    def missing(name: str, package: str | None = None):
        if name == "uvicorn":
            raise ImportError("not installed")
        return original(name, package)

    monkeypatch.setattr(cli.importlib, "import_module", missing)
    result = CliRunner().invoke(cli_app, ["demo"])
    assert result.exit_code != 0
    assert "Install the demo extra" in result.output


def test_demo_command_reports_database_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_path: Path) -> Path:
        raise OSError("fixture unavailable")

    monkeypatch.setattr(demo, "create_demo_database", fail)
    result = CliRunner().invoke(cli_app, ["demo"])
    assert result.exit_code != 0
    assert "fixture unavailable" in result.output


def test_demo_database_removes_partial_file_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "demo.duckdb"

    def fail(path: str):
        Path(path).write_bytes(b"partial")
        raise RuntimeError("database creation failed")

    monkeypatch.setattr(demo.duckdb, "connect", fail)
    with pytest.raises(RuntimeError, match="database creation failed"):
        create_demo_database(target)
    assert not target.exists()
    assert not (tmp_path / ".demo.duckdb.gma-demo-lock").exists()


def test_demo_database_rechecks_target_after_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "demo.duckdb"
    original_exists = Path.exists
    checks = 0

    def exists(path: Path) -> bool:
        nonlocal checks
        if path == target:
            checks += 1
            return checks > 1
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", exists)
    with pytest.raises(FileExistsError):
        create_demo_database(target)
    assert not (tmp_path / ".demo.duckdb.gma-demo-lock").exists()


def test_demo_database_closes_connection_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenConnection:
        closed = False

        def execute(self, _sql: str) -> None:
            raise RuntimeError("fixture schema failed")

        def close(self) -> None:
            self.closed = True

    connection = BrokenConnection()
    monkeypatch.setattr(demo.duckdb, "connect", lambda _path: connection)
    with pytest.raises(RuntimeError, match="fixture schema failed"):
        create_demo_database(tmp_path / "demo.duckdb")
    assert connection.closed
