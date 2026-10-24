"""Bounded, value-free URI-resolution diagnostics for one PBS XML member.

The screen reports aggregate resolution outcomes only. It never exports URI
values, literals, payload excerpts, external targets, or semantic edges.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit

from .parser_safety import ParserPolicy, ParserSafetyError, iter_xml_events

XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
RDF_ABOUT = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about"
RDF_RESOURCE = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
MAX_MEMBER_BYTES = 512 * 1024**2
MAX_URI_CHARS = 16_384
MAX_INDEXED_URI_CHARS = 32 * 1024**2
MAX_ELEMENTS = 20_000_000
MAX_REFERENCE_ROWS = 8_000_000
PBS_NAMESPACE = "http://schema.pbs.gov.au/"
RDF_NAMESPACE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_BAD_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")

_KINDS = {
    RDF_ABOUT: "rdf_about",
    RDF_RESOURCE: "rdf_resource",
    XLINK_HREF: "xlink_href",
}
_QNAME = {
    RDF_ABOUT: "rdf:about",
    RDF_RESOURCE: "rdf:resource",
    XLINK_HREF: "xlink:href",
}
_LOWER_BOUND = 0x20
_DELETE = 0x7F
_NCNAME_MIDDLE_DOT = 0xB7
_NCNAME_START_RANGES = (
    (0x41, 0x5A),
    (0x61, 0x7A),
    (0xC0, 0xD6),
    (0xD8, 0xF6),
    (0xF8, 0x2FF),
    (0x370, 0x37D),
    (0x37F, 0x1FFF),
    (0x200C, 0x200D),
    (0x2070, 0x218F),
    (0x2C00, 0x2FEF),
    (0x3001, 0xD7FF),
    (0xF900, 0xFDCF),
    (0xFDF0, 0xFFFD),
    (0x10000, 0xEFFFF),
)
_NCNAME_EXTRA_RANGES = ((0x30, 0x39), (0x300, 0x36F), (0x203F, 0x2040))


def _valid_reference(value: str) -> bool:
    return (
        not any(
            ord(char) <= _LOWER_BOUND or ord(char) == _DELETE or char == "\\"
            for char in value
        )
        and _BAD_PERCENT.search(value) is None
    )


def _is_ncname(value: str) -> bool:
    """Return whether a value satisfies the XML 1.0 NCName production."""
    if not value or ":" in value:
        return False
    first = ord(value[0])
    if value[0] != "_" and not any(
        start <= first <= end for start, end in _NCNAME_START_RANGES
    ):
        return False
    return all(
        char in "_.-"
        or any(start <= ord(char) <= end for start, end in _NCNAME_START_RANGES)
        or any(start <= ord(char) <= end for start, end in _NCNAME_EXTRA_RANGES)
        or ord(char) == _NCNAME_MIDDLE_DOT
        for char in value[1:]
    )


def _absolute_base(value: str | None) -> str | None:
    if value is None or not _valid_reference(value) or not _SCHEME.match(value):
        return None
    try:
        parts = urlsplit(value)
        if not parts.scheme:
            return None
        # Accessing port also validates malformed bracket/port authorities.
        _ = parts.port
    except ValueError:
        return None
    return value


def _effective_base(parent: str | None, override: str | None) -> str | None:
    if override is None:
        return parent
    if not _valid_reference(override):
        return None
    if _SCHEME.match(override):
        return _absolute_base(override)
    if parent is None:
        return None
    try:
        resolved = urljoin(parent, override)
    except ValueError:
        return None
    return _absolute_base(resolved)


def _resolve(value: str | None, base: str | None) -> str | None:
    if value is None or not value or len(value) > MAX_URI_CHARS:
        return None
    if not _valid_reference(value):
        return None
    if _SCHEME.match(value):
        return _absolute_base(value)
    if base is None:
        return None
    try:
        return _absolute_base(urljoin(base, value))
    except ValueError:
        return None


def _safe_qname(name: str) -> str:
    if name.startswith(f"{{{PBS_NAMESPACE}}}"):
        return f"pbs:{name.split('}', 1)[1]}"
    if name.startswith(f"{{{RDF_NAMESPACE}}}"):
        return f"rdf:{name.split('}', 1)[1]}"
    return "other_or_unresolved"


@dataclass
class _ScreenIndex:
    rdf_definitions: Counter[str] = field(default_factory=Counter)
    xml_ids: Counter[str] = field(default_factory=Counter)
    refs: list[tuple[str, str, str | None, bool]] = field(default_factory=list)
    definition_counts: Counter[str] = field(default_factory=Counter)
    definition_element_qnames: Counter[str] = field(default_factory=Counter)
    predicate_qnames: Counter[str] = field(default_factory=Counter)
    reference_element_qnames: Counter[str] = field(default_factory=Counter)
    reference_attribute_qnames: Counter[str] = field(default_factory=Counter)
    invalid_xml_id_count: int = 0
    indexed_uri_chars: int = 0
    elements: int = 0


def _record_attribute(
    index: _ScreenIndex,
    attribute: str,
    value: str,
    effective_base: str | None,
    *,
    has_base_override: bool,
    element_qname: str,
) -> None:
    if len(value) > MAX_URI_CHARS:
        raise ValueError("PBS URI screen URI bound exceeded")
    if attribute in {XML_ID, RDF_ABOUT, RDF_RESOURCE, XLINK_HREF}:
        index.indexed_uri_chars += len(value)
        if index.indexed_uri_chars > MAX_INDEXED_URI_CHARS:
            raise ValueError("PBS URI screen indexed URI bound exceeded")
    if attribute == XML_ID:
        index.definition_counts["xml:id"] += 1
        index.definition_element_qnames[element_qname] += 1
        if _is_ncname(value):
            index.xml_ids[value] += 1
        else:
            index.invalid_xml_id_count += 1
    elif attribute == RDF_ABOUT:
        index.definition_counts["rdf:about"] += 1
        index.definition_element_qnames[element_qname] += 1
        resolved = _resolve(value, effective_base)
        if resolved is not None:
            index.rdf_definitions[resolved] += 1
    elif attribute in {RDF_RESOURCE, XLINK_HREF}:
        if len(index.refs) >= MAX_REFERENCE_ROWS:
            raise ValueError("PBS URI screen reference bound exceeded")
        index.refs.append((attribute, value, effective_base, has_base_override))
        index.reference_element_qnames[element_qname] += 1
        index.reference_attribute_qnames[_QNAME[attribute]] += 1


def _index_member(
    member: bytes,
    progress: Callable[[str, int, int], None] | None,
) -> _ScreenIndex:
    index = _ScreenIndex()
    base_stack: list[str | None] = []
    inherited_override: list[bool] = []
    policy = ParserPolicy(
        max_bytes=MAX_MEMBER_BYTES,
        max_xml_depth=256,
        max_xml_elements=MAX_ELEMENTS,
        max_xml_text_bytes=MAX_MEMBER_BYTES,
    )
    for event, element, parent in iter_xml_events(member, policy=policy):
        if event != "start":
            if parent is not None:
                parent.remove(element)
            element.clear()
            base_stack.pop()
            inherited_override.pop()
            continue
        index.elements += 1
        if index.elements > MAX_ELEMENTS:
            raise ValueError("PBS URI screen element bound exceeded")
        parent_base = base_stack[-1] if base_stack else None
        parent_override = (
            inherited_override[-1] if inherited_override else False
        )
        has_override = XML_BASE in element.attrib
        effective = _effective_base(parent_base, element.attrib.get(XML_BASE))
        base_stack.append(effective)
        effective_override = parent_override or has_override
        inherited_override.append(effective_override)
        if parent is not None and (
            parent.tag == f"{{{RDF_NAMESPACE}}}Description"
            or RDF_ABOUT in parent.attrib
        ):
            index.predicate_qnames[_safe_qname(element.tag)] += 1
        element_qname = _safe_qname(element.tag)
        for attribute, value in element.attrib.items():
            _record_attribute(
                index,
                attribute,
                value,
                effective,
                has_base_override=effective_override,
                element_qname=element_qname,
            )
        if progress is not None and index.elements % 100_000 == 0:
            progress(
                "pbs-uri-screen-parse",
                index.elements // 100_000,
                index.elements,
            )
    return index


def screen_pbs_native_uris(  # ruff: ignore[too-many-branches] -- explicit outcome matrix is the auditable report contract
    member: bytes,
    *,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, Any]:
    """Screen one XML member using strict, in-memory URI resolution.

    Absolute RDF ``about``/``resource`` references are comparable only after
    both resolve to the same absolute URI. Fragment-only XLink references are
    comparable to XML IDs only when no ``xml:base`` override occurs anywhere
    on the referencing element's ancestry. No archive URL is supplied or
    inferred as a document base.
    """
    if len(member) > MAX_MEMBER_BYTES:
        raise ValueError("PBS URI screen member byte bound exceeded")
    # Only bounded in-memory identities/counters survive element release.
    try:
        index = _index_member(member, progress)
    except ParserSafetyError as exc:
        raise ValueError("PBS URI screen XML is malformed or unsafe") from exc

    # XML IDs are member-local anchors; retain a count so ambiguous IDs abstain.
    outcomes: dict[str, Counter[str]] = defaultdict(Counter)
    qname_outcomes: dict[str, Counter[str]] = defaultdict(Counter)
    for kind, value, effective, has_override in index.refs:
        if kind == XLINK_HREF and value.startswith("#") and len(value) > 1:
            fragment = value[1:]
            if has_override:
                outcome = "abstained_xml_base_override"
            elif _BAD_PERCENT.search(fragment):
                outcome = "abstained_malformed_fragment"
            else:
                try:
                    target = unquote(fragment, errors="strict")
                except UnicodeDecodeError:
                    outcome = "abstained_malformed_fragment"
                else:
                    count = index.xml_ids[target]
                    outcome = (
                        "same_member_unique_id"
                        if count == 1
                        else "ambiguous_id_target"
                        if count > 1
                        else "missing_id_target"
                    )
        elif kind == XLINK_HREF:
            outcome = "external_or_nonfragment_xlink_unresolved"
        else:
            resolved = _resolve(value, effective)
            if resolved is None:
                outcome = (
                    "unresolved_unknown_base"
                    if effective is None and not _SCHEME.match(value)
                    else "unresolved_invalid_uri"
                )
            else:
                targets = index.rdf_definitions[resolved]
                outcome = (
                    "absolute_uri_unique_candidate"
                    if targets == 1
                    else "absolute_uri_ambiguous_candidate"
                    if targets > 1
                    else "absolute_uri_no_member_definition"
                )
        label = _KINDS[kind]
        outcomes[label][outcome] += 1
        qname_outcomes[_QNAME[kind]][outcome] += 1

    if progress is not None:
        progress("pbs-uri-screen-classify", 1, len(index.refs))
    return {
        "schema_id": "global-medicines-atlas.pbs-native-uri-screen",
        "schema_version": 1,
        "native_member_bytes": len(member),
        "xml_elements": index.elements,
        "definition_counts_by_qname": {
            qname: index.definition_counts.get(qname, 0)
            for qname in ("rdf:about", "xml:id")
        },
        "invalid_xml_id_count": index.invalid_xml_id_count,
        "definition_element_qname_counts": dict(
            sorted(index.definition_element_qnames.items())
        ),
        "predicate_qname_counts": dict(sorted(index.predicate_qnames.items())),
        "target_element_qname_counts": dict(
            sorted(index.reference_element_qnames.items())
        ),
        "target_attribute_qname_counts": {
            qname: index.reference_attribute_qnames.get(qname, 0)
            for qname in ("rdf:resource", "xlink:href")
        },
        "reference_counts_by_kind": {
            kind: sum(outcomes[kind].values())
            for kind in ("rdf_resource", "xlink_href")
        },
        "reference_counts_by_qname": {
            qname: index.reference_attribute_qnames.get(qname, 0)
            for qname in ("rdf:resource", "xlink:href")
        },
        "outcome_counts_by_kind": {
            kind: dict(sorted(counts.items()))
            for kind, counts in sorted(outcomes.items())
        },
        "outcome_counts_by_qname": {
            name: dict(sorted(counts.items()))
            for name, counts in sorted(qname_outcomes.items())
        },
        "uri_resolution_performed": True,
        "uri_values_emitted": False,
        "literal_values_emitted": False,
        "payload_emitted": False,
        "external_targets_fetched": 0,
        "semantic_relationships_qualified": False,
        "precision_claimed": False,
        "rights_conclusions_made": False,
        "admissions": 0,
        "publications": 0,
        "canaries": 0,
    }
