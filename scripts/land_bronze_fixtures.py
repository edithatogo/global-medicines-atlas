"""Land all governed current-scope fixtures into an immutable Bronze root."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from global_medicines_atlas.bronze_fixture_landing import (
    land_governed_fixtures,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "build" / "bronze-fixtures"
DEFAULT_RETRIEVED_AT = "2026-08-20T06:00:00+00:00"


def main(argv: list[str] | None = None) -> int:
    """Run deterministic fixture landing and write its manifest."""

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--retrieved-at",
        default=DEFAULT_RETRIEVED_AT,
        help="Aware ISO-8601 retrieval clock for deterministic replay",
    )
    args = parser.parse_args(argv)
    retrieved_at = datetime.fromisoformat(args.retrieved_at)
    if retrieved_at.tzinfo is None:
        parser.error("--retrieved-at must include a timezone")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = land_governed_fixtures(
        ROOT,
        bronze_root=output,
        retrieved_at=retrieved_at,
    )
    manifest_path = output / "fixture-landing-manifest.json"
    manifest_path.write_bytes(manifest.canonical_json() + b"\n")
    print(
        f"landed {len(manifest.landings)} fixture acquisitions for "
        f"{len(manifest.source_ids)} sources at {manifest_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
