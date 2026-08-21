"""Catalog rows for the 36-track bronze source expansion.

Rows use schema v5. They extend the single registry; they are not a second
catalog. Licensing conclusions remain review-required until a human gate.
"""

from __future__ import annotations

from typing import Any

from .countries import SourceDimension
from .source_catalog import (
    AccessMode,
    AvailableField,
    ChangeSemantics,
    DiscoveryStatus,
    GeographicScope,
    InformationDomain,
    IntegrationLayer,
    InterfaceStatus,
    LanguageCode,
    PopulationScope,
    QualificationState,
    RecordEntity,
    SourceReadiness,
    StatusSemantics,
)
from .source_expansion import source_bindings
from .source_profiles import AuthenticationMode

REVIEWED_AT = "2026-08-20"
PRIORITY_AFRICA = "africa"
PRIORITY_EXPANSION = "source_expansion_20260820"

_DENOMINATOR = {
    "included": True,
    "wla": None,
    "ml3": None,
    "ml4": None,
    "status": "pending_receipt_verification",
    "evidence_limit": (
        "Discovery denominator only; no WHO status or product-level claim "
        "without a receipt."
    ),
}


def expansion_jurisdictions() -> tuple[dict[str, Any], ...]:
    rows = (
        ("EGY", "Egypt"),
        ("GHA", "Ghana"),
        ("IRL", "Ireland"),
        ("KEN", "Kenya"),
        ("MUS", "Mauritius"),
        ("PAK", "Pakistan"),
        ("RWA", "Rwanda"),
        ("SEN", "Senegal"),
        ("TZA", "United Republic of Tanzania"),
        ("UGA", "Uganda"),
        ("ZWE", "Zimbabwe"),
    )
    return tuple(
        {
            "jurisdiction": code,
            "name": name,
            "priority_cohorts": [PRIORITY_AFRICA, PRIORITY_EXPANSION]
            if code not in {"IRL", "PAK"}
            else [PRIORITY_EXPANSION],
            "regulatory_denominator": dict(_DENOMINATOR),
        }
        for code, name in rows
    )


def expansion_source_rows() -> tuple[dict[str, Any], ...]:
    rows = (
        *_who_rows(),
        *_africa_rows(),
        *_india_rows(),
        *_fda_rows(),
        *_ema_rows(),
        *_utilisation_rows(),
        *_pv_rows(),
    )
    by_id = {row["source_id"]: row for row in rows}
    return tuple(by_id[key] for key in sorted(by_id))


def existing_source_patches() -> dict[str, dict[str, str]]:
    """Native-identifier and evidence-limit patches for reused rows."""

    patches: dict[str, dict[str, str]] = {}
    for binding in source_bindings():
        if not binding.existing or binding.source_id == (
            "global-medicines-source-index"
        ):
            continue
        patches[binding.source_id] = {
            "native_identifier": binding.native_identifier,
        }
    patches["us-fda-orange-book"]["evidence_limit"] = (
        "Orange Book TE codes are not clinical substitutability; complete "
        "versioned files belong in Bronze, not catalog-only."
    )
    patches["us-openfda-ndc"]["evidence_limit"] = (
        "NDC listing is not approval or reimbursement; preserve product and "
        "package grain separately."
    )
    patches["us-gsrs-unii"]["evidence_limit"] = (
        "UNII/GSRS is terminology/substance evidence, not canonical medicine "
        "identity; Silver crosswalks must not alter Bronze payloads."
    )
    patches["eu-union-register"]["evidence_limit"] = (
        "Union Register must be versioned in Bronze; fixtures are not complete "
        "acquisition. Nationally authorised products remain out of this source."
    )
    patches["eu-ema-article57"]["evidence_limit"] = (
        "Public Article 57 extract is metadata; credentialed xEVMPD is a "
        "separate blocked source. Do not weaken the credential boundary."
    )
    patches["eu-ema-pms-fhir"]["evidence_limit"] = (
        "Credentialed PMS FHIR; metadata-only is not bronze coverage."
    )
    patches["eu-spor-rms-oms"]["evidence_limit"] = (
        "Credentialed SPOR RMS/OMS; metadata-only is not bronze coverage."
    )
    patches["gb-nice-ta"]["evidence_limit"] = (
        "NICE recommendation is not actual funding or utilisation; retain "
        "superseded guidance identities."
    )
    patches["us-cms-partd-formulary"]["evidence_limit"] = (
        "Part D formulary evidence is not total US utilisation or national "
        "registration."
    )
    patches["in-nlem"]["evidence_limit"] = (
        "NLEM is formulary/EML evidence, not automatically reimbursement."
    )
    patches["eu-ema-medicines"]["evidence_limit"] = (
        "Structured EMA medicine rows and EPAR documents are separate artefacts "
        "linked by source-native IDs; extraction must not overwrite structured "
        "fields."
    )
    return patches


def apply_expansion_to_catalog(document: dict[str, Any]) -> dict[str, Any]:
    """Merge expansion jurisdictions and sources into the single registry."""

    document = dict(document)
    document["reviewed_at"] = REVIEWED_AT
    jurisdictions = list(document["jurisdictions"])
    existing_j = {entry["jurisdiction"] for entry in jurisdictions}
    jurisdictions.extend(
        entry
        for entry in expansion_jurisdictions()
        if entry["jurisdiction"] not in existing_j
    )
    document["jurisdictions"] = sorted(
        jurisdictions,
        key=lambda entry: str(entry["jurisdiction"]),
    )
    sources = list(document["sources"])
    by_id = {str(row["source_id"]): row for row in sources}
    for source_id, patch in existing_source_patches().items():
        if source_id in by_id:
            by_id[source_id] = {**by_id[source_id], **patch}
    for row in expansion_source_rows():
        by_id[str(row["source_id"])] = row
    document["sources"] = sorted(
        by_id.values(),
        key=lambda row: str(row["source_id"]),
    )
    return document


