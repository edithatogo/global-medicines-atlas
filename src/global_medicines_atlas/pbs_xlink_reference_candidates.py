"""Value-free structural candidates for exact same-member PBS XLink edges.

An emitted edge means only that a literal local XLink fragment resolves to a
unique ``xml:id`` in the same receipt-bound XML member. It is not a medicine,
clinical, terminology, or domain relationship qualification.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, BinaryIO, cast

import orjson

from .adapters.au_pbs import PBS_V3_NAMESPACE, XML_NAMESPACE
from .parser_safety import ParserPolicy, iter_xml_events
from .pbs_member_identity import (
    PbsXmlMemberBinding,
    validate_pbs_xml_member_binding,
)
from .pbs_native_uri_screen import XLINK_HREF, XML_BASE
from .receipts import SourceReceipt

MAX_MEMBER_BYTES = 512 * 1024**2
MAX_ELEMENTS = 20_000_000
MAX_REFERENCES = 1_100_000
MAX_IDENTIFIERS = 600_000
MAX_OUTPUT_EDGES = 1_000_000
# At the pinned 992,456 XLink-reference scale, one compact edge is roughly
# 200 bytes; 512 MiB accommodates that envelope while retaining a hard cap.
MAX_OUTPUT_BYTES = 512 * 1024**2
MAX_INDEX_BYTES = 256 * 1024**2
MIN_INDEX_BYTES = 3 * 4096
MAX_LITERAL_BYTES = 4096
MAX_OCCURRENCE_ADDRESS_BYTES = 4096
XML_ID = f"{{{XML_NAMESPACE}}}id"
_NCNAME_START = (
    "A-Z_a-z\\u00c0-\\u00d6\\u00d8-\\u00f6\\u00f8-\\u02ff"
    "\\u0370-\\u037d\\u037f-\\u1fff\\u200c-\\u200d"
    "\\u2070-\\u218f\\u2c00-\\u2fef\\u3001-\\ud7ff"
    "\\uf900-\\ufdcf\\ufdf0-\\ufffd"
)
_NCNAME_CHAR = _NCNAME_START + "\\-.0-9\\u00b7\\u0300-\\u036f\\u203f-\\u2040"
_NCNAME = re.compile(f"^[{_NCNAME_START}][{_NCNAME_CHAR}]*$")
_PBS = f"{{{PBS_V3_NAMESPACE}}}"
# The same finite PBS source-element review vocabulary used by the URI review
# packet; unknown namespaces and tags abstain instead of entering the export.
_ALLOWED_PBS_ELEMENTS = frozenset({
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


def _qname(value: str) -> str | None:
    if not value.startswith(_PBS):
        return None
    local = value[len(_PBS) :]
    if local not in _ALLOWED_PBS_ELEMENTS:
        return None
    return f"pbs:{local}"


def _address_digest(address: str) -> str:
    encoded = address.encode("utf-8")
    if len(encoded) > MAX_OCCURRENCE_ADDRESS_BYTES:
        raise ValueError("PBS XLink occurrence address exceeds byte limit")
    return hashlib.sha256(encoded).hexdigest()


# Each parser pass retains only current ancestry and detaches completed nodes.
def _iter_member_starts(
    member: bytes,
) -> Iterator[tuple[str, str, bool, dict[str, str]]]:
    if len(member) > MAX_MEMBER_BYTES:
        raise ValueError("PBS XLink member exceeds byte limit")
    policy = ParserPolicy(
        max_bytes=MAX_MEMBER_BYTES,
        max_xml_depth=256,
        max_xml_elements=MAX_ELEMENTS,
        max_xml_text_bytes=MAX_MEMBER_BYTES,
    )
    paths: list[str] = []
    inherited_base: list[bool] = []
    child_counts: list[Counter[str]] = []
    elements = 0
    for event, element, parent in iter_xml_events(member, policy=policy):
        if event == "start":
            elements += 1
            if elements > MAX_ELEMENTS:
                raise ValueError("PBS XLink element limit exceeded")
            tag = str(element.tag)
            if parent is None:
                path = f"/{tag}[1]"
                base = XML_BASE in element.attrib
            else:
                counts = child_counts[-1]
                counts[tag] += 1
                path = f"{paths[-1]}/{tag}[{counts[tag]}]"
                base = inherited_base[-1] or XML_BASE in element.attrib
            paths.append(path)
            inherited_base.append(base)
            child_counts.append(Counter())
            yield tag, path, base, dict(element.attrib)
        else:
            if not paths:
                raise ValueError("PBS XLink parser event stack is inconsistent")
            paths.pop()
            inherited_base.pop()
            child_counts.pop()
            element.clear()
            if parent is not None:
                parent.remove(element)


def _build_identifier_index(
    member: bytes, connection: sqlite3.Connection
) -> tuple[int, int]:
    identifier_count = element_count = 0
    with connection:
        for tag, path, _base, attributes in _iter_member_starts(member):
            element_count += 1
            value = attributes.get(XML_ID)
            if value is None:
                continue
            if len(value.encode("utf-8")) > MAX_LITERAL_BYTES:
                raise ValueError("PBS XLink identifier byte limit exceeded")
            identifier_count += 1
            if identifier_count > MAX_IDENTIFIERS:
                raise ValueError("PBS XLink identifier limit exceeded")
            connection.execute(
                "INSERT INTO identifiers VALUES (?, 1, ?, ?) "
                "ON CONFLICT(literal) DO UPDATE SET "
                "occurrence_count = occurrence_count + 1",
                (value, _address_digest(path), _qname(tag)),
            )
            if identifier_count % 4096 == 0:
                page_count = connection.execute("PRAGMA page_count").fetchone()[
                    0
                ]
                page_size = connection.execute("PRAGMA page_size").fetchone()[0]
                if page_count * page_size > MAX_INDEX_BYTES:
                    raise ValueError(
                        "PBS XLink identifier index byte limit exceeded"
                    )
    return element_count, identifier_count


def _resolve_and_write(  # ruff: ignore[too-many-branches]
    member: bytes, connection: sqlite3.Connection, output: BinaryIO
) -> tuple[Counter[str], int, int, int, str, int]:
    outcomes: Counter[str] = Counter()
    references = edges = byte_count = elements = 0
    digest = hashlib.sha256()
    for tag, source_path, has_base, attributes in _iter_member_starts(member):
        elements += 1
        href = attributes.get(XLINK_HREF)
        if href is None:
            continue
        references += 1
        if references > MAX_REFERENCES:
            raise ValueError("PBS XLink reference limit exceeded")
        if len(href.encode("utf-8")) > MAX_LITERAL_BYTES:
            raise ValueError("PBS XLink reference byte limit exceeded")
        source_qname = _qname(tag)
        reason: str | None = None
        if has_base:
            reason = "xml_base_in_ancestry"
        elif "%" in href:
            reason = "percent_encoded_fragment"
        elif not href.startswith("#") or href.count("#") != 1:
            reason = "malformed_or_nonlocal_href"
        else:
            fragment = href[1:]
            if not fragment or not _NCNAME.fullmatch(fragment):
                reason = "invalid_ncname_fragment"
            else:
                found = connection.execute(
                    "SELECT occurrence_count, occurrence_sha256, element_qname "
                    "FROM identifiers WHERE literal = ?",
                    (fragment,),
                ).fetchone()
                if found is None:
                    reason = "missing_same_member_xml_id"
                elif found[0] != 1:
                    reason = "duplicate_same_member_xml_id"
                elif source_qname is None or found[2] is None:
                    reason = "element_qname_not_allowlisted"
                else:
                    if edges >= MAX_OUTPUT_EDGES:
                        raise ValueError("PBS XLink output edge limit exceeded")
                    edge = {
                        "kind": "source_declared_xlink_link",
                        "source_occurrence_sha256": _address_digest(
                            source_path
                        ),
                        "source_element_qname": source_qname,
                        "target_occurrence_sha256": found[1],
                        "target_element_qname": found[2],
                    }
                    line = (
                        orjson.dumps(edge, option=orjson.OPT_SORT_KEYS) + b"\n"
                    )
                    if byte_count + len(line) > MAX_OUTPUT_BYTES:
                        raise ValueError("PBS XLink output byte limit exceeded")
                    written = output.write(line)
                    if written != len(line):
                        raise OSError(
                            "PBS XLink candidate write was incomplete"
                        )
                    digest.update(line)
                    byte_count += written
                    edges += 1
                    outcomes["candidate_unique_same_member_id"] += 1
                    continue
        outcomes[reason or "candidate_unique_same_member_id"] += 1
    return outcomes, references, edges, byte_count, digest.hexdigest(), elements


def export_pbs_xlink_reference_candidates(
    archive: bytes,
    member: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    output_path: Path,
) -> dict[str, Any]:
    """Resolve only literal local fragments against unique same-member IDs.

    The report binds candidates to the supplied source receipt and member
    binding. No source values, IDs, URI literals, external links, or semantic
    assertions are emitted. JSONL is streamed to a temporary sibling file and
    atomically renamed only after parsing, resolution, limits, digesting and
    flush succeed. A failure preserves any previous destination and removes
    the incomplete temporary artifact.
    """
    parent = SourceReceipt.model_validate(parent.model_dump())
    binding = validate_pbs_xml_member_binding(binding, archive, member, parent)
    output_path = Path(output_path)
    temporary_path: Path | None = None
    try:
        # The index path depends on the temporary directory lifetime.
        with TemporaryDirectory(  # ruff: ignore[multiple-with-statements]
            prefix="pbs-xlink-candidate-index-"
        ) as work:
            with closing(sqlite3.connect(Path(work) / "ids.sqlite")) as index:
                index.execute(f"PRAGMA page_size = {4096}")
                if MAX_INDEX_BYTES < MIN_INDEX_BYTES:
                    raise ValueError(
                        "PBS XLink identifier index byte limit is below "
                        "the minimum supported schema size"
                    )
                index.execute(
                    f"PRAGMA max_page_count = {MAX_INDEX_BYTES // 4096}"
                )
                index.execute("PRAGMA temp_store = FILE")
                index.execute(
                    "CREATE TABLE identifiers ("
                    "literal TEXT PRIMARY KEY, occurrence_count INTEGER NOT NULL, "
                    "occurrence_sha256 TEXT NOT NULL, element_qname TEXT)"
                )
                first_elements, identifier_count = _build_identifier_index(
                    member, index
                )
                with NamedTemporaryFile(
                    mode="wb",
                    dir=output_path.parent,
                    prefix=f".{output_path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as output:
                    temporary_path = Path(output.name)
                    (
                        outcomes,
                        reference_count,
                        edge_count,
                        output_bytes,
                        output_sha256,
                        second_elements,
                    ) = _resolve_and_write(
                        member, index, cast("BinaryIO", output)
                    )
                    if second_elements != first_elements:
                        raise ValueError("PBS XLink pass element counts differ")
                    output.flush()
                    os.fsync(output.fileno())
        temporary_path.replace(output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    abstentions = {
        reason: count
        for reason, count in sorted(outcomes.items())
        if reason != "candidate_unique_same_member_id"
    }
    return {
        "schema_id": "global-medicines-atlas.pbs-xlink-reference-candidates",
        "schema_version": 1,
        "qualification": "candidate",
        "semantic_relationships_qualified": False,
        "occurrence_hash_disclosure": "deterministic_pseudonymous_correlatable",
        "source_revision": binding.source.catalog_version,
        "source_receipt_sha256": binding.parent_receipt_sha256,
        "archive_sha256": binding.archive_payload.sha256,
        "member_path": binding.member_path,
        "member_sha256": binding.member_payload.sha256,
        "xml_elements": first_elements,
        "xml_id_occurrences": identifier_count,
        "candidate_edge_count": edge_count,
        "reference_count": reference_count,
        "resolution_counts": dict(sorted(outcomes.items())),
        "abstention_counts": abstentions,
        "artifact_finalized": True,
        "artifact_sha256": output_sha256,
        "artifact_byte_count": output_bytes,
        "external_links_emitted": 0,
    }
