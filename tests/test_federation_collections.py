"""Offline collection/registry reconciliation; never a Hub mutation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from global_medicines_atlas.federation_collections import (
    CollectionEstateBinding,
    CollectionExpectation,
    CollectionItem,
    CollectionObservation,
    EstateRegistryObservation,
    RegistryEntry,
    reconcile_collection_estate,
)

MBS = CollectionItem(
    dataset="edithatogo/australian-mbs-source-archive",
    revision="a" * 40,
    note="Exact source-native MBS archive; raw evidence is not duplicated here.",
)
PBS = CollectionItem(
    dataset="edithatogo/australian-pbs-source-archive",
    revision="b" * 40,
    note="Exact source-native PBS archive; raw evidence is not duplicated here.",
)


def expectation() -> CollectionExpectation:
    return CollectionExpectation(
        identity="edithatogo/policy-aus-123",
        title="Policy AUS",
        note="Australian policy data, with source archives kept distinct.",
        items=(MBS, PBS),
    )


def observation() -> CollectionObservation:
    expected = expectation()
    return CollectionObservation(
        identity=expected.identity,
        title=expected.title,
        private=False,
        note=expected.note,
        items=expected.items,
    )


def registry() -> EstateRegistryObservation:
    collection = expectation()
    return EstateRegistryObservation(
        dataset="edithatogo/dataset-estate-registry",
        revision="c" * 40,
        private=False,
        gated=False,
        entries=tuple(
            RegistryEntry(
                dataset=item.dataset,
                revision=item.revision,
                collections=(collection.identity,),
            )
            for item in collection.items
        ),
    )


def reconcile(
    *,
    expected: tuple[CollectionExpectation, ...] | None = None,
    observed: tuple[CollectionObservation, ...] | None = None,
    estate: EstateRegistryObservation | None = None,
) -> CollectionEstateBinding:
    return reconcile_collection_estate(
        (expectation(),) if expected is None else expected,
        (observation(),) if observed is None else observed,
        registry() if estate is None else estate,
        registry_dataset="edithatogo/dataset-estate-registry",
    )


def test_exact_public_collection_and_registry_reconcile() -> None:
    result = reconcile()
    assert result.collections == (expectation().identity,)
    assert result.datasets == (MBS.dataset, PBS.dataset)
    assert result.registry_revision == "c" * 40


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("private", True, "public"),
        ("title", "Policy Australia", "title"),
        ("note", "stale metadata-only note", "note"),
        ("identity", "edithatogo/other-123", "collection"),
    ],
)
def test_collection_visibility_identity_and_notes_are_exact(
    field: str, value: object, message: str
) -> None:
    changed = replace(observation(), **{field: value})
    with pytest.raises(ValueError, match=message):
        reconcile(observed=(changed,))


@pytest.mark.parametrize("mode", ["missing", "extra", "duplicate"])
def test_collection_denominator_is_a_bijection(mode: str) -> None:
    observed = [observation()]
    if mode == "missing":
        observed.clear()
    elif mode == "extra":
        observed.append(
            replace(observation(), identity="edithatogo/unexpected-123")
        )
    else:
        observed.append(observation())
    with pytest.raises(ValueError, match=r"collection|duplicate"):
        reconcile(observed=tuple(observed))


@pytest.mark.parametrize("mode", ["missing", "extra", "duplicate", "drift"])
def test_member_identity_revision_and_note_cannot_drift(mode: str) -> None:
    items = list(observation().items)
    if mode == "missing":
        items.pop()
    elif mode == "extra":
        items.append(
            CollectionItem(
                dataset="edithatogo/unexpected",
                revision="d" * 40,
                note="Unexpected dataset.",
            )
        )
    elif mode == "duplicate":
        items.append(items[0])
    else:
        items[0] = replace(items[0], revision="d" * 40)
    with pytest.raises(ValueError, match=r"member|duplicate"):
        reconcile(observed=(replace(observation(), items=tuple(items)),))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("dataset", "edithatogo/wrong-registry", "registry identity"),
        ("revision", "main", "immutable"),
        ("private", True, "public"),
        ("gated", "auto", "non-gated"),
    ],
)
def test_registry_identity_revision_and_visibility_are_bound(
    field: str, value: object, message: str
) -> None:
    changed = replace(registry(), **{field: value})
    with pytest.raises(ValueError, match=message):
        reconcile(estate=changed)


@pytest.mark.parametrize("mode", ["missing", "stale", "revision", "membership"])
def test_registry_is_exact_for_the_scoped_dataset_denominator(mode: str) -> None:
    entries = list(registry().entries)
    if mode == "missing":
        entries.pop()
    elif mode == "stale":
        entries.append(
            RegistryEntry(
                dataset="edithatogo/removed-dataset",
                revision="d" * 40,
                collections=(expectation().identity,),
            )
        )
    elif mode == "revision":
        entries[0] = replace(entries[0], revision="d" * 40)
    else:
        entries[0] = replace(entries[0], collections=())
    with pytest.raises(ValueError, match=r"registry|stale"):
        reconcile(estate=replace(registry(), entries=tuple(entries)))


def test_multiple_collections_require_complete_cross_membership() -> None:
    heor = CollectionExpectation(
        identity="edithatogo/heor-123",
        title="Health Economics and Outcomes Research",
        note="Public medallion and HEOR datasets, distinguished from raw archives.",
        items=(PBS,),
    )
    observed_heor = CollectionObservation(
        identity=heor.identity,
        title=heor.title,
        private=False,
        note=heor.note,
        items=heor.items,
    )
    entries = list(registry().entries)
    entries[1] = replace(
        entries[1], collections=(expectation().identity, heor.identity)
    )
    result = reconcile_collection_estate(
        (expectation(), heor),
        (observation(), observed_heor),
        replace(registry(), entries=tuple(entries)),
        registry_dataset="edithatogo/dataset-estate-registry",
    )
    assert result.collections == (expectation().identity, heor.identity)


@pytest.mark.parametrize(
    "item",
    [
        replace(MBS, revision="main"),
        replace(MBS, note=" "),
        replace(MBS, dataset="not-a-dataset"),
    ],
)
def test_mutable_or_malformed_collection_items_fail_closed(
    item: CollectionItem,
) -> None:
    expected = replace(expectation(), items=(item, PBS))
    with pytest.raises(ValueError, match=r"immutable|note|identity"):
        reconcile(expected=(expected,))
