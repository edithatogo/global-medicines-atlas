from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from global_medicines_atlas.parser_safety import (
    ParserPolicy,
    ParserSafetyError,
    parse_xml,
)

pytestmark = pytest.mark.edge


def test_parse_xml_rejects_dtd_entities_and_oversized_payloads() -> None:
    with pytest.raises(ParserSafetyError, match="DTD or entity"):
        parse_xml(b'<!DOCTYPE x [<!ENTITY y "z">]><x>&y;</x>')

    with pytest.raises(ParserSafetyError, match="byte limit"):
        parse_xml(b"<x>12345</x>", policy=ParserPolicy(max_bytes=8))


def test_parse_xml_enforces_depth_element_and_text_limits() -> None:
    with pytest.raises(ParserSafetyError, match="nesting depth"):
        parse_xml(
            b"<a><b><c /></b></a>",
            policy=ParserPolicy(max_xml_depth=2),
        )
    with pytest.raises(ParserSafetyError, match="element count"):
        parse_xml(
            b"<a><b /><c /></a>",
            policy=ParserPolicy(max_xml_elements=2),
        )
    with pytest.raises(ParserSafetyError, match="text size"):
        parse_xml(
            b"<a>12345</a>",
            policy=ParserPolicy(max_xml_text_bytes=4),
        )


@given(st.integers(min_value=1, max_value=20))
def test_parse_xml_depth_boundary_is_deterministic(depth: int) -> None:
    payload = ("<x>" * depth + "</x>" * depth).encode()
    policy = ParserPolicy(max_xml_depth=depth)

    root = parse_xml(payload, policy=policy)

    assert root.tag == "x"
