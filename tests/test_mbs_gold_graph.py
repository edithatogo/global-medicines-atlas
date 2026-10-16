"""MBS Gold graph candidates preserve explicit synthetic and admitted evidence."""

# pyright: reportPrivateUsage=false
# pyright: reportUnknownMemberType=false

from datetime import UTC, date, datetime
from io import BytesIO
from operator import attrgetter, itemgetter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError
from test_mbs_silver import (
    _receipt,  # ruff: ignore[import-private-name] -- shared synthetic fixture
    _xml,  # ruff: ignore[import-private-name] -- shared synthetic fixture
)

import global_medicines_atlas.mbs_gold_graph as gold_graph_module
from global_medicines_atlas.mbs_gold_graph import (
    MBS_GOLD_EDGE_SCHEMA,
    MBS_GOLD_NODE_SCHEMA,
    MbsGoldAdmittedSilverInput,
    MbsGoldEdge,
    MbsGoldFieldEvidence,
    MbsGoldGraphCandidate,
    MbsGoldNode,
    _edge_id,  # ruff: ignore[import-private-name] -- adversarial contract test
    _node_id,  # ruff: ignore[import-private-name] -- adversarial contract test
    build_mbs_gold_graph_candidate,
    build_mbs_gold_graph_from_admitted_silver,
    project_mbs_gold_graph_arrow,
)
from global_medicines_atlas.receipts import EvidenceClass, RightsState

REAL_SOURCE_SHA256 = (
    "db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556"
)
REAL_RECEIPT_SHA256 = (
    "c8c3e3baeee4c08dba1a944c19652ec184d90de850968fc4d6a124747d994e03"
)
REAL_RETRIEVED_AT = "2026-09-27T20:37:32.916888+00:00"


def _admitted_table(name: str, native_field: str) -> pa.Table:
    metadata = {
        "schema_name": f"global-medicines-atlas.mbs-silver.{name}",
        "schema_version": "1.1",
        "source_id": "au-mbs",
        "subject_kind": "service",
        "dimension": "service_benefit",
        "absence_interpretation": "unknown",
        "mapping_status": "source_native",
        "qualification": "candidate",
        "conversion_version": "mbs-scalar-v2",
        "source_receipt_sha256": REAL_RECEIPT_SHA256,
        "source_uri": "https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive",
        "retrieved_at": REAL_RETRIEVED_AT,
        "rights_state": "permitted",
        "evidence_class": "live",
        "schema_era": "2025-07-version-3",
        "source_record_count": "2",
    }
    rows = [
        {
            "source_record_id": f"au-mbs:3::2025-07-{ordinal}",
            "source_ordinal": ordinal,
            "source_sha256": REAL_SOURCE_SHA256,
            "receipt_sha256": REAL_RECEIPT_SHA256,
            native_field: {
                "native_value": str(ordinal + 1),
                "native_state": "value",
                "conversion_status": "preserved",
                "typed_value": str(ordinal + 1),
            },
        }
        for ordinal in range(2)
    ]
    return pa.Table.from_pylist(rows).replace_schema_metadata({
        key.encode(): value.encode() for key, value in metadata.items()
    })


def _admitted_input() -> MbsGoldAdmittedSilverInput:
    return MbsGoldAdmittedSilverInput(
        source_sha256=REAL_SOURCE_SHA256,
        receipt_sha256=REAL_RECEIPT_SHA256,
        catalog_version="2025-07-version-3",
        source_record_count=2,
        source_effective_date=date(2025, 7, 1),
        retrieved_at=datetime.fromisoformat(REAL_RETRIEVED_AT),
        rights_state=RightsState.PERMITTED,
        admission_sha256="a" * 64,
        semantic_manifest_sha256="b" * 64,
    )


def graph(count: int = 2) -> MbsGoldGraphCandidate:
    payload = _xml(
        "<BenefitType>A</BenefitType><Benefit100>42.50</Benefit100>",
        count=count,
    )
    return build_mbs_gold_graph_candidate(payload, _receipt(payload))


