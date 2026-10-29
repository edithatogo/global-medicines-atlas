"""Prepare a bounded review packet from an exact hosted PBS screen receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from global_medicines_atlas.pbs_reference_meaning import (
    review_reference_meanings,
)
from global_medicines_atlas.pbs_reference_review_packet import (
    MAX_PACKET_CASES,
    prepare_reference_review_packet,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--screen-receipt", type=Path, required=True)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-cases", type=int, default=MAX_PACKET_CASES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    destination = (
        args.output if args.output.is_absolute() else root / args.output
    )
    destination = destination.resolve()
    if destination.exists():
        parser.error("existing review packet must be preserved")
    meaning = review_reference_meanings(
        root,
        args.screen_receipt,
        require_per_kind=True,
        expected_exact_commit=args.exact_commit,
        expected_run_id=args.run_id,
        require_context=True,
    )
    packet = prepare_reference_review_packet(meaning, max_cases=args.max_cases)
    canonical = json.dumps(
        packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    envelope = {
        "report": packet,
        "report_sha256": hashlib.sha256(canonical).hexdigest(),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("x", encoding="utf-8") as output:
            output.write(json.dumps(envelope, sort_keys=True, indent=2) + "\n")
    except FileExistsError:
        parser.error("existing review packet must be preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
