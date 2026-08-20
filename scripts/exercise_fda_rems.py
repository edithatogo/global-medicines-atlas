"""Exercise the complete bounded public FDA REMS Bronze surface family."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.rems_acquisition import exercise_fda_rems

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--authorization",
        type=Path,
        default=ROOT
        / "quality/qualifications/fda-rems-live-authorization.json",
    )
    parser.add_argument("--document-url-file", type=Path)
    args = parser.parse_args()
    document_urls = None
    if args.document_url_file is not None:
        document_urls = frozenset(
            line.strip()
            for line in args.document_url_file.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        )
    manifest = exercise_fda_rems(
        repository_root=ROOT,
        output_dir=args.output,
        authorization_path=args.authorization,
        document_urls=document_urls,
    )
    print(json.dumps(manifest.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