def test_explicit_service_benefit_edges_preserve_every_silver_record():
    result = graph()
    assert result.qualification == "synthetic_silver_candidate_only"
    assert result.admission_performed is False
    assert result.terminology_linking_performed is False
    assert result.publication_performed is False
    assert result.source_record_count == 2
    assert result.graph_sha256 == (
        "78cde38b55da2c051168a96f77008809f19316444c5d7bf78bc8dbda8c52647c"
    )
    assert len(result.nodes) == 4
    assert len(result.edges) == 2
    by_id = {node.node_id: node for node in result.nodes}
    for edge in result.edges:
        assert edge.inferred is False
        assert edge.assertion_basis == "same_source_record"
        assert edge.mapping_method == "source-explicit"
        assert edge.confidence is None
        assert edge.review_state == "not_reviewed"
        assert edge.valid_time_status == "unselected"
        assert edge.supporting_revisions == ("synthetic-iso-v1",)
        assert edge.evidence.catalog_version == "synthetic-iso-v1"
        assert edge.contradiction_edge_ids == ()
        assert edge.supersedes_edge_ids == ()
        assert edge.negative_control_outcome == "not_applicable"
        assert by_id[edge.source_node_id].kind == "mbs_service_record"
        assert by_id[edge.target_node_id].kind == "mbs_benefit_record"
        assert by_id[edge.source_node_id].evidence == edge.evidence
        benefit = by_id[edge.target_node_id]
        values = {field.native_name: field for field in benefit.fields}
        assert values["Benefit100"].native_value == "42.50"
        assert values["Benefit100"].typed_value == "42.500000000"


def test_graph_and_arrow_projection_are_deterministic_and_portable():
    result = graph()
    assert result == graph()
    assert (
        MbsGoldGraphCandidate.model_validate_json(result.model_dump_json())
        == result
    )
    nodes, edges = project_mbs_gold_graph_arrow(result)
    assert nodes.schema == MBS_GOLD_NODE_SCHEMA
    assert edges.schema == MBS_GOLD_EDGE_SCHEMA
    assert edges.column("inferred").to_pylist() == [False, False]
    for table in (nodes, edges):
        output = BytesIO()
        pq.write_table(table, output)
        assert pq.read_table(BytesIO(output.getvalue())).equals(
            table, check_metadata=True
        )


def test_frozen_v2_graph_receipt_remains_readable_and_digest_stable():
    legacy_path = (
        Path(__file__).parent / "fixtures/mbs_gold_graph_v2_synthetic.json"
    )
    legacy_bytes = legacy_path.read_bytes()
    result = MbsGoldGraphCandidate.model_validate_json(legacy_bytes)
    assert result.schema_version == 2
    assert result.qualification == "synthetic_silver_candidate_only"
    assert result.graph_sha256 == (
        "78cde38b55da2c051168a96f77008809f19316444c5d7bf78bc8dbda8c52647c"
    )
    serialized = result.model_dump(mode="json")
    assert "input_admission_sha256" not in serialized
    assert "input_semantic_manifest_sha256" not in serialized
    assert all(
        "source_snapshot_effective_date" not in edge
        for edge in serialized["edges"]
    )
    nodes, edges = project_mbs_gold_graph_arrow(result)
    assert nodes.schema.metadata == MBS_GOLD_NODE_SCHEMA.metadata
    assert edges.schema.metadata == MBS_GOLD_EDGE_SCHEMA.metadata


