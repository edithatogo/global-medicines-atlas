"""Bounded, value-free URI-resolution diagnostics for one PBS XML member.

The screen reports aggregate resolution outcomes only. It never exports URI
values, literals, payload excerpts, external targets, or semantic edges.
"""

from __future__ import annotations

import hashlib
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
# Keep the aggregate URI/index budget consistent with the already-enforced
# maximum member size, rather than imposing a smaller arbitrary ceiling on a
# valid pinned member. Individual URIs, rows, and XML elements stay bounded.
MAX_INDEXED_URI_CHARS = MAX_MEMBER_BYTES
MAX_ELEMENTS = 20_000_000
MAX_REFERENCE_ROWS = 8_000_000
MAX_REVIEW_CASES = 64
MAX_REVIEW_OCCURRENCE_ADDRESS_BYTES = 4096
URI_SCREEN_SCHEMA_VERSION = 2
PBS_NAMESPACE = "http://schema.pbs.gov.au/"
RDF_NAMESPACE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_BAD_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_REVIEW_PBS_ELEMENTS = frozenset({
    "ATC",
    "administrative-advice",
    "administrative-advice-reference",
    "age",
    "amount",
    "assessment",
    "benefit-type",
    "block-container",
    "brand-name",
    "care-type",
    "caution",
    "caution-reference",
    "chart-categories-list",
    "chart-category",
    "clinical",
    "code",
    "condition",
    "condition-parameter",
    "condition-reference",
    "container",
    "container-definition",
    "content",
    "contribution",
    "copayment",
    "criteria-reference",
    "discount",
    "dispensing-rule",
    "dispensing-rule-reference",
    "dpmq",
    "episodicity",
    "episodicity-reference",
    "ex-manufacturer",
    "fee",
    "fee-definition",
    "hundred-grams",
    "incentive",
    "increase",
    "indication",
    "indication-reference",
    "location",
    "markup",
    "markup-band",
    "maximum-prescribable",
    "medication-chart-definition",
    "member-of",
    "moved",
    "mp",
    "mp-reference",
    "mpp",
    "mpp-reference",
    "mpuu",
    "mpuu-reference",
    "one-gram",
    "one-tenth",
    "organisation",
    "organisation-reference",
    "other",
    "parameter-reference",
    "patient",
    "pharmaceutical-item",
    "pharmaceutical-item-reference",
    "pharmacist",
    "population",
    "preferred-term",
    "prescriber",
    "prescriber-instruction",
    "prescriber-instruction-reference",
    "prescribing-rule",
    "previous",
    "pricing",
    "pricing-model",
    "product-listing",
    "program",
    "quantity",
    "recovery-price-reference",
    "restriction",
    "restriction-reference",
    "safety-net",
    "severity",
    "severity-reference",
    "sex",
    "ten-grams",
    "threshold",
    "to-pharmacist",
    "tpp",
    "tpp-reference",
    "tpuu",
    "tpuu-reference",
    "treatment",
    "treatment-parameter",
    "treatment-phase",
    "treatment-phase-reference",
    "unit-of-measure",
})
_REVIEW_QNAME_ALLOWLIST = {
    PBS_NAMESPACE: ("pbs", _REVIEW_PBS_ELEMENTS),
    "http://pbs.gov.au/": (
        "pbsdata",
        frozenset({
            "applies-to",
            "assessment",
            "concept",
            "fee",
            "has-fee",
            "has-revision",
            "has-revision-history",
            "patient",
            "pricing",
        }),
    ),
    "http://extension.schema.pbs.gov.au/": (
        "pbsext",
        frozenset({"ex-manufacturer"}),
    ),
    "http://www.w3.org/2004/02/skos/core#": (
        "skos",
        frozenset({"Concept"}),
    ),
}
URI_SCREEN_FAILURE_CODES = frozenset({
    "uri-value-bound",
    "indexed-uri-bound",
    "reference-row-bound",
    "review-occurrence-absent",
    "review-case-bound",
    "review-case-binding-invalid",
    "element-bound",
    "member-byte-bound",
    "xml-malformed-or-unsafe",
})


