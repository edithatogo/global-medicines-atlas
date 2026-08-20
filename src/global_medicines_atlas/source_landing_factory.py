"""Generate Bronze landing adapters and work from the source catalogue.

The factory deliberately produces acquisition configuration, not Silver
transformations. Network execution remains behind reuse, rights, credential,
admission, and receipt gates. Sparse overrides record exceptional evidence;
the governed source catalogue supplies the common case.
"""

from __future__ import annotations

import json
from collections import Counter
from enum import StrEnum
from pathlib import Path
from typing import Literal, cast

from pydantic import Field, model_validator

from .models import FrozenModel
from .receipts import DeterministicReceipt
from .source_catalog import (
    AccessMode,
    AuthenticationMode,
    IntegrationLayer,
    MedicineDataSource,
    SourceCatalog,
)

EvidenceScope = Literal[
    "live_receipt",
    "governed_fixture",
    "parser_contract",
    "none",
]

OVERRIDES_PATH = (
    Path(__file__).with_name("data") / "source_landing_overrides.json"
)
ARCHIVE_FORMATS = frozenset({"zip", "tar", "tar.gz", "tgz", "gzip", "7z"})
UNRESOLVED_RIGHTS_MARKERS = (
    "review",
    "terms apply",
    "agreement",
    "registration",
    "licence",
    "license",
    "verify endpoint terms",
)


class LandingAdapterFamily(StrEnum):
    """Reusable acquisition shapes supported by the Bronze factory."""

    STATIC_FILE_DOWNLOAD = "static_file_download"
    ARCHIVE_RELEASE = "archive_release"
    PAGINATED_REST_API = "paginated_rest_api"
    REGULATOR_SEARCH_EXPORT = "regulator_search_export"
    DOCUMENT_COLLECTION = "document_collection"
    MANUAL_REPRODUCIBLE_EXPORT = "manual_reproducible_export"


class LandingDisposition(StrEnum):
    """Exactly-one current state for each governed catalogue source."""

    LANDED = "landed_and_evidenced"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    RIGHTS_BLOCKED = "rights_blocked"
    CREDENTIALED_EXCLUDED = "credentialed_and_excluded"
    MANUAL_ONLY = "manual_only_documented_acquisition"
    SUPERSEDED_BY_REUSE = "superseded_by_reused_source"
    NOT_YET_IMPLEMENTED = "not_yet_implemented"


class LandingOverride(FrozenModel):
    """Sparse source-specific exception backed by machine-readable evidence."""

    source_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    family: LandingAdapterFamily | None = None
    state: LandingDisposition | None = None
    failure_receipt: str | None = Field(default=None, min_length=1)
    reuse_reference: str | None = Field(default=None, min_length=1)
    manual_instructions: str | None = Field(default=None, min_length=1)
    evidence_references: tuple[str, ...] = ()

    @model_validator(mode="after")
    def exceptional_states_have_evidence(self) -> LandingOverride:
        if (
            self.state is LandingDisposition.TEMPORARILY_UNAVAILABLE
            and self.failure_receipt is None
        ):
            raise ValueError("temporarily unavailable requires failure receipt")
        if (
            self.state is LandingDisposition.SUPERSEDED_BY_REUSE
            and self.reuse_reference is None
        ):
            raise ValueError("superseded source requires reuse reference")
        if (
            self.state is LandingDisposition.MANUAL_ONLY
            and self.manual_instructions is None
        ):
            raise ValueError("manual-only source requires manual instructions")
        if (
            self.state is LandingDisposition.LANDED
            and not self.evidence_references
        ):
            raise ValueError("landed override requires evidence references")
        return self


class LandingOverrides(FrozenModel):
    """Versioned sparse exceptions to catalogue-derived factory defaults."""

    schema_version: Literal[1] = 1
    overrides: tuple[LandingOverride, ...] = ()

    @model_validator(mode="after")
    def source_ids_are_unique(self) -> LandingOverrides:
        ids = [item.source_id for item in self.overrides]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate source override")
        return self

    @classmethod
    def load(cls, path: Path = OVERRIDES_PATH) -> LandingOverrides:
        """Load the committed sparse override contract."""

        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class LandingAdapterConfig(FrozenModel):
    """Standardized family configuration for one catalogue source."""

    source_id: str = Field(min_length=1)
    family: LandingAdapterFamily
    endpoint: str = Field(min_length=1)
    formats: tuple[str, ...] = Field(min_length=1)
    acquisition_profile: str | None = None
    acquisition_instructions: str = Field(min_length=1)
    pagination: Literal["none", "source_config_required", "manual"]
    preserves_source_bytes: Literal[True] = True
    requires_reuse_gate: Literal[True] = True
    requires_rights_gate: Literal[True] = True
    credentials_persisted: Literal[False] = False


