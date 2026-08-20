"""Bronze admission keeps evidentiary payloads when processing is unsafe."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Literal

import orjson
from pydantic import AwareDatetime, Field, model_validator

from .bronze_integrity import inspect_untrusted_payload
from .bronze_landing import ADMISSION_DIR, BronzeLanding
from .models import FrozenModel
from .receipts import SHA256_PATTERN, require_temporal

ADMISSION_SCHEMA_ID = "global-medicines-atlas.bronze-admission"


class BronzeAdmissionState(StrEnum):
    """Lifecycle of one landed payload relative to downstream processing."""

    LANDED = "landed"
    ACCEPTED = "accepted"
    QUARANTINED = "quarantined"
    REJECTED_FROM_PROCESSING = "rejected-from-processing"


class DownstreamAdmissionError(ValueError):
    """Downstream asked for material that is not admitted."""


class ValidationResult(FrozenModel):
    """One machine-readable validation outcome."""

    check_id: str = Field(min_length=1)
    passed: bool
    message: str = Field(min_length=1)


class BronzeAdmissionRecord(FrozenModel):
    """Admission decision bound to an immutable acquisition event."""

    schema_id: Literal["global-medicines-atlas.bronze-admission"] = (
        ADMISSION_SCHEMA_ID
    )
    schema_version: Literal[2] = 2
    decision_id: str = Field(pattern=SHA256_PATTERN)
    acquisition_id: str = Field(pattern=SHA256_PATTERN)
    content_id: str = Field(pattern=SHA256_PATTERN)
    state: BronzeAdmissionState
    reason_codes: tuple[str, ...] = ()
    validation_results: tuple[ValidationResult, ...] = ()
    reviewer_status: Literal["unreviewed", "approved", "rejected"] = (
        "unreviewed"
    )
    actor: str = Field(min_length=1)
    decided_at: AwareDatetime
    supersedes_decision_id: str | None = Field(
        default=None,
        pattern=SHA256_PATTERN,
    )
    path: Path | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def validate_decision_identity(self) -> BronzeAdmissionRecord:
        if self.supersedes_decision_id == self.decision_id:
            raise ValueError("admission decision cannot supersede itself")
        expected = admission_decision_id_for(
            acquisition_id=self.acquisition_id,
            content_id=self.content_id,
            state=self.state,
            reason_codes=self.reason_codes,
            validation_results=self.validation_results,
            reviewer_status=self.reviewer_status,
            actor=self.actor,
            decided_at=self.decided_at,
            supersedes_decision_id=self.supersedes_decision_id,
        )
        if self.decision_id != expected:
            raise ValueError("decision_id does not bind the admission decision")
        return self


def admission_decision_id_for(
    *,
    acquisition_id: str,
    content_id: str,
    state: BronzeAdmissionState,
    reason_codes: tuple[str, ...],
    validation_results: tuple[ValidationResult, ...],
    reviewer_status: str,
    actor: str,
    decided_at: datetime,
    supersedes_decision_id: str | None,
) -> str:
    """Bind an admission event to its evidence, actor, clock, and parent."""

    material = {
        "acquisition_id": acquisition_id,
        "actor": actor,
        "content_id": content_id,
        "decided_at": decided_at.isoformat(),
        "reason_codes": reason_codes,
        "reviewer_status": reviewer_status,
        "state": state.value,
        "supersedes_decision_id": supersedes_decision_id,
        "validation_results": [
            item.model_dump(mode="json") for item in validation_results
        ],
    }
    return sha256(
        orjson.dumps(material, option=orjson.OPT_SORT_KEYS)
    ).hexdigest()


def create_admission_decision(
    *,
    acquisition_id: str,
    content_id: str,
    state: BronzeAdmissionState,
    reason_codes: tuple[str, ...] = (),
    validation_results: tuple[ValidationResult, ...] = (),
    reviewer_status: Literal[
        "unreviewed", "approved", "rejected"
    ] = "unreviewed",
    actor: str = "global-medicines-atlas:automated-admission-v2",
    decided_at: datetime | None = None,
    supersedes_decision_id: str | None = None,
) -> BronzeAdmissionRecord:
    finished = decided_at or datetime.now(UTC)
    decision_id = admission_decision_id_for(
        acquisition_id=acquisition_id,
        content_id=content_id,
        state=state,
        reason_codes=reason_codes,
        validation_results=validation_results,
        reviewer_status=reviewer_status,
        actor=actor,
        decided_at=finished,
        supersedes_decision_id=supersedes_decision_id,
    )
    return BronzeAdmissionRecord(
        decision_id=decision_id,
        acquisition_id=acquisition_id,
        content_id=content_id,
        state=state,
        reason_codes=reason_codes,
        validation_results=validation_results,
        reviewer_status=reviewer_status,
        actor=actor,
        decided_at=finished,
        supersedes_decision_id=supersedes_decision_id,
    )


def classify_bronze_payload(
    payload: bytes,
    *,
    acquisition_id: str | None = None,
) -> BronzeAdmissionRecord:
    """Classify bytes without mutating them; malformed stays preservable."""

    content_id = sha256(payload).hexdigest()
    event_id = (
        acquisition_id or sha256(f"classify\n{content_id}".encode()).hexdigest()
    )
    try:
        parsed = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
        return create_admission_decision(
            acquisition_id=event_id,
            content_id=content_id,
            state=BronzeAdmissionState.QUARANTINED,
            reason_codes=("malformed_payload",),
            validation_results=(
                ValidationResult(
                    check_id="json-object",
                    passed=False,
                    message=str(error) or "payload is not JSON",
                ),
            ),
        )
    if not isinstance(parsed, dict):
        return create_admission_decision(
            acquisition_id=event_id,
            content_id=content_id,
            state=BronzeAdmissionState.QUARANTINED,
            reason_codes=("schema_breaking",),
            validation_results=(
                ValidationResult(
                    check_id="json-object",
                    passed=False,
                    message="bronze JSON payloads must be objects",
                ),
            ),
        )
    return create_admission_decision(
        acquisition_id=event_id,
        content_id=content_id,
        state=BronzeAdmissionState.ACCEPTED,
        validation_results=(
            ValidationResult(
                check_id="json-object",
                passed=True,
                message="payload is a JSON object",
            ),
        ),
    )


def evaluate_bronze_admission(landing: BronzeLanding) -> BronzeAdmissionRecord:
    """Admit or quarantine landed bytes; never rewrite the payload."""

    temporal = require_temporal(landing.receipt.temporal)
    payload = landing.payload_path.read_bytes()
    http = getattr(landing.receipt.retrieval, "http", None)
    raw_length = None if http is None else getattr(http, "content_length", None)
    declared_length = raw_length if isinstance(raw_length, int) else None
    inspection = inspect_untrusted_payload(
        payload,
        declared_media=landing.payload_path.suffix,
        declared_filename=landing.payload_path.name,
        expected_sha256=landing.receipt.payload.sha256,
        declared_length=declared_length,
        acquisition_id=temporal.acquisition_id,
    )
    if inspection.blocking:
        state = BronzeAdmissionState.QUARANTINED
        reasons = inspection.reason_codes
    elif inspection.sniffed_kind == "json":
        return classify_bronze_payload(
            payload,
            acquisition_id=temporal.acquisition_id,
        )
    else:
        state = BronzeAdmissionState.ACCEPTED
        reasons = ()
    return create_admission_decision(
        acquisition_id=temporal.acquisition_id,
        content_id=inspection.content_id,
        state=state,
        reason_codes=reasons,
        validation_results=tuple(
            ValidationResult(
                check_id=item.check_id,
                passed=item.passed,
                message=item.message,
            )
            for item in inspection.findings
        ),
    )


def admit_bronze_landing(
    landing: BronzeLanding,
    *,
    actor: str = "global-medicines-atlas:automated-admission-v2",
    decided_at: datetime | None = None,
    supersedes_decision_id: str | None = None,
) -> BronzeAdmissionRecord:
    """Persist an admission record beside an immutable payload."""

    evaluated = evaluate_bronze_admission(landing)
    record = create_admission_decision(
        acquisition_id=evaluated.acquisition_id,
        content_id=evaluated.content_id,
        state=evaluated.state,
        reason_codes=evaluated.reason_codes,
        validation_results=evaluated.validation_results,
        reviewer_status=evaluated.reviewer_status,
        actor=actor,
        decided_at=decided_at,
        supersedes_decision_id=supersedes_decision_id,
    )
    temporal = require_temporal(landing.receipt.temporal)
    source_id = landing.receipt.source.source_id
    bronze_root = landing.receipt_path.parents[2]
    admission_dir = bronze_root / ADMISSION_DIR / source_id
    admission_dir.mkdir(parents=True, exist_ok=True)
    if supersedes_decision_id is not None:
        superseded = (
            admission_dir
            / temporal.acquisition_id
            / f"{supersedes_decision_id}.json"
        )
        if not superseded.is_file():
            raise ValueError("superseded admission decision does not exist")
    path = (
        admission_dir / temporal.acquisition_id / f"{record.decision_id}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = record.model_dump(mode="json", exclude_none=False)
    serialized = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS) + b"\n"
    if path.exists() and path.read_bytes() != serialized:
        raise ValueError("append-only admission history cannot be rewritten")
    if not path.exists():
        path.write_bytes(serialized)
    return record.model_copy(update={"path": path})


def require_admitted_for_processing(
    record: BronzeAdmissionRecord,
    *,
    authorized: bool = False,
) -> BronzeAdmissionRecord:
    """Fail closed on quarantined or rejected material unless authorized."""

    if record.state is BronzeAdmissionState.ACCEPTED:
        return record
    if record.state is BronzeAdmissionState.LANDED:
        raise DownstreamAdmissionError("landed material is not yet admitted")
    if authorized and record.state is BronzeAdmissionState.QUARANTINED:
        return record
    raise DownstreamAdmissionError(
        "fail closed on quarantined material unless explicitly authorised"
    )
