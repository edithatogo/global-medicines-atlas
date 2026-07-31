"""Deterministic offline rehearsal of the stable-v1 incident lifecycle."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from .models import FrozenModel

Digest = str


class IncidentRehearsalError(ValueError):
    """Raised when an incident transition or receipt fails closed."""


class IncidentState(StrEnum):
    """Ordered states in the offline incident lifecycle."""

    DETECTED = "detected"
    QUARANTINED = "quarantined"
    CREDENTIAL_REVOKED = "credential_revoked"
    DATASET_WITHDRAWN = "dataset_withdrawn"
    REPLACEMENT_PREPARED = "replacement_prepared"
    NOTIFICATION_PREPARED = "notification_prepared"


class IncidentAction(StrEnum):
    """Actions admitted by the incident state machine."""

    QUARANTINE_SOURCE = "quarantine_source"
    REVOKE_SIGNING_CREDENTIAL = "revoke_signing_credential"
    WITHDRAW_DATASET = "withdraw_dataset"
    PREPARE_CORRECTED_REPLACEMENT = "prepare_corrected_replacement"
    PREPARE_DOWNSTREAM_NOTIFICATION = "prepare_downstream_notification"


class EvidenceIdentity(FrozenModel):
    """Digest-bound evidence for one non-interchangeable status dimension."""

    dimension: Literal["regulatory", "funding"]
    source_id: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class IncidentGate(FrozenModel):
    """Explicit authority gates; external effects remain false in rehearsal."""

    human_approved: bool = False
    credential_authority_approved: bool = False
    publication_approved: bool = False
    external_effect_performed: Literal[False] = False


class IncidentCommand(FrozenModel):
    """One requested transition and its authority evidence."""

    action: IncidentAction
    gate: IncidentGate = IncidentGate()


class IncidentTransition(FrozenModel):
    """One hash-chained state transition."""

    sequence: int = Field(ge=1)
    action: IncidentAction
    from_state: IncidentState
    to_state: IncidentState
    gate: IncidentGate
    previous_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    transition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class StableV1IncidentReceipt(FrozenModel):
    """Tamper-evident result of the deterministic offline rehearsal."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    incident_id: Literal["stable-v1-synthetic-compromised-source"] = (
        "stable-v1-synthetic-compromised-source"
    )
    evidence_class: Literal["synthetic_offline_rehearsal"] = (
        "synthetic_offline_rehearsal"
    )
    compromised_source_id: Literal["synthetic-compromised-source"] = (
        "synthetic-compromised-source"
    )
    initial_state: Literal[IncidentState.DETECTED] = IncidentState.DETECTED
    final_state: IncidentState
    replacement_evidence: tuple[EvidenceIdentity, EvidenceIdentity]
    transitions: tuple[IncidentTransition, ...] = Field(min_length=1)
    quarantine_enforced: bool
    signing_credential_revocation_rehearsed: bool
    dataset_withdrawal_rehearsed: bool
    corrected_replacement_prepared: bool
    downstream_notification_prepared: bool
    downstream_notification_externally_sent: Literal[False] = False
    dataset_externally_withdrawn: Literal[False] = False
    replacement_externally_published: Literal[False] = False
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_separate_evidence(self) -> Self:
        """Reject conflated or duplicate regulatory and funding evidence."""

        dimensions = {item.dimension for item in self.replacement_evidence}
        source_ids = {item.source_id for item in self.replacement_evidence}
        if (
            dimensions != {"regulatory", "funding"}
            or len(source_ids) != _REQUIRED_EVIDENCE_COUNT
        ):
            raise ValueError(
                "replacement requires separate regulatory and funding evidence"
            )
        return self


