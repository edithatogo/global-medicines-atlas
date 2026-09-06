"""Deterministic, source-faithful comparison of two PBS snapshots.

This module deliberately compares literal projected rows only.  It does not
infer that a missing item was ceased, nor does it qualify either snapshot as
current.  Callers must provide the snapshot labels (for example ``legacy``
and ``current``) and retain the returned uncertainty for downstream use.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any, Literal, TypedDict

ChangeKind = Literal[
    "addition",
    "cessation",
    "change",
    "present_only_legacy",
    "present_only_current",
]


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
    legacy_complete: bool = True,
    current_complete: bool = True,
    max_rows: int = 100_000,
) -> list[PbsSnapshotChange]:
    """Return stable literal additions, cessations, and changes.

    A cessation means a key present in ``legacy`` is absent from ``current``;
    it is *not* a regulatory or commercial cessation claim. Duplicate keys,
    missing keys, and unhashable key values fail closed. Values are copied into
    ordinary dictionaries so the result cannot alias caller-owned mappings.
    """

    if max_rows < 1:
        raise ValueError("max_rows must be positive")

    def index(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            if len(result) >= max_rows:
                raise ValueError("PBS snapshot exceeds max_rows bound")
            if key not in row or not isinstance(row[key], str) or not row[key]:
                raise ValueError(
                    "PBS snapshot rows require a non-empty string key"
                )
            identity = row[key]
            if identity in result:
                raise ValueError("duplicate PBS snapshot key")
            result[identity] = deepcopy(dict(row))
        return result

    before = index(legacy)
    after = index(current)
    changes: list[PbsSnapshotChange] = []
    for identity in sorted(before.keys() | after.keys()):
        old = before.get(identity)
        new = after.get(identity)
        if old is None:
            kind: ChangeKind = (
                "addition" if current_complete else "present_only_current"
            )
        elif new is None:
            kind = "cessation" if legacy_complete else "present_only_legacy"
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
