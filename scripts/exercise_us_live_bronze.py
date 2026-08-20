"""Exercise the approved internal U.S. live-source Bronze cohort."""

from __future__ import annotations

import argparse
from pathlib import Path

from global_medicines_atlas.us_live_bronze import (
    PRIVATE_MANIFEST_FILENAME,
    exercise_us_live_bronze_corpus,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTHORIZATION = (
    ROOT / "quality/qualifications/us-live-acquisition-authorization.json"
)
DEFAULT_OUTPUT = ROOT / "build/us-live-bronze-corpus"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--authorization", type=Path, default=DEFAULT_AUTHORIZATION
    )
    args = parser.parse_args(argv)
    manifest = exercise_us_live_bronze_corpus(
        repository_root=ROOT,
        output_dir=args.output_dir.resolve(),
        authorization_path=args.authorization.resolve(),
    )
    print(
        f"acquired {manifest.acquisition_succeeded_count}/"
        f"{manifest.source_count} authorized sources; accepted "
        f"{manifest.accepted_admission_count}; private archive manifest: "
        f"{args.output_dir.resolve() / PRIVATE_MANIFEST_FILENAME}"
    )
    return 0 if manifest.acquisition_failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
