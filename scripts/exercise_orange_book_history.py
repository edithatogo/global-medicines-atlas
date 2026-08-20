"""Exercise the authorized Orange Book historical Bronze corpus."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.orange_book_historical_acquisition import (
    exercise_orange_book_history,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Run the internal-only historical acquisition."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--authorization",
        type=Path,
        default=ROOT
        / "quality/qualifications/orange-book-historical-authorization.json",
    )
    args = parser.parse_args()
    manifest = exercise_orange_book_history(
        repository_root=ROOT,
        output_dir=args.output.resolve(),
        authorization_path=args.authorization.resolve(),
    )
    print(manifest.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
