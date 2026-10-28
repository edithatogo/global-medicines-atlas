"""Metadata-only lineage receipts for rebuildable research exports.

The receipt records identities and public locations only.  Source payloads and
export bytes remain outside this Platinum projection and are never embedded.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Literal, cast
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, model_validator

from .models import FrozenModel

LOCAL_LINEAGE_SCHEMA_VERSION = 3
_SHA256 = r"^[0-9a-f]{64}$"
_REVISION = r"^[0-9a-f]{40}$"


class ResearchLineageArtifact(FrozenModel):
    """A content-addressed input or output reference without payload bytes."""

    model_config = ConfigDict(revalidate_instances="always")

    identifier: str = Field(min_length=1)
    role: Literal["input", "output"]
    public_url: str | None = Field(
        default=None, min_length=1, exclude_if=lambda value: value is None
    )
    content_address: str | None = Field(
        default=None, min_length=1, exclude_if=lambda value: value is None
    )
    sha256: str = Field(pattern=_SHA256)
    revision: str | None = Field(default=None, pattern=_REVISION)

    @model_validator(mode="after")
    def require_public_https_url(self) -> ResearchLineageArtifact:
        if (self.public_url is None) == (self.content_address is None):
            raise ValueError(
                "lineage requires one public URL or local content address"
            )
        if self.content_address is not None:
            if (
                self.role != "output"
                or self.content_address != f"urn:sha256:{self.sha256}"
                or self.revision is not None
            ):
                raise ValueError(
                    "local output content address or revision differs"
                )
            return self
        parsed = urlsplit(cast("str", self.public_url))
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("lineage artifact URL must be public HTTPS")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError(
                "lineage artifact URL must not contain credentials"
            )
        if parsed.fragment:
            raise ValueError("lineage artifact URL must not contain a fragment")
        return self


class ResearchLineageReceipt(FrozenModel):
    """Deterministic lineage envelope for one research-export revision."""

    schema_id: Literal["global-medicines-atlas.research-lineage"]
    schema_version: Literal[1, 2, 3]
    export_id: str = Field(min_length=1)
    revision: str = Field(pattern=_REVISION)
    revision_scope: Literal["assembly_commit"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    artifacts: tuple[ResearchLineageArtifact, ...] = Field(min_length=1)
    payloads_embedded: Literal[False] = False

    @model_validator(mode="after")
    def require_input_and_output(self) -> ResearchLineageReceipt:
        if self.schema_version == 1 and any(
            artifact.revision is not None for artifact in self.artifacts
        ):
            raise ValueError(
                "artifact revisions require research-lineage schema version 2"
            )
        self._validate_local_scope()
        roles = {artifact.role for artifact in self.artifacts}
        if roles != {"input", "output"}:
            raise ValueError(
                "lineage receipt requires input and output artifacts"
            )
        identifiers = tuple(artifact.identifier for artifact in self.artifacts)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("lineage artifact identifiers must be unique")
        for artifact in self.artifacts:
            artifact_revision = artifact.revision or self.revision
            if artifact.role == "output" and artifact_revision != self.revision:
                raise ValueError(
                    "lineage output revision must match the export revision"
                )
            if artifact.content_address is not None:
                continue
            path_parts = tuple(
                part
                for part in urlsplit(
                    cast("str", artifact.public_url)
                ).path.split("/")
                if part
            )
            if artifact_revision not in path_parts:
                raise ValueError(
                    "lineage artifact URL must bind to the declared immutable revision"
                )
        return self

    def _validate_local_scope(self) -> None:
        local = [
            artifact
            for artifact in self.artifacts
            if artifact.content_address is not None
        ]
        if (self.schema_version == LOCAL_LINEAGE_SCHEMA_VERSION) != bool(local):
            raise ValueError(
                "local output requires research-lineage schema version 3"
            )
        if local and self.revision_scope != "assembly_commit":
            raise ValueError("local lineage requires an assembly commit scope")
        if not local and self.revision_scope is not None:
            raise ValueError("public lineage cannot claim local assembly scope")
        if local and any(
            a.role == "input" and a.revision is None for a in self.artifacts
        ):
            raise ValueError(
                "local lineage inputs require explicit source revisions"
            )
        if local and (
            len(local) != 1
            or sum(a.role == "output" for a in self.artifacts) != 1
        ):
            raise ValueError("local lineage requires exactly one local output")

    def document(self) -> dict[str, object]:
        """Return canonical, payload-free receipt metadata."""

        return self.model_dump(mode="json", exclude_none=True)

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

    normalized_artifacts = tuple(sorted(artifacts, key=artifact_identifier))
    schema_version: Literal[1, 2, 3] = (
        3
        if any(a.content_address is not None for a in normalized_artifacts)
        else 2
        if any(a.revision is not None for a in normalized_artifacts)
        else 1
    )
    return ResearchLineageReceipt(
        schema_id="global-medicines-atlas.research-lineage",
        schema_version=schema_version,
        export_id=export_id,
        revision=revision,
        revision_scope="assembly_commit"
        if schema_version == LOCAL_LINEAGE_SCHEMA_VERSION
        else None,
        artifacts=normalized_artifacts,
    )
