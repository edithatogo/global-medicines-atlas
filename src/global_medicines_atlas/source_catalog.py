"""Governed catalog of authoritative medicine data access surfaces."""

from __future__ import annotations

import json
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, Self, cast

from pydantic import Field, HttpUrl, model_validator

from .countries import SourceDimension
from .logging import get_logger
from .models import FrozenModel
from .source_profiles import PROFILES, AuthenticationMode

LOGGER = get_logger("source_catalog", component="source-catalog")
STRICT_SOURCE_SCHEMA_VERSION = 5


class AccessMode(StrEnum):
    API = "api"
    DOWNLOAD = "download"
    API_AND_DOWNLOAD = "api_and_download"
    WEB_SEARCH = "web_search"
    LICENSED_FEED = "licensed_feed"
    DOCUMENT = "document"


class InterfaceStatus(StrEnum):
    """Whether automation uses a supported interface."""

    SUPPORTED = "supported"
    DOCUMENTED_DOWNLOAD = "documented_download"
    INTERACTIVE_ONLY = "interactive_only"
    RESTRICTED = "restricted"
    UNDOCUMENTED = "undocumented"


class IntegrationLayer(StrEnum):
    """Highest locally evidenced integration layer."""

    CATALOGUED = "catalogued"
    ACQUISITION = "acquisition"
    PARSER = "parser"
    FIXTURE = "fixture"
    LIVE_RECEIPT = "live_receipt"


class SourceReadiness(StrEnum):
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    CANDIDATE = "candidate"
    BLOCKED = "blocked"


class DiscoveryStatus(StrEnum):
    """Evidence level for a catalog declaration, never a currency claim."""

    DISCOVERY_ONLY = "discovery_only"
    DECLARATION_VERIFIED = "declaration_verified"
    RECEIPT_BACKED = "receipt_backed"


class QualificationState(StrEnum):
    """Evidence-backed qualification of a catalog declaration."""

    DECLARED = "declared"
    DOCUMENTATION_VERIFIED = "documentation_verified"
    FIXTURE_VERIFIED = "fixture_verified"
    LIVE_VERIFIED = "live_verified"


class InformationDomain(StrEnum):
    """Controlled description of the information a source can contain."""

    PRODUCT_IDENTITY = "product_identity"
    REGULATORY_STATUS = "regulatory_status"
    FUNDING_STATUS = "funding_status"
    FORMULARY_STATUS = "formulary_status"
    TERMINOLOGY = "terminology"
    CLINICAL_DOCUMENTATION = "clinical_documentation"
    SAFETY = "safety"
    PRICING = "pricing"
    REIMBURSEMENT_CRITERIA = "reimbursement_criteria"
    HTA_DECISION = "hta_decision"


class RecordEntity(StrEnum):
    SUBSTANCE = "substance"
    INGREDIENT = "ingredient"
    MEDICINAL_PRODUCT = "medicinal_product"
    PACKAGED_PRODUCT = "packaged_product"
    APPROVAL = "approval"
    FUNDING_LISTING = "funding_listing"
    FORMULARY_ENTRY = "formulary_entry"
    TERMINOLOGY_CONCEPT = "terminology_concept"
    DOCUMENT = "document"
    PRICE = "price"
    DECISION = "decision"


class StatusSemantics(StrEnum):
    AUTHORIZATION = "authorization"
    REGISTRATION = "registration"
    APPROVAL_HISTORY = "approval_history"
    REIMBURSEMENT = "reimbursement"
    SUBSIDY = "subsidy"
    FORMULARY_INCLUSION = "formulary_inclusion"
    PRICE_LISTING = "price_listing"
    TERMINOLOGY_ONLY = "terminology_only"
    RECOMMENDATION = "recommendation"
    DOCUMENT_ONLY = "document_only"
    MIXED = "mixed"
    NONE = "none"


class GeographicScope(StrEnum):
    NATIONAL = "national"
    SUBNATIONAL = "subnational"
    REGIONAL = "regional"
    GLOBAL = "global"


class PopulationScope(StrEnum):
    GENERAL = "general"
    DEFINED_POPULATION = "defined_population"
    PROGRAMME_SPECIFIC = "programme_specific"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class LanguageCode(StrEnum):
    """BCP 47 primary-language labels used by the current catalog."""

    UNDETERMINED = "und"
    ARABIC = "ar"
    CHINESE = "zh"
    DANISH = "da"
    DUTCH = "nl"
    ENGLISH = "en"
    FRENCH = "fr"
    GERMAN = "de"
    INDONESIAN = "id"
    JAPANESE = "ja"
    KOREAN = "ko"
    MALAY = "ms"
    NORWEGIAN = "no"
    PORTUGUESE = "pt"
    SPANISH = "es"
    SWEDISH = "sv"
    THAI = "th"


