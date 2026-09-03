"""Read-only service boundary for admitted Platinum dataset identities."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol

from .platinum_surface_contracts import (
    DatasetIdentityEnvelope,
    dataset_identity,
)

if TYPE_CHECKING:
    from .platinum_resolver import ResolvedResource

_JURISDICTION = re.compile(r"[A-Z]{2,3}")


class UnknownPlatinumResourceError(LookupError):
    """The requested admitted resource is absent from this service."""


class DatasetIdentityLookup(Protocol):
    """Shared lookup contract consumed by CLI and API adapters."""

    def identity(self, resource_id: str) -> DatasetIdentityEnvelope: ...


class ResolverIdentityLookup(Protocol):
    """Resolver subset needed by this metadata-only service."""

    def resolve(self, resource_id: str) -> ResolvedResource: ...


class ResolverDatasetIdentityService:
    """Expose resolver identities without opening or querying their bytes."""

    def __init__(
        self,
        resolver: ResolverIdentityLookup,
        *,
        jurisdictions: Mapping[str, str],
    ) -> None:
        if not jurisdictions or any(
            not resource_id or _JURISDICTION.fullmatch(jurisdiction) is None
            for resource_id, jurisdiction in jurisdictions.items()
        ):
            raise ValueError("valid resource jurisdictions are required")
        self._resolver = resolver
        self._jurisdictions = dict(jurisdictions)

    def identity(self, resource_id: str) -> DatasetIdentityEnvelope:
        """Return one exact admitted identity without source-byte access."""
        try:
            jurisdiction = self._jurisdictions[resource_id]
            resolved = self._resolver.resolve(resource_id)
        except KeyError, ValueError:
            raise UnknownPlatinumResourceError from None
        return dataset_identity(resolved, jurisdiction=jurisdiction)


__all__ = [
    "DatasetIdentityLookup",
    "ResolverDatasetIdentityService",
    "UnknownPlatinumResourceError",
]
