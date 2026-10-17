"""Tests for the candidate-only MBS Gold scalar consumer bridge."""

import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient
from test_mbs_gold_graph import (
    _admitted_input,  # ruff: ignore[import-private-name] -- shared fixture
    _admitted_table,  # ruff: ignore[import-private-name] -- shared fixture
)
from test_mbs_gold_graph import (
    graph as synthetic_graph,
)
from test_platinum_benefits_api import service as benefits_service

import global_medicines_atlas.mbs_gold_graph as graph_module
import global_medicines_atlas.mbs_gold_scalar_projection as projection_module
from global_medicines_atlas.api import create_app
from global_medicines_atlas.australian_source_contracts import (
    mbs_field_contracts,
)
from global_medicines_atlas.mbs_gold_graph import (
    MbsGoldFieldEvidence,
    MbsGoldGraphCandidate,
    build_mbs_gold_graph_from_admitted_silver,
)
from global_medicines_atlas.mbs_gold_scalar_projection import (
    project_mbs_gold_scalar_candidate,
)
from global_medicines_atlas.mbs_typed_values import ConversionStatus
from global_medicines_atlas.platinum_benefits import BenefitsPage
from global_medicines_atlas.query_service import ReadOnlyQueryService
from global_medicines_atlas.receipts import (
    SensitivityClassification,
    SourceReceipt,
)

_ROOT = Path(__file__).resolve().parents[1]
_RECEIPT = (
    _ROOT
    / "quality/bronze/receipts/au-mbs/bbd662119ebebfdf08baf14c0b15c0dd5c93465910fd4f5309f37ecd37a82b8d.json"
)


def _real_candidate():
    benefits = _typed_benefits("Benefit100", ["10.25", "2.75"], "converted")
    graph = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        benefits,
        _admitted_input(),
    )
    receipt = SourceReceipt.model_validate_json(_RECEIPT.read_bytes())
    return graph, receipt


def _candidate_parquet(field_name: str, values: list[str]) -> tuple[bytes, str]:
    graph = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        _typed_benefits(field_name, values, "converted"),
        _admitted_input(),
    )
    receipt = SourceReceipt.model_validate_json(_RECEIPT.read_bytes())
    projected = project_mbs_gold_scalar_candidate(graph, receipt)
    sink = io.BytesIO()
    pq.write_table(projected, sink)
    payload = sink.getvalue()
    round_tripped = pq.read_table(io.BytesIO(payload))
    metadata = round_tripped.schema.metadata or {}
    assert metadata[b"qualification"] == b"candidate_only"
    assert metadata[b"consumer_admission"] == b"not_performed"
    return payload, f"benefit__{field_name}__typed_value"


def _benefits_client(payload: bytes) -> TestClient:
    return TestClient(
        create_app(
            cast("ReadOnlyQueryService", object()),
            benefits=benefits_service(payload=payload),
        )
    )


def _typed_benefits(
    native_name: str, values: list[str], status: str
) -> pa.Table:
    table = _admitted_table("benefits", native_name)
    rows = table.to_pylist()
    for row, value in zip(rows, values, strict=True):
        row[native_name] = {
            "native_value": value,
            "native_state": "value",
            "conversion_status": status,
            "typed_value": value if status == "converted" else None,
        }
    return pa.Table.from_pylist(rows, schema=table.schema)


