"""Bounded durable storage for content-addressed Platinum receipts only.

The store accepts the canonical cache and query receipt types, never query
rows or source payload streams. Each immutable envelope is written to a
temporary sibling, flushed, atomically replaced, and verified on every read.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from .platinum_query import QueryReceipt, QueryUnavailable
from .platinum_resolver import CacheReceipt

ReceiptKind = Literal["cache", "query", "query_unavailable"]
PersistableReceipt = CacheReceipt | QueryReceipt | QueryUnavailable
_DIGEST_LENGTH = 64
_MAX_RECEIPT_BYTES = 64 * 1024


class ReceiptStoreError(ValueError):
    """Raised when durable receipt evidence is unavailable or invalid."""


@dataclass(frozen=True)
class StoredReceipt:
    """Identity and bounded local location of one durable receipt envelope."""

    envelope_sha256: str
    receipt_sha256: str
    kind: ReceiptKind
    stored_at: datetime
    expires_at: datetime
    byte_count: int
    path: Path


@dataclass(frozen=True)
class _VerifiedEnvelope:
    stored: StoredReceipt
    canonical_receipt: bytes


class DurableReceiptStore:
    """Persist only bounded canonical receipt metadata under a local root."""

    def __init__(
        self,
        root: Path,
        *,
        max_bytes: int,
        max_entries: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if (
            type(max_bytes) is not int
            or max_bytes < 1
            or type(max_entries) is not int
            or max_entries < 1
        ):
            raise ValueError("receipt store budget is invalid")
        self._root = root
        self._max_bytes = max_bytes
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.RLock()

    def persist(
        self, receipt: PersistableReceipt, *, expires_at: datetime
    ) -> StoredReceipt:
        """Atomically persist a verified, bounded receipt-only envelope."""
        with self._lock:
            return self._persist(receipt, expires_at=expires_at)

    def _persist(
        self, receipt: PersistableReceipt, *, expires_at: datetime
    ) -> StoredReceipt:
        now = _aware(self._clock(), "store clock")
        expiry = _aware(expires_at, "receipt expiry")
        if expiry <= now:
            raise ReceiptStoreError("receipt is already expired")
        kind = _kind(receipt)
        canonical_receipt = receipt.canonical_bytes
        if len(canonical_receipt) > _MAX_RECEIPT_BYTES:
            raise ReceiptStoreError("receipt exceeds metadata budget")
        if (
            hashlib.sha256(canonical_receipt).hexdigest()
            != receipt.receipt_sha256
        ):
            raise ReceiptStoreError("receipt digest mismatch")
        try:
            receipt_document: object = json.loads(canonical_receipt)
        except json.JSONDecodeError:
            raise ReceiptStoreError(
                "receipt canonical JSON is invalid"
            ) from None
        if not isinstance(receipt_document, dict):
            raise ReceiptStoreError("receipt canonical JSON must be an object")
        receipt_document = cast("dict[str, object]", receipt_document)
        document: dict[str, object] = {
            "expires_at": expiry.isoformat(),
            "kind": kind,
            "receipt": receipt_document,
            "receipt_sha256": receipt.receipt_sha256,
            "stored_at": now.isoformat(),
            "version": "1.0",
        }
        envelope = _canonical(document)
        if len(envelope) > self._max_bytes:
            raise ReceiptStoreError("receipt exceeds store byte budget")
        envelope_sha256 = hashlib.sha256(envelope).hexdigest()
        path = self._path(envelope_sha256)
        _atomic_write(path, envelope)
        stored = self._load(path, envelope_sha256).stored
        try:
            self._enforce_budgets(protected=envelope_sha256)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return stored

    def read(self, envelope_sha256: str) -> bytes:
        """Return exact canonical receipt bytes after digest and expiry checks."""
        with self._lock:
            return self._read(envelope_sha256)

    def _read(self, envelope_sha256: str) -> bytes:
        path = self._path(_digest(envelope_sha256))
        if not path.is_file():
            raise ReceiptStoreError("receipt is unavailable")
        verified = self._load(path, envelope_sha256)
        if verified.stored.expires_at <= _aware(self._clock(), "store clock"):
            path.unlink(missing_ok=True)
            raise ReceiptStoreError("receipt is expired")
        return verified.canonical_receipt

    def evict(self, envelope_sha256: str) -> bool:
        """Remove one exact durable receipt envelope, if present."""
        with self._lock:
            return self._evict(envelope_sha256)

    def _evict(self, envelope_sha256: str) -> bool:
        path = self._path(_digest(envelope_sha256))
        if not path.exists():
            return False
        path.unlink()
        return True

    def _path(self, envelope_sha256: str) -> Path:
        return (
            self._root
            / "sha256"
            / envelope_sha256[:2]
            / f"{envelope_sha256}.json"
        )

    def _load(self, path: Path, expected_digest: str) -> _VerifiedEnvelope:
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            raise ReceiptStoreError("receipt is unavailable") from None
        if len(raw) > self._max_bytes:
            raise ReceiptStoreError("receipt exceeds store byte budget")
        if hashlib.sha256(raw).hexdigest() != expected_digest:
            raise ReceiptStoreError("receipt envelope digest mismatch")
        try:
            untyped: object = json.loads(raw, object_pairs_hook=_unique_object)
        except json.JSONDecodeError, ValueError:
            raise ReceiptStoreError(
                "receipt envelope JSON is invalid"
            ) from None
        if not isinstance(untyped, dict):
            raise ReceiptStoreError("receipt envelope claims are invalid")
        document = cast("dict[str, object]", untyped)
        if set(document) != {
            "expires_at",
            "kind",
            "receipt",
            "receipt_sha256",
            "stored_at",
            "version",
        }:
            raise ReceiptStoreError("receipt envelope claims are invalid")
        raw_kind = document["kind"]
        if raw_kind not in {"cache", "query", "query_unavailable"}:
            raise ReceiptStoreError("receipt envelope kind is invalid")
        kind = cast("ReceiptKind", raw_kind)
        if document["version"] != "1.0" or not isinstance(
            document["receipt"], dict
        ):
            raise ReceiptStoreError("receipt envelope claims are invalid")
        canonical_receipt = _canonical(
            cast("dict[str, object]", document["receipt"])
        )
        receipt_sha256 = _digest(document["receipt_sha256"])
        if hashlib.sha256(canonical_receipt).hexdigest() != receipt_sha256:
            raise ReceiptStoreError("receipt digest mismatch")
        stored_at = _timestamp(document["stored_at"], "stored_at")
        expires_at = _timestamp(document["expires_at"], "expires_at")
        return _VerifiedEnvelope(
            stored=StoredReceipt(
                envelope_sha256=expected_digest,
                receipt_sha256=receipt_sha256,
                kind=kind,
                stored_at=stored_at,
                expires_at=expires_at,
                byte_count=len(raw),
                path=path,
            ),
            canonical_receipt=canonical_receipt,
        )

    def _enforce_budgets(self, *, protected: str) -> None:
        now = _aware(self._clock(), "store clock")
        entries: list[StoredReceipt] = []
        for path in self._root.glob("sha256/*/*.json"):
            expected = path.stem
            verified = self._load(path, _digest(expected)).stored
            if verified.expires_at <= now:
                path.unlink(missing_ok=True)
            else:
                entries.append(verified)
        entries.sort(key=lambda item: (item.stored_at, item.envelope_sha256))
        total = sum(item.byte_count for item in entries)
        while len(entries) > self._max_entries or total > self._max_bytes:
            candidates = [
                item for item in entries if item.envelope_sha256 != protected
            ]
            if not candidates:
                raise ReceiptStoreError(
                    "receipt store budget cannot retain entry"
                )
            evicted = candidates[0]
            evicted.path.unlink(missing_ok=True)
            entries.remove(evicted)
            total -= evicted.byte_count


def _kind(receipt: PersistableReceipt) -> ReceiptKind:
    if type(receipt) is CacheReceipt:
        return "cache"
    if type(receipt) is QueryReceipt:
        return "query"
    if type(receipt) is QueryUnavailable:
        return "query_unavailable"
    raise TypeError("unsupported durable receipt type")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
        temporary = None
        _sync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _canonical(document: object) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _sync_directory(path: Path) -> None:
    """Best-effort directory sync where the host permits directory handles."""
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _digest(value: object) -> str:
    if (
        type(value) is not str
        or len(value) != _DIGEST_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReceiptStoreError("invalid receipt digest")
    return value


def _timestamp(value: object, field: str) -> datetime:
    if type(value) is not str:
        raise ReceiptStoreError(f"receipt {field} is invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ReceiptStoreError(f"receipt {field} is invalid") from None
    return _aware(parsed, field)


def _aware(value: object, field: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate receipt envelope key")
    return result
