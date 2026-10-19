from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

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