def test_admitted_real_silver_graph_preserves_provenance_and_scope():
    result = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        _admitted_table("benefits", "Benefit100"),
        _admitted_input(),
    )
    assert result.qualification == "admitted_real_silver_candidate_only"
    assert result.schema_version == 3
    assert result.admission_performed is False
    assert result.input_admission_sha256 == "a" * 64
    assert result.input_semantic_manifest_sha256 == "b" * 64
    assert result.source_record_count == 2
    assert len(result.nodes) == 4
    assert len(result.edges) == 2
    assert all(
        edge.valid_time_status == "source_snapshot_effective_date"
        for edge in result.edges
    )
    assert all(
        edge.source_snapshot_effective_date == date(2025, 7, 1)
        for edge in result.edges
    )
    assert all(edge.review_state == "not_reviewed" for edge in result.edges)
    assert all(
        edge.negative_control_outcome == "not_applicable"
        for edge in result.edges
    )
    nodes, edges = project_mbs_gold_graph_arrow(result)
    assert nodes.schema.metadata[b"qualification"] == (
        b"admitted_real_silver_candidate_only"
    )
    assert edges.schema.metadata[b"qualification"] == (
        b"admitted_real_silver_candidate_only"
    )
    assert nodes.schema.metadata[b"schema_version"] == b"3.0"
    assert edges.schema.metadata[b"schema_version"] == b"3.0"
    assert edges.schema.metadata[b"input_admission_sha256"] == b"a" * 64
    assert edges.schema.metadata[b"input_semantic_manifest_sha256"] == (
        b"b" * 64
    )
    assert (
        edges.schema.metadata[b"graph_sha256"] == result.graph_sha256.encode()
    )
    for key in (
        b"qualification",
        b"schema_version",
        b"input_admission_sha256",
        b"input_semantic_manifest_sha256",
        b"graph_sha256",
    ):
        assert nodes.schema.metadata[key] == edges.schema.metadata[key]

    changed_binding = build_mbs_gold_graph_from_admitted_silver(
        _admitted_table("services", "ItemNum"),
        _admitted_table("benefits", "Benefit100"),
        _admitted_input().model_copy(
            update={
                "admission_sha256": "c" * 64,
                "semantic_manifest_sha256": "d" * 64,
            }
        ),
    )
    changed_nodes, changed_edges = project_mbs_gold_graph_arrow(changed_binding)
    assert changed_binding.graph_sha256 != result.graph_sha256
    assert not nodes.equals(changed_nodes, check_metadata=True)
    assert not edges.equals(changed_edges, check_metadata=True)
    for table in (nodes, edges, changed_nodes, changed_edges):
        output = BytesIO()
        pq.write_table(table, output)
        restored = pq.read_table(BytesIO(output.getvalue()))
        assert restored.equals(table, check_metadata=True)
        assert restored.schema.metadata == table.schema.metadata


def test_admitted_real_silver_graph_rejects_cross_receipt_or_unpermitted_input():
    services = _admitted_table("services", "ItemNum")
    benefits = _admitted_table("benefits", "Benefit100")
    bad_metadata = dict(benefits.schema.metadata or {})
    bad_metadata[b"source_receipt_sha256"] = b"0" * 64
    with pytest.raises(ValueError, match="metadata differs"):
        build_mbs_gold_graph_from_admitted_silver(
            services,
            benefits.replace_schema_metadata(bad_metadata),
            _admitted_input(),
        )
    with pytest.raises(ValueError, match="permitted"):
        build_mbs_gold_graph_from_admitted_silver(
            services,
            benefits,
            _admitted_input().model_copy(
                update={"rights_state": RightsState.UNKNOWN}
            ),
        )


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        ("source_sha256", REAL_SOURCE_SHA256),
        ("receipt_sha256", REAL_RECEIPT_SHA256),
    ],
)
def test_admitted_real_silver_graph_rejects_paired_forged_row_digests(
    column: str, expected: str
):
    services = _admitted_table("services", "ItemNum")
    benefits = _admitted_table("benefits", "Benefit100")
    forged = "0" * 64
    assert expected != forged
    for table_name, table in (("services", services), ("benefits", benefits)):
        index = table.schema.get_field_index(column)
        changed = table.set_column(
            index,
            table.schema.field(index),
            pa.array([forged] * table.num_rows, type=pa.string()),
        )
        if table_name == "services":
            services = changed
        else:
            benefits = changed
    with pytest.raises(ValueError, match="admitted digests"):
        build_mbs_gold_graph_from_admitted_silver(
            services, benefits, _admitted_input()
        )


