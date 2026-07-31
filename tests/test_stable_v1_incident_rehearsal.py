"""Tests for the deterministic stable-v1 incident rehearsal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.stable_v1_incident_rehearsal import (
    EvidenceIdentity,
    IncidentAction,
    IncidentCommand,
    IncidentRehearsalError,
    IncidentState,
    StableV1IncidentReceipt,
    default_incident_rehearsal,
    execute_incident_rehearsal,
    verify_incident_receipt,
    write_incident_receipt,
)

pytestmark = pytest.mark.integration


def test_complete_rehearsal_is_fail_closed_and_does_not_claim_external_effects(
    tmp_path: Path,
) -> None:
    receipt = default_incident_rehearsal()
    output = tmp_path / "receipt.json"
    write_incident_receipt(output, receipt)

    assert receipt.final_state is IncidentState.NOTIFICATION_PREPARED
    assert receipt.quarantine_enforced
    assert receipt.signing_credential_revocation_rehearsed
    assert receipt.dataset_withdrawal_rehearsed
    assert receipt.corrected_replacement_prepared
    assert receipt.downstream_notification_prepared
    assert not receipt.downstream_notification_externally_sent
    assert not receipt.dataset_externally_withdrawn
    assert not receipt.replacement_externally_published
    assert (
        StableV1IncidentReceipt.model_validate_json(output.read_text())
        == receipt
    )


@pytest.mark.parametrize(
    "commands",
    [
        (IncidentCommand(action=IncidentAction.WITHDRAW_DATASET),),
        (
            IncidentCommand(action=IncidentAction.QUARANTINE_SOURCE),
            IncidentCommand(action=IncidentAction.WITHDRAW_DATASET),
        ),
    ],
)
def test_invalid_ordering_fails_closed(
    commands: tuple[IncidentCommand, ...],
) -> None:
    with pytest.raises(IncidentRehearsalError, match="invalid action"):
        execute_incident_rehearsal(commands, _evidence())


def test_missing_human_credential_and_publication_gates_fail_closed() -> None:
    quarantined = (IncidentCommand(action=IncidentAction.QUARANTINE_SOURCE),)
    with pytest.raises(IncidentRehearsalError, match="credential authority"):
        execute_incident_rehearsal(
            (
                *quarantined,
                IncidentCommand(
                    action=IncidentAction.REVOKE_SIGNING_CREDENTIAL
                ),
            ),
            _evidence(),
        )


def test_tampering_is_detected() -> None:
    receipt = default_incident_rehearsal()
    tampered = receipt.model_copy(
        update={
            "transitions": (
                receipt.transitions[0].model_copy(update={"sequence": 2}),
                *receipt.transitions[1:],
            )
        }
    )
    with pytest.raises(IncidentRehearsalError, match="ordering"):
        verify_incident_receipt(tampered)


def test_exact_retry_and_repeated_runs_are_idempotent(tmp_path: Path) -> None:
    receipt = default_incident_rehearsal()
    commands = tuple(
        IncidentCommand(action=item.action, gate=item.gate)
        for item in receipt.transitions
    )
    retried = execute_incident_rehearsal(
        (commands[0], commands[0], *commands[1:]),
        receipt.replacement_evidence,
    )
    assert retried == receipt

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_incident_receipt(first, default_incident_rehearsal())
    write_incident_receipt(second, default_incident_rehearsal())
    assert first.read_bytes() == second.read_bytes()


def test_regulatory_and_funding_evidence_must_remain_separate() -> None:
    receipt = default_incident_rehearsal()
    regulatory = receipt.replacement_evidence[0]
    payload = receipt.model_dump(mode="json")
    payload["replacement_evidence"] = [
        regulatory.model_dump(mode="json"),
        regulatory.model_dump(mode="json"),
    ]
    with pytest.raises(
        ValidationError, match="separate regulatory and funding"
    ):
        StableV1IncidentReceipt.model_validate(payload)


def test_serialized_receipt_never_claims_notification_was_sent() -> None:
    payload = json.loads(default_incident_rehearsal().model_dump_json())
    assert payload["downstream_notification_externally_sent"] is False
    assert "notification sent externally" in payload["limitations"][1]


def _evidence() -> tuple[EvidenceIdentity, EvidenceIdentity]:
    return (
        EvidenceIdentity(
            dimension="regulatory", source_id="reg", sha256="1" * 64
        ),
        EvidenceIdentity(
            dimension="funding", source_id="fund", sha256="2" * 64
        ),
    )
