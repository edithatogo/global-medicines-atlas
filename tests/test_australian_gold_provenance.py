"""Australian Gold provenance keeps source-declared authority non-canonical."""

# pyright: reportPrivateUsage=false
# pyright: reportUnknownMemberType=false

from datetime import UTC, datetime
from io import BytesIO

import pyarrow.parquet as pq
import pytest
from pydantic import ValidationError
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- synthetic fixture
)

from global_medicines_atlas.australian_gold_provenance import (
    AUSTRALIAN_GOLD_PROVENANCE_EDGE_SCHEMA,
    AUSTRALIAN_GOLD_PROVENANCE_NODE_SCHEMA,
    AustralianGoldProvenanceCandidate,
    AustralianGoldProvenanceEdge,
    AustralianGoldProvenanceNode,
    _edge_id,  # ruff: ignore[import-private-name] -- adversarial contract test
    build_australian_gold_provenance_candidate,
    project_australian_gold_provenance_arrow,
)
from global_medicines_atlas.receipts import (
    DataSensitivity,
    EvidenceClass,
    PersonalDataState,
    PublicationDisposition,
    SensitivityClassification,
)

PAYLOAD = b"<synthetic-australian-source/>"


def candidate(source_id: str = "au-pbs") -> AustralianGoldProvenanceCandidate:
    """Build a candidate from a source-faithful synthetic receipt."""
    return build_australian_gold_provenance_candidate(
        _receipt(PAYLOAD, source_id)
    )


@pytest.mark.parametrize("source_id", ["au-mbs", "au-pbs"])
def test_source_document_and_declared_authority_are_explicit(source_id: str):
    result = candidate(source_id)
    assert result.qualification == "synthetic_source_identity_candidate_only"
    assert result.asserted_dimensions == ()
    assert result.admission_performed is False
    assert result.inference_performed is False
    assert result.publication_performed is False
    assert len(result.nodes) == 2
    assert len(result.edges) == 1
    by_kind = {node.kind: node for node in result.nodes}
    authority = by_kind["source_declared_organization"]
    document = by_kind["source_document"]
    assert authority.label == "Synthetic fixture"
    assert authority.identity_status == "source_declared_label_not_canonical"
    edge = result.edges[0]
    assert edge.source_node_id == document.node_id
    assert edge.target_node_id == authority.node_id
    assert edge.kind == "source_declares_authority"
    assert edge.semantic_dimension == "source_provenance"
    assert edge.mapping_method == "source-explicit"
    assert edge.confidence is None
    assert edge.review_state == "not_reviewed"
    assert edge.supporting_native_paths == ("source.authority",)
    assert edge.inferred is False


def test_receipt_evidence_time_rights_and_sensitivity_are_preserved():
    sensitivity = SensitivityClassification(
        data_sensitivity=DataSensitivity.NON_SENSITIVE,
        personal_data=PersonalDataState.NONE,
        publication=PublicationDisposition.PERMITTED,
        reason_codes=("synthetic_fixture",),
    )
    receipt = _receipt(PAYLOAD, "au-pbs").model_copy(
        update={
            "effective_from": datetime(2026, 8, 1, tzinfo=UTC),
            "effective_to": datetime(2026, 9, 1, tzinfo=UTC),
            "sensitivity": sensitivity,
        }
    )
    result = build_australian_gold_provenance_candidate(receipt)
    edge = result.edges[0]
    assert edge.evidence.receipt_sha256 == receipt.digest()
    assert edge.evidence.source_sha256 == receipt.payload.sha256
    assert edge.retrieved_at == receipt.retrieval.retrieved_at
    assert edge.source_effective_from == receipt.effective_from
    assert edge.source_effective_to == receipt.effective_to
    assert edge.rights_state == receipt.rights_state
    assert edge.sensitivity == sensitivity
    assert edge.valid_time_status == "unselected"


def test_missing_sensitivity_is_an_explicit_unknown_classification():
    edge = candidate().edges[0]
    assert edge.sensitivity == SensitivityClassification()


