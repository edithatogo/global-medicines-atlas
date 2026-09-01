"""Synthetic Platinum resolution/read tests; no live data or publication."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from global_medicines_atlas.federation_distribution import (
    DistributionBinding,
    ProducedObject,
    reconcile_distribution,
)
from global_medicines_atlas.platinum_resolver import (
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


def resource(raw: bytes | None = None) -> ProductResource:
    raw = contract() if raw is None else raw
    return ProductResource(
        resource_id="au.mbs.service-items",
        semantic_dimension="service_benefit",
        entity_granularity="service_item",
        binding=binding(raw),
        contract=raw,
    )


def resolver(
    hub: Hub,
    *resources: ProductResource,
    admitted: frozenset[str] | None = None,
    **options: Any,
) -> StorageNeutralResolver:
    selected = resources or (resource(),)
    return StorageNeutralResolver(
        schema=SCHEMA,
        resources=selected,
        admitted_contracts=admitted
        if admitted is not None
        else frozenset(item.binding.contract_sha256 for item in selected),
        transport_factory=lambda: httpx.MockTransport(hub.handle),
        clock=lambda: NOW,
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
        assert len(hub.requests) == 2
        with client.open("au.mbs.service-items", offline=True) as result:
            assert result.verified.origin == "verified_cache"
            assert result.verified.stream.read() == PAYLOAD
        assert len(hub.requests) == 2
        client.evict()
        with (
            pytest.raises(ValueError, match="offline"),
            client.open("au.mbs.service-items", offline=True),
        ):
            pytest.fail("offline miss must fail closed")


def test_resolution_requires_independently_admitted_exact_contract() -> None:
    item = resource()
    hub = Hub()
    with pytest.raises(ValueError, match="admitted"):
        resolver(hub, item, admitted=frozenset())
    assert not hub.requests


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
    alias = replace(item, resource_id="au.mbs.other")
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