class ChangeSemantics(StrEnum):
    CURRENT_STATE = "current_state"
    SNAPSHOT = "snapshot"
    APPEND_ONLY_HISTORY = "append_only_history"
    DELTA = "delta"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class AvailableField(StrEnum):
    IDENTIFIERS = "identifiers"
    NAMES = "names"
    INGREDIENTS = "ingredients"
    STRENGTHS = "strengths"
    DOSAGE_FORMS = "dosage_forms"
    ROUTES = "routes"
    PACKAGES = "packages"
    ORGANISATIONS = "organisations"
    INDICATIONS = "indications"
    STATUS_DATES = "status_dates"
    PRICES = "prices"
    ELIGIBILITY_CRITERIA = "eligibility_criteria"
    DOCUMENTS = "documents"
    SAFETY_NOTICES = "safety_notices"
    TERMINOLOGY_RELATIONSHIPS = "terminology_relationships"


class MonitoringSchedule(FrozenModel):
    """Cadence contract for non-mutating source checks."""

    source_health: str = Field(min_length=1)
    schema_drift: str = Field(min_length=1)


class MedicineDataSource(FrozenModel):
    source_id: str = Field(min_length=1)
    jurisdictions: tuple[str, ...] = Field(min_length=1)
    authority: str = Field(min_length=1)
    title: str = Field(min_length=1)
    dimension: SourceDimension
    access_mode: AccessMode
    interface_status: InterfaceStatus
    formats: tuple[str, ...] = Field(min_length=1)
    authentication: AuthenticationMode
    product_grain: str = Field(min_length=1)
    historical_scope: str = Field(min_length=1)
    native_identifier: str = Field(min_length=1)
    last_verified_at: date
    integration_layer: IntegrationLayer = IntegrationLayer.CATALOGUED
    acquisition_profile: str | None = Field(default=None, min_length=1)
    landing_page: HttpUrl
    documentation_url: HttpUrl
    api_url: HttpUrl | None = None
    download_url: HttpUrl | None = None
    update_cadence: str = Field(min_length=1)
    rights_status: str = Field(min_length=1)
    readiness: SourceReadiness
    discovery_status: DiscoveryStatus = DiscoveryStatus.DISCOVERY_ONLY
    qualification_state: QualificationState = QualificationState.DECLARED
    qualification_references: tuple[str, ...] = ()
    implemented_ingestion: bool = False
    current_receipt_id: str | None = Field(default=None, min_length=1)
    monitoring: MonitoringSchedule = MonitoringSchedule(
        source_health="weekly",
        schema_drift="monthly",
    )
    evidence_limit: str = Field(min_length=1)
    information_domains: tuple[InformationDomain, ...] = (
        InformationDomain.PRODUCT_IDENTITY,
    )
    record_entities: tuple[RecordEntity, ...] = (
        RecordEntity.MEDICINAL_PRODUCT,
    )
    status_semantics: tuple[StatusSemantics, ...] = (StatusSemantics.NONE,)
    geographic_scope: GeographicScope = GeographicScope.NATIONAL
    population_scope: PopulationScope = PopulationScope.UNKNOWN
    languages: tuple[LanguageCode, ...] = (LanguageCode.UNDETERMINED,)
    change_semantics: ChangeSemantics = ChangeSemantics.UNKNOWN
    available_fields: tuple[AvailableField, ...] = (AvailableField.IDENTIFIERS,)

    @classmethod
    def from_legacy(
        cls,
        **value: Any,
    ) -> Self:
        """Migrate an explicit pre-v3 in-memory declaration.

        Catalog JSON never uses this compatibility path: schema-v3 rows must
        declare every governed field themselves.
        """
        payload = dict(value)
        raw_mode = payload.get("access_mode", AccessMode.WEB_SEARCH)
        mode = (
            raw_mode
            if isinstance(raw_mode, AccessMode)
            else AccessMode(str(raw_mode))
        )
        interface_by_mode = {
            AccessMode.API: InterfaceStatus.SUPPORTED,
            AccessMode.API_AND_DOWNLOAD: InterfaceStatus.SUPPORTED,
            AccessMode.DOWNLOAD: InterfaceStatus.DOCUMENTED_DOWNLOAD,
            AccessMode.WEB_SEARCH: InterfaceStatus.INTERACTIVE_ONLY,
            AccessMode.LICENSED_FEED: InterfaceStatus.RESTRICTED,
            AccessMode.DOCUMENT: InterfaceStatus.DOCUMENTED_DOWNLOAD,
        }
        payload.setdefault(
            "interface_status",
            interface_by_mode.get(mode, InterfaceStatus.UNDOCUMENTED),
        )
        payload.setdefault("formats", ("source-defined",))
        payload.setdefault("authentication", AuthenticationMode.UNKNOWN)
        payload.setdefault("product_grain", "source-defined")
        payload.setdefault("historical_scope", "source-defined")
        payload.setdefault("native_identifier", "source-defined")
        payload.setdefault("last_verified_at", date(1970, 1, 1))
        payload.setdefault("documentation_url", payload["landing_page"])
        payload.setdefault(
            "integration_layer",
            IntegrationLayer.PARSER
            if payload.get("implemented_ingestion")
            else IntegrationLayer.CATALOGUED,
        )
        raw_dimension = payload.get("dimension")
        dimension = (
            raw_dimension
            if isinstance(raw_dimension, SourceDimension)
            else SourceDimension(str(raw_dimension))
        )
        semantic_defaults = {
            SourceDimension.REGULATORY: (
                (
                    InformationDomain.PRODUCT_IDENTITY,
                    InformationDomain.REGULATORY_STATUS,
                ),
                (RecordEntity.MEDICINAL_PRODUCT, RecordEntity.APPROVAL),
                (StatusSemantics.AUTHORIZATION,),
            ),
            SourceDimension.FUNDING: (
                (
                    InformationDomain.PRODUCT_IDENTITY,
                    InformationDomain.FUNDING_STATUS,
                ),
                (
                    RecordEntity.MEDICINAL_PRODUCT,
                    RecordEntity.FUNDING_LISTING,
                ),
                (StatusSemantics.REIMBURSEMENT,),
            ),
            SourceDimension.FORMULARY: (
                (
                    InformationDomain.PRODUCT_IDENTITY,
                    InformationDomain.FORMULARY_STATUS,
                ),
                (
                    RecordEntity.MEDICINAL_PRODUCT,
                    RecordEntity.FORMULARY_ENTRY,
                ),
                (StatusSemantics.FORMULARY_INCLUSION,),
            ),
            SourceDimension.TERMINOLOGY: (
                (
                    InformationDomain.PRODUCT_IDENTITY,
                    InformationDomain.TERMINOLOGY,
                ),
                (
                    RecordEntity.MEDICINAL_PRODUCT,
                    RecordEntity.TERMINOLOGY_CONCEPT,
                ),
                (StatusSemantics.TERMINOLOGY_ONLY,),
            ),
        }
        domains, entities, semantics = semantic_defaults[dimension]
        payload.setdefault("information_domains", domains)
        payload.setdefault("record_entities", entities)
        payload.setdefault("status_semantics", semantics)
        payload.setdefault("geographic_scope", GeographicScope.NATIONAL)
        payload.setdefault("population_scope", PopulationScope.UNKNOWN)
        payload.setdefault("languages", (LanguageCode.UNDETERMINED,))
        payload.setdefault("change_semantics", ChangeSemantics.UNKNOWN)
        payload.setdefault("available_fields", (AvailableField.IDENTIFIERS,))
        payload.setdefault("qualification_state", QualificationState.DECLARED)
        payload.setdefault("qualification_references", ())
        return cls.model_validate(payload)

    @model_validator(mode="after")
    def access_surface_matches_mode(self) -> MedicineDataSource:
        if (
            self.access_mode in {AccessMode.API, AccessMode.API_AND_DOWNLOAD}
            and self.api_url is None
        ):
            raise ValueError("API access mode requires api_url")
        if (
            self.access_mode
            in {AccessMode.DOWNLOAD, AccessMode.API_AND_DOWNLOAD}
            and self.download_url is None
        ):
            raise ValueError("download access mode requires download_url")
        if self.current_receipt_id is not None and (
            self.discovery_status != DiscoveryStatus.RECEIPT_BACKED
        ):
            raise ValueError(
                "current receipt requires receipt-backed discovery status"
            )
        if self.implemented_ingestion != (
            self.readiness == SourceReadiness.IMPLEMENTED
        ):
            raise ValueError(
                "implemented_ingestion must agree with implemented readiness"
            )
        if self.implemented_ingestion != (
            self.integration_layer
            in {
                IntegrationLayer.PARSER,
                IntegrationLayer.FIXTURE,
                IntegrationLayer.LIVE_RECEIPT,
            }
        ):
            raise ValueError(
                "implemented_ingestion requires a parser-or-higher "
                "integration layer"
            )
        if self.current_receipt_id is not None and (
            self.integration_layer != IntegrationLayer.LIVE_RECEIPT
        ):
            raise ValueError(
                "current receipt requires live-receipt integration layer"
            )
        if (
            self.qualification_state == QualificationState.LIVE_VERIFIED
            and self.current_receipt_id is None
        ):
            raise ValueError(
                "live-verified qualification requires a current receipt"
            )
        if (
            self.qualification_state != QualificationState.DECLARED
            and not self.qualification_references
        ):
            raise ValueError(
                "verified qualification requires evidence references"
            )
        if (
            self.access_mode
            in {
                AccessMode.WEB_SEARCH,
                AccessMode.DOCUMENT,
            }
            and self.interface_status == InterfaceStatus.SUPPORTED
        ):
            raise ValueError(
                "interactive/document sources are not supported APIs"
            )
        if self.acquisition_profile is not None and self.access_mode not in {
            AccessMode.API,
            AccessMode.DOWNLOAD,
            AccessMode.API_AND_DOWNLOAD,
            AccessMode.LICENSED_FEED,
        }:
            raise ValueError(
                "acquisition profiles require an automatable access mode"
            )
        return self

    @model_validator(mode="after")
    def information_schema_is_semantically_coherent(
        self,
    ) -> MedicineDataSource:
        domains = set(self.information_domains)
        entities = set(self.record_entities)
        semantics = set(self.status_semantics)
        fields = set(self.available_fields)
        required_domain = {
            SourceDimension.REGULATORY: InformationDomain.REGULATORY_STATUS,
            SourceDimension.FUNDING: InformationDomain.FUNDING_STATUS,
            SourceDimension.FORMULARY: InformationDomain.FORMULARY_STATUS,
            SourceDimension.TERMINOLOGY: InformationDomain.TERMINOLOGY,
        }[self.dimension]
        if required_domain not in domains:
            raise ValueError(
                f"{self.dimension.value} sources require "
                f"{required_domain.value} information"
            )
        domain_contracts = {
            InformationDomain.REGULATORY_STATUS: (
                {RecordEntity.APPROVAL},
                {
                    StatusSemantics.AUTHORIZATION,
                    StatusSemantics.REGISTRATION,
                    StatusSemantics.APPROVAL_HISTORY,
                    StatusSemantics.MIXED,
                },
            ),
            InformationDomain.FUNDING_STATUS: (
                {RecordEntity.FUNDING_LISTING},
                {
                    StatusSemantics.REIMBURSEMENT,
                    StatusSemantics.SUBSIDY,
                    StatusSemantics.PRICE_LISTING,
                    StatusSemantics.MIXED,
                },
            ),
            InformationDomain.FORMULARY_STATUS: (
                {RecordEntity.FORMULARY_ENTRY},
                {
                    StatusSemantics.FORMULARY_INCLUSION,
                    StatusSemantics.MIXED,
                },
            ),
            InformationDomain.TERMINOLOGY: (
                {RecordEntity.TERMINOLOGY_CONCEPT},
                {StatusSemantics.TERMINOLOGY_ONLY, StatusSemantics.MIXED},
            ),
        }
        for domain, (required_entities, allowed_semantics) in (
            domain_contracts.items()
        ):
            if domain not in domains:
                continue
            if not required_entities <= entities:
                raise ValueError(
                    f"{domain.value} requires record entities "
                    f"{sorted(item.value for item in required_entities)}"
                )
            if (
                domain != InformationDomain.TERMINOLOGY
                or self.dimension == SourceDimension.TERMINOLOGY
            ) and semantics.isdisjoint(allowed_semantics):
                raise ValueError(
                    f"{domain.value} requires compatible status semantics"
                )
        field_contracts = {
            AvailableField.PRICES: (
                InformationDomain.PRICING,
                RecordEntity.PRICE,
            ),
            AvailableField.SAFETY_NOTICES: (
                InformationDomain.SAFETY,
                RecordEntity.DOCUMENT,
            ),
            AvailableField.TERMINOLOGY_RELATIONSHIPS: (
                InformationDomain.TERMINOLOGY,
                RecordEntity.TERMINOLOGY_CONCEPT,
            ),
        }
        for field, (domain, entity) in field_contracts.items():
            if field in fields and (domain not in domains or entity not in entities):
                raise ValueError(
                    f"{field.value} requires {domain.value} and "
                    f"{entity.value}"
                )
        return self


