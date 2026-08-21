"""Deterministic B0 Source Index projections over the governed catalogue."""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Literal

import orjson
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import Field, model_validator

from .models import FrozenModel
from .source_catalog import (
    DiscoveryStatus,
    SourceCatalog,
)
from .source_landing_factory import (
    EvidenceScope,
    LandingDisposition,
    SourceLandingQueue,
)

SHA256_PATTERN = r"^[0-9a-f]{64}$"
SOURCE_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
INDEX_JSON_PATH = "quality/qualifications/bronze-source-index-v1.json"
INDEX_PARQUET_PATH = "quality/qualifications/bronze-source-index-v1.parquet"


class B0SourceIndexRow(FrozenModel):
    """One citable B0 declaration with independent evidence states."""

    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    jurisdictions: tuple[str, ...] = Field(min_length=1)
    authority: str = Field(min_length=1)
    title: str = Field(min_length=1)
    information_domains: tuple[str, ...] = Field(min_length=1)
    landing_page: str = Field(min_length=1)
    api_url: str = ""
    download_url: str = ""
    documentation_url: str = Field(min_length=1)
    access_mode: str = Field(min_length=1)
    authentication: str = Field(min_length=1)
    expected_formats: tuple[str, ...] = Field(min_length=1)
    acquisition_family: str = Field(min_length=1)
    update_cadence: str = Field(min_length=1)
    source_health_policy: str = Field(min_length=1)
    schema_drift_policy: str = Field(min_length=1)
    rights_review_state: str = Field(min_length=1)
    discovery_state: str = Field(min_length=1)
    metadata_verified: bool
    current_landing_disposition: str = Field(min_length=1)
    evidence_scope: EvidenceScope
    qualification_state: str = Field(min_length=1)
    qualification_references: tuple[str, ...] = ()
    supersession_or_reuse_reference: str = ""
    last_reviewed_at: str = Field(min_length=10)
    last_verified_at: str = Field(min_length=10)
    indexed: Literal[True] = True
    index_presence_implies_coverage: Literal[False] = False
    missing_source_is_negative_evidence: Literal[False] = False

    @model_validator(mode="after")
    def metadata_state_matches_discovery_evidence(self) -> B0SourceIndexRow:
        expected = self.discovery_state != DiscoveryStatus.DISCOVERY_ONLY.value
        if self.metadata_verified != expected:
            raise ValueError(
                "metadata_verified must follow discovery evidence, not index presence"
            )
        return self


class B0SourceIndex(FrozenModel):
    """Versioned B0 snapshot derived from the canonical source catalogue."""

    schema_id: Literal["global-medicines-atlas.b0-source-index"] = (
        "global-medicines-atlas.b0-source-index"
    )
    schema_version: Literal[1] = 1
    dataset_id: Literal["global-medicines-source-index"] = (
        "global-medicines-source-index"
    )
    stratum: Literal["B0 Source Index"] = "B0 Source Index"
    generated_from: Literal[
        "src/global_medicines_atlas/data/medicine_source_catalog.json"
    ] = "src/global_medicines_atlas/data/medicine_source_catalog.json"
    catalog_schema_version: int = Field(ge=1)
    catalog_reviewed_at: str = Field(min_length=10)
    snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
    snapshot_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_count: int = Field(ge=1)
    discovery_state_counts: dict[str, int]
    evidence_scope_counts: dict[str, int]
    qualification_state_counts: dict[str, int]
    landing_disposition_counts: dict[str, int]
    sources: tuple[B0SourceIndexRow, ...] = Field(min_length=1)
    index_presence_implies_coverage: Literal[False] = False
    missing_source_is_negative_evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_identity_and_counts(self) -> B0SourceIndex:
        ids = [source.source_id for source in self.sources]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("B0 sources must have unique sorted stable IDs")
        if self.source_count != len(ids):
            raise ValueError("B0 source_count must match source rows")
        count_sets = (
            (self.discovery_state_counts, "discovery_state"),
            (self.evidence_scope_counts, "evidence_scope"),
            (self.qualification_state_counts, "qualification_state"),
            (
                self.landing_disposition_counts,
                "current_landing_disposition",
            ),
        )
        for counts, field in count_sets:
            observed = Counter(
                str(getattr(source, field)) for source in self.sources
            )
            if dict(sorted(observed.items())) != counts:
                raise ValueError(f"B0 {field} counts do not match source rows")
        expected = _snapshot_sha256(
            catalog_schema_version=self.catalog_schema_version,
            catalog_reviewed_at=self.catalog_reviewed_at,
            sources=self.sources,
        )
        if self.snapshot_sha256 != expected:
            raise ValueError("B0 snapshot digest does not match canonical rows")
        if self.snapshot_id != f"sha256:{expected}":
            raise ValueError("B0 snapshot ID must bind the canonical digest")
        return self


