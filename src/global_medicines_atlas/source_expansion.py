"""One bronze source-expansion program for tracks 1-36.

Inventory, reuse-gate, and coverage reconciliation share one registry
contract. Missing coverage is recorded as a blocker, never as negative
medicine evidence. Hugging Face is an archive boundary, not truth.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field

from .bronze_landing import EVIDENTIARY_TRUTH_SENTENCE, land_bronze_payload
from .countries import SourceDimension
from .models import FrozenModel
from .receipts import SourceReceipt
from .reuse_gate import (
    ReuseGateDecision,
    ReuseGateRequiredError,
    evaluate_reuse_gate,
    require_reuse_decision,
)
from .source_catalog import (
    AccessMode,
    InformationDomain,
    MedicineDataSource,
    SourceReadiness,
    load_catalog,
    load_source_catalog,
)
from .source_profiles import AuthenticationMode

INDEX_SCHEMA_ID = "global-medicines-atlas.source-index"
INDEX_VERSION = 1
INDEX_ID = "global-medicines-data-source-index-2026-08-20"
HF_ROLE = "archive_output_not_source_of_truth"
AFRICAN_EXPANSION_TRACK_ID = 9
AFRICAN_COVERAGE_JURISDICTIONS: tuple[str, ...] = (
    "EGY",
    "GHA",
    "KEN",
    "MUS",
    "NGA",
    "RWA",
    "SEN",
    "TZA",
    "UGA",
    "ZAF",
    "ZWE",
)
INDEPENDENT_DIMENSIONS: tuple[str, ...] = (
    "regulatory",
    "formulary",
    "reimbursement",
    "procurement",
    "pharmacovigilance",
    "utilisation",
    "terminology",
)


class CoverageFacet(StrEnum):
    """Measured coverage columns; absence is not a clinical claim."""

    REGULATOR = "regulator"
    REGISTRATION = "registration"
    EML_FORMULARY = "eml_formulary"
    REIMBURSEMENT = "reimbursement"
    PRICING_PROCUREMENT = "pricing_procurement"
    PHARMACOVIGILANCE = "pharmacovigilance"
    RECALLS = "recalls"
    SHORTAGES = "shortages"
    UTILISATION = "utilisation"
    TERMINOLOGY_SUBSTANCE = "terminology_substance"
    HISTORICAL_DEPTH = "historical_depth"


class BronzeDisposition(StrEnum):
    """What bronze may claim after inventory and the reuse gate."""

    ELIGIBLE_NOT_LIVE = "eligible_public_not_live_acquired"
    FIXTURE_LANDABLE = "fixture_landable_not_live"
    RIGHTS_BLOCKED = "rights_unresolved_fail_closed"
    CREDENTIALED_BLOCKED = "credentialed_metadata_only"
    INTERACTIVE_ONLY = "interactive_only_blocker"
    UNAVAILABLE = "unavailable_source_recorded"
    REUSED_EXISTING = "reused_existing_catalog_entry"


class TrackFamily(StrEnum):
    WHO = "who"
    AFRICA = "africa"
    INDIA = "india"
    FDA = "fda"
    EMA = "ema"
    UK = "uk"
    UTILISATION = "utilisation"
    PHARMACOVIGILANCE = "pharmacovigilance"
    RECONCILIATION = "reconciliation"


class ExpansionTrack(FrozenModel):
    """One of the 36 acquisition prompts."""

    track_id: int = Field(ge=1, le=36)
    family: TrackFamily
    title: str = Field(min_length=1)
    invariant: str = Field(min_length=1)
    source_ids: tuple[str, ...] = Field(min_length=1)
    facets: tuple[CoverageFacet, ...] = Field(min_length=1)


class SourceBinding(FrozenModel):
    """How one catalog source participates in the expansion program."""

    source_id: str = Field(min_length=1)
    track_ids: tuple[int, ...] = Field(min_length=1)
    facets: tuple[CoverageFacet, ...] = Field(min_length=1)
    existing: bool
    native_identifier: str = Field(min_length=1)
    blocker: str | None = None


class TrackOutcome(FrozenModel):
    track_id: int
    landed_source_ids: tuple[str, ...]
    blocked_source_ids: tuple[str, ...]
    notes: str = Field(min_length=1)


class CoverageCell(FrozenModel):
    jurisdiction: str = Field(min_length=1)
    facet: CoverageFacet
    source_ids: tuple[str, ...]
    state: str = Field(min_length=1)
    evidence_limit: str = Field(min_length=1)


class ExpansionAcquireResult(FrozenModel):
    source_id: str
    disposition: BronzeDisposition
    reuse_disposition: str
    landed: bool
    blocker: str | None = None


def expansion_tracks() -> tuple[ExpansionTrack, ...]:
    """Return the locked 1-36 track registry."""

    return _TRACKS


def source_bindings() -> tuple[SourceBinding, ...]:
    return _BINDINGS


def binding_for(source_id: str) -> SourceBinding:
    for binding in _BINDINGS:
        if binding.source_id == source_id:
            return binding
    raise KeyError(source_id)


def required_source_ids() -> frozenset[str]:
    return frozenset(
        source_id for track in _TRACKS for source_id in track.source_ids
    )


def _disposition_from_blocker(blocker: str) -> BronzeDisposition | None:
    if "credential" in blocker or "account" in blocker:
        return BronzeDisposition.CREDENTIALED_BLOCKED
    if "unavailable" in blocker:
        return BronzeDisposition.UNAVAILABLE
    if "interactive" in blocker:
        return BronzeDisposition.INTERACTIVE_ONLY
    if "rights" in blocker:
        return BronzeDisposition.RIGHTS_BLOCKED
    return None


def classify_bronze_disposition(
    source: MedicineDataSource,
    *,
    binding: SourceBinding | None = None,
) -> BronzeDisposition:
    """Fail closed on rights and credentials; metadata-only is not coverage."""

    resolved = binding or _optional_binding(source.source_id)
    if resolved is not None and resolved.blocker:
        from_blocker = _disposition_from_blocker(resolved.blocker)
        if from_blocker is not None:
            return from_blocker
    rights = source.rights_status.lower()
    blocked_rights = (
        "review_required",
        "unclear",
        "prohibited",
        "dataset_specific",
    )
    checks = (
        (
            source.authentication != AuthenticationMode.NONE
            or source.access_mode is AccessMode.LICENSED_FEED,
            BronzeDisposition.CREDENTIALED_BLOCKED,
        ),
        (
            source.readiness is SourceReadiness.BLOCKED,
            BronzeDisposition.UNAVAILABLE,
        ),
        (
            any(token in rights for token in blocked_rights),
            BronzeDisposition.RIGHTS_BLOCKED,
        ),
        (
            source.access_mode is AccessMode.WEB_SEARCH,
            BronzeDisposition.INTERACTIVE_ONLY,
        ),
        (
            resolved is not None and resolved.existing,
            BronzeDisposition.REUSED_EXISTING,
        ),
    )
    for matched, disposition in checks:
        if matched:
            return disposition
    return BronzeDisposition.ELIGIBLE_NOT_LIVE


def run_expansion_reuse_gate(
    source_id: str,
    *,
    repository_root: Path,
    catalog: Sequence[MedicineDataSource] | None = None,
) -> ReuseGateDecision:
    """Mandatory ecosystem reuse gate before any acquire/download."""

    sources = load_source_catalog() if catalog is None else catalog
    return evaluate_reuse_gate(
        source_id,
        repository_root=repository_root,
        catalog=sources,
    )


def acquire_expansion_source(
    source_id: str,
    *,
    repository_root: Path,
    reuse: ReuseGateDecision | None,
    payload: bytes | None = None,
    receipt: SourceReceipt | None = None,
    bronze_root: Path | None = None,
) -> ExpansionAcquireResult:
    """Acquire only after the reuse gate; never claim live ingest for blockers."""

    if not repository_root.exists():
        raise ValueError("repository_root must exist for the reuse gate")
    decision = require_reuse_decision(reuse, source_id)
    catalog = {item.source_id: item for item in load_source_catalog()}
    if source_id not in catalog:
        raise KeyError(f"source {source_id} is not in the governed registry")
    source = catalog[source_id]
    binding = _optional_binding(source_id)
    disposition = classify_bronze_disposition(source, binding=binding)
    blocked = disposition in {
        BronzeDisposition.RIGHTS_BLOCKED,
        BronzeDisposition.CREDENTIALED_BLOCKED,
        BronzeDisposition.INTERACTIVE_ONLY,
        BronzeDisposition.UNAVAILABLE,
    }
    if blocked or payload is None or receipt is None or bronze_root is None:
        return ExpansionAcquireResult(
            source_id=source_id,
            disposition=disposition,
            reuse_disposition=decision.disposition.value,
            landed=False,
            blocker=_blocker_text(source, binding, disposition),
        )
    land_bronze_payload(
        payload,
        receipt,
        bronze_root=bronze_root,
        reuse=decision,
    )
    return ExpansionAcquireResult(
        source_id=source_id,
        disposition=BronzeDisposition.FIXTURE_LANDABLE,
        reuse_disposition=decision.disposition.value,
        landed=True,
        blocker=None,
    )


def reconcile_coverage(
    catalog: Sequence[MedicineDataSource] | None = None,
) -> tuple[CoverageCell, ...]:
    """Build facet cells; missing sources stay not-covered, not negative."""

    sources = load_source_catalog() if catalog is None else tuple(catalog)
    by_id = {item.source_id: item for item in sources}
    cells: list[CoverageCell] = []
    jurisdictions = sorted(
        {
            jurisdiction
            for source in sources
            for jurisdiction in source.jurisdictions
        }
        | {"GLOBAL"}
    )
    for jurisdiction in jurisdictions:
        for facet in CoverageFacet:
            ids = tuple(
                binding.source_id
                for binding in _BINDINGS
                if facet in binding.facets
                and _source_in_jurisdiction(
                    by_id.get(binding.source_id),
                    jurisdiction,
                    binding,
                )
            )
            state = "catalogued" if ids else "not_covered"
            limits = tuple(
                by_id[source_id].evidence_limit
                for source_id in ids
                if source_id in by_id
            )
            cells.append(
                CoverageCell(
                    jurisdiction=jurisdiction,
                    facet=facet,
                    source_ids=ids,
                    state=state,
                    evidence_limit=(
                        " | ".join(limits)
                        if limits
                        else (
                            "Not covered in the current registry; missing "
                            "coverage is not negative evidence."
                        )
                    ),
                )
            )
    return tuple(cells)


def african_source_coverage_matrix(
    catalog: Sequence[MedicineDataSource] | None = None,
) -> tuple[CoverageCell, ...]:
    cells = reconcile_coverage(catalog)
    return tuple(
        cell
        for cell in cells
        if cell.jurisdiction in AFRICAN_COVERAGE_JURISDICTIONS
    )


def track_outcomes(
    catalog: Sequence[MedicineDataSource] | None = None,
) -> tuple[TrackOutcome, ...]:
    sources = {
        item.source_id: item
        for item in (load_source_catalog() if catalog is None else catalog)
    }
    outcomes: list[TrackOutcome] = []
    for track in _TRACKS:
        landed: list[str] = []
        blocked: list[str] = []
        notes: list[str] = []
        for source_id in track.source_ids:
            if source_id == "global-medicines-source-index":
                landed.append(source_id)
                notes.append(
                    "derived catalogue index; Hugging Face is not truth"
                )
                continue
            source = sources.get(source_id)
            if source is None:
                blocked.append(source_id)
                notes.append(f"{source_id} missing from registry")
                continue
            binding = _optional_binding(source_id)
            disposition = classify_bronze_disposition(source, binding=binding)
            landed.append(source_id)
            if disposition in {
                BronzeDisposition.CREDENTIALED_BLOCKED,
                BronzeDisposition.UNAVAILABLE,
            }:
                blocked.append(source_id)
            notes.append(f"{source_id}:{disposition.value}")
        outcomes.append(
            TrackOutcome(
                track_id=track.track_id,
                landed_source_ids=tuple(landed),
                blocked_source_ids=tuple(blocked),
                notes="; ".join(notes) or track.invariant,
            )
        )
    return tuple(outcomes)


def high_value_gaps(
    catalog: Sequence[MedicineDataSource] | None = None,
) -> tuple[str, ...]:
    """Gaps that may justify later tracks; not treated as medicine absence."""

    outcomes = track_outcomes(catalog)
    gaps = [
        f"track {outcome.track_id} blocked "
        f"{', '.join(outcome.blocked_source_ids)}"
        for outcome in outcomes
        if outcome.blocked_source_ids
    ]
    cells = african_source_coverage_matrix(catalog)
    for jurisdiction in AFRICAN_COVERAGE_JURISDICTIONS:
        by_facet = {
            cell.facet: cell
            for cell in cells
            if cell.jurisdiction == jurisdiction
        }
        for facet in (
            CoverageFacet.REGISTRATION,
            CoverageFacet.EML_FORMULARY,
            CoverageFacet.PHARMACOVIGILANCE,
        ):
            cell = by_facet[facet]
            if cell.state == "not_covered":
                gaps.append(f"{jurisdiction} {facet.value} not inventoried")
    return tuple(gaps)


def build_source_index(
    catalog: Sequence[MedicineDataSource] | None = None,
) -> dict[str, object]:
    """Citable, versioned global medicines-data source index."""

    sources = load_source_catalog() if catalog is None else tuple(catalog)
    catalog_doc = load_catalog()
    outcomes = track_outcomes(sources)
    cells = reconcile_coverage(sources)
    african = african_source_coverage_matrix(sources)
    return {
        "schema_id": INDEX_SCHEMA_ID,
        "schema_version": INDEX_VERSION,
        "index_id": INDEX_ID,
        "generated_from": (
            "src/global_medicines_atlas/data/medicine_source_catalog.json"
        ),
        "catalog_reviewed_at": catalog_doc.reviewed_at.isoformat(),
        "evidentiary_truth": EVIDENTIARY_TRUTH_SENTENCE,
        "hugging_face_role": HF_ROLE,
        "independent_dimensions": list(INDEPENDENT_DIMENSIONS),
        "reuse_gate_surfaces": [
            "local_clones",
            "github",
            "hugging_face",
            "source_registry",
        ],
        "tracks": [
            {
                "track_id": track.track_id,
                "family": track.family.value,
                "title": track.title,
                "invariant": track.invariant,
                "source_ids": list(track.source_ids),
                "facets": [facet.value for facet in track.facets],
            }
            for track in _TRACKS
        ],
        "track_outcomes": [
            outcome.model_dump(mode="json") for outcome in outcomes
        ],
        "sources": [
            {
                "source_id": source.source_id,
                "jurisdictions": list(source.jurisdictions),
                "authority": source.authority,
                "dimension": source.dimension.value,
                "native_identifier": source.native_identifier,
                "rights_status": source.rights_status,
                "authentication": source.authentication.value,
                "readiness": source.readiness.value,
                "information_domains": [
                    domain.value for domain in source.information_domains
                ],
            }
            for source in sources
        ],
        "coverage_matrix": [cell.model_dump(mode="json") for cell in cells],
        "african_coverage_matrix": [
            cell.model_dump(mode="json") for cell in african
        ],
        "high_value_gaps": list(high_value_gaps(sources)),
        "silver_gold_implemented": False,
    }


def write_source_index(
    path: Path,
    payload: Mapping[str, object] | None = None,
) -> Path:
    document = payload or build_source_index()
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def dimensions_remain_independent(source: MedicineDataSource) -> bool:
    """Reject collapsing registration, formulary, funding, and terminology."""

    domains = set(source.information_domains)
    if source.dimension is SourceDimension.REGULATORY:
        return InformationDomain.FUNDING_STATUS not in domains
    if source.dimension is SourceDimension.FORMULARY:
        return InformationDomain.REGULATORY_STATUS not in domains
    if source.dimension is SourceDimension.TERMINOLOGY:
        return InformationDomain.REGULATORY_STATUS not in domains
    return True


def _optional_binding(source_id: str) -> SourceBinding | None:
    for binding in _BINDINGS:
        if binding.source_id == source_id:
            return binding
    return None


def _blocker_text(
    source: MedicineDataSource,
    binding: SourceBinding | None,
    disposition: BronzeDisposition,
) -> str:
    if binding is not None and binding.blocker:
        return binding.blocker
    return f"{disposition.value}; rights={source.rights_status}"


def _source_in_jurisdiction(
    source: MedicineDataSource | None,
    jurisdiction: str,
    binding: SourceBinding,
) -> bool:
    if source is None:
        return (
            jurisdiction == "GLOBAL"
            and AFRICAN_EXPANSION_TRACK_ID in binding.track_ids
        )
    if jurisdiction in source.jurisdictions:
        return True
    return jurisdiction == "GLOBAL" and "GLOBAL" in source.jurisdictions


def _track(
    track_id: int,
    family: TrackFamily,
    title: str,
    invariant: str,
    source_ids: tuple[str, ...],
    facets: tuple[CoverageFacet, ...],
) -> ExpansionTrack:
    return ExpansionTrack(
        track_id=track_id,
        family=family,
        title=title,
        invariant=invariant,
        source_ids=source_ids,
        facets=facets,
    )


def _bind(
    source_id: str,
    track_ids: tuple[int, ...],
    facets: tuple[CoverageFacet, ...],
    *,
    existing: bool = False,
    native_identifier: str,
    blocker: str | None = None,
) -> SourceBinding:
    return SourceBinding(
        source_id=source_id,
        track_ids=track_ids,
        facets=facets,
        existing=existing,
        native_identifier=native_identifier,
        blocker=blocker,
    )


_TRACKS: tuple[ExpansionTrack, ...] = (
    _track(
        1,
        TrackFamily.WHO,
        "WHO National Essential Medicines Lists / Global EML",
        "EML/formulary evidence is not automatically reimbursement.",
        (
            "global-who-eml",
            "global-who-national-eml-index",
        ),
        (CoverageFacet.EML_FORMULARY, CoverageFacet.HISTORICAL_DEPTH),
    ),
    _track(
        2,
        TrackFamily.WHO,
        "WHO AMDS / GPRM",
        "Procurement price is not reimbursement, retail, list, or PPP-normalised.",
        ("global-who-amds-gprm",),
        (CoverageFacet.PRICING_PROCUREMENT,),
    ),
    _track(
        3,
        TrackFamily.WHO,
        "WHO medicines price, availability, and shortage sources",
        "Register each dataset separately; do not infer shortage from missing data.",
        (
            "global-who-medicine-prices",
            "global-who-availability-surveys",
            "global-who-shortage-sources",
        ),
        (
            CoverageFacet.PRICING_PROCUREMENT,
            CoverageFacet.SHORTAGES,
        ),
    ),
    _track(
        4,
        TrackFamily.WHO,
        "WHO MI4A vaccines",
        "Vaccine-market evidence is distinct from conventional medicines reimbursement.",
        ("global-who-mi4a",),
        (CoverageFacet.PRICING_PROCUREMENT,),
    ),
    _track(
        5,
        TrackFamily.AFRICA,
        "Uganda NDA, EML, and public safety",
        "Keep registration, formulary, and safety dimensions separate.",
        ("ug-nda-register", "ug-national-eml", "ug-nda-safety"),
        (
            CoverageFacet.REGULATOR,
            CoverageFacet.REGISTRATION,
            CoverageFacet.EML_FORMULARY,
            CoverageFacet.PHARMACOVIGILANCE,
            CoverageFacet.RECALLS,
        ),
    ),
    _track(
        6,
        TrackFamily.AFRICA,
        "Kenya PPB, formularies, and safety",
        "Do not infer current registration from historical presence or absence.",
        ("ke-ppb-register", "ke-national-eml", "ke-ppb-safety"),
        (
            CoverageFacet.REGULATOR,
            CoverageFacet.REGISTRATION,
            CoverageFacet.EML_FORMULARY,
            CoverageFacet.PHARMACOVIGILANCE,
        ),
    ),
    _track(
        7,
        TrackFamily.AFRICA,
        "Tanzania TMDA products, EML, and safety",
        "Preserve manufacturer/sponsor as source-native fields.",
        ("tz-tmda-products", "tz-national-eml", "tz-tmda-safety"),
        (
            CoverageFacet.REGISTRATION,
            CoverageFacet.EML_FORMULARY,
            CoverageFacet.PHARMACOVIGILANCE,
        ),
    ),
    _track(
        8,
        TrackFamily.AFRICA,
        "Pakistan DRAP, NEML, and safety",
        "Distinguish provisional, registered, and historical source-native states.",
        ("pk-drap-register", "pk-neml", "pk-drap-safety"),
        (
            CoverageFacet.REGISTRATION,
            CoverageFacet.EML_FORMULARY,
            CoverageFacet.PHARMACOVIGILANCE,
            CoverageFacet.SHORTAGES,
        ),
    ),
    _track(
        9,
        TrackFamily.AFRICA,
        "African regulatory registries expansion",
        "Per-jurisdiction inventory; measured matrix; missing lists are not negatives.",
        (
            "eg-eda-register",
            "eg-national-eml",
            "eg-eda-safety",
            "gh-fda-register",
            "gh-national-eml",
            "gh-fda-safety",
            "rw-rwandafda-register",
            "rw-national-eml",
            "rw-rwandafda-safety",
            "sn-dpm-register",
            "sn-national-eml",
            "sn-dpm-safety",
            "zw-mcaz-register",
            "zw-national-eml",
            "zw-mcaz-safety",
            "mus-pharmacy-board-register",
            "ng-nafdac-products",
            "ng-nhia-medicines",
            "za-sahpra-register",
            "za-national-eml",
            "za-sahpra-safety",
            "ng-nafdac-safety",
            "mus-pharmacy-board-safety",
            "ug-nda-register",
            "ke-ppb-register",
            "tz-tmda-products",
        ),
        (
            CoverageFacet.REGULATOR,
            CoverageFacet.REGISTRATION,
            CoverageFacet.EML_FORMULARY,
            CoverageFacet.PHARMACOVIGILANCE,
        ),
    ),
    _track(
        10,
        TrackFamily.AFRICA,
        "Mauritius approved drug list and public registration",
        "Distinguish registration, formulary, and reimbursement.",
        (
            "mus-approved-drug-list",
            "mus-pharmacy-board-register",
            "mus-historical-eml-archive",
        ),
        (
            CoverageFacet.REGISTRATION,
            CoverageFacet.EML_FORMULARY,
            CoverageFacet.HISTORICAL_DEPTH,
        ),
    ),
    _track(
        11,
        TrackFamily.INDIA,
        "India expansion beyond CDSCO/NLEM seeds",
        "NPPA ceiling price is not a transaction or reimbursement price.",
        (
            "in-cdsco-approved-drugs",
            "in-cdsco-products",
            "in-nlem",
            "in-nppa-ceiling-prices",
            "in-procurement-availability",
            "in-pvpi-safety",
        ),
        (
            CoverageFacet.REGISTRATION,
            CoverageFacet.EML_FORMULARY,
            CoverageFacet.PRICING_PROCUREMENT,
            CoverageFacet.PHARMACOVIGILANCE,
        ),
    ),
    _track(
        12,
        TrackFamily.FDA,
        "FDA FAERS public releases",
        "Reports are not causation; no dedup or identity collapse in Bronze.",
        ("us-fda-faers", "us-openfda-faers"),
        (CoverageFacet.PHARMACOVIGILANCE,),
    ),
    _track(
        13,
        TrackFamily.FDA,
        "FDA recalls and enforcement",
        "API and files overlap; model the relationship, do not silent-dedup.",
        ("us-openfda-enforcement", "us-fda-recalls-notices"),
        (CoverageFacet.RECALLS,),
    ),
    _track(
        14,
        TrackFamily.FDA,
        "FDA drug shortages",
        "Absence from the current list is not evidence of no historical shortage.",
        ("us-fda-drug-shortages",),
        (CoverageFacet.SHORTAGES, CoverageFacet.HISTORICAL_DEPTH),
    ),
    _track(
        15,
        TrackFamily.FDA,
        "FDA REMS",
        "REMS is distinct from approval and from pharmacovigilance case data.",
        ("us-fda-rems",),
        (CoverageFacet.REGISTRATION,),
    ),
    _track(
        16,
        TrackFamily.FDA,
        "FDA Orange Book versioned family",
        "Therapeutic equivalence codes are not clinical substitutability.",
        ("us-fda-orange-book",),
        (CoverageFacet.REGISTRATION, CoverageFacet.HISTORICAL_DEPTH),
    ),
    _track(
        17,
        TrackFamily.FDA,
        "FDA NDC Directory",
        "Listing is not approval; preserve product versus package grain.",
        ("us-openfda-ndc", "us-fda-ndc-directory"),
        (CoverageFacet.REGISTRATION, CoverageFacet.TERMINOLOGY_SUBSTANCE),
    ),
    _track(
        18,
        TrackFamily.FDA,
        "FDA UNII / GSRS",
        "Substance terminology is not canonical medicine identity.",
        ("us-gsrs-unii",),
        (CoverageFacet.TERMINOLOGY_SUBSTANCE,),
    ),
    _track(
        19,
        TrackFamily.FDA,
        "FDA NSDE",
        "Authoritative NSDE is the FDA SPL NDC SPL Data Elements file.",
        ("us-fda-nsde", "us-openfda-nsde"),
        (CoverageFacet.TERMINOLOGY_SUBSTANCE, CoverageFacet.REGISTRATION),
    ),
    _track(
        20,
        TrackFamily.EMA,
        "EMA EPAR structured data and documents",
        "Documents must not overwrite structured source-native fields.",
        ("eu-ema-medicines", "eu-ema-json", "eu-ema-epar-documents"),
        (CoverageFacet.REGISTRATION,),
    ),
    _track(
        21,
        TrackFamily.EMA,
        "EMA EudraVigilance public",
        "Public dashboards are not unrestricted case-level data.",
        ("eu-eudravigilance-public",),
        (CoverageFacet.PHARMACOVIGILANCE,),
    ),
    _track(
        22,
        TrackFamily.EMA,
        "EMA orphan designations",
        "Orphan designation is distinct from marketing authorisation.",
        ("eu-ema-orphan",),
        (CoverageFacet.REGISTRATION,),
    ),
    _track(
        23,
        TrackFamily.EMA,
        "EMA referrals",
        "Referral events must not collapse into ordinary approval status.",
        ("eu-ema-referrals",),
        (CoverageFacet.REGISTRATION,),
    ),
    _track(
        24,
        TrackFamily.EMA,
        "EMA safety communications",
        "Do not infer causality beyond the regulator statement.",
        ("eu-ema-safety-communications",),
        (CoverageFacet.PHARMACOVIGILANCE,),
    ),
    _track(
        25,
        TrackFamily.EMA,
        "EMA Union Register",
        "Fully catalogued and versioned; fixtures are not complete acquisition.",
        ("eu-union-register",),
        (CoverageFacet.REGISTRATION, CoverageFacet.HISTORICAL_DEPTH),
    ),
    _track(
        26,
        TrackFamily.EMA,
        "EMA Article 57 / xEVMPD",
        "Public metadata stays public; credentialed payloads stay metadata-only.",
        ("eu-ema-article57", "eu-ema-xevmpd-credentialed"),
        (CoverageFacet.REGISTRATION, CoverageFacet.TERMINOLOGY_SUBSTANCE),
    ),
    _track(
        27,
        TrackFamily.EMA,
        "EMA SPOR / PMS / RMS / OMS",
        "Metadata-only credentialed rows are not bronze coverage.",
        ("eu-spor-rms-oms", "eu-ema-pms-fhir", "eu-spor-public-metadata"),
        (CoverageFacet.TERMINOLOGY_SUBSTANCE, CoverageFacet.REGISTRATION),
    ),
    _track(
        28,
        TrackFamily.UK,
        "UK NICE technology appraisals",
        "A recommendation is not actual funding or utilisation.",
        ("gb-nice-ta",),
        (CoverageFacet.REIMBURSEMENT, CoverageFacet.HISTORICAL_DEPTH),
    ),
    _track(
        29,
        TrackFamily.UK,
        "UK use of NICE-appraised medicines",
        "Do not force a universal utilisation unit across methodology changes.",
        ("gb-nice-medicines-utilisation",),
        (CoverageFacet.UTILISATION, CoverageFacet.HISTORICAL_DEPTH),
    ),
    _track(
        30,
        TrackFamily.UK,
        "England OpenPrescribing",
        "Rights and volume constraints; no cross-country unit normalisation.",
        ("gb-openprescribing",),
        (CoverageFacet.UTILISATION,),
    ),
    _track(
        31,
        TrackFamily.UTILISATION,
        "US Medicare Part D utilisation",
        "Part D is not total US utilisation; population limits stay explicit.",
        ("us-cms-partd-spending", "us-cms-partd-formulary"),
        (CoverageFacet.UTILISATION, CoverageFacet.REIMBURSEMENT),
    ),
    _track(
        32,
        TrackFamily.UTILISATION,
        "Netherlands GIPdatabank",
        "Retain methodology and classification version; no ATC transform in Bronze.",
        ("nl-gipdatabank",),
        (CoverageFacet.UTILISATION,),
    ),
    _track(
        33,
        TrackFamily.UTILISATION,
        "Nordic utilisation (DK/NO/SE)",
        "Separate sources; no cross-country comparability claim.",
        (
            "dk-medstat-utilisation",
            "no-norpd-utilisation",
            "se-socialstyrelsen-utilisation",
        ),
        (CoverageFacet.UTILISATION,),
    ),
    _track(
        34,
        TrackFamily.UTILISATION,
        "Additional public utilisation (FR/JP/CA/IE)",
        "Bounded discovery; prefer national/payer authorities over aggregators.",
        (
            "fr-open-medic",
            "jp-mhlw-ndb-utilisation",
            "ca-cihi-nhex-medicines",
            "ie-pcrs-reimbursement",
        ),
        (CoverageFacet.UTILISATION,),
    ),
    _track(
        35,
        TrackFamily.PHARMACOVIGILANCE,
        "Global PV expansion beyond FDA/EMA",
        "Register restricted systems; bronze coverage only for acquired evidence.",
        (
            "global-umc-vigibase",
            "gb-mhra-yellow-card",
            "au-tga-daen",
            "ca-canada-vigilance",
            "jp-pmda-safety",
        ),
        (CoverageFacet.PHARMACOVIGILANCE,),
    ),
    _track(
        36,
        TrackFamily.RECONCILIATION,
        "Final source-coverage reconciliation",
        "Citable versioned index from the registry; new tracks only for high-value gaps.",
        ("global-medicines-source-index",),
        tuple(CoverageFacet),
    ),
)


def _africa_bind(
    source_id: str,
    track_ids: tuple[int, ...],
    native: str,
    *,
    existing: bool = False,
    blocker: str | None = None,
) -> SourceBinding:
    facets = (
        CoverageFacet.REGULATOR,
        CoverageFacet.REGISTRATION,
        CoverageFacet.EML_FORMULARY,
        CoverageFacet.PHARMACOVIGILANCE,
        CoverageFacet.RECALLS,
    )
    if (
        "eml" in source_id
        or "neml" in source_id
        or "approved-drug" in source_id
    ):
        facets = (CoverageFacet.EML_FORMULARY, CoverageFacet.HISTORICAL_DEPTH)
    elif "safety" in source_id:
        facets = (
            CoverageFacet.PHARMACOVIGILANCE,
            CoverageFacet.RECALLS,
        )
    elif "register" in source_id or "products" in source_id:
        facets = (
            CoverageFacet.REGULATOR,
            CoverageFacet.REGISTRATION,
            CoverageFacet.HISTORICAL_DEPTH,
        )
    return _bind(
        source_id,
        track_ids,
        facets,
        existing=existing,
        native_identifier=native,
        blocker=blocker,
    )


_BINDINGS: tuple[SourceBinding, ...] = (
    _bind(
        "global-who-eml",
        (1,),
        (CoverageFacet.EML_FORMULARY, CoverageFacet.HISTORICAL_DEPTH),
        native_identifier="WHO EML medicine/section identifier + list year",
    ),
    _bind(
        "global-who-national-eml-index",
        (1, 9),
        (CoverageFacet.EML_FORMULARY,),
        native_identifier="WHO national EML country/list edition",
        blocker="unavailable national lists recorded; not negative evidence",
    ),
    _bind(
        "global-who-amds-gprm",
        (2,),
        (CoverageFacet.PRICING_PROCUREMENT,),
        native_identifier="WHO GPRM transaction/product/incoterm identifier",
    ),
    _bind(
        "global-who-medicine-prices",
        (3,),
        (CoverageFacet.PRICING_PROCUREMENT,),
        native_identifier="WHO/HAI survey medicine/country/year identifier",
    ),
    _bind(
        "global-who-availability-surveys",
        (3,),
        (CoverageFacet.PRICING_PROCUREMENT,),
        native_identifier="WHO/HAI facility-survey wave identifier",
        blocker="unavailable survey waves recorded; absence is not unavailability",
    ),
    _bind(
        "global-who-shortage-sources",
        (3,),
        (CoverageFacet.SHORTAGES,),
        native_identifier="WHO shortage source dataset identifier",
        blocker="unavailable_source: no single global WHO shortage register",
    ),
    _bind(
        "global-who-mi4a",
        (4,),
        (CoverageFacet.PRICING_PROCUREMENT,),
        native_identifier="WHO MI4A vaccine product/market identifier",
    ),
    _africa_bind(
        "ug-nda-register", (5, 9), "Uganda NDA product/registration number"
    ),
    _africa_bind(
        "ug-national-eml", (5, 9), "Uganda EML/health supplies list entry"
    ),
    _africa_bind(
        "ug-nda-safety",
        (5, 9),
        "Uganda NDA safety/recall notice identifier",
        blocker="interactive_only public notices; rights review required",
    ),
    _africa_bind(
        "ke-ppb-register",
        (6, 9),
        "Kenya PPB product registration number",
        blocker="interactive_only portal; historical presence is not current registration",
    ),
    _africa_bind(
        "ke-national-eml", (6, 9), "Kenya EML/formulary entry identifier"
    ),
    _africa_bind(
        "ke-ppb-safety", (6, 9), "Kenya PPB safety/recall notice identifier"
    ),
    _africa_bind(
        "tz-tmda-products",
        (7, 9),
        "TMDA product registration number + manufacturer/sponsor",
    ),
    _africa_bind("tz-national-eml", (7, 9), "Tanzania EML entry identifier"),
    _africa_bind("tz-tmda-safety", (7, 9), "TMDA safety notice identifier"),
    _africa_bind(
        "pk-drap-register",
        (8,),
        "DRAP registration/provisional/historical native status identifier",
    ),
    _africa_bind("pk-neml", (8,), "Pakistan NEML entry identifier"),
    _africa_bind(
        "pk-drap-safety",
        (8,),
        "DRAP safety/recall/shortage notice identifier",
    ),
    _africa_bind(
        "eg-eda-register", (9,), "Egypt EDA product registration number"
    ),
    _africa_bind("eg-national-eml", (9,), "Egypt EML entry identifier"),
    _africa_bind("eg-eda-safety", (9,), "Egypt EDA safety notice identifier"),
    _africa_bind(
        "gh-fda-register", (9,), "Ghana FDA product registration number"
    ),
    _africa_bind("gh-national-eml", (9,), "Ghana EML/STG entry identifier"),
    _africa_bind("gh-fda-safety", (9,), "Ghana FDA safety/recall identifier"),
    _africa_bind(
        "rw-rwandafda-register",
        (9,),
        "Rwanda FDA product registration number",
    ),
    _africa_bind("rw-national-eml", (9,), "Rwanda EML entry identifier"),
    _africa_bind(
        "rw-rwandafda-safety",
        (9,),
        "Rwanda FDA safety notice identifier",
    ),
    _africa_bind(
        "sn-dpm-register", (9,), "Senegal DPM product registration number"
    ),
    _africa_bind("sn-national-eml", (9,), "Senegal EML/LNME entry identifier"),
    _africa_bind("sn-dpm-safety", (9,), "Senegal DPM safety notice identifier"),
    _africa_bind("zw-mcaz-register", (9,), "MCAZ product registration number"),
    _africa_bind("zw-national-eml", (9,), "Zimbabwe EML entry identifier"),
    _africa_bind("zw-mcaz-safety", (9,), "MCAZ safety/recall identifier"),
    _africa_bind(
        "mus-pharmacy-board-register",
        (9, 10),
        "Mauritius Pharmacy Board product registration number",
    ),
    _africa_bind(
        "mus-pharmacy-board-safety",
        (9, 10),
        "Mauritius safety/recall notice identifier",
        blocker="interactive_only public notices; rights review required",
    ),
    _africa_bind(
        "mus-approved-drug-list",
        (10,),
        "Mauritius Approved Drug List / EML entry identifier",
    ),
    _bind(
        "mus-historical-eml-archive",
        (10,),
        (CoverageFacet.EML_FORMULARY, CoverageFacet.HISTORICAL_DEPTH),
        native_identifier="Mauritius historical EML edition identifier",
        blocker="rights: historical edition archive only if lawful",
    ),
    _bind(
        "ng-nafdac-products",
        (9,),
        (CoverageFacet.REGULATOR, CoverageFacet.REGISTRATION),
        existing=True,
        native_identifier="NAFDAC registration number",
    ),
    _bind(
        "ng-nhia-medicines",
        (9,),
        (CoverageFacet.EML_FORMULARY, CoverageFacet.REIMBURSEMENT),
        existing=True,
        native_identifier="NHIA medicines list entry identifier",
    ),
    _bind(
        "za-sahpra-register",
        (9,),
        (CoverageFacet.REGULATOR, CoverageFacet.REGISTRATION),
        existing=True,
        native_identifier="SAHPRA register number",
    ),
    _africa_bind(
        "ng-nafdac-safety",
        (9,),
        "NAFDAC safety/recall notice identifier",
        blocker="interactive_only public notices; rights review required",
    ),
    _africa_bind(
        "za-sahpra-safety",
        (9,),
        "SAHPRA safety/recall notice identifier",
        blocker="interactive_only public notices; rights review required",
    ),
    _bind(
        "za-national-eml",
        (9,),
        (CoverageFacet.EML_FORMULARY,),
        existing=True,
        native_identifier="South Africa NEML entry identifier",
    ),
    _bind(
        "in-cdsco-approved-drugs",
        (11,),
        (CoverageFacet.REGISTRATION,),
        existing=True,
        native_identifier="CDSCO approved-drug identifier",
    ),
    _bind(
        "in-cdsco-products",
        (11,),
        (CoverageFacet.REGISTRATION,),
        native_identifier="CDSCO product/license identifier",
        blocker="interactive_only SUGAM/public product surfaces",
    ),
    _bind(
        "in-nlem",
        (11,),
        (CoverageFacet.EML_FORMULARY,),
        existing=True,
        native_identifier="India NLEM medicine identifier + list year",
    ),
    _bind(
        "in-nppa-ceiling-prices",
        (11,),
        (CoverageFacet.PRICING_PROCUREMENT,),
        native_identifier="NPPA scheduled-formulation ceiling-price identifier",
    ),
    _bind(
        "in-procurement-availability",
        (11,),
        (CoverageFacet.PRICING_PROCUREMENT,),
        native_identifier="India public procurement/availability source identifier",
        blocker="interactive_only/state-level portals; not a national transaction feed",
    ),
    _bind(
        "in-pvpi-safety",
        (11, 35),
        (CoverageFacet.PHARMACOVIGILANCE,),
        native_identifier="PvPI ICSRs are not public case-level bronze payloads",
        blocker="credentialed/restricted PV; metadata-only until lawful access",
    ),
    _bind(
        "us-fda-faers",
        (12,),
        (CoverageFacet.PHARMACOVIGILANCE, CoverageFacet.HISTORICAL_DEPTH),
        native_identifier="FAERS primaryid / caseid (case-version retained)",
    ),
    _bind(
        "us-openfda-faers",
        (12,),
        (CoverageFacet.PHARMACOVIGILANCE,),
        native_identifier="openFDA safetyreportid overlapping FAERS files",
        blocker="overlapping API vs files; do not silent-dedup",
    ),
    _bind(
        "us-openfda-enforcement",
        (13,),
        (CoverageFacet.RECALLS,),
        native_identifier="openFDA enforcement report number / event_id",
        blocker="overlapping API vs files; do not silent-dedup",
    ),
    _bind(
        "us-fda-recalls-notices",
        (13,),
        (CoverageFacet.RECALLS,),
        native_identifier="FDA recall firm-press notice identifier",
    ),
    _bind(
        "us-fda-drug-shortages",
        (14,),
        (CoverageFacet.SHORTAGES, CoverageFacet.HISTORICAL_DEPTH),
        native_identifier="FDA shortage drug/update identifier + snapshot date",
    ),
    _bind(
        "us-fda-rems",
        (15,),
        (CoverageFacet.REGISTRATION,),
        native_identifier="FDA REMS program/application identifier",
    ),
    _bind(
        "us-fda-orange-book",
        (16,),
        (CoverageFacet.REGISTRATION, CoverageFacet.HISTORICAL_DEPTH),
        existing=True,
        native_identifier="FDA Orange Book Appl_No + ingredient + TE code",
    ),
    _bind(
        "us-openfda-ndc",
        (17,),
        (CoverageFacet.REGISTRATION, CoverageFacet.TERMINOLOGY_SUBSTANCE),
        existing=True,
        native_identifier="NDC product_ndc / package_ndc",
    ),
    _bind(
        "us-fda-ndc-directory",
        (17,),
        (CoverageFacet.REGISTRATION,),
        native_identifier="FDA NDC Directory product/package NDC",
    ),
    _bind(
        "us-gsrs-unii",
        (18,),
        (CoverageFacet.TERMINOLOGY_SUBSTANCE,),
        existing=True,
        native_identifier="UNII",
    ),
    _bind(
        "us-fda-nsde",
        (19,),
        (CoverageFacet.TERMINOLOGY_SUBSTANCE, CoverageFacet.REGISTRATION),
        native_identifier="NSDE item code / NDC11 from FDA SPL NSDE zip",
    ),
    _bind(
        "us-openfda-nsde",
        (19,),
        (CoverageFacet.TERMINOLOGY_SUBSTANCE,),
        native_identifier="openFDA other/nsde package_ndc (derived, not authoritative origin)",
        blocker="openFDA is a derived API over NSDE, not the authoritative file",
    ),
    _bind(
        "eu-ema-medicines",
        (20, 25),
        (CoverageFacet.REGISTRATION,),
        existing=True,
        native_identifier="EMA medicine / product number / EU number",
    ),
    _bind(
        "eu-ema-json",
        (20,),
        (CoverageFacet.REGISTRATION,),
        existing=True,
        native_identifier="EMA JSON medicine/document identifier",
    ),
    _bind(
        "eu-ema-epar-documents",
        (20,),
        (CoverageFacet.REGISTRATION,),
        native_identifier="EPAR document identifier linked to EMA product number",
    ),
    _bind(
        "eu-eudravigilance-public",
        (21, 35),
        (CoverageFacet.PHARMACOVIGILANCE,),
        native_identifier="adrreports.eu aggregated reaction identifier",
        blocker="credentialed/restricted: public dashboard is not case-level data",
    ),
    _bind(
        "eu-ema-orphan",
        (22,),
        (CoverageFacet.REGISTRATION,),
        native_identifier="EMA orphan designation number + sponsor",
    ),
    _bind(
        "eu-ema-referrals",
        (23,),
        (CoverageFacet.REGISTRATION,),
        native_identifier="EMA referral procedure number",
    ),
    _bind(
        "eu-ema-safety-communications",
        (24,),
        (CoverageFacet.PHARMACOVIGILANCE,),
        native_identifier="EMA safety communication identifier",
    ),
    _bind(
        "eu-union-register",
        (25,),
        (CoverageFacet.REGISTRATION, CoverageFacet.HISTORICAL_DEPTH),
        existing=True,
        native_identifier="EU Union Register EU number",
    ),
    _bind(
        "eu-ema-article57",
        (26,),
        (CoverageFacet.REGISTRATION, CoverageFacet.TERMINOLOGY_SUBSTANCE),
        existing=True,
        native_identifier="Article 57 EV Code / organisation identifier",
    ),
    _bind(
        "eu-ema-xevmpd-credentialed",
        (26,),
        (CoverageFacet.REGISTRATION,),
        native_identifier="xEVMPD EV Code (credentialed payload)",
        blocker="credentialed xEVMPD payload; public Article 57 extract remains separate",
    ),
    _bind(
        "eu-spor-rms-oms",
        (27,),
        (CoverageFacet.TERMINOLOGY_SUBSTANCE,),
        existing=True,
        native_identifier="SPOR RMS/OMS identifier",
        blocker="credentialed SPOR surfaces remain metadata-only",
    ),
    _bind(
        "eu-ema-pms-fhir",
        (27,),
        (CoverageFacet.REGISTRATION, CoverageFacet.TERMINOLOGY_SUBSTANCE),
        existing=True,
        native_identifier="PMS FHIR resource identifier",
        blocker="credentialed EMA PMS FHIR; metadata-only is not coverage",
    ),
    _bind(
        "eu-spor-public-metadata",
        (27,),
        (CoverageFacet.TERMINOLOGY_SUBSTANCE,),
        native_identifier="Public SPOR/RMS/OMS metadata identifier",
    ),
    _bind(
        "gb-nice-ta",
        (28,),
        (CoverageFacet.REIMBURSEMENT, CoverageFacet.HISTORICAL_DEPTH),
        existing=True,
        native_identifier="NICE TA identifier including superseded guidance",
    ),
    _bind(
        "gb-nice-medicines-utilisation",
        (29,),
        (CoverageFacet.UTILISATION, CoverageFacet.HISTORICAL_DEPTH),
        native_identifier="NHS utilisation series identifier + methodology version",
    ),
    _bind(
        "gb-openprescribing",
        (30,),
        (CoverageFacet.UTILISATION,),
        native_identifier="BNF presentation code + practice/CCG + month",
        blocker="rights and volume: OpenPrescribing/EPD redistribution review required",
    ),
    _bind(
        "us-cms-partd-spending",
        (31,),
        (CoverageFacet.UTILISATION,),
        native_identifier="CMS Part D spending-by-drug brand/generic identifier",
    ),
    _bind(
        "us-cms-partd-formulary",
        (31,),
        (CoverageFacet.REIMBURSEMENT,),
        existing=True,
        native_identifier="CMS Part D formulary/plan identifier",
    ),
    _bind(
        "nl-gipdatabank",
        (32,),
        (CoverageFacet.UTILISATION,),
        native_identifier="GIPdatabank ATC/product + classification-version year",
    ),
    _bind(
        "dk-medstat-utilisation",
        (33,),
        (CoverageFacet.UTILISATION,),
        native_identifier="Medstat.dk ATC/product + year",
    ),
    _bind(
        "no-norpd-utilisation",
        (33,),
        (CoverageFacet.UTILISATION,),
        native_identifier="NorPD product/ATC identifier",
        blocker="historic anonymous report surface frozen through 2020",
    ),
    _bind(
        "se-socialstyrelsen-utilisation",
        (33,),
        (CoverageFacet.UTILISATION,),
        native_identifier="Socialstyrelsen läkemedelsstatistik ATC + year",
    ),
    _bind(
        "fr-open-medic",
        (34,),
        (CoverageFacet.UTILISATION,),
        native_identifier="Open Medic CIP/ATC + year + regime",
    ),
    _bind(
        "jp-mhlw-ndb-utilisation",
        (34,),
        (CoverageFacet.UTILISATION,),
        native_identifier="MHLW NDB tabulated identifier",
        blocker="credentialed/restricted NDB; public tables only if separately published",
    ),
    _bind(
        "ca-cihi-nhex-medicines",
        (34,),
        (CoverageFacet.UTILISATION,),
        native_identifier="CIHI NHEX/plan expenditure identifier",
        blocker="licensed/restricted CIHI extracts; metadata-only until rights",
    ),
    _bind(
        "ie-pcrs-reimbursement",
        (34,),
        (CoverageFacet.UTILISATION, CoverageFacet.REIMBURSEMENT),
        native_identifier="HSE PCRS ATC/product reimbursement identifier",
    ),
    _bind(
        "global-umc-vigibase",
        (35,),
        (CoverageFacet.PHARMACOVIGILANCE,),
        native_identifier="VigiBase/VigiLyze case identifier",
        blocker="credentialed UMC VigiBase; register only, no bronze payload",
    ),
    _bind(
        "gb-mhra-yellow-card",
        (35,),
        (CoverageFacet.PHARMACOVIGILANCE,),
        native_identifier="MHRA Yellow Card report identifier",
        blocker="interactive/restricted public outputs are not case-level bronze",
    ),
    _bind(
        "au-tga-daen",
        (35,),
        (CoverageFacet.PHARMACOVIGILANCE,),
        native_identifier="TGA DAEN case number",
        blocker="interactive DAEN; not complete case-level bronze",
    ),
    _bind(
        "ca-canada-vigilance",
        (35,),
        (CoverageFacet.PHARMACOVIGILANCE,),
        native_identifier="Canada Vigilance adverse reaction number",
    ),
    _bind(
        "jp-pmda-safety",
        (35,),
        (CoverageFacet.PHARMACOVIGILANCE,),
        native_identifier="PMDA safety report/alert identifier",
    ),
    _bind(
        "global-medicines-source-index",
        (36,),
        tuple(CoverageFacet),
        native_identifier="Atlas source-index identifier + catalog reviewed_at",
        existing=True,
    ),
)


# Track 36 uses a derived index identity that is not a live ingest source.
# It is catalogued as documentation metadata in the expansion program only.


def assert_program_invariants() -> None:
    tracks = expansion_tracks()
    if [track.track_id for track in tracks] != list(range(1, 37)):
        raise ValueError("expansion tracks must be 1-36 in order")
    bound_ids = {binding.source_id for binding in _BINDINGS}
    for track in tracks:
        for source_id in track.source_ids:
            if source_id == "global-medicines-source-index":
                continue
            if source_id not in bound_ids:
                raise ValueError(f"{source_id} lacks a binding")


AcquireWithoutGate = Literal["forbidden"]


def acquire_without_reuse_gate(source_id: str) -> None:
    raise ReuseGateRequiredError(
        f"reuse gate required before acquiring {source_id}"
    )
