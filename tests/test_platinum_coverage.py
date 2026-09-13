from datetime import UTC, datetime

import pytest

from global_medicines_atlas.platinum_coverage import (
    CoverageEnvelope,
    bind_federated_coverage,
    build_coverage_envelope,
)
from global_medicines_atlas.platinum_query import QueryReceipt
from global_medicines_atlas.platinum_surface_contracts import (
    DatasetIdentityEnvelope,
)
from global_medicines_atlas.product_contracts import (
    AsOfClocks,
    CoverageItem,
    CoverageResponse,
    EvidenceDimension,
    PageMetadata,
    ProvenanceLink,
    ResponseMetadata,
)


def _identity() -> DatasetIdentityEnvelope:
    return DatasetIdentityEnvelope.model_construct(
        resource_id="au-pbs-current",
        object_sha256="a" * 64,
        contract_sha256="b" * 64,
        semantic_manifest_sha256="c" * 64,
        jurisdiction="AU",
        source_id="au-pbs",
    )


def _receipt(response: CoverageResponse) -> QueryReceipt:
    return QueryReceipt(
        resource_id="au-pbs-current",
        engine="polars",
        canonical_query=b"{}",
        query_sha256="d" * 64,
        result_sha256=build_coverage_envelope(response).page_sha256,
        row_count=1,
        object_sha256="a" * 64,
        contract_sha256="b" * 64,
        semantic_manifest_sha256="c" * 64,
        cache_receipt_sha256="f" * 64,
    )


def _response() -> CoverageResponse:
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    return CoverageResponse(
        metadata=ResponseMetadata(
            generated_at=clock,
            clocks=AsOfClocks(valid_at=clock, observed_at=clock),
            page=PageMetadata(limit=10, returned=1),
        ),
        coverage=(
            CoverageItem(
                jurisdiction="AU",
                dimension=EvidenceDimension.FUNDING,
                state="unknown",
                covered_count=0,
                denominator=None,
                valid_time=AsOfClocks(valid_at=clock, observed_at=clock),
            ),
        ),
    )


def test_envelope_preserves_unknown_and_undeclared_coverage() -> None:
    result = build_coverage_envelope(_response())
    assert isinstance(result, CoverageEnvelope)
    assert result.coverage_complete is False
    assert result.missing_coverage_is_negative_evidence is False
    assert result.coverage[0].state == "unknown"
    assert result.coverage[0].denominator is None
    assert result.page_sha256 == result.page_sha256


def test_envelope_rejects_page_count_mismatch() -> None:
    response = _response()
    response = response.model_construct(
        metadata=response.metadata.model_copy(
            update={
                "page": response.metadata.page.model_construct(
                    limit=10, returned=2, next_cursor=None
                )
            }
        ),
        coverage=response.coverage,
    )
    with pytest.raises(ValueError, match="returned count"):
        build_coverage_envelope(response)


def test_envelope_digest_binds_coverage_payload() -> None:
    original = build_coverage_envelope(_response())
    changed = _response().model_copy(
        update={
            "coverage": (
                _response().coverage[0].model_copy(update={"covered_count": 1}),
            )
        }
    )
    revised = build_coverage_envelope(changed)
    assert revised.page_sha256 != original.page_sha256


def test_federated_binding_requires_exact_receipt_and_jurisdiction() -> None:
    response = _response()
    receipt = _receipt(response)
    bound = bind_federated_coverage(response, _identity(), receipt)
    assert bound.query_receipt_sha256 == receipt.receipt_sha256
    wrong_jurisdiction = response.model_copy(
        update={
            "coverage": (
                response.coverage[0].model_copy(update={"jurisdiction": "NZ"}),
            )
        }
    )
    with pytest.raises(ValueError, match="jurisdiction"):
        bind_federated_coverage(
            wrong_jurisdiction, _identity(), _receipt(wrong_jurisdiction)
        )
    linked = response.model_copy(
        update={
            "coverage": (
                response.coverage[0].model_copy(
                    update={
                        "provenance": (
                            ProvenanceLink(
                                source_id="au-pbs",
                                source_uri="https://example.test/pbs",
                                retrieved_at=response.metadata.generated_at,
                            ),
                        )
                    }
                ),
            )
        }
    )
    assert (
        bind_federated_coverage(
            linked, _identity(), _receipt(linked)
        ).identity.source_id
        == "au-pbs"
    )
    wrong_source = linked.model_copy(
        update={
            "coverage": (
                linked.coverage[0].model_copy(
                    update={
                        "provenance": (
                            ProvenanceLink(
                                source_id="nz-pharmac",
                                source_uri="https://example.test/pharmac",
                                retrieved_at=linked.metadata.generated_at,
                            ),
                        )
                    }
                ),
            )
        }
    )
    with pytest.raises(ValueError, match="provenance"):
        bind_federated_coverage(
            wrong_source, _identity(), _receipt(wrong_source)
        )


def test_federated_binding_rejects_a_receipt_for_another_resource() -> None:
    response = _response()
    receipt = _receipt(response)
    mismatched = QueryReceipt(
        resource_id="au-pbs-historical",
        engine=receipt.engine,
        canonical_query=receipt.canonical_query,
        query_sha256=receipt.query_sha256,
        result_sha256=receipt.result_sha256,
        row_count=receipt.row_count,
        object_sha256=receipt.object_sha256,
        contract_sha256=receipt.contract_sha256,
        semantic_manifest_sha256=receipt.semantic_manifest_sha256,
        cache_receipt_sha256=receipt.cache_receipt_sha256,
    )
    with pytest.raises(ValueError, match="query receipt"):
        bind_federated_coverage(response, _identity(), mismatched)


def test_federated_binding_rejects_a_receipt_for_another_payload() -> None:
    response = _response()
    changed = response.model_copy(
        update={
            "coverage": (
                response.coverage[0].model_copy(update={"covered_count": 1}),
            )
        }
    )
    with pytest.raises(ValueError, match="coverage payload"):
        bind_federated_coverage(changed, _identity(), _receipt(response))
