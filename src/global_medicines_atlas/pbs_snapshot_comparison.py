"""Deterministic, source-faithful comparison of two PBS snapshots.

This module deliberately compares literal projected rows only.  It does not
infer that a missing item was ceased, nor does it qualify either snapshot as
current.  Callers must provide the snapshot labels (for example ``legacy``
and ``current``) and retain the returned uncertainty for downstream use.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal, TypedDict

ChangeKind = Literal["addition", "cessation", "change"]


class PbsSnapshotChange(TypedDict):
    key: str
    kind: ChangeKind
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    interpretation: Literal["literal_snapshot_difference"]


def compare_pbs_snapshots(
    legacy: Iterable[Mapping[str, Any]],
    current: Iterable[Mapping[str, Any]],
    *,
    key: str = "native_xml_id",
) -> list[PbsSnapshotChange]:
    """Return stable literal additions, cessations, and changes.

    A cessation means a key present in ``legacy`` is absent from ``current``;
    it is *not* a regulatory or commercial cessation claim. Duplicate keys,
    missing keys, and unhashable key values fail closed. Values are copied into
    ordinary dictionaries so the result cannot alias caller-owned mappings.
    """

    def index(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            if key not in row or not isinstance(row[key], str) or not row[key]:
                raise ValueError("PBS snapshot rows require a non-empty string key")
            identity = row[key]
            if identity in result:
                raise ValueError("duplicate PBS snapshot key")
            result[identity] = dict(row)
        return result

    before = index(legacy)
    after = index(current)
    changes: list[PbsSnapshotChange] = []
    for identity in sorted(before.keys() | after.keys()):
        old = before.get(identity)
        new = after.get(identity)
        if old is None:
            kind: ChangeKind = "addition"
        elif new is None:
            kind = "cessation"
        elif old != new:
            kind = "change"
        else:
            continue
        changes.append({
            "key": identity,
            "kind": kind,
            "before": old,
            "after": new,
            "interpretation": "literal_snapshot_difference",
        })
    return changes
