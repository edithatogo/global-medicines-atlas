"""Shared bounded parsing contracts for untrusted source payloads."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import cast
from xml.etree import (  # ruff: ignore[suspicious-xml-etree-import]
    ElementTree as ET,
)


class ParserSafetyError(ValueError):
    """An input exceeded a parser safety contract."""


@dataclass(frozen=True, slots=True)
class ParserPolicy:
    """Resource ceilings applied before and during parsing."""

    max_bytes: int = 8 * 1024 * 1024
    max_xml_depth: int = 64
    max_xml_elements: int = 100_000
    max_xml_text_bytes: int = 8 * 1024 * 1024
    chunk_bytes: int = 64 * 1024

    def __post_init__(self) -> None:
        if (
            min(
                self.max_bytes,
                self.max_xml_depth,
                self.max_xml_elements,
                self.max_xml_text_bytes,
                self.chunk_bytes,
            )
            < 1
        ):
            raise ValueError("parser policy limits must be positive")


DEFAULT_PARSER_POLICY = ParserPolicy()


def _consume_events(
    parser: ET.XMLPullParser[ET.Element],
    *,
    policy: ParserPolicy,
    state: list[int],
) -> ET.Element | None:
    root: ET.Element | None = None
    events = cast(
        "Iterator[tuple[str, ET.Element]]",
        parser.read_events(),
    )
    for event, element in events:
        if event == "start":
            state[0] += 1
            state[1] += 1
            if root is None:
                root = element
            if state[0] > policy.max_xml_depth:
                raise ParserSafetyError("XML nesting depth limit exceeded")
            if state[1] > policy.max_xml_elements:
                raise ParserSafetyError("XML element count limit exceeded")
        else:
            state[2] += len((element.text or "").encode())
            state[2] += len((element.tail or "").encode())
            if state[2] > policy.max_xml_text_bytes:
                raise ParserSafetyError("XML text size limit exceeded")
            state[0] -= 1
    return root


def parse_xml(
    payload: bytes,
    *,
    policy: ParserPolicy = DEFAULT_PARSER_POLICY,
) -> ET.Element:
    """Parse XML incrementally while enforcing structural resource ceilings."""
    if len(payload) > policy.max_bytes:
        raise ParserSafetyError("XML payload exceeds the byte limit")
    upper = payload.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ParserSafetyError("XML payload must not contain a DTD or entity")

    parser: ET.XMLPullParser[ET.Element] = ET.XMLPullParser(
        events=("start", "end")
    )
    state = [0, 0, 0]
    root: ET.Element | None = None
    try:
        for offset in range(0, len(payload), policy.chunk_bytes):
            parser.feed(payload[offset : offset + policy.chunk_bytes])
            candidate = _consume_events(parser, policy=policy, state=state)
            if root is None:
                root = candidate
        parser.close()
    except ET.ParseError as error:
        raise ParserSafetyError("XML payload is not well formed") from error
    if root is None:
        raise ParserSafetyError("XML payload has no document element")
    return root
