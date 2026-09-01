"""Candidate MBS Gold graph uses only explicit synthetic Silver evidence."""

# pyright: reportPrivateUsage=false
# pyright: reportUnknownMemberType=false

from io import BytesIO
from operator import itemgetter

import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError
from test_mbs_silver import (
    _receipt,  # ruff: ignore[import-private-name] -- shared synthetic fixture
    _xml,  # ruff: ignore[import-private-name] -- shared synthetic fixture
)

from global_medicines_atlas.mbs_gold_graph import (
    MBS_GOLD_EDGE_SCHEMA,
    MBS_GOLD_NODE_SCHEMA,
    MbsGoldEdge,
    MbsGoldFieldEvidence,
    MbsGoldGraphCandidate,
    MbsGoldNode,
    _edge_id,  # ruff: ignore[import-private-name] -- adversarial contract test
    build_mbs_gold_graph_candidate,
    project_mbs_gold_graph_arrow,
)
from global_medicines_atlas.receipts import EvidenceClass


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
    assert len(result.nodes) == 4
    assert len(result.edges) == 2
    by_id = {node.node_id: node for node in result.nodes}
    for edge in result.edges:
        assert edge.inferred is False
        assert edge.assertion_basis == "same_source_record"
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


def test_live_receipts_are_out_of_scope_before_projection():
    payload = _xml()
    receipt = _receipt(payload).model_copy(
        update={"evidence_class": EvidenceClass.LIVE}
    )
    with pytest.raises(ValueError, match="synthetic evidence"):
        build_mbs_gold_graph_candidate(payload, receipt)


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
    )
    changed = result.model_dump()
    changed["edges"] = list(changed["edges"])
    changed["edges"][0] = mismatched.model_dump()
    changed["edges"] = sorted(changed["edges"], key=itemgetter("edge_id"))
    with pytest.raises(ValidationError, match="same record"):
        MbsGoldGraphCandidate.model_validate(changed)


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
