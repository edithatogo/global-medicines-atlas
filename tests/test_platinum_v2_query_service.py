"""Source-backed controls for the additive five-dimension query adapter."""

from __future__ import annotations

from pathlib import Path

from test_query_service import (
    NOW,
    SECRET,
    _database,  # ruff: ignore[import-private-name]
)

from global_medicines_atlas.platinum_v2_contracts import (
    V2ComparisonQuery,
    V2EvidenceDimension,
)
from global_medicines_atlas.platinum_v2_query_service import (
    V2ReadOnlyQueryService,
)


def test_v2_query_service_preserves_v1_and_additive_dimensions(
    tmp_path: Path,
) -> None:
    service = V2ReadOnlyQueryService(
        _database(tmp_path / "atlas.duckdb"),
        cursor_secret=SECRET,
        allowed_root=tmp_path,
    )
    response = service.v2_comparisons(
        V2ComparisonQuery(
            concept_id="rx:1",
            jurisdictions=("NZ", "AU", "US"),
            dimensions=tuple(V2EvidenceDimension),
            valid_at=NOW,
            observed_at=NOW,
        )
    )
    values = {
        (item.jurisdiction, item.dimension.value): item
        for item in response.conclusions
    }

    assert values["NZ", "regulatory"].status_code == "approved"
    assert values["NZ", "funding"].status_code == "funded"
    assert values["AU", "funding"].status_code is None
    assert values["US", "regulatory"].status_code is None
    assert "service_benefit" not in {
        item.dimension.value for item in response.conclusions
    }
    assert "terminology" not in {
        item.dimension.value for item in response.conclusions
    }


def test_v2_query_service_omits_unknown_status_code(tmp_path: Path) -> None:
    service = V2ReadOnlyQueryService(
        _database(tmp_path / "atlas.duckdb"),
        cursor_secret=SECRET,
        allowed_root=tmp_path,
    )
    response = service.v2_comparisons(
        V2ComparisonQuery(
            concept_id="rx:1",
            jurisdictions=("US",),
            dimensions=(V2EvidenceDimension.REGULATORY,),
            valid_at=NOW,
            observed_at=NOW,
        )
    )

    assert response.conclusions[0].status_code is None
