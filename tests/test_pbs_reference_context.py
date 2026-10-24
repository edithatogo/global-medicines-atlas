"""PBS contextual screening emits structure and counts, never source values."""

import json

import pytest

import global_medicines_atlas.pbs_reference_context as context_module
from global_medicines_atlas.pbs_reference_context import (
    ReferenceContextError,
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


def test_context_screen_emits_value_free_substage_progress(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(context_module, "CONTEXT_PROGRESS_EVENT_INTERVAL", 1)
    monkeypatch.setattr(
        context_module, "CONTEXT_PROGRESS_OCCURRENCE_INTERVAL", 1
    )
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <edge rdf:resource="private-target"/>
    </root>"""
    checkpoints: list[tuple[str, int, int]] = []

    report = screen_reference_context(
        xml,
        progress=lambda phase, batches, rows: checkpoints.append((
            phase,
            batches,
            rows,
        )),
    )

    assert [checkpoint[0] for checkpoint in checkpoints] == [
        "reference-context-index",
        "reference-context-index",
        "reference-context-index",
        "reference-context-index",
        "reference-context-index",
        "reference-context-join",
        "reference-context-aggregate",
        "reference-context-report",
    ]
    assert checkpoints[0] == ("reference-context-index", 0, 0)
    assert checkpoints[5:] == [
        ("reference-context-join", 1, 1),
        ("reference-context-aggregate", 1, 1),
        ("reference-context-report", 1, 1),
    ]
    assert "private-target" not in json.dumps(checkpoints)
    assert report["reference_occurrences"] == 1


def test_context_failure_code_rejects_values_outside_allowlist():
    with pytest.raises(
        ValueError, match="invalid reference context diagnostic code"
    ):
        ReferenceContextError("private-source-value", "must not be retained")


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


def test_nested_subject_and_duplicate_targets_have_exact_occurrence_addresses():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <outer rdf:about="urn:subject">
        <wrapper><edge rdf:resource="urn:target"/></wrapper>
      </outer>
      <target rdf:about="urn:target"/>
      <target rdf:about="urn:target"/>
    </root>"""
    report = screen_reference_context(xml)
    row = next(
        row
        for row in report["strata"]
        if row["match_status"] == "ambiguous_exact_literal"
    )
    example = row["examples"][0]
    assert row["predicate_element_qname"] == "{http://schema.pbs.gov.au/}edge"
    assert (
        row["nearest_subject_element_qname"]
        == "{http://schema.pbs.gov.au/}outer"
    )
    assert (
        example["predicate_element"]["qname"]
        == "{http://schema.pbs.gov.au/}edge"
    )
    assert example["predicate_element"]["occurrence"].endswith("}edge/1")
    assert (
        example["nearest_subject_element"]["qname"]
        == "{http://schema.pbs.gov.au/}outer"
    )
    assert example["nearest_subject_element"]["occurrence"].endswith("}outer/1")
    assert example["target_multiplicity"] == 2
    assert [target["qname"] for target in example["targets"]] == [
        "{http://schema.pbs.gov.au/}target",
        "{http://schema.pbs.gov.au/}target",
    ]
    assert [
        target["occurrence"].rsplit("/", 1)[-1] for target in example["targets"]
    ] == ["1", "2"]
    serialized = json.dumps(report)
    assert "urn:subject" not in serialized
    assert "urn:target" not in serialized


def test_reference_and_target_base_contexts_are_reported_without_resolution():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <target rdf:about="https://example.invalid/clean"/>
      <edge rdf:resource="https://example.invalid/clean"/>
      <scope xml:base="https://example.invalid/base/">
        <target rdf:about="https://example.invalid/target-based"/>
      </scope>
      <edge rdf:resource="https://example.invalid/target-based"/>
      <target rdf:about="https://example.invalid/reference-based"/>
      <scope xml:base="https://example.invalid/other/">
        <edge rdf:resource="https://example.invalid/reference-based"/>
      </scope>
      <target rdf:about="https://example.invalid/shared"/>
      <edge rdf:resource="https://example.invalid/shared"/>
      <scope xml:base="https://example.invalid/scope/">
        <edge rdf:resource="https://example.invalid/shared"/>
      </scope>
    </root>"""
    report = screen_reference_context(xml)
    assert report["unique_exact_literal_no_xml_base_candidates"] == 2
    rows = [
        row
        for row in report["strata"]
        if row["kind"] == "rdf_resource"
        and row["match_status"] == "unique_exact_literal"
    ]
    target_contexts = [
        (row["xml_base_context"], example["targets"][0]["xml_base_context"])
        for row in rows
        for example in row["examples"]
    ]
    assert ("no_xml_base", "no_xml_base") in target_contexts
    assert ("no_xml_base", "xml_base_present") in target_contexts
    assert ("xml_base_present", "no_xml_base") in target_contexts
    reference_contexts_by_target: dict[str, set[str]] = {}
    for row in rows:
        for example in row["examples"]:
            for target in example["targets"]:
                reference_contexts_by_target.setdefault(
                    target["occurrence"], set()
                ).add(row["xml_base_context"])
    assert {
        "no_xml_base",
        "xml_base_present",
    } in reference_contexts_by_target.values()
    assert report["uri_resolution_performed"] is False
    serialized = json.dumps(report)
    assert "example.invalid" not in serialized


def test_xml_id_is_not_misreported_as_an_rdf_subject():
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:xlink="http://www.w3.org/1999/xlink">
      <identifier xml:id="private-id"><link xlink:href="#private-id"/></identifier>
    </root>"""
    report = screen_reference_context(xml)
    example = next(
        row["examples"][0]
        for row in report["strata"]
        if row["kind"] == "xlink_href"
    )
    assert example["nearest_subject_element"] is None
    assert example["nearest_identifier_element"]["qname"] == (
        "{http://schema.pbs.gov.au/}identifier"
    )
    assert example["nearest_identifier_element"]["occurrence"].endswith(
        "}identifier/1"
    )
    assert report["semantic_relationships_qualified"] is False


@pytest.mark.parametrize(
    ("attribute", "namespaces"),
    [
        (b'xml:id="', b""),
        (
            b'rdf:about="',
            b' xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"',
        ),
        (
            b'rdf:resource="',
            b' xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"',
        ),
        (b'xlink:href="', b' xmlns:xlink="http://www.w3.org/1999/xlink"'),
    ],
)
def test_oversized_indexed_literals_fail_closed(
    attribute: bytes, namespaces: bytes
) -> None:
    literal = b"x" * (context_module.MAX_LITERAL_BYTES + 1)
    xml = (
        b'<root xmlns="http://schema.pbs.gov.au/"'
        + namespaces
        + b"><entry "
        + attribute
        + literal
        + b'"/></root>'
    )
    with pytest.raises(ValueError, match="literal byte bound"):
        screen_reference_context(xml)


def test_high_cardinality_context_strata_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(context_module, "MAX_STRATA", 1)
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <first rdf:resource="one"/><second rdf:resource="two"/>
    </root>"""
    with pytest.raises(ValueError, match="stratum bound"):
        screen_reference_context(xml)


def test_global_example_budget_records_omitted_occurrences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(context_module, "MAX_REPORT_EXAMPLES", 1)
    xml = b"""<root xmlns="http://schema.pbs.gov.au/"
      xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <target rdf:about="https://example.invalid/one"/>
      <target rdf:about="https://example.invalid/two"/>
      <edge rdf:resource="https://example.invalid/one"/>
      <edge rdf:resource="https://example.invalid/two"/>
    </root>"""
    report = screen_reference_context(xml)
    assert report["examples_emitted"] == 1
    assert report["examples_omitted"] == 1
    assert sum(row["examples_omitted"] for row in report["strata"]) == 1


def test_context_screen_rejects_wrong_root():
    with pytest.raises(ValueError, match="root does not match"):
        screen_reference_context(b"<wrong/>")
