import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from global_medicines_atlas.platinum_coverage import (
    CoverageEnvelope,
    CoverageLookup,
    CoverageTransformationReceipt,
    bind_federated_coverage,
    build_coverage_envelope,
    coverage_transformation_receipt,
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
    return DatasetIdentityEnvelope(
        resource_id="au-pbs-current",
        dataset="example/pbs",
        revision="1" * 40,
        path="coverage.parquet",
        object_sha256="a" * 64,
        byte_count=1,
        contract_sha256="b" * 64,
        semantic_manifest_sha256="c" * 64,
        jurisdiction="AU",
        semantic_dimension="funding",
        entity_granularity="coverage_record",
        source_id="au-pbs",
        acquisition_id="pbs-receipt-current",
        layer="gold",
        schema_era="2026",
        comparison_cohort="current",
        effective_date="2026-01-01",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        cache_expires_at=datetime(2027, 1, 1, tzinfo=UTC),
        capabilities=("exact_v4_resolution",),
        coverage_state="not_declared",
        comparison_validity="not_evaluated",
        product_admitted=True,
        rows_queried=False,
    )


def _receipt(response: CoverageResponse | None = None) -> QueryReceipt:
    result = _canonical_query_result(response)
    return QueryReceipt(
        resource_id="au-pbs-current",
        engine="polars",
        canonical_query=b"{}",
        query_sha256=hashlib.sha256(b"{}").hexdigest(),
        result_sha256=hashlib.sha256(result).hexdigest(),
        row_count=1,
        object_sha256="a" * 64,
        contract_sha256="b" * 64,
        semantic_manifest_sha256="c" * 64,
        cache_receipt_sha256="f" * 64,
    )


def _canonical_query_result(response: CoverageResponse | None = None) -> bytes:
    response = _response() if response is None else response
    return json.dumps(
        [item.model_dump(mode="json") for item in response.coverage],
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


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


def test_coverage_lookup_remains_a_public_compatibility_protocol() -> None:
    class Lookup:
        def coverage(self, query: object) -> CoverageResponse:
            assert query == "coverage-query"
            return _response()

    lookup: CoverageLookup = Lookup()
    assert lookup.coverage("coverage-query") == _response()


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
    receipt = _receipt()
    transformation = coverage_transformation_receipt(
        response, _identity(), receipt, _canonical_query_result()
    )
    bound = bind_federated_coverage(response, transformation)
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
            wrong_jurisdiction,
            coverage_transformation_receipt(
                wrong_jurisdiction,
                _identity(),
                _receipt(wrong_jurisdiction),
                _canonical_query_result(wrong_jurisdiction),
            ),
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
            linked,
            coverage_transformation_receipt(
                linked,
                _identity(),
                _receipt(linked),
                _canonical_query_result(linked),
            ),
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
            wrong_source,
            coverage_transformation_receipt(
                wrong_source,
                _identity(),
                _receipt(wrong_source),
                _canonical_query_result(wrong_source),
            ),
        )


def test_federated_binding_rejects_a_receipt_for_another_resource() -> None:
    response = _response()
    receipt = _receipt()
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
        coverage_transformation_receipt(
            response, _identity(), mismatched, _canonical_query_result()
        )


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
        bind_federated_coverage(
            changed,
            coverage_transformation_receipt(
                response, _identity(), _receipt(), _canonical_query_result()
            ),
        )


def test_federated_binding_revalidates_the_receipt_digest() -> None:
    response = _response()
    receipt = coverage_transformation_receipt(
        response, _identity(), _receipt(), _canonical_query_result()
    )
    tampered = receipt.model_construct(
        **(receipt.model_dump() | {"receipt_sha256": "0" * 64})
    )
    with pytest.raises(ValueError, match="receipt digest"):
        bind_federated_coverage(response, tampered)


def test_federated_binding_rejects_mismatched_coverage_dimension() -> None:
    response = _response()
    regulatory = response.model_copy(
        update={
            "coverage": (
                response.coverage[0].model_copy(
                    update={"dimension": EvidenceDimension.REGULATORY}
                ),
            )
        }
    )
    receipt = coverage_transformation_receipt(
        regulatory,
        _identity(),
        _receipt(regulatory),
        _canonical_query_result(regulatory),
    )
    with pytest.raises(ValueError, match="coverage dimension"):
        bind_federated_coverage(regulatory, receipt)


def test_coverage_transformation_receipt_rejects_unsupported_version() -> None:
    receipt = coverage_transformation_receipt(
        _response(), _identity(), _receipt(), _canonical_query_result()
    )
    with pytest.raises(ValueError, match="version"):
        CoverageTransformationReceipt(
            **(receipt.model_dump() | {"version": "2.0"})
        )


def test_coverage_transformation_receipt_rejects_unreceipted_query_result() -> (
    None
):
    with pytest.raises(ValueError, match="query result"):
        coverage_transformation_receipt(
            _response(), _identity(), _receipt(), b'[{"item_code":"PBS-002"}]'
        )


def test_coverage_transformation_receipt_derives_coverage_from_receipted_rows() -> (
    None
):
    response = _response()
    unrelated = response.model_copy(
        update={
            "coverage": (
                response.coverage[0].model_copy(update={"covered_count": 1}),
            )
        }
    )
    with pytest.raises(ValueError, match="coverage differs"):
        coverage_transformation_receipt(
            unrelated,
            _identity(),
            _receipt(response),
            _canonical_query_result(response),
        )


def test_coverage_transformation_receipt_rejects_rows_without_coverage_shape() -> (
    None
):
    raw_result = b'[{"item_code":"PBS-001"}]'
    receipt = replace(
        _receipt(), result_sha256=hashlib.sha256(raw_result).hexdigest()
    )
    with pytest.raises(ValueError, match="cannot be transformed"):
        coverage_transformation_receipt(
            _response(), _identity(), receipt, raw_result
        )


def test_coverage_transformation_receipt_rejects_invalid_query_digest() -> None:
    with pytest.raises(ValueError, match="query digest"):
        coverage_transformation_receipt(
            _response(),
            _identity(),
            replace(_receipt(), query_sha256="0" * 64),
            _canonical_query_result(),
        )


@pytest.mark.parametrize(
    ("raw_result", "error_type", "message"),
    [
        (b"not-json", ValueError, "canonical JSON"),
        (b'{"item_code":"PBS-001"}', TypeError, "JSON array"),
        (
            b'[{"item_code":"PBS-001"},{"item_code":"PBS-002"}]',
            ValueError,
            "row count",
        ),
        (b'[ { "item_code": "PBS-001" } ]', ValueError, "canonical JSON"),
    ],
)
def test_coverage_transformation_receipt_rejects_invalid_result_shape(
    raw_result: bytes,
    error_type: type[Exception],
    message: str,
) -> None:
    receipt = replace(
        _receipt(), result_sha256=hashlib.sha256(raw_result).hexdigest()
    )
    with pytest.raises(error_type, match=message):
        coverage_transformation_receipt(
            _response(), _identity(), receipt, raw_result
        )


def test_coverage_receipt_binds_generated_time() -> None:
    response = _response()
    changed_time = response.model_copy(
        update={
            "metadata": response.metadata.model_copy(
                update={"generated_at": datetime(2026, 1, 2, tzinfo=UTC)}
            )
        }
    )
    receipt = coverage_transformation_receipt(
        response, _identity(), _receipt(), _canonical_query_result()
    )
    with pytest.raises(ValueError, match="coverage payload"):
        bind_federated_coverage(changed_time, receipt)
