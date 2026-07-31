"""DuckDB integration tests for deterministic concept discovery."""

# ruff: file-ignore[import-private-name]

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from tests.test_query_service import (
    SECRET,
    _database,
)

from global_medicines_atlas.product_contracts import (
    ConceptSearchQuery,
    MatchMethod,
)
from global_medicines_atlas.query_service import (
    InvalidCursorError,
    InvalidDatabaseError,
    QueryServiceError,
    ReadOnlyQueryService,
)


def _catalog_database(path: Path) -> Path:
    _database(path)
    connection = duckdb.connect(str(path))
    connection.execute(
        """
        CREATE TABLE medicine_concepts (
            concept_id VARCHAR NOT NULL,
            preferred_name VARCHAR NOT NULL,
            concept_type VARCHAR NOT NULL
        );
        CREATE TABLE medicine_identifiers (
            concept_id VARCHAR NOT NULL,
            identifier_system VARCHAR NOT NULL,
            identifier_value VARCHAR NOT NULL
        );
        CREATE TABLE medicine_names (
            concept_id VARCHAR NOT NULL,
            name VARCHAR NOT NULL,
            name_type VARCHAR NOT NULL,
            normalized_name VARCHAR NOT NULL
        );
        CREATE TABLE medicine_concept_jurisdictions (
            concept_id VARCHAR NOT NULL,
            jurisdiction VARCHAR NOT NULL
        );
        CREATE TABLE medicine_sources (
            source_id VARCHAR NOT NULL,
            jurisdiction VARCHAR NOT NULL,
            authority VARCHAR NOT NULL,
            regulatory_system BOOLEAN NOT NULL,
            funding_system BOOLEAN NOT NULL
        );
        INSERT INTO medicine_concepts VALUES
            ('gma:aspirin', 'Aspirin', 'substance'),
            ('gma:para', 'Paracetamol', 'substance'),
            ('gma:combo', 'Paracetamol and caffeine', 'product');
        INSERT INTO medicine_identifiers VALUES
            ('gma:aspirin', 'rxnorm', '1191'),
            ('gma:para', 'rxnorm', '161');
        INSERT INTO medicine_names VALUES
            ('gma:aspirin', 'Aspirin', 'preferred', 'aspirin'),
            ('gma:aspirin', 'Acetylsalicylic acid', 'alias',
             'acetylsalicylic acid'),
            ('gma:para', 'Paracetamol', 'preferred', 'paracetamol'),
            ('gma:para', 'Acetaminophen', 'alias', 'acetaminophen'),
            ('gma:combo', 'Paracetamol and caffeine', 'preferred',
             'paracetamol and caffeine');
        INSERT INTO medicine_concept_jurisdictions VALUES
            ('gma:aspirin', 'AU'), ('gma:aspirin', 'NZ'),
            ('gma:para', 'NZ'), ('gma:combo', 'AU');
        INSERT INTO medicine_sources VALUES
            ('artg', 'AU', 'TGA', true, false),
            ('medsafe', 'NZ', 'Medsafe', true, false),
            ('pharmac', 'NZ', 'Pharmac', false, true);
        """
    )
    connection.close()
    return path


@pytest.fixture
def discovery_service(tmp_path: Path) -> ReadOnlyQueryService:
    return ReadOnlyQueryService(
        _catalog_database(tmp_path / "catalog.duckdb"),
        cursor_secret=SECRET,
        allowed_root=tmp_path,
    )


@pytest.mark.parametrize(
    ("query", "expected", "method"),
    [
        ("gma:aspirin", "gma:aspirin", MatchMethod.EXACT_CONCEPT_ID),
        ("1191", "gma:aspirin", MatchMethod.EXACT_IDENTIFIER),
        ("ASPIRIN", "gma:aspirin", MatchMethod.NORMALIZED_PREFERRED_NAME),
        ("acetaminophen", "gma:para", MatchMethod.NORMALIZED_ALIAS),
    ],
)
def test_search_precedence_and_explanation(
    discovery_service: ReadOnlyQueryService,
    query: str,
    expected: str,
    method: MatchMethod,
) -> None:
    response = discovery_service.search_concepts(
        ConceptSearchQuery(query=query)
    )

    assert response.concepts[0].concept_id == expected
    assert response.concepts[0].explanation.method is method
    assert response.concepts[0].explanation.establishes_equivalence is False


def test_search_is_bounded_filtered_and_keyset_paginated(
    discovery_service: ReadOnlyQueryService,
) -> None:
    first = discovery_service.search_concepts(
        ConceptSearchQuery(query="paracetamol", limit=1)
    )
    assert [item.concept_id for item in first.concepts] == ["gma:para"]
    assert first.metadata.page.next_cursor is not None

    second = discovery_service.search_concepts(
        ConceptSearchQuery(
            query="paracetamol",
            limit=1,
            cursor=first.metadata.page.next_cursor,
        )
    )
    assert [item.concept_id for item in second.concepts] == ["gma:combo"]
    assert second.metadata.page.next_cursor is None

    nz = discovery_service.search_concepts(
        ConceptSearchQuery(query="paracetamol", jurisdictions=("NZ",))
    )
    assert [item.concept_id for item in nz.concepts] == ["gma:para"]


def test_cursor_is_bound_to_normalized_query_and_filters(
    discovery_service: ReadOnlyQueryService,
) -> None:
    first = discovery_service.search_concepts(
        ConceptSearchQuery(query="paracetamol", limit=1)
    )
    cursor = first.metadata.page.next_cursor
    assert cursor is not None

    with pytest.raises(InvalidCursorError):
        discovery_service.search_concepts(
            ConceptSearchQuery(query="aspirin", limit=1, cursor=cursor)
        )


def test_detail_catalogues_and_unknowns_fail_closed(
    discovery_service: ReadOnlyQueryService,
) -> None:
    detail = discovery_service.concept_detail("gma:aspirin")
    assert detail.preferred_name == "Aspirin"
    assert [item.value for item in detail.identifiers] == ["1191"]
    assert detail.jurisdictions == ("AU", "NZ")

    assert [
        item.jurisdiction for item in discovery_service.jurisdictions()
    ] == [
        "AU",
        "NZ",
    ]
    assert [item.source_id for item in discovery_service.sources("nz")] == [
        "medsafe",
        "pharmac",
    ]

    with pytest.raises(QueryServiceError, match="unknown"):
        discovery_service.concept_detail("gma:missing")


def test_hostile_input_is_parameterized(
    discovery_service: ReadOnlyQueryService,
) -> None:
    result = discovery_service.search_concepts(
        ConceptSearchQuery(
            query="'; DROP TABLE medicine_concepts; --",
        )
    )

    assert result.concepts == ()
    assert discovery_service.concept_detail("gma:aspirin").concept_id == (
        "gma:aspirin"
    )


def test_missing_catalog_fails_closed(tmp_path: Path) -> None:
    service = ReadOnlyQueryService(
        _database(tmp_path / "legacy.duckdb"),
        cursor_secret=SECRET,
        allowed_root=tmp_path,
    )

    with pytest.raises(InvalidDatabaseError, match="catalogue is incomplete"):
        service.search_concepts(ConceptSearchQuery(query="aspirin"))
