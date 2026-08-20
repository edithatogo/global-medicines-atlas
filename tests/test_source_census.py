"""Governed global source-census coverage tests."""

from __future__ import annotations

from global_medicines_atlas.source_catalog import (
    DiscoveryStatus,
    load_catalog,
)
from global_medicines_atlas.source_census import (
    aggregate_census_coverage,
    jurisdiction_coverage,
)


def test_priority_cohorts_and_who_denominator_fields_are_declared() -> None:
    catalog = load_catalog()
    entries = {entry.jurisdiction: entry for entry in catalog.jurisdictions}
    expected = {
        "BRA": {"brazil", "latin_america"},
        "KOR": {"south_korea"},
        "SGP": {"singapore"},
        "CHE": {"switzerland"},
        "IND": {"india"},
        "ZAF": {"south_africa", "africa"},
        "SAU": {"gulf"},
        "MEX": {"latin_america"},
        "NGA": {"africa"},
    }

    for jurisdiction, cohorts in expected.items():
        entry = entries[jurisdiction]
        assert cohorts <= set(entry.priority_cohorts)
        denominator = entry.regulatory_denominator
        assert denominator.included
        assert denominator.status
        assert denominator.evidence_limit
        assert denominator.wla is None
        assert denominator.ml3 is None
        assert denominator.ml4 is None


def test_priority_jurisdictions_declare_regulatory_and_funding_sources() -> (
    None
):
    rows = {row.jurisdiction: row for row in jurisdiction_coverage()}
    for jurisdiction in (
        "BRA",
        "KOR",
        "SGP",
        "CHE",
        "IND",
        "ZAF",
        "SAU",
        "MEX",
        "NGA",
    ):
        assert rows[jurisdiction].regulatory_source
        assert rows[jurisdiction].funding_source


def test_discovery_declarations_do_not_claim_receipts_or_ingestion() -> None:
    priority_ids = {
        "BRA",
        "KOR",
        "SGP",
        "CHE",
        "IND",
        "ZAF",
        "SAU",
        "MEX",
        "NGA",
    }
    sources = [
        source
        for source in load_catalog().sources
        if priority_ids.intersection(source.jurisdictions)
    ]

    assert sources
    assert all(
        source.discovery_status
        in {
            DiscoveryStatus.DISCOVERY_ONLY,
            DiscoveryStatus.DECLARATION_VERIFIED,
        }
        for source in sources
    )
    assert all(not source.implemented_ingestion for source in sources)
    assert all(source.current_receipt_id is None for source in sources)
    assert all("review_required" in source.rights_status for source in sources)


def test_coverage_measures_each_required_capability() -> None:
    coverage = aggregate_census_coverage()

    assert coverage.denominator == len(jurisdiction_coverage())
    assert 0 < coverage.regulatory_source <= coverage.denominator
    assert 0 < coverage.funding_source <= coverage.denominator
    assert 0 < coverage.api <= coverage.denominator
    assert 0 < coverage.bulk <= coverage.denominator
    assert 0 < coverage.implemented_ingestion <= coverage.denominator
    assert coverage.current_receipt == 1
    assert coverage.source_health_scheduled == coverage.denominator
    assert coverage.schema_drift_scheduled == coverage.denominator
    assert coverage.parser_capable_sources > 0
    assert coverage.live_receipt_sources == 0
    assert coverage.production_qualified_sources == 0


def test_global_expansion_denominator_and_source_counts_are_measurable() -> (
    None
):
    catalog = load_catalog()

    assert len(catalog.jurisdictions) >= 34
    assert len(catalog.sources) >= 95
    assert (
        len({
            jurisdiction
            for source in catalog.sources
            for jurisdiction in source.jurisdictions
        })
        >= 34
    )


def test_monitoring_contract_is_explicit_and_applied_to_every_source() -> None:
    catalog = load_catalog()

    assert catalog.monitoring_contract.source_health == "weekly"
    assert catalog.monitoring_contract.schema_drift == "monthly"
    assert all(
        source.monitoring == catalog.monitoring_contract
        for source in catalog.sources
    )
