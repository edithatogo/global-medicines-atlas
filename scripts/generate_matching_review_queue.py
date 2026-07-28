"""Generate deterministic matching review artifacts from JSONL entries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.matching_columnar import write_matching_outputs
from global_medicines_atlas.review_queue import ReviewQueueEntry


def generate(input_path: Path, output_dir: Path) -> None:
    entries = tuple(
        ReviewQueueEntry.model_validate_json(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line
    )
    manifest = write_matching_outputs(entries, output_dir)
    print(json.dumps(manifest.model_dump(mode="json"), sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    generate(arguments.input, arguments.output)


if __name__ == "__main__":
    main()
