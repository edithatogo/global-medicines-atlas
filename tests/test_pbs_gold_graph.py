"""PBS Gold candidates preserve Silver evidence without semantic promotion."""

# pyright: reportPrivateUsage=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false
# pyright: reportUnknownMemberType=false

from datetime import UTC, datetime
from io import BytesIO
from operator import itemgetter

import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError
from test_au_pbs_v3 import (
    _xml as rich_xml,  # ruff: ignore[import-private-name] -- synthetic fixture
)
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- synthetic fixture receipt
)
from test_pbs_silver import XML

from global_medicines_atlas import pbs_gold_graph
from global_medicines_atlas.pbs_gold_graph import (
    PBS_GOLD_EDGE_SCHEMA,
    PBS_GOLD_NODE_SCHEMA,
    PbsGoldEdge,
    PbsGoldEvidence,
    PbsGoldFieldEvidence,
    PbsGoldGraphCandidate,
    PbsGoldNode,
    _digest,  # ruff: ignore[import-private-name] -- adversarial identity test
    _edge_id,  # ruff: ignore[import-private-name] -- adversarial identity test
    build_pbs_gold_graph_candidate,
    project_pbs_gold_graph_arrow,
)
from global_medicines_atlas.receipts import (
    DataSensitivity,
    EvidenceClass,
    PersonalDataState,
    PublicationDisposition,
    SensitivityClassification,
)


def graph() -> PbsGoldGraphCandidate:
    """Build the representative synthetic PBS graph."""
    return build_pbs_gold_graph_candidate(XML, _receipt(XML, "au-pbs"))


def test_source_explicit_graph_preserves_all_entity_and_field_evidence() -> (
    None
):
    result = graph()
    assert result.qualification == "synthetic_silver_candidate_only"
    assert result.admission_performed is False
    assert result.inference_performed is False
    assert result.terminology_resolution_performed is False
    assert result.publication_performed is False
    assert len(result.nodes) == result.source_entity_count
    assert len(result.edges) == result.source_entity_count - 1
    assert sum(node.evidence.field_count for node in result.nodes) == 28
    rich = build_pbs_gold_graph_candidate(
        rich_xml(), _receipt(rich_xml(), "au-pbs")
    )
    assert {node.semantic_dimension for node in rich.nodes} >= {
        "source_document",
        "pbs_item_structure",
        "restriction_structure",
        "terminology_reference_structure",
        "classification_reference_structure",
    }
    assert "unmapped_source_structure" in {
        node.semantic_dimension for node in result.nodes
    }
    for node in result.nodes:
        ordinals = tuple(field.source_ordinal for field in node.fields)
        assert ordinals == tuple(range(min(ordinals), max(ordinals) + 1))
        assert all(
            field.source_sha256 == node.evidence.source_sha256
            for field in node.fields
        )
        assert all(
            field.receipt_sha256 == node.evidence.receipt_sha256
            for field in node.fields
        )


def test_funding_regulatory_formulary_and_terminology_are_not_conflated() -> (
    None
):
    result = graph()
    assert result.asserted_dimensions == ()
    assert all(
        edge.semantic_dimension == "source_structure" for edge in result.edges
    )
    assert all(
        edge.mapping_method == "source-explicit" for edge in result.edges
    )
    assert all(edge.confidence is None for edge in result.edges)
    assert all(edge.review_state == "not_reviewed" for edge in result.edges)
    assert all(edge.inferred is False for edge in result.edges)
    assert all(
        edge.negative_control_outcome == "not_applicable"
        for edge in result.edges
    )
    assert all(
        edge.comparison_validity == "source_structure_only"
        for edge in result.edges
    )
    serialized = result.model_dump_json()
    for forbidden in (
        "regulatory_approval",
        "funding_entitlement",
        "formulary_admission",
        "terminology_equivalence",
    ):
        assert forbidden not in serialized


def test_every_edge_is_same_source_parent_child_evidence() -> None:
    result = graph()
    by_id = {node.node_id: node for node in result.nodes}
    for edge in result.edges:
        parent = by_id[edge.source_node_id]
        child = by_id[edge.target_node_id]
        assert child.evidence.parent_entity_id == parent.evidence.entity_id
        assert edge.evidence == child.evidence
        assert edge.supporting_source_ids == ("au-pbs",)
        assert edge.supporting_revisions == (child.evidence.schema_era,)
        assert edge.supporting_native_rows == (child.evidence.entity_id,)
        assert edge.supporting_native_paths == tuple(
            field.path for field in child.fields
        )
        assert edge.valid_time_status == "unselected"
        assert edge.source_effective_from is None
        assert edge.source_effective_to is None
        assert edge.sensitivity == SensitivityClassification()
        assert edge.contradiction_edge_ids == ()
        assert edge.supersedes_edge_ids == ()


