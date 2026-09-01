"""Synthetic Platinum resolution/read tests; no live data or publication."""

from __future__ import annotations

import hashlib
import io
import json
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from global_medicines_atlas.federation_distribution import (
    DistributionBinding,
    ProducedObject,
    reconcile_distribution,
)
from global_medicines_atlas.federation_reader import VerifiedRead
from global_medicines_atlas.platinum_resolver import (
    CacheReceipt,
    ProductResource,
    StorageNeutralResolver,
)

ROOT = Path(__file__).resolve().parents[1] / "contracts/medallion/v4"
SCHEMA = (ROOT / "federation.schema.json").read_bytes()
PAYLOAD = b"synthetic product rows"
NOW = datetime(2026, 9, 1, tzinfo=UTC)


class Hub:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status = 200
        self.payload = PAYLOAD

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert "authorization" not in request.headers
        if "/api/datasets/" in request.url.path:
            return httpx.Response(
                self.status,
                json={"sha": "a" * 40, "private": False, "gated": False},
            )
        return httpx.Response(self.status, content=self.payload)


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def contract(**changes: Any) -> bytes:
    document = json.loads((ROOT / "fixtures/valid.json").read_bytes())
    digest = hashlib.sha256(PAYLOAD).hexdigest()
    document["source"].update(
        layer="platinum", bronze_stratum=None, representation="projection"
    )
    document["recovery"]["role"] = "primary"
    document["lineage"]["inputs"] = [document["verification"]["receipt"]]
    document["lineage"]["promotion_receipt"] = document["verification"][
        "receipt"
    ]
    for group in ("location", "verification"):
        document[group].update(bytes=len(PAYLOAD), sha256=digest)
    document["rights"]["subject_sha256"] = digest
    document["cache"]["offline_behavior"] = "verified_exact_digest_only"
    document["cache"]["expires_at"] = "2026-09-02T00:00:00Z"
    for group, fields in changes.items():
        document[group].update(fields)
    return json.dumps(document).encode()


def binding(raw: bytes) -> DistributionBinding:
    document = json.loads(raw)
    obj = ProducedObject(
        producer_repository=document["authority"]["producer_repository"],
        source_id=document["source"]["source_id"],
        acquisition_id=document["source"]["acquisition_id"],
        layer=document["source"]["layer"],
        bronze_stratum=document["source"]["bronze_stratum"],
        path=document["location"]["path"],
        sha256=document["location"]["sha256"],
        byte_count=document["location"]["bytes"],
        evidence_kind=document["evidence_kind"],
    )
    return reconcile_distribution(
        [obj],
        [raw],
        schema=SCHEMA,
        destinations={"platinum": document["location"]["dataset"]},
    )[0]


