"""Exercise current and historical FDA drug-shortage Bronze surfaces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.shortages_acquisition import exercise_fda_shortages

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--authorization",
        type=Path,
        default=ROOT
        / "quality/qualifications/fda-shortages-live-authorization.json",
    )
    parser.add_argument("--capture-timestamp", action="append", default=[])
    args = parser.parse_args()
    manifest = exercise_fda_shortages(
        repository_root=ROOT,
        output_dir=args.output,
        authorization_path=args.authorization,
        capture_timestamps=(
            frozenset(args.capture_timestamp)
            if args.capture_timestamp
            else None
        ),
    )
    print(json.dumps(manifest.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
