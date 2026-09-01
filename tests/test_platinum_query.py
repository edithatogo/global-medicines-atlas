"""Contract tests for bounded storage-neutral Platinum queries."""

from __future__ import annotations

import hashlib
import io
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from global_medicines_atlas import platinum_query
from global_medicines_atlas.federation_distribution import (
    DistributionBinding,
    ProducedObject,
    reconcile_distribution,
)
from global_medicines_atlas.platinum_query import (
    DuckDBQueryAdapter,
    PlatinumQueryService,
    PolarsQueryAdapter,
    QueryFilter,
    QueryResult,
    QuerySpec,
    QueryUnavailable,
)
from global_medicines_atlas.platinum_resolver import (
    ProductResource,
    StorageNeutralResolver,
)

ROOT = Path(__file__).resolve().parents[1] / "contracts/medallion/v4"
SCHEMA = (ROOT / "federation.schema.json").read_bytes()
NOW = datetime(2026, 9, 2, tzinfo=UTC)


def parquet_payload() -> bytes:
    sink = io.BytesIO()
    pq.write_table(
        pa.table({
            "item_code": ["100", "200", "300"],
            "benefit": [12.5, 25.0, 37.5],
            "note": ["legacy", "current", "current"],
        }),
        sink,
    )
    return sink.getvalue()


def contract(payload: bytes) -> bytes:
    document = json.loads((ROOT / "fixtures/valid.json").read_bytes())
    digest = hashlib.sha256(payload).hexdigest()
    document["source"].update(
        layer="platinum",
        bronze_stratum=None,
        representation="projection",
        schema_era="mbs-2026-09",
        comparison_cohort="synthetic",
        effective_date="2026-09-01",
        retrieved_at="2026-09-02T00:00:00Z",
    )
    document["recovery"]["role"] = "primary"
    document["lineage"]["inputs"] = [document["verification"]["receipt"]]
    document["lineage"]["promotion_receipt"] = document["verification"][
        "receipt"
    ]
    document["location"].update(
        path="platinum/mbs.parquet", bytes=len(payload), sha256=digest
    )
    document["verification"].update(
        path="platinum/mbs.parquet",
        bytes=len(payload),
        sha256=digest,
        verified_at="2026-09-02T00:05:00Z",
    )
    document["rights"].update(
        subject_sha256=digest, path="platinum/mbs.parquet"
    )
    document["cache"]["offline_behavior"] = "verified_exact_digest_only"
    document["cache"]["expires_at"] = "2026-09-03T00:00:00Z"
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


