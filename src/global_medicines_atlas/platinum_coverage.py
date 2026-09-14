"""Read-only Platinum coverage envelope over temporal coverage results."""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Protocol, cast

from pydantic import AwareDatetime, Field, ValidationError, model_validator

from .platinum_query import QueryReceipt
from .platinum_surface_contracts import (
    DatasetIdentityEnvelope,
    PlatinumSurfaceModel,
    Sha256,
)
from .product_contracts import AsOfClocks, CoverageItem, CoverageResponse


class CoverageEnvelope(PlatinumSurfaceModel):
    """A bounded coverage page whose absence never means non-coverage."""

    schema_version: str = "1.0"
    generated_at: AwareDatetime
    clocks: AsOfClocks
    coverage: tuple[CoverageItem, ...]
    page_limit: int = Field(ge=1)
    next_cursor: str | None = None
    page_sha256: Sha256
    coverage_complete: bool = False
    missing_coverage_is_negative_evidence: bool = False
    temporal_selection: str = "valid_and_observed_half_open"


class CoverageLookup(Protocol):
    """Compatibility protocol for services that expose temporal coverage."""

    def coverage(self, query: object) -> CoverageResponse: ...


class FederatedCoverageEnvelope(CoverageEnvelope):
    """Coverage that is explicitly bound to one admitted dataset identity."""

    identity: DatasetIdentityEnvelope
    query_receipt_sha256: Sha256
    coverage_receipt_sha256: Sha256


class CoverageTransformationReceipt(PlatinumSurfaceModel):
    """Content-addressed evidence for transforming one exact query to coverage."""

    version: Literal["1.0"] = "1.0"
    identity: DatasetIdentityEnvelope
    query_receipt_sha256: Sha256
    query_result_sha256: Sha256
    coverage_page_sha256: Sha256
    receipt_sha256: Sha256

    @model_validator(mode="after")
    def digest_is_current(self) -> CoverageTransformationReceipt:
        if self.receipt_sha256 != _receipt_digest(
            self.identity,
            self.query_receipt_sha256,
            self.query_result_sha256,
            self.coverage_page_sha256,
        ):
            raise ValueError("coverage receipt digest does not match evidence")
        return self


def _digest(response: CoverageResponse) -> str:
    payload = {
        "generated_at": response.metadata.generated_at.isoformat(),
        "clocks": response.metadata.clocks.model_dump(mode="json"),
        "coverage": [
            item.model_dump(mode="json") for item in response.coverage
        ],
        "page": response.metadata.page.model_dump(mode="json"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _receipt_digest(
    identity: DatasetIdentityEnvelope,
    query_receipt_sha256: str,
    query_result_sha256: str,
    coverage_page_sha256: str,
) -> str:
    canonical = json.dumps(
        {
            "coverage_page_sha256": coverage_page_sha256,
            "identity": identity.model_dump(mode="json"),
            "query_receipt_sha256": query_receipt_sha256,
            "query_result_sha256": query_result_sha256,
            "version": "1.0",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_coverage_envelope(response: CoverageResponse) -> CoverageEnvelope:
    """Translate an existing temporal response without adding source claims."""
    if response.metadata.page.returned != len(response.coverage):
        raise ValueError("returned count must match coverage")
    return CoverageEnvelope(
        generated_at=response.metadata.generated_at,
        clocks=response.metadata.clocks,
        coverage=response.coverage,
        page_limit=response.metadata.page.limit,
        next_cursor=response.metadata.page.next_cursor,
        page_sha256=_digest(response),
    )


def _coverage_from_query_rows(rows: list[object]) -> tuple[CoverageItem, ...]:
    """Derive the exact coverage page from canonical, receipted query rows."""
    try:
        return tuple(CoverageItem.model_validate(row) for row in rows)
    except ValidationError as error:
        raise ValueError(
            "query result cannot be transformed into coverage"
        ) from error


def coverage_transformation_receipt(
    response: CoverageResponse,
    identity: DatasetIdentityEnvelope,
    query_receipt: QueryReceipt,
    canonical_query_result: bytes,
) -> CoverageTransformationReceipt:
    """Record the trusted transformation from an exact query into coverage."""
    if (
        query_receipt.resource_id != identity.resource_id
        or query_receipt.object_sha256 != identity.object_sha256
        or query_receipt.contract_sha256 != identity.contract_sha256
        or query_receipt.semantic_manifest_sha256
        != identity.semantic_manifest_sha256
    ):
        raise ValueError("query receipt differs from resource identity")
    if hashlib.sha256(query_receipt.canonical_query).hexdigest() != (
        query_receipt.query_sha256
    ):
        raise ValueError("query receipt query digest is invalid")
    if hashlib.sha256(canonical_query_result).hexdigest() != (
        query_receipt.result_sha256
    ):
        raise ValueError("query receipt differs from query result")
    try:
        parsed_rows: object = json.loads(canonical_query_result)
    except (TypeError, ValueError) as error:
        raise ValueError("query result is not canonical JSON") from error
    if not isinstance(parsed_rows, list):
        raise TypeError("query result must be a JSON array")
    result_rows = cast("list[object]", parsed_rows)
    if len(result_rows) != query_receipt.row_count:
        raise ValueError("query receipt row count differs from query result")
    canonical_rows = json.dumps(
        result_rows,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if canonical_rows != canonical_query_result:
        raise ValueError("query result is not canonical JSON")
    derived_coverage = _coverage_from_query_rows(result_rows)
    if derived_coverage != response.coverage:
        raise ValueError("coverage differs from receipted query result")
    envelope = build_coverage_envelope(response)
    digest = _receipt_digest(
        identity,
        query_receipt.receipt_sha256,
        query_receipt.result_sha256,
        envelope.page_sha256,
    )
    return CoverageTransformationReceipt(
        identity=identity,
        query_receipt_sha256=query_receipt.receipt_sha256,
        query_result_sha256=query_receipt.result_sha256,
        coverage_page_sha256=envelope.page_sha256,
        receipt_sha256=digest,
    )


def bind_federated_coverage(
    response: CoverageResponse,
    receipt: CoverageTransformationReceipt,
) -> FederatedCoverageEnvelope:
    """Expose coverage only when its transformation receipt matches exactly."""
    receipt = CoverageTransformationReceipt.model_validate(
        receipt.model_dump(warnings=False)
    )
    envelope = build_coverage_envelope(response)
    if receipt.coverage_page_sha256 != envelope.page_sha256:
        raise ValueError("coverage receipt differs from coverage payload")
    for item in envelope.coverage:
        if item.jurisdiction != receipt.identity.jurisdiction:
            raise ValueError(
                "coverage jurisdiction differs from resource identity"
            )
        if item.dimension.value != receipt.identity.semantic_dimension:
            raise ValueError(
                "coverage dimension differs from resource identity"
            )
        if item.provenance and any(
            link.source_id != receipt.identity.source_id
            for link in item.provenance
        ):
            raise ValueError(
                "coverage provenance differs from resource identity"
            )
    return FederatedCoverageEnvelope(
        **envelope.model_dump(),
        identity=receipt.identity,
        query_receipt_sha256=receipt.query_receipt_sha256,
        coverage_receipt_sha256=receipt.receipt_sha256,
    )


__all__ = [
    "CoverageEnvelope",
    "CoverageLookup",
    "CoverageTransformationReceipt",
    "FederatedCoverageEnvelope",
    "bind_federated_coverage",
    "build_coverage_envelope",
    "coverage_transformation_receipt",
]
