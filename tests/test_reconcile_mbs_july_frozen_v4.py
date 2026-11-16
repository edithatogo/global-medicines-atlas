"""One exact hosted admission must not widen the frozen denominator."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import scripts.reconcile_mbs_august_frozen_v4 as august_ledger
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


def _august_inputs() -> list[dict[str, Any]]:
    return [
        json.loads((august_ledger.ROOT / path).read_bytes())
        for path in (
            ledger.PRIOR,
            ledger.FROZEN,
            ledger.OUTPUT,
            august_ledger.RECEIPT,
            august_ledger.ARTIFACT,
        )
    ]


def test_august_hosted_readers_add_two_distinct_frozen_paths() -> None:
    result = august_ledger.reconcile(*_august_inputs())
    assert result == august_ledger.build()
    assert result["effective_counts"] == {
        "frozen_objects": 1759,
        "raw_v4_admissions": 17,
        "raw_admitted_object_reader_canaries": 17,
        "deferred_objects": 1742,
        "frozen_denominator_changed": False,
    }
    rows = result["new_admissions"]
    assert len(rows) == 2
    assert rows[0]["path"] != rows[1]["path"]
    assert rows[0]["sha256"] == rows[1]["sha256"]
    assert all(
        row["approved_dataset_revision"] == ledger.july.lineage.REVISION
        for row in rows
    )
    assert result["boundaries"]["independent_recovery_established"] is False


def test_august_rejects_duplicate_paths() -> None:
    older, frozen, previous, receipt, artifact = _august_inputs()
    receipt["objects"][1] = receipt["objects"][0]
    with pytest.raises(
        ValueError, match="hosted qualification boundary differs"
    ):
        august_ledger.reconcile(older, frozen, previous, receipt, artifact)


def test_august_rejects_different_frozen_revision() -> None:
    older, frozen, previous, receipt, artifact = _august_inputs()
    member = next(
        x for x in frozen["members"] if x["path"] == ledger.july.lineage.ALIAS
    )
    member["approved_dataset_revision"] = member[
        "current_reconciliation_revision"
    ]
    with pytest.raises(
        ValueError, match="frozen membership or prior ledger differs"
    ):
        august_ledger.reconcile(older, frozen, previous, receipt, artifact)


def test_august_rejects_consumer_digest_mismatch() -> None:
    older, frozen, previous, receipt, artifact = _august_inputs()
    receipt["objects"][1]["consumer_canary"]["verification"][
        "consumer_stream_digest_match"
    ] = False
    with pytest.raises(
        ValueError, match="hosted consumer or privacy boundary differs"
    ):
        august_ledger.reconcile(older, frozen, previous, receipt, artifact)


def test_august_rejects_artifact_or_semantic_boundary_drift() -> None:
    older, frozen, previous, receipt, artifact = _august_inputs()
    artifact["workflow"]["commit"] = "0" * 40
    with pytest.raises(ValueError, match="hosted artifact identity differs"):
        august_ledger.reconcile(older, frozen, previous, receipt, artifact)
    older, frozen, previous, receipt, artifact = _august_inputs()
    receipt["source_profile"]["field_semantics_accepted"] = True
    with pytest.raises(
        ValueError, match="hosted qualification boundary differs"
    ):
        august_ledger.reconcile(older, frozen, previous, receipt, artifact)


def test_august_cli_detects_stale_ledger(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(august_ledger, "ROOT", tmp_path)
    monkeypatch.setattr(august_ledger, "build", lambda: {"status": "synthetic"})
    path = tmp_path / august_ledger.OUTPUT
    path.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "argv", ["ledger"])
    assert august_ledger.main() == 0
    monkeypatch.setattr(sys, "argv", ["ledger", "--check"])
    assert august_ledger.main() == 0
    path.write_text("{}")
    with pytest.raises(ValueError, match="August ledger is stale"):
        august_ledger.main()
