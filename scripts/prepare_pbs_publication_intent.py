"""Stage the exact PBS candidate and intent for a protected hosted transaction.

This command performs only preparation and public metadata reads. It never
uploads or admits data. Its intent must be retained before any later append.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
from typing import Any

from scripts import pbs_publication_intent as intent
from scripts import prepare_pbs_reproduced_delivery as preparation

READBACK = (
    preparation.ROOT
    / "quality/qualifications/pbs-reproduced-public-tree-readback-20261029/readback.json"
)
TREE = READBACK.with_name("tree.json")


def prepare_intent(
    exact_commit: str, root: Path, public: Any
) -> dict[str, Any]:
    """Stage candidate, recheck public parent and persist the exact intent."""
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    root = root.resolve(strict=True)
    if not root.is_relative_to(runner_temp):
        raise ValueError("PBS transaction directory must be inside RUNNER_TEMP")
    intent_path = root / "intent.json"
    preparation_path = root / "preparation.json"
    if any(
        path.exists() or path.is_symlink()
        for path in (intent_path, preparation_path)
    ):
        raise ValueError("PBS intent already exists")
    candidate = preparation.prepare(exact_commit, root / "candidate")
    manifest_path = root / "candidate/first/manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("PBS prepared package manifest is unavailable")
    manifest_raw = manifest_path.read_bytes()
    if len(manifest_raw) > intent.MAX_ARTIFACT_BYTES:
        raise ValueError("PBS prepared package manifest exceeds its bound")
    preparation.validate_candidate_identity(json.loads(manifest_raw))
    preparation_receipt = {
        **candidate,
        "package_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "complete_source_reparse_and_restore": True,
        "parquet_bytes_identical": True,
        "independent_pipeline_builds": False,
    }
    with preparation_path.open("x", encoding="utf-8") as output:
        output.write(json.dumps(preparation_receipt, sort_keys=True) + "\n")
    plan = preparation.build_publication_plan(
        candidate, READBACK.read_bytes(), TREE.read_bytes()
    )
    preparation.verify_live_publication_parent(public, plan)
    document = intent.build_intent(plan)
    body = json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    if len(body.encode()) > intent.MAX_INTENT_BYTES:
        raise ValueError("PBS intent exceeds supported size")
    with intent_path.open("x", encoding="utf-8") as output:
        output.write(body)
    if intent_path.read_text(encoding="utf-8") != body:
        raise ValueError("PBS intent readback differs")
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    if os.environ.get("HF_TOKEN"):
        print(json.dumps({"status": "preparation_failed"}))
        return 1
    try:
        sdk: Any = importlib.import_module("huggingface_hub")
        document = prepare_intent(
            args.exact_commit, args.root, sdk.HfApi(token=False)
        )
    except Exception:  # Never emit source-bearing exception text.
        print(json.dumps({"status": "preparation_failed"}))
        return 1
    print(
        json.dumps({
            "status": "intent_prepared",
            "output_id": document["output_id"],
        })
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
