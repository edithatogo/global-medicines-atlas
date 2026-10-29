"""Read the exact frozen group workbook layout on protected main Actions."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.mbs_group_workbook_layout import (
    inspect_layout,
    load_reference,
)

if __package__:
    from scripts import qualify_mbs_q1_native_silver as qualifier
else:
    import qualify_mbs_q1_native_silver as qualifier

ROOT = Path(__file__).resolve().parents[1]
COMMIT_LENGTH = 40


def qualify(exact_commit: str) -> dict[str, Any]:
    """Enforce runner identity before any source transport."""
    if not (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_REPOSITORY")
        == "edithatogo/global-medicines-atlas"
        and os.environ.get("GITHUB_REF") == "refs/heads/main"
        and len(exact_commit) == COMMIT_LENGTH
        and all(char in "0123456789abcdef" for char in exact_commit)
        and os.environ.get("GITHUB_SHA") == exact_commit
    ):
        raise ValueError("Qualification requires exact main Actions commit")
    reference = load_reference(ROOT)
    if (
        reference["dataset"] != qualifier.source_reader.DATASET
        or reference["revision"] != qualifier.source_reader.REVISION
    ):
        raise ValueError("group workbook transport identity differs")
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=120,
        max_bytes=25_000_000,
        max_attempts=1,
        max_redirects=3,
    )
    with httpx.Client(
        timeout=120,
        trust_env=False,
        follow_redirects=True,
        max_redirects=3,
        transport=BoundIPAddressTransport(policy=policy),
    ) as client:
        payload = qualifier.source_reader.fetch_exact_source_bytes(
            client, reference
        )
    result = inspect_layout(payload, reference)
    del payload
    return {
        "schema_id": "global-medicines-atlas.mbs-group-workbook-layout",
        "schema_version": 1,
        "workflow_commit": exact_commit,
        "source": reference,
        "result": result,
        "new_sources": 0,
        "new_admissions": 0,
        "publications": 0,
        "rights_conclusion_changed": False,
    }


def main() -> None:
    """Emit bounded native header candidates; withhold source-bearing failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = qualify(args.exact_commit)
    except Exception:
        raise SystemExit(
            "Group workbook layout failed; source details withheld"
        ) from None
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