class SourceLandingWorkItem(FrozenModel):
    """One deterministic Conductor queue item derived from the catalogue."""

    source_id: str = Field(min_length=1)
    state: LandingDisposition
    evidence_scope: EvidenceScope
    adapter: LandingAdapterConfig
    reason: str = Field(min_length=1)
    evidence_references: tuple[str, ...] = Field(min_length=1)
    next_action: str = Field(min_length=1)
    priority: int = Field(ge=0, le=100)

    @property
    def endpoint(self) -> str:
        """Expose the configured public endpoint without request material."""

        return self.adapter.endpoint


class SourceLandingQueue(DeterministicReceipt):
    """Exhaustive source-family work queue generated from the catalogue."""

    schema_id: Literal["global-medicines-atlas.bronze-source-landing-queue"] = (
        "global-medicines-atlas.bronze-source-landing-queue"
    )
    schema_version: Literal[1] = 1
    catalog_schema_version: int = Field(ge=1)
    catalog_reviewed_at: str = Field(min_length=10)
    source_count: int = Field(ge=1)
    state_counts: dict[LandingDisposition, int]
    family_counts: dict[LandingAdapterFamily, int]
    items: tuple[SourceLandingWorkItem, ...] = Field(min_length=1)
    silver_transformations_included: Literal[False] = False

    @model_validator(mode="after")
    def queue_is_exhaustive(self) -> SourceLandingQueue:
        ids = [item.source_id for item in self.items]
        if len(ids) != self.source_count or len(ids) != len(set(ids)):
            raise ValueError("queue must contain each source exactly once")
        if sum(self.state_counts.values()) != self.source_count:
            raise ValueError("state counts must cover every source")
        if sum(self.family_counts.values()) != self.source_count:
            raise ValueError("family counts must cover every source")
        if set(self.state_counts) != set(LandingDisposition):
            raise ValueError("state counts must declare every disposition")
        if set(self.family_counts) != set(LandingAdapterFamily):
            raise ValueError("family counts must declare every adapter family")
        return self


def family_for_source(
    source: MedicineDataSource,
    override: LandingOverride | None = None,
) -> LandingAdapterFamily:
    """Select one reusable adapter family from governed source metadata."""

    if override is not None and override.family is not None:
        return override.family
    formats = {item.lower() for item in source.formats}
    if source.access_mode in {AccessMode.API, AccessMode.API_AND_DOWNLOAD}:
        family = LandingAdapterFamily.PAGINATED_REST_API
    elif formats.intersection(ARCHIVE_FORMATS):
        family = LandingAdapterFamily.ARCHIVE_RELEASE
    elif source.access_mode is AccessMode.WEB_SEARCH:
        family = LandingAdapterFamily.REGULATOR_SEARCH_EXPORT
    elif source.access_mode is AccessMode.DOCUMENT or "pdf" in formats:
        family = LandingAdapterFamily.DOCUMENT_COLLECTION
    elif source.access_mode is AccessMode.DOWNLOAD:
        family = LandingAdapterFamily.STATIC_FILE_DOWNLOAD
    else:
        family = LandingAdapterFamily.MANUAL_REPRODUCIBLE_EXPORT
    return family


def _endpoint(source: MedicineDataSource, family: LandingAdapterFamily) -> str:
    if family is LandingAdapterFamily.PAGINATED_REST_API:
        endpoint = source.api_url
    elif family in {
        LandingAdapterFamily.STATIC_FILE_DOWNLOAD,
        LandingAdapterFamily.ARCHIVE_RELEASE,
    }:
        endpoint = source.download_url
    else:
        endpoint = source.landing_page
    return str(endpoint or source.documentation_url)