class UriScreenError(ValueError):
    """A scanner-owned failure with a fixed, value-free diagnostic code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code if code in URI_SCREEN_FAILURE_CODES else "unknown"
        super().__init__(message)


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
    if value is None or len(value) > MAX_URI_CHARS:
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
    for namespace, (prefix, allowed_names) in _REVIEW_QNAME_ALLOWLIST.items():
        if name.startswith(f"{{{namespace}}}"):
            local_name = name.split("}", 1)[1]
            return (
                f"{prefix}:{local_name}"
                if local_name in allowed_names
                else "other_or_unresolved"
            )
    if name.startswith(f"{{{RDF_NAMESPACE}}}"):
        return (
            "rdf:Description"
            if name.split("}", 1)[1] == "Description"
            else "other_or_unresolved"
        )
    return "other_or_unresolved"


def _safe_review_qname(name: str) -> str:
    """Expose only allowlisted vocabulary QNames in selected case bindings."""
    return _safe_qname(name)


@dataclass
class _ScreenIndex:
    rdf_definitions: Counter[str] = field(default_factory=Counter)
    xml_ids: Counter[str] = field(default_factory=Counter)
    refs: list[tuple[str, str, str | None, bool, str | None, str | None]] = (
        field(default_factory=list)
    )
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
    element_address: str,
    selected_addresses: set[str],
) -> None:
    if len(value) > MAX_URI_CHARS:
        raise UriScreenError(
            "uri-value-bound", "PBS URI screen URI bound exceeded"
        )
    if attribute in {XML_ID, RDF_ABOUT, RDF_RESOURCE, XLINK_HREF}:
        index.indexed_uri_chars += len(value)
        if index.indexed_uri_chars > MAX_INDEXED_URI_CHARS:
            raise UriScreenError(
                "indexed-uri-bound", "PBS URI screen indexed URI bound exceeded"
            )
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
            raise UriScreenError(
                "reference-row-bound", "PBS URI screen reference bound exceeded"
            )
        occurrence = f"{element_address}/attributes/{_pointer(attribute)}"
        index.refs.append((
            attribute,
            value,
            effective_base,
            has_base_override,
            occurrence if occurrence in selected_addresses else None,
            element_qname if occurrence in selected_addresses else None,
        ))
        index.reference_element_qnames[element_qname] += 1
        index.reference_attribute_qnames[_QNAME[attribute]] += 1


def _pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _bind_review_cases(
    review_cases: list[dict[str, str]] | None,
    occurrence_outcomes: dict[str, str],
    occurrence_contexts: dict[str, dict[str, str | None]],
) -> list[dict[str, Any]]:
    if review_cases is None:
        return []
    bindings: list[dict[str, Any]] = []
    for case in review_cases:
        case_id = case.get("case_id", "")
        address = case.get("reference_occurrence", "")
        outcome = occurrence_outcomes.get(address)
        if outcome is None:
            raise UriScreenError(
                "review-occurrence-absent",
                "PBS URI review occurrence is absent",
            )
        bindings.append({
            "case_id": case_id,
            "reference_occurrence_sha256": hashlib.sha256(
                address.encode("utf-8")
            ).hexdigest(),
            **occurrence_contexts[address],
            "uri_resolution": outcome,
            "semantic_review_state": "pending",
            "adjudication": "unreviewed",
            "semantic_relationship_qualified": False,
        })
    return bindings


def _review_case_addresses(
    review_cases: list[dict[str, str]] | None,
) -> set[str]:
    if review_cases is None:
        return set()
    if len(review_cases) > MAX_REVIEW_CASES:
        raise UriScreenError(
            "review-case-bound", "PBS URI review case bound exceeded"
        )
    addresses: set[str] = set()
    case_ids: set[str] = set()
    for case in review_cases:
        case_id = case.get("case_id", "")
        address = case.get("reference_occurrence", "")
        if (
            re.fullmatch(r"[0-9a-f]{64}", case_id) is None
            or not address
            or len(address.encode("utf-8"))
            > MAX_REVIEW_OCCURRENCE_ADDRESS_BYTES
            or case_id in case_ids
            or address in addresses
        ):
            raise UriScreenError(
                "review-case-binding-invalid",
                "PBS URI review case binding is invalid",
            )
        case_ids.add(case_id)
        addresses.add(address)
    return addresses


def _index_member(
    member: bytes,
    progress: Callable[[str, int, int], None] | None,
    selected_addresses: set[str],
) -> _ScreenIndex:
    index = _ScreenIndex()
    base_stack: list[str | None] = []
    inherited_override: list[bool] = []
    address_stack: list[str] = []
    child_counts: list[Counter[str]] = []
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
            address_stack.pop()
            child_counts.pop()
            continue
        index.elements += 1
        if index.elements > MAX_ELEMENTS:
            raise UriScreenError(
                "element-bound", "PBS URI screen element bound exceeded"
            )
        parent_base = base_stack[-1] if base_stack else None
        parent_override = (
            inherited_override[-1] if inherited_override else False
        )
        has_override = XML_BASE in element.attrib
        if parent is None:
            element_address = f"/{_pointer(element.tag)}/1"
        else:
            counts = child_counts[-1]
            counts[element.tag] += 1
            element_address = f"{address_stack[-1]}/{_pointer(element.tag)}/{counts[element.tag]}"
        effective = _effective_base(parent_base, element.attrib.get(XML_BASE))
        base_stack.append(effective)
        effective_override = parent_override or has_override
        inherited_override.append(effective_override)
        address_stack.append(element_address)
        child_counts.append(Counter())
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
                element_address=element_address,
                selected_addresses=selected_addresses,
            )
        if progress is not None and index.elements % 100_000 == 0:
            progress(
                "pbs-uri-screen-parse",
                index.elements // 100_000,
                index.elements,
            )
    return index


def _review_target_contexts(  # ruff: ignore[too-many-branches] -- bounded streaming parse keeps only selected target identities
    member: bytes,
    selected_targets: set[tuple[str, str]],
    progress: Callable[[str, int, int], None] | None,
) -> dict[tuple[str, str], tuple[str, str]]:
    """Locate only selected unique targets in a bounded second XML pass."""
    if not selected_targets:
        return {}
    contexts: dict[tuple[str, str], tuple[str, str]] = {}
    base_stack: list[str | None] = []
    address_stack: list[str] = []
    child_counts: list[Counter[str]] = []
    elements = 0
    policy = ParserPolicy(
        max_bytes=MAX_MEMBER_BYTES,
        max_xml_depth=256,
        max_xml_elements=MAX_ELEMENTS,
        max_xml_text_bytes=MAX_MEMBER_BYTES,
    )
    try:  # ruff: ignore[too-many-statements-in-try-clause] -- one parser pass maintains synchronized bounded context stacks
        for event, element, parent in iter_xml_events(member, policy=policy):
            if event != "start":
                if parent is not None:
                    parent.remove(element)
                element.clear()
                base_stack.pop()
                address_stack.pop()
                child_counts.pop()
                continue
            elements += 1
            if elements > MAX_ELEMENTS:
                raise UriScreenError(
                    "element-bound", "PBS URI screen element bound exceeded"
                )
            if parent is None:
                element_address = f"/{_pointer(element.tag)}/1"
            else:
                counts = child_counts[-1]
                counts[element.tag] += 1
                element_address = (
                    f"{address_stack[-1]}/{_pointer(element.tag)}"
                    f"/{counts[element.tag]}"
                )
            parent_base = base_stack[-1] if base_stack else None
            effective_base = _effective_base(
                parent_base, element.attrib.get(XML_BASE)
            )
            base_stack.append(effective_base)
            address_stack.append(element_address)
            child_counts.append(Counter())
            element_qname = _safe_review_qname(element.tag)
            for attribute, value in element.attrib.items():
                target_key: tuple[str, str] | None = None
                if attribute == XML_ID and _is_ncname(value):
                    target_key = ("xml_id", value)
                elif attribute == RDF_ABOUT:
                    resolved = _resolve(value, effective_base)
                    if resolved is not None:
                        target_key = ("rdf_about", resolved)
                if target_key in selected_targets:
                    if target_key in contexts:
                        raise UriScreenError(
                            "review-case-binding-invalid",
                            "PBS URI review target is not unique",
                        )
                    contexts[target_key] = (
                        element_qname,
                        hashlib.sha256(element_address.encode()).hexdigest(),
                    )
            if progress is not None and elements % 100_000 == 0:
                progress(
                    "pbs-uri-review-target-context",
                    elements // 100_000,
                    elements,
                )
    except ParserSafetyError as exc:
        raise UriScreenError(
            "xml-malformed-or-unsafe",
            "PBS URI review target pass XML is malformed or unsafe",
        ) from exc
    if contexts.keys() != selected_targets:
        raise UriScreenError(
            "review-occurrence-absent",
            "PBS URI review target occurrence is absent",
        )
    return contexts


def screen_pbs_native_uris(  # ruff: ignore[too-many-branches, too-many-locals, too-many-statements] -- explicit outcome matrix and selected-case bindings are the auditable report contract
    member: bytes,
    *,
    progress: Callable[[str, int, int], None] | None = None,
    review_cases: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Screen one XML member using strict, in-memory URI resolution.

    Absolute RDF ``about``/``resource`` references are comparable only after
    both resolve to the same absolute URI. Fragment-only XLink references are
    comparable to XML IDs only when no ``xml:base`` override occurs anywhere
    on the referencing element's ancestry. No archive URL is supplied or
    inferred as a document base.
    """
    if len(member) > MAX_MEMBER_BYTES:
        raise UriScreenError(
            "member-byte-bound", "PBS URI screen member byte bound exceeded"
        )
    selected_addresses = _review_case_addresses(review_cases)
    # Only bounded in-memory identities/counters survive element release.
    try:
        index = _index_member(member, progress, selected_addresses)
    except ParserSafetyError as exc:
        raise UriScreenError(
            "xml-malformed-or-unsafe",
            "PBS URI screen XML is malformed or unsafe",
        ) from exc

    # XML IDs are member-local anchors; retain a count so ambiguous IDs abstain.
    outcomes: dict[str, Counter[str]] = defaultdict(Counter)
    qname_outcomes: dict[str, Counter[str]] = defaultdict(Counter)
    occurrence_outcomes: dict[str, str] = {}
    selected_reference_qnames: dict[str, str] = {}
    selected_reference_kinds: dict[str, str] = {}
    selected_target_by_address: dict[str, tuple[str, str]] = {}
    for (
        kind,
        value,
        effective,
        has_override,
        address,
        element_qname,
    ) in index.refs:
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
                    if (
                        outcome == "same_member_unique_id"
                        and address is not None
                    ):
                        selected_target_by_address[address] = ("xml_id", target)
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
                if (
                    outcome == "absolute_uri_unique_candidate"
                    and address is not None
                ):
                    selected_target_by_address[address] = (
                        "rdf_about",
                        resolved,
                    )
        label = _KINDS[kind]
        outcomes[label][outcome] += 1
        qname_outcomes[_QNAME[kind]][outcome] += 1
        if address is not None:
            occurrence_outcomes[address] = outcome
            selected_reference_qnames[address] = element_qname or ""
            selected_reference_kinds[address] = label

    target_contexts = _review_target_contexts(
        member, set(selected_target_by_address.values()), progress
    )
    occurrence_contexts: dict[str, dict[str, str | None]] = {}
    for address in occurrence_outcomes:
        target_key = selected_target_by_address.get(address)
        target_context = (
            target_contexts.get(target_key) if target_key is not None else None
        )
        occurrence_contexts[address] = {
            "reference_kind": selected_reference_kinds[address],
            "structural_role": (
                "rdf_resource_attribute"
                if selected_reference_kinds[address] == "rdf_resource"
                else "xlink_href_attribute"
            ),
            "reference_element_qname": selected_reference_qnames[address],
            "target_element_qname": (
                target_context[0] if target_context is not None else None
            ),
            "target_occurrence_sha256": (
                target_context[1] if target_context is not None else None
            ),
        }

    case_bindings = _bind_review_cases(
        review_cases, occurrence_outcomes, occurrence_contexts
    )

    if progress is not None:
        progress("pbs-uri-screen-classify", 1, len(index.refs))
    return {
        "schema_id": "global-medicines-atlas.pbs-native-uri-screen",
        "schema_version": URI_SCREEN_SCHEMA_VERSION,
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
        "review_case_uri_bindings": case_bindings,
        "review_case_count": len(case_bindings),
        "review_cases_adjudicated": 0,
        "review_case_sampling_is_probability_based": False,
    }
