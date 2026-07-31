"""Focused contract and abuse tests for the read-only product query service."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from global_medicines_atlas.product_contracts import (
    ComparisonQuery,
    CoverageQuery,
    EvidenceDimension,
    EvidenceQuery,
    ProductState,
)
from global_medicines_atlas.query_service import (
    InvalidCursorError,
    InvalidDatabaseError,
    QueryServiceError,
    ReadOnlyQueryService,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)
SECRET = b"query-service-test-secret"


def _database(path: Path) -> Path:
    connection = duckdb.connect(str(path))
    connection.execute(
        """
        CREATE TABLE temporal_assertions (
            assertion_id VARCHAR NOT NULL,
            concept_id VARCHAR NOT NULL,
            jurisdiction VARCHAR NOT NULL,
            kind VARCHAR NOT NULL,
            authority VARCHAR NOT NULL,
            status_code VARCHAR NOT NULL,
            evidence_status VARCHAR NOT NULL,
            restrictions VARCHAR[] NOT NULL,
            valid_from TIMESTAMPTZ NOT NULL,
            valid_to TIMESTAMPTZ,
            observed_from TIMESTAMPTZ NOT NULL,
            observed_to TIMESTAMPTZ,
            supersedes_assertion_id VARCHAR,
            conflict_id VARCHAR,
            source_id VARCHAR NOT NULL,
            source_uri VARCHAR NOT NULL,
            retrieved_at TIMESTAMPTZ,
            source_effective_at TIMESTAMPTZ,
            source_path VARCHAR,
            source_sha256 VARCHAR,
            source_version VARCHAR,
            transformation VARCHAR
        );
        CREATE TABLE temporal_coverage (
            jurisdiction VARCHAR NOT NULL,
            source_id VARCHAR NOT NULL,
            receipt_id VARCHAR NOT NULL,
            observation_id VARCHAR NOT NULL,
            population_partition_id VARCHAR NOT NULL,
            dimension VARCHAR NOT NULL,
            medicine_concept_id VARCHAR,
            assertion_type VARCHAR NOT NULL,
            assertion_status VARCHAR NOT NULL,
            concept_population VARCHAR NOT NULL,
            valid_from TIMESTAMPTZ NOT NULL,
            valid_to TIMESTAMPTZ,
            observed_from TIMESTAMPTZ NOT NULL,
            observed_to TIMESTAMPTZ,
            assertion_count BIGINT NOT NULL,
            concept_numerator BIGINT NOT NULL,
            eligible_denominator BIGINT,
            exclusion_count BIGINT NOT NULL,
            exclusion_reasons VARCHAR[] NOT NULL,
            conflicting_assertion_count BIGINT NOT NULL
        )
        """
    )
    assertions = [
        (
            "a-nz-reg",
            "rx:1",
            "NZ",
            "regulatory",
            "Medsafe",
            "approved",
            "confirmed",
            [],
            NOW,
            None,
            NOW,
            None,
            None,
            None,
            "medsafe",
            "https://example.test/medsafe/1",
            NOW,
            None,
            None,
            "a" * 64,
            "2026-07",
            "nz-adapter-v1",
        ),
        (
            "a-nz-fund",
            "rx:1",
            "NZ",
            "funding",
            "Pharmac",
            "funded",
            "confirmed",
            [],
            NOW,
            None,
            NOW,
            None,
            None,
            None,
            "pharmac",
            "https://example.test/pharmac/1",
            NOW,
            None,
            None,
            None,
            "2026-07",
            "nz-adapter-v1",
        ),
        (
            "a-au-reg",
            "rx:1",
            "AU",
            "regulatory",
            "TGA",
            "registered",
            "confirmed",
            [],
            NOW,
            None,
            NOW,
            None,
            None,
            None,
            "artg",
            "https://example.test/artg/1",
            NOW,
            None,
            None,
            None,
            "2026-07",
            "au-adapter-v1",
        ),
    ]
    connection.executemany(
        """
        INSERT INTO temporal_assertions VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        assertions,
    )
    coverage = [
        (
            "AU",
            "pbs",
            "receipt-au",
            "obs-au-funding",
            "all",
            "funding",
            "rx:1",
            "medicine",
            "not_covered",
            "all listed medicines",
            NOW,
            None,
            NOW,
            None,
            0,
            0,
            100,
            0,
            [],
            0,
        ),
        (
            "US",
            "fda",
            "receipt-us",
            "obs-us-reg",
            "all",
            "regulatory",
            "rx:1",
            "medicine",
            "unknown",
            "all observed medicines",
            NOW,
            None,
            NOW,
            None,
            0,
            0,
            None,
            0,
            [],
            0,
        ),
    ]
    connection.executemany(
        """
        INSERT INTO temporal_coverage VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        coverage,
    )
    connection.close()
    return path


@pytest.fixture
def service(tmp_path: Path) -> ReadOnlyQueryService:
    database = _database(tmp_path / "atlas.duckdb")
    return ReadOnlyQueryService(
        database, cursor_secret=SECRET, allowed_root=tmp_path
    )


def _comparison(
    *,
    jurisdictions: tuple[str, ...] = ("NZ", "AU", "US"),
    limit: int = 50,
    cursor: str | None = None,
    concept_id: str = "rx:1",
) -> ComparisonQuery:
    return ComparisonQuery(
        concept_id=concept_id,
        jurisdictions=jurisdictions,
        dimensions=(
            EvidenceDimension.REGULATORY,
            EvidenceDimension.FUNDING,
        ),
        valid_at=NOW,
        observed_at=NOW,
        limit=limit,
        cursor=cursor,
    )


def test_comparisons_preserve_dimensions_and_explicit_absent_states(
    service: ReadOnlyQueryService,
) -> None:
    response = service.comparisons(_comparison())
    values = {
        (item.jurisdiction, item.dimension.value): item
        for item in response.conclusions
    }

    assert values["NZ", "regulatory"].status_code == "approved"
    assert values["NZ", "funding"].status_code == "funded"
    assert values["AU", "funding"].state is ProductState.NOT_COVERED
    assert values["AU", "funding"].status_code is None
    assert values["US", "regulatory"].state is ProductState.UNKNOWN
    assert ("US", "funding") not in values
    assert values["NZ", "regulatory"].terminology.native_system == "Medsafe"
    assert values["NZ", "regulatory"].provenance[0].source_sha256 == "a" * 64
    assert response.validity
    assert all(
        item.outcome.value == "insufficient_evidence"
        for item in response.validity
    )
    assert all(
        item.left_subject_id.endswith(":regulatory")
        == item.right_subject_id.endswith(":regulatory")
        for item in response.validity
    )
    assert all(not item.establishes_equal_benefit for item in response.validity)


def test_absence_without_coverage_is_not_a_negative_conclusion(
    service: ReadOnlyQueryService,
) -> None:
    response = service.comparisons(
        _comparison(jurisdictions=("NZ",), concept_id="not-observed")
    )
    assert response.conclusions == ()


def test_cursor_is_stable_and_bound_to_filters_and_clocks(
    service: ReadOnlyQueryService,
) -> None:
    first = service.comparisons(_comparison(limit=2))
    assert first.metadata.page.next_cursor is not None
    second = service.comparisons(
        _comparison(limit=2, cursor=first.metadata.page.next_cursor)
    )
    assert set(first.conclusions).isdisjoint(second.conclusions)
    with pytest.raises(InvalidCursorError):
        service.comparisons(
            _comparison(
                jurisdictions=("NZ",),
                limit=2,
                cursor=first.metadata.page.next_cursor,
            )
        )


def test_comparison_validity_is_stable_across_limit_one_pages(
    service: ReadOnlyQueryService,
) -> None:
    first = service.comparisons(_comparison(limit=1))
    assert first.metadata.page.next_cursor is not None
    second = service.comparisons(
        _comparison(limit=1, cursor=first.metadata.page.next_cursor)
    )

    assert first.validity == second.validity
    assert len(first.validity) == 4
    assert all(
        assessment.outcome.value == "insufficient_evidence"
        for assessment in first.validity
    )
    assert all(
        assessment.left_subject_id.endswith(":regulatory")
        == assessment.right_subject_id.endswith(":regulatory")
        for assessment in first.validity
    )
    assert all(
        not assessment.establishes_medicine_equivalence
        and not assessment.establishes_substitutability
        and not assessment.establishes_therapeutic_interchangeability
        and not assessment.establishes_equal_benefit
        for assessment in first.validity
    )


def test_comparison_validity_excludes_missing_and_cross_dimension_pairs(
    service: ReadOnlyQueryService,
) -> None:
    response = service.comparisons(_comparison(limit=1))
    subjects = {
        subject
        for assessment in response.validity
        for subject in (
            assessment.left_subject_id,
            assessment.right_subject_id,
        )
    }

    assert "rx:1:US:funding" not in subjects
    assert all(
        left.rsplit(":", maxsplit=1)[-1]
        == right.rsplit(":", maxsplit=1)[-1]
        for left, right in (
            (assessment.left_subject_id, assessment.right_subject_id)
            for assessment in response.validity
        )
    )


def test_evidence_and_coverage_use_sql_keyset_pages(
    service: ReadOnlyQueryService,
) -> None:
    first_evidence = service.evidence(
        EvidenceQuery(
            concept_id="rx:1",
            valid_at=NOW,
            observed_at=NOW,
            limit=1,
        )
    )
    assert first_evidence.metadata.page.next_cursor is not None
    second_evidence = service.evidence(
        EvidenceQuery(
            concept_id="rx:1",
            valid_at=NOW,
            observed_at=NOW,
            limit=1,
            cursor=first_evidence.metadata.page.next_cursor,
        )
    )
    assert first_evidence.evidence[0] != second_evidence.evidence[0]

    first_coverage = service.coverage(
        CoverageQuery(
            jurisdictions=("AU", "US"),
            valid_at=NOW,
            observed_at=NOW,
            limit=1,
        )
    )
    assert first_coverage.metadata.page.next_cursor is not None
    second_coverage = service.coverage(
        CoverageQuery(
            jurisdictions=("AU", "US"),
            valid_at=NOW,
            observed_at=NOW,
            limit=1,
            cursor=first_coverage.metadata.page.next_cursor,
        )
    )
    assert first_coverage.coverage[0] != second_coverage.coverage[0]


def test_coverage_cursor_preserves_raw_status_after_normalization(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path / "atlas.duckdb")
    connection = duckdb.connect(str(database))
    rows = [
        (
            "NZ",
            "custom",
            f"receipt-{status}",
            f"observation-{status}",
            "all",
            "regulatory",
            None,
            "medicine",
            status,
            "observed medicines",
            NOW,
            None,
            NOW,
            None,
            1,
            1,
            2,
            0,
            [],
            0,
        )
        for status in ("active", "approved")
    ]
    connection.executemany(
        """
        INSERT INTO temporal_coverage VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        rows,
    )
    connection.close()
    query_service = ReadOnlyQueryService(
        database, cursor_secret=SECRET, allowed_root=tmp_path
    )
    first = query_service.coverage(
        CoverageQuery(
            jurisdictions=("NZ",),
            dimensions=(EvidenceDimension.REGULATORY,),
            valid_at=NOW,
            observed_at=NOW,
            limit=1,
        )
    )
    assert first.coverage[0].state is ProductState.UNKNOWN
    assert first.metadata.page.next_cursor is not None
    second = query_service.coverage(
        CoverageQuery(
            jurisdictions=("NZ",),
            dimensions=(EvidenceDimension.REGULATORY,),
            valid_at=NOW,
            observed_at=NOW,
            limit=1,
            cursor=first.metadata.page.next_cursor,
        )
    )
    assert len(second.coverage) == 1
    assert second.coverage[0].state is ProductState.UNKNOWN
    assert second.metadata.page.next_cursor is None


