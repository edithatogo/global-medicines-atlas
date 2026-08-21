"""Offline CLI for bounded manual-acquisition sessions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from global_medicines_atlas.manual_acquisition import (
    ManualAcquisitionReceipt,
    generate_manual_recipes,
    validate_receipt_files,
)
from global_medicines_atlas.source_catalog import load_catalog
from global_medicines_atlas.source_landing_factory import (
    LandingOverrides,
    build_source_landing_queue,
)


def recipes() -> tuple:
    return generate_manual_recipes(build_source_landing_queue(load_catalog(), LandingOverrides.load()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    init = sub.add_parser("init")
    init.add_argument("source_id")
    init.add_argument("--output", type=Path, required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--recipe", type=Path, required=True)
    validate.add_argument("--receipt", type=Path, required=True)
    validate.add_argument("--files", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    by_id = {item.source_id: item for item in recipes()}
    if args.command == "list":
        print(json.dumps([item.model_dump(mode="json") for item in by_id.values()], sort_keys=True, indent=2))
    elif args.command == "init":
        if args.source_id not in by_id:
            parser.error(f"unknown or non-manual source: {args.source_id}")
        args.output.write_text(by_id[args.source_id].model_dump_json(indent=2), encoding="utf-8")
    else:
        recipe = next(item for item in by_id.values() if item.recipe_id == json.loads(args.recipe.read_text())["recipe_id"])
        receipt = ManualAcquisitionReceipt.model_validate_json(args.receipt.read_bytes())
        completed = validate_receipt_files(recipe, receipt, args.files)
        args.output.write_text(completed.model_dump_json(indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