def resolver(
    payload: bytes,
    *,
    status: int = 200,
    metadata_json: object | None = None,
    clock: Any = lambda: NOW,
) -> StorageNeutralResolver:
    raw = contract(payload)
    distribution = binding(raw)
    semantic = json.dumps(
        {
            "contract_sha256": distribution.contract_sha256,
            "entity_granularity": "service_item",
            "resource_id": "au.mbs.service-items",
            "semantic_dimension": "service_benefit",
            "version": "1.0",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    resource = ProductResource(
        resource_id="au.mbs.service-items",
        semantic_dimension="service_benefit",
        entity_granularity="service_item",
        binding=distribution,
        contract=raw,
        semantic_manifest=semantic,
    )

    def handle(request: httpx.Request) -> httpx.Response:
        if "/api/datasets/" in request.url.path:
            return httpx.Response(
                status,
                json=(
                    metadata_json
                    if metadata_json is not None
                    else {"sha": "a" * 40, "private": False, "gated": False}
                ),
            )
        return httpx.Response(status, content=payload)

    return StorageNeutralResolver(
        schema=SCHEMA,
        resources=[resource],
        admitted_contracts=frozenset({distribution.contract_sha256}),
        admitted_semantic_manifests=frozenset({
            hashlib.sha256(semantic).hexdigest()
        }),
        transport_factory=lambda: httpx.MockTransport(handle),
        clock=clock,
    )


@pytest.mark.parametrize(
    ("engine", "adapter"),
    [("duckdb", DuckDBQueryAdapter()), ("polars", PolarsQueryAdapter())],
)
def test_query_projects_filters_limits_and_wraps_exact_evidence(
    engine: str, adapter: Any
) -> None:
    payload = parquet_payload()
    with resolver(payload) as client:
        service = PlatinumQueryService(client, adapters={engine: adapter})
        result = service.query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(
                columns=("item_code", "benefit"),
                filters=(QueryFilter("benefit", ">=", 20.0),),
                limit=1,
            ),
        )

    assert result.status == "available"
    assert result.engine == engine
    assert result.capabilities == (
        "column_projection",
        "predicate_pushdown",
        "bounded_limit",
    )
    assert result.rows == ({"item_code": "200", "benefit": 25.0},)
    assert result.row_count == 1
    assert (
        result.result_sha256
        == hashlib.sha256(result.canonical_rows).hexdigest()
    )
    assert result.evidence.dataset == "example/synthetic-mbs"
    assert result.evidence.revision == "a" * 40
    assert result.evidence.path == "platinum/mbs.parquet"
    assert result.evidence.object_sha256 == hashlib.sha256(payload).hexdigest()
    assert result.evidence.semantic_dimension == "service_benefit"
    assert result.evidence.entity_granularity == "service_item"
    assert result.evidence.schema_era == "mbs-2026-09"
    assert result.evidence.comparison_cohort == "synthetic"
    assert result.evidence.effective_date == "2026-09-01"
    assert result.evidence.retrieved_at == "2026-09-02T00:00:00Z"
    assert result.evidence.coverage_state == "not_declared"
    assert result.evidence.uncertainty_state == "not_declared"
    assert result.evidence.review_state == "not_declared"
    assert result.evidence.comparison_validity == "not_evaluated"
    assert result.cache_receipt.status == "verified_exact_digest"
    assert result.query_receipt.result_sha256 == result.result_sha256
    assert (
        result.query_receipt.query_sha256
        == hashlib.sha256(result.query_receipt.canonical_query).hexdigest()
    )
    assert (
        result.query_receipt.receipt_sha256
        == hashlib.sha256(result.query_receipt.canonical_bytes).hexdigest()
    )
    assert result.query_receipt.cache_receipt_sha256 == (
        result.cache_receipt.receipt_sha256
    )
    assert result.query_receipt.semantic_manifest_sha256 == (
        result.evidence.semantic_manifest_sha256
    )


@pytest.mark.parametrize(
    "adapter", [DuckDBQueryAdapter(), PolarsQueryAdapter()]
)
def test_query_rejects_unknown_columns_and_injection(adapter: Any) -> None:
    payload = parquet_payload()
    with resolver(payload) as client:
        service = PlatinumQueryService(client, adapters={adapter.name: adapter})
        for spec in (
            QuerySpec(columns=("missing",), limit=1),
            QuerySpec(
                columns=("item_code",),
                filters=(QueryFilter("item_code; DROP TABLE x", "=", "100"),),
                limit=1,
            ),
        ):
            with pytest.raises(ValueError, match="column"):
                service.query(
                    "au.mbs.service-items",
                    engine=adapter.name,
                    spec=spec,
                )


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (QuerySpec(columns=(), limit=1), "columns"),
        (QuerySpec(columns=("item_code",), limit=0), "limit"),
        (QuerySpec(columns=("item_code",), limit=1001), "limit"),
        (
            QuerySpec(
                columns=("item_code",),
                filters=tuple(
                    QueryFilter("item_code", "=", "100") for _ in range(17)
                ),
                limit=1,
            ),
            "filters",
        ),
    ],
)
def test_query_plan_budgets_fail_before_read(
    spec: QuerySpec, message: str
) -> None:
    payload = parquet_payload()
    with resolver(payload) as client:
        service = PlatinumQueryService(client)
        with pytest.raises(ValueError, match=message):
            service.query("au.mbs.service-items", engine="duckdb", spec=spec)
        assert (
            client.cache_receipt("au.mbs.service-items").status == "unavailable"
        )


