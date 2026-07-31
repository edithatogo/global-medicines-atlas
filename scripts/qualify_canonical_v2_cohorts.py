"""Generate deterministic canonical schema-v2 adapter-cohort evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from global_medicines_atlas.canonical_v2_cohorts import (  # ruff: ignore[module-import-not-at-top-of-file]
    build_representative_adapter_cohorts,
    qualify_representative_cohorts,
    write_receipt,
)

DEFAULT_OUTPUT = (
    PROJECT_ROOT / "quality/qualifications/canonical-v2-cohorts.json"
)


def main() -> int:
    """Run the fixture cohort qualification and write its receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    receipt = qualify_representative_cohorts(
        build_representative_adapter_cohorts(PROJECT_ROOT)
    )
    write_receipt(receipt, args.output)
    print(args.output)
    print(receipt.receipt_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
