"""Immutable identity emitted by offline trusted-profile admission."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .models import FrozenModel

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class AdmissionRecord(FrozenModel):
    """Exact admitted identity; it is not a publication or rights decision."""

    scope: Literal["offline_trusted_profile"] = "offline_trusted_profile"
    producer_repository: str
    contract_repository: str
    contract_commit: str
    schema_sha256: Digest
    evidence_kind: Literal["live", "synthetic"]
    dataset: str
    revision: str
    path: str
    byte_count: int = Field(ge=0)
    sha256: Digest
    layer: Literal["bronze", "silver", "gold", "platinum"]
    bronze_stratum: Literal["B0", "B1", "B2"] | None
    representation: Literal["index", "metadata", "raw", "projection"]
    source_id: str
    acquisition_id: str
    schema_era: str
    comparison_cohort: Literal["legacy", "current", "synthetic"]
    effective_date: str | None
    retrieved_at: str
    contract_sha256: Digest
