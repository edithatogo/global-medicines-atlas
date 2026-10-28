"""Read-only command-line access to the Global Medicines Atlas."""

from __future__ import annotations

import importlib
import json
import os
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, NoReturn, cast

import typer
from pydantic import ValidationError

from .comparison_validity import abstaining_status_comparison_validity
from .gold_edge_review import (
    GoldEdgeReviewCase,
    build_gold_edge_review_queue,
    regenerate_gold_edge_review_queue,
)
from .historical_change_configuration import load_historical_change_service
from .platinum_edge_configuration import MAX_EDGE_FILE_ROWS, load_gold_edges
from .platinum_edges import MAX_EDGE_ROWS, gold_edge_payload
from .platinum_types import MAX_QUERY_OFFSET
from .platinum_v2_contracts import (
    V2ComparisonQuery,
    V2ComparisonResponse,
    V2EvidenceDimension,
    V2EvidenceQuery,
    V2EvidenceResponse,
)
from .platinum_v2_query_service import V2ReadOnlyQueryService
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
    ProductConclusion,
)
from .query_service import (
    InvalidCursorError,
    InvalidDatabaseError,
    QueryServiceError,
    ReadOnlyQueryService,
)
from .review_queue import load_adjudications

if TYPE_CHECKING:
    from .platinum_benefits import (
        BenefitsLookup,
        BenefitsPage,
        BenefitsQuery,
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
_BENEFITS_CURSOR_KEY_BYTES = 32
_BENEFITS_EXPORT_MAX_ROWS = 1000
_BENEFITS_EXPORT_MAX_BYTES = 8 * 1024 * 1024
_ROW_COLLECTIONS = frozenset({
    "conclusions",
    "concepts",
    "coverage",
    "evidence",
    "jurisdictions",
    "sources",
})
type ProductResponse = (
    ComparisonResponse
    | ConceptSearchResponse
    | CoverageResponse
    | EvidenceResponse
    | V2ComparisonResponse
    | V2EvidenceResponse
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


def _validated[ValueT](factory: Callable[[], ValueT]) -> ValueT:
    """Turn command-model validation into the stable CLI error envelope."""
    try:
        return factory()
    except ValidationError:
        _fail(ErrorCode.INVALID_REQUEST, "Command parameters are invalid")


def _service(
    database: Path,
    allowed_root: Path | None,
    service_type: type[ReadOnlyQueryService] = ReadOnlyQueryService,
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
        return service_type(
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
    collection_names = tuple(key for key in payload if key in _ROW_COLLECTIONS)
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
    collection_names = tuple(key for key in payload if key in _ROW_COLLECTIONS)
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
    include_comparison_validity: bool = True,
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
    if collection_name == "conclusions" and include_comparison_validity:
        conclusions = tuple(
            ProductConclusion.model_validate(row) for row in rows
        )
        payload["validity"] = [
            item.model_dump(mode="json")
            for item in abstaining_status_comparison_validity(conclusions)
        ]
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
    try:
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
    except ValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc
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


@app.command("v2-comparison")
def v2_comparison(
    database: DatabaseOption,
    concept_id: Annotated[str, typer.Option("--concept-id")],
    jurisdiction: Annotated[
        list[str], typer.Option("--jurisdiction", help="Repeat per country.")
    ],
    valid_at: ClockOption,
    observed_at: ClockOption,
    dimension: Annotated[
        list[V2EvidenceDimension],
        typer.Option("--dimension", case_sensitive=False),
    ],
    allowed_root: AllowedRootOption = None,
    limit: LimitOption = 50,
    cursor: CursorOption = None,
    format_: FormatOption = ExportFormat.JSON,
    max_rows: MaxRowsOption = 50,
) -> None:
    """Compare explicit V2 evidence dimensions without changing V1 output."""
    output = ExportRequest(format=format_, max_rows=max_rows)
    if format_ is ExportFormat.JSON and max_rows > limit:
        _fail(
            ErrorCode.INVALID_REQUEST,
            "V2 JSON output requires max-rows no greater than limit; use jsonl "
            "for multi-page exports",
        )
    query = _validated(
        lambda: V2ComparisonQuery(
            concept_id=concept_id,
            jurisdictions=tuple(jurisdiction),
            dimensions=tuple(dimension),
            valid_at=valid_at,
            observed_at=observed_at,
            limit=limit,
            cursor=cursor,
        )
    )
    service = cast(
        "V2ReadOnlyQueryService",
        _service(database, allowed_root, V2ReadOnlyQueryService),
    )
    _run(
        "v2 comparison",
        lambda page_cursor, page_limit: service.v2_comparisons(
            query.model_copy(
                update={"cursor": page_cursor, "limit": page_limit},
            )
        ),
        output,
        cursor=cursor,
        page_limit=limit,
        include_comparison_validity=False,
    )


@app.command("v2-evidence")
def v2_evidence(
    database: DatabaseOption,
    concept_id: Annotated[str, typer.Option("--concept-id")],
    jurisdiction: Annotated[str, typer.Option("--jurisdiction")],
    dimension: Annotated[
        V2EvidenceDimension,
        typer.Option("--dimension", case_sensitive=False),
    ],
    valid_at: ClockOption,
    observed_at: ClockOption,
    allowed_root: AllowedRootOption = None,
    limit: LimitOption = 50,
    cursor: CursorOption = None,
    format_: FormatOption = ExportFormat.JSON,
    max_rows: MaxRowsOption = 50,
) -> None:
    """Page complete assertion evidence for one V2 dimension."""
    output = ExportRequest(format=format_, max_rows=max_rows)
    if format_ is ExportFormat.JSON and max_rows > limit:
        _fail(
            ErrorCode.INVALID_REQUEST,
            "V2 JSON output requires max-rows no greater than limit; use jsonl "
            "for multi-page exports",
        )
    query = _validated(
        lambda: V2EvidenceQuery(
            concept_id=concept_id,
            jurisdiction=jurisdiction,
            dimension=dimension,
            valid_at=valid_at,
            observed_at=observed_at,
            limit=limit,
            cursor=cursor,
        )
    )
    service = cast(
        "V2ReadOnlyQueryService",
        _service(database, allowed_root, V2ReadOnlyQueryService),
    )
    _run(
        "v2 evidence",
        lambda page_cursor, page_limit: service.v2_evidence(
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


@app.command("history")
def history_query(
    history_file: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    offset: Annotated[int, typer.Option(min=0)] = 0,
    limit: Annotated[int, typer.Option(min=1, max=1000)] = 100,
) -> None:
    """Page validated source-native historical-change observations."""
    try:
        page = load_historical_change_service(history_file).page(
            offset=offset, limit=limit
        )
    except OSError, ValidationError, ValueError:
        _fail(
            ErrorCode.INVALID_REQUEST,
            "The historical evidence file is invalid or unavailable",
        )
    typer.echo(page.model_dump_json())


@app.command("edges")
def edges_query(
    edge_file: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    source_node_id: Annotated[str | None, typer.Option()] = None,
    target_node_id: Annotated[str | None, typer.Option()] = None,
    kind: Annotated[str | None, typer.Option()] = None,
    limit: Annotated[int, typer.Option(min=1, max=MAX_EDGE_ROWS)] = 1000,
    offset: Annotated[int, typer.Option(min=0, max=MAX_EDGE_FILE_ROWS)] = 0,
) -> None:
    """Inspect bounded structural Gold evidence edges."""
    try:
        payload = gold_edge_payload(
            load_gold_edges(edge_file),
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            kind=kind,
            max_rows=limit,
            offset=offset,
            include_pagination=True,
        )
    except OSError, ValueError:
        _fail(
            ErrorCode.INVALID_REQUEST,
            "The Gold edge file or selectors are invalid",
        )
    typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))


@app.command("gold-review-queue")
def gold_review_queue_query(
    edge_file: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    queued_at: Annotated[
        datetime,
        typer.Option(
            formats=["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"],
            help="Timezone-aware timestamp used to bind review case identity.",
        ),
    ],
    adjudications_file: Annotated[
        Path | None,
        typer.Option(
            exists=True,
            dir_okay=False,
            help="Optional append-only caller-supplied adjudication JSONL.",
        ),
    ] = None,
    limit: Annotated[int, typer.Option(min=1, max=1000)] = 1000,
) -> None:
    """List pending Gold review cases without authoring decisions or promotion."""
    try:
        pending, event_count = _pending_gold_review_cases(
            edge_file,
            queued_at=queued_at,
            adjudications_file=adjudications_file,
            limit=limit,
        )
    except KeyError, OSError, TypeError, ValidationError, ValueError:
        _fail(
            ErrorCode.INVALID_REQUEST,
            "The Gold edge or adjudication file is invalid",
        )
    typer.echo(
        json.dumps(
            {
                "adjudication_event_count": event_count,
                "adjudication_authority_verified": False,
                "cases": [case.model_dump(mode="json") for case in pending],
                "promotion_performed": False,
                "qualification": "synthetic_silver_candidate_only",
                "schema_version": 1,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _pending_gold_review_cases(
    edge_file: Path,
    *,
    queued_at: datetime,
    adjudications_file: Path | None,
    limit: int,
) -> tuple[tuple[GoldEdgeReviewCase, ...], int]:
    edges = load_gold_edges(edge_file)
    if edges.num_rows > limit:
        raise ValueError("review queue edge row bound exceeded")
    projected_items = gold_edge_payload(edges, max_rows=limit)["items"]
    models: list[dict[str, object]] = []
    for item in projected_items:
        model = {
            key: value
            for key, value in item.items()
            if key not in {"evidence", "controls"}
        }
        model["evidence"] = item["evidence"]
        model.update(item["controls"])
        models.append(model)
    cases = build_gold_edge_review_queue(models, queued_at=queued_at)
    events = (
        load_adjudications(adjudications_file)
        if adjudications_file is not None
        else ()
    )
    return regenerate_gold_edge_review_queue(cases, events), len(events)


def _benefits_jsonl_export(  # ruff: ignore[too-many-locals,too-many-statements] -- keep cursor, identity, and output bounds in one auditable traversal.
    service: BenefitsLookup,
    resource_id: str,
    query: BenefitsQuery,
    max_rows: int,
    page_payload: Callable[[BenefitsPage], dict[str, object]],
) -> tuple[str, bool]:
    """Collect and validate a bounded page chain before emitting any bytes."""

    pages: list[dict[str, object]] = []
    row_count = 0
    page_size = min(query.limit, max_rows)
    seen_cursors: set[str] = (
        {query.cursor} if query.cursor is not None else set()
    )
    cursor = query.cursor
    baseline: dict[str, object] | None = None
    truncated = False
    rows_by_page: list[list[dict[str, object]]] = []
    while True:
        page_query = query.model_copy(
            update={
                "cursor": cursor,
                "limit": page_size,
            }
        )
        page = service.query(resource_id, page_query)
        payload = page_payload(page)
        if page.status == "unavailable":
            return _benefits_serialize_jsonl({
                "type": "summary",
                "status": "unavailable",
                "source_completeness": "not_established",
                "page": payload,
            }), True

        current = {
            "identity": payload["identity"],
            "query_sha256": payload["query_sha256"],
            "window_sha256": payload["window_sha256"],
            "applied_filters": payload["applied_filters"],
            "window_rows": payload["window_rows"],
            "window_limit": payload["window_limit"],
        }
        if baseline is None:
            baseline = current
        elif current != baseline:
            raise ValueError(
                "benefits pages changed identity or query evidence"
            )
        page_rows = payload["rows"]
        if not isinstance(page_rows, list):
            raise TypeError("benefits page rows must be a list")
        raw_rows = cast("list[object]", page_rows)
        if any(not isinstance(row, dict) for row in raw_rows):
            raise TypeError("benefits page contains an invalid row")
        typed_rows = cast("list[dict[str, object]]", raw_rows)
        if row_count + len(typed_rows) > max_rows:
            raise ValueError(
                "benefits page exceeded the requested export bound"
            )
        row_count += len(typed_rows)
        rows_by_page.append(typed_rows)
        pages.append(payload)
        next_cursor = payload["next_cursor"]
        if next_cursor is None:
            cursor = None
            break
        if not isinstance(next_cursor, str) or next_cursor in seen_cursors:
            raise ValueError("benefits cursor loop detected")
        cursor = next_cursor
        seen_cursors.add(next_cursor)
        if row_count + page_size > max_rows:
            truncated = True
            break
    metadata_keys = (
        "identity",
        "query_sha256",
        "window_sha256",
        "applied_filters",
        "coverage_state",
        "confidence_state",
        "uncertainty_state",
        "review_state",
        "comparison_validity",
    )
    records: list[str] = []
    for page_number, (payload, page_rows) in enumerate(
        zip(pages, rows_by_page, strict=True), start=1
    ):
        records.extend(
            _benefits_serialize_jsonl({
                "type": "record",
                "page": page_number,
                **{key: payload[key] for key in metadata_keys},
                "page_sha256": payload["page_sha256"],
                "receipt_sha256": payload["receipt_sha256"],
                "record": row,
            })
            for row in page_rows
        )
    final_page = pages[-1]
    summary = {
        "type": "summary",
        "status": "available",
        "row_count": row_count,
        "page_count": len(pages),
        "page_size": page_size,
        "max_rows": max_rows,
        "source_completeness": "not_established",
        "truncated": truncated,
        "next_cursor": cursor,
        "window_rows": final_page["window_rows"],
        "window_limit": final_page["window_limit"],
        "window_complete": final_page["window_complete"],
        "page_sha256s": [page["page_sha256"] for page in pages],
        "receipt_sha256s": [page["receipt_sha256"] for page in pages],
        **{key: baseline[key] for key in metadata_keys[:4]},
        **{key: final_page[key] for key in metadata_keys[4:]},
    }
    records.append(_benefits_serialize_jsonl(summary))
    output = "\n".join(records)
    if len(output.encode("utf-8")) + 1 > _BENEFITS_EXPORT_MAX_BYTES:
        raise ValueError("benefits JSONL export exceeds the byte limit")
    return output, False


def _benefits_serialize_jsonl(record: dict[str, object]) -> str:
    """Serialize strict JSONL records with finite values and stable keys."""
    return json.dumps(
        record,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


@app.command("benefits")
def benefits_query(
    resource_id: Annotated[str, typer.Argument()],
    trust_file: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    metadata_root: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    schema_file: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    columns: Annotated[list[str], typer.Option("--column")],
    limit: Annotated[int, typer.Option(min=1, max=100)] = 100,
    cursor: str | None = None,
    filters_json: Annotated[str | None, typer.Option("--filters-json")] = None,
    output_format: Annotated[
        ExportFormat,
        typer.Option("--format", case_sensitive=False, help="json or jsonl."),
    ] = ExportFormat.JSON,
    max_rows: Annotated[
        int,
        typer.Option(
            "--max-rows",
            min=1,
            max=_BENEFITS_EXPORT_MAX_ROWS,
            help="Maximum rows in a JSONL export (at most 1,000).",
        ),
    ] = _BENEFITS_EXPORT_MAX_ROWS,
    *,
    offline: bool = False,
) -> None:
    """Query trusted benefits pages; JSONL exports are bounded and paged."""
    from .platinum_benefits import (  # ruff: ignore[import-outside-top-level] -- optional federation boundary
        BenefitsQuery,
        BenefitsService,
        benefits_page_payload,
        parse_benefits_filters,
    )

    try:
        from .platinum_configuration import (  # ruff: ignore[import-outside-top-level] -- optional federation boundary
            load_benefits_resolver,
        )
    except ModuleNotFoundError as error:
        if error.name != "jsonschema":
            raise
        _fail(
            ErrorCode.SERVICE_UNAVAILABLE,
            "Install 'global-medicines-atlas[federation]' to query benefits",
        )
    from .platinum_identity_service import (  # ruff: ignore[import-outside-top-level] -- optional federation boundary
        UnknownPlatinumResourceError,
    )

    secret = os.environ.get(_CURSOR_ENV, "")
    if len(secret.encode()) < _BENEFITS_CURSOR_KEY_BYTES:
        _fail(ErrorCode.SERVICE_UNAVAILABLE, f"{_CURSOR_ENV} requires 32 bytes")
    resolver = None
    try:  # ruff: ignore[too-many-statements-in-try-clause] -- one stable CLI error envelope covers resolver and page traversal errors.
        query = BenefitsQuery(
            columns=tuple(columns),
            limit=limit,
            cursor=cursor,
            offline=offline,
            filters=parse_benefits_filters(filters_json),
        )
        resolver = load_benefits_resolver(
            trust_file=trust_file,
            metadata_root=metadata_root,
            schema_file=schema_file,
        )
        service = BenefitsService(resolver, cursor_key=secret.encode())
        if output_format == ExportFormat.JSON:
            page = service.query(resource_id, query)
            typer.echo(page.model_dump_json())
            if page.status == "unavailable":
                raise typer.Exit(3)
            return
        output, unavailable = _benefits_jsonl_export(
            service, resource_id, query, max_rows, benefits_page_payload
        )
        typer.echo(output)
        if unavailable:
            raise typer.Exit(3)
    except UnknownPlatinumResourceError:
        _fail(
            ErrorCode.NOT_FOUND, "The admitted benefits resource was not found"
        )
    except ValueError, OSError, TypeError:
        _fail(
            ErrorCode.INVALID_REQUEST,
            "The benefits query or operator configuration is invalid",
        )

    finally:
        if resolver is not None:
            resolver.close()


@app.command("source-structure")
def source_structure_query(
    resource_id: Annotated[str, typer.Argument()],
    trust_file: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    metadata_root: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    schema_file: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    columns: Annotated[list[str], typer.Option("--column")],
    limit: Annotated[int, typer.Option(min=1, max=100)] = 100,
    offset: Annotated[int, typer.Option(min=0, max=MAX_QUERY_OFFSET)] = 0,
    *,
    offline: bool = False,
    view: Annotated[Literal["records", "fields"], typer.Option()] = "records",
) -> None:
    """Query bounded source-structure evidence from operator-pinned trust."""
    try:
        resolver = _dataset_resolver_loader()(
            trust_file=trust_file,
            metadata_root=metadata_root,
            schema_file=schema_file,
        )
    except ValueError, OSError:
        _fail(
            ErrorCode.INVALID_REQUEST,
            "The source-structure operator configuration is invalid",
        )

    from .platinum_identity_service import (  # ruff: ignore[import-outside-top-level] -- optional federation boundary
        UnknownPlatinumResourceError,
    )
    from .platinum_structure import (  # ruff: ignore[import-outside-top-level] -- optional federation boundary
        SourceStructureQuery,
        SourceStructureService,
    )

    try:
        jurisdictions = {
            candidate_id: candidate_id.split(".", maxsplit=1)[0].upper()
            for candidate_id in resolver.resource_ids
        }
        page = SourceStructureService(
            resolver, jurisdictions=jurisdictions
        ).query(
            resource_id,
            SourceStructureQuery(
                columns=tuple(columns),
                limit=limit,
                offset=offset,
                offline=offline,
                view=view,
            ),
        )
    except UnknownPlatinumResourceError:
        _fail(
            ErrorCode.NOT_FOUND,
            "The admitted source-structure resource was not found",
        )
    except ValueError, OSError:
        _fail(
            ErrorCode.INVALID_REQUEST,
            "The source-structure query or operator configuration is invalid",
        )
    typer.echo(page.model_dump_json())
    if page.status == "unavailable":
        raise typer.Exit(3)


def _dataset_resolver_loader() -> Callable[..., Any]:
    """Load the optional resolver configuration with a typed failure mode."""
    try:
        module = importlib.import_module(
            ".platinum_configuration", package=__package__
        )
    except ModuleNotFoundError as error:
        if error.name != "jsonschema":
            raise
        _fail(
            ErrorCode.SERVICE_UNAVAILABLE,
            "Install 'global-medicines-atlas[federation]' to inspect datasets",
        )
    return cast("Callable[..., Any]", module.load_benefits_resolver)


@app.command("datasets")
def dataset_list(
    trust_file: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    metadata_root: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    schema_file: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
) -> None:
    """List bounded exact identities from independently provisioned trust."""
    from .platinum_identity_service import (  # ruff: ignore[import-outside-top-level] -- optional federation boundary
        ResolverDatasetIdentityService,
    )

    try:
        resolver = _dataset_resolver_loader()(
            trust_file=trust_file,
            metadata_root=metadata_root,
            schema_file=schema_file,
        )
        jurisdictions = {
            resource_id: resource_id.split(".", maxsplit=1)[0].upper()
            for resource_id in resolver.resource_ids
        }
        page = ResolverDatasetIdentityService(
            resolver, jurisdictions=jurisdictions
        ).identities()
    except ValueError, OSError:
        _fail(
            ErrorCode.INVALID_REQUEST,
            "The dataset identity operator configuration is invalid",
        )
    typer.echo(page.model_dump_json())


def main() -> None:
    """Run the command-line application."""
    app()


if __name__ == "__main__":
    main()
