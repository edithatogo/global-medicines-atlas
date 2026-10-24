"""Bounded same-member XLink candidate export remains value-free."""

import hashlib
import json

import pytest
from test_au_pbs_v3 import _zip  # ruff: ignore[import-private-name]
from test_australian_source_contracts import _receipt  # ruff: ignore[import-private-name]
from test_pbs_historical_silver import PATH, SOURCE

from global_medicines_atlas import pbs_xlink_reference_candidates as module
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)

NS = b'''xmlns="http://schema.pbs.gov.au/" xmlns:xlink="http://www.w3.org/1999/xlink"'''


def _run(body: bytes, output_path):
    member = b"<root " + NS + b">" + body + b"</root>"
    archive = _zip([(PATH, member)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    return module.export_pbs_xlink_reference_candidates(
        archive, member, parent, binding, output_path
    )


def test_unique_local_edges_stream_with_digest_and_count(tmp_path):
    output_path = tmp_path / "edges.jsonl"
    report = _run(
        b'<code xml:id="target"/><code xlink:href="#target"/>'
        b'<code xlink:href="#target"/>',
        output_path,
    )
    payload = output_path.read_bytes()
    edges = [json.loads(line) for line in payload.splitlines()]
    assert report["candidate_edge_count"] == 2
    assert report["reference_count"] == 2
    assert report["abstention_counts"] == {}
    assert report["resolution_counts"] == {"candidate_unique_same_member_id": 2}
    assert [edge["kind"] for edge in edges] == [
        "source_declared_xlink_link",
        "source_declared_xlink_link",
    ]
    assert (
        edges[0]["source_occurrence_sha256"]
        != edges[1]["source_occurrence_sha256"]
    )
    serialized = json.dumps(report)
    assert '"href"' not in serialized
    assert "#target" not in serialized
    assert report["semantic_relationships_qualified"] is False
    assert report["artifact_finalized"] is True
    assert report["artifact_byte_count"] == len(payload)
    assert report["artifact_sha256"] == hashlib.sha256(payload).hexdigest()


def test_negative_controls_are_accounted_and_never_exported(tmp_path):
    report = _run(
        b'<code xml:id="dup"/><code xml:id="dup"/>'
        b'<code xlink:href="#dup"/>'
        b'<code xlink:href="#missing"/>'
        b'<code xlink:href="#"/>'
        b'<code xlink:href="#bad%20id"/>'
        b'<code xlink:href="https://example.test/id"/>'
        b'<code xlink:href="relative"/>'
        b'<code xlink:href="##id"/>'
        b'<code xml:base="https://example.test/" xlink:href="#target"/>'
        b'<container xml:base="https://example.test/"><code xlink:href="#target"/></container>'
        b'<code xlink:href="#other_member"/>',
        tmp_path / "edges.jsonl",
    )
    assert report["candidate_edge_count"] == 0
    assert report["abstention_counts"] == {
        "duplicate_same_member_xml_id": 1,
        "invalid_ncname_fragment": 1,
        "malformed_or_nonlocal_href": 3,
        "missing_same_member_xml_id": 2,
        "percent_encoded_fragment": 1,
        "xml_base_in_ancestry": 2,
    }
    assert report["external_links_emitted"] == 0
    assert report["artifact_byte_count"] == 0
    assert (tmp_path / "edges.jsonl").read_bytes() == b""


def test_cross_member_identifier_does_not_resolve(tmp_path):
    member = b"<root " + NS + b'><code xlink:href="#other_member"/></root>'
    other = b"<root " + NS + b'><code xml:id="other_member"/></root>'
    archive = _zip([(PATH, member), ("other.xml", other)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    report = module.export_pbs_xlink_reference_candidates(
        archive, member, parent, binding, tmp_path / "edges.jsonl"
    )
    assert report["abstention_counts"] == {"missing_same_member_xml_id": 1}
    assert report["candidate_edge_count"] == 0


@pytest.mark.parametrize(
    ("name", "expected"),
    [("_okay.1-\u03b1", True), ("1bad", False), ("has:colon", False)],
)
def test_ncname_validation(name, expected):
    assert bool(module._NCNAME.fullmatch(name)) is expected


@pytest.mark.parametrize(
    ("limit", "message"),
    [
        ("MAX_MEMBER_BYTES", "member exceeds"),
        ("MAX_REFERENCES", "reference limit"),
        ("MAX_IDENTIFIERS", "identifier limit"),
        ("MAX_OUTPUT_EDGES", "output edge limit"),
        ("MAX_OUTPUT_BYTES", "output byte limit"),
    ],
)
def test_bounds_fail_closed(monkeypatch, limit, message, tmp_path):
    monkeypatch.setattr(module, limit, 1)
    if limit == "MAX_REFERENCES":
        body = b'<code xlink:href="#one"/><code xlink:href="#two"/>'
    elif limit == "MAX_IDENTIFIERS":
        body = b'<code xml:id="one"/><code xml:id="two"/>'
    elif limit == "MAX_OUTPUT_EDGES":
        body = (
            b'<code xml:id="target"/><code xlink:href="#target"/>'
            b'<code xlink:href="#target"/>'
        )
    elif limit == "MAX_OUTPUT_BYTES":
        body = b'<code xml:id="target"/><code xlink:href="#target"/>'
    else:
        body = b'<code xml:id="target"/><code xlink:href="#target"/>'
    with pytest.raises(ValueError, match=message):
        _run(body, tmp_path / "edges.jsonl")
    assert not list(tmp_path.iterdir())


def test_output_failure_preserves_previous_file_and_removes_partial_temp(
    monkeypatch, tmp_path
):
    output_path = tmp_path / "edges.jsonl"
    output_path.write_bytes(b"previous complete artifact")
    monkeypatch.setattr(module, "MAX_OUTPUT_BYTES", 300)
    body = (
        b'<code xml:id="target"/><code xlink:href="#target"/>'
        b'<code xlink:href="#target"/>'
    )
    with pytest.raises(ValueError, match="output byte limit"):
        _run(body, output_path)
    assert output_path.read_bytes() == b"previous complete artifact"
    assert list(tmp_path.iterdir()) == [output_path]


def test_input_identity_must_match_exact_member(tmp_path):
    member = b"<root " + NS + b"><code/></root>"
    archive = _zip([(PATH, member)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    with pytest.raises(ValueError, match="member"):
        module.export_pbs_xlink_reference_candidates(
            archive, member + b" ", parent, binding, tmp_path / "edges.jsonl"
        )
    assert not list(tmp_path.iterdir())
