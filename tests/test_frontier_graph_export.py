"""Portable graph export preserves evidence and never interpolates labels."""

import json
from urllib.parse import quote

import pyarrow as pa
import pytest
from test_mbs_gold_graph import graph
from test_pbs_gold_graph import graph as pbs_graph

from global_medicines_atlas import frontier_graph_export as graph_export_module
from global_medicines_atlas.frontier_graph_export import (
    export_gold_tables,
    export_rdf_star,
)
from global_medicines_atlas.mbs_gold_graph import project_mbs_gold_graph_arrow
from global_medicines_atlas.pbs_gold_graph import project_pbs_gold_graph_arrow


def test_reference_and_cypher_parameters_preserve_every_portable_field():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    result = export_gold_tables(nodes, edges)
    reference = json.loads(result.reference_json)
    parameters = json.loads(result.parameters_json)
    assert reference["nodes"] == nodes.to_pylist()
    assert reference["edges"] == edges.to_pylist()
    assert [
        json.loads(row["payload_json"]) for row in parameters["nodes"]
    ] == reference["nodes"]
    assert [
        json.loads(row["payload_json"]) for row in parameters["edges"]
    ] == reference["edges"]
    assert export_gold_tables(nodes, edges) == result
    assert (
        export_gold_tables(nodes.take([3, 2, 1, 0]), edges.take([1, 0]))
        == result
    )


def test_hostile_native_text_is_only_parameter_data():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    rows = nodes.to_pylist()
    hostile = "'\\\n` MATCH (n) DETACH DELETE n; // 雪"
    rows[0]["fields_json"] = json.dumps({"native_value": hostile})
    result = export_gold_tables(
        pa.Table.from_pylist(rows, schema=nodes.schema), edges
    )
    assert hostile not in result.node_statement + result.edge_statement
    recovered = json.loads(
        json.loads(result.parameters_json)["nodes"][0]["payload_json"]
    )
    assert json.loads(recovered["fields_json"])["native_value"] == hostile


@pytest.mark.parametrize("family", ["mbs", "pbs"])
@pytest.mark.parametrize(
    ("classification", "value"),
    [
        ("rights_state", "restricted"),
        ("rights_state", "prohibited"),
        ("data_sensitivity", "restricted"),
        ("personal_data", "present"),
        ("publication", "prohibited"),
    ],
)
def test_known_restricted_graph_metadata_is_rejected_before_serialization(
    family: str,
    classification: str,
    value: str,
    monkeypatch: pytest.MonkeyPatch,
):
    nodes, edges = (
        project_mbs_gold_graph_arrow(graph())
        if family == "mbs"
        else project_pbs_gold_graph_arrow(pbs_graph())
    )
    rows = edges.to_pylist()
    for row in rows:
        controls = json.loads(row["controls_json"])
        if classification == "rights_state":
            controls[classification] = value
        else:
            controls["sensitivity"][classification] = value
        row["controls_json"] = json.dumps(controls)
    edges = pa.Table.from_pylist(rows, schema=edges.schema)

    def reject_serialization(_value):
        raise AssertionError("restricted payload reached serialization")

    monkeypatch.setattr(graph_export_module, "_json", reject_serialization)
    with pytest.raises(ValueError, match="restricted or prohibited"):
        export_gold_tables(nodes, edges)


