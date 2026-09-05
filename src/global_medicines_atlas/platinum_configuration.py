"""Bounded operator-controlled configuration of already-admitted resources.

The trust file must be provisioned independently of candidate metadata. This
loader verifies its expectations; it cannot establish who approved that file.
It performs no network requests or admission decisions.
"""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .federation_distribution import DistributionBinding
from .platinum_resolver import ProductResource, StorageNeutralResolver
from .platinum_types import EntityGranularity, SemanticDimension

_MAX_BYTES = 1024 * 1024
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ResourceConfiguration(BaseModel):
    """Trusted identity/binding plus paths to untrusted candidate metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    resource_id: str
    semantic_dimension: SemanticDimension
    entity_granularity: EntityGranularity
    binding: DistributionBinding
    semantic_sha256: Digest
    contract_path: str
    semantic_path: str


class DeploymentTrust(BaseModel):
    """Operator-supplied allowlist, never generated from candidate contents."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal["1.0"]
    resources: tuple[ResourceConfiguration, ...] = Field(
        min_length=1, max_length=32
    )


def _read(path: Path) -> bytes:
    if not path.is_file():
        raise ValueError("configuration metadata must be a regular file")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("configuration metadata must be a regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            data = stream.read(_MAX_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(data) > _MAX_BYTES:
        raise ValueError("configuration metadata exceeds byte bound")
    return data


def _candidate(root: Path, relative: str) -> bytes:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("candidate metadata path must remain inside root")
    resolved = (root / candidate).resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("candidate metadata path must remain inside root")
    return _read(resolved)


def load_benefits_resolver(
    *, trust_file: Path, metadata_root: Path, schema_file: Path
) -> StorageNeutralResolver:
    """Check separate trust expectations before constructing a read resolver.

    Only metadata files are read. The resolver independently enforces schema,
    binding and semantic identities; its construction does not fetch payloads.
    """
    trust = DeploymentTrust.model_validate_json(_read(trust_file))
    root = metadata_root.resolve(strict=True)
    resources: list[ProductResource] = []
    for entry in trust.resources:
        contract = _candidate(root, entry.contract_path)
        semantic = _candidate(root, entry.semantic_path)
        if (
            hashlib.sha256(contract).hexdigest()
            != entry.binding.contract_sha256
        ):
            raise ValueError("candidate contract differs from operator trust")
        if hashlib.sha256(semantic).hexdigest() != entry.semantic_sha256:
            raise ValueError("candidate semantics differ from operator trust")
        resources.append(
            ProductResource(
                resource_id=entry.resource_id,
                semantic_dimension=entry.semantic_dimension,
                entity_granularity=entry.entity_granularity,
                binding=entry.binding,
                contract=contract,
                semantic_manifest=semantic,
            )
        )
    return StorageNeutralResolver(
        schema=_read(schema_file),
        resources=resources,
        admitted_contracts=frozenset(
            entry.binding.contract_sha256 for entry in trust.resources
        ),
        admitted_semantic_manifests=frozenset(
            entry.semantic_sha256 for entry in trust.resources
        ),
    )
