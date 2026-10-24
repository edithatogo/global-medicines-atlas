"""Value-free structural context for source-local PBS reference candidates.

This pass records bounded occurrence addresses and structural descriptors. It
does not resolve URIs, emit literal values, or qualify semantic relationships.
"""

# ruff: file-ignore[too-many-nested-blocks] -- bounded parser and grouping pass

from __future__ import annotations

import json
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
MAX_LITERAL_BYTES = 4096
MAX_STRATA = 10_000
MAX_EXAMPLES_PER_STRATUM = 5
MAX_REPORT_EXAMPLES = 1_000
MAX_STRUCTURAL_QNAME_BYTES = 256
MAX_OCCURRENCE_ADDRESS_BYTES = 4096
# The hosted parent receipt is capped at 48,000 bytes. Reserve room for its
# source bindings and aggregate lexical screen by keeping this embedded object
# below 36,000 bytes.
MAX_REPORT_BYTES = 36_000
# Bound the two variable-size portions independently so the exact hosted
# receipt remains serializable as strata and occurrence examples grow.
MAX_REPORT_STRATA_BYTES = 31_000
MAX_REPORT_EXAMPLE_BYTES = 3_500
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
            "CREATE TABLE defs (space TEXT, literal TEXT, address TEXT, target_qname TEXT, base_depth INTEGER)"
        )
        db.execute(
            "CREATE TABLE refs (kind TEXT, space TEXT, literal TEXT, address TEXT, predicate_qname TEXT, predicate_address TEXT, subject_qname TEXT, subject_address TEXT, identifier_qname TEXT, identifier_address TEXT, base_depth INTEGER, literal_class TEXT)"
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
                    if len(element.tag.encode()) > MAX_STRUCTURAL_QNAME_BYTES:
                        raise ValueError(
                            "PBS reference context QName byte bound exceeded"
                        )
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
                            if frame["rdf_subject_address"]
                        ),
                        None,
                    )
                    identifier_frame = next(
                        (
                            frame
                            for frame in reversed(stack)
                            if frame["identifier_address"]
                        ),
                        None,
                    )
                    current = {
                        "address": address,
                        "base_depth": base_depth,
                        "element": element,
                        "rdf_subject_address": address
                        if RDF_ABOUT in element.attrib
                        else (
                            subject_frame["rdf_subject_address"]
                            if subject_frame
                            else None
                        ),
                        "rdf_subject_qname": element.tag
                        if RDF_ABOUT in element.attrib
                        else (
                            subject_frame["rdf_subject_qname"]
                            if subject_frame
                            else None
                        ),
                        "identifier_address": address
                        if XML_ID in element.attrib
                        else (
                            identifier_frame["identifier_address"]
                            if identifier_frame
                            else None
                        ),
                        "identifier_qname": element.tag
                        if XML_ID in element.attrib
                        else (
                            identifier_frame["identifier_qname"]
                            if identifier_frame
                            else None
                        ),
                        "tag": element.tag,
                    }
                    stack.append(current)
                    child_counts.append(Counter())
                    for attr, literal in element.attrib.items():
                        if attr == XML_ID:
                            if len(literal.encode()) > MAX_LITERAL_BYTES:
                                raise ValueError(
                                    "PBS reference context literal byte bound exceeded"
                                )
                            definitions_seen += 1
                            if definitions_seen + refs_seen > MAX_INDEX_ROWS:
                                raise ValueError(
                                    "PBS reference context index row bound exceeded"
                                )
                            db.execute(
                                "INSERT INTO defs VALUES (?, ?, ?, ?, ?)",
                                (
                                    "xml_id",
                                    literal,
                                    address,
                                    element.tag,
                                    base_depth,
                                ),
                            )
                        elif attr == RDF_ABOUT:
                            if len(literal.encode()) > MAX_LITERAL_BYTES:
                                raise ValueError(
                                    "PBS reference context literal byte bound exceeded"
                                )
                            definitions_seen += 1
                            if definitions_seen + refs_seen > MAX_INDEX_ROWS:
                                raise ValueError(
                                    "PBS reference context index row bound exceeded"
                                )
                            db.execute(
                                "INSERT INTO defs VALUES (?, ?, ?, ?, ?)",
                                (
                                    "rdf_literal",
                                    literal,
                                    address,
                                    element.tag,
                                    base_depth,
                                ),
                            )
                        elif attr in {RDF_RESOURCE, XLINK_HREF}:
                            if len(literal.encode()) > MAX_LITERAL_BYTES:
                                raise ValueError(
                                    "PBS reference context literal byte bound exceeded"
                                )
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
                                "INSERT INTO refs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                (
                                    kind,
                                    space,
                                    target_literal,
                                    f"{address}/attributes/{_pointer(attr)}",
                                    element.tag,
                                    address,
                                    current["rdf_subject_qname"],
                                    current["rdf_subject_address"],
                                    current["identifier_qname"],
                                    current["identifier_address"],
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
        report_example_count = 0
        report_example_bytes = 0
        omitted_examples = 0
        cursor = db.execute("""
            SELECT r.kind, r.literal, r.space, r.address, r.predicate_qname,
                   r.predicate_address, coalesce(r.subject_qname, 'none'),
                   r.subject_address, r.identifier_qname, r.identifier_address,
                   r.base_depth,
                   r.literal_class, count(d.address),
                   sum(CASE WHEN d.base_depth > 0 THEN 1 ELSE 0 END)
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
            identifier_qname,
            identifier_address,
            base_depth,
            form,
            target_count,
            targets_with_base,
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
            key = (
                kind,
                status,
                predicate_qname,
                subject,
                identifier_qname or "none",
                base,
                form,
            )
            if key not in summaries and len(summaries) >= MAX_STRATA:
                raise ValueError("PBS reference context stratum bound exceeded")
            row = summaries.setdefault(
                key,
                {
                    "kind": kind,
                    "match_status": status,
                    "predicate_element_qname": predicate_qname,
                    "nearest_subject_element_qname": subject,
                    "nearest_identifier_element_qname": identifier_qname
                    or "none",
                    "xml_base_context": base,
                    "literal_shape": form,
                    "occurrences": 0,
                    "unique_target_occurrences": 0,
                    "ambiguous_target_occurrences": 0,
                    "no_xml_base_exact_target_occurrences": 0,
                    "unique_exact_literal_no_xml_base_candidates": 0,
                    "examples_omitted": 0,
                    "examples": [],
                },
            )
            row["occurrences"] += 1
            row["unique_target_occurrences"] += status == "unique_exact_literal"
            row["ambiguous_target_occurrences"] += (
                status == "ambiguous_exact_literal"
            )
            if (
                base_depth == 0
                and status
                in {"unique_exact_literal", "ambiguous_exact_literal"}
                and targets_with_base == 0
            ):
                row["no_xml_base_exact_target_occurrences"] += 1
                if status == "unique_exact_literal":
                    row["unique_exact_literal_no_xml_base_candidates"] += 1
            if (
                len(row["examples"]) < MAX_EXAMPLES_PER_STRATUM
                and report_example_count < MAX_REPORT_EXAMPLES
            ):
                if len(address.encode()) > MAX_OCCURRENCE_ADDRESS_BYTES:
                    raise ValueError(
                        "PBS reference context occurrence address bound exceeded"
                    )
                targets = db.execute(
                    "SELECT address, target_qname, base_depth FROM defs WHERE space = ? AND literal = ? ORDER BY address LIMIT 10",
                    (space, literal),
                ).fetchall()
                if any(
                    len(target_address.encode()) > MAX_OCCURRENCE_ADDRESS_BYTES
                    for target_address, _, _ in targets
                ):
                    raise ValueError(
                        "PBS reference context target address bound exceeded"
                    )
                example = {
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
                    "nearest_identifier_element": (
                        {
                            "occurrence": identifier_address,
                            "qname": identifier_qname,
                        }
                        if identifier_address is not None
                        else None
                    ),
                    "target_multiplicity": target_count,
                    "targets": [
                        {
                            "occurrence": target_address,
                            "qname": target_qname,
                            "xml_base_context": (
                                "no_xml_base"
                                if target_base_depth == 0
                                else "xml_base_present"
                            ),
                        }
                        for target_address, target_qname, target_base_depth in targets
                    ],
                }
                example_bytes = len(
                    json.dumps(
                        example, ensure_ascii=False, separators=(",", ":")
                    ).encode()
                )
                if (
                    report_example_bytes + example_bytes
                    <= MAX_REPORT_EXAMPLE_BYTES
                ):
                    row["examples"].append(example)
                    report_example_count += 1
                    report_example_bytes += example_bytes
                else:
                    row["examples_omitted"] += 1
                    omitted_examples += 1
            else:
                row["examples_omitted"] += 1
                omitted_examples += 1
        strata = [summaries[key] for key in sorted(summaries)]
        strata_representation: list[dict[str, Any]] = [
            {**row, "examples": []} for row in strata
        ]
        strata_bytes = len(
            json.dumps(
                strata_representation,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        )
        if strata_bytes > MAX_REPORT_STRATA_BYTES:
            raise ValueError("PBS reference context strata byte bound exceeded")
        result = {
            "reference_occurrences": refs_seen,
            "strata_count": len(summaries),
            "examples_emitted": report_example_count,
            "examples_omitted": omitted_examples,
            "unique_exact_literal_no_xml_base_candidates": sum(
                row["unique_exact_literal_no_xml_base_candidates"]
                for row in summaries.values()
            ),
            "strata": strata,
            "uri_resolution_performed": False,
            "literal_values_emitted": False,
            "raw_source_emitted": False,
            "semantic_relationships_qualified": False,
            "external_targets_fetched": 0,
        }
        if (
            len(json.dumps(result, ensure_ascii=False).encode())
            > MAX_REPORT_BYTES
        ):
            raise ValueError("PBS reference context report byte bound exceeded")
        return result


def screen_reference_context(member: bytes) -> dict[str, Any]:
    """Return aggregate contextual strata over one already-bound PBS XML member."""
    result = _screen(member)
    return {
        "schema_id": "global-medicines-atlas.pbs-reference-context-screen",
        "schema_version": 1,
        **result,
    }
