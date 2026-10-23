"""Value-free structural context for source-local PBS reference candidates.

This pass records bounded occurrence addresses and structural descriptors. It
does not resolve URIs, emit literal values, or qualify semantic relationships.
"""

# ruff: file-ignore[too-many-nested-blocks] -- bounded parser and grouping pass

from __future__ import annotations

import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .adapters.au_pbs import PBS_V3_NAMESPACE, PBS_XML_POLICY
from .parser_safety import iter_xml_events

XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
RDF_ABOUT = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about"
RDF_RESOURCE = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
MAX_INDEX_ROWS = 8_000_000
MAX_INDEX_BYTES = 4 * 1024**3
MAX_REFERENCE_OCCURRENCES = 3_000_000
MAX_EXAMPLES_PER_STRATUM = 5
ROOT_CHILD_STACK_DEPTH = 2


def _pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _literal_class(kind: str, value: str) -> str:
    """Classify spelling shape only; never return or normalize the value."""
    if not value:
        return "empty"
    if kind == "xlink_href" and value.startswith("#"):
        return "fragment"
    if "://" in value:
        return "absolute_looking"
    if value.startswith("/"):
        return "root_relative_looking"
    if ":" in value:
        return "scheme_looking"
    return "relative_or_other"


def _screen(member: bytes) -> dict[str, Any]:  # ruff: ignore[too-many-branches,too-many-statements,too-many-locals] -- bounded source parser
    with (
        TemporaryDirectory(prefix="pbs-reference-context-") as temporary,
        closing(sqlite3.connect(Path(temporary) / "context.sqlite")) as db,
    ):
        db.execute("PRAGMA temp_store=FILE")
        db.execute("PRAGMA page_size=4096")
        db.execute(f"PRAGMA max_page_count={MAX_INDEX_BYTES // 4096}")
        db.execute("PRAGMA cache_size=-8192")
        db.execute(
            "CREATE TABLE defs (space TEXT, literal TEXT, address TEXT, target_qname TEXT)"
        )
        db.execute(
            "CREATE TABLE refs (kind TEXT, space TEXT, literal TEXT, address TEXT, predicate_qname TEXT, predicate_address TEXT, subject_qname TEXT, subject_address TEXT, base_depth INTEGER, literal_class TEXT)"
        )
        stack: list[dict[str, Any]] = []
        child_counts: list[Counter[str]] = []
        root_seen = False
        refs_seen = 0
        definitions_seen = 0
        with db:
            for event, element, parent in iter_xml_events(
                member, policy=PBS_XML_POLICY
            ):
                if event == "start":
                    if parent is None:
                        if element.tag not in {
                            f"{{{PBS_V3_NAMESPACE}}}root",
                            f"{{{PBS_V3_NAMESPACE}}}schedule",
                        }:
                            raise ValueError(
                                "PBS reference context root does not match source contract"
                            )
                        address = f"/{_pointer(element.tag)}/1"
                        root_seen = True
                    else:
                        counts = child_counts[-1]
                        counts[element.tag] += 1
                        address = f"{stack[-1]['address']}/{_pointer(element.tag)}/{counts[element.tag]}"
                    inherited_base = stack[-1]["base_depth"] if stack else 0
                    base_depth = inherited_base + (
                        1 if XML_BASE in element.attrib else 0
                    )
                    subject_frame = next(
                        (
                            frame
                            for frame in reversed(stack)
                            if frame["subject_address"]
                        ),
                        None,
                    )
                    local_subject = (
                        RDF_ABOUT
                        if RDF_ABOUT in element.attrib
                        else XML_ID
                        if XML_ID in element.attrib
                        else None
                    )
                    current = {
                        "address": address,
                        "base_depth": base_depth,
                        "element": element,
                        "subject_address": address
                        if local_subject
                        else (
                            subject_frame["subject_address"]
                            if subject_frame
                            else None
                        ),
                        "subject_qname": element.tag
                        if local_subject
                        else (
                            subject_frame["subject_qname"]
                            if subject_frame
                            else None
                        ),
                        "tag": element.tag,
                    }
                    stack.append(current)
                    child_counts.append(Counter())
                    for attr, literal in element.attrib.items():
                        if attr == XML_ID:
                            definitions_seen += 1
                            if definitions_seen + refs_seen > MAX_INDEX_ROWS:
                                raise ValueError(
                                    "PBS reference context index row bound exceeded"
                                )
                            db.execute(
                                "INSERT INTO defs VALUES (?, ?, ?, ?)",
                                ("xml_id", literal, address, element.tag),
                            )
                        elif attr == RDF_ABOUT:
                            definitions_seen += 1
                            if definitions_seen + refs_seen > MAX_INDEX_ROWS:
                                raise ValueError(
                                    "PBS reference context index row bound exceeded"
                                )
                            db.execute(
                                "INSERT INTO defs VALUES (?, ?, ?, ?)",
                                ("rdf_literal", literal, address, element.tag),
                            )
                        elif attr in {RDF_RESOURCE, XLINK_HREF}:
                            kind = (
                                "rdf_resource"
                                if attr == RDF_RESOURCE
                                else "xlink_href"
                            )
                            space: str | None = (
                                "rdf_literal" if attr == RDF_RESOURCE else None
                            )
                            target_literal = literal
                            if (
                                attr == XLINK_HREF
                                and literal.startswith("#")
                                and len(literal) > 1
                            ):
                                space, target_literal = "xml_id", literal[1:]
                            refs_seen += 1
                            if (
                                refs_seen > MAX_REFERENCE_OCCURRENCES
                                or refs_seen + definitions_seen > MAX_INDEX_ROWS
                            ):
                                raise ValueError(
                                    "PBS reference context occurrence bound exceeded"
                                )
                            db.execute(
                                "INSERT INTO refs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (
                                    kind,
                                    space,
                                    target_literal,
                                    f"{address}/attributes/{_pointer(attr)}",
                                    element.tag,
                                    address,
                                    current["subject_qname"],
                                    current["subject_address"],
                                    base_depth,
                                    _literal_class(kind, literal),
                                ),
                            )
                else:
                    if not stack:
                        raise ValueError(
                            "PBS reference context element stack is inconsistent"
                        )
                    if len(stack) == ROOT_CHILD_STACK_DEPTH:
                        root = stack[0]["element"]
                        root.remove(element)
                        element.clear()
                    child_counts.pop()
                    stack.pop()
        if not root_seen or stack:
            raise ValueError("PBS reference context document is incomplete")
        db.execute("CREATE INDEX definition_literal ON defs(space, literal)")

        summaries: dict[tuple[str, ...], dict[str, Any]] = {}
        cursor = db.execute("""
            SELECT r.kind, r.literal, r.space, r.address, r.predicate_qname,
                   r.predicate_address, coalesce(r.subject_qname, 'none'),
                   r.subject_address, r.base_depth,
                   r.literal_class, count(d.address)
            FROM refs r LEFT JOIN defs d ON r.space = d.space AND r.literal = d.literal
            GROUP BY r.rowid
            ORDER BY r.kind, r.address
        """)
        for (
            kind,
            literal,
            space,
            address,
            predicate_qname,
            predicate_address,
            subject,
            subject_address,
            base_depth,
            form,
            target_count,
        ) in cursor:
            status = (
                "empty_literal"
                if not literal
                else "unsupported_reference_form"
                if space is None
                else "no_exact_literal"
                if target_count == 0
                else "unique_exact_literal"
                if target_count == 1
                else "ambiguous_exact_literal"
            )
            base = "no_xml_base" if base_depth == 0 else "xml_base_present"
            key = (kind, status, predicate_qname, subject, base, form)
            row = summaries.setdefault(
                key,
                {
                    "kind": kind,
                    "match_status": status,
                    "predicate_element_qname": predicate_qname,
                    "nearest_subject_element_qname": subject,
                    "xml_base_context": base,
                    "literal_shape": form,
                    "occurrences": 0,
                    "unique_target_occurrences": 0,
                    "ambiguous_target_occurrences": 0,
                    "examples": [],
                },
            )
            row["occurrences"] += 1
            row["unique_target_occurrences"] += target_count == 1
            row["ambiguous_target_occurrences"] += target_count > 1
            if len(row["examples"]) < MAX_EXAMPLES_PER_STRATUM:
                targets = db.execute(
                    "SELECT address, target_qname FROM defs WHERE space = ? AND literal = ? ORDER BY address LIMIT 10",
                    (space, literal),
                ).fetchall()
                row["examples"].append({
                    "reference_occurrence": address,
                    "predicate_element": {
                        "occurrence": predicate_address,
                        "qname": predicate_qname,
                    },
                    "nearest_subject_element": (
                        {
                            "occurrence": subject_address,
                            "qname": subject,
                        }
                        if subject_address is not None
                        else None
                    ),
                    "target_multiplicity": target_count,
                    "targets": [
                        {"occurrence": target_address, "qname": target_qname}
                        for target_address, target_qname in targets
                    ],
                })
        strata = [summaries[key] for key in sorted(summaries)]
        return {
            "reference_occurrences": refs_seen,
            "strata": strata,
            "uri_resolution_performed": False,
            "literal_values_emitted": False,
            "raw_source_emitted": False,
            "semantic_relationships_qualified": False,
            "external_targets_fetched": 0,
        }


def screen_reference_context(member: bytes) -> dict[str, Any]:
    """Return aggregate contextual strata over one already-bound PBS XML member."""
    result = _screen(member)
    return {
        "schema_id": "global-medicines-atlas.pbs-reference-context-screen",
        "schema_version": 1,
        **result,
    }
