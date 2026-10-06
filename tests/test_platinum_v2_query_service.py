"""Source-backed controls for the additive five-dimension query adapter."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from test_query_service import (
    NOW,
    SECRET,
    _database,  # ruff: ignore[import-private-name]
)

import global_medicines_atlas.platinum_v2_query_service as v2_query_service
from global_medicines_atlas.platinum_v2_contracts import (
    V2ComparisonQuery,
    V2EvidenceDimension,
    V2EvidenceQuery,
)
from global_medicines_atlas.platinum_v2_query_service import (
    V2ReadOnlyQueryService,
)
from global_medicines_atlas.query_service import InvalidCursorError


def _add_service_benefit_assertions(database: Path) -> None:
    """Create more rows than the comparison provenance cap."""
    rows = [
        (
            f"a-nz-service-{index:02d}",
            "rx:1",
            "NZ",
            "service_benefit",
            "NZ service register",
            "eligible",
            "confirmed",
            [],
            NOW,
            None,
            NOW,
            None,
            None,
            None,
            "nz-service-register",
            f"https://example.test/nz/service/{index}",
            NOW,
            None,
            None,
            "b" * 64,
            "2026-09",
            "nz-service-adapter-v1",
        )
        for index in range(33)
    ]
    connection = duckdb.connect(str(database))
    connection.executemany(
        """
        INSERT INTO temporal_assertions VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        rows,
    )
    connection.close()


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
    assert values["NZ", "regulatory"].evidence_context.comparison_cohort == (
        "unknown"
    )
    assert values["NZ", "funding"].status_code == "funded"
    assert values["AU", "funding"].status_code is None
    assert values["US", "regulatory"].status_code is None
    assert {item.dimension for item in response.conclusions} == set(
        V2EvidenceDimension
    )
    assert values["NZ", "service_benefit"].state.value == "unknown"
    assert values["NZ", "service_benefit"].evidence_availability.value == (
        "unavailable"
    )


def test_v2_comparisons_report_pairwise_validity_for_complete_pages(
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
            dimensions=(
                V2EvidenceDimension.REGULATORY,
                V2EvidenceDimension.FUNDING,
            ),
            valid_at=NOW,
            observed_at=NOW,
            limit=50,
        )
    )

    subjects = {
        f"{item.concept_id}:{item.jurisdiction}:{item.dimension.value}": item
        for item in response.conclusions
    }
    assert response.validity_completeness == "complete"
    assert len(response.comparison_validity) == 6
    for item in response.comparison_validity:
        assert item.outcome.value == "insufficient_evidence"
        assert (
            item.left_evidence_context
            == subjects[item.left_subject_id].evidence_context
        )
        assert (
            item.right_evidence_context
            == subjects[item.right_subject_id].evidence_context
        )


def test_v2_comparison_validity_exposes_page_truncation(
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
            limit=7,
        )
    )

    assert response.validity_completeness == "partial"
    subjects = {
        f"{item.concept_id}:{item.jurisdiction}:{item.dimension.value}"
        for item in response.conclusions
    }
    assert all(
        item.left_subject_id in subjects and item.right_subject_id in subjects
        for item in response.comparison_validity
    )


def test_v2_single_jurisdiction_has_no_pairwise_validity(
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
            jurisdictions=("NZ",),
            dimensions=(V2EvidenceDimension.REGULATORY,),
            valid_at=NOW,
            observed_at=NOW,
        )
    )

    assert response.validity_completeness == "not_applicable"
    assert response.comparison_validity == ()


def test_v2_validity_skips_same_jurisdiction_pairs(tmp_path: Path) -> None:
    service = V2ReadOnlyQueryService(
        _database(tmp_path / "atlas.duckdb"),
        cursor_secret=SECRET,
        allowed_root=tmp_path,
    )
    response = service.v2_comparisons(
        V2ComparisonQuery(
            concept_id="rx:1",
            jurisdictions=("NZ",),
            dimensions=(V2EvidenceDimension.REGULATORY,),
            valid_at=NOW,
            observed_at=NOW,
        )
    )
    conclusion = response.conclusions[0]
    same_jurisdiction = conclusion.model_copy(update={"concept_id": "rx:other"})

    assert (
        v2_query_service._comparison_validity((conclusion, same_jurisdiction))
        == ()
    )


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


