"""Hosted MBS replay evidence binds exact plans and preserves privacy."""

from __future__ import annotations

import copy
from typing import Any

import pytest
import scripts.qualify_mbs_frozen_raw_replay as candidate
import scripts.reconcile_mbs_frozen_v3_replays as reconciliation
from scripts.qualify_m112_existing_reimbursement_batch import (
    read_bound_metadata,
)


@pytest.fixture(scope="module")
def evidence() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    _, _, plans = candidate.build()
    receipts = {
        path: read_bound_metadata(
            reconciliation.ROOT,
            reconciliation._receipt_path(run["run"]),  # pyright: ignore[reportPrivateUsage]
            run["receipt_sha256"],
        )
        for path, run in reconciliation.RUNS.items()
    }
    return plans, receipts


def test_replay_manifest_binds_three_receipts_without_admission() -> None:
    manifest = reconciliation.build()
    assert manifest["summary"] == {
        "exact_replays_passed": 3,
        "new_v4_admissions": 0,
        "new_consumer_canaries": 0,
        "independent_recovery_established": False,
    }
    assert {row["path"] for row in manifest["objects"]} == set(candidate.PATHS)
    assert all(row["status"] == "passed" for row in manifest["objects"])
    assert all(
        row["native_artifact"]["zip_crc_verified"]
        for row in manifest["objects"]
    )
    assert all(
        row["v4_admission"] == "not_performed" for row in manifest["objects"]
    )
    assert not any(manifest["boundaries"].values())


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "denominator"),
        ("revision", "identity or registration"),
        ("plan", "identity or registration"),
        ("registration", "identity or registration"),
        ("run", "hosted or privacy"),
        ("storage", "hosted or privacy"),
        ("admission", "hosted or privacy"),
    ],
)
def test_replay_receipt_mismatch_fails_closed(
    evidence: tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]],
    mutation: str,
    message: str,
) -> None:
    plans, receipts = copy.deepcopy(evidence)
    receipt = receipts[candidate.JULY]
    if mutation == "missing":
        del receipts[candidate.ALIAS]
    elif mutation == "revision":
        receipt["scope"]["revision"] = "0" * 40
    elif mutation == "plan":
        receipt["replay"]["plan_sha256"] = "0" * 64
    elif mutation == "registration":
        receipt["replay"]["registration"]["metadata_sha256"] = "0" * 64
    elif mutation == "run":
        receipt["hosted_workflow"]["run_id"] = 1
    elif mutation == "storage":
        receipt["verification"]["payload_storage"] = "persisted"
    else:
        receipt["boundaries"]["v4_admission_performed"] = True
    with pytest.raises(ValueError, match=message):
        reconciliation.reconcile(plans, receipts)
