"""Bounded Australian benefits pagination and public API regression tests."""

import hashlib
import io
import json
from typing import cast

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient
from test_platinum_query import NOW, SCHEMA, binding, contract, parquet_payload

from global_medicines_atlas.api import create_app
from global_medicines_atlas.platinum_benefits import (
    BenefitsQuery,
    BenefitsService,
)
from global_medicines_atlas.platinum_resolver import (
    ProductResource,
    StorageNeutralResolver,
)
from global_medicines_atlas.query_service import ReadOnlyQueryService


def service(
    source: str = "mbs", payload: bytes | None = None
) -> BenefitsService:
    payload = payload or parquet_payload()
    raw = json.loads(contract(payload))
    raw["source"]["source_id"] = f"au-{source}"
    raw["cache"]["max_bytes"] = max(1024, len(payload))
    encoded = json.dumps(raw).encode()
    distribution = binding(encoded)
    resource_id = f"au.{source}.service-items"
    dimension = "service_benefit" if source == "mbs" else "funding"
    granularity = "service_item" if source == "mbs" else "medicine_item"
    semantic = json.dumps({
        "version": "1.0",
        "resource_id": resource_id,
        "semantic_dimension": dimension,
        "entity_granularity": granularity,
        "contract_sha256": distribution.contract_sha256,
    }).encode()
    resource = ProductResource(
        resource_id=resource_id,
        semantic_dimension=dimension,
        entity_granularity=granularity,
        binding=distribution,
        contract=encoded,
        semantic_manifest=semantic,
    )

    def handle(request: httpx.Request) -> httpx.Response:
        if "/api/datasets/" in request.url.path:
            return httpx.Response(
                200, json={"sha": "a" * 40, "private": False, "gated": False}
            )
        return httpx.Response(200, content=payload)

    backend = StorageNeutralResolver(
        schema=SCHEMA,
        resources=[resource],
        admitted_contracts=frozenset({distribution.contract_sha256}),
        admitted_semantic_manifests=frozenset({
            hashlib.sha256(semantic).hexdigest()
        }),
        transport_factory=lambda: httpx.MockTransport(handle),
        clock=lambda: NOW,
    )
    return BenefitsService(backend, cursor_key=b"k" * 32)


def test_pages_preserve_evidence_and_reject_query_drift() -> None:
    backend = service()
    query = BenefitsQuery(columns=("item_code", "benefit"), limit=2)
    first = backend.query("au.mbs.service-items", query)
    assert [row["item_code"] for row in first.rows] == ["100", "200"]
    assert first.identity.semantic_dimension == "service_benefit"
    assert first.identity.revision == "a" * 40
    assert first.window_complete is True
    assert first.next_cursor
    second = backend.query(
        "au.mbs.service-items",
        query.model_copy(update={"cursor": first.next_cursor}),
    )
    assert [row["item_code"] for row in second.rows] == ["300"]
    assert second.next_cursor is None
    with pytest.raises(ValueError, match="cursor"):
        backend.query(
            "au.mbs.service-items",
            BenefitsQuery(columns=("benefit",), cursor=first.next_cursor),
        )


def test_api_unavailable_validation_and_read_only() -> None:
    app = create_app(cast("ReadOnlyQueryService", object()), benefits=service())
    client = TestClient(app)
    url = "/api/v1/benefits/au.mbs.service-items"
    response = client.get(url, params={"columns": "item_code", "limit": 2})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert len(response.json()["rows"]) == 2
    assert (
        client.get(
            url, params={"columns": "item_code", "limit": 101}
        ).status_code
        == 422
    )
    assert client.post(url).status_code == 405
    assert (
        client.get(
            "/api/v1/benefits/au.mbs.missing", params={"columns": "item_code"}
        ).status_code
        == 404
    )
    offline = client.get(url, params={"columns": "item_code", "offline": True})
    assert offline.status_code == 200
    missing = TestClient(create_app(cast("ReadOnlyQueryService", object())))
    assert missing.get(url, params={"columns": "item_code"}).status_code == 503


def test_offline_miss_is_explicit() -> None:
    result = service().query(
        "au.mbs.service-items",
        BenefitsQuery(columns=("item_code",), offline=True),
    )
    assert result.status == "unavailable"
    assert result.reason == "offline_cache_unavailable"
    assert result.rows == ()


def test_pbs_funding_is_independent_and_page_digest_is_exact() -> None:
    result = service("pbs").query(
        "au.pbs.service-items", BenefitsQuery(columns=("item_code",), limit=1)
    )
    assert result.identity.semantic_dimension == "funding"
    assert result.identity.entity_granularity == "medicine_item"
    assert (
        result.page_sha256
        == hashlib.sha256(
            json.dumps(
                result.rows,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )
    assert result.page_sha256 != result.window_sha256
    assert result.coverage_state == "not_declared"
    assert result.comparison_validity == "not_evaluated"


@pytest.mark.parametrize(
    "token", ["garbage", "0:x:y", "1000:x:y", "2:x:y", "02:x:y"]
)
def test_hostile_cursor_rejected(token: str) -> None:
    with pytest.raises(ValueError, match="cursor"):
        service().query(
            "au.mbs.service-items",
            BenefitsQuery(columns=("item_code",), cursor=token),
        )


def test_scan_limit_never_claims_complete_source() -> None:
    sink = io.BytesIO()
    pq.write_table(pa.table({"item_code": [str(i) for i in range(1001)]}), sink)
    result = service(payload=sink.getvalue()).query(
        "au.mbs.service-items", BenefitsQuery(columns=("item_code",))
    )
    assert result.window_rows == 1000
    assert result.window_complete is False
    assert len(result.rows) == 100


def test_cursor_is_bound_to_page_size_and_signature() -> None:
    backend = service()
    query = BenefitsQuery(columns=("item_code",), limit=1)
    first = backend.query("au.mbs.service-items", query)
    assert first.next_cursor is not None
    with pytest.raises(ValueError, match="cursor"):
        backend.query(
            "au.mbs.service-items",
            query.model_copy(update={"limit": 2, "cursor": first.next_cursor}),
        )
    with pytest.raises(ValueError, match="cursor"):
        backend.query(
            "au.mbs.service-items",
            query.model_copy(update={"cursor": first.next_cursor[:-1] + "x"}),
        )


def test_weak_cursor_keys_rejected() -> None:
    with pytest.raises(ValueError, match="cursor key"):
        BenefitsService(
            cast("StorageNeutralResolver", object()), cursor_key=b"short"
        )


@pytest.mark.parametrize("limit", [-1, 0, 101, 1000])
@pytest.mark.parametrize("construction", ["copy", "construct"])
def test_shared_service_revalidates_unchecked_limits(
    limit: int, construction: str
) -> None:
    query = BenefitsQuery(columns=("item_code",), limit=1)
    if construction == "copy":
        unchecked = query.model_copy(update={"limit": limit})
    else:
        unchecked = BenefitsQuery.model_construct(
            **{**query.model_dump(), "limit": limit}
        )
    backend = BenefitsService(
        cast("StorageNeutralResolver", object()), cursor_key=b"k" * 32
    )
    with pytest.raises(ValueError, match="limit"):
        backend.query("au.mbs.service-items", unchecked)
