"""Governance tests for the global API and downloadable-source catalog."""

from __future__ import annotations

from global_medicines_atlas.countries import SourceDimension
from global_medicines_atlas.source_catalog import (
    AccessMode,
    SourceReadiness,
    load_source_catalog,
    sources_for,
)


def test_source_catalog_has_unique_governed_access_surfaces() -> None:
    sources = load_source_catalog()

    assert len(sources) >= 20
    assert len({source.source_id for source in sources}) == len(sources)
    assert all(source.rights_status for source in sources)
    assert all(source.evidence_limit for source in sources)


def test_every_first_cohort_jurisdiction_has_regulatory_source() -> None:
    for jurisdiction in ("NZL", "AUS", "USA", "GBR", "CAN", "JPN", "EU"):
        regulatory = sources_for(jurisdiction, SourceDimension.REGULATORY)
        assert regulatory, jurisdiction


def test_funding_and_regulatory_sources_are_independent() -> None:
    nz_regulatory = sources_for("NZL", SourceDimension.REGULATORY)
    nz_funding = sources_for("NZL", SourceDimension.FUNDING)

    assert {source.source_id for source in nz_regulatory} == {
        "nz-medsafe-products"
    }
    assert {source.source_id for source in nz_funding} == {
        "nz-pharmac-schedule"
    }


def test_api_and_download_modes_have_declared_endpoints() -> None:
    for source in load_source_catalog():
        if source.access_mode in {AccessMode.API, AccessMode.API_AND_DOWNLOAD}:
            assert source.api_url is not None
        if source.access_mode in {
            AccessMode.DOWNLOAD,
            AccessMode.API_AND_DOWNLOAD,
        }:
            assert source.download_url is not None


def test_only_executable_local_capabilities_are_marked_implemented() -> None:
    implemented = {
        source.source_id
        for source in load_source_catalog()
        if source.readiness == SourceReadiness.IMPLEMENTED
    }
    assert implemented == {"global-rxnorm", "us-drugsfda"}
