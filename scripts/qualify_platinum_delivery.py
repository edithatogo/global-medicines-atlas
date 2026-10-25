"""Run bounded consumer qualification without emitting source values."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter

from global_medicines_atlas.platinum_delivery_qualification import (
    DeliveryRequest,
    run_product_delivery_qualification,
)

MAX_REQUEST_BYTES = 65536
MAX_REQUESTS = 32


def _requests(path: Path) -> tuple[DeliveryRequest, ...]:
    with path.open("rb") as stream:
        raw = stream.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("request input exceeds bound")
    requests = TypeAdapter(tuple[DeliveryRequest, ...]).validate_json(raw)
    if not 1 <= len(requests) <= MAX_REQUESTS:
        raise ValueError("request count exceeds bound")
    return requests


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trust-file", type=Path, required=True)
    parser.add_argument("--metadata-root", type=Path, required=True)
    parser.add_argument("--schema-file", type=Path, required=True)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    try:
        requests = _requests(args.requests)
        report = run_product_delivery_qualification(
            args.trust_file,
            args.metadata_root,
            args.schema_file,
            requests,
            offline=args.offline,
        )
    except Exception:
        # Validation and consumer exceptions may embed native values or paths.
        print("Delivery qualification failed; no passing evidence written.")
        return 1
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
