"""Scriptable CLI exposure for deterministic concept discovery."""

# ruff: file-ignore[import-private-name]

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.test_concept_query_service import _catalog_database
from typer.testing import CliRunner

from global_medicines_atlas import cli
from global_medicines_atlas.cli import app
from global_medicines_atlas.query_service import QueryServiceError

runner = CliRunner()
ENV = {"GMA_CURSOR_SECRET": "concept-cli-secret-long-enough"}


@pytest.fixture
def database(tmp_path: Path) -> Path:
    return _catalog_database(tmp_path / "catalog.duckdb")


def _invoke(database: Path, *arguments: str):
    return runner.invoke(
        app,
        [*arguments, "--database", str(database)],
        env=ENV,
    )


def test_concept_search_supports_bounded_json_and_jsonl(
    database: Path,
) -> None:
    result = _invoke(
        database,
        "concept",
        "search",
        "paracetamol",
        "--limit",
        "1",
        "--max-rows",
        "2",
        "--format",
        "jsonl",
    )

    assert result.exit_code == 0, result.stderr
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert [item["record"]["concept_id"] for item in records] == [
        "gma:para",
        "gma:combo",
    ]
    assert all(
        item["record"]["explanation"]["establishes_equivalence"] is False
        for item in records
    )


def test_concept_show_and_catalogue_lists_are_scriptable(
    database: Path,
) -> None:
    detail = _invoke(database, "concept", "show", "gma:aspirin")
    jurisdictions = _invoke(database, "jurisdiction", "list")
    sources = _invoke(
        database,
        "source",
        "list",
        "--jurisdiction",
        "NZ",
        "--format",
        "jsonl",
    )

    assert json.loads(detail.stdout)["preferred_name"] == "Aspirin"
    assert [
        item["jurisdiction"]
        for item in json.loads(jurisdictions.stdout)["jurisdictions"]
    ] == ["AU", "NZ"]
    source_records = [json.loads(line) for line in sources.stdout.splitlines()]
    assert {item["record"]["source_id"] for item in source_records} == {
        "medsafe",
        "pharmac",
    }


def test_unknown_concept_is_a_structured_stderr_failure(
    database: Path,
) -> None:
    result = _invoke(database, "concept", "show", "unknown")

    assert result.exit_code == 2
    assert not result.stdout
    assert json.loads(result.stderr)["error"] == "not_found"


def test_concept_show_supports_jsonl(database: Path) -> None:
    result = _invoke(
        database,
        "concept",
        "show",
        "gma:aspirin",
        "--format",
        "jsonl",
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["record"]["preferred_name"] == "Aspirin"


@pytest.mark.parametrize(
    ("arguments", "method"),
    [
        (("jurisdiction", "list"), "jurisdictions"),
        (("source", "list"), "sources"),
    ],
)
def test_catalogue_failures_are_structured(
    database: Path,
    monkeypatch: pytest.MonkeyPatch,
    arguments: tuple[str, ...],
    method: str,
) -> None:
    class UnavailableCatalogue:
        def jurisdictions(self) -> None:
            raise QueryServiceError("unavailable")

        def sources(self, _jurisdiction: str | None) -> None:
            raise QueryServiceError("unavailable")

    monkeypatch.setattr(
        cli,
        "_service",
        lambda _database, _allowed_root: UnavailableCatalogue(),
    )
    result = _invoke(database, *arguments)

    assert result.exit_code == 2
    assert not result.stdout
    assert json.loads(result.stderr)["error"] == "service_unavailable"
    assert method in {"jurisdictions", "sources"}
