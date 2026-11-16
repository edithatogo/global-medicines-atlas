"""Qualify two existing August MBS raw paths without adding data.

The source comparison role is limited to the documented July/August pair.
The v4 release label is not a qualified cross-era schema or field semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import scripts.qualify_m112_pbs_v4_admission as receipts
import scripts.qualify_mbs_july_frozen_v4 as shared
from scripts.qualify_m112_v4_july2016_admission import run_reader_canary

from global_medicines_atlas.federation_admission import admit_closed_contract
from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRECTORY = (
    "quality/qualifications/australian-mbs-august-frozen-v4-20261115"
)
OUTPUTS = {
    shared.lineage.AUGUST: f"{OUTPUT_DIRECTORY}/canonical-contract.json",
    shared.lineage.ALIAS: f"{OUTPUT_DIRECTORY}/alias-contract.json",
}


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def qualify(*, workflow_commit: str, root: Path = ROOT) -> dict[str, Any]:
    """Close exact role evidence and exercise both independently pinned paths."""
    require_hosted_main(workflow_commit)
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    run = os.environ.get("GITHUB_RUN_ID", "")
    _require(
        attempt.isdigit()
        and int(attempt) > 0
        and run.isdigit()
        and int(run) > 0,
        "hosted run identity missing",
    )
    objects: list[dict[str, Any]] = []
    for path, output in OUTPUTS.items():
        raw, trusted = shared.candidate(root, path=path)
        _require(
            (root / output).read_bytes() == raw, "August contract is stale"
        )
        closure = receipts.receipt_closure(raw, root=root)
        admission = admit_closed_contract(
            raw,
            closure,
            schema=(root / shared.SCHEMA).read_bytes(),
            trusted=trusted,
        )
        canary = run_reader_canary(
            raw,
            admission.model_dump(mode="json"),
            workflow_commit=workflow_commit,
            workflow_run_id=run,
            workflow_run_attempt=attempt,
            root=root,
        )
        objects.append({
            "path": path,
            "contract_sha256": hashlib.sha256(raw).hexdigest(),
            "admission": admission.model_dump(mode="json"),
            "receipt_closure": closure.model_dump(mode="json"),
            "consumer_canary": canary,
        })
    return {
        "schema_id": "global-medicines-atlas.mbs-august-frozen-v4-admission-reader",
        "schema_version": 1,
        "status": "passed",
        "objects": objects,
        "source_profile": {
            "comparison_cohort_scope": "later_member_of_documented_july_august_2026_pair",
            "schema_era_meaning": "source_release_revision",
            "field_semantics_accepted": False,
            "latest_schedule_claimed": False,
        },
        "boundaries": {
            "dataset_added_or_published": False,
            "participant_or_cohort_data_accessed": False,
            "source_values_interpreted": False,
            "independent_recovery_established": False,
            "federation_gate_closed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    parser.add_argument("--workflow-commit")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.verify:
        _require(
            args.workflow_commit and args.report,
            "hosted commit and report required",
        )
        result = qualify(workflow_commit=args.workflow_commit)
        args.report.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print("August exact v4 admissions and reader canaries passed")
        return 0
    for path, output in OUTPUTS.items():
        raw, _trusted = shared.candidate(path=path)
        destination = ROOT / output
        if args.check:
            _require(
                destination.is_file() and destination.read_bytes() == raw,
                "August contract is stale",
            )
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
    print("August v4 candidates validated; no admission or source read")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
