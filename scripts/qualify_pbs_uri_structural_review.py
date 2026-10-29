"""Write the bounded PBS URI structural match-behavior review receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from global_medicines_atlas.pbs_uri_structural_review import (
    StructuralReviewError,
    review_structural_match_behavior,
)


def write_receipt(root: Path, output: Path) -> None:
    report = review_structural_match_behavior(root)
    canonical = json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    envelope = {
        "report": report,
        "report_sha256": hashlib.sha256(canonical).hexdigest(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(
            envelope, stream, sort_keys=True, indent=2, ensure_ascii=False
        )
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        write_receipt(root, output)
    except (OSError, UnicodeError, ValueError, StructuralReviewError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
