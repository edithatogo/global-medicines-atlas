"""Contract tests for bounded durable Platinum receipt storage."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from global_medicines_atlas import platinum_receipts
from global_medicines_atlas.platinum_query import QueryReceipt, QueryUnavailable
from global_medicines_atlas.platinum_receipts import (
    DurableReceiptStore,
    ReceiptStoreError,
)
from global_medicines_atlas.platinum_resolver import CacheReceipt

NOW = datetime(2026, 9, 2, tzinfo=UTC)


def query_receipt(*, resource_id: str = "au.mbs.service-items") -> QueryReceipt:
    """Return one synthetic receipt without source or result payload bytes."""
    canonical_query = b'{"columns":["item_code"],"version":"1.0"}'
    return QueryReceipt(
        resource_id=resource_id,
        engine="duckdb",
        canonical_query=canonical_query,
        query_sha256=hashlib.sha256(canonical_query).hexdigest(),
        result_sha256="1" * 64,
        row_count=1,
        object_sha256="2" * 64,
        contract_sha256="3" * 64,
        semantic_manifest_sha256="4" * 64,
        cache_receipt_sha256="5" * 64,
    )


def cache_receipt(*, resource_id: str = "au.mbs.service-items") -> CacheReceipt:
    """Return one synthetic bounded cache observation."""
    return CacheReceipt(
        resource_id=resource_id,
        contract_sha256="3" * 64,
        object_sha256="2" * 64,
        byte_count=512,
        status="verified_exact_digest",
        last_origin="remote",
        last_verified_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        max_read_bytes=1024,
        cache_budget_bytes=1024,
        max_cache_entries=2,
        max_open_reads=1,
        timeout_seconds=5,
    )


def test_atomic_content_addressed_write_and_exact_readback(tmp_path) -> None:
    receipt = query_receipt()
    store = DurableReceiptStore(
        tmp_path, clock=lambda: NOW, max_bytes=4096, max_entries=2
    )
    stored = store.persist(receipt, expires_at=NOW + timedelta(hours=1))

    assert stored.receipt_sha256 == receipt.receipt_sha256
    assert (
        stored.envelope_sha256
        == hashlib.sha256(stored.path.read_bytes()).hexdigest()
    )
    assert stored.path.name == f"{stored.envelope_sha256}.json"
    assert store.read(stored.envelope_sha256) == receipt.canonical_bytes
    reopened = DurableReceiptStore(
        tmp_path, clock=lambda: NOW, max_bytes=4096, max_entries=2
    )
    assert reopened.read(stored.envelope_sha256) == receipt.canonical_bytes
    assert b"source-payload-sentinel" not in stored.path.read_bytes()
    assert not tuple(tmp_path.rglob("*.tmp"))


def test_tamper_and_expiry_fail_closed(tmp_path) -> None:
    current = NOW
    store = DurableReceiptStore(
        tmp_path, clock=lambda: current, max_bytes=4096, max_entries=2
    )
    stored = store.persist(
        cache_receipt(), expires_at=NOW + timedelta(minutes=1)
    )
    stored.path.write_bytes(stored.path.read_bytes() + b" ")
    with pytest.raises(ReceiptStoreError, match="digest mismatch"):
        store.read(stored.envelope_sha256)

    stored = store.persist(
        cache_receipt(), expires_at=NOW + timedelta(minutes=1)
    )
    current = NOW + timedelta(minutes=2)
    with pytest.raises(ReceiptStoreError, match="expired"):
        store.read(stored.envelope_sha256)
    assert not stored.path.exists()


def test_entry_budget_evicts_oldest_verified_envelope(tmp_path) -> None:
    current = NOW
    store = DurableReceiptStore(
        tmp_path, clock=lambda: current, max_bytes=4096, max_entries=1
    )
    first = store.persist(
        query_receipt(resource_id="au.mbs.first"),
        expires_at=NOW + timedelta(hours=1),
    )
    current += timedelta(seconds=1)
    second_receipt = query_receipt(resource_id="au.mbs.second")
    second = store.persist(second_receipt, expires_at=NOW + timedelta(hours=1))

    with pytest.raises(ReceiptStoreError, match="unavailable"):
        store.read(first.envelope_sha256)
    assert store.read(second.envelope_sha256) == second_receipt.canonical_bytes
    assert store.evict(second.envelope_sha256)
    assert not store.evict(second.envelope_sha256)


def test_expired_entries_are_removed_during_next_atomic_write(tmp_path) -> None:
    current = NOW
    store = DurableReceiptStore(
        tmp_path, clock=lambda: current, max_bytes=4096, max_entries=2
    )
    expired = store.persist(
        query_receipt(), expires_at=NOW + timedelta(seconds=1)
    )
    current += timedelta(seconds=2)
    store.persist(cache_receipt(), expires_at=NOW + timedelta(hours=1))
    assert not expired.path.exists()


def test_unavailable_query_receipt_is_supported_but_payloads_are_not(
    tmp_path,
) -> None:
    canonical_query = b'{"columns":["item_code"],"version":"1.0"}'
    receipt = QueryUnavailable(
        status="unavailable",
        reason="unknown_resource",
        resource_id="au.unknown.resource",
        engine="duckdb",
        canonical_query=canonical_query,
        query_sha256=hashlib.sha256(canonical_query).hexdigest(),
        evidence=None,
        cache_receipt=None,
    )
    store = DurableReceiptStore(
        tmp_path, clock=lambda: NOW, max_bytes=4096, max_entries=2
    )
    stored = store.persist(receipt, expires_at=NOW + timedelta(hours=1))
    assert stored.kind == "query_unavailable"
    with pytest.raises(TypeError, match="unsupported"):
        store.persist(  # type: ignore[arg-type]
            b"source-payload-sentinel",
            expires_at=NOW + timedelta(hours=1),
        )


def test_interrupted_replace_preserves_existing_receipt(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = DurableReceiptStore(
        tmp_path, clock=lambda: NOW, max_bytes=4096, max_entries=2
    )
    first = store.persist(query_receipt(), expires_at=NOW + timedelta(hours=1))

    def interrupt(*_args: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(Path, "replace", interrupt)
    with pytest.raises(KeyboardInterrupt):
        store.persist(cache_receipt(), expires_at=NOW + timedelta(hours=1))
    assert store.read(first.envelope_sha256) == query_receipt().canonical_bytes
    assert not tuple(tmp_path.rglob("*.tmp"))


@pytest.mark.parametrize(
    ("max_bytes", "max_entries"),
    [(0, 1), (4096, 0), (True, 1), (4096, True)],
)
def test_store_budgets_are_strict(tmp_path, max_bytes, max_entries) -> None:
    with pytest.raises(ValueError, match="budget"):
        DurableReceiptStore(
            tmp_path,
            clock=lambda: NOW,
            max_bytes=max_bytes,
            max_entries=max_entries,
        )


def _write_envelope(tmp_path: Path, document: object) -> str:
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).hexdigest()
    path = tmp_path / "sha256" / digest[:2] / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return digest


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda item: item.update(extra=True), "claims"),
        (lambda item: item.update(kind="source_payload"), "kind"),
        (lambda item: item.update(version="2.0"), "claims"),
        (lambda item: item.update(receipt=[]), "claims"),
        (lambda item: item.update(receipt_sha256="0" * 64), "receipt digest"),
        (
            lambda item: item.update(receipt_sha256="bad"),
            "invalid receipt digest",
        ),
        (lambda item: item.update(stored_at=3), "stored_at"),
        (lambda item: item.update(stored_at="not-a-time"), "stored_at"),
        (lambda item: item.update(expires_at="2026-09-03"), "timezone-aware"),
    ],
)
def test_malformed_envelope_claims_fail_closed(
    tmp_path, change, message
) -> None:
    store = DurableReceiptStore(
        tmp_path, clock=lambda: NOW, max_bytes=4096, max_entries=2
    )
    stored = store.persist(query_receipt(), expires_at=NOW + timedelta(hours=1))
    document = json.loads(stored.path.read_bytes())
    change(document)
    digest = _write_envelope(tmp_path, document)
    with pytest.raises((ReceiptStoreError, ValueError), match=message):
        store.read(digest)


def test_invalid_envelope_shapes_and_addresses_fail_closed(tmp_path) -> None:
    store = DurableReceiptStore(
        tmp_path, clock=lambda: NOW, max_bytes=4096, max_entries=2
    )
    array_digest = _write_envelope(tmp_path, [])
    with pytest.raises(ReceiptStoreError, match="claims"):
        store.read(array_digest)
    with pytest.raises(ReceiptStoreError, match="invalid receipt digest"):
        store.read("../not-a-digest")

    duplicate = b'{"kind":"cache","kind":"query"}'
    duplicate_digest = hashlib.sha256(duplicate).hexdigest()
    duplicate_path = (
        tmp_path / "sha256" / duplicate_digest[:2] / f"{duplicate_digest}.json"
    )
    duplicate_path.parent.mkdir(parents=True, exist_ok=True)
    duplicate_path.write_bytes(duplicate)
    with pytest.raises(ReceiptStoreError, match="JSON"):
        store.read(duplicate_digest)


def test_expiry_and_store_byte_budgets_reject_before_persistence(
    tmp_path,
) -> None:
    store = DurableReceiptStore(
        tmp_path, clock=lambda: NOW, max_bytes=100, max_entries=1
    )
    with pytest.raises(ReceiptStoreError, match="already expired"):
        store.persist(query_receipt(), expires_at=NOW)
    with pytest.raises(ReceiptStoreError, match="store byte budget"):
        store.persist(query_receipt(), expires_at=NOW + timedelta(hours=1))
    with pytest.raises(ValueError, match="timezone-aware"):
        store.persist(query_receipt(), expires_at=NOW.replace(tzinfo=None))


@pytest.mark.parametrize(
    ("canonical", "digest", "message"),
    [
        (b"not-json", None, "canonical JSON is invalid"),
        (b"[]", None, "must be an object"),
        (b'{"valid":true}', "0" * 64, "receipt digest mismatch"),
        (
            b'{"oversized":"' + b"x" * (64 * 1024) + b'"}',
            None,
            "metadata budget",
        ),
    ],
)
def test_forged_receipt_metadata_is_rejected(
    tmp_path, monkeypatch, canonical, digest, message
) -> None:
    expected = digest or hashlib.sha256(canonical).hexdigest()
    monkeypatch.setattr(
        QueryReceipt, "canonical_bytes", property(lambda _self: canonical)
    )
    monkeypatch.setattr(
        QueryReceipt, "receipt_sha256", property(lambda _self: expected)
    )
    store = DurableReceiptStore(
        tmp_path, clock=lambda: NOW, max_bytes=128 * 1024, max_entries=2
    )
    with pytest.raises(ReceiptStoreError, match=message):
        store.persist(query_receipt(), expires_at=NOW + timedelta(hours=1))


def test_disappearing_and_oversized_envelopes_fail_closed(
    tmp_path, monkeypatch
) -> None:
    store = DurableReceiptStore(
        tmp_path, clock=lambda: NOW, max_bytes=4096, max_entries=2
    )
    stored = store.persist(query_receipt(), expires_at=NOW + timedelta(hours=1))

    def disappear(_path: Path) -> bytes:
        raise FileNotFoundError

    monkeypatch.setattr(Path, "read_bytes", disappear)
    with pytest.raises(ReceiptStoreError, match="unavailable"):
        store._load(stored.path, stored.envelope_sha256)
    monkeypatch.undo()

    tiny = DurableReceiptStore(
        tmp_path / "tiny", clock=lambda: NOW, max_bytes=100, max_entries=1
    )
    raw = b"x" * 101
    digest = hashlib.sha256(raw).hexdigest()
    path = tiny._path(digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    with pytest.raises(ReceiptStoreError, match="store byte budget"):
        tiny.read(digest)


def test_failed_budget_enforcement_removes_new_envelope(tmp_path) -> None:
    store = DurableReceiptStore(
        tmp_path, clock=lambda: NOW, max_bytes=4096, max_entries=1
    )
    store._max_entries = 0
    with pytest.raises(ReceiptStoreError, match="cannot retain"):
        store.persist(query_receipt(), expires_at=NOW + timedelta(hours=1))
    assert not tuple(tmp_path.rglob("*.json"))


def test_directory_sync_is_best_effort_on_unsupported_hosts(
    tmp_path, monkeypatch
) -> None:
    def unsupported(*_args: object) -> int:
        raise OSError("directory handles unavailable")

    monkeypatch.setattr(platinum_receipts.os, "open", unsupported)
    platinum_receipts._sync_directory(tmp_path)
