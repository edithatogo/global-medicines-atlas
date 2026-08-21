#!/usr/bin/env python3
"""Refresh a pinned reuse-discovery snapshot from offline indexes.

Indexes may be produced by ``gh``/Hugging Face CLI in an authenticated
session; this command only consumes their JSON output and never stores tokens.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from global_medicines_atlas.reuse_gate import (
    build_discovery_snapshot,
    write_discovery_snapshot,
)


def _load(path: str | None) -> dict[str, list[str]] | None:
    if path is None:
        return None
    with Path(path).open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError(
            "discovery index must map repository names to string paths"
        )
    result: dict[str, list[str]] = {}
    for key, raw_items in cast("dict[object, object]", value).items():
        if not isinstance(key, str) or not isinstance(raw_items, list):
            raise TypeError(
                "discovery index must map repository names to string paths"
            )
        items = cast("list[object]", raw_items)
        if not all(isinstance(item, str) for item in items):
            raise ValueError("discovery index paths must be strings")
        result[key] = cast("list[str]", items)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--repository-root", type=Path, default=Path())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-index", type=Path)
    parser.add_argument("--hugging-face-index", type=Path)
    parser.add_argument("--generated-at")
    parser.add_argument("--freshness-seconds", type=int, default=86_400)
    parser.add_argument("--tool-version", default="refresh_reuse_discovery/v1")
    args = parser.parse_args()
    generated_at = (
        datetime.fromisoformat(args.generated_at)
        if args.generated_at
        else datetime.now(UTC)
    )
    snapshot = build_discovery_snapshot(
        args.source_id,
        repository_root=args.repository_root,
        github_index=_load(str(args.github_index))
        if args.github_index
        else None,
        huggingface_index=_load(str(args.hugging_face_index))
        if args.hugging_face_index
        else None,
        generated_at=generated_at,
        freshness_seconds=args.freshness_seconds,
        tool_version=args.tool_version,
    )
    write_discovery_snapshot(snapshot, args.output)
    print(snapshot.snapshot_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
