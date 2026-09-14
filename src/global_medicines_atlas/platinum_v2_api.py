"""Separate read-only FastAPI transport for additive V2 comparisons."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Annotated, Any, Protocol
from uuid import uuid4

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import AwareDatetime, ValidationError

from .platinum_v2_contracts import (
    V2_API_BASE_PATH,
    V2_API_VERSION,
    V2ComparisonQuery,
    V2ComparisonResponse,
    V2EvidenceDimension,
    V2EvidenceQuery,
    V2EvidenceResponse,
)
from .product_contracts import (
    MAX_PAGE_SIZE,
    ErrorCode,
    ErrorDetail,
    ProductModel,
)
from .query_service import InvalidCursorError, QueryServiceError

_MAX_REQUEST_ID_LENGTH = 128


class V2ErrorEnvelope(ProductModel):
    """Versioned, non-leaking error body for the independent V2 transport."""

    api_version: str = V2_API_VERSION
    error: ErrorCode
    message: str
    request_id: str
    details: tuple[ErrorDetail, ...] = ()
    retryable: bool = False


class V2ComparisonService(Protocol):
    """Minimal dependency required by the V2 read-only transport."""

    def v2_comparisons(
        self, query: V2ComparisonQuery
    ) -> V2ComparisonResponse: ...

    def v2_evidence(self, query: V2EvidenceQuery) -> V2EvidenceResponse: ...


_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": V2ErrorEnvelope},
    422: {"model": V2ErrorEnvelope},
    503: {"model": V2ErrorEnvelope},
}


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
    envelope = V2ErrorEnvelope(
        error=code,
        message=message,
        request_id=request_id,
        details=details,
        retryable=retryable,
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json"),
        headers={"cache-control": "no-store", "x-request-id": request_id},
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
    request: Request, factory: Callable[[], QueryT]
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
    request: Request, operation: Callable[[], ResponseT]
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
            message="The read-only V2 query service is unavailable",
            retryable=True,
        )


def _cache_headers(response: Response) -> None:
    response.headers["cache-control"] = (
        "public, max-age=60, stale-while-revalidate=300"
    )
    response.headers["vary"] = "accept"


def create_v2_app(service: V2ComparisonService) -> FastAPI:
    """Create an isolated additive V2 API without changing the V1 schema."""

    app = FastAPI(
        title="Global Medicines Atlas V2 API",
        version=V2_API_VERSION,
        description=(
            "Read-only evidence-backed comparison across five independent "
            "dimensions. Absence is never interpreted as a negative status."
        ),
        docs_url=f"{V2_API_BASE_PATH}/docs",
        openapi_url=f"{V2_API_BASE_PATH}/openapi.json",
        redoc_url=None,
    )

    def request_validation_error(
        request: Request, error: Exception
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

    app.add_exception_handler(RequestValidationError, request_validation_error)

    @app.api_route(
        f"{V2_API_BASE_PATH}/comparisons",
        methods=["GET"],
        response_model=V2ComparisonResponse,
        responses=_ERROR_RESPONSES,
        tags=["comparisons"],
        summary="Compare five independent evidence dimensions",
    )
    def comparisons(
        request: Request,
        response: Response,
        concept_id: Annotated[str, Query(min_length=1, max_length=512)],
        jurisdictions: Annotated[list[str], Query(min_length=1, max_length=50)],
        dimensions: Annotated[
            list[V2EvidenceDimension], Query(min_length=1, max_length=5)
        ],
        valid_at: Annotated[AwareDatetime, Query()],
        observed_at: Annotated[AwareDatetime, Query()],
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
        cursor: Annotated[
            str | None,
            Query(min_length=16, max_length=2048, pattern=r"^[A-Za-z0-9_-]+$"),
        ] = None,
    ) -> V2ComparisonResponse | JSONResponse:
        query = _query_or_error(
            request,
            lambda: V2ComparisonQuery(
                concept_id=concept_id,
                jurisdictions=tuple(jurisdictions),
                dimensions=tuple(dimensions),
                valid_at=valid_at,
                observed_at=observed_at,
                limit=limit,
                cursor=cursor,
            ),
        )
        if isinstance(query, JSONResponse):
            return query
        result = _service_or_error(
            request, lambda: service.v2_comparisons(query)
        )
        if not isinstance(result, JSONResponse):
            _cache_headers(response)
        return result

    app.add_api_route(
        f"{V2_API_BASE_PATH}/comparisons",
        comparisons,
        methods=["HEAD"],
        response_model=None,
        include_in_schema=False,
    )

    @app.api_route(
        f"{V2_API_BASE_PATH}/evidence",
        methods=["GET"],
        response_model=V2EvidenceResponse,
        responses=_ERROR_RESPONSES,
        tags=["evidence"],
        summary="Page complete source evidence for one V2 dimension",
    )
    def evidence(
        request: Request,
        response: Response,
        concept_id: Annotated[str, Query(min_length=1, max_length=512)],
        jurisdiction: Annotated[str, Query(min_length=2, max_length=3)],
        dimension: Annotated[V2EvidenceDimension, Query()],
        valid_at: Annotated[AwareDatetime, Query()],
        observed_at: Annotated[AwareDatetime, Query()],
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
        cursor: Annotated[
            str | None,
            Query(min_length=16, max_length=2048, pattern=r"^[A-Za-z0-9_-]+$"),
        ] = None,
    ) -> V2EvidenceResponse | JSONResponse:
        query = _query_or_error(
            request,
            lambda: V2EvidenceQuery(
                concept_id=concept_id,
                jurisdiction=jurisdiction,
                dimension=dimension,
                valid_at=valid_at,
                observed_at=observed_at,
                limit=limit,
                cursor=cursor,
            ),
        )
        if isinstance(query, JSONResponse):
            return query
        result = _service_or_error(request, lambda: service.v2_evidence(query))
        if not isinstance(result, JSONResponse):
            _cache_headers(response)
        return result

    app.add_api_route(
        f"{V2_API_BASE_PATH}/evidence",
        evidence,
        methods=["HEAD"],
        response_model=None,
        include_in_schema=False,
    )
    return app


__all__ = ["V2ComparisonService", "V2ErrorEnvelope", "create_v2_app"]