_TRANSITIONS: dict[IncidentState, tuple[IncidentAction, IncidentState]] = {
    IncidentState.DETECTED: (
        IncidentAction.QUARANTINE_SOURCE,
        IncidentState.QUARANTINED,
    ),
    IncidentState.QUARANTINED: (
        IncidentAction.REVOKE_SIGNING_CREDENTIAL,
        IncidentState.CREDENTIAL_REVOKED,
    ),
    IncidentState.CREDENTIAL_REVOKED: (
        IncidentAction.WITHDRAW_DATASET,
        IncidentState.DATASET_WITHDRAWN,
    ),
    IncidentState.DATASET_WITHDRAWN: (
        IncidentAction.PREPARE_CORRECTED_REPLACEMENT,
        IncidentState.REPLACEMENT_PREPARED,
    ),
    IncidentState.REPLACEMENT_PREPARED: (
        IncidentAction.PREPARE_DOWNSTREAM_NOTIFICATION,
        IncidentState.NOTIFICATION_PREPARED,
    ),
}
_ZERO_DIGEST = "0" * 64
_REQUIRED_EVIDENCE_COUNT = 2


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        + "\n"
    ).encode()


def _digest(value: object) -> Digest:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _required_gate(action: IncidentAction, gate: IncidentGate) -> None:
    if action is IncidentAction.REVOKE_SIGNING_CREDENTIAL and not (
        gate.human_approved and gate.credential_authority_approved
    ):
        raise IncidentRehearsalError(
            "credential revocation requires human and credential authority gates"
        )
    if action in {
        IncidentAction.WITHDRAW_DATASET,
        IncidentAction.PREPARE_CORRECTED_REPLACEMENT,
    } and not (gate.human_approved and gate.publication_approved):
        raise IncidentRehearsalError(
            "dataset publication transition requires human and publication gates"
        )
    if (
        action is IncidentAction.PREPARE_DOWNSTREAM_NOTIFICATION
        and not gate.human_approved
    ):
        raise IncidentRehearsalError(
            "downstream notification preparation requires a human gate"
        )


def _transition_payload(
    *,
    sequence: int,
    command: IncidentCommand,
    from_state: IncidentState,
    to_state: IncidentState,
    previous_sha256: str,
) -> dict[str, object]:
    return {
        "sequence": sequence,
        "action": command.action.value,
        "from_state": from_state.value,
        "to_state": to_state.value,
        "gate": command.gate.model_dump(mode="json"),
        "previous_sha256": previous_sha256,
    }


def execute_incident_rehearsal(
    commands: tuple[IncidentCommand, ...],
    replacement_evidence: tuple[EvidenceIdentity, EvidenceIdentity],
) -> StableV1IncidentReceipt:
    """Execute commands once, accepting exact adjacent retries idempotently."""

    state = IncidentState.DETECTED
    previous_sha256 = _ZERO_DIGEST
    transitions: list[IncidentTransition] = []
    previous_command: IncidentCommand | None = None
    for command in commands:
        if command == previous_command:
            continue
        expected = _TRANSITIONS.get(state)
        if expected is None or command.action is not expected[0]:
            raise IncidentRehearsalError(
                f"invalid action {command.action.value!r} from state {state.value!r}"
            )
        _required_gate(command.action, command.gate)
        to_state = expected[1]
        payload = _transition_payload(
            sequence=len(transitions) + 1,
            command=command,
            from_state=state,
            to_state=to_state,
            previous_sha256=previous_sha256,
        )
        transition_sha256 = _digest(payload)
        transitions.append(
            IncidentTransition(
                sequence=len(transitions) + 1,
                action=command.action,
                from_state=state,
                to_state=to_state,
                gate=command.gate,
                previous_sha256=previous_sha256,
                transition_sha256=transition_sha256,
            )
        )
        state = to_state
        previous_sha256 = transition_sha256
        previous_command = command
    if state is not IncidentState.NOTIFICATION_PREPARED:
        raise IncidentRehearsalError(
            f"incident rehearsal stopped fail-closed in state {state.value!r}"
        )
    unsigned = StableV1IncidentReceipt(
        final_state=state,
        replacement_evidence=replacement_evidence,
        transitions=tuple(transitions),
        quarantine_enforced=True,
        signing_credential_revocation_rehearsed=True,
        dataset_withdrawal_rehearsed=True,
        corrected_replacement_prepared=True,
        downstream_notification_prepared=True,
        receipt_sha256=_ZERO_DIGEST,
        limitations=(
            "All transitions use synthetic offline artifacts.",
            "No credential was revoked, dataset withdrawn, replacement published, or notification sent externally.",
        ),
    )
    receipt_payload = unsigned.model_dump(
        mode="json", exclude={"receipt_sha256"}
    )
    return unsigned.model_copy(
        update={"receipt_sha256": _digest(receipt_payload)}
    )


