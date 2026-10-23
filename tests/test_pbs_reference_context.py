"""PBS contextual screening emits structure and counts, never source values."""

import json

import pytest

from global_medicines_atlas.pbs_reference_context import (
    screen_reference_context,
)


def test_context_screen_reports_occurrence_structure_without_literals():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
      xmlns:xlink="http://www.w3.org/1999/xlink">
      <rdf:Description xml:id="private-id" rdf:about="https://example.invalid/private">
        <rdf:resource rdf:resource="https://example.invalid/private"/>
      </rdf:Description>
      <group xml:base="https://example.invalid/base/">
        <link xlink:href="#private-id"/>
        <link xlink:href="relative-target"/>
      </group>
    </root>"""
    report = screen_reference_context(xml)
    serialized = json.dumps(report)
    assert report["reference_occurrences"] == 3
    assert report["literal_values_emitted"] is False
    assert report["raw_source_emitted"] is False
    assert report["semantic_relationships_qualified"] is False
    assert report["uri_resolution_performed"] is False
    assert report["external_targets_fetched"] == 0
    assert "private-id" not in serialized
    assert "example.invalid" not in serialized
    assert "relative-target" not in serialized
    assert any(
        row["match_status"] == "unique_exact_literal"
        and row["literal_shape"] == "absolute_looking"
        for row in report["strata"]
    )
    assert any(
        row["xml_base_context"] == "xml_base_present"
        and row["literal_shape"] == "fragment"
        for row in report["strata"]
    )


def test_context_screen_is_deterministic_and_classifies_negative_controls():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <a rdf:about="same"/><a rdf:about="same"/>
      <b rdf:resource="same"/><b rdf:resource="missing"/><b rdf:resource=""/>
    </root>"""
    report = screen_reference_context(xml)
    assert report == screen_reference_context(xml)
    statuses = {row["match_status"] for row in report["strata"]}
    assert statuses == {
        "ambiguous_exact_literal",
        "no_exact_literal",
        "empty_literal",
    }


def test_context_screen_rejects_wrong_root():
    with pytest.raises(ValueError, match="root does not match"):
        screen_reference_context(b"<wrong/>")