def test_live_or_non_australian_receipts_fail_closed():
    receipt = _receipt(PAYLOAD, "au-pbs")
    with pytest.raises(ValueError, match="synthetic evidence"):
        build_australian_gold_provenance_candidate(
            receipt.model_copy(update={"evidence_class": EvidenceClass.LIVE})
        )
    other = receipt.model_dump()
    other["source"]["source_id"] = "other"
    other["source"]["catalog_id"] = "other"
    with pytest.raises(ValueError, match="Australian benefits source"):
        build_australian_gold_provenance_candidate(other)


def test_json_arrow_and_parquet_are_deterministic():
    result = candidate()
    assert result == candidate()
    assert (
        AustralianGoldProvenanceCandidate.model_validate_json(
            result.model_dump_json()
        )
        == result
    )
    nodes, edges = project_australian_gold_provenance_arrow(result)
    assert nodes.schema == AUSTRALIAN_GOLD_PROVENANCE_NODE_SCHEMA
    assert edges.schema == AUSTRALIAN_GOLD_PROVENANCE_EDGE_SCHEMA
    for table in (nodes, edges):
        output = BytesIO()
        pq.write_table(table, output)
        assert pq.read_table(BytesIO(output.getvalue())).equals(
            table, check_metadata=True
        )


def test_node_edge_and_graph_tampering_fail_closed():
    result = candidate()
    node = result.nodes[0]
    changed = node.model_dump()
    changed["node_id"] = "australian-gold-node:" + "0" * 64
    with pytest.raises(ValidationError, match="node identity"):
        AustralianGoldProvenanceNode.model_validate(changed)
    changed = node.model_dump()
    changed["identity_status"] = (
        "source_declared_label_not_canonical"
        if node.kind == "source_document"
        else "exact_source_payload"
    )
    with pytest.raises(ValidationError, match="node status"):
        AustralianGoldProvenanceNode.model_validate(changed)
    edge = result.edges[0]
    changed = edge.model_dump()
    changed["edge_id"] = "australian-gold-edge:" + "0" * 64
    with pytest.raises(ValidationError, match="edge identity"):
        AustralianGoldProvenanceEdge.model_validate(changed)
    for key, value, match in (
        ("target_node_id", edge.source_node_id, "self-edge"),
        ("supporting_source_ids", ("au-mbs",), "source support"),
        ("supporting_revisions", ("other",), "revision support"),
        (
            "contradiction_edge_ids",
            ("australian-gold-edge:" + "0" * 64,),
            "history is not asserted",
        ),
    ):
        changed = edge.model_dump()
        changed[key] = value
        with pytest.raises(ValidationError, match=match):
            AustralianGoldProvenanceEdge.model_validate(changed)
    changed = result.model_dump()
    changed["nodes"] = changed["nodes"][::-1]
    with pytest.raises(ValidationError, match="nodes are not deterministic"):
        AustralianGoldProvenanceCandidate.model_validate(changed)
    changed = result.model_dump()
    changed["nodes"] = changed["nodes"][:1]
    with pytest.raises(ValidationError, match="graph denominator"):
        AustralianGoldProvenanceCandidate.model_validate(changed)
    changed = result.model_dump()
    changed["nodes"] = [changed["nodes"][0], changed["nodes"][0]]
    with pytest.raises(ValidationError, match="node identity is ambiguous"):
        AustralianGoldProvenanceCandidate.model_validate(changed)
    changed = result.model_dump()
    changed_edge = changed["edges"][0]
    changed_edge["source_node_id"] = "australian-gold-node:" + "0" * 64
    changed_edge["edge_id"] = _edge_id({
        key: value for key, value in changed_edge.items() if key != "edge_id"
    })
    with pytest.raises(ValidationError, match="edge support differs"):
        AustralianGoldProvenanceCandidate.model_validate(changed)
    changed = result.model_dump()
    changed["graph_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="graph digest"):
        AustralianGoldProvenanceCandidate.model_validate(changed)


def test_arrow_projection_revalidates_constructed_graph():
    result = candidate()
    forged = result.model_copy(update={"graph_sha256": "0" * 64})
    with pytest.raises(ValidationError, match="graph digest"):
        project_australian_gold_provenance_arrow(forged)