def test_scalar_projection_preserves_row_states_and_governed_bindings():
    graph, receipt = _real_candidate()
    result = project_mbs_gold_scalar_candidate(graph, receipt)

    assert result.num_rows == graph.source_record_count
    assert result.column("source_record_id").to_pylist() == [
        f"au-mbs:3::2025-07-{ordinal}" for ordinal in range(2)
    ]
    assert result.column("service__ItemNum__native_state").to_pylist() == [
        "value",
        "value",
    ]
    assert result.column(
        "benefit__Benefit100__typed_value_text"
    ).to_pylist() == ["10.25", "2.75"]
    assert result.schema.field(
        "benefit__Benefit100__typed_value"
    ).type == pa.decimal128(38, 9)
    assert result.column("benefit__Benefit100__typed_value").to_pylist() == [
        Decimal("10.25"),
        Decimal("2.75"),
    ]
    assert result.column("source_effective_at").to_pylist() == [None, None]
    assert result.column("valid_time_status").to_pylist() == [
        "source_snapshot_effective_date",
        "source_snapshot_effective_date",
    ]
    assert result.column("source_snapshot_effective_date").to_pylist() == [
        "2025-07-01",
        "2025-07-01",
    ]
    graph_sensitivity = cast(
        "list[str]", result.column("sensitivity_json").to_pylist()
    )
    receipt_sensitivity = cast(
        "list[str]",
        result.column("source_receipt_sensitivity_json").to_pylist(),
    )
    assert '"data_sensitivity":"unknown"' in graph_sensitivity[0]
    assert '"data_sensitivity":"non_sensitive"' in receipt_sensitivity[0]
    metadata = result.schema.metadata or {}
    assert metadata[b"qualification"] == b"candidate_only"
    assert metadata[b"consumer_admission"] == b"not_performed"
    assert (
        metadata[b"value_representation"] == b"contract_bound_arrow_scalars_v1"
    )
    assert metadata[b"source_receipt_sha256"].decode() == receipt.digest()
    assert (
        metadata[b"acquisition_id"].decode() == receipt.temporal.acquisition_id
    )


def test_projection_decodes_only_contract_bound_decimal_and_date_values():
    _graph, receipt = _real_candidate()
    date_graph = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        _typed_benefits(
            "BenefitStartDate", ["2025-07-01", "2025-08-01"], "converted"
        ),
        _admitted_input(),
    )
    projected = project_mbs_gold_scalar_candidate(date_graph, receipt)
    assert (
        projected.schema.field("benefit__BenefitStartDate__typed_value").type
        == pa.date32()
    )
    assert projected.column(
        "benefit__BenefitStartDate__typed_value"
    ).to_pylist() == [date(2025, 7, 1), date(2025, 8, 1)]

    bad_decimal = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        _typed_benefits("Benefit100", ["10.1234567891", "2.75"], "converted"),
        _admitted_input(),
    )
    with pytest.raises(ValueError, match="exact decimal128"):
        project_mbs_gold_scalar_candidate(bad_decimal, receipt)


@pytest.mark.parametrize(
    ("native_name", "status", "typed_value", "schema_era", "message"),
    [
        (
            "Benefit100",
            "invalid",
            "1",
            "2025-07-version-3",
            "non-converted",
        ),
        (
            "Benefit100",
            "converted",
            "not-a-decimal",
            "2025-07-version-3",
            "exact decimal128",
        ),
        (
            "BenefitStartDate",
            "converted",
            "2025-07-01",
            "other-era",
            "qualified source era",
        ),
        (
            "BenefitStartDate",
            "converted",
            "01.07.2025",
            "2025-07-version-3",
            "canonical ISO",
        ),
        (
            "ItemNum",
            "converted",
            "001",
            "2025-07-version-3",
            "text MBS field",
        ),
    ],
)
def test_typed_scalar_conversion_fails_closed_on_contract_mismatch(
    native_name: str,
    status: ConversionStatus,
    typed_value: str,
    schema_era: str,
    message: str,
):
    field = MbsGoldFieldEvidence(
        native_name=native_name,
        native_state="value",
        native_value="native",
        conversion_status=status,
        typed_value=typed_value,
    )
    contract = next(
        item
        for item in mbs_field_contracts()
        if item.native_name == native_name
    )
    with pytest.raises(ValueError, match=message):
        projection_module._typed_value(field, contract, schema_era)


