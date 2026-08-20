"""Exercise the authorized EU Union Register Bronze corpus."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.union_register_acquisition import (
    exercise_union_register,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Run the internal-only Union Register acquisition."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--authorization",
        type=Path,
        default=ROOT
        / "quality/qualifications/union-register-live-authorization.json",
    )
    args = parser.parse_args()
    manifest = exercise_union_register(
        repository_root=ROOT,
        output_dir=args.output.resolve(),
        authorization_path=args.authorization.resolve(),
    )
    print(manifest.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
