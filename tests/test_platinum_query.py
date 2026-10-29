"""Contract tests for bounded storage-neutral Platinum queries."""

from __future__ import annotations

import hashlib
import io
import json
import math
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient
from test_pbs_value_package import inputs
from test_support.federation import admission_record
from typer.testing import CliRunner

from global_medicines_atlas import cli, platinum_query
from global_medicines_atlas import (
    platinum_structure_qualification as qualification,
)
from global_medicines_atlas.atlas import AtlasQueryService, create_atlas_app
from global_medicines_atlas.federation_distribution import (
    DistributionBinding,
    ProducedObject,
    reconcile_distribution,
)
from global_medicines_atlas.pbs_direct_values import (
    iter_direct_historical_value_batches,
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
from global_medicines_atlas.platinum_structure import SourceStructureService
from global_medicines_atlas.platinum_v2_api import create_v2_app

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


def decimal_parquet_payload() -> bytes:
    sink = io.BytesIO()
    pq.write_table(
        pa.table({
            "item_code": ["100", "200", "300"],
            "benefit": pa.array(
                [Decimal("2.00"), Decimal("10.00"), Decimal("25.00")],
                type=pa.decimal128(38, 9),
            ),
        }),
        sink,
    )
    return sink.getvalue()


def date_parquet_payload() -> bytes:
    sink = io.BytesIO()
    pq.write_table(
        pa.table({
            "item_code": ["100", "200", "300"],
            "start_date": pa.array(
                [date(2025, 7, 1), date(2025, 8, 1), date(2025, 9, 1)],
                type=pa.date32(),
            ),
        }),
        sink,
    )
    return sink.getvalue()


def nested_native_parquet_payload() -> bytes:
    sink = io.BytesIO()
    item_type = pa.struct([
        pa.field("native_value", pa.string()),
        pa.field("native_state", pa.string(), nullable=False),
        pa.field("conversion_status", pa.string(), nullable=False),
        pa.field("typed_value", pa.string()),
    ])
    pq.write_table(
        pa.table({
            "ItemNum": pa.array(
                [
                    {
                        "native_value": "MBS-A",
                        "native_state": "present",
                        "conversion_status": "preserved",
                        "typed_value": "MBS-A",
                    },
                    {
                        "native_value": None,
                        "native_state": "null",
                        "conversion_status": "preserved",
                        "typed_value": None,
                    },
                    {
                        "native_value": "MBS-B",
                        "native_state": "present",
                        "conversion_status": "preserved",
                        "typed_value": "MBS-B",
                    },
                ],
                type=item_type,
            ),
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
    document["cache"]["max_bytes"] = max(1024, len(payload))
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
    semantic_dimension: Literal[
        "service_benefit", "source_structure"
    ] = "service_benefit",
) -> StorageNeutralResolver:
    raw = contract(payload)
    distribution = binding(raw)
    semantic = json.dumps(
        {
            "contract_sha256": distribution.contract_sha256,
            "entity_granularity": "service_item",
            "resource_id": "au.mbs.service-items",
            "semantic_dimension": semantic_dimension,
            "version": "1.0",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    resource = ProductResource(
        resource_id="au.mbs.service-items",
        semantic_dimension=semantic_dimension,
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
        admission_records=(admission_record(raw),),
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
    ("engine", "adapter"),
    [("duckdb", DuckDBQueryAdapter()), ("polars", PolarsQueryAdapter())],
)
def test_query_projects_native_components_from_source_field_structs(
    engine: str, adapter: Any
) -> None:
    payload = nested_native_parquet_payload()
    with resolver(payload) as client:
        result = PlatinumQueryService(client, adapters={engine: adapter}).query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(
                columns=("ItemNum__native_value",),
                filters=(QueryFilter("ItemNum__native_state", "=", "present"),),
                limit=2,
            ),
        )

    assert result.rows == (
        {"ItemNum__native_value": "MBS-A"},
        {"ItemNum__native_value": "MBS-B"},
    )


def test_nested_projection_tokens_do_not_capture_gold_column_names():
    assert platinum_query._column_parts(
        "benefit__BenefitStartDate__typed_value"
    ) == ("benefit__BenefitStartDate__typed_value", None)
    assert platinum_query._column_parts("ItemNum__native_value") == (
        "ItemNum",
        "native_value",
    )


@pytest.mark.parametrize(
    ("engine", "adapter"),
    [("duckdb", DuckDBQueryAdapter()), ("polars", PolarsQueryAdapter())],
)
def test_decimal_filter_uses_exact_numeric_order_and_receipt_value(
    engine: str, adapter: Any
) -> None:
    payload = decimal_parquet_payload()
    with resolver(payload) as client:
        result = PlatinumQueryService(client, adapters={engine: adapter}).query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(
                columns=("item_code", "benefit"),
                filters=(QueryFilter("benefit", ">=", Decimal("9.99")),),
                limit=3,
            ),
        )

    assert result.rows == (
        {"item_code": "200", "benefit": "10.000000000"},
        {"item_code": "300", "benefit": "25.000000000"},
    )
    query_document = json.loads(result.query_receipt.canonical_query)
    assert query_document["filters"][0]["value"] == {
        "type": "decimal",
        "value": "9.99",
    }


@pytest.mark.parametrize(
    ("engine", "adapter"),
    [("duckdb", DuckDBQueryAdapter()), ("polars", PolarsQueryAdapter())],
)
def test_date_filter_uses_explicit_typed_value_and_canonical_receipt(
    engine: str, adapter: Any
) -> None:
    payload = date_parquet_payload()
    with resolver(payload) as client:
        result = PlatinumQueryService(client, adapters={engine: adapter}).query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(
                columns=("item_code", "start_date"),
                filters=(QueryFilter("start_date", ">=", date(2025, 8, 1)),),
                limit=3,
            ),
        )

    assert result.rows == (
        {"item_code": "200", "start_date": "2025-08-01"},
        {"item_code": "300", "start_date": "2025-09-01"},
    )
    query_document = json.loads(result.query_receipt.canonical_query)
    assert query_document["filters"][0]["value"] == {
        "type": "date",
        "value": "2025-08-01",
    }


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
        (
            QuerySpec(
                columns=("benefit",),
                filters=(QueryFilter("benefit", "=", Decimal("NaN")),),
                limit=1,
            ),
            "scalar",
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
        (QuerySpec(columns=("ItemNum.secret",)), "invalid query column"),
        (
            QuerySpec(columns=('ItemNum.native_value" or 1=1',)),
            "invalid query column",
        ),
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
        assert (
            missing.query_sha256
            == hashlib.sha256(missing.canonical_query).hexdigest()
        )

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


def native_field_collection_payload() -> bytes:
    """Model the preserved PBS list of source-native field observations."""
    sink = io.BytesIO()
    fields = pa.list_(
        pa.struct([
            pa.field("source_field_id", pa.string()),
            pa.field("value", pa.string()),
            pa.field("state", pa.string()),
        ])
    )
    pq.write_table(
        pa.table({
            "entity_id": ["a", "b", "c", "d"],
            "native_fields": pa.array(
                [
                    [
                        {
                            "source_field_id": "a/text",
                            "value": "001",
                            "state": "present",
                        },
                        {
                            "source_field_id": "a/attribute",
                            "value": None,
                            "state": "null",
                        },
                    ],
                    [],
                    None,
                    [
                        {
                            "source_field_id": "d/text",
                            "value": "source only",
                            "state": "present",
                        }
                    ],
                ],
                type=fields,
            ),
        }),
        sink,
    )
    return sink.getvalue()


def test_query_reads_pipeline_produced_pbs_native_structure():
    table = pa.Table.from_batches(
        list(iter_direct_historical_value_batches(*inputs()))
    )
    sink = io.BytesIO()
    pq.write_table(table, sink)
    with resolver(
        sink.getvalue(), semantic_dimension="source_structure"
    ) as client:
        records = PlatinumQueryService(client).query(
            "au.mbs.service-items",
            engine="polars",
            spec=QuerySpec(columns=("entity_id", "native_name"), limit=2),
        )
        fields = PlatinumQueryService(client).query(
            "au.mbs.service-items",
            engine="polars",
            spec=QuerySpec(
                columns=("source_field_id", "value", "state"),
                field_collection="native_fields",
                limit=2,
            ),
        )
    assert len(records.rows) == 2
    assert all(row["entity_id"] for row in records.rows)
    assert len(fields.rows) == 2
    assert all(row["source_field_id"] for row in fields.rows)
    assert fields.evidence.comparison_validity == "not_evaluated"


@pytest.mark.parametrize("engine", ["duckdb", "polars"])
def test_query_reads_bounded_native_fields_without_inventing_empty_rows(engine):
    with resolver(native_field_collection_payload()) as client:
        result = PlatinumQueryService(client).query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(
                columns=("source_field_id", "value", "state"),
                field_collection="native_fields",
                limit=3,
            ),
        )
    assert result.rows == (
        {"source_field_id": "a/text", "value": "001", "state": "present"},
        {"source_field_id": "a/attribute", "value": None, "state": "null"},
        {
            "source_field_id": "d/text",
            "value": "source only",
            "state": "present",
        },
    )
    query = json.loads(result.query_receipt.canonical_query)
    assert query["field_collection"] == "native_fields"
    assert query["version"] == "1.1"
    assert result.evidence.comparison_validity == "not_evaluated"


@pytest.mark.parametrize("engine", ["duckdb", "polars"])
def test_native_field_filters_apply_to_fields_and_keep_output_bounded(engine):
    with resolver(native_field_collection_payload()) as client:
        result = PlatinumQueryService(client).query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(
                columns=("source_field_id", "value"),
                filters=(QueryFilter("state", "=", "present"),),
                field_collection="native_fields",
                limit=1,
            ),
        )
    assert result.rows == ({"source_field_id": "a/text", "value": "001"},)


@pytest.mark.parametrize("engine", ["duckdb", "polars"])
@pytest.mark.parametrize("collection", ["entity_id", "unknown"])
def test_native_field_collection_rejects_wrong_or_missing_schema(
    engine, collection
):
    with (
        resolver(native_field_collection_payload()) as client,
        pytest.raises(ValueError, match="field collection"),
    ):
        PlatinumQueryService(client).query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(columns=("value",), field_collection=collection),
        )


