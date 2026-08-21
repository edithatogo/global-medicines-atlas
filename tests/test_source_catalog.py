"""Governance tests for the global API and downloadable-source catalog."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse

import pytest
from pydantic import ValidationError

from global_medicines_atlas import source_catalog
from global_medicines_atlas.bronze_fixture_landing import (
    CURRENT_SCOPE_FIXTURE_SOURCE_IDS,
)
from global_medicines_atlas.countries import SourceDimension
from global_medicines_atlas.source_catalog import (
    AccessMode,
    AvailableField,
    ChangeSemantics,
    DiscoveryStatus,
    GeographicScope,
    InformationDomain,
    IntegrationLayer,
    InterfaceStatus,
    LanguageCode,
    MedicineDataSource,
    MonitoringSchedule,
    PopulationScope,
    QualificationState,
    RecordEntity,
    SourceReadiness,
    StatusSemantics,
    load_catalog,
    load_source_catalog,
    sources_for,
)
from global_medicines_atlas.source_profiles import acquisition_profile


def test_source_catalog_has_unique_governed_access_surfaces() -> None:
    sources = load_source_catalog()

    assert len(sources) >= 95
    assert len({source.source_id for source in sources}) == len(sources)
    assert all(source.rights_status for source in sources)
    assert all(source.evidence_limit for source in sources)
    assert all(source.discovery_status for source in sources)
    assert all(source.information_domains for source in sources)
    assert all(source.record_entities for source in sources)
    assert all(source.status_semantics for source in sources)
    assert all(source.languages for source in sources)
    assert all(source.available_fields for source in sources)


def test_information_schema_uses_versioned_controlled_labels() -> None:
    catalog = load_catalog()

    assert catalog.schema_version == 5
    for source in catalog.sources:
        assert all(
            isinstance(value, InformationDomain)
            for value in source.information_domains
        )
        assert all(
            isinstance(value, RecordEntity) for value in source.record_entities
        )
        assert all(
            isinstance(value, StatusSemantics)
            for value in source.status_semantics
        )
        assert isinstance(source.geographic_scope, GeographicScope)
        assert isinstance(source.population_scope, PopulationScope)
        assert all(
            isinstance(value, LanguageCode) for value in source.languages
        )
        assert isinstance(source.change_semantics, ChangeSemantics)
        assert all(
            isinstance(value, AvailableField)
            for value in source.available_fields
        )


def test_published_information_schema_matches_model() -> None:
    schema_path = (
        Path(__file__).parents[1] / "schemas" / "international-resource-v5.json"
    )

    assert json.loads(schema_path.read_text(encoding="utf-8")) == (
        source_catalog.SourceCatalog.model_json_schema()
    )


def test_every_first_cohort_jurisdiction_has_regulatory_source() -> None:
    for jurisdiction in ("NZL", "AUS", "USA", "GBR", "CAN", "JPN", "EU"):
        regulatory = sources_for(jurisdiction, SourceDimension.REGULATORY)
        assert regulatory, jurisdiction


def test_funding_and_regulatory_sources_are_independent() -> None:
    nz_regulatory = sources_for("NZL", SourceDimension.REGULATORY)
    nz_funding = sources_for("NZL", SourceDimension.FUNDING)

    assert {source.source_id for source in nz_regulatory} >= {
        "nz-medsafe-products",
        "nz-medsafe-documents",
    }
    assert {source.source_id for source in nz_funding} >= {
        "nz-pharmac-schedule",
        "nz-pharmac-schedule-xml",
    }
    assert not {source.source_id for source in nz_regulatory}.intersection(
        source.source_id for source in nz_funding
    )


def test_api_and_download_modes_have_declared_endpoints() -> None:
    for source in load_source_catalog():
        if source.access_mode in {AccessMode.API, AccessMode.API_AND_DOWNLOAD}:
            assert source.api_url is not None
        if source.access_mode in {
            AccessMode.DOWNLOAD,
            AccessMode.API_AND_DOWNLOAD,
        }:
            assert source.download_url is not None


def test_supported_apis_use_operational_endpoints_not_documentation() -> None:
    documentation_markers = {
        "/about/",
        "/developer/",
        "/document/",
        "/documentation/",
        "/docs/",
        "/help/",
        "/swagger",
    }
    for source in load_source_catalog():
        if source.interface_status != InterfaceStatus.SUPPORTED:
            continue
        assert source.api_url is not None, source.source_id
        endpoint = str(source.api_url).lower()
        parsed = urlparse(endpoint)
        assert not any(
            marker in parsed.path for marker in documentation_markers
        ), source.source_id
        assert endpoint != str(source.documentation_url).lower()


@pytest.mark.parametrize(
    "required_field",
    [
        "interface_status",
        "formats",
        "authentication",
        "product_grain",
        "historical_scope",
        "native_identifier",
        "last_verified_at",
        "integration_layer",
        "documentation_url",
        "information_domains",
        "record_entities",
        "status_semantics",
        "geographic_scope",
        "population_scope",
        "languages",
        "change_semantics",
        "available_fields",
        "qualification_state",
        "qualification_references",
    ],
)
def test_schema_v4_catalog_rejects_omitted_governance_fields(
    monkeypatch: pytest.MonkeyPatch,
    required_field: str,
) -> None:
    payload = deepcopy(load_catalog().model_dump(mode="json"))
    del payload["sources"][0][required_field]
    monkeypatch.setattr(source_catalog.json, "loads", lambda _: payload)

    with pytest.raises(ValidationError, match=required_field):
        load_catalog()


def test_legacy_factory_is_explicit_and_model_validation_is_strict() -> None:
    source = next(
        source
        for source in load_source_catalog()
        if source.source_id == "us-drugsfda"
    )
    payload = source.model_dump()
    for field in (
        "interface_status",
        "formats",
        "authentication",
        "product_grain",
        "historical_scope",
        "native_identifier",
        "last_verified_at",
        "integration_layer",
        "documentation_url",
    ):
        payload.pop(field)

    with pytest.raises(ValidationError):
        MedicineDataSource.model_validate(payload)

    migrated = MedicineDataSource.from_legacy(**payload)
    assert migrated.formats == ("source-defined",)
    assert migrated.documentation_url == migrated.landing_page


@pytest.mark.parametrize(
    ("dimension", "domain", "entity", "semantics"),
    [
        (
            SourceDimension.REGULATORY,
            InformationDomain.REGULATORY_STATUS,
            RecordEntity.APPROVAL,
            StatusSemantics.AUTHORIZATION,
        ),
        (
            SourceDimension.FUNDING,
            InformationDomain.FUNDING_STATUS,
            RecordEntity.FUNDING_LISTING,
            StatusSemantics.REIMBURSEMENT,
        ),
        (
            SourceDimension.FORMULARY,
            InformationDomain.FORMULARY_STATUS,
            RecordEntity.FORMULARY_ENTRY,
            StatusSemantics.FORMULARY_INCLUSION,
        ),
        (
            SourceDimension.TERMINOLOGY,
            InformationDomain.TERMINOLOGY,
            RecordEntity.TERMINOLOGY_CONCEPT,
            StatusSemantics.TERMINOLOGY_ONLY,
        ),
    ],
)
def test_legacy_factory_derives_semantically_coherent_defaults(
    dimension: SourceDimension,
    domain: InformationDomain,
    entity: RecordEntity,
    semantics: StatusSemantics,
) -> None:
    source = next(
        source
        for source in load_source_catalog()
        if source.source_id == "us-drugsfda"
    )
    payload = source.model_dump()
    payload["dimension"] = dimension
    for field in (
        "information_domains",
        "record_entities",
        "status_semantics",
    ):
        payload.pop(field)

    migrated = MedicineDataSource.from_legacy(**payload)

    assert domain in migrated.information_domains
    assert entity in migrated.record_entities
    assert semantics in migrated.status_semantics


def test_verified_qualification_requires_references_and_live_receipt() -> None:
    base = load_source_catalog()[0].model_dump()

    with pytest.raises(ValidationError, match="evidence references"):
        MedicineDataSource.model_validate({
            **base,
            "qualification_state": QualificationState.DOCUMENTATION_VERIFIED,
            "qualification_references": (),
        })
    with pytest.raises(ValidationError, match="current receipt"):
        MedicineDataSource.model_validate({
            **base,
            "qualification_state": QualificationState.LIVE_VERIFIED,
            "qualification_references": ("receipt:missing",),
        })


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {"information_domains": (InformationDomain.PRODUCT_IDENTITY,)},
            "regulatory_status information",
        ),
        (
            {
                "record_entities": (RecordEntity.MEDICINAL_PRODUCT,),
            },
            "requires record entities",
        ),
        (
            {"status_semantics": (StatusSemantics.REIMBURSEMENT,)},
            "compatible status semantics",
        ),
        (
            {
                "available_fields": (
                    AvailableField.IDENTIFIERS,
                    AvailableField.PRICES,
                ),
            },
            "prices requires pricing and price",
        ),
    ],
)
def test_information_schema_rejects_cross_field_contradictions(
    updates: dict[str, object],
    message: str,
) -> None:
    base = next(
        source
        for source in load_source_catalog()
        if source.source_id == "us-drugsfda"
    ).model_dump()

    with pytest.raises(ValidationError, match=message):
        MedicineDataSource.model_validate({**base, **updates})


def test_only_executable_local_capabilities_are_marked_implemented() -> None:
    implemented = {
        source.source_id
        for source in load_source_catalog()
        if source.readiness == SourceReadiness.IMPLEMENTED
    }
    assert implemented == {
        "fr-open-medic",
        "global-rxnorm",
        *CURRENT_SCOPE_FIXTURE_SOURCE_IDS,
    }


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
        "integration_layer": IntegrationLayer.LIVE_RECEIPT,
        "implemented_ingestion": True,
        "readiness": SourceReadiness.IMPLEMENTED,
    })
    assert receipt_backed.current_receipt_id == "receipt-current"


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {"access_mode": AccessMode.API, "api_url": None},
            "API access mode requires api_url",
        ),
        (
            {"access_mode": AccessMode.DOWNLOAD, "download_url": None},
            "download access mode requires download_url",
        ),
        (
            {
                "implemented_ingestion": False,
                "integration_layer": IntegrationLayer.PARSER,
            },
            "parser-or-higher",
        ),
        (
            {
                "current_receipt_id": "receipt-current",
                "discovery_status": DiscoveryStatus.RECEIPT_BACKED,
                "integration_layer": IntegrationLayer.CATALOGUED,
            },
            "live-receipt",
        ),
        (
            {
                "access_mode": AccessMode.DOCUMENT,
                "interface_status": InterfaceStatus.SUPPORTED,
            },
            "not supported APIs",
        ),
        (
            {
                "access_mode": AccessMode.DOCUMENT,
                "acquisition_profile": "public-bulk",
            },
            "automatable access mode",
        ),
    ],
)
def test_access_and_integration_claims_are_fail_closed(
    updates: dict[str, object],
    message: str,
) -> None:
    base = load_source_catalog()[0].model_dump()

    with pytest.raises(ValidationError, match=message):
        MedicineDataSource.model_validate({**base, **updates})


def test_schema_prevalidator_preserves_legacy_payload_shapes() -> None:
    validator = source_catalog.SourceCatalog.governed_rows_are_explicit

    assert validator("invalid") == "invalid"
    assert validator({"schema_version": 2}) == {"schema_version": 2}
    assert validator({"schema_version": 3, "sources": "invalid"}) == {
        "schema_version": 3,
        "sources": "invalid",
    }
    assert validator({"schema_version": 3, "sources": ["invalid"]}) == {
        "schema_version": 3,
        "sources": ["invalid"],
    }


def test_catalog_rejects_duplicate_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = load_catalog().model_dump(mode="json")
    payload["sources"].append(payload["sources"][0])
    monkeypatch.setattr(source_catalog.json, "loads", lambda _: payload)

    with pytest.raises(ValueError, match="duplicate source_id"):
        load_catalog()


def test_catalog_exposes_governed_interface_and_integration_metadata() -> None:
    catalog = load_catalog()

    assert catalog.schema_version >= 3
    assert all(source.formats for source in catalog.sources)
    assert all(source.product_grain for source in catalog.sources)
    assert all(source.historical_scope for source in catalog.sources)
    assert all(source.native_identifier for source in catalog.sources)
    assert all(
        source.last_verified_at <= catalog.reviewed_at
        for source in catalog.sources
    )
    assert all(
        source.interface_status != InterfaceStatus.SUPPORTED
        for source in catalog.sources
        if source.access_mode in {AccessMode.WEB_SEARCH, AccessMode.DOCUMENT}
    )
    assert all(
        source.integration_layer
        in {
            IntegrationLayer.CATALOGUED,
            IntegrationLayer.ACQUISITION,
            IntegrationLayer.PARSER,
            IntegrationLayer.FIXTURE,
            IntegrationLayer.LIVE_RECEIPT,
        }
        for source in catalog.sources
    )


def test_required_researched_source_families_are_catalogued() -> None:
    ids = {source.source_id for source in load_source_catalog()}
    required = {
        "nz-nzulm-bulk",
        "nz-nzhts-fhir",
        "nz-medsafe-products",
        "nz-pharmac-schedule-xml",
        "nz-pharmac-hml",
        "au-pbs-api",
        "au-pbs-embargo",
        "au-pbs-historical-xml",
        "au-amt-rf2",
        "au-artg",
        "au-tga-regulatory-events",
        "us-drugsfda",
        "us-openfda-drugsfda",
        "us-fda-orange-book",
        "us-openfda-ndc",
        "us-dailymed-spl",
        "us-gsrs-unii",
        "global-rxnorm",
        "us-rxnorm-api",
        "us-cms-partd-formulary",
        "us-cms-nadac",
        "eu-ema-json",
        "eu-ema-article57",
        "eu-ema-pms-fhir",
        "eu-spor-rms-oms",
        "eu-union-register",
        "fr-bdpm",
        "no-fest",
        "se-npl-nsl",
        "co-invima-cum",
        "ae-ede-register",
    }
    assert required <= ids


def test_every_acquisition_profile_resolves() -> None:
    for source in load_source_catalog():
        if source.acquisition_profile is not None:
            assert (
                acquisition_profile(source.acquisition_profile).profile_id
                == source.acquisition_profile
            )


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


def test_catalog_rejects_unknown_jurisdiction_and_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = load_catalog().model_dump(mode="json")
    unknown_jurisdiction = deepcopy(baseline)
    unknown_jurisdiction["sources"][0]["jurisdictions"] = ["ZZZ"]
    monkeypatch.setattr(
        source_catalog.json,
        "loads",
        lambda _: unknown_jurisdiction,
    )
    with pytest.raises(ValidationError, match="undeclared jurisdictions"):
        load_catalog()

    unknown_profile = deepcopy(baseline)
    unknown_profile["sources"][0]["acquisition_profile"] = "unknown-profile"
    monkeypatch.setattr(source_catalog.json, "loads", lambda _: unknown_profile)
    with pytest.raises(
        ValidationError, match="undeclared acquisition profiles"
    ):
        load_catalog()
