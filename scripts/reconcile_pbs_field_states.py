"""Write a value-free, exact-denominator PBS field-state reconciliation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from global_medicines_atlas.mbs_historical_csv_package import (
    canonical_package_json,
)
from global_medicines_atlas.pbs_field_reconciliation import (
    reconcile_pbs_field_states,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "quality/qualifications/"
            "pbs-native-silver-field-reconciliation-20261024-r6.json"
        ),
    )
    args = parser.parse_args()
    destination = args.root / args.output
    if destination.exists():
        parser.error("existing PBS field reconciliation must be preserved")
    report = reconcile_pbs_field_states(args.root)
    digest = hashlib.sha256(canonical_package_json(report)).hexdigest()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {"report": report, "report_sha256": digest},
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