@pytest.mark.parametrize(
    ("validity", "snapshot_date", "message"),
    [
        ("source_snapshot_effective_date", None, "snapshot date must preserve"),
        ("unselected", date(2025, 7, 1), "unselected validity cannot carry"),
    ],
)
def test_gold_edge_rejects_invalid_snapshot_date_binding(
    validity: str, snapshot_date: date | None, message: str
) -> None:
    edge = graph().edges[0].model_dump()
    edge["valid_time_status"] = validity
    edge["source_snapshot_effective_date"] = snapshot_date
    with pytest.raises(ValidationError, match=message):
        MbsGoldEdge.model_validate(edge)


@pytest.mark.parametrize(
    ("qualification", "schema_version", "admission", "semantic", "message"),
    [
        (
            "synthetic_silver_candidate_only",
            3,
            None,
            None,
            "synthetic Gold graph must retain schema v2",
        ),
        (
            "synthetic_silver_candidate_only",
            2,
            "a" * 64,
            "b" * 64,
            "synthetic Gold graph cannot claim real Silver admission",
        ),
        (
            "admitted_real_silver_candidate_only",
            2,
            "a" * 64,
            "b" * 64,
            "admitted real Silver Gold graph requires schema v3",
        ),
        (
            "admitted_real_silver_candidate_only",
            3,
            None,
            None,
            "real Silver Gold graph requires both admission digests",
        ),
    ],
)
def test_gold_candidate_rejects_inconsistent_admission_binding(
    qualification: str,
    schema_version: int,
    admission: str | None,
    semantic: str | None,
    message: str,
) -> None:
    candidate = graph().model_dump()
    candidate.update(
        qualification=qualification,
        schema_version=schema_version,
        input_admission_sha256=admission,
        input_semantic_manifest_sha256=semantic,
    )
    with pytest.raises(ValidationError, match=message):
        MbsGoldGraphCandidate.model_validate(candidate)


def test_admitted_real_silver_graph_checks_row_denominator_and_identity() -> (
    None
):
    services = _admitted_table("services", "ItemNum")
    benefits = _admitted_table("benefits", "Benefit100")
    with pytest.raises(ValueError, match="row count differs"):
        build_mbs_gold_graph_from_admitted_silver(
            services,
            benefits,
            _admitted_input().model_copy(update={"source_record_count": 3}),
        )

    services_without_ordinal = services.remove_column(
        services.schema.get_field_index("source_ordinal")
    )
    with pytest.raises(ValueError, match="lacks source row identity"):
        build_mbs_gold_graph_from_admitted_silver(
            services_without_ordinal, benefits, _admitted_input()
        )

    mismatched_benefits = benefits.set_column(
        benefits.schema.get_field_index("source_record_id"),
        benefits.schema.field("source_record_id"),
        pa.array(["other:record:0", "other:record:1"], type=pa.string()),
    )
    with pytest.raises(ValueError, match="row identities do not pair exactly"):
        build_mbs_gold_graph_from_admitted_silver(
            services, mismatched_benefits, _admitted_input()
        )


