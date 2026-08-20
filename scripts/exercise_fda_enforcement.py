"""Exercise current FDA enforcement and recall-notice Bronze surfaces."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.enforcement_acquisition import (
    exercise_fda_enforcement,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    """Run the internal-only current enforcement acquisition."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--authorization",
        type=Path,
        default=ROOT
        / "quality/qualifications/fda-enforcement-live-authorization.json",
    )
    args = parser.parse_args()
    manifest = exercise_fda_enforcement(
        repository_root=ROOT,
        output_dir=args.output.resolve(),
        authorization_path=args.authorization.resolve(),
    )
    print(manifest.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
