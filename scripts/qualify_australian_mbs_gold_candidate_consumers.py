"""Qualify all current consumers of the pinned MBS Gold edge candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

from qualify_australian_mbs_gold_real_silver import (
    ADMISSION_PATH,
    ROOT,
    SEMANTIC_PATH,
    _read_json,  # ruff: ignore[import-private-name] -- reuse qualifier  # pyright: ignore[reportPrivateUsage]
)
from qualify_australian_mbs_gold_real_silver import (
    OUTPUT_PATH as QUALIFICATION_PATH,
)

from global_medicines_atlas.atlas_browser_qualification import (
    qualify_candidate_atlas_browser,
)
from global_medicines_atlas.mbs_gold_consumer_qualification import (
    qualify_consumers,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edge-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output.expanduser()
    qualification: dict[str, Any] = _read_json(QUALIFICATION_PATH)
    receipt = qualify_consumers(
        args.edge_file.expanduser(),
        qualification,
        expected_bindings={
            "input_admission_sha256": _sha256(ROOT / ADMISSION_PATH),
            "input_semantic_manifest_sha256": _sha256(ROOT / SEMANTIC_PATH),
            "graph_sha256": cast("str", qualification["graph"]["graph_sha256"]),
        },
        browser_qualifier=qualify_candidate_atlas_browser,
    )
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
        stream.write("\n")
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
