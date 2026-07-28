"""Generate a governed LanceDB matching index from supplied embeddings."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

import orjson

from global_medicines_atlas.matching_indexes import (
    MatchingIndexLineage,
    MatchingIndexRow,
    generate_lancedb_index,
)


def _rows(path: Path) -> tuple[MatchingIndexRow, ...]:
    return tuple(
        MatchingIndexRow.model_validate(orjson.loads(line))
        for line in path.read_bytes().splitlines()
        if line.strip()
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rows", type=Path)
    parser.add_argument("lineage", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--table", default="medicine_embeddings")
    args = parser.parse_args()
    lineage_payload = orjson.loads(args.lineage.read_bytes())
    lineage = MatchingIndexLineage.model_validate(
        cast("dict[str, object]", lineage_payload)
    )
    manifest = generate_lancedb_index(
        _rows(args.rows),
        lineage,
        args.output,
        table_name=args.table,
    )
    print(manifest.index_digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