def test_admitted_real_silver_graph_rejects_empty_projected_denominator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def skip_table_validation(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(
        gold_graph_module,
        "_validate_admitted_silver_table",
        skip_table_validation,
    )
    with pytest.raises(ValueError, match="denominators differ"):
        build_mbs_gold_graph_from_admitted_silver(
            pa.table({}), pa.table({}), _admitted_input()
        )


def test_live_receipts_are_out_of_scope_before_projection():
    payload = _xml()
    receipt = _receipt(payload).model_copy(
        update={"evidence_class": EvidenceClass.LIVE}
    )
    with pytest.raises(ValueError, match="synthetic evidence"):
        build_mbs_gold_graph_candidate(payload, receipt)


def test_canonical_temporal_receipt_clocks_are_projected_without_retrieval_fill():
    payload = _xml()
    receipt = _receipt(payload)
    assert receipt.temporal is not None
    valid_from = datetime(2026, 7, 1, tzinfo=UTC)
    valid_to = datetime(2026, 8, 1, tzinfo=UTC)
    receipt = receipt.model_copy(
        update={
            "temporal": receipt.temporal.model_copy(
                update={
                    "source_effective_at": datetime(2026, 6, 1, tzinfo=UTC),
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                }
            )
        }
    )
    edge = build_mbs_gold_graph_candidate(payload, receipt).edges[0]
    assert receipt.temporal is not None
    assert edge.source_effective_from == valid_from
    assert edge.source_effective_to == valid_to
    assert edge.retrieved_at == receipt.temporal.retrieved_at


def test_source_effective_clock_is_preserved_when_no_valid_interval_exists():
    payload = _xml()
    receipt = _receipt(payload)
    assert receipt.temporal is not None
    source_effective_at = datetime(2026, 6, 1, tzinfo=UTC)
    receipt = receipt.model_copy(
        update={
            "temporal": receipt.temporal.model_copy(
                update={"source_effective_at": source_effective_at}
            )
        }
    )
    edge = build_mbs_gold_graph_candidate(payload, receipt).edges[0]
    assert edge.source_effective_from == source_effective_at
    assert edge.source_effective_to is None


def test_unrepresentable_silver_values_remain_graph_evidence():
    payload = _xml("<Benefit100>0.1234567891</Benefit100>")
    result = build_mbs_gold_graph_candidate(payload, _receipt(payload))
    benefit = next(
        node for node in result.nodes if node.kind == "mbs_benefit_record"
    )
    field = next(
        field for field in benefit.fields if field.native_name == "Benefit100"
    )
    assert field.native_value == "0.1234567891"
    assert field.conversion_status == "unrepresentable"
    assert field.typed_value is None


def test_field_node_edge_and_graph_tampering_fail_closed():
    result = graph(1)
    with pytest.raises(ValidationError, match="native state"):
        MbsGoldFieldEvidence(
            native_name="Benefit100",
            native_state="value",
            native_value=None,
            conversion_status="null",
            typed_value=None,
        )
    node = result.nodes[0]
    changed_node = node.model_dump()
    changed_node["node_id"] = "mbs-gold-node:" + "0" * 64
    with pytest.raises(ValidationError, match="node identity"):
        MbsGoldNode.model_validate(changed_node)
    edge = result.edges[0]
    changed_edge = edge.model_dump()
    changed_edge["edge_id"] = "mbs-gold-edge:" + "0" * 64
    with pytest.raises(ValidationError, match="edge identity"):
        MbsGoldEdge.model_validate(changed_edge)
    changed_edge = edge.model_dump()
    changed_edge["contradiction_edge_ids"] = ("mbs-gold-edge:" + "0" * 64,)
    with pytest.raises(ValidationError, match="graph history"):
        MbsGoldEdge.model_validate(changed_edge)
    changed_edge = edge.model_dump()
    changed_edge["supporting_revisions"] = ("other-revision",)
    with pytest.raises(ValidationError, match="revision differs"):
        MbsGoldEdge.model_validate(changed_edge)
    changed_graph = result.model_dump()
    changed_graph["edges"][0]["source_node_id"] = changed_graph["edges"][0][
        "target_node_id"
    ]
    with pytest.raises(ValidationError):
        MbsGoldGraphCandidate.model_validate(changed_graph)
    changed_graph = result.model_dump()
    changed_graph["graph_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="graph digest"):
        MbsGoldGraphCandidate.model_validate(changed_graph)


def test_graph_requires_records_and_receipt_matching_bytes():
    empty = b"<MBS_XML></MBS_XML>"
    with pytest.raises(ValueError, match="no Data records"):
        build_mbs_gold_graph_candidate(empty, _receipt(empty))
    payload = _xml()
    with pytest.raises(ValueError, match="source bytes"):
        build_mbs_gold_graph_candidate(payload, _receipt(b"other"))


def test_arrow_projection_revalidates_graph():
    result = graph(1)
    forged = result.model_copy(update={"graph_sha256": "0" * 64})
    with pytest.raises(ValidationError, match="graph digest"):
        project_mbs_gold_graph_arrow(forged)


def test_graph_order_uniqueness_denominator_and_edge_support_are_validated():
    result = graph(2)
    changed = result.model_dump()
    changed["nodes"] = changed["nodes"][::-1]
    with pytest.raises(ValidationError, match="nodes are not deterministic"):
        MbsGoldGraphCandidate.model_validate(changed)
    changed = result.model_dump()
    changed["edges"] = changed["edges"][::-1]
    with pytest.raises(ValidationError, match="edges are not deterministic"):
        MbsGoldGraphCandidate.model_validate(changed)
    changed = result.model_dump()
    changed["nodes"] = list(changed["nodes"])
    changed["nodes"][1] = changed["nodes"][0]
    changed["nodes"] = sorted(changed["nodes"], key=itemgetter("node_id"))
    with pytest.raises(ValidationError, match="node identity is ambiguous"):
        MbsGoldGraphCandidate.model_validate(changed)
    changed = result.model_dump()
    changed["edges"] = list(changed["edges"])
    changed["edges"][1] = changed["edges"][0]
    with pytest.raises(ValidationError, match="edge identity is ambiguous"):
        MbsGoldGraphCandidate.model_validate(changed)
    changed = result.model_dump()
    changed["source_record_count"] = 1
    with pytest.raises(ValidationError, match="denominator differs"):
        MbsGoldGraphCandidate.model_validate(changed)

    edge = result.edges[0]
    absent = "mbs-gold-node:" + "0" * 64
    forged_edge = MbsGoldEdge(
        edge_id=_edge_id(edge.source_node_id, absent, edge.evidence),
        source_node_id=edge.source_node_id,
        target_node_id=absent,
        evidence=edge.evidence,
        supporting_revisions=edge.supporting_revisions,
        retrieved_at=edge.retrieved_at,
        rights_state=edge.rights_state,
    )
    changed = result.model_dump()
    changed["edges"] = list(changed["edges"])
    changed["edges"][0] = forged_edge.model_dump()
    changed["edges"] = sorted(changed["edges"], key=itemgetter("edge_id"))
    with pytest.raises(ValidationError, match="endpoint is absent"):
        MbsGoldGraphCandidate.model_validate(changed)

    services = [
        node for node in result.nodes if node.kind == "mbs_service_record"
    ]
    benefits = [
        node for node in result.nodes if node.kind == "mbs_benefit_record"
    ]
    other_benefit = next(
        node for node in benefits if node.evidence != services[0].evidence
    )
    mismatched = MbsGoldEdge(
        edge_id=_edge_id(
            services[0].node_id, other_benefit.node_id, services[0].evidence
        ),
        source_node_id=services[0].node_id,
        target_node_id=other_benefit.node_id,
        evidence=services[0].evidence,
        supporting_revisions=result.edges[0].supporting_revisions,
        retrieved_at=result.edges[0].retrieved_at,
        rights_state=result.edges[0].rights_state,
    )
    changed = result.model_dump()
    changed["edges"] = list(changed["edges"])
    matching_edge = next(
        index
        for index, edge in enumerate(result.edges)
        if edge.evidence == services[0].evidence
    )
    changed["edges"][matching_edge] = mismatched.model_dump()
    changed["edges"] = sorted(changed["edges"], key=itemgetter("edge_id"))
    with pytest.raises(ValidationError, match="same record"):
        MbsGoldGraphCandidate.model_validate(changed)


def test_graph_rejects_rights_metadata_mismatch_between_nodes_and_edges():
    candidate = graph()
    nodes = []
    node_ids = {}
    for node in candidate.nodes:
        evidence = node.evidence.model_copy(
            update={"rights_state": RightsState.PERMITTED}
        )
        node_id = _node_id(node.kind, evidence, node.fields)
        node_ids[node.node_id] = node_id
        nodes.append(
            node.model_copy(update={"evidence": evidence, "node_id": node_id})
        )
    edges = []
    for edge in candidate.edges:
        evidence = edge.evidence.model_copy(
            update={"rights_state": RightsState.PERMITTED}
        )
        source_id = node_ids[edge.source_node_id]
        target_id = node_ids[edge.target_node_id]
        edges.append(
            edge.model_copy(
                update={
                    "evidence": evidence,
                    "source_node_id": source_id,
                    "target_node_id": target_id,
                    "edge_id": _edge_id(source_id, target_id, evidence),
                }
            )
        )
    changed = candidate.model_copy(
        update={
            "nodes": tuple(sorted(nodes, key=lambda item: item.node_id)),
            "edges": tuple(sorted(edges, key=lambda item: item.edge_id)),
            "graph_sha256": "0" * 64,
        }
    )

    with pytest.raises(ValueError, match="rights/sensitivity metadata"):
        MbsGoldGraphCandidate.model_validate(changed.model_dump())


def test_node_field_order_and_self_edges_are_rejected():
    result = graph(1)
    node = result.nodes[0]
    changed = node.model_dump()
    changed["fields"] = changed["fields"][::-1]
    with pytest.raises(ValidationError, match="sorted and unique"):
        MbsGoldNode.model_validate(changed)
    edge = result.edges[0]
    changed_edge = edge.model_dump()
    changed_edge["target_node_id"] = changed_edge["source_node_id"]
    with pytest.raises(ValidationError, match="self-edge"):
        MbsGoldEdge.model_validate(changed_edge)


def test_graph_denominator_requires_unique_evidence_addresses():
    payload = b"""<MBS_XML>
      <Data><ItemNum>1</ItemNum><NewItem>A</NewItem><Benefit100>1</Benefit100></Data>
      <Data><ItemNum>2</ItemNum><NewItem>B</NewItem><Benefit100>2</Benefit100></Data>
    </MBS_XML>"""
    result = build_mbs_gold_graph_candidate(payload, _receipt(payload))
    service = next(
        node for node in result.nodes if node.kind == "mbs_service_record"
    )
    benefit = next(
        node
        for node in result.nodes
        if node.kind == "mbs_benefit_record"
        and node.evidence == service.evidence
    )
    other_service = next(
        node
        for node in result.nodes
        if node.kind == "mbs_service_record"
        and node.evidence != service.evidence
    )
    other_benefit = next(
        node
        for node in result.nodes
        if node.kind == "mbs_benefit_record"
        and node.evidence != service.evidence
    )
    duplicate_service = MbsGoldNode(
        node_id=_node_id(
            other_service.kind, service.evidence, other_service.fields
        ),
        kind=other_service.kind,
        evidence=service.evidence,
        fields=other_service.fields,
    )
    duplicate_benefit = MbsGoldNode(
        node_id=_node_id(
            other_benefit.kind, benefit.evidence, other_benefit.fields
        ),
        kind=other_benefit.kind,
        evidence=benefit.evidence,
        fields=other_benefit.fields,
    )
    duplicate_edge = MbsGoldEdge(
        edge_id=_edge_id(
            duplicate_service.node_id,
            duplicate_benefit.node_id,
            service.evidence,
        ),
        source_node_id=duplicate_service.node_id,
        target_node_id=duplicate_benefit.node_id,
        evidence=service.evidence,
        supporting_revisions=result.edges[0].supporting_revisions,
        retrieved_at=result.edges[0].retrieved_at,
        rights_state=result.edges[0].rights_state,
    )
    nodes = tuple(
        sorted(
            (service, benefit, duplicate_service, duplicate_benefit),
            key=attrgetter("node_id"),
        )
    )
    original_edge = next(
        edge for edge in result.edges if edge.evidence == service.evidence
    )
    edges = tuple(
        sorted((original_edge, duplicate_edge), key=attrgetter("edge_id"))
    )
    forged = result.model_dump()
    forged["nodes"] = tuple(node.model_dump() for node in nodes)
    forged["edges"] = tuple(edge.model_dump() for edge in edges)
    with pytest.raises(
        ValidationError, match="evidence denominator is ambiguous"
    ):
        MbsGoldGraphCandidate.model_validate(forged)
