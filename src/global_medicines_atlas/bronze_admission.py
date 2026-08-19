"""Bronze admission keeps evidentiary payloads when processing is unsafe."""

from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Literal

import orjson
from pydantic import Field

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
    schema_version: Literal[1] = 1
    acquisition_id: str = Field(pattern=SHA256_PATTERN)
    content_id: str = Field(pattern=SHA256_PATTERN)
    state: BronzeAdmissionState
    reason_codes: tuple[str, ...] = ()
    validation_results: tuple[ValidationResult, ...] = ()
    reviewer_status: Literal["unreviewed", "approved", "rejected"] = (
        "unreviewed"
    )
    path: Path | None = Field(default=None, exclude=True)


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
        return BronzeAdmissionRecord(
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
        return BronzeAdmissionRecord(
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
    return BronzeAdmissionRecord(
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
    return BronzeAdmissionRecord(
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


def admit_bronze_landing(landing: BronzeLanding) -> BronzeAdmissionRecord:
    """Persist an admission record beside an immutable payload."""

    record = evaluate_bronze_admission(landing)
    temporal = require_temporal(landing.receipt.temporal)
    source_id = landing.receipt.source.source_id
    bronze_root = landing.receipt_path.parents[2]
    admission_dir = bronze_root / ADMISSION_DIR / source_id
    admission_dir.mkdir(parents=True, exist_ok=True)
    path = admission_dir / f"{temporal.acquisition_id}.json"
    payload = record.model_dump(mode="json", exclude_none=False)
    path.write_bytes(orjson.dumps(payload, option=orjson.OPT_SORT_KEYS) + b"\n")
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
