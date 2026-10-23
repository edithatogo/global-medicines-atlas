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
        "--screen-receipt",
        type=Path,
        help="exact hosted PBS reference-screen receipt to reconcile",
    )
    parser.add_argument(
        "--require-per-kind",
        action="store_true",
        help="fail unless the exact receipt includes source counts by reference kind",
    )
    parser.add_argument(
        "--exact-commit",
        help="expected exact-main commit for a per-kind hosted receipt",
    )
    parser.add_argument(
        "--run-id",
        help="expected GitHub Actions run ID for a per-kind hosted receipt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "quality/qualifications/"
            "pbs-native-reference-meaning-review-20261023.json"
        ),
    )
    args = parser.parse_args()
    if args.require_per_kind and (
        args.exact_commit is None or args.run_id is None
    ):
        parser.error(
            "--require-per-kind requires both --exact-commit and --run-id"
        )
    report = review_reference_meanings(
        args.root,
        args.screen_receipt
        or "quality/qualifications/pbs-native-reference-screen-20261022-39730665004.json",
        require_per_kind=args.require_per_kind,
        expected_exact_commit=args.exact_commit,
        expected_run_id=args.run_id,
    )
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