def test_scalar_projection_is_deterministic_and_rejects_receipt_tampering():
    graph, receipt = _real_candidate()
    first = project_mbs_gold_scalar_candidate(graph, receipt)
    second = project_mbs_gold_scalar_candidate(graph, receipt)
    assert first.equals(second, check_metadata=True)

    changed = receipt.model_copy(update={"receipt_id": "forged"})
    with pytest.raises(ValueError, match="receipt differs"):
        project_mbs_gold_scalar_candidate(graph, changed)

    missing_temporal = receipt.model_copy(update={"temporal": None})
    with pytest.raises(ValueError, match="lacks acquisition identity"):
        projection_module._validate_receipt_binding(graph, missing_temporal)


def test_scalar_projection_rejects_synthetic_graph():
    _graph, receipt = _real_candidate()
    with pytest.raises(ValueError, match="admitted real Silver"):
        project_mbs_gold_scalar_candidate(synthetic_graph(), receipt)


def test_scalar_projection_rejects_mixed_source_payload_cohorts():
    graph, receipt = _real_candidate()
    source_record_id = graph.edges[0].evidence.source_record_id
    node_id_map = {}
    changed_nodes = []
    for node in graph.nodes:
        if node.evidence.source_record_id != source_record_id:
            changed_nodes.append(node)
            continue
        evidence = node.evidence.model_copy(update={"source_sha256": "a" * 64})
        changed = node.model_copy(
            update={
                "evidence": evidence,
                "node_id": graph_module._node_id(
                    node.kind, evidence, node.fields
                ),
            }
        )
        node_id_map[node.node_id] = changed.node_id
        changed_nodes.append(changed)

    changed_edges = []
    for edge in graph.edges:
        if edge.evidence.source_record_id != source_record_id:
            changed_edges.append(edge)
            continue
        evidence = edge.evidence.model_copy(update={"source_sha256": "a" * 64})
        source_id = node_id_map[edge.source_node_id]
        target_id = node_id_map[edge.target_node_id]
        changed_edges.append(
            edge.model_copy(
                update={
                    "evidence": evidence,
                    "source_node_id": source_id,
                    "target_node_id": target_id,
                    "edge_id": graph_module._edge_id(
                        source_id, target_id, evidence
                    ),
                }
            )
        )

    body = graph.model_dump()
    body["nodes"] = [
        node.model_dump()
        for node in sorted(changed_nodes, key=lambda item: item.node_id)
    ]
    body["edges"] = [
        edge.model_dump()
        for edge in sorted(changed_edges, key=lambda item: item.edge_id)
    ]
    body["graph_sha256"] = graph_module._digest({
        key: value for key, value in body.items() if key != "graph_sha256"
    })
    mixed = MbsGoldGraphCandidate.model_validate(body)

    with pytest.raises(ValueError, match="receipt differs"):
        project_mbs_gold_scalar_candidate(mixed, receipt)


def test_scalar_projection_parquet_reaches_benefits_api_with_exact_decimal():
    """Exercise only a synthetic product wrapper, not real admission."""
    payload, value_column = _candidate_parquet("Benefit100", ["10.25", "2.75"])
    filters = (
        '[{"column":'
        + json.dumps(value_column)
        + ',"operator":">=","value":10.00}]'
    )

    response = _benefits_client(payload).get(
        "/api/v1/benefits/au.mbs.service-items",
        params=[
            ("columns", "source_record_id"),
            ("columns", value_column),
            ("filters", filters),
            ("limit", "2"),
        ],
    )

    assert response.status_code == 200, response.json()
    page = BenefitsPage.model_validate(response.json())
    assert page.identity.comparison_cohort == "synthetic"
    assert page.review_state == "not_declared"
    assert page.rows == (
        {
            "source_record_id": "au-mbs:3::2025-07-0",
            value_column: "10.250000000",
        },
    )


