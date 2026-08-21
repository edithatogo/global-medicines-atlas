"""Build the private exact-manifest international publication candidate."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.international_public_archive import (
    build_international_publication_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        build_international_publication_candidate(
            args.staging, args.output
        ).model_dump_json(indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
