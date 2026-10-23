"""Write a value-free interpretation of the retained PBS reference screen."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from global_medicines_atlas.pbs_reference_meaning import (
    review_reference_meanings,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "quality/qualifications/"
            "pbs-native-reference-meaning-review-20261023.json"
        ),
    )
    args = parser.parse_args()
    report = review_reference_meanings(args.root)
    canonical = json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    envelope = {
        "report": report,
        "report_sha256": hashlib.sha256(canonical).hexdigest(),
    }
    destination = args.root / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(envelope, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
