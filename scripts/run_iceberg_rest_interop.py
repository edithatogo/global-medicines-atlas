"""Run the disposable Iceberg REST interoperability experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.iceberg_interop import run_rest_catalog_interop


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_rest_catalog_interop(
        rest_uri=args.uri,
        fixture_path=args.fixture,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
