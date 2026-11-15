"""One exact hosted admission must not widen the frozen denominator."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import scripts.reconcile_mbs_july_frozen_v4 as ledger


def _inputs() -> list[dict[str, Any]]:
    return [
        json.loads((ledger.ROOT / path).read_bytes())
        for path in (
            ledger.PRIOR,
            ledger.FROZEN,
            ledger.RECEIPT,
            ledger.ARTIFACT,
        )
    ]


def test_exact_hosted_admission_updates_one_existing_frozen_member() -> None:
    report = ledger.reconcile(*_inputs())
    assert report == ledger.build()
    assert report["effective_counts"] == {
        "frozen_objects": 1759,
        "raw_v4_admissions": 15,
        "raw_admitted_object_reader_canaries": 15,
        "deferred_objects": 1744,
        "frozen_denominator_changed": False,
    }
    member = report["new_admission"]
    assert (
        member["approved_dataset_revision"]
        == "243f9ff5498816af6e4d9ae4db60528728f01834"
    )
    assert (
        member["later_reconciliation_revision"]
        == "40891976f77ee5e7688edceed25c9ac98a77547e"
    )
    assert report["boundaries"]["independent_recovery_established"] is False


def test_different_approved_revision_is_not_accepted() -> None:
    prior, frozen, receipt, artifact = _inputs()
    item = next(
        x for x in frozen["members"] if x["path"] == ledger.july.lineage.JULY
    )
    item["approved_dataset_revision"] = item["current_reconciliation_revision"]
    with pytest.raises(
        ValueError, match="frozen membership or prior ledger differs"
    ):
        ledger.reconcile(prior, frozen, receipt, artifact)


def test_duplicate_prior_identity_is_not_counted_twice() -> None:
    prior, frozen, receipt, artifact = _inputs()
    prior["new_admitted_identities"].append(prior["new_admitted_identities"][0])
    with pytest.raises(
        ValueError, match="frozen membership or prior ledger differs"
    ):
        ledger.reconcile(prior, frozen, receipt, artifact)


def test_consumer_digest_must_match() -> None:
    prior, frozen, receipt, artifact = _inputs()
    receipt["consumer_canary"]["verification"][
        "consumer_stream_digest_match"
    ] = False
    with pytest.raises(
        ValueError, match="hosted consumer or privacy boundary differs"
    ):
        ledger.reconcile(prior, frozen, receipt, artifact)


def test_artifact_must_bind_the_hosted_main_commit() -> None:
    prior, frozen, receipt, artifact = _inputs()
    artifact["workflow"]["commit"] = "0" * 40
    with pytest.raises(ValueError, match="hosted artifact identity differs"):
        ledger.reconcile(prior, frozen, receipt, artifact)


def test_hosted_receipt_cannot_claim_independent_recovery() -> None:
    prior, frozen, receipt, artifact = _inputs()
    receipt["boundaries"]["independent_recovery_established"] = True
    with pytest.raises(ValueError, match="hosted admission boundary differs"):
        ledger.reconcile(prior, frozen, receipt, artifact)


def test_cli_writes_and_detects_stale_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ledger, "ROOT", tmp_path)
    monkeypatch.setattr(ledger, "build", lambda: {"status": "synthetic"})
    path = tmp_path / ledger.OUTPUT
    path.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "argv", ["ledger"])
    assert ledger.main() == 0
    monkeypatch.setattr(sys, "argv", ["ledger", "--check"])
    assert ledger.main() == 0
    path.write_text("{}")
    with pytest.raises(ValueError, match="ledger is stale"):
        ledger.main()