def test_comparison_provenance_is_bounded_but_conflict_uses_all_rows(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path / "atlas.duckdb")
    connection = duckdb.connect(str(database))
    connection.execute(
        """
        INSERT INTO temporal_assertions
        SELECT printf('bulk-%03d', number), 'rx:1', 'NZ', 'regulatory',
               'Medsafe',
               CASE WHEN number = 99 THEN 'withdrawn' ELSE 'approved' END,
               'confirmed', [], ?, NULL, ?, NULL, NULL, NULL, 'medsafe',
               'https://example.test/medsafe/bulk', ?, NULL, NULL, NULL,
               '2026-07', 'nz-adapter-v1'
        FROM range(100) AS generated(number)
        """,
        [NOW, NOW, NOW],
    )
    connection.close()
    query_service = ReadOnlyQueryService(
        database, cursor_secret=SECRET, allowed_root=tmp_path
    )

    response = query_service.comparisons(
        ComparisonQuery(
            concept_id="rx:1",
            jurisdictions=("NZ",),
            dimensions=(EvidenceDimension.REGULATORY,),
            valid_at=NOW,
            observed_at=NOW,
            limit=1,
        )
    )
    conclusion = response.conclusions[0]
    assert conclusion.state is ProductState.CONFLICTING
    assert len(conclusion.provenance) == 32
    assert conclusion.uncertainty.reason is not None
    assert "32 of 101" in conclusion.uncertainty.reason
    assert "paginated evidence endpoint" in conclusion.uncertainty.reason


