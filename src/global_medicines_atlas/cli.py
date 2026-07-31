"""Read-only command-line access to the Global Medicines Atlas."""

from __future__ import annotations

import json
import os
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, NoReturn, cast

import typer
from pydantic import ValidationError

from .product_contracts import (
    API_VERSION,
    MAX_EXPORT_ROWS,
    MAX_PAGE_SIZE,
    PRODUCT_EVIDENCE_VERSION,
    ComparisonQuery,
    ComparisonResponse,
    ConceptSearchQuery,
    ConceptSearchResponse,
    CoverageQuery,
    CoverageResponse,
    ErrorCode,
    ErrorEnvelope,
    EvidenceDimension,
    EvidenceQuery,
    EvidenceResponse,
    ExportFormat,
    ExportRequest,
    HealthCheck,
    HealthResponse,
    HealthState,
)
from .query_service import (
    InvalidCursorError,
    InvalidDatabaseError,
    QueryServiceError,
    ReadOnlyQueryService,
)

app = typer.Typer(
    add_completion=False,
    help="Read-only medicine comparison, coverage, and evidence queries.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
concept_app = typer.Typer(add_completion=False, no_args_is_help=True)
jurisdiction_app = typer.Typer(add_completion=False, no_args_is_help=True)
source_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(concept_app, name="concept", help="Discover canonical concepts.")
app.add_typer(
    jurisdiction_app, name="jurisdiction", help="Inspect jurisdictions."
)
app.add_typer(source_app, name="source", help="Inspect governed sources.")
_CURSOR_ENV = "GMA_CURSOR_" + "SECRET"
_MINIMUM_CURSOR_KEY_BYTES = 16
type ProductResponse = (
    ComparisonResponse
    | ConceptSearchResponse
    | CoverageResponse
    | EvidenceResponse
)
type PageAction = Callable[[str | None, int], ProductResponse]

DatabaseOption = Annotated[
    Path,
    typer.Option(
        "--database",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Absolute path to a canonical DuckDB database.",
    ),
]
AllowedRootOption = Annotated[
    Path | None,
    typer.Option(
        "--allowed-root",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Directory within which the database must reside.",
    ),
]
ClockOption = Annotated[
    datetime,
    typer.Option(
        formats=["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"],
        help="Timezone-aware ISO-8601 clock.",
    ),
]
LimitOption = Annotated[
    int,
    typer.Option(min=1, max=MAX_PAGE_SIZE, help="Maximum rows in this page."),
]
CursorOption = Annotated[
    str | None,
    typer.Option(help="Opaque cursor returned by the preceding page."),
]
FormatOption = Annotated[
    ExportFormat,
    typer.Option("--format", case_sensitive=False, help="json or jsonl."),
]
MaxRowsOption = Annotated[
    int,
    typer.Option(
        "--max-rows",
        min=1,
        max=MAX_EXPORT_ROWS,
        help="Hard export bound; cannot exceed 10,000.",
    ),
]


def _request_id() -> str:
    return secrets.token_hex(8)


def _fail(
    code: ErrorCode,
    message: str,
    *,
    exit_code: int = 2,
) -> NoReturn:
    envelope = ErrorEnvelope(
        error=code,
        message=message,
        request_id=_request_id(),
    )
    typer.echo(envelope.model_dump_json(), err=True)
    raise typer.Exit(exit_code)


def _service(
    database: Path,
    allowed_root: Path | None,
) -> ReadOnlyQueryService:
    secret = os.environ.get(_CURSOR_ENV)
    if secret is None:
        _fail(
            ErrorCode.SERVICE_UNAVAILABLE,
            f"{_CURSOR_ENV} must be set and contain at least "
            f"{_MINIMUM_CURSOR_KEY_BYTES} UTF-8 bytes",
        )
    if len(secret.encode()) < _MINIMUM_CURSOR_KEY_BYTES:
        _fail(
            ErrorCode.SERVICE_UNAVAILABLE,
            f"{_CURSOR_ENV} must contain at least "
            f"{_MINIMUM_CURSOR_KEY_BYTES} UTF-8 bytes",
        )
    root = allowed_root if allowed_root is not None else database.parent
    try:
        return ReadOnlyQueryService(
            database,
            cursor_secret=secret.encode(),
            allowed_root=root,
        )
    except InvalidDatabaseError as error:
        _fail(ErrorCode.INVALID_REQUEST, str(error))


def _emit(payload: dict[str, Any], output: ExportRequest) -> None:
    if output.format is ExportFormat.JSON:
        typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return

    metadata = payload["metadata"]
    collection_names = tuple(key for key in payload if key != "metadata")
    if len(collection_names) != 1:
        _fail(ErrorCode.INTERNAL_ERROR, "response shape is not exportable")
    rows_object: object = payload[collection_names[0]]
    if not isinstance(rows_object, list):
        _fail(ErrorCode.INTERNAL_ERROR, "response rows are not exportable")
    rows = cast("list[object]", rows_object)
    if len(rows) > output.max_rows:
        _fail(
            ErrorCode.LIMIT_EXCEEDED,
            f"response exceeds the {output.max_rows}-row export bound",
        )
    for row in rows:
        typer.echo(
            json.dumps(
                {"metadata": metadata, "record": row},
                sort_keys=True,
                separators=(",", ":"),
            )
        )


def _collection(payload: dict[str, Any]) -> tuple[str, list[object]]:
    collection_names = tuple(key for key in payload if key != "metadata")
    if len(collection_names) != 1:
        _fail(ErrorCode.INTERNAL_ERROR, "response shape is not exportable")
    collection_name = collection_names[0]
    rows_object: object = payload[collection_name]
    if not isinstance(rows_object, list):
        _fail(ErrorCode.INTERNAL_ERROR, "response rows are not exportable")
    return collection_name, cast("list[object]", rows_object)


def _emit_records(
    collection: str,
    records: list[dict[str, Any]],
    output: ExportRequest,
) -> None:
    payload = {
        "metadata": {
            "api_version": API_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "page": {
                "limit": len(records) or 1,
                "returned": len(records),
                "next_cursor": None,
            },
        },
        collection: records,
    }
    _emit(payload, output)


def _run(
    operation: str,
    action: PageAction,
    output: ExportRequest,
    *,
    cursor: str | None,
    page_limit: int,
) -> None:
    rows: list[object] = []
    seen_cursors: set[str] = {cursor} if cursor is not None else set()
    next_cursor = cursor
    payload: dict[str, Any] | None = None
    collection_name: str | None = None
    truncated = False
    pages_fetched = 0

    while len(rows) < output.max_rows:
        requested = min(page_limit, output.max_rows - len(rows))
        try:
            response = action(next_cursor, requested)
        except InvalidCursorError as error:
            _fail(ErrorCode.INVALID_CURSOR, str(error))
        except QueryServiceError as error:
            _fail(ErrorCode.SERVICE_UNAVAILABLE, str(error))
        except (ValidationError, ValueError) as error:
            _fail(ErrorCode.INVALID_REQUEST, str(error))

        page_payload = response.model_dump(mode="json")
        pages_fetched += 1
        page_collection, page_rows = _collection(page_payload)
        if collection_name is not None and page_collection != collection_name:
            _fail(
                ErrorCode.INTERNAL_ERROR,
                "response collection changed between pages",
            )
        collection_name = page_collection
        payload = page_payload
        rows.extend(page_rows)

        raw_cursor: object = page_payload["metadata"]["page"]["next_cursor"]
        if raw_cursor is not None and not isinstance(raw_cursor, str):
            _fail(ErrorCode.INTERNAL_ERROR, "response cursor is not exportable")
        following_cursor = raw_cursor
        if following_cursor is None:
            next_cursor = None
            break
        if following_cursor in seen_cursors:
            _fail(
                ErrorCode.INVALID_CURSOR,
                f"{operation} returned a repeated pagination cursor",
            )
        seen_cursors.add(following_cursor)
        next_cursor = following_cursor
    else:
        truncated = next_cursor is not None

    if payload is None or collection_name is None:
        _fail(ErrorCode.INTERNAL_ERROR, f"{operation} returned no response")
    payload[collection_name] = rows
    if pages_fetched > 1 or truncated:
        payload["metadata"]["export"] = {
            "max_rows": output.max_rows,
            "returned": len(rows),
            "truncated": truncated,
            "next_cursor": next_cursor if truncated else None,
        }
    _emit(payload, output)


@app.command("comparison")
def comparison(
    database: DatabaseOption,
    concept_id: Annotated[str, typer.Option("--concept-id")],
    jurisdiction: Annotated[
        list[str], typer.Option("--jurisdiction", help="Repeat per country.")
    ],
    valid_at: ClockOption,
    observed_at: ClockOption,
    dimension: Annotated[
        list[EvidenceDimension] | None,
        typer.Option("--dimension", case_sensitive=False),
    ] = None,
    allowed_root: AllowedRootOption = None,
    limit: LimitOption = 50,
    cursor: CursorOption = None,
    format_: FormatOption = ExportFormat.JSON,
    max_rows: MaxRowsOption = 1_000,
) -> None:
    """Compare regulatory, funding, and formulary evidence."""
    output = ExportRequest(format=format_, max_rows=max_rows)
    query = ComparisonQuery(
        concept_id=concept_id,
        jurisdictions=tuple(jurisdiction),
        dimensions=tuple(
            dimension
            or (EvidenceDimension.REGULATORY, EvidenceDimension.FUNDING)
        ),
        valid_at=valid_at,
        observed_at=observed_at,
        limit=limit,
        cursor=cursor,
        export=output,
    )
    service = _service(database, allowed_root)
    _run(
        "comparison",
        lambda page_cursor, page_limit: service.comparisons(
            query.model_copy(
                update={"cursor": page_cursor, "limit": page_limit},
            )
        ),
        output,
        cursor=cursor,
        page_limit=limit,
    )


@concept_app.command("search")
def concept_search(
    database: DatabaseOption,
    query_text: Annotated[str, typer.Argument(help="Medicine name or ID.")],
    jurisdiction: Annotated[
        list[str] | None,
        typer.Option("--jurisdiction", help="Repeat per country."),
    ] = None,
    allowed_root: AllowedRootOption = None,
    limit: LimitOption = 50,
    cursor: CursorOption = None,
    format_: FormatOption = ExportFormat.JSON,
    max_rows: MaxRowsOption = 1_000,
) -> None:
    """Search canonical concepts deterministically."""
    output = ExportRequest(format=format_, max_rows=max_rows)
    query = ConceptSearchQuery(
        query=query_text,
        jurisdictions=tuple(jurisdiction or ()),
        limit=limit,
        cursor=cursor,
    )
    service = _service(database, allowed_root)
    _run(
        "concept search",
        lambda page_cursor, page_limit: service.search_concepts(
            query.model_copy(
                update={"cursor": page_cursor, "limit": page_limit},
            )
        ),
        output,
        cursor=cursor,
        page_limit=limit,
    )


@concept_app.command("show")
def concept_show(
    database: DatabaseOption,
    concept_id: Annotated[str, typer.Argument(help="Canonical concept ID.")],
    allowed_root: AllowedRootOption = None,
    format_: FormatOption = ExportFormat.JSON,
) -> None:
    """Show one canonical concept."""
    try:
        detail = _service(database, allowed_root).concept_detail(concept_id)
    except QueryServiceError:
        _fail(ErrorCode.NOT_FOUND, "The canonical concept was not found")
    record = detail.model_dump(mode="json")
    if format_ is ExportFormat.JSON:
        typer.echo(json.dumps(record, sort_keys=True, separators=(",", ":")))
    else:
        typer.echo(
            json.dumps(
                {"record": record},
                sort_keys=True,
                separators=(",", ":"),
            )
        )


@jurisdiction_app.command("list")
def jurisdiction_list(
    database: DatabaseOption,
    allowed_root: AllowedRootOption = None,
    format_: FormatOption = ExportFormat.JSON,
    max_rows: MaxRowsOption = 1_000,
) -> None:
    """List measured jurisdiction catalogue entries."""
    output = ExportRequest(format=format_, max_rows=max_rows)
    try:
        rows = _service(database, allowed_root).jurisdictions()
    except QueryServiceError:
        _fail(
            ErrorCode.SERVICE_UNAVAILABLE,
            "The read-only query service is unavailable",
        )
    _emit_records(
        "jurisdictions",
        [row.model_dump(mode="json") for row in rows],
        output,
    )


@source_app.command("list")
def source_list(
    database: DatabaseOption,
    jurisdiction: Annotated[str | None, typer.Option("--jurisdiction")] = None,
    allowed_root: AllowedRootOption = None,
    format_: FormatOption = ExportFormat.JSON,
    max_rows: MaxRowsOption = 1_000,
) -> None:
    """List governed source catalogue entries."""
    output = ExportRequest(format=format_, max_rows=max_rows)
    try:
        rows = _service(database, allowed_root).sources(jurisdiction)
    except QueryServiceError:
        _fail(
            ErrorCode.SERVICE_UNAVAILABLE,
            "The read-only query service is unavailable",
        )
    _emit_records(
        "sources",
        [row.model_dump(mode="json") for row in rows],
        output,
    )


@app.command()
def coverage(
    database: DatabaseOption,
    jurisdiction: Annotated[
        list[str], typer.Option("--jurisdiction", help="Repeat per country.")
    ],
    valid_at: ClockOption,
    observed_at: ClockOption,
    dimension: Annotated[
        list[EvidenceDimension] | None,
        typer.Option("--dimension", case_sensitive=False),
    ] = None,
    allowed_root: AllowedRootOption = None,
    limit: LimitOption = 50,
    cursor: CursorOption = None,
    format_: FormatOption = ExportFormat.JSON,
    max_rows: MaxRowsOption = 1_000,
) -> None:
    """Report explicit source coverage without inferring negative status."""
    output = ExportRequest(format=format_, max_rows=max_rows)
    query = CoverageQuery(
        jurisdictions=tuple(jurisdiction),
        dimensions=tuple(dimension or ()),
        valid_at=valid_at,
        observed_at=observed_at,
        limit=limit,
        cursor=cursor,
    )
    service = _service(database, allowed_root)
    _run(
        "coverage",
        lambda page_cursor, page_limit: service.coverage(
            query.model_copy(
                update={"cursor": page_cursor, "limit": page_limit},
            )
        ),
        output,
        cursor=cursor,
        page_limit=limit,
    )


@app.command()
def evidence(
    database: DatabaseOption,
    valid_at: ClockOption,
    observed_at: ClockOption,
    assertion_id: Annotated[str | None, typer.Option("--assertion-id")] = None,
    concept_id: Annotated[str | None, typer.Option("--concept-id")] = None,
    allowed_root: AllowedRootOption = None,
    limit: LimitOption = 50,
    cursor: CursorOption = None,
    format_: FormatOption = ExportFormat.JSON,
    max_rows: MaxRowsOption = 1_000,
) -> None:
    """Drill down to provenance-bearing evidence."""
    output = ExportRequest(format=format_, max_rows=max_rows)
    query = EvidenceQuery(
        assertion_id=assertion_id,
        concept_id=concept_id,
        valid_at=valid_at,
        observed_at=observed_at,
        limit=limit,
        cursor=cursor,
    )
    service = _service(database, allowed_root)
    _run(
        "evidence",
        lambda page_cursor, page_limit: service.evidence(
            query.model_copy(
                update={"cursor": page_cursor, "limit": page_limit},
            )
        ),
        output,
        cursor=cursor,
        page_limit=limit,
    )


@app.command()
def health(
    database: DatabaseOption,
    allowed_root: AllowedRootOption = None,
) -> None:
    """Validate that the configured canonical database is queryable."""
    service = _service(database, allowed_root)
    check = HealthCheck(
        name="canonical_database",
        state=HealthState.OK,
        detail=str(service.database_path),
    )
    state = HealthState.OK
    response = HealthResponse(
        api_version=API_VERSION,
        evidence_version=PRODUCT_EVIDENCE_VERSION,
        state=state,
        checked_at=datetime.now(UTC),
        checks=(check,),
    )
    typer.echo(response.model_dump_json())


def main() -> None:
    """Run the command-line application."""
    app()


if __name__ == "__main__":
    main()
