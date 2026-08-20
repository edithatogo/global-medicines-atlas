"""Generate the additive batch-attestation experiment receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from global_medicines_atlas.batch_attestation import (
    AttestationLeaf,
    build_experiment_receipt,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--leaves", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.leaves.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise TypeError("attestation leaves must be an array")
    leaves = tuple(
        AttestationLeaf.model_validate(item)
        for item in cast("list[object]", raw)
    )
    receipt = build_experiment_receipt(leaves)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
