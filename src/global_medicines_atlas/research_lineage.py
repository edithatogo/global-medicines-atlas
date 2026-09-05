"""Metadata-only lineage receipts for rebuildable research exports.

The receipt records identities and public locations only.  Source payloads and
export bytes remain outside this Platinum projection and are never embedded.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Literal

from pydantic import Field, model_validator

from .models import FrozenModel

_SHA256 = r"^[0-9a-f]{64}$"


class ResearchLineageArtifact(FrozenModel):
    """A content-addressed input or output reference without payload bytes."""

    identifier: str = Field(min_length=1)
    role: Literal["input", "output"]
    public_url: str = Field(min_length=1)
    sha256: str = Field(pattern=_SHA256)


class ResearchLineageReceipt(FrozenModel):
    """Deterministic lineage envelope for one research-export revision."""

    schema_id: Literal["global-medicines-atlas.research-lineage"]
    schema_version: Literal[1]
    export_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    artifacts: tuple[ResearchLineageArtifact, ...] = Field(min_length=1)
    payloads_embedded: Literal[False] = False

    @model_validator(mode="after")
    def require_input_and_output(self) -> ResearchLineageReceipt:
        roles = {artifact.role for artifact in self.artifacts}
        if roles != {"input", "output"}:
            raise ValueError(
                "lineage receipt requires input and output artifacts"
            )
        identifiers = tuple(artifact.identifier for artifact in self.artifacts)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("lineage artifact identifiers must be unique")
        return self

    def document(self) -> dict[str, object]:
        """Return canonical, payload-free receipt metadata."""

        return self.model_dump(mode="json")

    def canonical_bytes(self) -> bytes:
        return (
            json.dumps(
                self.document(), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            + b"\n"
        )

    def sha256(self) -> str:
        """Return the digest of the canonical metadata receipt."""

        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def build_research_lineage_receipt(
    *,
    export_id: str,
    revision: str,
    artifacts: Sequence[ResearchLineageArtifact],
) -> ResearchLineageReceipt:
    """Build a stable receipt by sorting artifacts by identifier."""

    def artifact_identifier(artifact: ResearchLineageArtifact) -> str:
        return artifact.identifier

    return ResearchLineageReceipt(
        schema_id="global-medicines-atlas.research-lineage",
        schema_version=1,
        export_id=export_id,
        revision=revision,
        artifacts=tuple(sorted(artifacts, key=artifact_identifier)),
    )
