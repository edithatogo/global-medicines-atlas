"""CLI contracts for bounded, evidence-preserving read-only queries."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from tests import test_query_service as query_service_tests
from typer.testing import CliRunner

from global_medicines_atlas import cli
from global_medicines_atlas.cli import app
from global_medicines_atlas.product_contracts import (
    ComparisonResponse,
    ErrorCode,
    EvidenceQuery,
)
from global_medicines_atlas.query_service import (
    InvalidCursorError,
    QueryServiceError,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)
CLOCK = NOW.isoformat()
CURSOR_KEY = "cli-query-" + "secret-long-enough"
runner = CliRunner()


class _Page:
    def __init__(
        self,
        collection: str,
        rows: list[dict[str, Any]],
        next_cursor: str | None,
    ) -> None:
        self._payload = {
            "metadata": {
                "api_version": "v1",
                "evidence_version": "0.6",
                "generated_at": CLOCK,
                "clocks": {"valid_at": CLOCK, "observed_at": CLOCK},
                "page": {
                    "limit": len(rows) or 1,
                    "returned": len(rows),
                    "next_cursor": next_cursor,
                },
            },
            collection: rows,
        }

    def model_dump(self, *, mode: str) -> dict[str, Any]:
        assert mode == "json"
        return self._payload


@pytest.fixture
def database(tmp_path: Path) -> Path:
    database_factory = (
        query_service_tests._database  # pyright: ignore[reportPrivateUsage]
    )
    return database_factory(tmp_path / "atlas.duckdb")


def _invoke(
    database: Path,
    command: str,
    arguments: list[str],
    *,
    secret: str | None = CURSOR_KEY,
):
    environment = {} if secret is None else {"GMA_CURSOR_SECRET": secret}
    return runner.invoke(
        app,
        [
            command,
            "--database",
            str(database),
            "--valid-at",
            CLOCK,
            "--observed-at",
            CLOCK,
            *arguments,
        ],
        env=environment,
    )


@pytest.mark.integration
def test_comparison_emits_contract_json_with_evidence(database: Path) -> None:
    result = _invoke(
        database,
        "comparison",
        [
            "--concept-id",
            "rx:1",
            "--jurisdiction",
            "NZ",
            "--jurisdiction",
            "AU",
        ],
    )

    assert result.exit_code == 0, result.stderr
    response = ComparisonResponse.model_validate_json(result.stdout)
    assert response.metadata.api_version == "v1"
    assert {item.dimension.value for item in response.conclusions} == {
        "regulatory",
        "funding",
    }
    assert all(
        item.provenance or item.evidence_unavailable_reason
        for item in response.conclusions
    )
    assert not result.stderr


@pytest.mark.integration
def test_coverage_preserves_unknown_denominator(database: Path) -> None:
    result = _invoke(
        database,
        "coverage",
        ["--jurisdiction", "US", "--dimension", "regulatory"],
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["coverage"][0]["denominator"] is None
    assert payload["coverage"][0]["state"] == "unknown"


@pytest.mark.integration
def test_evidence_jsonl_has_metadata_and_provenance(database: Path) -> None:
    result = _invoke(
        database,
        "evidence",
        ["--concept-id", "rx:1", "--format", "jsonl"],
    )

    assert result.exit_code == 0, result.stderr
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(records) == 3
    assert all(record["metadata"]["api_version"] == "v1" for record in records)
    assert all(record["record"]["provenance"] for record in records)
    assert all(record["record"]["valid_time"] for record in records)


@pytest.mark.smoke
def test_health_is_machine_readable(database: Path) -> None:
    result = runner.invoke(
        app,
        ["health", "--database", str(database)],
        env={"GMA_CURSOR_SECRET": CURSOR_KEY},
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["state"] == "ok"
    assert payload["checks"][0]["name"] == "canonical_database"


@pytest.mark.edge
@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            [
                "--concept-id",
                "rx:1",
                "--jurisdiction",
                "NZ",
                "--valid-at",
                "2026-07-29T00:00:00",
                "--observed-at",
                CLOCK,
            ],
            "invalid value",
        ),
        (
            [
                "--concept-id",
                "rx:1",
                "--jurisdiction",
                "NZ",
                "--max-rows",
                "10001",
            ],
            "10000",
        ),
    ],
)
def test_bad_cli_inputs_fail_without_stdout(
    database: Path, arguments: list[str], message: str
) -> None:
    result = runner.invoke(
        app,
        ["comparison", "--database", str(database), *arguments],
        env={"GMA_CURSOR_SECRET": CURSOR_KEY},
    )

    assert result.exit_code != 0
    assert not result.stdout
    assert message.casefold() in result.stderr.casefold()


@pytest.mark.edge
def test_missing_secret_is_structured_stderr(database: Path) -> None:
    result = _invoke(
        database,
        "comparison",
        ["--concept-id", "rx:1", "--jurisdiction", "NZ"],
        secret=None,
    )

    assert result.exit_code == 2
    assert not result.stdout
    envelope = json.loads(result.stderr)
    assert envelope["error"] == ErrorCode.SERVICE_UNAVAILABLE
    assert "GMA_CURSOR_SECRET" in envelope["message"]


@pytest.mark.edge
def test_database_cannot_escape_allowed_root(
    database: Path, tmp_path: Path
) -> None:
    other_root = tmp_path / "other"
    other_root.mkdir()
    result = _invoke(
        database,
        "comparison",
        [
            "--concept-id",
            "rx:1",
            "--jurisdiction",
            "NZ",
            "--allowed-root",
            str(other_root),
        ],
    )

    assert result.exit_code == 2
    envelope = json.loads(result.stderr)
    assert envelope["error"] == ErrorCode.INVALID_REQUEST
    assert "outside allowed_root" in envelope["message"]


@pytest.mark.edge
def test_formula_like_identifiers_remain_json_data(database: Path) -> None:
    result = _invoke(
        database,
        "comparison",
        ["--concept-id", "=HYPERLINK(1)", "--jurisdiction", "NZ"],
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["conclusions"] == []
    assert result.stdout.startswith("{")
    assert not result.stdout.startswith("=")


@pytest.mark.edge
def test_invalid_cursor_is_structured_stderr(database: Path) -> None:
    result = _invoke(
        database,
        "comparison",
        [
            "--concept-id",
            "rx:1",
            "--jurisdiction",
            "NZ",
            "--cursor",
            "invalid-cursor-token",
        ],
    )

    assert result.exit_code == 2
    envelope = json.loads(result.stderr)
    assert envelope["error"] == ErrorCode.INVALID_CURSOR


@pytest.mark.edge
@pytest.mark.parametrize(
    "failure", ["database deleted", "database corrupt", "I/O failure"]
)
def test_runtime_query_failures_are_service_unavailable_without_internal_leakage(
    database: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    internal_detail = f"{failure}: C:\\private\\atlas.duckdb secret-token"

    class UnavailableService:
        def comparisons(self, _query: object) -> ComparisonResponse:
            raise QueryServiceError(
                "query service is unavailable"
            ) from RuntimeError(internal_detail)

    def unavailable_service(
        _database: Path,
        _allowed_root: Path | None,
    ) -> UnavailableService:
        return UnavailableService()

    monkeypatch.setattr(cli, "_service", unavailable_service)
    result = _invoke(
        database,
        "comparison",
        ["--concept-id", "rx:1", "--jurisdiction", "NZ"],
    )

    assert result.exit_code == 2
    assert not result.stdout
    envelope = json.loads(result.stderr)
    assert envelope["error"] == ErrorCode.SERVICE_UNAVAILABLE
    assert envelope["message"] == "query service is unavailable"
    assert internal_detail not in result.stderr


@pytest.mark.integration
def test_jsonl_export_traverses_more_than_one_full_page(
    database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        {
            "assertion_id": f"a-{index:04d}",
            "provenance": {"source_record_id": f"source-{index:04d}"},
            "valid_time": {"valid_at": CLOCK, "observed_at": CLOCK},
        }
        for index in range(601)
    ]
    calls: list[tuple[str | None, int]] = []

    class Service:
        def evidence(self, query: EvidenceQuery) -> _Page:
            calls.append((query.cursor, query.limit))
            start = 0 if query.cursor is None else int(query.cursor)
            stop = min(start + query.limit, len(rows))
            next_cursor = str(stop) if stop < len(rows) else None
            return _Page("evidence", rows[start:stop], next_cursor)

    def service_factory(*_args: object, **_kwargs: object) -> Service:
        return Service()

    monkeypatch.setattr(cli, "_service", service_factory)
    result = _invoke(
        database,
        "evidence",
        [
            "--concept-id",
            "rx:1",
            "--format",
            "jsonl",
            "--limit",
            "250",
            "--max-rows",
            "1000",
        ],
    )

    assert result.exit_code == 0, result.stderr
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert [record["record"]["assertion_id"] for record in records] == [
        f"a-{index:04d}" for index in range(601)
    ]
    assert calls == [(None, 250), ("250", 250), ("500", 250)]
    assert all(
        record["metadata"]["export"]["truncated"] is False for record in records
    )
    assert (
        records[-1]["record"]["provenance"]["source_record_id"] == "source-0600"
    )


@pytest.mark.integration
def test_json_export_stops_at_max_rows_and_reports_resume_cursor(
    database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [{"assertion_id": f"a-{index:04d}"} for index in range(700)]

    class Service:
        def evidence(self, query: EvidenceQuery) -> _Page:
            start = 0 if query.cursor is None else int(query.cursor)
            stop = min(start + query.limit, len(rows))
            next_cursor = str(stop) if stop < len(rows) else None
            return _Page("evidence", rows[start:stop], next_cursor)

    def service_factory(*_args: object, **_kwargs: object) -> Service:
        return Service()

    monkeypatch.setattr(cli, "_service", service_factory)
    result = _invoke(
        database,
        "evidence",
        [
            "--concept-id",
            "rx:1",
            "--limit",
            "250",
            "--max-rows",
            "525",
        ],
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert len(payload["evidence"]) == 525
    assert payload["evidence"][0]["assertion_id"] == "a-0000"
    assert payload["evidence"][-1]["assertion_id"] == "a-0524"
    assert payload["metadata"]["export"] == {
        "max_rows": 525,
        "next_cursor": "525",
        "returned": 525,
        "truncated": True,
    }


@pytest.mark.edge
def test_repeated_export_cursor_fails_closed(
    database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Service:
        def evidence(self, query: EvidenceQuery) -> _Page:
            return _Page(
                "evidence",
                [{"assertion_id": str(query.cursor)}],
                "repeated",
            )

    service = Service()

    def service_factory(*_args: object, **_kwargs: object) -> Service:
        return service

    monkeypatch.setattr(cli, "_service", service_factory)
    result = _invoke(
        database,
        "evidence",
        ["--concept-id", "rx:1", "--max-rows", "10"],
    )

    assert result.exit_code == 2
    assert not result.stdout
    envelope = json.loads(result.stderr)
    assert envelope["error"] == ErrorCode.INVALID_CURSOR
    assert "repeated" in envelope["message"]


@pytest.mark.edge
def test_later_page_cursor_failure_is_structured(
    database: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Service:
        def evidence(self, query: EvidenceQuery) -> _Page:
            if query.cursor is not None:
                raise InvalidCursorError("cursor signature mismatch")
            return _Page("evidence", [{"assertion_id": "a-0000"}], "next")

    def service_factory(*_args: object, **_kwargs: object) -> Service:
        return Service()

    monkeypatch.setattr(cli, "_service", service_factory)
    result = _invoke(
        database,
        "evidence",
        ["--concept-id", "rx:1", "--max-rows", "10"],
    )

    assert result.exit_code == 2
    assert not result.stdout
    envelope = json.loads(result.stderr)
    assert envelope["error"] == ErrorCode.INVALID_CURSOR
    assert "signature mismatch" in envelope["message"]


@pytest.mark.unit
def test_cli_has_no_output_path_or_mutation_options() -> None:
    result = runner.invoke(app, ["comparison", "--help"])

    assert result.exit_code == 0
    assert "--output" not in result.stdout
    assert "--write" not in result.stdout
    assert "--delete" not in result.stdout