def test_scalar_projection_parquet_reaches_benefits_api_with_date_filter():
    """Exercise tagged date filters under a synthetic product wrapper."""
    payload, value_column = _candidate_parquet(
        "BenefitStartDate", ["2025-07-01", "2025-08-01"]
    )
    filters = json.dumps([
        {
            "column": value_column,
            "operator": "=",
            "value": {"type": "date", "value": "2025-07-01"},
        }
    ])

    response = _benefits_client(payload).get(
        "/api/v1/benefits/au.mbs.service-items",
        params=[
            ("columns", "source_record_id"),
            ("columns", value_column),
            ("filters", filters),
            ("limit", "2"),
        ],
    )

    assert response.status_code == 200, response.json()
    page = BenefitsPage.model_validate(response.json())
    assert page.identity.comparison_cohort == "synthetic"
    assert page.review_state == "not_declared"
    assert page.rows == (
        {
            "source_record_id": "au-mbs:3::2025-07-0",
            value_column: "2025-07-01",
        },
    )


def test_field_contract_rejects_missing_classes_mixed_fields_and_bad_names():
    graph, _ = _real_candidate()
    with pytest.raises(ValueError, match="missing a required node class"):
        projection_module._validate_field_contract(
            graph.model_copy(
                update={
                    "nodes": tuple(
                        node
                        for node in graph.nodes
                        if node.kind == "mbs_service_record"
                    )
                }
            )
        )

    alternate = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemType"),
        _admitted_table("benefits", "Benefit100"),
        _admitted_input(),
    )
    mixed_nodes = list(graph.nodes)
    original = next(
        node
        for node in mixed_nodes
        if node.kind == "mbs_service_record"
        and node.evidence.source_ordinal == 0
    )
    alternate_node = next(
        node
        for node in alternate.nodes
        if node.kind == "mbs_service_record"
        and node.evidence.source_ordinal == 0
    )
    mixed_nodes[mixed_nodes.index(original)] = alternate_node
    with pytest.raises(ValueError, match="field denominator differs"):
        projection_module._validate_field_contract(
            graph.model_copy(update={"nodes": tuple(mixed_nodes)})
        )

    invalid_field = MbsGoldFieldEvidence(
        native_name="bad.name",
        native_state="value",
        native_value="x",
        conversion_status="preserved",
        typed_value="x",
    )
    invalid_nodes = tuple(
        node.model_copy(update={"fields": (invalid_field,)})
        if node.kind == "mbs_service_record"
        else node
        for node in graph.nodes
    )
    with pytest.raises(ValueError, match="cannot form a scalar column"):
        projection_module._validate_field_contract(
            graph.model_copy(update={"nodes": invalid_nodes})
        )

    wrong_table_field = MbsGoldFieldEvidence(
        native_name="Benefit100",
        native_state="value",
        native_value="1.00",
        conversion_status="converted",
        typed_value="1.00",
    )
    wrong_table_nodes = tuple(
        node.model_copy(update={"fields": (wrong_table_field,)})
        if node.kind == "mbs_service_record"
        else node
        for node in graph.nodes
    )
    with pytest.raises(ValueError, match="table contract"):
        projection_module._validate_field_contract(
            graph.model_copy(update={"nodes": wrong_table_nodes})
        )


def test_record_flattening_rejects_cross_record_pairing():
    graph, receipt = _real_candidate()
    service = next(
        node
        for node in graph.nodes
        if node.kind == "mbs_service_record"
        and node.evidence.source_ordinal == 0
    )
    benefit = next(
        node
        for node in graph.nodes
        if node.kind == "mbs_benefit_record"
        and node.evidence.source_ordinal == 1
    )
    edge = graph.edges[0]
    temporal = receipt.temporal
    assert temporal is not None
    with pytest.raises(ValueError, match="crosses source records"):
        projection_module._record_values(
            service,
            benefit,
            edge,
            temporal,
            receipt.sensitivity or SensitivityClassification(),
        )
