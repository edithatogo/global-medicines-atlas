"""Synthetic negative controls for PBS reference matcher behavior.

These fixtures contain no source values. They verify the lexical screen's
candidate accounting and, especially, that a candidate never becomes a
qualified semantic relationship without contextual review.
"""

from __future__ import annotations

import pytest
from test_au_pbs_v3 import _zip  # ruff: ignore[import-private-name]
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name]
)
from test_pbs_historical_silver import PATH, SOURCE

from global_medicines_atlas.parser_safety import ParserSafetyError
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)
from global_medicines_atlas.pbs_native_reference_screen import (
    screen_native_references,
)
from global_medicines_atlas.pbs_reference_context import (
    screen_reference_context,
)

_HEADER = b"""<root xmlns="http://schema.pbs.gov.au/"
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:xlink="http://www.w3.org/1999/xlink"
 xmlns:xml="http://www.w3.org/XML/1998/namespace">"""
_FOOTER = b"</root>"


def _screen(body: bytes) -> dict[str, object]:
    member = _HEADER + body + _FOOTER
    archive = _zip([(PATH, member)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    return screen_native_references(archive, member, parent, binding)


def _context(body: bytes) -> dict[str, object]:
    return screen_reference_context(_HEADER + body + _FOOTER)


@pytest.mark.parametrize(
    ("name", "body", "expected", "expected_occurrences"),
    [
        (
            "duplicate target",
            (
                b'<a rdf:about="urn:fixture:item"/><a rdf:about="urn:fixture:item"/>'
                b'<b rdf:resource="urn:fixture:item"/>'
            ),
            "ambiguous_exact_literal",
            1,
        ),
        (
            "wrong target type",
            (
                b'<a xml:id="fixture-item"/><b rdf:resource="fixture-item"/>'
                b'<c rdf:about="fixture-about"/><d xlink:href="#fixture-about"/>'
            ),
            "no_exact_literal",
            2,
        ),
        (
            "missing target",
            b'<b rdf:resource="urn:fixture:absent"/>',
            "no_exact_literal",
            1,
        ),
        (
            "case mismatch",
            b'<a rdf:about="urn:fixture:Item"/><b rdf:resource="urn:fixture:item"/>',
            "no_exact_literal",
            1,
        ),
        (
            "nested xml base",
            (
                b'<group xml:base="https://one.invalid/root/">'
                b'<a rdf:about="item"/></group>'
                b'<group xml:base="https://two.invalid/root/">'
                b'<b rdf:resource="item"/></group>'
            ),
            "unique_exact_literal",
            1,
        ),
        (
            "external URI",
            b'<b rdf:resource="https://outside.invalid/concept/1"/>',
            "no_exact_literal",
            1,
        ),
    ],
)
def test_negative_controls_remain_unqualified(
    name: str, body: bytes, expected: str, expected_occurrences: int
) -> None:
    report = _screen(body)
    kind_counts = report["reference_kind_status_counts"]
    assert isinstance(kind_counts, dict), name
    assert kind_counts["rdf_resource"][expected] == 1, name
    assert report["semantic_relationships_qualified"] is False, name
    assert report["native_values_emitted"] is False, name
    assert report["external_targets_fetched"] == 0, name
    assert report["new_sources"] == 0, name

    context = _context(body)
    strata = context["strata"]
    assert isinstance(strata, list), name
    assert sum(row["occurrences"] for row in strata) == expected_occurrences, (
        name
    )
    assert context["semantic_relationships_qualified"] is False, name
    assert context["uri_resolution_performed"] is False, name
    assert context["external_targets_fetched"] == 0, name
    assert context["literal_values_emitted"] is False, name


def test_lexical_candidate_with_nested_base_is_an_abstention() -> None:
    report = _screen(
        b'<group xml:base="https://one.invalid/">'
        b'<a rdf:about="relative"/></group>'
        b'<group xml:base="https://two.invalid/">'
        b'<b rdf:resource="relative"/></group>'
    )
    # Literal equality yields a candidate, but the distinct nested bases mean
    # the context is insufficient to assert that both references resolve to
    # the same resource.
    assert report["reference_status_counts"] == {"unique_exact_literal": 1}
    assert report["semantic_relationships_qualified"] is False
    assert report["uri_normalization_or_base_resolution"] is False

    context = _context(
        b'<group xml:base="https://one.invalid/">'
        b'<a rdf:about="relative"/></group>'
        b'<group xml:base="https://two.invalid/">'
        b'<b rdf:resource="relative"/></group>'
    )
    strata = context["strata"]
    assert isinstance(strata, list)
    assert context["semantic_relationships_qualified"] is False
    assert all(row["xml_base_context"] == "xml_base_present" for row in strata)
    assert sum(row["occurrences"] for row in strata) == 1


def test_malformed_xml_fails_closed_without_a_partial_report() -> None:
    member = _HEADER + b'<a rdf:about="unterminated></root>'
    archive = _zip([(PATH, member)])
    parent = _receipt(archive, SOURCE)
    with pytest.raises(ParserSafetyError, match="not well formed"):
        build_pbs_xml_member_binding(archive, parent)
    with pytest.raises(ParserSafetyError, match="not well formed"):
        screen_reference_context(member)
