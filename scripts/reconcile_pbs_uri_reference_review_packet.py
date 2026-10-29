"""Reconcile the pinned PBS review packet with an exact v2 URI receipt."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.pbs_uri_review_packet_reconciler import (
    PACKET_FILENAME,
    ReconciliationError,
    reconcile_uri_review_packet,
    write_new_envelope,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--uri-receipt", type=Path, required=True)
    parser.add_argument("--expected-uri-receipt-sha256", required=True)
    parser.add_argument("--expected-run-id", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    packet = root / "quality/qualifications" / PACKET_FILENAME
    receipt = (
        args.uri_receipt
        if args.uri_receipt.is_absolute()
        else root / args.uri_receipt
    )
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        envelope = reconcile_uri_review_packet(
            packet,
            receipt.resolve(),
            expected_run_id=args.expected_run_id,
            expected_commit=args.expected_commit,
            expected_uri_receipt_sha256=args.expected_uri_receipt_sha256,
        )
        write_new_envelope(envelope, output.resolve())
    except ReconciliationError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
