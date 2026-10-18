"""Validate the M-106 annual workbook metadata-only HEAD receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = (
    ROOT / "quality/qualifications/"
    "australian-mbs-m106-annual-workbook-head-readback-20261019.json"
)
SCHEMA = (
    ROOT / "schemas/australian-mbs-m106-annual-workbook-head-readback-v1.json"
)


def validate_receipt(receipt: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate schema and bind both HEAD URLs to the exact linked workbook."""
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
        receipt
    )
    page = receipt["official_page"]
    head = receipt["attachment_head"]
    attachment_url = page["attachment_url"]
    if head["requested_url"] != attachment_url:
        raise ValueError("HEAD request URL does not match the page attachment")
    if head["final_url"] != attachment_url:
        raise ValueError("HEAD final URL does not match the page attachment")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    arguments = parser.parse_args()
    receipt = json.loads(arguments.receipt.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validate_receipt(receipt, schema)
    print(f"validated M-106 metadata-only readback: {arguments.receipt}")


if __name__ == "__main__":
    main()