def verify_incident_receipt(receipt: StableV1IncidentReceipt) -> None:
    """Verify lifecycle ordering, chain integrity, and receipt identity."""

    state = IncidentState.DETECTED
    previous_sha256 = _ZERO_DIGEST
    for sequence, transition in enumerate(receipt.transitions, start=1):
        expected = _TRANSITIONS.get(state)
        expected_identity = None if expected is None else expected[0:2]
        observed_identity = (transition.action, transition.to_state)
        if (
            expected_identity != observed_identity
            or transition.sequence != sequence
            or transition.from_state is not state
            or transition.previous_sha256 != previous_sha256
        ):
            raise IncidentRehearsalError(
                "receipt transition ordering is invalid"
            )
        _required_gate(transition.action, transition.gate)
        payload = transition.model_dump(
            mode="json", exclude={"transition_sha256"}
        )
        if _digest(payload) != transition.transition_sha256:
            raise IncidentRehearsalError(
                "receipt transition chain was tampered with"
            )
        state = transition.to_state
        previous_sha256 = transition.transition_sha256
    if state is not receipt.final_state:
        raise IncidentRehearsalError(
            "receipt final state disagrees with transition chain"
        )
    payload = receipt.model_dump(mode="json", exclude={"receipt_sha256"})
    if _digest(payload) != receipt.receipt_sha256:
        raise IncidentRehearsalError("receipt identity was tampered with")


def write_incident_receipt(
    output: Path, receipt: StableV1IncidentReceipt
) -> None:
    """Verify and atomically persist canonical deterministic JSON."""

    verify_incident_receipt(receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_bytes(_canonical_json(receipt.model_dump(mode="json")))
    temporary.replace(output)


def default_incident_rehearsal() -> StableV1IncidentReceipt:
    """Run the complete synthetic lifecycle with explicit simulated gates."""

    human = IncidentGate(human_approved=True)
    credential = IncidentGate(
        human_approved=True,
        credential_authority_approved=True,
    )
    publication = IncidentGate(
        human_approved=True,
        publication_approved=True,
    )
    commands = (
        IncidentCommand(action=IncidentAction.QUARANTINE_SOURCE),
        IncidentCommand(
            action=IncidentAction.REVOKE_SIGNING_CREDENTIAL,
            gate=credential,
        ),
        IncidentCommand(
            action=IncidentAction.WITHDRAW_DATASET, gate=publication
        ),
        IncidentCommand(
            action=IncidentAction.PREPARE_CORRECTED_REPLACEMENT,
            gate=publication,
        ),
        IncidentCommand(
            action=IncidentAction.PREPARE_DOWNSTREAM_NOTIFICATION,
            gate=human,
        ),
    )
    evidence = (
        EvidenceIdentity(
            dimension="regulatory",
            source_id="synthetic-regulator-correction",
            sha256=hashlib.sha256(b"regulatory correction\n").hexdigest(),
        ),
        EvidenceIdentity(
            dimension="funding",
            source_id="synthetic-funder-correction",
            sha256=hashlib.sha256(b"funding correction\n").hexdigest(),
        ),
    )
    return execute_incident_rehearsal(commands, evidence)
