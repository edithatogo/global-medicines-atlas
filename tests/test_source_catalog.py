"""Governance tests for the global API and downloadable-source catalog."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from global_medicines_atlas import source_catalog
from global_medicines_atlas.countries import SourceDimension
from global_medicines_atlas.source_catalog import (
    AccessMode,
    DiscoveryStatus,
    MedicineDataSource,
    MonitoringSchedule,
    SourceReadiness,
    load_catalog,
    load_source_catalog,
    sources_for,
)


def test_source_catalog_has_unique_governed_access_surfaces() -> None:
    sources = load_source_catalog()

    assert len(sources) >= 38
    assert len({source.source_id for source in sources}) == len(sources)
    assert all(source.rights_status for source in sources)
    assert all(source.evidence_limit for source in sources)
    assert all(source.discovery_status for source in sources)


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


def test_receipt_and_implementation_claims_are_fail_closed() -> None:
    base = load_source_catalog()[0].model_dump()

    with pytest.raises(ValidationError, match="receipt-backed"):
        MedicineDataSource.model_validate({
            **base,
            "current_receipt_id": "receipt-without-status",
        })

    with pytest.raises(ValidationError, match="implemented_ingestion"):
        MedicineDataSource.model_validate({
            **base,
            "readiness": SourceReadiness.IMPLEMENTED,
            "implemented_ingestion": False,
        })

    receipt_backed = MedicineDataSource.model_validate({
        **base,
        "discovery_status": DiscoveryStatus.RECEIPT_BACKED,
        "current_receipt_id": "receipt-current",
    })
    assert receipt_backed.current_receipt_id == "receipt-current"


def test_catalog_rejects_duplicate_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = load_catalog().model_dump(mode="json")
    payload["sources"].append(payload["sources"][0])
    monkeypatch.setattr(source_catalog.json, "loads", lambda _: payload)

    with pytest.raises(ValueError, match="duplicate source_id"):
        load_catalog()


def test_catalog_rejects_duplicate_jurisdictions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = load_catalog().model_dump(mode="json")
    payload["jurisdictions"].append(payload["jurisdictions"][0])
    monkeypatch.setattr(source_catalog.json, "loads", lambda _: payload)

    with pytest.raises(ValueError, match="duplicate jurisdictions"):
        load_catalog()


def test_catalog_rejects_monitoring_contract_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = load_catalog().model_dump(mode="json")
    payload["sources"][0]["monitoring"] = MonitoringSchedule(
        source_health="daily",
        schema_drift="monthly",
    ).model_dump()
    monkeypatch.setattr(source_catalog.json, "loads", lambda _: payload)

    with pytest.raises(ValidationError, match="monitoring contract"):
        load_catalog()
