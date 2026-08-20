"""Land, admit, reconstruct, and archive the governed Bronze corpus."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from global_medicines_atlas.bronze_corpus_archive import (
    MANIFEST_FILENAME,
    build_bronze_corpus_archive,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "build" / "bronze-corpus-archive"
DEFAULT_EXERCISED_AT = "2026-08-20T06:00:00+00:00"


def main(argv: list[str] | None = None) -> int:
    """Execute the corpus exercise and report its durable manifest."""

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--exercised-at", default=DEFAULT_EXERCISED_AT)
    args = parser.parse_args(argv)
    exercised_at = datetime.fromisoformat(args.exercised_at)
    if exercised_at.tzinfo is None:
        parser.error("--exercised-at must include a timezone")
    manifest = build_bronze_corpus_archive(
        ROOT,
        args.output_dir.resolve(),
        exercised_at=exercised_at,
    )
    print(
        f"exercised {manifest.acquisition_count} acquisitions across "
        f"{manifest.exercised_source_count} sources; archive manifest: "
        f"{args.output_dir.resolve() / MANIFEST_FILENAME}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