def semantic_manifest(
    contract_sha256: str,
    *,
    resource_id: str = "au.mbs.service-items",
    dimension: str = "service_benefit",
    granularity: str = "service_item",
) -> bytes:
    return json.dumps(
        {
            "contract_sha256": contract_sha256,
            "entity_granularity": granularity,
            "resource_id": resource_id,
            "semantic_dimension": dimension,
            "version": "1.0",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def resource(raw: bytes | None = None) -> ProductResource:
    raw = contract() if raw is None else raw
    distribution = binding(raw)
    return ProductResource(
        resource_id="au.mbs.service-items",
        semantic_dimension="service_benefit",
        entity_granularity="service_item",
        binding=distribution,
        contract=raw,
        semantic_manifest=semantic_manifest(distribution.contract_sha256),
    )


def resolver(
    hub: Hub,
    *resources: ProductResource,
    admitted: frozenset[str] | None = None,
    admitted_semantics: frozenset[str] | None = None,
    **options: Any,
) -> StorageNeutralResolver:
    selected = resources or (resource(),)
    clock = options.pop("clock", lambda: NOW)
    return StorageNeutralResolver(
        schema=SCHEMA,
        resources=selected,
        admitted_contracts=admitted
        if admitted is not None
        else frozenset(item.binding.contract_sha256 for item in selected),
        admitted_semantic_manifests=admitted_semantics
        if admitted_semantics is not None
        else frozenset(
            hashlib.sha256(item.semantic_manifest).hexdigest()
            for item in selected
        ),
        transport_factory=lambda: httpx.MockTransport(hub.handle),
        clock=clock,
        **options,
    )


def test_resolve_is_storage_neutral_and_exact() -> None:
    hub = Hub()
    with resolver(hub) as client:
        result = client.resolve("au.mbs.service-items")
        assert result.dataset == "example/synthetic-mbs"
        assert result.revision == "a" * 40
        assert result.path == "raw/synthetic.xml"
        assert result.sha256 == hashlib.sha256(PAYLOAD).hexdigest()
        assert result.byte_count == len(PAYLOAD)
        assert result.semantic_dimension == "service_benefit"
        assert result.entity_granularity == "service_item"
        assert result.capabilities == (
            "exact_v4_resolution",
            "anonymous_verified_read",
            "verified_cache_offline",
        )
    assert not hub.requests


def test_remote_read_and_explicit_offline_cache_roundtrip() -> None:
    hub = Hub()
    with resolver(hub) as client:
        with client.open("au.mbs.service-items") as result:
            assert result.metadata == client.resolve("au.mbs.service-items")
            assert result.verified.origin == "remote"
            assert result.verified.stream.read() == PAYLOAD
            assert result.cache_receipt == CacheReceipt(
                resource_id="au.mbs.service-items",
                contract_sha256=result.metadata.contract_sha256,
                object_sha256=result.metadata.sha256,
                byte_count=len(PAYLOAD),
                status="verified_exact_digest",
                last_origin="remote",
                last_verified_at=NOW,
                expires_at=datetime(2026, 9, 2, tzinfo=UTC),
                max_read_bytes=64 * 1024 * 1024,
                cache_budget_bytes=64 * 1024 * 1024,
                max_cache_entries=32,
                max_open_reads=2,
                timeout_seconds=30,
            )
        assert len(hub.requests) == 2
        with client.open("au.mbs.service-items", offline=True) as result:
            assert result.verified.origin == "verified_cache"
            assert result.verified.stream.read() == PAYLOAD
        assert len(hub.requests) == 2
        client.evict()
        receipt = client.cache_receipt("au.mbs.service-items")
        assert receipt.status == "unavailable"
        assert receipt.last_origin == "verified_cache"
        assert receipt.last_verified_at == NOW
        with (
            pytest.raises(ValueError, match="offline"),
            client.open("au.mbs.service-items", offline=True),
        ):
            pytest.fail("offline miss must fail closed")


def test_cache_receipt_expires_and_offline_read_fails_closed() -> None:
    hub = Hub()
    clock = Clock()
    with resolver(hub, clock=clock) as client:
        assert (
            client.cache_receipt("au.mbs.service-items").status == "unavailable"
        )
        with client.open("au.mbs.service-items"):
            pass
        assert (
            client.cache_receipt("au.mbs.service-items").status
            == "verified_exact_digest"
        )
        clock.now += timedelta(days=2)
        assert (
            "verified_cache_offline"
            not in client.resolve("au.mbs.service-items").capabilities
        )
        expired = client.cache_receipt("au.mbs.service-items")
        assert expired.status == "contract_expired"
        assert expired.last_origin == "remote"
        assert expired.last_verified_at == NOW
        with (
            pytest.raises(ValueError, match="offline"),
            client.open("au.mbs.service-items", offline=True),
        ):
            pytest.fail("expired cache must never be used offline")


def test_unverified_or_failed_content_never_produces_verified_receipt() -> None:
    hub = Hub()
    hub.payload = b"x" * len(PAYLOAD)
    with resolver(hub) as client:
        with (
            pytest.raises(ValueError, match=r"size|digest"),
            client.open("au.mbs.service-items"),
        ):
            pytest.fail("corrupt bytes")
        receipt = client.cache_receipt("au.mbs.service-items")
        assert receipt.status == "unavailable"
        assert receipt.last_origin is None
        assert receipt.last_verified_at is None


def test_cache_receipt_reports_exact_nondefault_budgets() -> None:
    item = resource()
    hub = Hub()
    with resolver(
        hub,
        item,
        max_read_bytes=1024,
        cache_bytes=512,
        max_cache_entries=1,
        max_open_reads=1,
        timeout_seconds=7.5,
    ) as client:
        with client.open(item.resource_id):
            pass
        receipt = client.cache_receipt(item.resource_id)
        assert receipt.max_read_bytes == 1024
        assert receipt.cache_budget_bytes == 512
        assert receipt.max_cache_entries == 1
        assert receipt.max_open_reads == 1
        assert receipt.timeout_seconds == pytest.approx(7.5)
        assert client.cached_bytes == len(PAYLOAD)


def test_resource_and_semantic_manifest_denominators_are_bounded() -> None:
    item = resource()
    with pytest.raises(ValueError, match="resource denominator"):
        resolver(Hub(), *(item for _ in range(257)))

    oversized = replace(item, semantic_manifest=b" " * (16 * 1024 + 1))
    admitted = frozenset({
        hashlib.sha256(oversized.semantic_manifest).hexdigest()
    })
    with pytest.raises(ValueError, match="semantic manifest exceeds"):
        resolver(Hub(), oversized, admitted_semantics=admitted)


def test_reader_identity_mismatch_fails_closed() -> None:
    hub = Hub()
    client = resolver(hub)

    @contextmanager
    def mismatched(*_args: object, **_kwargs: object) -> Any:
        metadata = client.resolve("au.mbs.service-items")
        yield VerifiedRead(
            stream=io.BytesIO(PAYLOAD),
            origin="remote",
            contract_sha256=metadata.contract_sha256,
            sha256="f" * 64,
            byte_count=len(PAYLOAD),
        )

    client._reader.open = mismatched  # type: ignore[method-assign]
    with (
        pytest.raises(ValueError, match="identity mismatch"),
        client.open("au.mbs.service-items"),
    ):
        pytest.fail("mismatched reader identity")
    client.close()


def test_verified_read_does_not_claim_retention_beyond_cache_budget() -> None:
    hub = Hub()
    with resolver(hub, cache_bytes=1) as client:
        assert (
            "verified_cache_offline"
            not in client.resolve("au.mbs.service-items").capabilities
        )
        with client.open("au.mbs.service-items") as result:
            assert result.verified.stream.read() == PAYLOAD
            assert result.cache_receipt.status == "unavailable"
            assert result.cache_receipt.last_origin == "remote"
        with (
            pytest.raises(ValueError, match="offline"),
            client.open("au.mbs.service-items", offline=True),
        ):
            pytest.fail("unretained bytes must not become offline data")


def test_resolution_requires_independently_admitted_exact_contract() -> None:
    item = resource()
    hub = Hub()
    with pytest.raises(ValueError, match="admitted"):
        resolver(hub, item, admitted=frozenset())
    assert not hub.requests


def test_semantics_require_an_independently_admitted_manifest() -> None:
    original = resource()
    forged = replace(
        original,
        semantic_dimension="regulatory",
        semantic_manifest=semantic_manifest(
            original.binding.contract_sha256,
            dimension="regulatory",
        ),
    )
    admitted = frozenset({
        hashlib.sha256(original.semantic_manifest).hexdigest()
    })
    with pytest.raises(ValueError, match=r"semantic manifest.*admitted"):
        resolver(Hub(), forged, admitted_semantics=admitted)


@pytest.mark.parametrize(
    "manifest",
    [
        b'{"version":"1.0","version":"1.0"}',
        json.dumps({
            "contract_sha256": "d" * 64,
            "entity_granularity": "service_item",
            "extra": True,
            "resource_id": "au.mbs.service-items",
            "semantic_dimension": "service_benefit",
            "version": "1.0",
        }).encode(),
    ],
)
def test_admitted_semantic_manifest_must_have_exact_unique_claims(
    manifest: bytes,
) -> None:
    item = replace(resource(), semantic_manifest=manifest)
    admitted = frozenset({hashlib.sha256(manifest).hexdigest()})
    with pytest.raises(ValueError, match=r"semantic manifest"):
        resolver(Hub(), item, admitted_semantics=admitted)


def test_fail_closed_contract_does_not_advertise_offline_capability() -> None:
    raw = contract(cache={"offline_behavior": "fail_closed"})
    item = resource(raw)
    with resolver(Hub(), item) as client:
        assert (
            "verified_cache_offline"
            not in client.resolve(item.resource_id).capabilities
        )
        with client.open(item.resource_id):
            pass
        with (
            pytest.raises(ValueError, match="offline"),
            client.open(item.resource_id, offline=True),
        ):
            pytest.fail("fail-closed policy")


@pytest.mark.parametrize(
    "change",
    [
        {"dataset": "example/substituted"},
        {"revision": "b" * 40},
        {"contract_sha256": "c" * 64},
    ],
)
def test_binding_substitution_is_rejected(change: dict[str, object]) -> None:
    item = resource()
    item = replace(item, binding=replace(item.binding, **change))
    with pytest.raises(ValueError, match=r"binding|distribution|digest"):
        resolver(Hub(), item)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("resource_id", " "),
        ("semantic_dimension", "clinical_equivalence"),
        ("entity_granularity", "patient"),
    ],
)
def test_product_identity_and_semantics_are_bounded(
    field: str, value: object
) -> None:
    item = replace(resource(), **{field: value})
    with pytest.raises(ValueError, match=r"resource|dimension|granularity"):
        resolver(Hub(), item)


