"""Pure reconciliation for public Hub collections and the estate registry.

The caller supplies the complete collection-scoped denominator.  This module
performs no network or filesystem I/O and cannot publish, mutate visibility,
establish rights, or authenticate the supplied observations.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

_IDENTITY = re.compile(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+")
_REVISION = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class CollectionItem:
    """One exact dataset revision and its collection-specific public note."""

    dataset: str
    revision: str
    note: str


@dataclass(frozen=True)
class CollectionExpectation:
    """Caller-governed intended state for one populated collection."""

    identity: str
    title: str
    note: str
    items: tuple[CollectionItem, ...]


@dataclass(frozen=True)
class CollectionObservation:
    """Public-safe observed collection metadata supplied by the caller."""

    identity: str
    title: str
    private: bool
    note: str
    items: tuple[CollectionItem, ...]


@dataclass(frozen=True)
class RegistryEntry:
    """Exact dataset pin and its complete scoped collection membership."""

    dataset: str
    revision: str
    collections: tuple[str, ...]


@dataclass(frozen=True)
class EstateRegistryObservation:
    """Observed immutable public estate-registry projection."""

    dataset: str
    revision: str
    private: bool
    gated: bool | Literal["auto", "manual"]
    entries: tuple[RegistryEntry, ...]


@dataclass(frozen=True)
class CollectionEstateBinding:
    """Immutable summary of an exact offline reconciliation."""

    collections: tuple[str, ...]
    datasets: tuple[str, ...]
    registry_dataset: str
    registry_revision: str


def reconcile_collection_estate(
    expected: tuple[CollectionExpectation, ...],
    observed: tuple[CollectionObservation, ...],
    registry: EstateRegistryObservation,
    *,
    registry_dataset: str,
) -> CollectionEstateBinding:
    """Require exact public collection state and registry cross-membership.

    Passing this check means only that caller-supplied metadata is internally
    consistent with the caller-supplied complete scoped denominator.  It is not
    a publication receipt, live-Hub observation, or rights determination.
    """
    if not expected:
        raise ValueError("empty collection denominator")
    _identity(registry_dataset, "registry identity")
    expected_by_id = _unique_collections(expected, "expected")
    observed_by_id = _unique_collections(observed, "observed")
    if expected_by_id.keys() != observed_by_id.keys():
        raise ValueError("collection denominator mismatch")

    dataset_revisions: dict[str, str] = {}
    expected_memberships: dict[str, set[str]] = {}
    for wanted in expected:
        actual = observed_by_id[wanted.identity]
        _validate_collection_pair(wanted, actual)
        for item in wanted.items:
            prior = dataset_revisions.setdefault(item.dataset, item.revision)
            if prior != item.revision:
                raise ValueError("collection member revision conflict")
            expected_memberships.setdefault(item.dataset, set()).add(
                wanted.identity
            )

    registry_by_dataset = _validate_registry(registry, registry_dataset)
    if registry_by_dataset.keys() != dataset_revisions.keys():
        raise ValueError("stale or missing registry dataset")
    for dataset, revision in dataset_revisions.items():
        entry = registry_by_dataset[dataset]
        if entry.revision != revision:
            raise ValueError("registry revision mismatch")
        if set(entry.collections) != expected_memberships[dataset]:
            raise ValueError("registry collection membership mismatch")

    return CollectionEstateBinding(
        collections=tuple(item.identity for item in expected),
        datasets=tuple(dataset_revisions),
        registry_dataset=registry.dataset,
        registry_revision=registry.revision,
    )


def _validate_collection_pair(
    wanted: CollectionExpectation, actual: CollectionObservation
) -> None:
    _collection_header(wanted.identity, wanted.title, wanted.note)
    wanted_items = _unique_items(wanted.items)
    _collection_header(actual.identity, actual.title, actual.note)
    if type(actual.private) is not bool or actual.private:
        raise ValueError("collection must be public")
    if actual.title != wanted.title:
        raise ValueError("collection title mismatch")
    if actual.note != wanted.note:
        raise ValueError("collection note mismatch")
    if _unique_items(actual.items) != wanted_items:
        raise ValueError("collection member mismatch")


def _validate_registry(
    registry: EstateRegistryObservation, registry_dataset: str
) -> dict[str, RegistryEntry]:
    if registry.dataset != registry_dataset:
        raise ValueError("registry identity mismatch")
    _revision(registry.revision)
    if type(registry.private) is not bool or registry.private:
        raise ValueError("estate registry must be public")
    if type(registry.gated) is not bool or registry.gated:
        raise ValueError("estate registry must be non-gated")
    result: dict[str, RegistryEntry] = {}
    for entry in registry.entries:
        _identity(entry.dataset, "registry dataset identity")
        _revision(entry.revision)
        if entry.dataset in result:
            raise ValueError("duplicate registry dataset")
        if len(entry.collections) != len(set(entry.collections)):
            raise ValueError("duplicate registry collection membership")
        for identity in entry.collections:
            _identity(identity, "registry collection identity")
        result[entry.dataset] = entry
    return result


def _unique_collections[
    Collection: (CollectionExpectation, CollectionObservation)
](
    collections: Sequence[Collection],
    kind: str,
) -> dict[str, Collection]:
    result = {item.identity: item for item in collections}
    if len(result) != len(collections):
        raise ValueError(f"duplicate {kind} collection")
    return result


def _unique_items(items: tuple[CollectionItem, ...]) -> dict[str, CollectionItem]:
    result: dict[str, CollectionItem] = {}
    for item in items:
        _identity(item.dataset, "dataset identity")
        _revision(item.revision)
        _text(item.note, "collection member note")
        if item.dataset in result:
            raise ValueError("duplicate collection member")
        result[item.dataset] = item
    if not result:
        raise ValueError("collection must be populated")
    return result


def _collection_header(identity: str, title: str, note: str) -> None:
    _identity(identity, "collection identity")
    _text(title, "collection title")
    _text(note, "collection note")


def _identity(value: str, label: str) -> None:
    if type(value) is not str or _IDENTITY.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")


def _revision(value: str) -> None:
    if type(value) is not str or _REVISION.fullmatch(value) is None:
        raise ValueError("revision must be immutable")


def _text(value: str, label: str) -> None:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise ValueError(f"invalid {label}")
