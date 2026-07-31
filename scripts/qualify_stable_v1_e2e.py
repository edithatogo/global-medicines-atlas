"""Generate the deterministic stable-v1 end-to-end qualification receipt."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.stable_v1_e2e_qualification import (
    write_stable_v1_e2e_receipt,
)


def main() -> None:
    """Run qualification and report the content-bound receipt identity."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/stable-v1/e2e-qualification.json"),
    )
    arguments = parser.parse_args()
    receipt = write_stable_v1_e2e_receipt(arguments.output)
    print(f"receipt={arguments.output}")
    print(f"sha256={receipt.receipt_sha256}")


if __name__ == "__main__":
    main()