def test_v2_comparisons_pages_requested_unknown_dimensions(
    tmp_path: Path,
) -> None:
    service = V2ReadOnlyQueryService(
        _database(tmp_path / "atlas.duckdb"),
        cursor_secret=SECRET,
        allowed_root=tmp_path,
    )
    query = V2ComparisonQuery(
        concept_id="rx:1",
        jurisdictions=("NZ", "AU", "US"),
        dimensions=tuple(V2EvidenceDimension),
        valid_at=NOW,
        observed_at=NOW,
        limit=7,
    )

    first = service.v2_comparisons(query)
    assert len(first.conclusions) == 7
    assert first.metadata.page.next_cursor is not None
    second = service.v2_comparisons(
        query.model_copy(update={"cursor": first.metadata.page.next_cursor})
    )
    assert len(second.conclusions) == 7
    assert second.metadata.page.next_cursor is not None
    third = service.v2_comparisons(
        query.model_copy(update={"cursor": second.metadata.page.next_cursor})
    )
    assert len(third.conclusions) == 1
    assert third.metadata.page.next_cursor is None
    assert (
        len({
            (item.jurisdiction, item.dimension)
            for item in (
                *first.conclusions,
                *second.conclusions,
                *third.conclusions,
            )
        })
        == 15
    )


def test_v2_evidence_pages_complete_overflowing_v2_dimension(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path / "atlas.duckdb")
    _add_service_benefit_assertions(database)
    service = V2ReadOnlyQueryService(
        database,
        cursor_secret=SECRET,
        allowed_root=tmp_path,
    )
    comparison = service.v2_comparisons(
        V2ComparisonQuery(
            concept_id="rx:1",
            jurisdictions=("NZ",),
            dimensions=(V2EvidenceDimension.SERVICE_BENEFIT,),
            valid_at=NOW,
            observed_at=NOW,
        )
    )
    conclusion = comparison.conclusions[0]
    assert conclusion.state.value == "confirmed"
    assert len(conclusion.provenance) == 32
    assert conclusion.uncertainty.reason == (
        "Comparison provenance is capped; use V2 evidence paging."
    )

    first = service.v2_evidence(
        V2EvidenceQuery(
            concept_id="rx:1",
            jurisdiction="NZ",
            dimension=V2EvidenceDimension.SERVICE_BENEFIT,
            valid_at=NOW,
            observed_at=NOW,
            limit=20,
        )
    )
    assert len(first.evidence) == 20
    assert first.metadata.page.next_cursor is not None
    second = service.v2_evidence(
        V2EvidenceQuery(
            concept_id="rx:1",
            jurisdiction="NZ",
            dimension=V2EvidenceDimension.SERVICE_BENEFIT,
            valid_at=NOW,
            observed_at=NOW,
            limit=20,
            cursor=first.metadata.page.next_cursor,
        )
    )
    assert len(second.evidence) == 13
    assert second.metadata.page.next_cursor is None
    assert all(
        item.evidence_context.schema_era is None
        and item.evidence_context.comparison_cohort == "unknown"
        and item.evidence_context.entity_granularity == "unknown"
        and item.evidence_context.review_state == "not_reported"
        for item in (*first.evidence, *second.evidence)
    )
    assert {
        item.assertion_id for item in (*first.evidence, *second.evidence)
    } == {f"a-nz-service-{index:02d}" for index in range(33)}
    with pytest.raises(InvalidCursorError):
        service.v2_evidence(
            V2EvidenceQuery(
                concept_id="rx:1",
                jurisdiction="NZ",
                dimension=V2EvidenceDimension.TERMINOLOGY,
                valid_at=NOW,
                observed_at=NOW,
                cursor=first.metadata.page.next_cursor,
            )
        )