def test_query_plan_receipt_proves_keyset_and_limit_pushdown(
    service: ReadOnlyQueryService,
) -> None:
    first = service.evidence(
        EvidenceQuery(
            concept_id="rx:1",
            valid_at=NOW,
            observed_at=NOW,
            limit=1,
        )
    )
    cursor = first.metadata.page.next_cursor
    assert cursor is not None

    receipt = service.query_plan_evidence(
        EvidenceQuery(
            concept_id="rx:1",
            valid_at=NOW,
            observed_at=NOW,
            limit=1,
            cursor=cursor,
        )
    )

    assert receipt.operation == "evidence"
    assert receipt.requested_limit == 1
    assert receipt.fetch_limit == 2
    assert receipt.keyset_applied is True
    assert receipt.schema_identity == service.schema_identity
    assert len(receipt.sql_sha256) == 64
    assert receipt.parameter_count > 0
    assert receipt.planning_duration_ms >= 0
    assert receipt.plan

    for query, operation in (
        (_comparison(limit=1), "comparisons"),
        (
            CoverageQuery(
                jurisdictions=("AU", "US"),
                valid_at=NOW,
                observed_at=NOW,
                limit=1,
            ),
            "coverage",
        ),
    ):
        plan = service.query_plan_evidence(query)
        assert plan.operation == operation
        assert plan.fetch_limit == 2
        assert plan.keyset_applied is False
        assert plan.plan


