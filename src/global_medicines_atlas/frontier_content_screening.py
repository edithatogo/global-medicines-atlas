"""Bounded content-pattern screening for disposable graph previews.

This module detects a small set of synthetic/direct-identifier canaries. A
clean result is not rights clearance, restricted-terminology detection, or a
claim that arbitrary content is safe to publish.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Literal, cast

from pydantic import Field

from .models import FrozenModel

_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?!\w)")
_MAX_PAYLOAD_COUNT = 100_000
_MAX_TOTAL_PAYLOAD_BYTES = 64 * 1024 * 1024
_SENSITIVE_KEY_PARTS = frozenset({
    "patient",
    "person",
    "consumer",
    "member",
    "subscriber",
    "birth",
    "dob",
    "email",
    "phone",
    "address",
    "national_id",
})
_FIELD_NAME_CARRIERS = frozenset({
    "name",
    "field_name",
    "source_field",
    # Native MBS/PBS graph field representations.
    "native_name",
    "source_field_id",
    "path",
    "schema_path",
})


class ScreenedPayload(FrozenModel):
    """One JSON payload and its non-sensitive caller-assigned identity."""

    path: str = Field(min_length=1, max_length=256)
    payload: str = Field(max_length=4 * 1024 * 1024)


class ContentScreenFinding(FrozenModel):
    """A redacted detector finding; never contains the matched value."""

    path: str = Field(min_length=1, max_length=256)
    category: Literal[
        "sensitive_field_name", "email_like_value", "known_value_digest"
    ]
    value_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ContentScreeningReceipt(FrozenModel):
    """Deterministic screening summary with explicit non-clearance status."""

    schema_id: Literal["global-medicines-atlas.frontier-content-screening"]
    schema_version: Literal[1]
    state: Literal["no_pattern_detected", "review_required"]
    payload_count: int = Field(ge=0)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    blocked_value_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    findings: tuple[ContentScreenFinding, ...]
    rights_cleared: Literal[False]
    restricted_terminology_cleared: Literal[False]


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _scan_value(
    value: object,
    *,
    path: str,
    blocked_value_sha256: frozenset[str],
    findings: list[ContentScreenFinding],
) -> None:
    if isinstance(value, dict):
        for raw_key, item in cast("dict[str, object]", value).items():
            key = raw_key.casefold().replace("-", "_").replace(" ", "_")
            key_digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
            if any(part in key.split("_") for part in _SENSITIVE_KEY_PARTS):
                findings.append(
                    ContentScreenFinding(
                        path=f"{path}.{key_digest[:12]}",
                        category="sensitive_field_name",
                        value_sha256=key_digest,
                    )
                )
            field_tokens = (
                frozenset(re.findall(r"[a-z0-9]+", item.casefold()))
                if isinstance(item, str) and key in _FIELD_NAME_CARRIERS
                else frozenset()
            )
            if field_tokens & _SENSITIVE_KEY_PARTS:
                findings.append(
                    ContentScreenFinding(
                        path=f"{path}.{key_digest[:12]}",
                        category="sensitive_field_name",
                        value_sha256=hashlib.sha256(
                            item.encode("utf-8")
                        ).hexdigest(),
                    )
                )
            _scan_value(
                item,
                path=f"{path}.{key_digest[:12]}",
                blocked_value_sha256=blocked_value_sha256,
                findings=findings,
            )
    elif isinstance(value, list):
        for index, item in enumerate(cast("list[object]", value)):
            _scan_value(
                item,
                path=f"{path}[{index}]",
                blocked_value_sha256=blocked_value_sha256,
                findings=findings,
            )
    elif isinstance(value, str):
        value_digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        if value_digest in blocked_value_sha256:
            findings.append(
                ContentScreenFinding(
                    path=path,
                    category="known_value_digest",
                    value_sha256=value_digest,
                )
            )
        if _EMAIL.search(value):
            findings.append(
                ContentScreenFinding(
                    path=path,
                    category="email_like_value",
                    value_sha256=value_digest,
                )
            )


def screen_graph_payloads(
    payloads: Iterable[ScreenedPayload],
    *,
    blocked_value_sha256: frozenset[str] = frozenset(),
) -> ContentScreeningReceipt:
    """Screen JSON graph payloads and return only value-redacted findings.

    The optional digest denylist supports exact canaries without embedding
    restricted strings in source. It is an exact-match detector, not a general
    terminology recognizer. Invalid JSON and scalar JSON fail closed.
    """
    if any(
        not re.fullmatch(r"[0-9a-f]{64}", item) for item in blocked_value_sha256
    ):
        raise ValueError("blocked value digests must be lowercase SHA-256")
    bounded: list[ScreenedPayload] = []
    byte_count = 0
    for item in payloads:
        if len(bounded) >= _MAX_PAYLOAD_COUNT:
            raise ValueError("screening payload count bound exceeded")
        byte_count += len(item.payload.encode("utf-8"))
        if byte_count > _MAX_TOTAL_PAYLOAD_BYTES:
            raise ValueError("screening payload byte bound exceeded")
        bounded.append(item)
    if not bounded:
        raise ValueError("screening requires at least one payload")
    ordered = tuple(sorted(bounded, key=lambda item: item.path))
    if len({item.path for item in ordered}) != len(ordered):
        raise ValueError("screening payload paths must be unique")
    findings: list[ContentScreenFinding] = []
    digest_input: list[dict[str, str]] = []
    for item in ordered:
        try:
            decoded = json.loads(
                item.payload,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=lambda _value: (_ for _ in ()).throw(
                    ValueError("non-finite JSON number")
                ),
            )
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("invalid screening payload JSON") from error
        if not isinstance(decoded, dict | list):
            raise TypeError("screening payload must be a JSON object or array")
        _scan_value(
            cast("object", decoded),
            path=item.path,
            blocked_value_sha256=blocked_value_sha256,
            findings=findings,
        )
        digest_input.append({
            "path": item.path,
            "payload_sha256": hashlib.sha256(
                item.payload.encode("utf-8")
            ).hexdigest(),
        })
    stable_findings = tuple(
        sorted(
            set(findings),
            key=lambda item: (item.path, item.category, item.value_sha256),
        )
    )
    return ContentScreeningReceipt(
        schema_id="global-medicines-atlas.frontier-content-screening",
        schema_version=1,
        state="review_required" if stable_findings else "no_pattern_detected",
        payload_count=len(ordered),
        payload_sha256=hashlib.sha256(
            _canonical_bytes(digest_input)
        ).hexdigest(),
        blocked_value_set_sha256=hashlib.sha256(
            _canonical_bytes(sorted(blocked_value_sha256))
        ).hexdigest(),
        findings=stable_findings,
        rights_cleared=False,
        restricted_terminology_cleared=False,
    )