def _base(
    source_id: str,
    jurisdictions: tuple[str, ...],
    authority: str,
    title: str,
    dimension: SourceDimension,
    *,
    landing: str,
    documentation: str,
    evidence_limit: str,
    native_identifier: str,
    access_mode: AccessMode,
    interface_status: InterfaceStatus,
    authentication: AuthenticationMode = AuthenticationMode.NONE,
    readiness: SourceReadiness = SourceReadiness.CANDIDATE,
    api_url: str | None = None,
    download_url: str | None = None,
    formats: tuple[str, ...] = ("html",),
    languages: tuple[LanguageCode, ...] = (LanguageCode.ENGLISH,),
    geographic_scope: GeographicScope | None = None,
    domains: tuple[InformationDomain, ...] | None = None,
    entities: tuple[RecordEntity, ...] | None = None,
    semantics: tuple[StatusSemantics, ...] | None = None,
    fields: tuple[AvailableField, ...] | None = None,
    change: ChangeSemantics = ChangeSemantics.SNAPSHOT,
    population: PopulationScope = PopulationScope.GENERAL,
    qualification: QualificationState = QualificationState.DECLARED,
    qualification_references: tuple[str, ...] = (),
    discovery: DiscoveryStatus = DiscoveryStatus.DECLARATION_VERIFIED,
    integration: IntegrationLayer = IntegrationLayer.CATALOGUED,
    acquisition_profile: str | None = None,
    product_grain: str | None = None,
) -> dict[str, Any]:
    dim_defaults = {
        SourceDimension.REGULATORY: (
            (
                InformationDomain.PRODUCT_IDENTITY,
                InformationDomain.REGULATORY_STATUS,
            ),
            (RecordEntity.MEDICINAL_PRODUCT, RecordEntity.APPROVAL),
            (StatusSemantics.AUTHORIZATION,),
            (AvailableField.IDENTIFIERS, AvailableField.NAMES),
        ),
        SourceDimension.FUNDING: (
            (
                InformationDomain.PRODUCT_IDENTITY,
                InformationDomain.FUNDING_STATUS,
            ),
            (RecordEntity.MEDICINAL_PRODUCT, RecordEntity.FUNDING_LISTING),
            (StatusSemantics.MIXED,),
            (AvailableField.IDENTIFIERS, AvailableField.NAMES),
        ),
        SourceDimension.FORMULARY: (
            (
                InformationDomain.PRODUCT_IDENTITY,
                InformationDomain.FORMULARY_STATUS,
            ),
            (RecordEntity.MEDICINAL_PRODUCT, RecordEntity.FORMULARY_ENTRY),
            (StatusSemantics.FORMULARY_INCLUSION,),
            (AvailableField.IDENTIFIERS, AvailableField.NAMES),
        ),
        SourceDimension.TERMINOLOGY: (
            (
                InformationDomain.PRODUCT_IDENTITY,
                InformationDomain.TERMINOLOGY,
            ),
            (RecordEntity.MEDICINAL_PRODUCT, RecordEntity.TERMINOLOGY_CONCEPT),
            (StatusSemantics.TERMINOLOGY_ONLY,),
            (
                AvailableField.IDENTIFIERS,
                AvailableField.NAMES,
                AvailableField.TERMINOLOGY_RELATIONSHIPS,
            ),
        ),
    }
    default_domains, default_entities, default_semantics, default_fields = (
        dim_defaults[dimension]
    )
    if "GLOBAL" in jurisdictions:
        scope = GeographicScope.GLOBAL
    elif geographic_scope is not None:
        scope = geographic_scope
    elif len(jurisdictions) > 1:
        scope = GeographicScope.REGIONAL
    else:
        scope = GeographicScope.NATIONAL
    row: dict[str, Any] = {
        "source_id": source_id,
        "jurisdictions": list(jurisdictions),
        "authority": authority,
        "title": title,
        "dimension": dimension.value,
        "access_mode": access_mode.value,
        "landing_page": landing,
        "update_cadence": "source-declared",
        "rights_status": "review_required",
        "readiness": readiness.value,
        "evidence_limit": evidence_limit,
        "interface_status": interface_status.value,
        "formats": list(formats),
        "authentication": authentication.value,
        "product_grain": product_grain
        or "source-defined medicine, product, package, decision, or document",
        "historical_scope": "source-declared current and historical scope",
        "native_identifier": native_identifier,
        "last_verified_at": REVIEWED_AT,
        "integration_layer": integration.value,
        "implemented_ingestion": False,
        "documentation_url": documentation,
        "discovery_status": discovery.value,
        "information_domains": [
            item.value for item in (domains or default_domains)
        ],
        "record_entities": [
            item.value for item in (entities or default_entities)
        ],
        "status_semantics": [
            item.value for item in (semantics or default_semantics)
        ],
        "geographic_scope": scope.value,
        "population_scope": population.value,
        "languages": [item.value for item in languages],
        "change_semantics": change.value,
        "available_fields": [item.value for item in (fields or default_fields)],
        "qualification_state": qualification.value,
        "qualification_references": list(qualification_references),
    }
    if api_url is not None:
        row["api_url"] = api_url
    if download_url is not None:
        row["download_url"] = download_url
    if acquisition_profile is not None:
        row["acquisition_profile"] = acquisition_profile
    return row