def test_schema_identity_is_deterministic_and_rejects_incompatible_types(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path / "atlas.duckdb")
    first = ReadOnlyQueryService(
        database, cursor_secret=SECRET, allowed_root=tmp_path
    )
    second = ReadOnlyQueryService(
        database, cursor_secret=SECRET, allowed_root=tmp_path
    )
    assert first.schema_identity == second.schema_identity
    assert len(first.schema_identity) == 64

    incompatible = tmp_path / "incompatible.duckdb"
    incompatible.write_bytes(database.read_bytes())
    connection = duckdb.connect(str(incompatible))
    connection.execute(
        """
        CREATE OR REPLACE TABLE temporal_assertions AS
        SELECT * REPLACE (42::INTEGER AS assertion_id)
        FROM temporal_assertions
        """
    )
    connection.close()
    with pytest.raises(InvalidDatabaseError, match="incompatible type"):
        ReadOnlyQueryService(
            incompatible, cursor_secret=SECRET, allowed_root=tmp_path
        )


def test_readiness_rejects_runtime_schema_identity_change(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path / "atlas.duckdb")
    service = ReadOnlyQueryService(
        database, cursor_secret=SECRET, allowed_root=tmp_path
    )
    connection = duckdb.connect(str(database))
    connection.execute("ALTER TABLE temporal_coverage ADD COLUMN extra VARCHAR")
    connection.close()

    with pytest.raises(InvalidDatabaseError, match="identity changed"):
        service.readiness_probe()


def test_tampered_and_malformed_cursors_are_rejected(
    service: ReadOnlyQueryService,
) -> None:
    cursor = service.comparisons(_comparison(limit=1)).metadata.page.next_cursor
    assert cursor is not None
    tampered = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
    for invalid in (tampered, "not-a-valid-cursor"):
        with pytest.raises(InvalidCursorError):
            service.comparisons(_comparison(limit=1, cursor=invalid))


