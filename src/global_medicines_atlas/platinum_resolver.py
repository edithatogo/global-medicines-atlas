"""Storage-neutral Platinum identity resolution and bounded verified reads.

The caller must supply independently admitted v4 contract digests and
distribution bindings.  This module does not discover, admit, publish, query,
or persist a dataset; it resolves product identifiers and delegates exact byte
retrieval to the existing anonymous bounded federation reader.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import threading
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Self

if TYPE_CHECKING:
    import httpx

from .federation_distribution import (
    DistributionBinding,
    reconcile_distribution,
)
from .federation_reader import FederatedReader, VerifiedRead

SemanticDimension = Literal[
    "service_benefit", "funding", "formulary", "regulatory", "terminology"
]
EntityGranularity = Literal[
    "service_item",
    "medicine_item",
    "evidence_edge",
    "history_event",
    "coverage_record",
    "provenance_record",
]
Capability = Literal[
    "exact_v4_resolution",
    "anonymous_verified_read",
    "verified_cache_offline",
]
BASE_CAPABILITIES: tuple[Capability, ...] = (
    "exact_v4_resolution",
    "anonymous_verified_read",
)
RESOURCE_LIMIT = 256
SEMANTIC_MANIFEST_BYTES = 16 * 1024
_RESOURCE_ID = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)+")
_DIMENSIONS = {
    "service_benefit",
    "funding",
    "formulary",
    "regulatory",
    "terminology",
}
_GRANULARITIES = {
    "service_item",
    "medicine_item",
    "evidence_edge",
    "history_event",
    "coverage_record",
    "provenance_record",
}


@dataclass(frozen=True)
class ProductResource:
    """Product-facing semantics bound to exact reconciled v4 bytes."""

    resource_id: str
    semantic_dimension: SemanticDimension
    entity_granularity: EntityGranularity
    binding: DistributionBinding
    contract: bytes
    semantic_manifest: bytes


@dataclass(frozen=True)
class ResolvedResource:
    """Storage-neutral immutable identity returned without I/O."""

    resource_id: str
    semantic_dimension: SemanticDimension
    entity_granularity: EntityGranularity
    dataset: str
    revision: str
    path: str
    sha256: str
    byte_count: int
    contract_sha256: str
    source_id: str
    acquisition_id: str
    layer: str
    cache_expires_at: datetime
    capabilities: tuple[Capability, ...]


@dataclass(frozen=True)
class CacheReceipt:
    """Current transient-cache state and the last verified read evidence."""

    resource_id: str
    contract_sha256: str
    object_sha256: str
    byte_count: int
    status: Literal["verified_exact_digest", "unavailable"]
    last_origin: Literal["remote", "verified_cache"] | None
    last_verified_at: datetime | None
    expires_at: datetime
    max_read_bytes: int
    cache_budget_bytes: int
    max_cache_entries: int
    max_open_reads: int
    timeout_seconds: float


@dataclass(frozen=True)
class ProductRead:
    """Resolved metadata paired with a context-owned verified byte stream."""

    metadata: ResolvedResource
    verified: VerifiedRead
    cache_receipt: CacheReceipt


class StorageNeutralResolver:
    """Resolve exact product resources and perform bounded anonymous reads."""

    def __init__(
        self,
        *,
        schema: bytes,
        resources: Sequence[ProductResource],
        admitted_contracts: frozenset[str],
        admitted_semantic_manifests: frozenset[str],
        max_read_bytes: int = 64 * 1024 * 1024,
        cache_bytes: int = 64 * 1024 * 1024,
        max_cache_entries: int = 32,
        max_open_reads: int = 2,
        timeout_seconds: float = 30,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        transport_factory: Callable[[], httpx.BaseTransport] | None = None,
    ) -> None:
        _budgets(
            max_read_bytes,
            cache_bytes,
            max_cache_entries,
            max_open_reads,
            timeout_seconds,
        )
        if not resources or len(resources) > RESOURCE_LIMIT:
            raise ValueError("resource denominator exceeds budget")
        self._resources: dict[str, tuple[ResolvedResource, bytes]] = {}
        self._last_reads: dict[
            str, tuple[Literal["remote", "verified_cache"], datetime]
        ] = {}
        self._receipt_lock = threading.Lock()
        self._clock = clock
        self._max_read_bytes = max_read_bytes
        self._cache_bytes = cache_bytes
        self._max_cache_entries = max_cache_entries
        self._max_open_reads = max_open_reads
        self._timeout_seconds = timeout_seconds
        contract_digests: set[str] = set()
        observed_at = clock()
        for resource in resources:
            resolved = _resolve_resource(
                resource,
                schema,
                admitted_semantic_manifests,
                cache_bytes=cache_bytes,
                observed_at=observed_at,
            )
            if resource.resource_id in self._resources:
                raise ValueError("duplicate resource identity")
            if resolved.contract_sha256 in contract_digests:
                raise ValueError("contract alias across product resources")
            if resolved.byte_count > max_read_bytes:
                raise ValueError("resource exceeds read budget")
            contract_digests.add(resolved.contract_sha256)
            self._resources[resource.resource_id] = (
                resolved,
                bytes(resource.contract),
            )
        if not contract_digests <= admitted_contracts:
            raise ValueError("resource contract is not independently admitted")
        self._reader = FederatedReader(
            schema=schema,
            admitted_contracts=admitted_contracts,
            max_object_bytes=max_read_bytes,
            cache_bytes=cache_bytes,
            max_entries=max_cache_entries,
            max_open_reads=max_open_reads,
            timeout_seconds=timeout_seconds,
            clock=clock,
            transport_factory=transport_factory,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @property
    def cached_bytes(self) -> int:
        """Return bounded verified-cache occupancy from the shared reader."""
        return self._reader.cached_bytes

    def resolve(self, resource_id: str) -> ResolvedResource:
        """Resolve one logical identifier without storage or network access."""
        try:
            resolved = self._resources[resource_id][0]
        except KeyError:
            raise ValueError("unknown resource identity") from None
        if (
            "verified_cache_offline" in resolved.capabilities
            and resolved.cache_expires_at <= self._clock()
        ):
            return replace(resolved, capabilities=BASE_CAPABILITIES)
        return resolved

    def cache_receipt(self, resource_id: str) -> CacheReceipt:
        """Return dynamic cache availability without creating durable state."""
        metadata = self.resolve(resource_id)
        available = self._reader.has_cached(metadata.contract_sha256)
        with self._receipt_lock:
            last = self._last_reads.get(resource_id)
        return CacheReceipt(
            resource_id=resource_id,
            contract_sha256=metadata.contract_sha256,
            object_sha256=metadata.sha256,
            byte_count=metadata.byte_count,
            status="verified_exact_digest" if available else "unavailable",
            last_origin=last[0] if last else None,
            last_verified_at=last[1] if last else None,
            expires_at=metadata.cache_expires_at,
            max_read_bytes=self._max_read_bytes,
            cache_budget_bytes=self._cache_bytes,
            max_cache_entries=self._max_cache_entries,
            max_open_reads=self._max_open_reads,
            timeout_seconds=self._timeout_seconds,
        )

    @contextmanager
    def open(
        self, resource_id: str, *, offline: bool = False
    ) -> Generator[ProductRead]:
        """Yield exact verified bytes; offline misses fail explicitly."""
        metadata = self.resolve(resource_id)
        contract = self._resources[resource_id][1]
        with self._reader.open(contract, offline=offline) as verified:
            if (
                verified.contract_sha256 != metadata.contract_sha256
                or verified.sha256 != metadata.sha256
                or verified.byte_count != metadata.byte_count
            ):
                raise ValueError("resolved read identity mismatch")
            with self._receipt_lock:
                self._last_reads[resource_id] = (
                    verified.origin,
                    self._clock(),
                )
            yield ProductRead(
                metadata,
                verified,
                self.cache_receipt(resource_id),
            )

    def evict(self) -> None:
        """Remove only transient verified cache objects owned by this resolver."""
        self._reader.evict()

    def close(self) -> None:
        """Close the transient cache; remote identities remain untouched."""
        self._reader.close()


def _resolve_resource(
    resource: ProductResource,
    schema: bytes,
    admitted_semantic_manifests: frozenset[str],
    *,
    cache_bytes: int,
    observed_at: datetime,
) -> ResolvedResource:
    if (
        type(resource.resource_id) is not str
        or _RESOURCE_ID.fullmatch(resource.resource_id) is None
    ):
        raise ValueError("invalid resource identity")
    if resource.semantic_dimension not in _DIMENSIONS:
        raise ValueError("invalid semantic dimension")
    if resource.entity_granularity not in _GRANULARITIES:
        raise ValueError("invalid entity granularity")
    digest = hashlib.sha256(resource.contract).hexdigest()
    if digest != resource.binding.contract_sha256:
        raise ValueError("binding contract digest mismatch")
    try:
        binding = reconcile_distribution(
            [resource.binding.object],
            [resource.contract],
            schema=schema,
            destinations={
                resource.binding.object.layer: resource.binding.dataset
            },
        )[0]
    except ValueError:
        raise ValueError("distribution binding mismatch") from None
    if binding != resource.binding:
        raise ValueError("distribution binding mismatch")
    obj = binding.object
    document: dict[str, Any] = json.loads(resource.contract)
    _semantic_admission(resource, digest, admitted_semantic_manifests)
    expires_at = datetime.fromisoformat(document["cache"]["expires_at"])
    capabilities = BASE_CAPABILITIES
    if (
        document["cache"]["offline_behavior"] == "verified_exact_digest_only"
        and obj.byte_count <= cache_bytes
        and obj.byte_count <= document["cache"]["max_bytes"]
        and expires_at > observed_at
    ):
        capabilities += ("verified_cache_offline",)
    return ResolvedResource(
        resource_id=resource.resource_id,
        semantic_dimension=resource.semantic_dimension,
        entity_granularity=resource.entity_granularity,
        dataset=binding.dataset,
        revision=binding.revision,
        path=obj.path,
        sha256=obj.sha256,
        byte_count=obj.byte_count,
        contract_sha256=binding.contract_sha256,
        source_id=obj.source_id,
        acquisition_id=obj.acquisition_id,
        layer=obj.layer,
        cache_expires_at=expires_at,
        capabilities=capabilities,
    )


def _semantic_admission(
    resource: ProductResource,
    contract_sha256: str,
    admitted: frozenset[str],
) -> None:
    if len(resource.semantic_manifest) > SEMANTIC_MANIFEST_BYTES:
        raise ValueError("semantic manifest exceeds metadata budget")
    digest = hashlib.sha256(resource.semantic_manifest).hexdigest()
    if digest not in admitted:
        raise ValueError("semantic manifest is not independently admitted")
    try:
        manifest = json.loads(
            resource.semantic_manifest,
            object_pairs_hook=_unique_object,
        )
    except TypeError, ValueError:
        raise ValueError("invalid semantic manifest") from None
    expected = {
        "contract_sha256": contract_sha256,
        "entity_granularity": resource.entity_granularity,
        "resource_id": resource.resource_id,
        "semantic_dimension": resource.semantic_dimension,
        "version": "1.0",
    }
    if manifest != expected:
        raise ValueError("semantic manifest claims mismatch")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate semantic manifest key")
    return result


def _budgets(
    max_read_bytes: int,
    cache_bytes: int,
    max_cache_entries: int,
    max_open_reads: int,
    timeout_seconds: float,
) -> None:
    for value in (
        max_read_bytes,
        cache_bytes,
        max_cache_entries,
        max_open_reads,
    ):
        if type(value) is not int or value <= 0:
            raise ValueError("resolver budgets must be positive integers")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("resolver timeout must be finite and positive")
