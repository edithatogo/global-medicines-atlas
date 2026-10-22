"""Bounded source-local lexical reference screening over original PBS bytes.

Exact literal equality is a diagnostic, not a semantic identity assertion.
RDF resource literals are compared only with RDF about literals. Explicit
XLink fragments are compared only with source XML ID literals. No URI
normalization, base resolution, vocabulary lookup or external request occurs.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .pbs_member_identity import (
    PbsXmlMemberBinding,
    validate_pbs_xml_member_binding,
)
from .pbs_xml_slots import iter_pbs_xml_slots
from .receipts import SourceReceipt

XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
RDF_ABOUT = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about"
RDF_RESOURCE = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
MAX_LITERAL_BYTES = 4096
MAX_INDEX_ROWS = 2_000_000
MAX_NATIVE_FIELDS = 20_000_000
MAX_INDEX_BYTES = 1024**3
PAGE_BYTES = 4096


def _attribute(path: str) -> str | None:
    if "/attributes/" not in path:
        return None
    return (
        path.rsplit("/attributes/", 1)[1].replace("~1", "/").replace("~0", "~")
    )


def _screen(connection: sqlite3.Connection, member: bytes) -> dict[str, Any]:
    connection.execute(
        "CREATE TABLE definitions (ordinal INTEGER PRIMARY KEY, space TEXT NOT NULL, literal TEXT, occurrence TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE refs (ordinal INTEGER PRIMARY KEY, kind TEXT NOT NULL, space TEXT, original TEXT, literal TEXT)"
    )
    digest = sha256()
    fields = definitions = references = 0
    with connection:
        for ordinal, slot in enumerate(iter_pbs_xml_slots(member)):
            fields += 1
            if fields > MAX_NATIVE_FIELDS:
                raise ValueError(
                    "PBS reference screen native field bound exceeded"
                )
            attribute = _attribute(slot.path)
            if attribute not in {XML_ID, RDF_ABOUT, RDF_RESOURCE, XLINK_HREF}:
                continue
            if (
                slot.value is not None
                and len(slot.value.encode()) > MAX_LITERAL_BYTES
            ):
                raise ValueError(
                    "PBS reference screen literal byte bound exceeded"
                )
            if definitions + references >= MAX_INDEX_ROWS:
                raise ValueError(
                    "PBS reference screen index row bound exceeded"
                )
            digest.update(
                (
                    json.dumps(
                        [ordinal, slot.path, slot.value],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode()
            )
            if attribute in {XML_ID, RDF_ABOUT}:
                space = "xml_id" if attribute == XML_ID else "rdf_literal"
                connection.execute(
                    "INSERT INTO definitions VALUES (?, ?, ?, ?)",
                    (ordinal, space, slot.value, slot.record_id),
                )
                definitions += 1
            else:
                space = "rdf_literal" if attribute == RDF_RESOURCE else None
                literal = slot.value
                if (
                    attribute == XLINK_HREF
                    and literal is not None
                    and literal.startswith("#")
                    and len(literal) > 1
                ):
                    space, literal = "xml_id", literal[1:]
                connection.execute(
                    "INSERT INTO refs VALUES (?, ?, ?, ?, ?)",
                    (
                        ordinal,
                        "rdf_resource"
                        if attribute == RDF_RESOURCE
                        else "xlink_href",
                        space,
                        slot.value,
                        literal,
                    ),
                )
                references += 1
    connection.execute(
        "CREATE INDEX definition_literal ON definitions(space, literal)"
    )
    statuses = dict(
        connection.execute("""
        WITH matches AS (
          SELECT r.ordinal, r.original, r.space, count(d.ordinal) AS targets
          FROM refs AS r LEFT JOIN definitions AS d
          ON r.space = d.space AND r.literal = d.literal
          GROUP BY r.ordinal
        ), classified AS (
          SELECT CASE
            WHEN original IS NULL OR original = '' THEN 'empty_literal'
            WHEN space IS NULL THEN 'unsupported_reference_form'
            WHEN targets = 0 THEN 'no_exact_literal'
            WHEN targets = 1 THEN 'unique_exact_literal'
            ELSE 'ambiguous_exact_literal' END AS status
          FROM matches
        ) SELECT status, count(*) FROM classified GROUP BY status
    """).fetchall()
    )
    duplicate = connection.execute(
        "SELECT count(*) FROM (SELECT space, literal FROM definitions WHERE literal IS NOT NULL AND literal != '' GROUP BY space, literal HAVING count(*) > 1)"
    ).fetchone()
    if sum(statuses.values()) != references or duplicate is None:
        raise ValueError("PBS reference screen denominator differs")
    return {
        "native_fields": fields,
        "definition_fields": definitions,
        "reference_fields": references,
        "ambiguous_definition_literals": duplicate[0],
        "reference_status_counts": dict(sorted(statuses.items())),
        "reference_fields_sha256": digest.hexdigest(),
    }


def screen_native_references(
    archive: bytes,
    member: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
) -> dict[str, Any]:
    """Account every source slot and candidate reference without exporting literals.

    Complete parsing, disk-bounded indexing and denominator reconciliation are
    mandatory before a report is returned. Duplicate definitions remain distinct
    occurrences. SQLite uses binary literal comparison and a private temporary
    database that is removed on success, failure or interruption.
    """
    if MAX_INDEX_BYTES < PAGE_BYTES * 3:
        raise ValueError("PBS reference screen index byte bound is invalid")
    parent = SourceReceipt.model_validate(parent.model_dump())
    binding = validate_pbs_xml_member_binding(binding, archive, member, parent)
    with (
        TemporaryDirectory(prefix="pbs-native-reference-screen-") as temporary,
        closing(
            sqlite3.connect(Path(temporary) / "index.sqlite")
        ) as connection,
    ):
        connection.execute(f"PRAGMA page_size={PAGE_BYTES}")
        connection.execute(
            f"PRAGMA max_page_count={MAX_INDEX_BYTES // PAGE_BYTES}"
        )
        connection.execute("PRAGMA cache_size=-8192")
        connection.execute("PRAGMA temp_store=FILE")
        result = _screen(connection, member)
    return {
        "schema_id": "global-medicines-atlas.pbs-native-reference-screen",
        "schema_version": 1,
        "member_sha256": binding.member_payload.sha256,
        "member_binding_sha256": binding.digest(),
        "parent_receipt_sha256": parent.digest(),
        "archive_sha256": binding.archive_payload.sha256,
        **result,
        "comparison": "binary_source_local_literal_equality_only",
        "uri_normalization_or_base_resolution": False,
        "semantic_relationships_qualified": False,
        "domain_semantics_qualified": False,
        "native_values_emitted": False,
        "external_targets_fetched": 0,
        "new_sources": 0,
        "new_admissions": 0,
        "publications": 0,
    }
