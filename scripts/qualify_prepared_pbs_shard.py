"""Write one bounded receipt for a prepared PBS phase/reference shard."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from global_medicines_atlas.pbs_prepared_qualification import (
    qualify_prepared_phase,
    qualify_prepared_reference,
)


def _write(path: Path, report: dict[str, Any]) -> None:
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    path.write_text(
        json.dumps(
            {
                "report": report,
                "report_sha256": hashlib.sha256(payload).hexdigest(),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--projection", choices=("native", "domain", "entities", "dates")
    )
    group.add_argument("--reference-shard", type=int)
    args = parser.parse_args(argv)
    identity = (
        {"projection_shard": args.projection}
        if args.projection is not None
        else {
            "projection_shard": "references",
            "reference_shard": args.reference_shard,
        }
    )
    try:
        report = (
            qualify_prepared_phase(
                args.input, args.exact_commit, args.projection
            )
            if args.projection is not None
            else qualify_prepared_reference(
                args.input, args.exact_commit, args.reference_shard
            )
        )
    except Exception:  # Never serialize source-bearing exception text.
        report = {
            "schema_version": 1,
            "status": "incomplete",
            **identity,
            "reason": "prepared-shard-did-not-complete",
            "publication_performed": False,
        }
    _write(args.output, report)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
