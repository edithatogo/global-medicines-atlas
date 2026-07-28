"""Read-only FastAPI surface for evidence-backed medicine comparisons."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import AwareDatetime, ValidationError

from .product_contracts import (
    API_BASE_PATH,
    MAX_PAGE_SIZE,
    PRODUCT_EVIDENCE_VERSION,
    ComparisonQuery,
    ComparisonResponse,
    CoverageQuery,
    CoverageResponse,
    ErrorCode,
    ErrorDetail,
    ErrorEnvelope,
    EvidenceDimension,
    EvidenceQuery,
    EvidenceResponse,
    HealthCheck,
    HealthResponse,
    HealthState,
)
from .query_service import (
    InvalidCursorError,
    QueryServiceError,
    ReadOnlyQueryService,
)

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorEnvelope},
    422: {"model": ErrorEnvelope},
    503: {"model": ErrorEnvelope},
}
_MAX_REQUEST_ID_LENGTH = 128


def _request_id(request: Request) -> str:
    supplied = request.headers.get("x-request-id", "").strip()
    if (
        supplied
        and len(supplied) <= _MAX_REQUEST_ID_LENGTH
        and supplied.isascii()
    ):
        return supplied
    return uuid4().hex


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
    details: tuple[ErrorDetail, ...] = (),
    retryable: bool = False,
) -> JSONResponse:
    request_id = _request_id(request)
    envelope = ErrorEnvelope(
        error=code,
        message=message,
        request_id=request_id,
        details=details,
        retryable=retryable,
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json"),
        headers={
            "cache-control": "no-store",
            "x-request-id": request_id,
        },
    )


def _validation_details(
    errors: Sequence[Mapping[str, Any]],
) -> tuple[ErrorDetail, ...]:
    return tuple(
        ErrorDetail(
            field=".".join(str(part) for part in error.get("loc", ())) or None,
            message=str(error.get("msg", "Invalid value")),
        )
        for error in errors
    )


def _query_or_error[QueryT](
    request: Request,
    factory: Callable[[], QueryT],
) -> QueryT | JSONResponse:
    try:
        return factory()
    except ValidationError as error:
        return _error_response(
            request,
            status_code=422,
            code=ErrorCode.INVALID_REQUEST,
            message="Request parameters are invalid",
            details=_validation_details(error.errors()),
        )


def _service_or_error[ResponseT](
    request: Request,
    operation: Callable[[], ResponseT],
) -> ResponseT | JSONResponse:
    try:
        return operation()
    except InvalidCursorError:
        return _error_response(
            request,
            status_code=400,
            code=ErrorCode.INVALID_CURSOR,
            message="The cursor is invalid for this query",
        )
    except QueryServiceError:
        return _error_response(
            request,
            status_code=503,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="The read-only query service is unavailable",
            retryable=True,
        )


def _cache_headers(response: Response) -> None:
    response.headers["cache-control"] = (
        "public, max-age=60, stale-while-revalidate=300"
    )
    response.headers["vary"] = "accept"


def create_app(service: ReadOnlyQueryService) -> FastAPI:
    """Create an API application with an explicitly injected query service."""

    app = FastAPI(
        title="Global Medicines Atlas API",
        version=PRODUCT_EVIDENCE_VERSION,
        description=(
            "Read-only evidence-backed regulatory, funding, and formulary "
            "comparisons. Absence is never interpreted as a negative status."
        ),
        docs_url=f"{API_BASE_PATH}/docs",
        openapi_url=f"{API_BASE_PATH}/openapi.json",
        redoc_url=None,
    )

    def request_validation_error(
        request: Request,
        error: Exception,
    ) -> JSONResponse:
        details = (
            _validation_details(error.errors())
            if isinstance(error, RequestValidationError)
            else ()
        )
        return _error_response(
            request,
            status_code=422,
            code=ErrorCode.INVALID_REQUEST,
            message="Request parameters are invalid",
            details=details,
        )

    app.add_exception_handler(
        RequestValidationError,
        request_validation_error,
    )

    @app.api_route(
        f"{API_BASE_PATH}/comparisons",
        methods=["GET"],
        response_model=ComparisonResponse,
        responses=_ERROR_RESPONSES,
        tags=["comparisons"],
        summary="Compare medicine status across jurisdictions",
    )
    def comparisons(
        request: Request,
        response: Response,
        concept_id: Annotated[str, Query(min_length=1, max_length=512)],
        jurisdictions: Annotated[
            list[str],
            Query(min_length=1, max_length=50),
        ],
        valid_at: Annotated[AwareDatetime, Query()],
        observed_at: Annotated[AwareDatetime, Query()],
        dimensions: Annotated[
            list[EvidenceDimension] | None,
            Query(),
        ] = None,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
        cursor: Annotated[
            str | None,
            Query(min_length=16, max_length=2048, pattern=r"^[A-Za-z0-9_-]+$"),
        ] = None,
    ) -> ComparisonResponse | JSONResponse:
        query = _query_or_error(
            request,
            lambda: ComparisonQuery(
                concept_id=concept_id,
                jurisdictions=tuple(jurisdictions),
                dimensions=tuple(
                    dimensions
                    or (
                        EvidenceDimension.REGULATORY,
                        EvidenceDimension.FUNDING,
                    )
                ),
                valid_at=valid_at,
                observed_at=observed_at,
                limit=limit,
                cursor=cursor,
            ),
        )
        if isinstance(query, JSONResponse):
            return query
        result = _service_or_error(
            request,
            lambda: service.comparisons(query),
        )
        if not isinstance(result, JSONResponse):
            _cache_headers(response)
        return result

    app.add_api_route(
        f"{API_BASE_PATH}/comparisons",
        comparisons,
        methods=["HEAD"],
        response_model=None,
        include_in_schema=False,
    )

    @app.api_route(
        f"{API_BASE_PATH}/coverage",
        methods=["GET"],
        response_model=CoverageResponse,
        responses=_ERROR_RESPONSES,
        tags=["coverage"],
        summary="Inspect explicit source coverage",
    )
    def coverage(
        request: Request,
        response: Response,
        jurisdictions: Annotated[
            list[str],
            Query(min_length=1, max_length=50),
        ],
        valid_at: Annotated[AwareDatetime, Query()],
        observed_at: Annotated[AwareDatetime, Query()],
        dimensions: Annotated[
            list[EvidenceDimension] | None,
            Query(),
        ] = None,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
        cursor: Annotated[
            str | None,
            Query(min_length=16, max_length=2048, pattern=r"^[A-Za-z0-9_-]+$"),
        ] = None,
    ) -> CoverageResponse | JSONResponse:
        query = _query_or_error(
            request,
            lambda: CoverageQuery(
                jurisdictions=tuple(jurisdictions),
                dimensions=tuple(dimensions or ()),
                valid_at=valid_at,
                observed_at=observed_at,
                limit=limit,
                cursor=cursor,
            ),
        )
        if isinstance(query, JSONResponse):
            return query
        result = _service_or_error(request, lambda: service.coverage(query))
        if not isinstance(result, JSONResponse):
            _cache_headers(response)
        return result

    app.add_api_route(
        f"{API_BASE_PATH}/coverage",
        coverage,
        methods=["HEAD"],
        response_model=None,
        include_in_schema=False,
    )

    @app.api_route(
        f"{API_BASE_PATH}/evidence",
        methods=["GET"],
        response_model=EvidenceResponse,
        responses=_ERROR_RESPONSES,
        tags=["evidence"],
        summary="Drill down from a conclusion to source evidence",
    )
    def evidence(
        request: Request,
        response: Response,
        valid_at: Annotated[AwareDatetime, Query()],
        observed_at: Annotated[AwareDatetime, Query()],
        assertion_id: Annotated[
            str | None,
            Query(min_length=1, max_length=512),
        ] = None,
        concept_id: Annotated[
            str | None,
            Query(min_length=1, max_length=512),
        ] = None,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
        cursor: Annotated[
            str | None,
            Query(min_length=16, max_length=2048, pattern=r"^[A-Za-z0-9_-]+$"),
        ] = None,
    ) -> EvidenceResponse | JSONResponse:
        query = _query_or_error(
            request,
            lambda: EvidenceQuery(
                assertion_id=assertion_id,
                concept_id=concept_id,
                valid_at=valid_at,
                observed_at=observed_at,
                limit=limit,
                cursor=cursor,
            ),
        )
        if isinstance(query, JSONResponse):
            return query
        result = _service_or_error(request, lambda: service.evidence(query))
        if not isinstance(result, JSONResponse):
            _cache_headers(response)
        return result

    app.add_api_route(
        f"{API_BASE_PATH}/evidence",
        evidence,
        methods=["HEAD"],
        response_model=None,
        include_in_schema=False,
    )

    def health_response() -> HealthResponse:
        return HealthResponse(
            state=HealthState.OK,
            checked_at=datetime.now(UTC),
            checks=(
                HealthCheck(name="api", state=HealthState.OK),
                HealthCheck(name="query-contract", state=HealthState.OK),
            ),
        )

    @app.api_route(
        f"{API_BASE_PATH}/health",
        methods=["GET"],
        response_model=HealthResponse,
        tags=["operations"],
        summary="Check API process health",
    )
    def health(response: Response) -> HealthResponse:
        response.headers["cache-control"] = "no-store"
        return health_response()

    app.add_api_route(
        f"{API_BASE_PATH}/health",
        health,
        methods=["HEAD"],
        response_model=None,
        include_in_schema=False,
    )

    @app.api_route(
        f"{API_BASE_PATH}/readiness",
        methods=["GET"],
        response_model=HealthResponse,
        responses={503: {"model": ErrorEnvelope}},
        tags=["operations"],
        summary="Check read-only service readiness",
    )
    def readiness(
        request: Request,
        response: Response,
    ) -> HealthResponse | JSONResponse:
        response.headers["cache-control"] = "no-store"
        unavailable = _service_or_error(request, service.readiness_probe)
        if isinstance(unavailable, JSONResponse):
            return unavailable
        return health_response()

    app.add_api_route(
        f"{API_BASE_PATH}/readiness",
        readiness,
        methods=["HEAD"],
        response_model=None,
        include_in_schema=False,
    )

    return app


__all__ = ["create_app"]