def test_engine_choice_is_explicit_and_offline_state_is_preserved() -> None:
    payload = parquet_payload()
    with resolver(payload) as client:
        service = PlatinumQueryService(client)
        with pytest.raises(ValueError, match="engine"):
            service.query(
                "au.mbs.service-items",
                engine="spark",
                spec=QuerySpec(columns=("item_code",), limit=1),
            )
        with pytest.raises(ValueError, match="offline"):
            service.query(
                "au.mbs.service-items",
                engine="duckdb",
                spec=QuerySpec(columns=("item_code",), limit=1),
                offline=True,
            )


def test_all_polars_predicates_are_supported_without_semantic_rewrite() -> None:
    payload = parquet_payload()
    expected = {
        "=": ("200",),
        "!=": ("100", "300"),
        "<": ("100",),
        "<=": ("100", "200"),
        ">": ("300",),
        ">=": ("200", "300"),
    }
    with resolver(payload) as client:
        service = PlatinumQueryService(client)
        for operator, item_codes in expected.items():
            result = service.query(
                "au.mbs.service-items",
                engine="polars",
                spec=QuerySpec(
                    columns=("item_code",),
                    filters=(
                        QueryFilter("benefit", operator, 25.0),  # type: ignore[arg-type]
                    ),
                    limit=3,
                ),
            )
            assert tuple(row["item_code"] for row in result.rows) == item_codes


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (QuerySpec(columns=("item_code", "item_code")), "unique"),
        (
            QuerySpec(columns=("item_code",), max_result_bytes=0),
            "byte budget",
        ),
        (
            QuerySpec(columns=("item_code",), max_result_bytes=1024 * 1024 + 1),
            "byte budget",
        ),
        (QuerySpec(columns=("item_code",), timeout_seconds=0), "timeout"),
        (
            QuerySpec(columns=("item_code",), timeout_seconds=math.inf),
            "timeout",
        ),
        (
            QuerySpec(
                columns=("item_code",),
                filters=(
                    QueryFilter("item_code", "contains", "1"),  # type: ignore[arg-type]
                ),
            ),
            "operator",
        ),
        (
            QuerySpec(
                columns=("item_code",),
                filters=(
                    QueryFilter("item_code", "=", object()),  # type: ignore[arg-type]
                ),
            ),
            "scalar",
        ),
    ],
)
def test_additional_query_plan_controls_fail_before_read(
    spec: QuerySpec, message: str
) -> None:
    payload = parquet_payload()
    with resolver(payload) as client:
        with pytest.raises(ValueError, match=message):
            PlatinumQueryService(client).query(
                "au.mbs.service-items", engine="duckdb", spec=spec
            )
        assert (
            client.cache_receipt("au.mbs.service-items").status == "unavailable"
        )


def test_result_byte_budget_and_adapter_identity_fail_closed() -> None:
    payload = parquet_payload()

    class WrongAdapter(DuckDBQueryAdapter):
        name = "polars"

    with resolver(payload) as client:
        service = PlatinumQueryService(client)
        with pytest.raises(ValueError, match="result exceeds"):
            service.query(
                "au.mbs.service-items",
                engine="duckdb",
                spec=QuerySpec(columns=("item_code",), max_result_bytes=1),
            )
        with pytest.raises(ValueError, match="identity mismatch"):
            PlatinumQueryService(
                client, adapters={"duckdb": WrongAdapter()}
            ).query(
                "au.mbs.service-items",
                engine="duckdb",
                spec=QuerySpec(columns=("item_code",), limit=1),
            )


def test_runtime_and_scalar_boundaries_are_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert platinum_query._scalar(datetime(2026, 9, 2, tzinfo=UTC)) == (
        "2026-09-02 00:00:00+00:00"
    )
    with pytest.raises(ValueError, match="unsupported scalar"):
        platinum_query._scalar(b"opaque")
    monkeypatch.setattr(platinum_query.time, "monotonic", lambda: 31.0)
    with pytest.raises(ValueError, match="runtime exceeds"):
        platinum_query._runtime(0.0, 30.0)