def test_graph_and_arrow_parquet_are_deterministic() -> None:
    result = graph()
    assert result == graph()
    assert (
        PbsGoldGraphCandidate.model_validate_json(result.model_dump_json())
        == result
    )
    nodes, edges = project_pbs_gold_graph_arrow(result)
    assert nodes.schema == PBS_GOLD_NODE_SCHEMA
    assert edges.schema == PBS_GOLD_EDGE_SCHEMA
    for table in (nodes, edges):
        stream = BytesIO()
        pq.write_table(table, stream)
        assert pq.read_table(BytesIO(stream.getvalue())).equals(
            table, check_metadata=True
        )


def test_live_source_is_not_admitted_by_candidate_builder() -> None:
    receipt = _receipt(XML, "au-pbs").model_copy(
        update={"evidence_class": EvidenceClass.LIVE}
    )
    with pytest.raises(ValueError, match="synthetic evidence"):
        build_pbs_gold_graph_candidate(XML, receipt)


def test_receipt_and_source_mismatch_fail_before_projection() -> None:
    with pytest.raises(ValueError, match="source bytes"):
        build_pbs_gold_graph_candidate(XML, _receipt(b"other", "au-pbs"))
    with pytest.raises(ValueError, match="source_id"):
        build_pbs_gold_graph_candidate(XML, _receipt(XML, "au-mbs"))


