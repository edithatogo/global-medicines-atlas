"""Publish the exact reviewed historical lifecycle bundle from Actions."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from publish_mbs_utilisation_rights import current_main, finalize
from publish_source_metadata import HubTransport, persist_receipt

from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main,
)
from global_medicines_atlas.mbs_utilisation_lifecycle_append import (
    BASELINE_PATH,
    CONTRACT_PATH,
    PAYLOAD_PATH,
    execute_lifecycle_append,
    validate_lifecycle_append,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Fail closed before transport construction and clean only after proof."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    args = parser.parse_args()
    require_hosted_main(args.exact_commit)
    contract = json.loads((ROOT / CONTRACT_PATH).read_bytes())
    payload = (ROOT / PAYLOAD_PATH).read_bytes()
    baseline = (ROOT / BASELINE_PATH).read_bytes()
    validate_lifecycle_append(contract, payload, baseline)
    if current_main() != args.exact_commit:
        raise ValueError("reviewed main has advanced")
    receipts = ROOT / "build/mbs-utilisation-lifecycle-receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    cache = Path(tempfile.mkdtemp(prefix="gma-mbs-lifecycle-"))
    result = execute_lifecycle_append(
        contract,
        payload,
        baseline,
        exact_commit=args.exact_commit,
        current_main=current_main,
        hub=HubTransport(cache),
        persist=lambda receipt: persist_receipt(receipt, receipts),
    )
    finalize(result, cache, receipts)


if __name__ == "__main__":
    main()