def test_native_collection_name_rejects_sql_injection_before_read():
    with resolver(native_field_collection_payload()) as client:
        with pytest.raises(ValueError, match="field collection"):
            PlatinumQueryService(client).query(
                "au.mbs.service-items",
                engine="duckdb",
                spec=QuerySpec(
                    columns=("value",), field_collection='x"; SELECT 1'
                ),
            )
        assert client.cached_bytes == 0


@pytest.mark.parametrize("engine", ["duckdb", "polars"])
def test_collection_rejects_scalar_lists_and_retains_result_budget(engine):
    sink = io.BytesIO()
    pq.write_table(pa.table({"native_fields": [["not a field struct"]]}), sink)
    with (
        resolver(sink.getvalue()) as client,
        pytest.raises(ValueError, match="list of structs"),
    ):
        PlatinumQueryService(client).query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(
                columns=("value",), field_collection="native_fields"
            ),
        )
    with (
        resolver(native_field_collection_payload()) as client,
        pytest.raises(ValueError, match="byte budget"),
    ):
        PlatinumQueryService(client).query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(
                columns=("value",),
                field_collection="native_fields",
                max_result_bytes=2,
            ),
        )


@pytest.mark.parametrize("engine", ["duckdb", "polars"])
def test_field_view_rejects_nested_scalar_component_selectors(engine):
    with (
        resolver(native_field_collection_payload()) as client,
        pytest.raises(ValueError, match="field collection"),
    ):
        PlatinumQueryService(client).query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(
                columns=("value__native_value",),
                field_collection="native_fields",
            ),
        )


