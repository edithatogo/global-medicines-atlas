"""Run the aggregate stable-v1 representative rehearsal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.stable_v1_rehearsal import (
    representative_identities,
    run_stable_v1_rehearsal,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture-child", action="store_true", help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/stable-v1/rehearsals/aggregate.json"),
    )
    arguments = parser.parse_args()
    if arguments.fixture_child:
        print(json.dumps(representative_identities(), sort_keys=True))
        return 0
    run_stable_v1_rehearsal(arguments.output)
    print(arguments.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
