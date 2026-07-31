"""Run the governed local-artifact recovery rehearsal."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.recovery_rehearsal import (
    rehearse_governed_recovery,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/recovery/rehearsal-receipt.json"),
    )
    arguments = parser.parse_args()
    receipt = rehearse_governed_recovery(arguments.output)
    if not (
        receipt.backup_verified
        and receipt.restore_verified
        and receipt.rollback_verified
        and receipt.failed_restore_quarantined
    ):
        return 1
    print(arguments.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
