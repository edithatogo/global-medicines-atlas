"""Read exact existing public MBS objects in Actions and emit value-free roles."""

from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path

from global_medicines_atlas.federation_reader import FederatedReader
from global_medicines_atlas.mbs_silver_delivery_qualification import (
    qualify_delivery,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--producer-commit", required=True)
    args = parser.parse_args()
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or not os.environ.get("GITHUB_RUN_ID", "").isdigit()
        or os.environ.get("GITHUB_SHA") != args.producer_commit
    ):
        raise ValueError(
            "live source qualification requires exact-commit GitHub Actions"
        )
    # The existing downloader checks anonymous destinations, DNS and redirects.
    reader = FederatedReader(
        schema=(
            args.repository_root
            / "contracts/medallion/v4/federation.schema.json"
        ).read_bytes(),
        admission_records=(),
        timeout_seconds=120,
    )

    def fetch(url: str, limit: int) -> bytes:
        with io.BytesIO() as stream:
            reader._download(url, stream, limit)  # pyright: ignore[reportPrivateUsage] - reuse guarded transport
            return stream.getvalue()

    try:
        reports = qualify_delivery(
            args.repository_root, fetch, producer_commit=args.producer_commit
        )
    finally:
        reader.close()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, report in reports.items():
        (args.output_dir / f"{name}.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0 if reports["qualification"]["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