class RegulatoryDenominator(FrozenModel):
    """WHO discovery-denominator fields awaiting receipt-backed verification."""

    included: bool
    wla: bool | None = None
    ml3: bool | None = None
    ml4: bool | None = None
    status: str = Field(min_length=1)
    evidence_limit: str = Field(min_length=1)


class JurisdictionCensusEntry(FrozenModel):
    jurisdiction: str = Field(min_length=2, max_length=3)
    name: str = Field(min_length=1)
    priority_cohorts: tuple[str, ...] = Field(min_length=1)
    regulatory_denominator: RegulatoryDenominator


class SourceCatalog(FrozenModel):
    schema_version: int = Field(ge=1)
    reviewed_at: date
    monitoring_contract: MonitoringSchedule
    jurisdictions: tuple[JurisdictionCensusEntry, ...]
    sources: tuple[MedicineDataSource, ...]

    @model_validator(mode="before")
    @classmethod
    def governed_rows_are_explicit(cls, value: Any) -> Any:
        """Reject incomplete governed rows before model defaults can apply."""
        if not isinstance(value, dict):
            return value
        payload = cast("dict[str, Any]", value)
        if payload.get("schema_version", 0) < STRICT_SOURCE_SCHEMA_VERSION:
            return payload
        required = {
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
        }
        raw_sources_value: object = payload.get("sources", ())
        if not isinstance(raw_sources_value, (list, tuple)):
            return payload
        raw_sources = cast(
            "list[object] | tuple[object, ...]",
            raw_sources_value,
        )
        for index, raw_source in enumerate(raw_sources):
            if not isinstance(raw_source, dict):
                continue
            source = cast("dict[str, Any]", raw_source)
            missing = sorted(required.difference(source))
            if missing:
                raise ValueError(
                    f"schema-v3 source row {index} is missing: {missing}"
                )
        return payload

    @model_validator(mode="after")
    def monitoring_contract_is_applied(self) -> SourceCatalog:
        if any(
            source.monitoring != self.monitoring_contract
            for source in self.sources
        ):
            raise ValueError(
                "source monitoring must match the catalog monitoring contract"
            )
        declared = {entry.jurisdiction for entry in self.jurisdictions}
        unknown = sorted({
            jurisdiction
            for source in self.sources
            for jurisdiction in source.jurisdictions
            if jurisdiction not in declared and jurisdiction != "GLOBAL"
        })
        if unknown:
            raise ValueError(
                f"source catalog uses undeclared jurisdictions: {unknown}"
            )
        profile_ids = {profile.profile_id for profile in PROFILES}
        missing_profiles = sorted({
            source.acquisition_profile
            for source in self.sources
            if source.acquisition_profile is not None
            and source.acquisition_profile not in profile_ids
        })
        if missing_profiles:
            raise ValueError(
                "source catalog uses undeclared acquisition profiles: "
                f"{missing_profiles}"
            )
        return self


def load_catalog() -> SourceCatalog:
    path = Path(__file__).with_name("data") / "medicine_source_catalog.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    catalog = SourceCatalog.model_validate(payload)
    ids = [source.source_id for source in catalog.sources]
    if len(ids) != len(set(ids)):
        raise ValueError("Source catalog contains duplicate source_id values")
    jurisdiction_ids = [entry.jurisdiction for entry in catalog.jurisdictions]
    if len(jurisdiction_ids) != len(set(jurisdiction_ids)):
        raise ValueError("Source catalog contains duplicate jurisdictions")
    LOGGER.debug(
        "Loaded governed medicine source catalog",
        extra={"source_id": str(path)},
    )
    return catalog


def load_source_catalog() -> tuple[MedicineDataSource, ...]:
    return tuple(
        sorted(load_catalog().sources, key=lambda source: source.source_id)
    )


def sources_for(
    jurisdiction: str,
    dimension: SourceDimension | None = None,
) -> tuple[MedicineDataSource, ...]:
    code = jurisdiction.upper()
    return tuple(
        source
        for source in load_source_catalog()
        if code in source.jurisdictions
        and (dimension is None or source.dimension == dimension)
    )