def test_evidence_lookup_is_parameterized_against_hostile_input(
    service: ReadOnlyQueryService,
) -> None:
    hostile = "rx:1'; DROP TABLE temporal_assertions; --"
    response = service.evidence(
        EvidenceQuery(concept_id=hostile, valid_at=NOW, observed_at=NOW)
    )
    assert response.evidence == ()
    assert (
        len(
            service.evidence(
                EvidenceQuery(concept_id="rx:1", valid_at=NOW, observed_at=NOW)
            ).evidence
        )
        == 3
    )


def test_evidence_by_assertion_preserves_native_and_canonical_terms(
    service: ReadOnlyQueryService,
) -> None:
    response = service.evidence(
        EvidenceQuery(assertion_id="a-au-reg", valid_at=NOW, observed_at=NOW)
    )
    item = response.evidence[0]
    assert item.terminology.native_code == "registered"
    assert item.terminology.canonical_code == "rx:1"
    assert item.provenance.source_uri == "https://example.test/artg/1"


def test_coverage_keeps_unknown_denominator_unknown(
    service: ReadOnlyQueryService,
) -> None:
    response = service.coverage(
        CoverageQuery(
            jurisdictions=("US",),
            dimensions=(EvidenceDimension.REGULATORY,),
            valid_at=NOW,
            observed_at=NOW,
        )
    )
    assert response.coverage[0].denominator is None
    assert response.coverage[0].state is ProductState.UNKNOWN


def test_connections_are_request_scoped_and_database_remains_read_only(
    service: ReadOnlyQueryService,
) -> None:
    service.readiness_probe()
    service.comparisons(_comparison())
    writer = duckdb.connect(str(service.database_path))
    writer.execute("CREATE TABLE proof_request_connection_closed (value INT)")
    writer.close()


def test_runtime_database_deletion_is_a_safe_service_failure(
    service: ReadOnlyQueryService,
) -> None:
    service.database_path.unlink()

    with pytest.raises(QueryServiceError, match="query service is unavailable"):
        service.readiness_probe()
    with pytest.raises(QueryServiceError, match="query service is unavailable"):
        service.comparisons(_comparison())


def test_runtime_database_corruption_is_a_safe_service_failure(
    service: ReadOnlyQueryService,
) -> None:
    service.database_path.write_bytes(b"not a DuckDB database")

    with pytest.raises(QueryServiceError, match="query service is unavailable"):
        service.readiness_probe()
    with pytest.raises(QueryServiceError, match="query service is unavailable"):
        service.coverage(
            CoverageQuery(
                jurisdictions=("NZ",),
                valid_at=NOW,
                observed_at=NOW,
            )
        )


def test_path_and_schema_safety(tmp_path: Path) -> None:
    database = _database(tmp_path / "safe.duckdb")
    outside = tmp_path.parent / "outside-query-service.duckdb"
    outside.write_bytes(database.read_bytes())
    try:
        with pytest.raises(InvalidDatabaseError, match="outside allowed_root"):
            ReadOnlyQueryService(
                outside, cursor_secret=SECRET, allowed_root=tmp_path
            )
    finally:
        outside.unlink()
    with pytest.raises(InvalidDatabaseError, match="absolute"):
        ReadOnlyQueryService(Path("relative.duckdb"), cursor_secret=SECRET)
    bad = tmp_path / "bad.duckdb"
    connection = duckdb.connect(str(bad))
    connection.execute("CREATE TABLE unrelated (value INT)")
    connection.close()
    with pytest.raises(InvalidDatabaseError, match="schema is incomplete"):
        ReadOnlyQueryService(bad, cursor_secret=SECRET)


def test_secret_and_extension_are_validated(tmp_path: Path) -> None:
    database = _database(tmp_path / "atlas.duckdb")
    with pytest.raises(ValueError, match="at least 16"):
        ReadOnlyQueryService(database, cursor_secret=b"short")
    disguised = tmp_path / "atlas.txt"
    disguised.write_bytes(database.read_bytes())
    with pytest.raises(InvalidDatabaseError, match="DuckDB file"):
        ReadOnlyQueryService(disguised, cursor_secret=SECRET)