def _snapshot_sha256(
    *,
    catalog_schema_version: int,
    catalog_reviewed_at: str,
    sources: tuple[B0SourceIndexRow, ...],
) -> str:
    payload = {
        "catalog_reviewed_at": catalog_reviewed_at,
        "catalog_schema_version": catalog_schema_version,
        "dataset_id": "global-medicines-source-index",
        "schema_id": "global-medicines-atlas.b0-source-index",
        "schema_version": 1,
        "sources": [source.model_dump(mode="json") for source in sources],
    }
    canonical = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    return hashlib.sha256(canonical).hexdigest()


def build_b0_source_index(
    catalog: SourceCatalog,
    queue: SourceLandingQueue,
) -> B0SourceIndex:
    """Project the catalogue and landing queue into one exhaustive B0 index."""

    queue_by_id = {item.source_id: item for item in queue.items}
    catalog_ids = {source.source_id for source in catalog.sources}
    if set(queue_by_id) != catalog_ids:
        raise ValueError("landing queue and source catalogue IDs must match")

    rows: list[B0SourceIndexRow] = []
    for source in sorted(catalog.sources, key=lambda item: item.source_id):
        work = queue_by_id[source.source_id]
        relationship = ""
        if work.state is LandingDisposition.SUPERSEDED_BY_REUSE:
            relationship = work.evidence_references[-1]
        rows.append(
            B0SourceIndexRow(
                source_id=source.source_id,
                jurisdictions=source.jurisdictions,
                authority=source.authority,
                title=source.title,
                information_domains=tuple(
                    item.value for item in source.information_domains
                ),
                landing_page=str(source.landing_page),
                api_url="" if source.api_url is None else str(source.api_url),
                download_url=(
                    ""
                    if source.download_url is None
                    else str(source.download_url)
                ),
                documentation_url=str(source.documentation_url),
                access_mode=source.access_mode.value,
                authentication=source.authentication.value,
                expected_formats=source.formats,
                acquisition_family=work.adapter.family.value,
                update_cadence=source.update_cadence,
                source_health_policy=source.monitoring.source_health,
                schema_drift_policy=source.monitoring.schema_drift,
                rights_review_state=source.rights_status,
                discovery_state=source.discovery_status.value,
                metadata_verified=(
                    source.discovery_status
                    is not DiscoveryStatus.DISCOVERY_ONLY
                ),
                current_landing_disposition=work.state.value,
                evidence_scope=work.evidence_scope,
                qualification_state=source.qualification_state.value,
                qualification_references=source.qualification_references,
                supersession_or_reuse_reference=relationship,
                last_reviewed_at=catalog.reviewed_at.isoformat(),
                last_verified_at=source.last_verified_at.isoformat(),
            )
        )
    sources = tuple(rows)
    digest = _snapshot_sha256(
        catalog_schema_version=catalog.schema_version,
        catalog_reviewed_at=catalog.reviewed_at.isoformat(),
        sources=sources,
    )
    return B0SourceIndex(
        catalog_schema_version=catalog.schema_version,
        catalog_reviewed_at=catalog.reviewed_at.isoformat(),
        snapshot_sha256=digest,
        snapshot_id=f"sha256:{digest}",
        source_count=len(sources),
        discovery_state_counts=_counts(sources, "discovery_state"),
        evidence_scope_counts=_counts(sources, "evidence_scope"),
        qualification_state_counts=_counts(sources, "qualification_state"),
        landing_disposition_counts=_counts(
            sources, "current_landing_disposition"
        ),
        sources=sources,
    )


def _counts(
    sources: tuple[B0SourceIndexRow, ...], field: str
) -> dict[str, int]:
    return dict(
        sorted(
            Counter(str(getattr(source, field)) for source in sources).items()
        )
    )


def source_index_parquet_bytes(index: B0SourceIndex) -> bytes:
    """Render stable Arrow/Parquet bytes for the B0 source rows."""

    rows = [source.model_dump(mode="json") for source in index.sources]
    table = pa.Table.from_pylist(rows)
    table = table.replace_schema_metadata({
        b"schema_name": index.schema_id.encode(),
        b"schema_version": str(index.schema_version).encode(),
        b"stratum": index.stratum.encode(),
        b"snapshot_sha256": index.snapshot_sha256.encode(),
        b"catalog_reviewed_at": index.catalog_reviewed_at.encode(),
        b"index_presence_implies_coverage": b"false",
        b"missing_source_is_negative_evidence": b"false",
    })
    sink = pa.BufferOutputStream()
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        table,
        sink,
        compression="zstd",
        compression_level=9,
        data_page_version="2.0",
        use_dictionary=False,
        write_page_index=False,
        write_statistics=True,
        version="2.6",
    )
    return sink.getvalue().to_pybytes()


