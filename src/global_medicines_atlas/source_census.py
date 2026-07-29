"""Measured source-census coverage without implied source currency."""

from __future__ import annotations

from pydantic import Field

from .countries import Capability, SourceDimension, builtin_source_capabilities
from .models import FrozenModel
from .source_catalog import AccessMode, SourceCatalog, load_catalog


class JurisdictionSourceCoverage(FrozenModel):
    """Boolean coverage measurements for one declared jurisdiction."""

    jurisdiction: str = Field(min_length=2, max_length=3)
    regulatory_source: bool
    funding_source: bool
    api: bool
    bulk: bool
    implemented_ingestion: bool
    current_receipt: bool
    source_health_scheduled: bool
    schema_drift_scheduled: bool


class CensusCoverage(FrozenModel):
    """Numerators over the declared discovery denominator."""

    denominator: int = Field(ge=0)
    regulatory_source: int = Field(ge=0)
    funding_source: int = Field(ge=0)
    api: int = Field(ge=0)
    bulk: int = Field(ge=0)
    implemented_ingestion: int = Field(ge=0)
    current_receipt: int = Field(ge=0)
    source_health_scheduled: int = Field(ge=0)
    schema_drift_scheduled: int = Field(ge=0)
    parser_capable_sources: int = Field(default=0, ge=0)
    live_receipt_sources: int = Field(default=0, ge=0)
    production_qualified_sources: int = Field(default=0, ge=0)


def jurisdiction_coverage(
    catalog: SourceCatalog | None = None,
) -> tuple[JurisdictionSourceCoverage, ...]:
    """Measure declarations and evidence state for denominator jurisdictions."""

    resolved = load_catalog() if catalog is None else catalog
    rows: list[JurisdictionSourceCoverage] = []
    for entry in resolved.jurisdictions:
        if not entry.regulatory_denominator.included:
            continue
        sources = tuple(
            source
            for source in resolved.sources
            if entry.jurisdiction in source.jurisdictions
        )
        rows.append(
            JurisdictionSourceCoverage(
                jurisdiction=entry.jurisdiction,
                regulatory_source=any(
                    source.dimension == SourceDimension.REGULATORY
                    for source in sources
                ),
                funding_source=any(
                    source.dimension
                    in {SourceDimension.FUNDING, SourceDimension.FORMULARY}
                    for source in sources
                ),
                api=any(
                    source.access_mode
                    in {AccessMode.API, AccessMode.API_AND_DOWNLOAD}
                    for source in sources
                ),
                bulk=any(
                    source.access_mode
                    in {AccessMode.DOWNLOAD, AccessMode.API_AND_DOWNLOAD}
                    for source in sources
                ),
                implemented_ingestion=any(
                    source.implemented_ingestion for source in sources
                ),
                current_receipt=any(
                    source.current_receipt_id is not None for source in sources
                ),
                source_health_scheduled=bool(sources)
                and all(
                    source.monitoring.source_health != "unscheduled"
                    for source in sources
                ),
                schema_drift_scheduled=bool(sources)
                and all(
                    source.monitoring.schema_drift != "unscheduled"
                    for source in sources
                ),
            )
        )
    return tuple(sorted(rows, key=lambda row: row.jurisdiction))


def aggregate_census_coverage(
    catalog: SourceCatalog | None = None,
) -> CensusCoverage:
    rows = jurisdiction_coverage(catalog)
    fields = (
        "regulatory_source",
        "funding_source",
        "api",
        "bulk",
        "implemented_ingestion",
        "current_receipt",
        "source_health_scheduled",
        "schema_drift_scheduled",
    )
    counts = {
        field: sum(bool(getattr(row, field)) for row in rows)
        for field in fields
    }
    capability_registry = builtin_source_capabilities()
    capability_registry.validate_catalog(
        (load_catalog() if catalog is None else catalog).sources
    )
    return CensusCoverage(
        denominator=len(rows),
        **counts,
        parser_capable_sources=sum(
            Capability.SOURCE_PARSER in declaration.capabilities
            for declaration in capability_registry
        ),
        live_receipt_sources=sum(
            Capability.LIVE_RECEIPT in declaration.capabilities
            for declaration in capability_registry
        ),
        production_qualified_sources=sum(
            Capability.PRODUCTION_QUALIFICATION in declaration.capabilities
            for declaration in capability_registry
        ),
    )