def _adapter(
    source: MedicineDataSource,
    family: LandingAdapterFamily,
    override: LandingOverride | None,
) -> LandingAdapterConfig:
    pagination: Literal["none", "source_config_required", "manual"] = "none"
    if family is LandingAdapterFamily.PAGINATED_REST_API:
        pagination = "source_config_required"
    elif family in {
        LandingAdapterFamily.REGULATOR_SEARCH_EXPORT,
        LandingAdapterFamily.DOCUMENT_COLLECTION,
        LandingAdapterFamily.MANUAL_REPRODUCIBLE_EXPORT,
    }:
        pagination = "manual"
    instructions = {
        LandingAdapterFamily.STATIC_FILE_DOWNLOAD: (
            "Download the public source file, preserve the response bytes, and "
            "issue a content-addressed receipt."
        ),
        LandingAdapterFamily.ARCHIVE_RELEASE: (
            "Download and receipt the archive before safely enumerating and "
            "extracting its members."
        ),
        LandingAdapterFamily.PAGINATED_REST_API: (
            "Traverse the configured API pagination contract, preserve each "
            "source response, and receipt the completed page set."
        ),
        LandingAdapterFamily.REGULATOR_SEARCH_EXPORT: (
            "Record the public search filters, export the complete result set, "
            "and receipt the source-native export."
        ),
        LandingAdapterFamily.DOCUMENT_COLLECTION: (
            "Enumerate the public collection, preserve each document unchanged, "
            "and receipt the collection manifest."
        ),
        LandingAdapterFamily.MANUAL_REPRODUCIBLE_EXPORT: (
            "Follow the documented public retrieval steps, record parameters, "
            "and receipt the source-native export."
        ),
    }[family]
    if override is not None and override.manual_instructions is not None:
        instructions = override.manual_instructions
    return LandingAdapterConfig(
        source_id=source.source_id,
        family=family,
        endpoint=_endpoint(source, family),
        formats=source.formats,
        acquisition_profile=source.acquisition_profile,
        acquisition_instructions=instructions,
        pagination=pagination,
    )


def _evidence_scope(
    source: MedicineDataSource,
) -> EvidenceScope:
    if source.integration_layer is IntegrationLayer.LIVE_RECEIPT:
        return "live_receipt"
    if source.integration_layer is IntegrationLayer.FIXTURE:
        return "governed_fixture"
    if source.integration_layer is IntegrationLayer.PARSER:
        return "parser_contract"
    return "none"


def _rights_unresolved(source: MedicineDataSource) -> bool:
    rights = source.rights_status.lower()
    return any(marker in rights for marker in UNRESOLVED_RIGHTS_MARKERS)


def _derived_state(
    source: MedicineDataSource,
    family: LandingAdapterFamily,
) -> LandingDisposition:
    if source.implemented_ingestion and source.qualification_references:
        return LandingDisposition.LANDED
    if source.authentication is not AuthenticationMode.NONE:
        return LandingDisposition.CREDENTIALED_EXCLUDED
    if family in {
        LandingAdapterFamily.REGULATOR_SEARCH_EXPORT,
        LandingAdapterFamily.DOCUMENT_COLLECTION,
        LandingAdapterFamily.MANUAL_REPRODUCIBLE_EXPORT,
    }:
        return LandingDisposition.MANUAL_ONLY
    if _rights_unresolved(source):
        return LandingDisposition.RIGHTS_BLOCKED
    return LandingDisposition.NOT_YET_IMPLEMENTED


def _state_reason(
    source: MedicineDataSource,
    state: LandingDisposition,
    override: LandingOverride | None,
) -> str:
    if override is not None:
        return override.reason
    reasons = {
        LandingDisposition.LANDED: (
            "catalogue implementation claim has committed qualification evidence"
        ),
        LandingDisposition.CREDENTIALED_EXCLUDED: (
            f"authentication mode {source.authentication.value} is excluded"
        ),
        LandingDisposition.MANUAL_ONLY: (
            "public interactive or document surface requires a documented "
            "reproducible acquisition step"
        ),
        LandingDisposition.RIGHTS_BLOCKED: (
            f"source-specific retention and transformation rights unresolved: "
            f"{source.rights_status}"
        ),
        LandingDisposition.NOT_YET_IMPLEMENTED: (
            "family configuration is available but source execution is pending"
        ),
        LandingDisposition.TEMPORARILY_UNAVAILABLE: (
            "a failure receipt records temporary source unavailability"
        ),
        LandingDisposition.SUPERSEDED_BY_REUSE: (
            "reuse evidence supersedes an independent source copy"
        ),
    }
    return reasons[state]


def _evidence_references(
    source: MedicineDataSource,
    state: LandingDisposition,
    override: LandingOverride | None,
) -> tuple[str, ...]:
    references = list(source.qualification_references)
    if override is not None:
        references.extend(override.evidence_references)
        if override.failure_receipt is not None:
            references.append(override.failure_receipt)
        if override.reuse_reference is not None:
            references.append(override.reuse_reference)
    if not references:
        references.append(str(source.documentation_url))
    if state is LandingDisposition.LANDED and not references:
        raise ValueError(f"landed source lacks evidence: {source.source_id}")
    return tuple(dict.fromkeys(references))


