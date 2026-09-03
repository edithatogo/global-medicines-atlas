"""Strict shared response contracts for Platinum CLI and API surfaces."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from .platinum_resolver import ResolvedResource

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Revision = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]


class PlatinumSurfaceModel(BaseModel):
    """Immutable public model that rejects undocumented fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DatasetIdentityEnvelope(PlatinumSurfaceModel):
    """One independently admitted resource identity, without row claims."""

    version: Literal["1.0"] = "1.0"
    resource_id: str = Field(min_length=1, max_length=256)
    dataset: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    revision: Revision
    path: str = Field(min_length=1, max_length=2048)
    object_sha256: Sha256
    byte_count: int = Field(gt=0)
    contract_sha256: Sha256
    semantic_manifest_sha256: Sha256
    semantic_dimension: str = Field(min_length=1)
    entity_granularity: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    acquisition_id: str = Field(min_length=1)
    layer: str = Field(min_length=1)
    schema_era: str = Field(min_length=1)
    comparison_cohort: Literal["legacy", "current", "synthetic"]
    effective_date: str | None
    retrieved_at: AwareDatetime
    cache_expires_at: AwareDatetime
    capabilities: tuple[str, ...]
    product_admitted: Literal[True] = True
    rows_queried: Literal[False] = False


def dataset_identity(resource: ResolvedResource) -> DatasetIdentityEnvelope:
    """Translate one admitted resolver result without performing I/O."""
    return DatasetIdentityEnvelope(
        resource_id=resource.resource_id,
        dataset=resource.dataset,
        revision=resource.revision,
        path=resource.path,
        object_sha256=resource.sha256,
        byte_count=resource.byte_count,
        contract_sha256=resource.contract_sha256,
        semantic_manifest_sha256=resource.semantic_manifest_sha256,
        semantic_dimension=resource.semantic_dimension,
        entity_granularity=resource.entity_granularity,
        source_id=resource.source_id,
        acquisition_id=resource.acquisition_id,
        layer=resource.layer,
        schema_era=resource.schema_era,
        comparison_cohort=resource.comparison_cohort,
        effective_date=resource.effective_date,
        retrieved_at=datetime.fromisoformat(resource.retrieved_at),
        cache_expires_at=resource.cache_expires_at,
        capabilities=resource.capabilities,
    )


__all__ = ["DatasetIdentityEnvelope", "dataset_identity"]
