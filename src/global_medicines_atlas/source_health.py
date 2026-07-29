"""Bounded, non-persisting health and schema-drift probes."""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from enum import StrEnum
from hashlib import sha256
from typing import Final, cast

import httpx
import orjson
from pydantic import Field

from .models import FrozenModel
from .source_catalog import (
    AccessMode,
    MedicineDataSource,
    SourceReadiness,
)

DEFAULT_MAX_BYTES: Final = 65_536
DEFAULT_TIMEOUT_SECONDS: Final = 10.0
type JsonValue = (
    bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None
)


class ProbeState(StrEnum):
    """Fail-honest outcomes for a source-health observation."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"


class SchemaDriftState(StrEnum):
    """Comparison outcome for a current observation and prior baseline."""

    UNCHANGED = "unchanged"
    CHANGED = "changed"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"
    NO_BASELINE = "no_baseline"


class EscalationState(StrEnum):
    """Deterministic escalation transition for one source-health receipt."""

    NONE = "none"
    OPEN = "open"
    DEDUPLICATED = "deduplicated"
    RESOLVED = "resolved"


class AdapterParityState(StrEnum):
    """Whether adapter output matches its prior qualified fingerprint."""

    MATCHED = "matched"
    CHANGED = "changed"
    NOT_ASSESSED = "not_assessed"


class RetryAttempt(FrozenModel):
    """Metadata-only record of a bounded probe attempt."""

    attempt: int = Field(ge=1)
    attempted_at: datetime
    outcome: ProbeState
    status_code: int | None = Field(default=None, ge=100, le=599)
    retry_after_seconds: int | None = Field(default=None, ge=0)


class SourceHealthObservation(FrozenModel):
    """Metadata-only observation; source payload bytes are never retained."""

    source_id: str = Field(min_length=1)
    checked_at: datetime
    state: ProbeState
    endpoint: str | None = None
    status_code: int | None = Field(default=None, ge=100, le=599)
    content_type: str | None = None
    bytes_sampled: int = Field(default=0, ge=0)
    schema_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    expected_cadence_seconds: int | None = Field(default=None, ge=1)
    source_updated_at: datetime | None = None
    freshness_age_seconds: int | None = Field(default=None, ge=0)
    is_fresh: bool | None = None
    detail: str = Field(min_length=1)


class SchemaDriftObservation(FrozenModel):
    """Metadata-only comparison; no source payload is retained."""

    source_id: str = Field(min_length=1)
    checked_at: datetime
    state: SchemaDriftState
    current_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    previous_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    detail: str = Field(min_length=1)


class SourceHealthReceipt(FrozenModel):
    """Durable deterministic receipt for health and escalation state."""

    schema_version: int = Field(default=1, ge=1)
    receipt_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    observation: SourceHealthObservation
    consecutive_failures: int = Field(ge=0)
    retry_history: tuple[RetryAttempt, ...] = ()
    deduplication_key: str = Field(min_length=1)
    escalation: EscalationState
    adapter_output_parity: AdapterParityState
    adapter_output_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    expected_adapter_output_fingerprint: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )


def _endpoint(source: MedicineDataSource) -> str | None:
    if source.access_mode in {AccessMode.API, AccessMode.API_AND_DOWNLOAD}:
        return str(source.api_url) if source.api_url is not None else None
    if source.access_mode is AccessMode.DOWNLOAD:
        return (
            str(source.download_url)
            if source.download_url is not None
            else None
        )
    return None


def _json_shape(value: JsonValue) -> object:
    if isinstance(value, dict):
        shape: object = {
            key: _json_shape(item) for key, item in sorted(value.items())
        }
    elif isinstance(value, list):
        shapes = {_canonical(_json_shape(item)) for item in value[:20]}
        shape = {"array_items": sorted(shapes)}
    elif value is None:
        shape = "null"
    elif isinstance(value, bool):
        shape = "boolean"
    elif isinstance(value, int):
        shape = "integer"
    elif isinstance(value, float):
        shape = "number"
    else:
        shape = "string"
    return shape


def _canonical(value: object) -> str:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS).decode("utf-8")


def schema_fingerprint(
    payload: bytes,
    *,
    content_type: str = "",
) -> str:
    """Fingerprint structure, not values, from a bounded response sample."""

    media_type = content_type.partition(";")[0].strip().lower()
    structure: object
    if "json" in media_type:
        structure = {
            "format": "json",
            "shape": _json_shape(cast("JsonValue", orjson.loads(payload))),
        }
    elif "csv" in media_type or media_type == "text/plain":
        text = payload.decode("utf-8-sig")
        rows = csv.reader(io.StringIO(text))
        try:
            header = next(rows)
        except StopIteration:
            header = []
        structure = {
            "format": "csv",
            "columns": [column.strip() for column in header],
        }
    elif "xml" in media_type:
        text = payload.decode("utf-8", errors="strict")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError(
                "DTD and entity declarations are not fingerprinted"
            )
        tags = sorted({
            match.group(1)
            for match in re.finditer(
                r"<(?:[A-Za-z_][\w.-]*:)?([A-Za-z_][\w.-]*)"
                r"(?:\s|/?>)",
                text,
            )
        })
        if not tags:
            raise ValueError("XML sample contains no element tags")
        structure = {"format": "xml", "tags": tags}
    else:
        structure = {
            "format": media_type or "unknown",
            "prefix_digest": sha256(payload[:4096]).hexdigest(),
        }
    return sha256(
        orjson.dumps(structure, option=orjson.OPT_SORT_KEYS)
    ).hexdigest()


def _request_sample(
    endpoint: str,
    *,
    headers: dict[str, str],
    transport: httpx.BaseTransport | None,
    timeout_seconds: float,
    max_bytes: int,
) -> httpx.Response:
    with (
        httpx.Client(
            transport=transport,
            timeout=timeout_seconds,
            follow_redirects=False,
        ) as client,
        client.stream("GET", endpoint, headers=headers) as response,
    ):
        sample = bytearray()
        for chunk in response.iter_bytes():
            remaining = max_bytes + 1 - len(sample)
            sample.extend(chunk[:remaining])
            if len(sample) > max_bytes:
                break
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            content=bytes(sample),
            request=response.request,
        )


def _non_probeable_observation(
    source: MedicineDataSource,
    observed_at: datetime,
    expected_cadence_seconds: int | None,
) -> SourceHealthObservation | None:
    if source.access_mode is AccessMode.LICENSED_FEED:
        detail = "licensed feed requires authorised access; no probe attempted"
        state = ProbeState.BLOCKED
    elif source.readiness is SourceReadiness.BLOCKED:
        detail = "catalog marks source blocked; no probe attempted"
        state = ProbeState.BLOCKED
    elif _endpoint(source) is None:
        detail = "catalog exposes no probeable API or download endpoint"
        state = ProbeState.UNAVAILABLE
    else:
        return None
    return SourceHealthObservation(
        source_id=source.source_id,
        checked_at=observed_at,
        state=state,
        expected_cadence_seconds=expected_cadence_seconds,
        detail=detail,
    )


def _evaluate_response(
    source: MedicineDataSource,
    observed_at: datetime,
    endpoint: str,
    response: httpx.Response,
    max_bytes: int,
    expected_cadence: timedelta | None,
) -> SourceHealthObservation:
    cadence_seconds = (
        int(expected_cadence.total_seconds())
        if expected_cadence is not None
        else None
    )
    source_updated_at = _source_updated_at(response)
    freshness_age_seconds = (
        max(0, int((observed_at - source_updated_at).total_seconds()))
        if source_updated_at is not None
        else None
    )
    is_fresh = (
        freshness_age_seconds <= cadence_seconds
        if freshness_age_seconds is not None and cadence_seconds is not None
        else None
    )
    if response.is_redirect:
        return SourceHealthObservation(
            source_id=source.source_id,
            checked_at=observed_at,
            state=ProbeState.UNAVAILABLE,
            endpoint=endpoint,
            status_code=response.status_code,
            expected_cadence_seconds=cadence_seconds,
            source_updated_at=source_updated_at,
            freshness_age_seconds=freshness_age_seconds,
            is_fresh=is_fresh,
            detail="redirect refused by bounded probe",
        )
    response.raise_for_status()
    sample = response.content[:max_bytes]
    content_type = response.headers.get("content-type", "")
    if len(response.content) > max_bytes:
        return SourceHealthObservation(
            source_id=source.source_id,
            checked_at=observed_at,
            state=ProbeState.AVAILABLE,
            endpoint=endpoint,
            status_code=response.status_code,
            content_type=content_type or None,
            bytes_sampled=len(sample),
            expected_cadence_seconds=cadence_seconds,
            source_updated_at=source_updated_at,
            freshness_age_seconds=freshness_age_seconds,
            is_fresh=is_fresh,
            detail=(
                "bounded response sample was truncated; "
                "schema fingerprint withheld"
            ),
        )
    fingerprint = schema_fingerprint(sample, content_type=content_type)
    return SourceHealthObservation(
        source_id=source.source_id,
        checked_at=observed_at,
        state=ProbeState.AVAILABLE,
        endpoint=endpoint,
        status_code=response.status_code,
        content_type=content_type or None,
        bytes_sampled=len(sample),
        schema_fingerprint=fingerprint,
        expected_cadence_seconds=cadence_seconds,
        source_updated_at=source_updated_at,
        freshness_age_seconds=freshness_age_seconds,
        is_fresh=is_fresh,
        detail="bounded response sampled; payload bytes discarded",
    )


def _source_updated_at(response: httpx.Response) -> datetime | None:
    value = response.headers.get("last-modified")
    if value is None:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except TypeError, ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def probe_source(
    source: MedicineDataSource,
    *,
    checked_at: datetime | None = None,
    transport: httpx.BaseTransport | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    expected_cadence: timedelta | None = None,
) -> SourceHealthObservation:
    """Probe one declared access surface without persisting its response."""

    observed_at = checked_at or datetime.now(tz=UTC)
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    if expected_cadence is not None and expected_cadence.total_seconds() <= 0:
        raise ValueError("expected_cadence must be positive")
    cadence_seconds = (
        int(expected_cadence.total_seconds())
        if expected_cadence is not None
        else None
    )
    non_probeable = _non_probeable_observation(
        source,
        observed_at,
        cadence_seconds,
    )
    if non_probeable is not None:
        return non_probeable
    endpoint = _endpoint(source)
    if endpoint is None:
        raise AssertionError("probeable source must have an endpoint")

    headers = {
        "Accept": "application/json, text/csv, application/xml;q=0.9, */*;q=0.1",
        "Range": f"bytes=0-{max_bytes - 1}",
        "User-Agent": "global-medicines-atlas-source-health/1",
    }
    try:
        response = _request_sample(
            endpoint,
            headers=headers,
            transport=transport,
            timeout_seconds=timeout_seconds,
            max_bytes=max_bytes,
        )
        return _evaluate_response(
            source,
            observed_at,
            endpoint,
            response,
            max_bytes,
            expected_cadence,
        )
    except (
        httpx.HTTPError,
        UnicodeError,
        ValueError,
        orjson.JSONDecodeError,
    ) as error:
        status_code = (
            error.response.status_code
            if isinstance(error, httpx.HTTPStatusError)
            else None
        )
        return SourceHealthObservation(
            source_id=source.source_id,
            checked_at=observed_at,
            state=ProbeState.UNAVAILABLE,
            endpoint=endpoint,
            status_code=status_code,
            expected_cadence_seconds=cadence_seconds,
            detail=f"{type(error).__name__}: source unavailable or unreadable",
        )


def probe_sources(
    sources: Iterable[MedicineDataSource],
    *,
    checked_at: datetime | None = None,
    transport: httpx.BaseTransport | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    expected_cadence: timedelta | None = None,
) -> tuple[SourceHealthObservation, ...]:
    """Probe sources in stable order and return metadata-only observations."""

    return tuple(
        probe_source(
            source,
            checked_at=checked_at,
            transport=transport,
            max_bytes=max_bytes,
            timeout_seconds=timeout_seconds,
            expected_cadence=expected_cadence,
        )
        for source in sorted(sources, key=lambda item: item.source_id)
    )


def compare_schema_fingerprints(
    current: Iterable[SourceHealthObservation],
    previous: dict[str, str],
) -> dict[str, str]:
    """Return source IDs whose comparable schema fingerprints changed."""

    return {
        observation.source_id: observation.schema_fingerprint
        for observation in current
        if observation.schema_fingerprint is not None
        and observation.source_id in previous
        and observation.schema_fingerprint != previous[observation.source_id]
    }


def assess_schema_drift(
    current: Iterable[SourceHealthObservation],
    previous: dict[str, str],
) -> tuple[SchemaDriftObservation, ...]:
    """Compare current metadata with a prior fingerprint baseline."""

    assessments: list[SchemaDriftObservation] = []
    for observation in sorted(current, key=lambda item: item.source_id):
        prior = previous.get(observation.source_id)
        if observation.state is ProbeState.BLOCKED:
            state = SchemaDriftState.BLOCKED
            detail = "source is blocked; schema comparison was not attempted"
        elif (
            observation.state is ProbeState.UNAVAILABLE
            or observation.schema_fingerprint is None
        ):
            state = SchemaDriftState.UNAVAILABLE
            detail = (
                "current source metadata is unavailable or not comparable; "
                "no schema-change claim made"
            )
        elif prior is None:
            state = SchemaDriftState.NO_BASELINE
            detail = "no previous fingerprint baseline exists"
        elif prior == observation.schema_fingerprint:
            state = SchemaDriftState.UNCHANGED
            detail = "current fingerprint matches the previous baseline"
        else:
            state = SchemaDriftState.CHANGED
            detail = "current fingerprint differs from the previous baseline"
        assessments.append(
            SchemaDriftObservation(
                source_id=observation.source_id,
                checked_at=observation.checked_at,
                state=state,
                current_fingerprint=observation.schema_fingerprint,
                previous_fingerprint=prior,
                detail=detail,
            )
        )
    return tuple(assessments)


def fingerprint_baseline(
    observations: Iterable[SourceHealthObservation],
) -> dict[str, str]:
    """Extract only comparable fingerprints for a future baseline."""

    return {
        observation.source_id: observation.schema_fingerprint
        for observation in observations
        if observation.schema_fingerprint is not None
    }


def observations_json(
    observations: Iterable[SourceHealthObservation],
) -> str:
    """Serialize observations without any source payload content."""

    payload = [
        observation.model_dump(mode="json") for observation in observations
    ]
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def drift_report_json(
    observations: Iterable[SourceHealthObservation],
    assessments: Iterable[SchemaDriftObservation],
) -> str:
    """Serialize a durable metadata-only health and drift report."""

    observation_items = tuple(observations)
    assessment_items = tuple(assessments)
    summary = {
        state.value: sum(item.state is state for item in assessment_items)
        for state in SchemaDriftState
    }
    payload = {
        "schema_version": 1,
        "baseline": fingerprint_baseline(observation_items),
        "observations": [
            item.model_dump(mode="json") for item in observation_items
        ],
        "schema_drift": [
            item.model_dump(mode="json") for item in assessment_items
        ],
        "summary": summary,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _failure_class(observation: SourceHealthObservation) -> str:
    if observation.state is not ProbeState.UNAVAILABLE:
        return observation.state.value
    match = re.match(r"([A-Za-z][A-Za-z0-9_]*):", observation.detail)
    return match.group(1) if match is not None else "unavailable"


def _receipt_observation(
    observation: SourceHealthObservation,
) -> SourceHealthObservation:
    """Remove variable exception text while retaining diagnostic class."""

    if observation.state is ProbeState.AVAILABLE:
        detail = "source available"
    elif observation.state is ProbeState.BLOCKED:
        detail = "source blocked"
    else:
        detail = f"{_failure_class(observation)}: source unavailable"
    return observation.model_copy(update={"detail": detail, "endpoint": None})


def build_source_health_receipt(
    observation: SourceHealthObservation,
    *,
    previous_consecutive_failures: int = 0,
    retry_history: Iterable[RetryAttempt] = (),
    previous_escalation_open: bool = False,
    escalation_threshold: int = 3,
    adapter_output_fingerprint: str | None = None,
    expected_adapter_output_fingerprint: str | None = None,
) -> SourceHealthReceipt:
    """Build a content-addressed health receipt and escalation transition."""

    if previous_consecutive_failures < 0:
        raise ValueError("previous_consecutive_failures must be non-negative")
    if escalation_threshold < 1:
        raise ValueError("escalation_threshold must be positive")
    attempts = tuple(sorted(retry_history, key=lambda item: item.attempt))
    if len({item.attempt for item in attempts}) != len(attempts):
        raise ValueError("retry attempt numbers must be unique")

    failed = observation.state is ProbeState.UNAVAILABLE
    consecutive_failures = previous_consecutive_failures + 1 if failed else 0
    if failed and consecutive_failures >= escalation_threshold:
        escalation = (
            EscalationState.DEDUPLICATED
            if previous_escalation_open
            else EscalationState.OPEN
        )
    elif not failed and previous_escalation_open:
        escalation = EscalationState.RESOLVED
    else:
        escalation = EscalationState.NONE

    parity = AdapterParityState.NOT_ASSESSED
    if (
        adapter_output_fingerprint is not None
        and expected_adapter_output_fingerprint is not None
    ):
        parity = (
            AdapterParityState.MATCHED
            if adapter_output_fingerprint == expected_adapter_output_fingerprint
            else AdapterParityState.CHANGED
        )

    safe_observation = _receipt_observation(observation)
    deduplication_key = (
        "source-health:"
        f"{observation.source_id}:"
        f"{observation.state.value}:"
        f"{observation.status_code or 'none'}:"
        f"{_failure_class(observation)}"
    )
    content = {
        "schema_version": 1,
        "observation": safe_observation.model_dump(mode="json"),
        "consecutive_failures": consecutive_failures,
        "retry_history": [item.model_dump(mode="json") for item in attempts],
        "deduplication_key": deduplication_key,
        "escalation": escalation.value,
        "adapter_output_parity": parity.value,
        "adapter_output_fingerprint": adapter_output_fingerprint,
        "expected_adapter_output_fingerprint": (
            expected_adapter_output_fingerprint
        ),
    }
    digest = sha256(
        orjson.dumps(content, option=orjson.OPT_SORT_KEYS)
    ).hexdigest()
    return SourceHealthReceipt(
        receipt_id=f"sha256:{digest}",
        observation=safe_observation,
        consecutive_failures=consecutive_failures,
        retry_history=attempts,
        deduplication_key=deduplication_key,
        escalation=escalation,
        adapter_output_parity=parity,
        adapter_output_fingerprint=adapter_output_fingerprint,
        expected_adapter_output_fingerprint=(
            expected_adapter_output_fingerprint
        ),
    )


def source_health_receipt_json(receipt: SourceHealthReceipt) -> str:
    """Serialize one deterministic, metadata-only receipt."""

    return (
        json.dumps(
            receipt.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