def _next_action(
    state: LandingDisposition,
    family: LandingAdapterFamily,
) -> str:
    actions = {
        LandingDisposition.LANDED: "verify receipt freshness on schedule",
        LandingDisposition.TEMPORARILY_UNAVAILABLE: (
            "retry under the failure-receipt schedule"
        ),
        LandingDisposition.RIGHTS_BLOCKED: (
            "record source-specific retention and transformation rights"
        ),
        LandingDisposition.CREDENTIALED_EXCLUDED: (
            "retain exclusion until credentials are explicitly authorised"
        ),
        LandingDisposition.MANUAL_ONLY: (
            "execute and receipt the documented public manual acquisition"
        ),
        LandingDisposition.SUPERSEDED_BY_REUSE: (
            "verify the reused source receipt remains current"
        ),
        LandingDisposition.NOT_YET_IMPLEMENTED: (
            f"configure and test the {family.value} adapter"
        ),
    }
    return actions[state]


def _priority(state: LandingDisposition) -> int:
    return {
        LandingDisposition.NOT_YET_IMPLEMENTED: 10,
        LandingDisposition.RIGHTS_BLOCKED: 20,
        LandingDisposition.MANUAL_ONLY: 30,
        LandingDisposition.TEMPORARILY_UNAVAILABLE: 40,
        LandingDisposition.LANDED: 90,
        LandingDisposition.SUPERSEDED_BY_REUSE: 95,
        LandingDisposition.CREDENTIALED_EXCLUDED: 100,
    }[state]


def build_source_landing_queue(
    catalog: SourceCatalog,
    overrides: LandingOverrides,
) -> SourceLandingQueue:
    """Generate the complete deterministic landing queue from the catalogue."""

    sources = {source.source_id: source for source in catalog.sources}
    override_by_id = {item.source_id: item for item in overrides.overrides}
    unknown = sorted(set(override_by_id) - set(sources))
    if unknown:
        raise ValueError(f"overrides name unknown catalog sources: {unknown}")

    items: list[SourceLandingWorkItem] = []
    for source_id in sorted(sources):
        source = sources[source_id]
        override = override_by_id.get(source_id)
        family = family_for_source(source, override)
        state = (
            override.state
            if override is not None and override.state is not None
            else _derived_state(source, family)
        )
        if (
            source.authentication is not AuthenticationMode.NONE
            and state is not (LandingDisposition.CREDENTIALED_EXCLUDED)
        ):
            raise ValueError(
                f"credentialed source cannot leave exclusion: {source_id}"
            )
        items.append(
            SourceLandingWorkItem(
                source_id=source_id,
                state=state,
                evidence_scope=(
                    _evidence_scope(source)
                    if state is LandingDisposition.LANDED
                    else "none"
                ),
                adapter=_adapter(source, family, override),
                reason=_state_reason(source, state, override),
                evidence_references=_evidence_references(
                    source, state, override
                ),
                next_action=_next_action(state, family),
                priority=_priority(state),
            )
        )

    state_counter = Counter(item.state for item in items)
    family_counter = Counter(item.adapter.family for item in items)
    return SourceLandingQueue(
        catalog_schema_version=catalog.schema_version,
        catalog_reviewed_at=catalog.reviewed_at.isoformat(),
        source_count=len(items),
        state_counts={
            state: state_counter[state] for state in LandingDisposition
        },
        family_counts={
            family: family_counter[family] for family in LandingAdapterFamily
        },
        items=tuple(items),
    )


def render_conductor_queue(queue: SourceLandingQueue) -> str:
    """Render an exhaustive generated Markdown queue for Conductor."""

    lines = [
        "# Generated Bronze source landing queue",
        "",
        "Generated from `medicine_source_catalog.json` and sparse governed ",
        "overrides. Do not edit this file by hand.",
        "",
        f"Catalogue sources: **{queue.source_count}**.",
        "Silver transformations included: **no**.",
        "",
        "## State summary",
        "",
    ]
    lines.extend(
        f"- `{state.value}`: {queue.state_counts[state]}"
        for state in LandingDisposition
    )
    completed = {
        LandingDisposition.LANDED,
        LandingDisposition.CREDENTIALED_EXCLUDED,
        LandingDisposition.SUPERSEDED_BY_REUSE,
    }
    for family in LandingAdapterFamily:
        lines.extend(("", f"## `{family.value}`", ""))
        family_items = [
            item for item in queue.items if item.adapter.family is family
        ]
        for item in family_items:
            marker = "x" if item.state in completed else " "
            lines.append(
                f"- [{marker}] `{item.source_id}` — `{item.state.value}`; "
                f"{item.next_action}."
            )
    return "\n".join(lines) + "\n"


def load_override_document(path: Path = OVERRIDES_PATH) -> dict[str, object]:
    """Return the raw override document for independent schema tooling."""

    value = cast("object", json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(value, dict):
        raise TypeError("landing overrides must be a JSON object")
    return cast("dict[str, object]", value)
