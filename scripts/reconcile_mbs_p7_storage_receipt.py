#!/usr/bin/env python3
"""Reconstruct the archived P7 metadata receipt without source bytes."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.mbs_p7_receipt_reconciliation import (
    write_reconciliation,
)

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    """Validate and write the P7 storage receipt reconciliation."""

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = write_reconciliation(args.root)
    print(
        f"{result.source_id}: exact archived receipt matched; "
        "direct Bronze qualification remains false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
