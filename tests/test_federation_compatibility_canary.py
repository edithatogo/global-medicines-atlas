"""Synthetic federation compatibility canaries; no remote reads or publication."""

from __future__ import annotations

from dataclasses import replace

import pytest

from global_medicines_atlas.federation_compatibility import (
    CompatibilitySnapshot,
    compare_federation_snapshots,
)

BASE = CompatibilitySnapshot(
    dataset="example/benefits",
    revision="a" * 40,
    schema_sha256="b" * 64,
    semantic_dimension="service_benefit",
    required_fields=frozenset({"id", "amount"}),
    successor_dataset="example/benefits-v2",
)


def test_identical_immutable_snapshots_are_compatible() -> None:
    result = compare_federation_snapshots(BASE, BASE)
    assert result.compatible
    assert result.reasons == ()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"revision": "c" * 40}, "revision drift"),
        ({"schema_sha256": "c" * 64}, "schema drift"),
        ({"semantic_dimension": "funding"}, "semantic dimension drift"),
        ({"required_fields": frozenset({"id"})}, "missing required fields"),
        ({"successor_dataset": None}, "successor link drift"),
    ],
)
def test_drift_is_reported_fail_closed(
    change: dict[str, object], message: str
) -> None:
    candidate = replace(BASE, **change)
    result = compare_federation_snapshots(BASE, candidate)
    assert not result.compatible
    assert message in result.reasons


@pytest.mark.parametrize("revision", ["", "HEAD", "a" * 39, "g" * 40])
def test_mutable_or_unpinned_revisions_are_rejected(revision: str) -> None:
    with pytest.raises(ValueError, match="immutable revision"):
        compare_federation_snapshots(BASE, replace(BASE, revision=revision))


def test_successor_must_be_explicit_and_nonempty() -> None:
    with pytest.raises(ValueError, match="successor"):
        compare_federation_snapshots(BASE, replace(BASE, successor_dataset=""))


@pytest.mark.parametrize("field", ["", " id", "id ", "field name"])
def test_required_field_names_are_canonical(field: str) -> None:
    with pytest.raises(ValueError, match="required fields"):
        compare_federation_snapshots(
            BASE, replace(BASE, required_fields=frozenset({field}))
        )


@pytest.mark.parametrize(
    ("field", "message"),
    [(" example/benefits", "dataset identity"), ("service benefit", "semantic dimension")],
)
def test_snapshot_identity_labels_are_canonical(field: str, message: str) -> None:
    change = {"dataset": field} if message == "dataset identity" else {"semantic_dimension": field}
    with pytest.raises(ValueError, match=message):
        compare_federation_snapshots(BASE, replace(BASE, **change))


@pytest.mark.edge
def test_successor_identity_rejects_embedded_whitespace() -> None:
    with pytest.raises(ValueError, match="successor"):
        compare_federation_snapshots(
            BASE, replace(BASE, successor_dataset="example/benefits v2")
        )
