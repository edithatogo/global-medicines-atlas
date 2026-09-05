from datetime import UTC, datetime

import pytest

from global_medicines_atlas.platinum_coverage import (
    CoverageEnvelope,
    build_coverage_envelope,
)
from global_medicines_atlas.product_contracts import (
    AsOfClocks,
    CoverageItem,
    CoverageResponse,
    EvidenceDimension,
    PageMetadata,
    ResponseMetadata,
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