def render_b0_source_index_markdown(index: B0SourceIndex) -> str:
    """Render human-readable documentation from the exact B0 snapshot."""

    lines = [
        "# Bronze B0 Source Index",
        "",
        (
            "> Generated from `medicine_source_catalog.json` and the governed "
            "Bronze landing queue. Do not edit this file by hand."
        ),
        "",
        f"- Snapshot: `{index.snapshot_id}`",
        f"- Catalogue reviewed: `{index.catalog_reviewed_at}`",
        f"- Indexed sources: `{index.source_count}`",
        "- External publication: `not performed`",
        "",
        (
            "Index presence is discovery metadata only. Indexed is not metadata "
            "verified; metadata verified is not payload acquired; a governed "
            "fixture is not a live acquisition; payload acquisition is not "
            "current source qualification; and a missing source is not negative "
            "medicines evidence."
        ),
        "",
        "## State counts",
        "",
    ]
    for label, counts in (
        ("Discovery", index.discovery_state_counts),
        ("Evidence", index.evidence_scope_counts),
        ("Qualification", index.qualification_state_counts),
        ("Landing", index.landing_disposition_counts),
    ):
        rendered = ", ".join(
            f"`{key}` {value}" for key, value in counts.items()
        )
        lines.append(f"- {label}: {rendered}")
    lines.extend([
        "",
        "## Sources",
        "",
        "| Source ID | Jurisdiction | Authority | Domains | Discovery | Evidence | Qualification | Landing |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    lines.extend(
        (
            "| "
            + " | ".join((
                f"`{source.source_id}`",
                ", ".join(source.jurisdictions),
                source.authority.replace("|", "\\|"),
                ", ".join(source.information_domains),
                source.discovery_state,
                source.evidence_scope,
                source.qualification_state,
                source.current_landing_disposition,
            ))
            + " |"
        )
        for source in index.sources
    )
    return "\n".join(lines) + "\n"


def build_b0_source_index_dataset_metadata(
    index: B0SourceIndex,
    *,
    json_sha256: str,
    parquet_sha256: str,
) -> dict[str, object]:
    """Prepare citation and dataset metadata without publishing externally."""

    return {
        "schema_id": "global-medicines-atlas.b0-source-index-dataset-metadata",
        "schema_version": 1,
        "title": "Global Medicines Atlas B0 Source Index",
        "dataset_id": index.dataset_id,
        "description": (
            "Versioned discovery index of medicines-related authorities and "
            "source surfaces; index presence is not coverage or qualification."
        ),
        "snapshot_id": index.snapshot_id,
        "snapshot_sha256": index.snapshot_sha256,
        "source_count": index.source_count,
        "catalog_reviewed_at": index.catalog_reviewed_at,
        "license": "Apache-2.0 for repository-generated index metadata only",
        "external_publication_performed": False,
        "related_catalogue_archive": {
            "url": (
                "https://huggingface.co/datasets/"
                "edithatogo/global-medicines-atlas-catalogue"
            ),
            "role": "archive_output_not_source_of_truth",
            "snapshot_published": False,
        },
        "citation": {
            "title": "Global Medicines Atlas B0 Source Index",
            "version": index.snapshot_id,
            "repository": (
                "https://github.com/edithatogo/global-medicines-atlas"
            ),
            "preferred_citation": (
                "Global Medicines Atlas contributors. Global Medicines Atlas "
                f"B0 Source Index ({index.snapshot_id})."
            ),
        },
        "distributions": [
            {
                "path": INDEX_JSON_PATH,
                "format": "JSON",
                "media_type": "application/json",
                "sha256": json_sha256,
            },
            {
                "path": INDEX_PARQUET_PATH,
                "format": "Parquet",
                "media_type": "application/vnd.apache.parquet",
                "sha256": parquet_sha256,
            },
        ],
        "evidence_boundary": {
            "index_presence_implies_coverage": False,
            "missing_source_is_negative_evidence": False,
            "fixtures_are_live_acquisitions": False,
            "payload_acquisition_implies_current_qualification": False,
        },
    }