def test_duplicate_resource_or_contract_alias_is_rejected() -> None:
    item = resource()
    with pytest.raises(ValueError, match="duplicate resource"):
        resolver(Hub(), item, item)
    alias = replace(
        item,
        resource_id="au.mbs.other",
        semantic_manifest=semantic_manifest(
            item.binding.contract_sha256,
            resource_id="au.mbs.other",
        ),
    )
    with pytest.raises(ValueError, match="contract alias"):
        resolver(Hub(), item, alias)


@pytest.mark.parametrize(
    "options",
    [
        {"max_read_bytes": len(PAYLOAD) - 1},
        {"max_read_bytes": 0},
        {"cache_bytes": True},
        {"max_cache_entries": 0},
        {"max_open_reads": 0},
        {"timeout_seconds": 0},
    ],
)
def test_byte_time_and_cache_budgets_fail_closed(
    options: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match=r"budget|timeout|exceeds"):
        resolver(Hub(), **options)


def test_remote_failure_never_falls_back_to_cached_data() -> None:
    hub = Hub()
    with resolver(hub) as client:
        with client.open("au.mbs.service-items"):
            pass
        hub.status = 503
        with (
            pytest.raises(ValueError, match="HTTP"),
            client.open("au.mbs.service-items"),
        ):
            pytest.fail("online error must not select stale cache")


def test_unknown_resource_and_closed_reader_are_explicit() -> None:
    client = resolver(Hub())
    with pytest.raises(ValueError, match="unknown resource"):
        client.resolve("au.pbs.medicines")
    client.close()
    with (
        pytest.raises(ValueError, match="closed"),
        client.open("au.mbs.service-items"),
    ):
        pytest.fail("closed resolver")