@pytest.mark.parametrize("family", ["mbs", "pbs"])
@pytest.mark.parametrize(
    "field_policy",
    [
        {
            "rights_state": "restricted",
            "sensitivity": {
                "data_sensitivity": "non_sensitive",
                "personal_data": "none",
                "publication": "permitted",
            },
        },
        {
            "rights_state": "prohibited",
            "sensitivity": {
                "data_sensitivity": "non_sensitive",
                "personal_data": "none",
                "publication": "permitted",
            },
        },
        {
            "rights_state": "permitted",
            "sensitivity": {
                "data_sensitivity": "sensitive",
                "personal_data": "none",
                "publication": "permitted",
            },
        },
        {
            "rights_state": "permitted",
            "sensitivity": {
                "data_sensitivity": "restricted",
                "personal_data": "none",
                "publication": "permitted",
            },
        },
        {
            "rights_state": "permitted",
            "sensitivity": {
                "data_sensitivity": "non_sensitive",
                "personal_data": "possible",
                "publication": "permitted",
            },
        },
        {
            "rights_state": "permitted",
            "sensitivity": {
                "data_sensitivity": "non_sensitive",
                "personal_data": "present",
                "publication": "permitted",
            },
        },
        {
            "rights_state": "permitted",
            "sensitivity": {
                "data_sensitivity": "non_sensitive",
                "personal_data": "none",
                "publication": "prohibited",
            },
        },
    ],
)
def test_nested_restricted_field_metadata_is_rejected_before_serialization(
    family: str,
    field_policy: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nodes, edges = (
        project_mbs_gold_graph_arrow(graph())
        if family == "mbs"
        else project_pbs_gold_graph_arrow(pbs_graph())
    )
    rows = nodes.to_pylist()
    fields = json.loads(rows[0]["fields_json"])
    fields[0]["field_policy"] = field_policy
    rows[0]["fields_json"] = json.dumps(fields)
    nodes = pa.Table.from_pylist(rows, schema=nodes.schema)

    def reject_serialization(_value):
        raise AssertionError("restricted field payload reached serialization")

    monkeypatch.setattr(graph_export_module, "_json", reject_serialization)
    with pytest.raises(ValueError, match="restricted field rights/sensitivity"):
        export_gold_tables(nodes, edges)


def test_field_policy_must_be_complete_and_unambiguous() -> None:
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    rows = nodes.to_pylist()
    rows[0]["fields_json"] = json.dumps([
        {"native_value": "fixture", "field_policy": {"rights_state": "unknown"}}
    ])
    nodes = pa.Table.from_pylist(rows, schema=nodes.schema)
    with pytest.raises(
        ValueError, match="invalid graph field rights/sensitivity"
    ):
        export_gold_tables(nodes, edges)

    rows[0]["fields_json"] = (
        '[{"native_value":"fixture","field_policy":'
        '{"rights_state":"unknown","rights_state":"restricted"}}]'
    )
    nodes = pa.Table.from_pylist(rows, schema=nodes.schema)
    with pytest.raises(ValueError, match="invalid graph fields metadata"):
        export_gold_tables(nodes, edges)


def test_nonrestrictive_field_policy_is_preserved_without_clearance_claim() -> (
    None
):
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    rows = nodes.to_pylist()
    field_policy = {
        "rights_state": "unknown",
        "sensitivity": {
            "data_sensitivity": "unknown",
            "personal_data": "unknown",
            "publication": "review_required",
        },
    }
    fields = json.loads(rows[0]["fields_json"])
    fields[0]["field_policy"] = field_policy
    rows[0]["fields_json"] = json.dumps(fields)
    nodes = pa.Table.from_pylist(rows, schema=nodes.schema)

    result = export_gold_tables(nodes, edges)

    exported = json.loads(result.reference_json)["nodes"][0]
    assert (
        json.loads(exported["fields_json"])[0]["field_policy"] == field_policy
    )


@pytest.mark.parametrize(
    ("evidence_json", "message"),
    [
        (
            '{"rights_state":"permitted","rights_state":"restricted"}',
            "metadata",
        ),
        ("{", "metadata"),
        ("[]", "metadata"),
        ('{"rights_state":null,"sensitivity":{}}', "rights/sensitivity"),
        (
            '{"rights_state":"permitted","sensitivity":[]}',
            "sensitivity",
        ),
        (
            '{"rights_state":"permitted","sensitivity":{"data_sensitivity":1,"personal_data":"none","publication":"permitted"}}',
            "rights/sensitivity",
        ),
        (
            '{"rights_state":"invalid","sensitivity":{"data_sensitivity":"unknown","personal_data":"unknown","publication":"review_required"}}',
            "rights/sensitivity",
        ),
    ],
)
def test_malformed_graph_policy_metadata_fails_closed(
    evidence_json: str, message: str
):
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    rows = nodes.to_pylist()
    rows[0]["evidence_json"] = evidence_json
    nodes = pa.Table.from_pylist(rows, schema=nodes.schema)

    with pytest.raises((TypeError, ValueError), match=message):
        export_gold_tables(nodes, edges)


@pytest.mark.parametrize("family", ["mbs", "pbs"])
def test_policy_metadata_must_be_consistent_across_graph_rows(family: str):
    nodes, edges = (
        project_mbs_gold_graph_arrow(graph())
        if family == "mbs"
        else project_pbs_gold_graph_arrow(pbs_graph())
    )
    rows = nodes.to_pylist()
    evidence = json.loads(rows[0]["evidence_json"])
    evidence["rights_state"] = "permitted"
    rows[0]["evidence_json"] = json.dumps(evidence)
    nodes = pa.Table.from_pylist(rows, schema=nodes.schema)

    with pytest.raises(ValueError, match="differs across rows"):
        export_gold_tables(nodes, edges)


@pytest.mark.parametrize("family", ["mbs", "pbs"])
def test_restricted_node_metadata_is_checked_independently_of_edge_metadata(
    family: str,
):
    nodes, edges = (
        project_mbs_gold_graph_arrow(graph())
        if family == "mbs"
        else project_pbs_gold_graph_arrow(pbs_graph())
    )
    rows = nodes.to_pylist()
    evidence = json.loads(rows[0]["evidence_json"])
    evidence["rights_state"] = "restricted"
    rows[0]["evidence_json"] = json.dumps(evidence)
    nodes = pa.Table.from_pylist(rows, schema=nodes.schema)

    with pytest.raises(ValueError, match="restricted or prohibited"):
        export_gold_tables(nodes, edges)


@pytest.mark.parametrize("family", ["mbs", "pbs"])
def test_edge_rights_metadata_must_match_its_evidence(family: str):
    nodes, edges = (
        project_mbs_gold_graph_arrow(graph())
        if family == "mbs"
        else project_pbs_gold_graph_arrow(pbs_graph())
    )
    rows = edges.to_pylist()
    evidence = json.loads(rows[0]["evidence_json"])
    evidence["rights_state"] = "permitted"
    rows[0]["evidence_json"] = json.dumps(evidence)
    edges = pa.Table.from_pylist(rows, schema=edges.schema)

    with pytest.raises(ValueError, match="metadata differs"):
        export_gold_tables(nodes, edges)


def test_duplicate_dangling_and_schema_mismatch_are_rejected():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    with pytest.raises(ValueError, match="duplicate"):
        export_gold_tables(pa.concat_tables([nodes, nodes]), edges)
    with pytest.raises(ValueError, match="endpoint"):
        export_gold_tables(nodes.slice(0, 1), edges)
    with pytest.raises(ValueError, match="schema"):
        export_gold_tables(nodes.drop(["fields_json"]), edges)


def test_export_denominator_is_bounded():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    with pytest.raises(ValueError, match="bound"):
        export_gold_tables(nodes, edges, max_rows=1)


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_bounds(limit):
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    with pytest.raises(ValueError, match="bound"):
        export_gold_tables(nodes, edges, max_bytes=limit)


def test_pbs_preserves_null_confidence_and_explicit_candidate_controls():
    nodes, edges = project_pbs_gold_graph_arrow(pbs_graph())
    result = export_gold_tables(nodes, edges)
    rows = json.loads(result.reference_json)["edges"]
    assert rows
    for row in rows:
        assert row["confidence"] is None
        assert row["review_state"] == "not_reviewed"
        assert json.loads(row["controls_json"])["inferred"] is False
    with pytest.raises(ValueError, match="schema"):
        export_gold_tables(nodes, project_mbs_gold_graph_arrow(graph())[1])


@pytest.mark.parametrize("family", ["mbs", "pbs"])
def test_unknown_binary_graph_column_is_rejected_before_serialization(
    family: str,
    monkeypatch: pytest.MonkeyPatch,
):
    nodes, edges = (
        project_mbs_gold_graph_arrow(graph())
        if family == "mbs"
        else project_pbs_gold_graph_arrow(pbs_graph())
    )
    unexpected_column = pa.array(
        [b"synthetic-binary-placeholder"] * nodes.num_rows,
        type=pa.binary(),
    )
    nodes_with_unexpected_column = nodes.append_column(
        "unexpected_binary_column", unexpected_column
    )

    def reject_serialization(_value):
        raise AssertionError("unsupported payload reached serialization")

    monkeypatch.setattr(graph_export_module, "_json", reject_serialization)

    with pytest.raises(
        ValueError, match=r"^unsupported or mismatched Gold schema$"
    ):
        export_gold_tables(nodes_with_unexpected_column, edges)


def test_empty_tables_and_byte_bounds():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    assert json.loads(
        export_gold_tables(nodes.slice(0, 0), edges.slice(0, 0)).reference_json
    ) == {"nodes": [], "edges": []}
    with pytest.raises(ValueError, match="byte bound"):
        export_gold_tables(nodes, edges, max_bytes=1)
    with pytest.raises(ValueError, match="serialized"):
        export_gold_tables(nodes, edges, max_bytes=nodes.nbytes + edges.nbytes)


def test_null_identity_rejected_even_with_nullable_arrow_field():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    rows = nodes.to_pylist()
    rows[0]["node_id"] = None
    with pytest.raises(ValueError, match="identity"):
        export_gold_tables(
            pa.Table.from_pylist(rows, schema=nodes.schema), edges
        )


def test_rdf_star_is_deterministic_lossless_and_quotes_edges():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    result = export_rdf_star(nodes, edges)
    assert result == export_rdf_star(
        nodes.take([3, 1, 0, 2]), edges.take([1, 0])
    )
    assert "<<<urn:gma:node:" in result
    assert "<urn:gma:payload-json>" in result
    assert "native_name" in result
    assert "urn:gma:edge-resource" in result


def test_rdf_star_reuses_fail_closed_bounds():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    with pytest.raises(ValueError, match="bound"):
        export_rdf_star(nodes, edges, max_rows=1)


def test_rdf_star_encodes_untrusted_graph_ids_as_valid_iri_references():
    nodes, edges = project_mbs_gold_graph_arrow(graph())
    node_rows = nodes.to_pylist()
    edge_rows = edges.to_pylist()
    original = node_rows[0]["node_id"]
    hostile = "service id/雪%?#<tag>\\value"
    node_rows[0]["node_id"] = hostile
    for edge in edge_rows:
        if edge["source_node_id"] == original:
            edge["source_node_id"] = hostile
        if edge["target_node_id"] == original:
            edge["target_node_id"] = hostile
    nodes = pa.Table.from_pylist(node_rows, schema=nodes.schema)
    edges = pa.Table.from_pylist(edge_rows, schema=edges.schema)

    output = export_rdf_star(nodes, edges)

    expected = f"<urn:gma:node:{quote(hostile, safe='-._~:')}>"
    assert expected in output
    assert all(ord(character) < 128 for character in output)