def _who_rows() -> tuple[dict[str, Any], ...]:
    who = "World Health Organization"
    eml = "https://www.who.int/groups/expert-committee-on-selection-and-use-of-essential-medicines/essential-medicines-lists"
    national = f"{eml}/national-essential-medicines-lists"
    amds = "https://www.who.int/teams/global-hiv-hepatitis-and-stis-programmes/hiv/treatment/aids-medicines-and-diagnostics-service"
    prices = "https://www.who.int/teams/health-product-and-policy-standards/medicines-selection-ip-and-affordability/affordability-pricing"
    mi4a = "https://www.who.int/teams/immunization-vaccines-and-biologicals/vaccine-access/mi4a"
    return (
        _base(
            "global-who-eml",
            ("GLOBAL",),
            who,
            "WHO Model List of Essential Medicines",
            SourceDimension.FORMULARY,
            landing=eml,
            documentation=eml,
            evidence_limit=(
                "Global EML is formulary/EML evidence, not reimbursement, "
                "registration, or procurement."
            ),
            native_identifier="WHO EML medicine/section identifier + list year",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url=eml,
            formats=("xlsx", "pdf", "html"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
            geographic_scope=GeographicScope.GLOBAL,
        ),
        _base(
            "global-who-national-eml-index",
            ("GLOBAL",),
            who,
            "WHO index of national essential medicines lists",
            SourceDimension.FORMULARY,
            landing=national,
            documentation=national,
            evidence_limit=(
                "Country/temporal coverage is measured from this index; "
                "unavailable lists are recorded and are not negative evidence."
            ),
            native_identifier="WHO national EML country/list edition",
            access_mode=AccessMode.DOCUMENT,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            formats=("html", "pdf"),
            geographic_scope=GeographicScope.GLOBAL,
        ),
        _base(
            "global-who-amds-gprm",
            ("GLOBAL",),
            who,
            "WHO AMDS / Global Price Reporting Mechanism",
            SourceDimension.FUNDING,
            landing=amds,
            documentation=amds,
            evidence_limit=(
                "AMDS/GPRM procurement prices are not reimbursement, retail, "
                "or list prices; no currency, product, or PPP normalisation."
            ),
            native_identifier="WHO GPRM transaction/product/incoterm identifier",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.INTERACTIVE_ONLY,
            formats=("html", "xlsx"),
            domains=(
                InformationDomain.PRODUCT_IDENTITY,
                InformationDomain.FUNDING_STATUS,
                InformationDomain.PRICING,
            ),
            entities=(
                RecordEntity.MEDICINAL_PRODUCT,
                RecordEntity.FUNDING_LISTING,
                RecordEntity.PRICE,
            ),
            semantics=(StatusSemantics.PRICE_LISTING,),
            fields=(
                AvailableField.IDENTIFIERS,
                AvailableField.NAMES,
                AvailableField.PRICES,
            ),
        ),
        _base(
            "global-who-medicine-prices",
            ("GLOBAL",),
            who,
            "WHO medicines pricing information sources",
            SourceDimension.FUNDING,
            landing=prices,
            documentation=prices,
            evidence_limit=(
                "Price surveys are not reimbursement schedules; datasets are "
                "registered separately from shortage and availability sources."
            ),
            native_identifier="WHO/HAI survey medicine/country/year identifier",
            access_mode=AccessMode.DOCUMENT,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            formats=("html", "pdf", "xlsx"),
            domains=(
                InformationDomain.PRODUCT_IDENTITY,
                InformationDomain.FUNDING_STATUS,
                InformationDomain.PRICING,
            ),
            entities=(
                RecordEntity.MEDICINAL_PRODUCT,
                RecordEntity.FUNDING_LISTING,
                RecordEntity.PRICE,
            ),
            semantics=(StatusSemantics.PRICE_LISTING,),
            fields=(
                AvailableField.IDENTIFIERS,
                AvailableField.NAMES,
                AvailableField.PRICES,
            ),
        ),
        _base(
            "global-who-availability-surveys",
            ("GLOBAL",),
            who,
            "WHO medicines availability survey sources",
            SourceDimension.FORMULARY,
            landing=prices,
            documentation=prices,
            evidence_limit=(
                "Missing survey coverage is not evidence of unavailability or "
                "shortage."
            ),
            native_identifier="WHO/HAI facility-survey wave identifier",
            access_mode=AccessMode.DOCUMENT,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            formats=("html", "pdf"),
        ),
        _base(
            "global-who-shortage-sources",
            ("GLOBAL",),
            who,
            "WHO medicines shortage source inventory",
            SourceDimension.REGULATORY,
            landing="https://www.who.int/teams/regulation-prequalification",
            documentation="https://www.who.int/teams/regulation-prequalification",
            evidence_limit=(
                "No single authoritative WHO global shortage register was "
                "verified; this row inventories the gap. Do not infer shortage "
                "from missing data."
            ),
            native_identifier="WHO shortage source dataset identifier",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.UNDOCUMENTED,
            readiness=SourceReadiness.BLOCKED,
            formats=("html",),
            domains=(
                InformationDomain.PRODUCT_IDENTITY,
                InformationDomain.REGULATORY_STATUS,
                InformationDomain.SAFETY,
            ),
            entities=(
                RecordEntity.MEDICINAL_PRODUCT,
                RecordEntity.APPROVAL,
                RecordEntity.DOCUMENT,
            ),
            fields=(
                AvailableField.IDENTIFIERS,
                AvailableField.NAMES,
                AvailableField.SAFETY_NOTICES,
            ),
        ),
        _base(
            "global-who-mi4a",
            ("GLOBAL",),
            who,
            "WHO MI4A vaccine market information",
            SourceDimension.FUNDING,
            landing=mi4a,
            documentation=mi4a,
            evidence_limit=(
                "MI4A vaccine-market prices and volumes are distinct from "
                "conventional medicines reimbursement and procurement."
            ),
            native_identifier="WHO MI4A vaccine product/market identifier",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url=mi4a,
            formats=("xlsx", "pdf", "html"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
            domains=(
                InformationDomain.PRODUCT_IDENTITY,
                InformationDomain.FUNDING_STATUS,
                InformationDomain.PRICING,
            ),
            entities=(
                RecordEntity.MEDICINAL_PRODUCT,
                RecordEntity.FUNDING_LISTING,
                RecordEntity.PRICE,
            ),
            semantics=(StatusSemantics.PRICE_LISTING,),
            fields=(
                AvailableField.IDENTIFIERS,
                AvailableField.NAMES,
                AvailableField.PRICES,
            ),
        ),
    )


def _africa_family(
    *,
    code: str,
    prefix: str,
    authority: str,
    register_title: str,
    landing: str,
    language: LanguageCode,
    register_native: str,
    eml_native: str,
    safety_native: str,
    extra: tuple[dict[str, Any], ...] = (),
) -> tuple[dict[str, Any], ...]:
    safety_domains = (
        InformationDomain.PRODUCT_IDENTITY,
        InformationDomain.REGULATORY_STATUS,
        InformationDomain.SAFETY,
    )
    safety_entities = (
        RecordEntity.MEDICINAL_PRODUCT,
        RecordEntity.APPROVAL,
        RecordEntity.DOCUMENT,
    )
    safety_fields = (
        AvailableField.IDENTIFIERS,
        AvailableField.NAMES,
        AvailableField.SAFETY_NOTICES,
        AvailableField.DOCUMENTS,
    )
    register = _base(
        f"{prefix}-register" if prefix != "tz-tmda" else "tz-tmda-products",
        (code,),
        authority,
        register_title,
        SourceDimension.REGULATORY,
        landing=landing,
        documentation=landing,
        evidence_limit=(
            "Registration evidence is not formulary, reimbursement, or current "
            "status from historical presence or absence."
        ),
        native_identifier=register_native,
        access_mode=AccessMode.WEB_SEARCH,
        interface_status=InterfaceStatus.INTERACTIVE_ONLY,
        languages=(language,),
        product_grain="source-native registered product + manufacturer/sponsor",
    )
    if prefix == "mus-pharmacy-board":
        register["source_id"] = "mus-pharmacy-board-register"
    eml = _base(
        f"{prefix.split('-', maxsplit=1)[0]}-national-eml"
        if prefix != "pk-drap"
        else "pk-neml",
        (code,),
        authority,
        f"{code} essential medicines / health-supplies list",
        SourceDimension.FORMULARY,
        landing=landing,
        documentation=landing,
        evidence_limit=(
            "EML/formulary evidence is not automatically reimbursement or "
            "registration."
        ),
        native_identifier=eml_native,
        access_mode=AccessMode.DOCUMENT,
        interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
        languages=(language,),
        formats=("pdf", "html"),
    )
    if prefix == "ug-nda":
        eml["source_id"] = "ug-national-eml"
        eml["title"] = "Uganda EML and health supplies list"
    elif prefix == "ke-ppb":
        eml["source_id"] = "ke-national-eml"
    elif prefix == "tz-tmda":
        eml["source_id"] = "tz-national-eml"
    elif prefix == "eg-eda":
        eml["source_id"] = "eg-national-eml"
        eml["languages"] = [
            LanguageCode.ARABIC.value,
            LanguageCode.ENGLISH.value,
        ]
    elif prefix == "gh-fda":
        eml["source_id"] = "gh-national-eml"
    elif prefix == "rw-rwandafda":
        eml["source_id"] = "rw-national-eml"
    elif prefix == "sn-dpm":
        eml["source_id"] = "sn-national-eml"
        eml["languages"] = [LanguageCode.FRENCH.value]
    elif prefix == "zw-mcaz":
        eml["source_id"] = "zw-national-eml"
    safety = _base(
        f"{prefix}-safety",
        (code,),
        authority,
        f"{authority} public safety/recall notices",
        SourceDimension.REGULATORY,
        landing=landing,
        documentation=landing,
        evidence_limit=(
            "Safety/recall notices are not registration status, shortage "
            "evidence, or causality beyond the regulator statement."
        ),
        native_identifier=safety_native,
        access_mode=AccessMode.WEB_SEARCH,
        interface_status=InterfaceStatus.INTERACTIVE_ONLY,
        languages=(language,),
        domains=safety_domains,
        entities=safety_entities,
        fields=safety_fields,
    )
    if prefix == "pk-drap":
        safety["source_id"] = "pk-drap-safety"
        safety["evidence_limit"] += (
            " Distinguish provisional, registered, and historical source-native "
            "states; shortage notices stay a separate facet of this source."
        )
        register["source_id"] = "pk-drap-register"
    return (register, eml, safety, *extra)


def _africa_rows() -> tuple[dict[str, Any], ...]:
    mauritius_eml = _base(
        "mus-approved-drug-list",
        ("MUS",),
        "Mauritius Ministry of Health and Wellness",
        "Mauritius Approved Drug List / EML",
        SourceDimension.FORMULARY,
        landing="https://health.govmu.org/",
        documentation="https://health.govmu.org/",
        evidence_limit=(
            "Approved Drug List is formulary evidence, not registration or "
            "reimbursement."
        ),
        native_identifier="Mauritius Approved Drug List / EML entry identifier",
        access_mode=AccessMode.DOCUMENT,
        interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
        formats=("pdf", "html"),
        languages=(LanguageCode.ENGLISH, LanguageCode.FRENCH),
    )
    historical = _base(
        "mus-historical-eml-archive",
        ("MUS",),
        "Mauritius Ministry of Health and Wellness",
        "Mauritius historical EML/Approved Drug List editions",
        SourceDimension.FORMULARY,
        landing="https://health.govmu.org/",
        documentation="https://health.govmu.org/",
        evidence_limit=(
            "Historical editions are archived only where lawful; absence of an "
            "edition is not negative formulary evidence."
        ),
        native_identifier="Mauritius historical EML edition identifier",
        access_mode=AccessMode.DOCUMENT,
        interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
        formats=("pdf",),
        languages=(LanguageCode.ENGLISH, LanguageCode.FRENCH),
        change=ChangeSemantics.APPEND_ONLY_HISTORY,
    )
    families = (
        _africa_family(
            code="UGA",
            prefix="ug-nda",
            authority="Uganda National Drug Authority",
            register_title="Uganda NDA product register",
            landing="https://www.nda.or.ug/",
            language=LanguageCode.ENGLISH,
            register_native="Uganda NDA product/registration number",
            eml_native="Uganda EML/health supplies list entry",
            safety_native="Uganda NDA safety/recall notice identifier",
        ),
        _africa_family(
            code="KEN",
            prefix="ke-ppb",
            authority="Kenya Pharmacy and Poisons Board",
            register_title="Kenya PPB product register",
            landing="https://www.pharmacyboardkenya.org/",
            language=LanguageCode.ENGLISH,
            register_native="Kenya PPB product registration number",
            eml_native="Kenya EML/formulary entry identifier",
            safety_native="Kenya PPB safety/recall notice identifier",
        ),
        _africa_family(
            code="TZA",
            prefix="tz-tmda",
            authority="Tanzania Medicines and Medical Devices Authority",
            register_title="TMDA registered products",
            landing="https://www.tmda.go.tz/",
            language=LanguageCode.ENGLISH,
            register_native="TMDA product registration number + manufacturer/sponsor",
            eml_native="Tanzania EML entry identifier",
            safety_native="TMDA safety notice identifier",
        ),
        _africa_family(
            code="PAK",
            prefix="pk-drap",
            authority="Pakistan Drug Regulatory Authority",
            register_title="DRAP registered/provisional products",
            landing="https://www.dra.gov.pk/",
            language=LanguageCode.ENGLISH,
            register_native=(
                "DRAP registration/provisional/historical native status identifier"
            ),
            eml_native="Pakistan NEML entry identifier",
            safety_native="DRAP safety/recall/shortage notice identifier",
        ),
        _africa_family(
            code="EGY",
            prefix="eg-eda",
            authority="Egyptian Drug Authority",
            register_title="Egypt EDA product register",
            landing="https://www.edaegypt.gov.eg/",
            language=LanguageCode.ARABIC,
            register_native="Egypt EDA product registration number",
            eml_native="Egypt EML entry identifier",
            safety_native="Egypt EDA safety notice identifier",
        ),
        _africa_family(
            code="GHA",
            prefix="gh-fda",
            authority="Ghana Food and Drugs Authority",
            register_title="Ghana FDA product register",
            landing="https://fdaghana.gov.gh/",
            language=LanguageCode.ENGLISH,
            register_native="Ghana FDA product registration number",
            eml_native="Ghana EML/STG entry identifier",
            safety_native="Ghana FDA safety/recall identifier",
        ),
        _africa_family(
            code="RWA",
            prefix="rw-rwandafda",
            authority="Rwanda Food and Drugs Authority",
            register_title="Rwanda FDA product register",
            landing="https://rwandafda.gov.rw/",
            language=LanguageCode.ENGLISH,
            register_native="Rwanda FDA product registration number",
            eml_native="Rwanda EML entry identifier",
            safety_native="Rwanda FDA safety notice identifier",
        ),
        _africa_family(
            code="SEN",
            prefix="sn-dpm",
            authority="Senegal Direction de la Pharmacie et du Médicament",
            register_title="Senegal DPM product register",
            landing="https://www.sante.gouv.sn/",
            language=LanguageCode.FRENCH,
            register_native="Senegal DPM product registration number",
            eml_native="Senegal EML/LNME entry identifier",
            safety_native="Senegal DPM safety notice identifier",
        ),
        _africa_family(
            code="ZWE",
            prefix="zw-mcaz",
            authority="Medicines Control Authority of Zimbabwe",
            register_title="MCAZ product register",
            landing="https://www.mcaz.co.zw/",
            language=LanguageCode.ENGLISH,
            register_native="MCAZ product registration number",
            eml_native="Zimbabwe EML entry identifier",
            safety_native="MCAZ safety/recall identifier",
        ),
        _africa_family(
            code="MUS",
            prefix="mus-pharmacy-board",
            authority="Mauritius Pharmacy Board",
            register_title="Mauritius public product registration",
            landing="https://health.govmu.org/",
            language=LanguageCode.ENGLISH,
            register_native="Mauritius Pharmacy Board product registration number",
            eml_native="Mauritius EML entry identifier",
            safety_native="Mauritius safety/recall notice identifier",
            extra=(mauritius_eml, historical),
        ),
    )
    nigeria_safety = _base(
        "ng-nafdac-safety",
        ("NGA",),
        "National Agency for Food and Drug Administration and Control",
        "NAFDAC public safety/recall notices",
        SourceDimension.REGULATORY,
        landing="https://www.nafdac.gov.ng/",
        documentation="https://www.nafdac.gov.ng/",
        evidence_limit=(
            "Safety/recall notices are not NAFDAC registration or NHIA "
            "formulary evidence."
        ),
        native_identifier="NAFDAC safety/recall notice identifier",
        access_mode=AccessMode.WEB_SEARCH,
        interface_status=InterfaceStatus.INTERACTIVE_ONLY,
        domains=(
            InformationDomain.PRODUCT_IDENTITY,
            InformationDomain.REGULATORY_STATUS,
            InformationDomain.SAFETY,
        ),
        entities=(
            RecordEntity.MEDICINAL_PRODUCT,
            RecordEntity.APPROVAL,
            RecordEntity.DOCUMENT,
        ),
        fields=(
            AvailableField.IDENTIFIERS,
            AvailableField.NAMES,
            AvailableField.SAFETY_NOTICES,
        ),
    )
    south_africa_safety = _base(
        "za-sahpra-safety",
        ("ZAF",),
        "South African Health Products Regulatory Authority",
        "SAHPRA public safety/recall notices",
        SourceDimension.REGULATORY,
        landing="https://www.sahpra.org.za/",
        documentation="https://www.sahpra.org.za/",
        evidence_limit=(
            "Safety/recall notices are not SAHPRA registration or NEML "
            "inclusion."
        ),
        native_identifier="SAHPRA safety/recall notice identifier",
        access_mode=AccessMode.WEB_SEARCH,
        interface_status=InterfaceStatus.INTERACTIVE_ONLY,
        domains=(
            InformationDomain.PRODUCT_IDENTITY,
            InformationDomain.REGULATORY_STATUS,
            InformationDomain.SAFETY,
        ),
        entities=(
            RecordEntity.MEDICINAL_PRODUCT,
            RecordEntity.APPROVAL,
            RecordEntity.DOCUMENT,
        ),
        fields=(
            AvailableField.IDENTIFIERS,
            AvailableField.NAMES,
            AvailableField.SAFETY_NOTICES,
        ),
    )
    rows: list[dict[str, Any]] = []
    for family in families:
        rows.extend(family)
    rows.extend((nigeria_safety, south_africa_safety))
    # Mauritius family also emitted a national-eml clone; drop duplicate id.
    by_id = {row["source_id"]: row for row in rows}
    by_id.pop("mus-national-eml", None)
    return tuple(by_id[key] for key in sorted(by_id))


def _india_rows() -> tuple[dict[str, Any], ...]:
    cdsco = "https://cdsco.gov.in/"
    nppa = "https://www.nppaindia.nic.in/"
    pvpi = "https://www.ipc.gov.in/PvPI/pv_home.html"
    return (
        _base(
            "in-cdsco-products",
            ("IND",),
            "Central Drugs Standard Control Organisation",
            "CDSCO public product/license surfaces beyond the approved-drugs seed",
            SourceDimension.REGULATORY,
            landing=cdsco,
            documentation=cdsco,
            evidence_limit=(
                "Product/license listings are not NLEM inclusion or NPPA ceiling "
                "prices."
            ),
            native_identifier="CDSCO product/license identifier",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.INTERACTIVE_ONLY,
        ),
        _base(
            "in-nppa-ceiling-prices",
            ("IND",),
            "National Pharmaceutical Pricing Authority",
            "NPPA ceiling prices",
            SourceDimension.FUNDING,
            landing=nppa,
            documentation=nppa,
            evidence_limit=(
                "Ceiling price is not a transaction, procurement, or "
                "reimbursement price."
            ),
            native_identifier="NPPA scheduled-formulation ceiling-price identifier",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url=nppa,
            formats=("xlsx", "pdf", "html"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
            domains=(
                InformationDomain.PRODUCT_IDENTITY,
                InformationDomain.FUNDING_STATUS,
                InformationDomain.PRICING,
            ),
            entities=(
                RecordEntity.MEDICINAL_PRODUCT,
                RecordEntity.FUNDING_LISTING,
                RecordEntity.PRICE,
            ),
            semantics=(StatusSemantics.PRICE_LISTING,),
            fields=(
                AvailableField.IDENTIFIERS,
                AvailableField.NAMES,
                AvailableField.PRICES,
            ),
        ),
        _base(
            "in-procurement-availability",
            ("IND",),
            "Government of India public procurement portals",
            "India public medicines procurement/availability surfaces",
            SourceDimension.FUNDING,
            landing="https://gem.gov.in/",
            documentation="https://gem.gov.in/",
            evidence_limit=(
                "Procurement/availability is not NPPA ceiling price or "
                "reimbursement; state portals remain separately blocked."
            ),
            native_identifier="India public procurement/availability source identifier",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.INTERACTIVE_ONLY,
            domains=(
                InformationDomain.PRODUCT_IDENTITY,
                InformationDomain.FUNDING_STATUS,
                InformationDomain.PRICING,
            ),
            entities=(
                RecordEntity.MEDICINAL_PRODUCT,
                RecordEntity.FUNDING_LISTING,
                RecordEntity.PRICE,
            ),
            semantics=(StatusSemantics.PRICE_LISTING,),
            fields=(
                AvailableField.IDENTIFIERS,
                AvailableField.NAMES,
                AvailableField.PRICES,
            ),
        ),
        _base(
            "in-pvpi-safety",
            ("IND",),
            "Pharmacovigilance Programme of India",
            "PvPI public safety communications",
            SourceDimension.REGULATORY,
            landing=pvpi,
            documentation=pvpi,
            evidence_limit=(
                "PvPI case-level ICSRs are not public bronze payloads; this row "
                "is metadata/safety-communication inventory only."
            ),
            native_identifier="PvPI safety communication identifier",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.RESTRICTED,
            authentication=AuthenticationMode.ACCOUNT,
            readiness=SourceReadiness.BLOCKED,
            domains=(
                InformationDomain.PRODUCT_IDENTITY,
                InformationDomain.REGULATORY_STATUS,
                InformationDomain.SAFETY,
            ),
            entities=(
                RecordEntity.MEDICINAL_PRODUCT,
                RecordEntity.APPROVAL,
                RecordEntity.DOCUMENT,
            ),
            fields=(
                AvailableField.IDENTIFIERS,
                AvailableField.NAMES,
                AvailableField.SAFETY_NOTICES,
            ),
        ),
    )


def _fda_rows() -> tuple[dict[str, Any], ...]:
    faers = "https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html"
    nsde = "https://www.fda.gov/industry/structured-product-labeling-resources/nsde"
    fda = "US Food and Drug Administration"
    safety = (
        InformationDomain.PRODUCT_IDENTITY,
        InformationDomain.REGULATORY_STATUS,
        InformationDomain.SAFETY,
    )
    safety_entities = (
        RecordEntity.MEDICINAL_PRODUCT,
        RecordEntity.APPROVAL,
        RecordEntity.DOCUMENT,
    )
    safety_fields = (
        AvailableField.IDENTIFIERS,
        AvailableField.NAMES,
        AvailableField.SAFETY_NOTICES,
        AvailableField.DOCUMENTS,
    )
    return (
        _base(
            "us-fda-faers",
            ("USA",),
            fda,
            "FDA FAERS quarterly public ASCII/XML releases",
            SourceDimension.REGULATORY,
            landing=faers,
            documentation=faers,
            evidence_limit=(
                "FAERS reports are not causation. Bronze keeps native case "
                "identity for later FDA case-version handling; no dedup or "
                "normalisation beyond lossless parse."
            ),
            native_identifier="FAERS primaryid / caseid (case-version retained)",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url=faers,
            formats=("zip", "ascii", "xml"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
            domains=safety,
            entities=safety_entities,
            fields=safety_fields,
            change=ChangeSemantics.APPEND_ONLY_HISTORY,
        ),
        _base(
            "us-openfda-faers",
            ("USA",),
            fda,
            "openFDA drug adverse-event API (FAERS-derived)",
            SourceDimension.REGULATORY,
            landing="https://open.fda.gov/apis/drug/event/",
            documentation="https://open.fda.gov/apis/drug/event/",
            evidence_limit=(
                "Overlaps FAERS files; do not silent-dedup. Reports are not "
                "causation. openFDA is derived, not evidentiary origin."
            ),
            native_identifier="openFDA safetyreportid overlapping FAERS files",
            access_mode=AccessMode.API,
            interface_status=InterfaceStatus.SUPPORTED,
            api_url="https://api.fda.gov/drug/event.json",
            formats=("json",),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-rest",
            domains=safety,
            entities=safety_entities,
            fields=safety_fields,
        ),
        _base(
            "us-openfda-enforcement",
            ("USA",),
            fda,
            "openFDA drug enforcement/recalls API",
            SourceDimension.REGULATORY,
            landing="https://open.fda.gov/apis/drug/enforcement/",
            documentation="https://open.fda.gov/apis/drug/enforcement/",
            evidence_limit=(
                "Enforcement API overlaps FDA recall notices; model the "
                "relationship and do not silent-dedup."
            ),
            native_identifier="openFDA enforcement report number / event_id",
            access_mode=AccessMode.API,
            interface_status=InterfaceStatus.SUPPORTED,
            api_url="https://api.fda.gov/drug/enforcement.json",
            formats=("json",),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-rest",
            domains=safety,
            entities=safety_entities,
            fields=safety_fields,
        ),
        _base(
            "us-fda-recalls-notices",
            ("USA",),
            fda,
            "FDA recall, market-withdrawal, and safety-alert notices",
            SourceDimension.REGULATORY,
            landing="https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts",
            documentation="https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts",
            evidence_limit=(
                "Firm press notices overlap openFDA enforcement; keep both "
                "identities. Recalls are not FAERS causality."
            ),
            native_identifier="FDA recall firm-press notice identifier",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.INTERACTIVE_ONLY,
            domains=safety,
            entities=safety_entities,
            fields=safety_fields,
        ),
        _base(
            "us-fda-drug-shortages",
            ("USA",),
            fda,
            "FDA drug shortages current and historical snapshots",
            SourceDimension.REGULATORY,
            landing="https://www.accessdata.fda.gov/scripts/drugshortages/default.cfm",
            documentation="https://www.fda.gov/drugs/drug-safety-and-availability/drug-shortages",
            evidence_limit=(
                "Absence from the current shortage list is not evidence of no "
                "historical shortage; missing coverage is not negative evidence."
            ),
            native_identifier="FDA shortage drug/update identifier + snapshot date",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.INTERACTIVE_ONLY,
            domains=safety,
            entities=safety_entities,
            fields=safety_fields,
            change=ChangeSemantics.SNAPSHOT,
        ),
        _base(
            "us-fda-rems",
            ("USA",),
            fda,
            "FDA Risk Evaluation and Mitigation Strategies",
            SourceDimension.REGULATORY,
            landing="https://www.accessdata.fda.gov/scripts/cder/rems/index.cfm",
            documentation="https://www.accessdata.fda.gov/scripts/cder/rems/index.cfm",
            evidence_limit=(
                "REMS is distinct from approval and from pharmacovigilance. "
                "Documents are payloads; structural metadata stays source-faithful."
            ),
            native_identifier="FDA REMS program/application identifier",
            access_mode=AccessMode.DOCUMENT,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            formats=("html", "pdf"),
            domains=(
                InformationDomain.PRODUCT_IDENTITY,
                InformationDomain.REGULATORY_STATUS,
                InformationDomain.CLINICAL_DOCUMENTATION,
            ),
            entities=(
                RecordEntity.MEDICINAL_PRODUCT,
                RecordEntity.APPROVAL,
                RecordEntity.DOCUMENT,
            ),
            semantics=(
                StatusSemantics.AUTHORIZATION,
                StatusSemantics.DOCUMENT_ONLY,
            ),
            fields=(
                AvailableField.IDENTIFIERS,
                AvailableField.NAMES,
                AvailableField.DOCUMENTS,
            ),
        ),
        _base(
            "us-fda-ndc-directory",
            ("USA",),
            fda,
            "FDA NDC Directory files",
            SourceDimension.TERMINOLOGY,
            landing="https://www.fda.gov/drugs/drug-approvals-and-databases/national-drug-code-directory",
            documentation="https://www.fda.gov/drugs/drug-approvals-and-databases/national-drug-code-directory",
            evidence_limit=(
                "NDC listing is not approval. Preserve product versus package "
                "granularity; do not treat this as Orange Book substitutability."
            ),
            native_identifier="FDA NDC Directory product/package NDC",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url="https://www.fda.gov/drugs/drug-approvals-and-databases/national-drug-code-directory",
            formats=("zip", "txt"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
        ),
        _base(
            "us-fda-nsde",
            ("USA",),
            fda,
            "FDA NDC SPL Data Elements (NSDE) comprehensive file",
            SourceDimension.TERMINOLOGY,
            landing=nsde,
            documentation=nsde,
            evidence_limit=(
                "Verified authoritative dataset is the FDA SPL NSDE zip on "
                f"{nsde}. NSDE/NDC listing is not approval or reimbursement. "
                "openFDA /other/nsde is a derived API, not the origin."
            ),
            native_identifier="NSDE item code / NDC11 from FDA SPL NSDE zip",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url=nsde,
            formats=("zip", "txt"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
        ),
        _base(
            "us-openfda-nsde",
            ("USA",),
            fda,
            "openFDA NSDE API (derived from FDA NSDE)",
            SourceDimension.TERMINOLOGY,
            landing="https://open.fda.gov/apis/other/nsde/",
            documentation="https://open.fda.gov/apis/other/nsde/",
            evidence_limit=(
                "Derived API over FDA NSDE; not the authoritative file and not "
                "an approval register."
            ),
            native_identifier="openFDA other/nsde package_ndc",
            access_mode=AccessMode.API,
            interface_status=InterfaceStatus.SUPPORTED,
            api_url="https://api.fda.gov/other/nsde.json",
            formats=("json",),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-rest",
        ),
    )


def _ema_rows() -> tuple[dict[str, Any], ...]:
    ema = "European Medicines Agency"
    medicines = "https://www.ema.europa.eu/en/medicines/download-medicine-data"
    epar = "https://www.ema.europa.eu/en/medicines"
    adr = "https://www.adrreports.eu/"
    orphan = "https://www.ema.europa.eu/en/human-regulatory-overview/orphan-designation-overview"
    referrals = medicines
    safety = "https://www.ema.europa.eu/en/human-regulatory-overview/post-authorisation/pharmacovigilance-post-authorisation/safety-communication"
    xevmpd = "https://www.ema.europa.eu/en/human-regulatory-overview/post-authorisation/data-medicines-iso-idmp-standards-post-authorisation"
    spor = "https://spor.ema.europa.eu/sporwi/"
    safety_domains = (
        InformationDomain.PRODUCT_IDENTITY,
        InformationDomain.REGULATORY_STATUS,
        InformationDomain.SAFETY,
    )
    safety_entities = (
        RecordEntity.MEDICINAL_PRODUCT,
        RecordEntity.APPROVAL,
        RecordEntity.DOCUMENT,
    )
    safety_fields = (
        AvailableField.IDENTIFIERS,
        AvailableField.NAMES,
        AvailableField.SAFETY_NOTICES,
        AvailableField.DOCUMENTS,
    )
    docs_domains = (
        InformationDomain.PRODUCT_IDENTITY,
        InformationDomain.REGULATORY_STATUS,
        InformationDomain.CLINICAL_DOCUMENTATION,
    )
    docs_entities = (
        RecordEntity.MEDICINAL_PRODUCT,
        RecordEntity.APPROVAL,
        RecordEntity.DOCUMENT,
    )
    return (
        _base(
            "eu-ema-epar-documents",
            ("EU",),
            ema,
            "EMA EPAR and medicine documents",
            SourceDimension.REGULATORY,
            landing=epar,
            documentation=medicines,
            evidence_limit=(
                "EPAR documents are separate from structured EMA medicine rows "
                "and are linked by source-native IDs; extraction must not "
                "overwrite structured fields."
            ),
            native_identifier="EPAR document identifier linked to EMA product number",
            access_mode=AccessMode.DOCUMENT,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            formats=("pdf", "html"),
            geographic_scope=GeographicScope.REGIONAL,
            domains=docs_domains,
            entities=docs_entities,
            semantics=(
                StatusSemantics.AUTHORIZATION,
                StatusSemantics.DOCUMENT_ONLY,
            ),
            fields=(
                AvailableField.IDENTIFIERS,
                AvailableField.NAMES,
                AvailableField.DOCUMENTS,
            ),
        ),
        _base(
            "eu-eudravigilance-public",
            ("EU",),
            ema,
            "EudraVigilance public ADR dashboard",
            SourceDimension.REGULATORY,
            landing=adr,
            documentation=adr,
            evidence_limit=(
                "Public EudraVigilance outputs are not unrestricted case-level "
                "data; access and redistribution constraints remain. Not "
                "equivalent to FAERS quarterly files."
            ),
            native_identifier="adrreports.eu aggregated reaction identifier",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.RESTRICTED,
            authentication=AuthenticationMode.ACCOUNT,
            readiness=SourceReadiness.BLOCKED,
            geographic_scope=GeographicScope.REGIONAL,
            domains=safety_domains,
            entities=safety_entities,
            fields=safety_fields,
        ),
        _base(
            "eu-ema-orphan",
            ("EU",),
            ema,
            "EMA orphan medicinal product designations",
            SourceDimension.REGULATORY,
            landing=orphan,
            documentation=orphan,
            evidence_limit=(
                "Orphan designation is distinct from marketing authorisation; "
                "retain sponsor as a source-native field."
            ),
            native_identifier="EMA orphan designation number + sponsor",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url=medicines,
            formats=("xlsx", "html"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
            geographic_scope=GeographicScope.REGIONAL,
            product_grain="orphan designation + sponsor organisation",
        ),
        _base(
            "eu-ema-referrals",
            ("EU",),
            ema,
            "EMA referral procedures",
            SourceDimension.REGULATORY,
            landing=epar,
            documentation=referrals,
            evidence_limit=(
                "Referral events are regulatory procedures and must not collapse "
                "into ordinary approval status."
            ),
            native_identifier="EMA referral procedure number",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url=medicines,
            formats=("xlsx", "html"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
            geographic_scope=GeographicScope.REGIONAL,
        ),
        _base(
            "eu-ema-safety-communications",
            ("EU",),
            ema,
            "EMA safety communications",
            SourceDimension.REGULATORY,
            landing=safety,
            documentation=safety,
            evidence_limit=(
                "Do not infer causality beyond the regulator statement. Safety "
                "communications are not EudraVigilance case data."
            ),
            native_identifier="EMA safety communication identifier",
            access_mode=AccessMode.DOCUMENT,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            formats=("html", "pdf"),
            geographic_scope=GeographicScope.REGIONAL,
            domains=safety_domains,
            entities=safety_entities,
            fields=safety_fields,
        ),
        _base(
            "eu-ema-xevmpd-credentialed",
            ("EU",),
            ema,
            "xEVMPD credentialed product dictionary",
            SourceDimension.REGULATORY,
            landing=xevmpd,
            documentation=xevmpd,
            evidence_limit=(
                "Credentialed xEVMPD payloads are out of bronze ingest. Public "
                "Article 57 metadata remains a separate catalog source."
            ),
            native_identifier="xEVMPD EV Code (credentialed payload)",
            access_mode=AccessMode.LICENSED_FEED,
            interface_status=InterfaceStatus.RESTRICTED,
            authentication=AuthenticationMode.ACCOUNT,
            readiness=SourceReadiness.BLOCKED,
            download_url=xevmpd,
            formats=("xml",),
            integration=IntegrationLayer.CATALOGUED,
            acquisition_profile="account-download",
            geographic_scope=GeographicScope.REGIONAL,
        ),
        _base(
            "eu-spor-public-metadata",
            ("EU",),
            ema,
            "SPOR public RMS/OMS metadata",
            SourceDimension.TERMINOLOGY,
            landing=spor,
            documentation=spor,
            evidence_limit=(
                "Public SPOR metadata is not PMS coverage. Credentialed PMS/RMS/"
                "OMS payloads stay metadata-only and are not bronze coverage."
            ),
            native_identifier="Public SPOR/RMS/OMS metadata identifier",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.INTERACTIVE_ONLY,
            geographic_scope=GeographicScope.REGIONAL,
        ),
    )


def _utilisation_rows() -> tuple[dict[str, Any], ...]:
    funding_util = (
        InformationDomain.PRODUCT_IDENTITY,
        InformationDomain.FUNDING_STATUS,
    )
    funding_entities = (
        RecordEntity.MEDICINAL_PRODUCT,
        RecordEntity.FUNDING_LISTING,
    )
    return (
        _base(
            "gb-nice-medicines-utilisation",
            ("GBR",),
            "NHS England / NHS Digital utilisation publications",
            "Use of NICE-appraised medicines",
            SourceDimension.FUNDING,
            landing="https://www.england.nhs.uk/",
            documentation="https://digital.nhs.uk/",
            evidence_limit=(
                "Utilisation of NICE-appraised medicines is not NICE funding "
                "status. Methodology and denominator changes are retained; no "
                "universal utilisation unit is forced."
            ),
            native_identifier="NHS utilisation series identifier + methodology version",
            access_mode=AccessMode.DOCUMENT,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            formats=("xlsx", "csv", "html"),
            domains=funding_util,
            entities=funding_entities,
            semantics=(StatusSemantics.MIXED,),
            population=PopulationScope.PROGRAMME_SPECIFIC,
        ),
        _base(
            "gb-openprescribing",
            ("GBR",),
            "Bennett Institute for Applied Data Science / NHSBSA EPD",
            "OpenPrescribing English primary-care prescribing",
            SourceDimension.FUNDING,
            landing="https://openprescribing.net/",
            documentation="https://openprescribing.net/api/",
            evidence_limit=(
                "England primary-care prescribing only. Rights and volume "
                "constraints apply; no cross-country measure normalisation."
            ),
            native_identifier="BNF presentation code + practice/CCG + month",
            access_mode=AccessMode.API_AND_DOWNLOAD,
            interface_status=InterfaceStatus.SUPPORTED,
            api_url="https://openprescribing.net/api/1.0/",
            download_url="https://openprescribing.net/api/",
            formats=("json", "csv"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-rest",
            domains=funding_util,
            entities=funding_entities,
            semantics=(StatusSemantics.MIXED,),
            population=PopulationScope.DEFINED_POPULATION,
        ),
        _base(
            "us-cms-partd-spending",
            ("USA",),
            "Centers for Medicare & Medicaid Services",
            "Medicare Part D spending by drug",
            SourceDimension.FUNDING,
            landing="https://data.cms.gov/summary-statistics-on-use-and-payments/medicare-medicaid-spending-by-drug/medicare-part-d-spending-by-drug",
            documentation="https://data.cms.gov/summary-statistics-on-use-and-payments/medicare-medicaid-spending-by-drug/medicare-part-d-spending-by-drug",
            evidence_limit=(
                "Part D spending/utilisation is not total US utilisation and is "
                "not a national registration or formulary completeness claim."
            ),
            native_identifier="CMS Part D spending-by-drug brand/generic identifier",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url="https://data.cms.gov/summary-statistics-on-use-and-payments/medicare-medicaid-spending-by-drug/medicare-part-d-spending-by-drug",
            formats=("csv", "xlsx"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
            domains=funding_util,
            entities=funding_entities,
            semantics=(StatusSemantics.MIXED,),
            population=PopulationScope.DEFINED_POPULATION,
        ),
        _base(
            "nl-gipdatabank",
            ("NLD",),
            "Zorginstituut Nederland",
            "GIPdatabank medicines utilisation",
            SourceDimension.FUNDING,
            landing="https://www.gipdatabank.nl/",
            documentation="https://www.gipdatabank.nl/",
            evidence_limit=(
                "Retain GIPdatabank methodology and classification-version. No "
                "ATC or canonical transform in Bronze. Not reimbursement status."
            ),
            native_identifier="GIPdatabank ATC/product + classification-version year",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url="https://www.gipdatabank.nl/",
            formats=("xlsx", "csv", "html"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
            languages=(LanguageCode.DUTCH, LanguageCode.ENGLISH),
            domains=funding_util,
            entities=funding_entities,
            semantics=(StatusSemantics.MIXED,),
        ),
        _base(
            "dk-medstat-utilisation",
            ("DNK",),
            "Danish Health Data Authority",
            "Medstat.dk medicines statistics",
            SourceDimension.FUNDING,
            landing="https://medstat.dk/",
            documentation="https://medstat.dk/",
            evidence_limit=(
                "Danish utilisation is not comparable by default to Norwegian or "
                "Swedish series; no cross-country claim."
            ),
            native_identifier="Medstat.dk ATC/product + year",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.INTERACTIVE_ONLY,
            languages=(LanguageCode.DANISH, LanguageCode.ENGLISH),
            domains=funding_util,
            entities=funding_entities,
            semantics=(StatusSemantics.MIXED,),
        ),
        _base(
            "no-norpd-utilisation",
            ("NOR",),
            "Norwegian Institute of Public Health",
            "Norwegian Prescription Database",
            SourceDimension.FUNDING,
            landing="https://statistikk.fhi.no/lmr/default.aspx",
            documentation="https://norpd.no/default.aspx",
            evidence_limit=(
                "Historic anonymous reports are frozen through 2020; do not "
                "infer successor coverage or person-level access. Not "
                "comparable by default to DK/SE."
            ),
            native_identifier="NorPD product/ATC identifier",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.INTERACTIVE_ONLY,
            formats=("html",),
            languages=(LanguageCode.NORWEGIAN, LanguageCode.ENGLISH),
            domains=funding_util,
            entities=funding_entities,
            semantics=(StatusSemantics.MIXED,),
        ),
        _base(
            "se-socialstyrelsen-utilisation",
            ("SWE",),
            "National Board of Health and Welfare",
            "Socialstyrelsen medicines statistics",
            SourceDimension.FUNDING,
            landing="https://www.socialstyrelsen.se/statistik-och-data/statistik/statistikamnen/lakemedel/",
            documentation="https://www.socialstyrelsen.se/statistik-och-data/statistik/statistikamnen/lakemedel/",
            evidence_limit=(
                "Swedish utilisation is a separate source from DK/NO; no "
                "cross-country comparability claim."
            ),
            native_identifier="Socialstyrelsen läkemedelsstatistik ATC + year",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url="https://www.socialstyrelsen.se/statistik-och-data/statistik/statistikamnen/lakemedel/",
            formats=("xlsx", "html"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
            languages=(LanguageCode.SWEDISH,),
            domains=funding_util,
            entities=funding_entities,
            semantics=(StatusSemantics.MIXED,),
        ),
        _base(
            "fr-open-medic",
            ("FRA",),
            "Assurance Maladie",
            "Open Medic interregime medicines expenditure",
            SourceDimension.FUNDING,
            landing="https://www.data.gouv.fr/fr/datasets/open-medic-base-complete-sur-les-depenses-de-medicaments-interregimes/",
            documentation="https://www.data.gouv.fr/fr/datasets/open-medic-base-complete-sur-les-depenses-de-medicaments-interregimes/",
            evidence_limit=(
                "French Open Medic expenditure is not a European utilisation "
                "standard and is not registration evidence."
            ),
            native_identifier="Open Medic CIP/ATC + year + regime",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url="https://www.data.gouv.fr/fr/datasets/open-medic-base-complete-sur-les-depenses-de-medicaments-interregimes/",
            formats=("csv",),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
            languages=(LanguageCode.FRENCH,),
            domains=funding_util,
            entities=funding_entities,
            semantics=(StatusSemantics.MIXED,),
            population=PopulationScope.DEFINED_POPULATION,
        ),
        _base(
            "jp-mhlw-ndb-utilisation",
            ("JPN",),
            "Ministry of Health, Labour and Welfare",
            "NDB tabulated medicines utilisation",
            SourceDimension.FUNDING,
            landing="https://www.mhlw.go.jp/ndb/opendatasite/",
            documentation="https://www.mhlw.go.jp/ndb/opendatasite/",
            evidence_limit=(
                "Public aggregate NDB open-data tables are distinct from "
                "credentialed microdata; neither is NHI price or PMDA approval."
            ),
            native_identifier="MHLW NDB tabulated identifier",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.INTERACTIVE_ONLY,
            download_url="https://www.mhlw.go.jp/ndb/opendatasite/",
            formats=("html",),
            integration=IntegrationLayer.ACQUISITION,
            languages=(LanguageCode.JAPANESE,),
            domains=funding_util,
            entities=funding_entities,
            semantics=(StatusSemantics.MIXED,),
        ),
        _base(
            "ca-cihi-nhex-medicines",
            ("CAN",),
            "Canadian Institute for Health Information",
            "CIHI National Health Expenditure medicines components",
            SourceDimension.FUNDING,
            landing="https://www.cihi.ca/en/national-health-expenditure-trends/nhex-trends-data",
            documentation="https://www.cihi.ca/en/national-health-expenditure-trends/nhex-trends-data",
            evidence_limit=(
                "Current NHEX Series G and open-data workbooks are public "
                "macro expenditure tables, not medicine-level utilisation or a formulary."
            ),
            native_identifier="CIHI NHEX/plan expenditure identifier",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url="https://www.cihi.ca/en/national-health-expenditure-trends/nhex-trends-data",
            formats=("xlsx", "zip", "pdf"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
            domains=funding_util,
            entities=funding_entities,
            semantics=(StatusSemantics.MIXED,),
        ),
        _base(
            "ie-pcrs-reimbursement",
            ("IRL",),
            "Health Service Executive Primary Care Reimbursement Service",
            "HSE PCRS reimbursement reports",
            SourceDimension.FUNDING,
            landing="https://about.hse.ie/publications/pcrs-statistical-analysis-of-claims-and-payments-2024/",
            documentation="https://about.hse.ie/publications/pcrs-statistical-analysis-of-claims-and-payments-2024/",
            evidence_limit=(
                "PCRS reimbursement volumes are not national utilisation of all "
                "medicines and are not HPRA registration."
            ),
            native_identifier="HSE PCRS ATC/product reimbursement identifier",
            access_mode=AccessMode.DOCUMENT,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url="https://about.hse.ie/publications/pcrs-statistical-analysis-of-claims-and-payments-2024/",
            formats=("pdf", "html"),
            integration=IntegrationLayer.ACQUISITION,
            domains=funding_util,
            entities=funding_entities,
            semantics=(StatusSemantics.REIMBURSEMENT, StatusSemantics.MIXED),
            population=PopulationScope.PROGRAMME_SPECIFIC,
        ),
    )


def _pv_rows() -> tuple[dict[str, Any], ...]:
    safety = (
        InformationDomain.PRODUCT_IDENTITY,
        InformationDomain.REGULATORY_STATUS,
        InformationDomain.SAFETY,
    )
    entities = (
        RecordEntity.MEDICINAL_PRODUCT,
        RecordEntity.APPROVAL,
        RecordEntity.DOCUMENT,
    )
    fields = (
        AvailableField.IDENTIFIERS,
        AvailableField.NAMES,
        AvailableField.SAFETY_NOTICES,
    )
    return (
        _base(
            "global-umc-vigibase",
            ("GLOBAL",),
            "Uppsala Monitoring Centre",
            "VigiBase",
            SourceDimension.REGULATORY,
            landing="https://who-umc.org/vigibase/",
            documentation="https://who-umc.org/vigibase/",
            evidence_limit=(
                "VigiBase is credentialed. Registration is not bronze coverage. "
                "Signals are independently typed from FDA FAERS and EMA EV."
            ),
            native_identifier="VigiBase/VigiLyze case identifier",
            access_mode=AccessMode.LICENSED_FEED,
            interface_status=InterfaceStatus.RESTRICTED,
            authentication=AuthenticationMode.SUBSCRIPTION,
            readiness=SourceReadiness.BLOCKED,
            download_url="https://who-umc.org/vigibase/",
            formats=("csv",),
            acquisition_profile="account-download",
            geographic_scope=GeographicScope.GLOBAL,
            domains=safety,
            entities=entities,
            fields=fields,
        ),
        _base(
            "gb-mhra-yellow-card",
            ("GBR",),
            "Medicines and Healthcare products Regulatory Agency",
            "Yellow Card Scheme public outputs",
            SourceDimension.REGULATORY,
            landing="https://yellowcard.mhra.gov.uk/",
            documentation="https://yellowcard.mhra.gov.uk/",
            evidence_limit=(
                "Yellow Card public outputs are not unrestricted case-level "
                "bronze and are not NICE or OpenPrescribing utilisation."
            ),
            native_identifier="MHRA Yellow Card report identifier",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.INTERACTIVE_ONLY,
            domains=safety,
            entities=entities,
            fields=fields,
        ),
        _base(
            "au-tga-daen",
            ("AUS",),
            "Therapeutic Goods Administration",
            "Database of Adverse Event Notifications",
            SourceDimension.REGULATORY,
            landing="https://www.tga.gov.au/safety/safety/safety-monitoring-daen-database-adverse-event-notifications",
            documentation="https://www.tga.gov.au/safety/safety/safety-monitoring-daen-database-adverse-event-notifications",
            evidence_limit=(
                "DAEN search is not complete case-level bronze and is not ARTG "
                "registration status."
            ),
            native_identifier="TGA DAEN case number",
            access_mode=AccessMode.WEB_SEARCH,
            interface_status=InterfaceStatus.INTERACTIVE_ONLY,
            domains=safety,
            entities=entities,
            fields=fields,
        ),
        _base(
            "ca-canada-vigilance",
            ("CAN",),
            "Health Canada",
            "Canada Vigilance adverse reaction online database",
            SourceDimension.REGULATORY,
            landing="https://www.canada.ca/en/health-canada/services/drugs-health-products/medeffect-canada/adverse-reaction-database.html",
            documentation="https://www.canada.ca/en/health-canada/services/drugs-health-products/medeffect-canada/adverse-reaction-database.html",
            evidence_limit=(
                "Canada Vigilance extracts are safety reports, not DPD "
                "registration or causality."
            ),
            native_identifier="Canada Vigilance adverse reaction number",
            access_mode=AccessMode.DOWNLOAD,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            download_url="https://www.canada.ca/en/health-canada/services/drugs-health-products/medeffect-canada/adverse-reaction-database.html",
            formats=("xlsx", "csv"),
            integration=IntegrationLayer.ACQUISITION,
            acquisition_profile="public-bulk",
            domains=safety,
            entities=entities,
            fields=fields,
        ),
        _base(
            "jp-pmda-safety",
            ("JPN",),
            "Pharmaceuticals and Medical Devices Agency",
            "PMDA safety information and alerts",
            SourceDimension.REGULATORY,
            landing="https://www.pmda.go.jp/english/safety/info-services/0001.html",
            documentation="https://www.pmda.go.jp/english/safety/info-services/0001.html",
            evidence_limit=(
                "PMDA safety communications are not approval status and are not "
                "causality beyond the regulator statement."
            ),
            native_identifier="PMDA safety report/alert identifier",
            access_mode=AccessMode.DOCUMENT,
            interface_status=InterfaceStatus.DOCUMENTED_DOWNLOAD,
            formats=("html", "pdf"),
            languages=(LanguageCode.JAPANESE, LanguageCode.ENGLISH),
            domains=safety,
            entities=entities,
            fields=fields,
        ),
    )
