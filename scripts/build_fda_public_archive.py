"""Build the exact-manifest FDA publication candidate."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.fda_public_archive import (
    build_fda_publication_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_fda_publication_candidate(args.corpus, args.output)
    print(manifest.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
