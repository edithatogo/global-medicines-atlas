"""Run the exact-public-Parquet Iceberg REST registration experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.iceberg_public_parquet import (
    run_public_parquet_registration,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", required=True)
    parser.add_argument("--temporary-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_public_parquet_registration(
        rest_uri=args.uri,
        temporary_directory=args.temporary_directory,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
