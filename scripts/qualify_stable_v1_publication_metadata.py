"""Generate or verify the stable-v1 publication-metadata receipt offline."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from global_medicines_atlas.publication_metadata_qualification import (  # ruff: ignore[module-import-not-at-top-of-file]
    canonical_receipt_bytes,
    qualify_publication_metadata,
    verify_publication_metadata_receipt,
)

DEFAULT_RECEIPT = (
    ROOT / "quality" / "qualifications" / "stable-v1-publication-metadata.json"
)
SCHEMA_PATH = "schemas/stable-v1-publication-metadata-qualification-v1.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Qualify release-candidate dataset metadata without network, "
            "credentials, signing, releases, or publication."
        )
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed receipt instead of writing it.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve(strict=True)
    receipt_path = args.receipt
    if not receipt_path.is_absolute():
        receipt_path = root / receipt_path
    if args.check:
        receipt = verify_publication_metadata_receipt(root, receipt_path)
    else:
        receipt = qualify_publication_metadata(root)
        payload = canonical_receipt_bytes(receipt)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_bytes(payload)

    schema = Draft202012Validator(
        json.loads((root / SCHEMA_PATH).read_text(encoding="utf-8"))
    )
    schema.check_schema(schema.schema)
    schema.validate(  # pyright: ignore[reportUnknownMemberType]
        receipt.model_dump(mode="json")
    )
    print(receipt.receipt_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