def test_field_view_flows_through_real_service_api_atlas_and_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One admitted synthetic object carries the same rows through all surfaces."""
    resource_id = "au.mbs.service-items"
    with resolver(
        native_field_collection_payload(), semantic_dimension="source_structure"
    ) as client:
        service = SourceStructureService(
            client, jurisdictions={resource_id: "AU"}
        )
        api = TestClient(
            create_v2_app(cast("Any", object()), source_structure=service)
        )
        response = api.get(
            f"/api/v2/source-structure/{resource_id}",
            params={
                "view": "fields",
                "columns": ["source_field_id", "value"],
                "limit": 2,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["rows"] == [
            {"source_field_id": "a/text", "value": "001"},
            {"source_field_id": "a/attribute", "value": None},
        ]
        later = api.get(
            f"/api/v2/source-structure/{resource_id}",
            params={
                "view": "fields",
                "columns": ["source_field_id", "value"],
                "limit": 2,
                "offset": 2,
            },
        )
        assert later.status_code == 200
        later_body = later.json()
        assert later_body["rows"] == [
            {"source_field_id": "d/text", "value": "source only"}
        ]
        assert later_body["offset"] == 2
        assert later_body["query_sha256"] != body["query_sha256"]
        atlas = TestClient(
            create_atlas_app(
                cast("AtlasQueryService", object()),
                federated_source_structure=service,
            )
        )
        page = atlas.get(
            "/federated/source-structure",
            params={
                "resource_id": resource_id,
                "view": "fields",
                "columns": "source_field_id,value",
                "limit": 2,
                "offset": 2,
            },
        )
        assert page.status_code == 200
        assert "d/text" in page.text
        assert "a/text" not in page.text
        assert body["identity"]["object_sha256"] in page.text
        trust, schema = tmp_path / "trust.json", tmp_path / "schema.json"
        trust.write_text("{}")
        schema.write_text("{}")
        monkeypatch.setattr(
            cli, "_dataset_resolver_loader", lambda: lambda **_: client
        )
        result = CliRunner().invoke(
            cli.app,
            [
                "source-structure",
                resource_id,
                "--trust-file",
                str(trust),
                "--metadata-root",
                str(tmp_path),
                "--schema-file",
                str(schema),
                "--view",
                "fields",
                "--column",
                "source_field_id",
                "--column",
                "value",
                "--limit",
                "2",
                "--offset",
                "2",
            ],
        )
        assert result.exit_code == 0, result.stderr
        cli_page = json.loads(result.stdout)
        assert cli_page["rows"] == later_body["rows"]
        assert cli_page["query_sha256"] == later_body["query_sha256"]
        assert (
            cli_page["identity"]["object_sha256"]
            == body["identity"]["object_sha256"]
        )


@pytest.mark.parametrize("engine", ["duckdb", "polars"])
def test_native_field_pages_are_bounded_and_bind_the_offset(engine):
    with resolver(native_field_collection_payload()) as client:
        service = PlatinumQueryService(client)
        first = service.query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(
                columns=("source_field_id",),
                field_collection="native_fields",
                limit=1,
            ),
        )
        second = service.query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(
                columns=("source_field_id",),
                field_collection="native_fields",
                limit=1,
                offset=1,
            ),
        )
        third = service.query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(
                columns=("source_field_id",),
                field_collection="native_fields",
                limit=2,
                offset=2,
            ),
        )
        assert first.rows == ({"source_field_id": "a/text"},)
        assert second.rows == ({"source_field_id": "a/attribute"},)
        assert third.rows == ({"source_field_id": "d/text"},)
        assert (
            first.query_receipt.query_sha256
            != second.query_receipt.query_sha256
        )
        assert json.loads(second.query_receipt.canonical_query)["offset"] == 1


@pytest.mark.parametrize("offset", [-1, True, 100_000_001])
def test_query_rejects_invalid_page_offsets_before_read(offset):
    with (
        resolver(native_field_collection_payload()) as client,
        pytest.raises(ValueError, match="offset"),
    ):
        PlatinumQueryService(client).query(
            "au.mbs.service-items",
            engine="polars",
            spec=QuerySpec(
                columns=("source_field_id",),
                field_collection="native_fields",
                offset=offset,
            ),
        )


@pytest.mark.parametrize("engine", ["duckdb", "polars"])
def test_flat_source_records_are_reachable_on_later_pages(engine):
    with resolver(parquet_payload()) as client:
        service = PlatinumQueryService(client)
        original = service.query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(columns=("item_code",), limit=1),
        )
        later = service.query(
            "au.mbs.service-items",
            engine=engine,
            spec=QuerySpec(columns=("item_code",), limit=1, offset=1),
        )
    assert original.rows == ({"item_code": "100"},)
    assert later.rows == ({"item_code": "200"},)
    assert (
        json.loads(original.query_receipt.canonical_query)["version"] == "1.0"
    )
    assert json.loads(later.query_receipt.canonical_query)["offset"] == 1
    assert (
        original.query_receipt.query_sha256 != later.query_receipt.query_sha256
    )


def test_source_structure_qualification_exercises_actual_consumers(
    monkeypatch, tmp_path
):
    def loader(**_kwargs):
        return resolver(
            native_field_collection_payload(),
            semantic_dimension="source_structure",
        )

    monkeypatch.setattr(qualification, "load_benefits_resolver", loader)
    monkeypatch.setattr(cli, "_dataset_resolver_loader", lambda: loader)
    trust_file = tmp_path / "trust.json"
    schema_file = tmp_path / "schema.json"
    trust_file.write_text("{}")
    schema_file.write_text("{}")
    receipt = qualification.qualify_structure_consumers(
        trust_file=trust_file,
        metadata_root=tmp_path,
        schema_file=schema_file,
        resource_id="au.mbs.service-items",
        columns=("source_field_id", "value"),
        view="fields",
        limit=2,
    )
    assert receipt["status"] == "passed"
    assert receipt["consumers"] == ["api_v2", "cli", "atlas"]
    assert receipt["row_count"] == 2
    assert "a/text" not in json.dumps(receipt)
