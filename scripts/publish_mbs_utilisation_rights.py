"""Append the exact approved MBS rights supplement from protected Actions."""

# Fixed gh argument arrays, no shell or caller-supplied paths.
# ruff: file-ignore[subprocess-without-shell-equals-true, start-process-with-partial-path]

from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- fixed gh argv
import tempfile
from pathlib import Path
from typing import Any

from publish_source_metadata import HubTransport, persist_receipt

from global_medicines_atlas.federation_metadata_hosted import (
    REPOSITORY,
    require_hosted_main,
)
from global_medicines_atlas.mbs_utilisation_rights_append import (
    DECISION_PATH,
    JOIN_PATH,
    PAYLOAD_PATH,
    validate_rights_append,
)
from global_medicines_atlas.mbs_utilisation_rights_hosted import (
    execute_rights_append,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = "quality/qualifications/australian-mbs-utilisation-rights-append-contract-20261004.json"


def current_main() -> str:
    """Independently read the current default-branch identity."""
    return subprocess.check_output(
        ["gh", "api", f"repos/{REPOSITORY}/commits/main", "--jq", ".sha"],
        text=True,
        timeout=30,
    ).strip()


def finalize(result: dict[str, Any], cache: Path, receipts: Path) -> None:
    """Remove the hosted cache only after a durable verification receipt."""
    if result.get("status") != "anonymously_verified" or not result.get(
        "receipt_url"
    ):
        raise ValueError("cleanup requires durable anonymous verification")
    shutil.rmtree(cache)
    cleanup = {
        **result,
        "status": "cleanup_completed",
        "temporary_cache_removed": True,
    }
    cleanup_url = persist_receipt(cleanup, receipts)
    (receipts / "result.json").write_text(
        json.dumps(
            {
                **result,
                "temporary_cache_removed": True,
                "cleanup_receipt_url": cleanup_url,
            },
            indent=2,
        )
        + "\n"
    )


def main() -> None:
    """Load fixed reviewed metadata and run the guarded single-object append."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    args = parser.parse_args()
    require_hosted_main(args.exact_commit)
    contract = json.loads((ROOT / CONTRACT_PATH).read_bytes())
    payload = (ROOT / PAYLOAD_PATH).read_bytes()
    decision = (ROOT / DECISION_PATH).read_bytes()
    joins = (ROOT / JOIN_PATH).read_bytes()
    validate_rights_append(contract, payload, decision, joins)
    if current_main() != args.exact_commit:
        raise ValueError("reviewed main has advanced")
    receipts = ROOT / "build/mbs-utilisation-rights-receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    cache = Path(tempfile.mkdtemp(prefix="gma-mbs-rights-"))
    result = execute_rights_append(
        contract,
        payload,
        decision,
        joins,
        exact_commit=args.exact_commit,
        current_main=current_main,
        hub=HubTransport(cache),
        persist=lambda receipt: persist_receipt(receipt, receipts),
    )
    finalize(result, cache, receipts)


if __name__ == "__main__":
    main()
