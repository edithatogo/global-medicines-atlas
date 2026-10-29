"""Explicitly synthetic local demo data and application wiring.

The fixture exists to exercise the product end to end. It is not sourced from,
or evidence about, any medicine authority or funding program.
"""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

import duckdb
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from starlette.concurrency import iterate_in_threadpool

from .api import create_app
from .atlas import create_atlas_app
from .query_service import ReadOnlyQueryService

DEMO_CLOCK = datetime(2026, 7, 29, tzinfo=UTC)
DEMO_DATA_MODE = "synthetic-fixture"
DEMO_NOTICE = (
    "Synthetic fixture data only. No live source coverage, regulatory status, "
    "funding status, formulary status, or clinical conclusion is asserted."
)
DEMO_SECRET = b"gma-synthetic-demo-cursor-key"


def create_demo_database(path: Path) -> Path:
    """Create a deterministic canonical DuckDB fixture without overwriting."""
    target = path.expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise FileExistsError("demo database path already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.with_name(f".{target.name}.gma-demo-lock")
    lock_stream = lock.open("x")
    if target.exists() or target.is_symlink():
        lock_stream.close()
        lock.unlink(missing_ok=True)
        raise FileExistsError("demo database path already exists")
    connection: duckdb.DuckDBPyConnection | None = None
    try:  # ruff: ignore[too-many-statements-in-try-clause] - rollback must own all partial fixture writes.
        connection = duckdb.connect(str(target))
        connection.execute(
            """
            CREATE TABLE temporal_assertions (
                assertion_id VARCHAR NOT NULL,
                concept_id VARCHAR NOT NULL,
                jurisdiction VARCHAR NOT NULL,
                kind VARCHAR NOT NULL,
                authority VARCHAR NOT NULL,
                status_code VARCHAR NOT NULL,
                evidence_status VARCHAR NOT NULL,
                restrictions VARCHAR[] NOT NULL,
                valid_from TIMESTAMPTZ NOT NULL,
                valid_to TIMESTAMPTZ,
                observed_from TIMESTAMPTZ NOT NULL,
                observed_to TIMESTAMPTZ,
                supersedes_assertion_id VARCHAR,
                conflict_id VARCHAR,
                source_id VARCHAR NOT NULL,
                source_uri VARCHAR NOT NULL,
                retrieved_at TIMESTAMPTZ,
                source_effective_at TIMESTAMPTZ,
                source_path VARCHAR,
                source_sha256 VARCHAR,
                source_version VARCHAR,
                transformation VARCHAR
            );
            CREATE TABLE temporal_coverage (
                jurisdiction VARCHAR NOT NULL,
                source_id VARCHAR NOT NULL,
                receipt_id VARCHAR NOT NULL,
                observation_id VARCHAR NOT NULL,
                population_partition_id VARCHAR NOT NULL,
                dimension VARCHAR NOT NULL,
                medicine_concept_id VARCHAR,
                assertion_type VARCHAR NOT NULL,
                assertion_status VARCHAR NOT NULL,
                concept_population VARCHAR NOT NULL,
                valid_from TIMESTAMPTZ NOT NULL,
                valid_to TIMESTAMPTZ,
                observed_from TIMESTAMPTZ NOT NULL,
                observed_to TIMESTAMPTZ,
                assertion_count BIGINT NOT NULL,
                concept_numerator BIGINT NOT NULL,
                eligible_denominator BIGINT,
                exclusion_count BIGINT NOT NULL,
                exclusion_reasons VARCHAR[] NOT NULL,
                conflicting_assertion_count BIGINT NOT NULL
            )
            """
        )
        assertions: list[tuple[Any, ...]] = [
            (
                "demo-nz-regulatory",
                "rx:demo-medicine",
                "NZ",
                "regulatory",
                "Synthetic Medsafe fixture",
                "approved",
                "confirmed",
                [],
                DEMO_CLOCK,
                None,
                DEMO_CLOCK,
                None,
                None,
                None,
                "demo-medsafe",
                "https://example.test/synthetic/medsafe/demo-medicine",
                DEMO_CLOCK,
                None,
                "synthetic/medsafe.json",
                "a" * 64,
                "fixture-v1",
                "self-authored synthetic fixture; no source ingestion",
            ),
            (
                "demo-nz-funding",
                "rx:demo-medicine",
                "NZ",
                "funding",
                "Synthetic PHARMAC fixture",
                "funded",
                "confirmed",
                [],
                DEMO_CLOCK,
                None,
                DEMO_CLOCK,
                None,
                None,
                None,
                "demo-pharmac",
                "https://example.test/synthetic/pharmac/demo-medicine",
                DEMO_CLOCK,
                None,
                "synthetic/pharmac.json",
                "b" * 64,
                "fixture-v1",
                "self-authored synthetic fixture; no source ingestion",
            ),
            (
                "demo-au-regulatory",
                "rx:demo-medicine",
                "AU",
                "regulatory",
                "Synthetic TGA fixture",
                "registered",
                "confirmed",
                [],
                DEMO_CLOCK,
                None,
                DEMO_CLOCK,
                None,
                None,
                None,
                "demo-artg",
                "https://example.test/synthetic/artg/demo-medicine",
                DEMO_CLOCK,
                None,
                "synthetic/artg.json",
                "c" * 64,
                "fixture-v1",
                "self-authored synthetic fixture; no source ingestion",
            ),
        ]
        connection.executemany(
            "INSERT INTO temporal_assertions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            assertions,
        )
        connection.execute(
            """
            INSERT INTO temporal_coverage VALUES (
                'AU', 'demo-pbs', 'demo-receipt-au-funding',
                'demo-observation-au-funding', 'all', 'funding',
                'rx:demo-medicine', 'medicine', 'not_covered',
                'synthetic demo population', ?, NULL, ?, NULL, 0, 0, 100,
                0, [], 0
            )
            """,
            [DEMO_CLOCK, DEMO_CLOCK],
        )
        connection.close()
        connection = None
        return target  # ruff: ignore[try-consider-else]
    except Exception:
        if connection is not None:
            connection.close()
        target.unlink(missing_ok=True)
        raise
    finally:
        lock_stream.close()
        lock.unlink(missing_ok=True)


def create_demo_app(database: Path) -> FastAPI:
    """Wire the fixture into the existing read-only API and Atlas surfaces."""
    service = ReadOnlyQueryService(
        database,
        cursor_secret=DEMO_SECRET,
        allowed_root=database.parent,
    )
    api_app = create_app(service)
    atlas_app = create_atlas_app(service)
    app = FastAPI(
        title="Global Medicines Atlas Synthetic Demo",
        description=DEMO_NOTICE,
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
        redoc_url=None,
    )
    app.include_router(api_app.router)
    app.mount("/atlas", atlas_app)

    @app.middleware("http")
    async def mark_fixture_responses(  # pyright: ignore[reportUnusedFunction]
        request: Request, call_next: Any
    ) -> Any:
        response = await call_next(request)
        response.headers["X-GMA-Data-Mode"] = DEMO_DATA_MODE
        response.headers["X-GMA-Notice"] = DEMO_NOTICE
        if request.url.path.startswith("/atlas/") and response.headers.get(
            "content-type", ""
        ).startswith("text/html"):
            chunks = [chunk async for chunk in response.body_iterator]
            body = b"".join(chunks)
            notice = (
                "<aside role='note' style='padding:1rem;background:#fff3cd;"
                "color:#332701;border:2px solid #8a6d00'>"
                f"<strong>{escape(DEMO_NOTICE)}</strong></aside>"
            ).encode()
            body = body.replace(b"</body>", notice + b"</body>")

            response.body_iterator = iterate_in_threadpool(iter([body]))
            response.headers["content-length"] = str(len(body))
        return response

    @app.get("/", response_class=HTMLResponse)
    def demo_home() -> HTMLResponse:  # pyright: ignore[reportUnusedFunction]
        atlas_url = (
            "/atlas/?concept_id=rx%3Ademo-medicine&jurisdiction=NZ"
            "&jurisdiction=AU&valid_at=2026-07-29T00%3A00%3A00%2B00%3A00"
            "&observed_at=2026-07-29T00%3A00%3A00%2B00%3A00"
        )
        return HTMLResponse(
            "<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width'>"
            "<title>Global Medicines Atlas demo</title><main>"
            "<h1>Global Medicines Atlas demo</h1>"
            f"<p><strong>{escape(DEMO_NOTICE)}</strong></p>"
            "<p>Results are generated from three self-authored synthetic "
            "records. They are not evidence about the named authorities or "
            "real-world medicine status.</p>"
            f"<p><a href='{atlas_url}'>Open the Atlas comparison</a></p>"
            "<p><a href='/api/v1/docs'>Explore the read-only API</a></p>"
            "</main></html>"
        )

    return app
