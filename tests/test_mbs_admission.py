"""MBS table acceptance and quarantine remain distinct from publication."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from global_medicines_atlas.bronze_admission import persist_admission_decision
from global_medicines_atlas.mbs_admission import (
    MbsTableAdmission,
    admit_mbs_html_tables,
    mbs_admission_health,
)
from global_medicines_atlas.mbs_compatibility import (
    historical_targets,
    rehearse_probes,
)
from global_medicines_atlas.mbs_tables import TableContract
from global_medicines_atlas.receipts import EvidenceClass, SourceReceipt
from global_medicines_atlas.reuse_gate import acquire_new_decision

NOW = datetime(2026, 8, 30, tzinfo=UTC)
PAYLOAD = b"<table><tr><th>Item</th></tr><tr><td>00104</td></tr></table>"


def _receipt(tmp_path: Path, payload: bytes) -> SourceReceipt:
    result = rehearse_probes(
        historical_targets((), 202401, 202401),
        tmp_path,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=payload, headers={"content-type": "text/html"}
            )
        ),
        reuse_decision=acquire_new_decision("au-mbs"),
        clock=lambda: NOW,
        sleep=lambda _: None,
    )
    receipt = result.attempts[0]
    assert isinstance(receipt, SourceReceipt)
    return receipt


def test_admission_binds_source_contract_and_clock(tmp_path: Path) -> None:
    receipt = _receipt(tmp_path, PAYLOAD)
    contract = (TableContract(table_id="items", columns=("Item",)),)
    outcome = admit_mbs_html_tables(PAYLOAD, receipt, contract, decided_at=NOW)
    assert outcome.decision.state.value == "accepted"
    assert outcome.decision.content_id == receipt.payload.sha256
    assert outcome.decision.decided_at == NOW
    assert outcome.tables[0].rows == (("00104",),)
    assert outcome.public_data_ready is False
    assert outcome == admit_mbs_html_tables(
        PAYLOAD, receipt, contract, decided_at=NOW
    )
    renamed = admit_mbs_html_tables(
        PAYLOAD,
        receipt,
        (TableContract(table_id="other", columns=("Item",)),),
        decided_at=NOW,
    )
    assert renamed.decision.decision_id != outcome.decision.decision_id


def test_maintenance_payload_is_quarantined_not_success(tmp_path: Path) -> None:
    payload = b"<html>Maintenance</html>"
    receipt = _receipt(tmp_path, payload)
    outcome = admit_mbs_html_tables(
        payload,
        receipt,
        (TableContract(table_id="items", columns=("Item",)),),
        decided_at=NOW,
    )
    assert outcome.decision.state.value == "quarantined"
    assert not outcome.tables
    assert not outcome.public_data_ready
    assert outcome.source_receipt == receipt
    assert outcome.decision.reason_codes == ("mbs_table_profile_mismatch",)


def test_digest_mismatch_cannot_become_an_admission(tmp_path: Path) -> None:
    receipt = _receipt(tmp_path, PAYLOAD)
    with pytest.raises(ValueError, match="match source bytes"):
        admit_mbs_html_tables(
            PAYLOAD + b" ",
            receipt,
            (TableContract(table_id="items", columns=("Item",)),),
            decided_at=NOW,
        )


def test_decision_persistence_is_append_only_and_roundtrips(
    tmp_path: Path,
) -> None:
    receipt = _receipt(tmp_path, PAYLOAD)
    outcome = admit_mbs_html_tables(
        PAYLOAD,
        receipt,
        (TableContract(table_id="items", columns=("Item",)),),
        decided_at=NOW,
    )
    receipt_path = tmp_path / "bronze" / "receipts" / "au-mbs" / "source.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes(receipt.canonical_json())
    before = receipt_path.read_bytes()
    persisted = persist_admission_decision(
        outcome.decision, receipt_path=receipt_path, receipt=receipt
    )
    assert persisted.path is not None
    decision_bytes = persisted.path.read_bytes()
    assert (
        persist_admission_decision(
            outcome.decision, receipt_path=receipt_path, receipt=receipt
        )
        == persisted
    )
    assert persisted.path.read_bytes() == decision_bytes
    assert receipt_path.read_bytes() == before
    assert (
        MbsTableAdmission.model_validate_json(outcome.model_dump_json())
        == outcome
    )


@pytest.mark.parametrize(
    "field", ["tables", "public", "source", "uri", "rows", "acquisition"]
)
def test_serialized_outcome_rejects_forged_binding(
    tmp_path: Path, field: str
) -> None:
    receipt = _receipt(tmp_path, PAYLOAD)
    outcome = admit_mbs_html_tables(
        PAYLOAD,
        receipt,
        (TableContract(table_id="items", columns=("Item",)),),
        decided_at=NOW,
    )
    value = outcome.model_dump(mode="json")
    if field == "tables":
        value["tables"] = []
    elif field == "public":
        value["public_data_ready"] = True
    elif field == "source":
        value["source_receipt"]["source"]["source_id"] = "au-pbs"
    elif field == "uri":
        value["tables"][0]["provenance"]["source_uri"] = (
            "https://example.org/other"
        )
    elif field == "rows":
        value["tables"][0]["rows"] = [["99999"]]
    else:
        value["source_receipt"]["temporal"]["acquisition_id"] = "f" * 64
    with pytest.raises(ValueError, match=r"MBS|accepted|literal"):
        MbsTableAdmission.model_validate(value)


def test_rehearsal_cannot_enter_live_health_history(tmp_path: Path) -> None:
    outcome = admit_mbs_html_tables(
        PAYLOAD,
        _receipt(tmp_path, PAYLOAD),
        (TableContract(table_id="items", columns=("Item",)),),
        decided_at=NOW,
    )
    with pytest.raises(ValueError, match="live acquisition"):
        mbs_admission_health(outcome)


@pytest.mark.parametrize("accepted", [True, False])
def test_health_separates_table_failures_from_usable_data(
    tmp_path: Path, *, accepted: bool
) -> None:
    # Simulated live-class receipt tests the policy; no live request is made.
    payload = PAYLOAD if accepted else b"<html>Maintenance</html>"
    receipt = _receipt(tmp_path, payload).model_copy(
        update={"evidence_class": EvidenceClass.LIVE}
    )
    outcome = admit_mbs_html_tables(
        payload,
        receipt,
        (TableContract(table_id="items", columns=("Item",)),),
        decided_at=NOW,
    )
    health = mbs_admission_health(outcome, previous_consecutive_failures=2)
    assert health.observation.state.value == (
        "available" if accepted else "unavailable"
    )
    assert health.observation.checked_at == NOW
    assert health.observation.is_fresh is None
    assert health.consecutive_failures == (0 if accepted else 3)
    assert health.escalation.value == ("none" if accepted else "open")
    assert outcome.public_data_ready is False
