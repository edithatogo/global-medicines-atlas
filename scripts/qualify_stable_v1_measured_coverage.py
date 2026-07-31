"""Generate or verify the offline stable-v1 measured coverage receipt."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import orjson

from global_medicines_atlas.stable_v1_measured_coverage import (
    build_measured_coverage_receipt,
    verify_measured_coverage_receipt,
    write_measured_coverage_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT / "quality/qualifications/stable-v1-measured-coverage.json"
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Qualify catalogue, fixture and live source coverage offline.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed receipt differs from regenerated evidence.",
    )
    return parser.parse_args()


def main() -> None:
    """Build deterministic evidence without network or publication actions."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    arguments = _arguments()
    output = arguments.output.resolve()
    receipt = build_measured_coverage_receipt(ROOT)
    verify_measured_coverage_receipt(receipt, ROOT)
    if arguments.check:
        if not output.is_file():
            raise SystemExit(f"measured coverage receipt is missing: {output}")
        committed = output.read_bytes()
        expected = (
            orjson.dumps(
                receipt.model_dump(mode="json"),
                option=orjson.OPT_SORT_KEYS,
            )
            + b"\n"
        )
        if committed != expected:
            raise SystemExit("measured coverage receipt is stale")
        return
    write_measured_coverage_receipt(receipt, output)
    print(receipt.receipt_sha256)


if __name__ == "__main__":
    main()
