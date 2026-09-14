"""Read-only service boundary for admitted Platinum dataset identities."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol

from pydantic import Field, model_validator

from .platinum_surface_contracts import (
    DatasetIdentityEnvelope,
    PlatinumSurfaceModel,
    dataset_identity,
)

if TYPE_CHECKING:
    from .platinum_resolver import ResolvedResource

_JURISDICTION = re.compile(r"[A-Z]{2,3}")
_RESOURCE_JURISDICTION = re.compile(r"(?P<jurisdiction>[a-z]{2,3})\.")


class UnknownPlatinumResourceError(LookupError):
    """The requested admitted resource is absent from this service."""


class DatasetIdentityPage(PlatinumSurfaceModel):
    """A small, deterministic catalogue of already-admitted identities."""

    datasets: tuple[DatasetIdentityEnvelope, ...] = Field(
        min_length=1, max_length=32
    )
    returned: int = Field(ge=1, le=32)

    @model_validator(mode="after")
    def returned_matches_datasets(self) -> DatasetIdentityPage:
        if self.returned != len(self.datasets):
            raise ValueError("dataset page returned count must match datasets")
        if tuple(sorted(item.resource_id for item in self.datasets)) != tuple(
            item.resource_id for item in self.datasets
        ):
            raise ValueError(
                "dataset page must be ordered by resource identity"
            )
        return self


class DatasetIdentityLookup(Protocol):
    """Shared lookup contract consumed by CLI and API adapters."""

    def identity(self, resource_id: str) -> DatasetIdentityEnvelope: ...

    def identities(self) -> DatasetIdentityPage: ...


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
            not resource_id
            or _JURISDICTION.fullmatch(jurisdiction) is None
            or (match := _RESOURCE_JURISDICTION.match(resource_id)) is None
            or match.group("jurisdiction").upper() != jurisdiction
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

    def identities(self) -> DatasetIdentityPage:
        """Return every configured identity in stable resource-id order."""
        datasets = tuple(
            self.identity(resource_id)
            for resource_id in sorted(self._jurisdictions)
        )
        return DatasetIdentityPage(datasets=datasets, returned=len(datasets))


__all__ = [
    "DatasetIdentityLookup",
    "DatasetIdentityPage",
    "ResolverDatasetIdentityService",
    "UnknownPlatinumResourceError",
]
