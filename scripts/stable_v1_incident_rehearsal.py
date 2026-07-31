"""Write a deterministic offline stable-v1 incident rehearsal receipt."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.stable_v1_incident_rehearsal import (
    default_incident_rehearsal,
    write_incident_receipt,
)


def main() -> int:
    """Run the offline rehearsal without performing external actions."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="receipt JSON path")
    arguments = parser.parse_args()
    receipt = default_incident_rehearsal()
    write_incident_receipt(arguments.output, receipt)
    print(receipt.receipt_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
