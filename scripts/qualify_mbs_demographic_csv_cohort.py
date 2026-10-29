"""Qualify one frozen quarterly demographic CSV without pooling its measures."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.mbs_demographic_csv_cohort import (
    CANDIDATE_COUNT,
    load_csv_candidates,
)

if __package__:
    from scripts import qualify_mbs_q1_native_silver as qualifier
else:
    import qualify_mbs_q1_native_silver as qualifier

ROOT = Path(__file__).resolve().parents[1]
COMMIT_LENGTH = 40


def qualify(quarter: int, exact_commit: str) -> dict[str, Any]:
    """Validate runner identity before reading only the selected pinned object."""
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
    if type(quarter) is not int or not 1 <= quarter <= CANDIDATE_COUNT:
        raise ValueError("Quarter selection is outside the frozen CSV cohort")
    candidate = load_csv_candidates(ROOT)[quarter - 1]
    source = candidate.source
    if (
        source.dataset != qualifier.source_reader.DATASET
        or source.source_revision != qualifier.source_reader.REVISION
    ):
        raise ValueError("CSV candidate transport identity differs")
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
            client,
            {
                "path": source.source_path,
                "sha256": source.source_sha256,
                "bytes": candidate.byte_count,
            },
        )
    with TemporaryDirectory(prefix="mbs-quarterly-csv-") as temporary:
        result = qualifier.qualify_object(
            payload,
            source,
            Path(temporary),
            expected_rows=candidate.expected_rows,
        )
    del payload
    return {
        "schema_id": "global-medicines-atlas.mbs-demographic-csv-candidate-qualification",
        "schema_version": 1,
        "workflow_commit": exact_commit,
        "frozen_candidate_count": CANDIDATE_COUNT,
        "selected_quarter": quarter,
        "prior_structural_receipt_sha256": candidate.prior_structural_receipt_sha256,
        "prior_header_receipt_sha256": candidate.prior_header_receipt_sha256,
        "dataset": source.dataset,
        "source_revision": source.source_revision,
        "source_path": source.source_path,
        "result": result,
        "temporary_derivatives_removed": True,
        "boundaries": {
            "candidate_only": True,
            "new_sources": 0,
            "new_admissions": 0,
            "new_federated_canaries": 0,
            "publications": 0,
            "benefit_equivalence_established": False,
            "rights_conclusion_changed": False,
        },
    }


def main() -> None:
    """Emit an aggregate receipt, withholding source-bearing error details."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quarter",
        required=True,
        type=int,
        choices=range(1, CANDIDATE_COUNT + 1),
    )
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = qualify(args.quarter, args.exact_commit)
    except Exception:
        raise SystemExit(
            "Demographic CSV qualification failed; source details withheld"
        ) from None
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
