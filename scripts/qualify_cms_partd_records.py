"""Build an exact-inventory CMS Part D source-record qualification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.cms_partd_records import (
    qualify_cms_partd_projections,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-manifest", type=Path, required=True)
    parser.add_argument("--shards-dir", type=Path, required=True)
    parser.add_argument("--qualified-at", required=True)
    parser.add_argument("--raw-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.raw_manifest.read_text(encoding="utf-8"))
    shards = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(args.shards_dir.glob("**/source-records.json"))
    ]
    result = qualify_cms_partd_projections(
        raw,
        shards,
        qualified_at=args.qualified_at,
        raw_revision=args.raw_revision,
    )
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
