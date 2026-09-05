"""Bounded Platinum envelope for historical comparison results."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from pydantic import AwareDatetime, model_validator

from .historical_change import HistoricalChange
from .platinum_surface_contracts import PlatinumSurfaceModel, Sha256


class HistoricalChangeEnvelope(PlatinumSurfaceModel):
    """A transport-safe change page that preserves missingness semantics."""

    schema_version: str = "1.0"
    generated_at: AwareDatetime
    comparison: HistoricalChange
    change_sha256: Sha256
    absence_is_negative_evidence: bool = False
    source_outage_is_negative_evidence: bool = False

    @model_validator(mode="after")
    def digest_matches(self) -> HistoricalChangeEnvelope:
        if self.change_sha256 != _digest(self.comparison):
            raise ValueError("historical change digest does not match payload")
        return self


def _digest(change: HistoricalChange) -> str:
    canonical = json.dumps(
        change.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_historical_change_envelope(
    change: HistoricalChange, *, generated_at: AwareDatetime | None = None
) -> HistoricalChangeEnvelope:
    """Wrap a validated comparison without inferring status from absence."""
    return HistoricalChangeEnvelope(
        generated_at=generated_at or datetime.now(UTC),
        comparison=change,
        change_sha256=_digest(change),
    )


__all__ = ["HistoricalChangeEnvelope", "build_historical_change_envelope"]
