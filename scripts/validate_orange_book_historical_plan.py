"""Validate the fail-closed Orange Book historical acquisition plan."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.orange_book_history import (
    OrangeBookHistoricalPlan,
    build_metadata_probe_requests,
    build_payload_requests,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "quality/qualifications/orange-book-historical-plan.json"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    return parser.parse_args()


def main() -> int:
    """Validate planning metadata without retrieving source payloads."""
    args = parse_args()
    plan = OrangeBookHistoricalPlan.model_validate_json(args.plan.read_bytes())
    probes = build_metadata_probe_requests(plan)
    try:
        build_payload_requests(plan)
    except PermissionError:
        payload_state = "blocked_pending_maintainer_authorization"
    else:
        payload_state = "authorized"
    print(
        f"source={plan.source_id} surfaces={len(plan.surfaces)} "
        f"metadata_probes={len(probes)} payload_state={payload_state} "
        f"historical_inventory_complete={plan.historical_inventory_complete}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
