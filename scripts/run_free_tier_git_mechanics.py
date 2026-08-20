"""Run the disposable Git mechanics experiment and write its receipt."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from global_medicines_atlas.free_tier_git_mechanics import run_git_mechanics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="gma-git-mechanics-") as temporary:
        receipt = run_git_mechanics(Path(temporary))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
