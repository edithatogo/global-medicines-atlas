"""Check supplied v4 receipt bytes, not authority, claims or reader admission.

No URLs are fetched and opaque receipt bodies are never parsed or retained in
the result. The caller must authenticate provenance and validate receipt claims
separately; a complete matching inventory is not a qualification or permission.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any, Literal, Self, cast

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from pydantic import ConfigDict, Field, model_validator

from .federation import validate_federation_semantics
from .federation_reader import METADATA_BYTES, SCHEMA_SHA256
from .models import FrozenModel

MAX_REFERENCES = 256
MAX_RECEIPT_BYTES = METADATA_BYTES
MAX_TOTAL_BYTES = 8 * METADATA_BYTES
MAX_STRUCTURE_NODES = 8192
MAX_STRUCTURE_DEPTH = 32
Digest = Annotated[
    str, Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)
]
Url = Annotated[str, Field(strict=True, min_length=1, max_length=2048)]


class _Model(FrozenModel):
    model_config = ConfigDict(
        revalidate_instances="always", hide_input_in_errors=True
    )


class ReceiptPayload(_Model):
    """Caller-supplied opaque bytes, not an authenticated remote observation."""

    url: Url
    payload: bytes = Field(
        strict=True, max_length=MAX_RECEIPT_BYTES, repr=False
    )


class ReceiptRole(_Model):
    """One contract JSON-pointer role bound to its referenced byte identity."""

    role: str = Field(min_length=1, max_length=256)
    url: Url
    sha256: Digest


class VerifiedReceipt(_Model):
    """Byte-digest observation only; does not validate receipt content claims."""

    url: Url
    sha256: Digest
    byte_count: int = Field(strict=True, ge=0, le=MAX_RECEIPT_BYTES)


class ReceiptClosure(_Model):
    """Immutable byte inventory; constructing metadata cannot confer authority."""

    scope: Literal["receipt_bytes_only"] = "receipt_bytes_only"
    contract_sha256: Digest
    roles: tuple[ReceiptRole, ...] = Field(
        min_length=1, max_length=MAX_REFERENCES
    )
    receipts: tuple[VerifiedReceipt, ...] = Field(
        min_length=1, max_length=MAX_REFERENCES
    )

    @model_validator(mode="after")
    def consistent_inventory(self) -> Self:
        by_url = {item.url: item for item in self.receipts}
        if len(by_url) != len(self.receipts) or len({
            item.role for item in self.roles
        }) != len(self.roles):
            raise ValueError("duplicate receipt inventory identity")
        if {item.url for item in self.roles} != by_url.keys() or any(
            by_url[item.url].sha256 != item.sha256 for item in self.roles
        ):
            raise ValueError("receipt role inventory mismatch")
        if sum(item.byte_count for item in self.receipts) > MAX_TOTAL_BYTES:
            raise ValueError("receipt aggregate byte limit exceeded")
        return self


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate contract JSON key")
        result[key] = value
    return result


def _preflight(document: object) -> None:
    """Bound untrusted structure before schema uniqueness comparisons.

    Count reference-shaped objects even when malformed; full schema validation
    follows this rejection-only pass. Never parse URLs or emit document values.
    """
    pending: list[tuple[object, int]] = [(document, 0)]
    nodes = references = 0
    while pending:
        value, depth = pending.pop()
        nodes += 1
        if nodes > MAX_STRUCTURE_NODES or depth > MAX_STRUCTURE_DEPTH:
            raise ValueError("contract structural node/depth limit exceeded")
        if isinstance(value, dict):
            node = cast("dict[str, object]", value)
            if len(node) > MAX_REFERENCES:
                raise ValueError("contract container count limit exceeded")
            if "url" in node and "sha256" in node:
                references += 1
                if references > MAX_REFERENCES:
                    raise ValueError("receipt reference count limit exceeded")
            pending.extend((child, depth + 1) for child in node.values())
        elif isinstance(value, list):
            items = cast("list[object]", value)
            if len(items) > MAX_REFERENCES:
                raise ValueError(
                    "receipt reference/container count limit exceeded"
                )
            pending.extend((child, depth + 1) for child in items)


def _document(raw: bytes, schema: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or len(raw) > METADATA_BYTES:
        raise ValueError("contract byte limit or type rejected")
    if (
        type(schema) is not bytes
        or len(schema) > METADATA_BYTES
        or hashlib.sha256(schema).hexdigest() != SCHEMA_SHA256
    ):
        raise ValueError("federation schema digest mismatch")
    formats = FormatChecker()
    if not {"date", "date-time", "uri"} <= formats.checkers.keys():
        raise ValueError("required federation format validators are missing")
    try:
        document: dict[str, Any] = json.loads(
            raw, object_pairs_hook=_unique_object
        )
    except ValueError, TypeError, RecursionError:
        raise ValueError("invalid federation contract") from None
    _preflight(document)
    try:
        validator = cast(
            "Any",
            Draft202012Validator(json.loads(schema), format_checker=formats),
        )
        validator.validate(document)
        validate_federation_semantics(document)
    except ValueError, TypeError, KeyError, RecursionError, ValidationError:
        raise ValueError("invalid federation contract") from None
    if document["authority"]["schema_sha256"] != SCHEMA_SHA256:
        raise ValueError("invalid federation contract schema pin")
    return document


def _roles(document: dict[str, Any]) -> tuple[ReceiptRole, ...]:
    output: list[ReceiptRole] = []
    by_url: dict[str, str] = {}

    def walk(value: object, path: str) -> None:
        if isinstance(value, dict):
            node = cast("dict[str, Any]", value)
            if set(node) == {"url", "sha256"}:
                if len(output) >= MAX_REFERENCES:
                    raise ValueError("receipt reference count limit exceeded")
                role = ReceiptRole(
                    role=path, url=node["url"], sha256=node["sha256"]
                )
                if role.url in by_url and by_url[role.url] != role.sha256:
                    raise ValueError("conflicting receipt digests at one URL")
                by_url[role.url] = role.sha256
                output.append(role)
            else:
                for key, child in node.items():
                    walk(child, f"{path}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(cast("list[Any]", value)):
                walk(child, f"{path}/{index}")

    walk(document, "")
    return tuple(sorted(output, key=lambda item: item.role))


def _payloads(receipts: object) -> tuple[ReceiptPayload, ...]:
    if not isinstance(receipts, (tuple, list)):
        raise TypeError("receipt payload count container rejected")
    items = cast("tuple[object, ...] | list[object]", receipts)
    if len(items) > MAX_REFERENCES:
        raise ValueError("receipt payload count limit exceeded")
    # Bound all inputs before JSON/schema work or hashing any opaque payload.
    size = 0
    supplied: list[ReceiptPayload] = []
    for item in items:
        if (
            not isinstance(item, ReceiptPayload)
            or type(item.payload) is not bytes
            or len(item.payload) > MAX_RECEIPT_BYTES
        ):
            raise ValueError("receipt byte limit or type rejected")
        size += len(item.payload)
        if size > MAX_TOTAL_BYTES:
            raise ValueError("receipt aggregate byte limit exceeded")
        supplied.append(item)
    try:
        return tuple(ReceiptPayload.model_validate(item) for item in supplied)
    except ValueError:
        raise ValueError("invalid receipt payload metadata") from None


def verify_receipt_closure(
    contract: bytes,
    receipts: tuple[ReceiptPayload, ...],
    *,
    schema: bytes,
) -> ReceiptClosure:
    """Require exact opaque bytes for every nested v4 receipt reference.

    One URL/digest may serve multiple roles, but a URL cannot have conflicting
    digests within this single closure. Supply each URL once, including distinct
    URLs sharing a digest. No recursive receipt resolution, admission allowlist,
    provenance authentication, rights decision or publication is performed.
    """
    supplied = _payloads(receipts)
    roles = _roles(_document(contract, schema))
    expected = {item.url: item.sha256 for item in roles}
    by_url = {item.url: item for item in supplied}
    if len(by_url) != len(supplied):
        raise ValueError("duplicate supplied receipt URL")
    if by_url.keys() != expected.keys():
        raise ValueError("missing or extra supplied receipt")
    verified: list[VerifiedReceipt] = []
    for url in sorted(by_url):
        payload = by_url[url].payload
        digest = hashlib.sha256(payload).hexdigest()
        if digest != expected[url]:
            raise ValueError("receipt byte digest mismatch")
        verified.append(
            VerifiedReceipt(url=url, sha256=digest, byte_count=len(payload))
        )
    return ReceiptClosure(
        contract_sha256=hashlib.sha256(contract).hexdigest(),
        roles=roles,
        receipts=tuple(verified),
    )


def contract_receipt_roles(
    contract: bytes, *, schema: bytes
) -> tuple[ReceiptRole, ...]:
    """Revalidate contract bytes and return their exact referenced roles."""
    return _roles(_document(contract, schema))
