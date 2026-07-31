"""Tests for the deterministic stable-v1 incident rehearsal."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import ValidationError

from global_medicines_atlas.stable_v1_incident_rehearsal import (
    EvidenceIdentity,
    IncidentAction,
    IncidentCommand,
    IncidentRehearsalError,
    IncidentState,
    IncidentTransition,
    StableV1IncidentReceipt,
    default_incident_rehearsal,
    execute_incident_rehearsal,
    verify_incident_receipt,
    write_incident_receipt,
)

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "stable_v1_incident_rehearsal.schema.json"


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
    payload = receipt.model_dump(mode="json")
    Draft202012Validator(
        json.loads(SCHEMA.read_text(encoding="utf-8"))
    ).validate(payload)
    gate = payload["transitions"][1]["gate"]
    assert set(gate) == {
        "simulated_human_gate",
        "simulated_credential_authority_gate",
        "simulated_publication_gate",
        "external_effect_performed",
    }
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
    with pytest.raises(IncidentRehearsalError, match=r"schema|ordering"):
        verify_incident_receipt(tampered)


def test_partial_resigned_receipt_fails_runtime_model_and_schema() -> None:
    receipt = default_incident_rehearsal()
    partial = _resign(
        receipt.model_copy(
            update={
                "final_state": IncidentState.QUARANTINED,
                "transitions": receipt.transitions[:1],
                "signing_credential_revocation_rehearsed": False,
                "dataset_withdrawal_rehearsed": False,
                "corrected_replacement_prepared": False,
                "downstream_notification_prepared": False,
            }
        )
    )

    with pytest.raises(IncidentRehearsalError, match="schema"):
        verify_incident_receipt(partial)
    with pytest.raises(ValidationError):
        StableV1IncidentReceipt.model_validate(partial.model_dump(mode="json"))
    validator = Draft202012Validator(
        json.loads(SCHEMA.read_text(encoding="utf-8"))
    )
    with pytest.raises(SchemaValidationError):
        validator.validate(partial.model_dump(mode="json"))


def test_resigned_summary_mismatch_fails_closed() -> None:
    receipt = default_incident_rehearsal()
    inconsistent = _resign(
        receipt.model_copy(update={"dataset_withdrawal_rehearsed": False})
    )

    with pytest.raises(IncidentRehearsalError, match=r"schema|summary"):
        verify_incident_receipt(inconsistent)


def test_resigned_transition_with_missing_simulated_gate_fails_closed() -> None:
    receipt = default_incident_rehearsal()
    transition = receipt.transitions[1]
    invalid_gate = transition.gate.model_copy(
        update={"simulated_credential_authority_gate": False}
    )
    invalid_transition = transition.model_copy(update={"gate": invalid_gate})
    invalid_transition = invalid_transition.model_copy(
        update={"transition_sha256": _transition_digest(invalid_transition)}
    )
    transitions = (receipt.transitions[0], invalid_transition)
    for original in receipt.transitions[2:]:
        updated = original.model_copy(
            update={"previous_sha256": transitions[-1].transition_sha256}
        )
        updated = updated.model_copy(
            update={"transition_sha256": _transition_digest(updated)}
        )
        transitions = (*transitions, updated)
    invalid = _resign(receipt.model_copy(update={"transitions": transitions}))

    with pytest.raises(IncidentRehearsalError, match="simulated credential"):
        verify_incident_receipt(invalid)


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


def _canonical_digest(payload: object) -> str:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _transition_digest(transition: IncidentTransition) -> str:
    payload = transition.model_dump(mode="json", exclude={"transition_sha256"})
    return _canonical_digest(payload)


def _resign(receipt: StableV1IncidentReceipt) -> StableV1IncidentReceipt:
    payload = receipt.model_dump(mode="json", exclude={"receipt_sha256"})
    return receipt.model_copy(
        update={"receipt_sha256": _canonical_digest(payload)}
    )
