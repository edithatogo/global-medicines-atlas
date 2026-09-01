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
    QuerySpec,
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


def resolver(payload: bytes) -> StorageNeutralResolver:
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
                200,
                json={"sha": "a" * 40, "private": False, "gated": False},
            )
        return httpx.Response(200, content=payload)

    return StorageNeutralResolver(
        schema=SCHEMA,
        resources=[resource],
        admitted_contracts=frozenset({distribution.contract_sha256}),
        admitted_semantic_manifests=frozenset({
            hashlib.sha256(semantic).hexdigest()
        }),
        transport_factory=lambda: httpx.MockTransport(handle),
        clock=lambda: NOW,
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