def test_node_edge_graph_and_arrow_tampering_fail_closed() -> None:
    result = graph()
    node = result.nodes[0]
    changed_node = node.model_dump()
    changed_node["node_id"] = "pbs-gold-node:" + "0" * 64
    with pytest.raises(ValidationError, match="node identity"):
        PbsGoldNode.model_validate(changed_node)
    edge = result.edges[0]
    changed_edge = edge.model_dump()
    changed_edge["edge_id"] = "pbs-gold-edge:" + "0" * 64
    with pytest.raises(ValidationError, match="edge identity"):
        PbsGoldEdge.model_validate(changed_edge)
    changed_graph = result.model_dump()
    changed_graph["graph_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="graph digest"):
        PbsGoldGraphCandidate.model_validate(changed_graph)
    forged = result.model_copy(update={"graph_sha256": "0" * 64})
    with pytest.raises(ValidationError, match="graph digest"):
        project_pbs_gold_graph_arrow(forged)


def test_order_denominator_endpoint_and_parent_support_fail_closed() -> None:
    result = graph()
    changed = result.model_dump()
    changed["nodes"] = changed["nodes"][::-1]
    with pytest.raises(ValidationError, match="nodes are not deterministic"):
        PbsGoldGraphCandidate.model_validate(changed)
    changed = result.model_dump()
    changed["edges"] = changed["edges"][::-1]
    with pytest.raises(ValidationError, match="edges are not deterministic"):
        PbsGoldGraphCandidate.model_validate(changed)
    changed = result.model_dump()
    changed["nodes"] = list(changed["nodes"])
    changed["nodes"][1] = changed["nodes"][0]
    changed["nodes"] = sorted(changed["nodes"], key=itemgetter("node_id"))
    with pytest.raises(ValidationError, match="node identity is ambiguous"):
        PbsGoldGraphCandidate.model_validate(changed)
    changed = result.model_dump()
    changed["source_entity_count"] -= 1
    with pytest.raises(ValidationError, match="denominator differs"):
        PbsGoldGraphCandidate.model_validate(changed)
    edge = result.edges[0]
    absent = "pbs-gold-node:" + "0" * 64
    forged_edge = PbsGoldEdge(
        edge_id=_edge_id(absent, edge.target_node_id, edge.evidence),
        source_node_id=absent,
        target_node_id=edge.target_node_id,
        evidence=edge.evidence,
        supporting_revisions=edge.supporting_revisions,
        supporting_native_rows=edge.supporting_native_rows,
        supporting_native_paths=edge.supporting_native_paths,
        retrieved_at=edge.retrieved_at,
        rights_state=edge.rights_state,
    )
    changed = result.model_dump()
    changed["edges"] = list(changed["edges"])
    changed["edges"][0] = forged_edge.model_dump()
    changed["edges"] = sorted(changed["edges"], key=itemgetter("edge_id"))
    with pytest.raises(ValidationError, match="endpoint is absent"):
        PbsGoldGraphCandidate.model_validate(changed)

    child = next(
        node for node in result.nodes if node.evidence.parent_entity_id
    )
    wrong_parent = next(
        node
        for node in result.nodes
        if node.evidence.entity_id != child.evidence.parent_entity_id
        and node.node_id != child.node_id
    )
    unsupported = edge.model_copy(
        update={
            "source_node_id": wrong_parent.node_id,
            "target_node_id": child.node_id,
            "evidence": child.evidence,
            "supporting_revisions": (child.evidence.schema_era,),
            "supporting_native_rows": (child.evidence.entity_id,),
            "edge_id": _edge_id(
                wrong_parent.node_id, child.node_id, child.evidence
            ),
        }
    )
    changed = result.model_dump()
    changed["edges"] = list(changed["edges"])
    changed["edges"][0] = unsupported.model_dump()
    changed["edges"] = sorted(changed["edges"], key=itemgetter("edge_id"))
    with pytest.raises(ValidationError, match="source-parent supported"):
        PbsGoldGraphCandidate.model_validate(changed)


def test_self_edges_and_unsorted_or_incomplete_fields_are_rejected() -> None:
    result = graph()
    node = next(node for node in result.nodes if len(node.fields) > 1)
    changed = node.model_dump()
    changed["fields"] = changed["fields"][::-1]
    with pytest.raises(ValidationError, match="fields are not ordered"):
        PbsGoldNode.model_validate(changed)
    changed = node.model_dump()
    changed["fields"] = changed["fields"][:-1]
    with pytest.raises(ValidationError, match="field denominator"):
        PbsGoldNode.model_validate(changed)
    edge = result.edges[0]
    changed_edge = edge.model_dump()
    changed_edge["target_node_id"] = changed_edge["source_node_id"]
    with pytest.raises(ValidationError, match="self-edge"):
        PbsGoldEdge.model_validate(changed_edge)


def test_nested_field_evidence_and_entity_address_tampering_fail_closed() -> (
    None
):
    result = graph()
    node = next(node for node in result.nodes if len(node.fields) > 1)
    field = node.fields[0]
    changed_field = field.model_dump()
    changed_field["value"] = None if field.value is not None else "invented"
    with pytest.raises(ValidationError, match="field state"):
        PbsGoldFieldEvidence.model_validate(changed_field)
    changed_field = field.model_dump()
    changed_field["source_field_id"] = "wrong"
    with pytest.raises(ValidationError, match="field identity"):
        PbsGoldFieldEvidence.model_validate(changed_field)
    changed_field = field.model_dump()
    changed_field["mapping_status"] = (
        "unmapped"
        if field.mapping_status == "source_structure"
        else "source_structure"
    )
    with pytest.raises(ValidationError, match="structural mapping"):
        PbsGoldFieldEvidence.model_validate(changed_field)

    evidence = node.evidence.model_dump()
    evidence["field_count"] += 1
    with pytest.raises(ValidationError, match="ordinal denominator"):
        PbsGoldEvidence.model_validate(evidence)
    evidence = node.evidence.model_dump()
    evidence["entity_id"] = "wrong"
    with pytest.raises(ValidationError, match="entity identity"):
        PbsGoldEvidence.model_validate(evidence)
    if node.evidence.parent_entity_id is None:
        node = next(
            item for item in result.nodes if item.evidence.parent_entity_id
        )
    evidence = node.evidence.model_dump()
    evidence["parent_entity_id"] = "wrong"
    with pytest.raises(ValidationError, match="parent identity"):
        PbsGoldEvidence.model_validate(evidence)

    fields = list(node.fields)
    changed = fields[0].model_copy(update={"value": "changed"})
    fields[0] = PbsGoldFieldEvidence.model_validate(changed.model_dump())
    node_data = node.model_dump()
    node_data["fields"] = [item.model_dump() for item in fields]
    with pytest.raises(ValidationError, match="fields differ"):
        PbsGoldNode.model_validate(node_data)
    node_data["evidence"]["fields_sha256"] = _digest(node_data["fields"])
    node_data["fields"][0]["record_id"] = "different-record"
    node_data["evidence"]["fields_sha256"] = _digest(node_data["fields"])
    with pytest.raises(ValidationError, match="field lineage"):
        PbsGoldNode.model_validate(node_data)


def test_edge_revision_native_row_and_history_claims_fail_closed() -> None:
    edge = graph().edges[0]
    for key, value, match in (
        ("supporting_revisions", ("other",), "revision differs"),
        ("supporting_native_rows", ("other",), "native row differs"),
        (
            "contradiction_edge_ids",
            ("pbs-gold-edge:" + "0" * 64,),
            "graph history",
        ),
        (
            "supersedes_edge_ids",
            ("pbs-gold-edge:" + "0" * 64,),
            "graph history",
        ),
    ):
        changed = edge.model_dump()
        changed[key] = value
        with pytest.raises(ValidationError, match=match):
            PbsGoldEdge.model_validate(changed)


def test_entity_and_parent_identities_are_exactly_bound_to_native_records() -> (
    None
):
    result = graph()
    child = next(
        node
        for node in result.nodes
        if node.evidence.parent_entity_id is not None
    )
    evidence = child.evidence.model_dump()
    evidence["entity_id"] = evidence["source_sha256"] + ":invented"
    with pytest.raises(ValidationError, match="entity identity differs"):
        PbsGoldEvidence.model_validate(evidence)

    evidence = child.evidence.model_dump()
    evidence["parent_entity_id"] = evidence["source_sha256"] + ":/invented/1"
    with pytest.raises(ValidationError, match="parent identity differs"):
        PbsGoldEvidence.model_validate(evidence)


def test_edges_preserve_source_effective_interval_and_sensitivity() -> None:
    payload = XML
    receipt = _receipt(payload, "au-pbs").model_copy(
        update={
            "effective_from": datetime(2026, 8, 1, tzinfo=UTC),
            "effective_to": datetime(2026, 9, 1, tzinfo=UTC),
            "sensitivity": SensitivityClassification(
                data_sensitivity=DataSensitivity.NON_SENSITIVE,
                personal_data=PersonalDataState.NONE,
                publication=PublicationDisposition.PERMITTED,
                reason_codes=("synthetic_public_fixture",),
            ),
        }
    )
    result = build_pbs_gold_graph_candidate(payload, receipt)
    for edge in result.edges:
        assert edge.valid_time_status == "unselected"
        assert edge.source_effective_from == receipt.effective_from
        assert edge.source_effective_to == receipt.effective_to
        assert edge.sensitivity == receipt.sensitivity


def test_node_structural_dimension_cannot_be_relabelled_or_mixed() -> None:
    result = graph()
    node = next(
        item
        for item in result.nodes
        if item.evidence.parent_entity_id is not None
        and len(item.fields) > 1
        and item.fields[0].mapping_target != "unmapped"
    )
    node_data = node.model_dump()
    node_data["semantic_dimension"] = "source_document"
    node_data["node_id"] = pbs_gold_graph._node_id(
        "source_document", node.evidence, node.fields
    )
    with pytest.raises(ValidationError, match="structural dimension differs"):
        PbsGoldNode.model_validate(node_data)

    node_data = node.model_dump()
    node_data["fields"] = list(node_data["fields"])
    node_data["fields"][0]["mapping_target"] = "unmapped"
    node_data["fields"][0]["mapping_status"] = "unmapped"
    node_data["evidence"]["fields_sha256"] = _digest(node_data["fields"])
    with pytest.raises(ValidationError, match="dimension is ambiguous"):
        PbsGoldNode.model_validate(node_data)


def test_missing_or_internally_incomplete_silver_entities_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pbs_gold_graph, "_rows", lambda _: [])
    with pytest.raises(ValueError, match="requires source entities"):
        build_pbs_gold_graph_candidate(XML, _receipt(XML, "au-pbs"))

    monkeypatch.undo()
    original = pbs_gold_graph._rows

    def without_root(batches: object) -> list[dict[str, object]]:
        rows = original(batches)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        return [row for row in rows if row["parent_entity_id"] is not None]

    monkeypatch.setattr(pbs_gold_graph, "_rows", without_root)
    with pytest.raises(ValueError, match="parent entity is absent"):
        build_pbs_gold_graph_candidate(XML, _receipt(XML, "au-pbs"))


def test_duplicate_child_edge_fails_complete_containment_denominator() -> None:
    result = graph()
    changed = result.model_dump()
    changed["edges"] = list(changed["edges"])
    changed["edges"][1] = changed["edges"][0]
    changed["edges"] = sorted(changed["edges"], key=itemgetter("edge_id"))
    with pytest.raises(ValidationError, match="edge identity is ambiguous"):
        PbsGoldGraphCandidate.model_validate(changed)


def test_edge_paths_are_bound_to_target_field_evidence() -> None:
    result = graph()
    edge = result.edges[0]
    changed_edge = edge.model_dump()
    changed_edge["supporting_native_paths"] = ("invented",)
    changed = result.model_dump()
    changed["edges"] = list(changed["edges"])
    changed["edges"][0] = changed_edge
    changed["edges"] = sorted(changed["edges"], key=itemgetter("edge_id"))
    with pytest.raises(ValidationError, match="source-parent supported"):
        PbsGoldGraphCandidate.model_validate(changed)