def test_query_state_distinguishes_offline_miss_eviction_and_expiry() -> None:
    payload = parquet_payload()
    with resolver(payload) as client:
        service = PlatinumQueryService(client)
        missing = service.query_state(
            "au.mbs.service-items",
            engine="duckdb",
            spec=QuerySpec(columns=("item_code",), limit=1),
            offline=True,
        )
        assert isinstance(missing, QueryUnavailable)
        assert missing.reason == "offline_cache_unavailable"
        assert missing.evidence is not None
        assert missing.cache_receipt is not None
        assert (
            missing.receipt_sha256
            == hashlib.sha256(missing.canonical_bytes).hexdigest()
        )
        assert missing.query_sha256 == hashlib.sha256(
            missing.canonical_query
        ).hexdigest()

        available = service.query_state(
            "au.mbs.service-items",
            engine="duckdb",
            spec=QuerySpec(columns=("item_code",), limit=1),
        )
        assert isinstance(available, QueryResult)
        client.evict()
        evicted = service.query_state(
            "au.mbs.service-items",
            engine="duckdb",
            spec=QuerySpec(columns=("item_code",), limit=1),
            offline=True,
        )
        assert isinstance(evicted, QueryUnavailable)
        assert evicted.reason == "offline_cache_unavailable"


def test_query_state_reports_unknown_expired_and_remote_unavailable() -> None:
    payload = parquet_payload()
    with resolver(payload) as client:
        unknown = PlatinumQueryService(client).query_state(
            "au.unknown.resource",
            engine="polars",
            spec=QuerySpec(columns=("item_code",), limit=1),
        )
        assert isinstance(unknown, QueryUnavailable)
        assert unknown.reason == "unknown_resource"
        assert unknown.evidence is None
        assert unknown.cache_receipt is None

    with resolver(payload, metadata_json=[]) as client:
        malformed = PlatinumQueryService(client).query_state(
            "au.mbs.service-items",
            engine="polars",
            spec=QuerySpec(columns=("item_code",), limit=1),
        )
        assert isinstance(malformed, QueryUnavailable)
        assert malformed.reason == "verified_resource_unavailable"

    with resolver(payload, status=503) as client:
        remote = PlatinumQueryService(client).query_state(
            "au.mbs.service-items",
            engine="polars",
            spec=QuerySpec(columns=("item_code",), limit=1),
        )
        assert isinstance(remote, QueryUnavailable)
        assert remote.reason == "verified_resource_unavailable"


def test_cache_receipts_are_content_addressed_and_expiry_is_explicit() -> None:
    payload = parquet_payload()
    with resolver(payload) as client:
        initial = client.cache_receipt("au.mbs.service-items")
        assert initial.status == "unavailable"
        assert (
            initial.receipt_sha256
            == hashlib.sha256(initial.canonical_bytes).hexdigest()
        )
        assert client.cache_receipt("au.mbs.service-items") == initial
        with client.open("au.mbs.service-items"):
            pass
        verified = client.cache_receipt("au.mbs.service-items")
        assert verified.receipt_sha256 != initial.receipt_sha256
        client.evict()
        evicted = client.cache_receipt("au.mbs.service-items")
        assert evicted.status == "unavailable"
        assert evicted.receipt_sha256 != verified.receipt_sha256

    with resolver(
        payload, clock=lambda: datetime(2026, 9, 4, tzinfo=UTC)
    ) as client:
        expired = client.cache_receipt("au.mbs.service-items")
        assert expired.status == "contract_expired"
        outcome = PlatinumQueryService(client).query_state(
            "au.mbs.service-items",
            engine="duckdb",
            spec=QuerySpec(columns=("item_code",), limit=1),
            offline=True,
        )
        assert isinstance(outcome, QueryUnavailable)
        assert outcome.reason == "offline_contract_expired"


def test_unavailable_receipt_binds_attempted_query_plan() -> None:
    payload = parquet_payload()
    with resolver(payload, status=503) as client:
        service = PlatinumQueryService(client)
        first = service.query_state(
            "au.mbs.service-items",
            engine="duckdb",
            spec=QuerySpec(columns=("item_code",), limit=1),
        )
        second = service.query_state(
            "au.mbs.service-items",
            engine="duckdb",
            spec=QuerySpec(columns=("benefit",), limit=2),
        )
    assert isinstance(first, QueryUnavailable)
    assert isinstance(second, QueryUnavailable)
    assert first.query_sha256 != second.query_sha256
    assert first.receipt_sha256 != second.receipt_sha256
