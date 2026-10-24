"""Attach retained, value-free PBS context examples to URI review cases."""

from __future__ import annotations

import base64
import hashlib
import json
import zlib
from typing import Any, cast


class ContextEnrichmentError(ValueError):
    """An input is not bound to the exact retained PBS review evidence."""


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def enrich_uri_review_packet(  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements] -- exact evidence joins stay together as one auditable contract
    packet_envelope: dict[str, Any],
    screen_envelope: dict[str, Any],
    reconciliation_envelope: dict[str, Any],
    *,
    packet_file_sha256: str,
    screen_file_sha256: str,
) -> dict[str, Any]:
    """Join exact retained context by hashed structural occurrence paths.

    No source literal, URI, or raw source bytes are copied to the result.
    """
    try:  # ruff: ignore[too-many-statements-in-try-clause] -- decode and validate the single retained payload together
        packet = cast("dict[str, Any]", packet_envelope["report"])
        screen = cast("dict[str, Any]", screen_envelope["report"])
        reconciliation = cast(
            "dict[str, Any]", reconciliation_envelope["report"]
        )
        packet_source = cast("dict[str, Any]", packet["source"])
        compressed = cast(
            "dict[str, Any]", screen["qualification"]["reference_context"]
        )
        packed = base64.b64decode(compressed["payload"], validate=True)
        payload = zlib.decompress(packed)
        context = cast("dict[str, Any]", json.loads(payload))
        cases = cast("list[dict[str, Any]]", packet["cases"])
        uri_cases = cast("list[dict[str, Any]]", reconciliation["cases"])
    except (KeyError, TypeError, ValueError, zlib.error) as exc:
        raise ContextEnrichmentError(
            "retained context evidence is invalid"
        ) from exc

    if packet_source.get("screen_run_id") != screen.get("run_id"):
        raise ContextEnrichmentError("packet and context run identities differ")
    if packet_source.get("screen_receipt_sha256") != screen_file_sha256:
        raise ContextEnrichmentError(
            "packet and context receipt digests differ"
        )
    if reconciliation.get("source_packet_sha256") != packet_file_sha256:
        raise ContextEnrichmentError("URI reconciliation packet digest differs")
    payload_digest = hashlib.sha256(payload).hexdigest()
    if compressed.get("payload_sha256") != payload_digest:
        raise ContextEnrichmentError("compressed context digest differs")
    if (
        context.get("literal_values_emitted") is not False
        or context.get("raw_source_emitted") is not False
    ):
        raise ContextEnrichmentError("context value boundary is not preserved")

    examples: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    strata = cast("list[dict[str, Any]]", context.get("strata", []))
    for stratum in strata:
        context_examples = cast(
            "list[dict[str, Any]]", stratum.get("examples", [])
        )
        for example in context_examples:
            address = example.get("reference_occurrence")
            if not isinstance(address, str):
                raise ContextEnrichmentError("context occurrence is invalid")
            key = _digest(address)
            if key in examples:
                raise ContextEnrichmentError("context occurrence is duplicated")
            examples[key] = (stratum, example)
    uri_by_id = {row.get("case_id"): row for row in uri_cases}
    if len(uri_by_id) != len(uri_cases) or len(cases) != len(uri_cases):
        raise ContextEnrichmentError("case binding cardinality differs")

    enriched: list[dict[str, Any]] = []
    for case in cases:
        case_id = case.get("case_id")
        uri_case = uri_by_id.get(case_id)
        address = case.get("reference_occurrence")
        if not isinstance(address, str) or uri_case is None:
            raise ContextEnrichmentError("packet case binding is incomplete")
        occurrence_hash = _digest(address)
        if uri_case.get("reference_occurrence_sha256") != occurrence_hash:
            raise ContextEnrichmentError("URI occurrence binding differs")
        match = examples.get(occurrence_hash)
        if match is None:
            raise ContextEnrichmentError("context occurrence is absent")
        stratum, example = match
        targets: list[dict[str, Any]] = []
        context_targets = cast(
            "list[dict[str, Any]]", example.get("targets", [])
        )
        for target in context_targets:
            target_path = target.get("occurrence")
            target_qname = target.get("qname")
            if not isinstance(target_path, str) or not isinstance(
                target_qname, str
            ):
                raise ContextEnrichmentError(
                    "context target identity is invalid"
                )
            targets.append({
                "occurrence_sha256": _digest(target_path),
                "element_qname": target_qname,
                "xml_base_context": target.get("xml_base_context"),
            })
        uri_target_hash = uri_case.get("target_occurrence_sha256")
        if uri_target_hash is not None and uri_target_hash not in {
            target["occurrence_sha256"] for target in targets
        }:
            raise ContextEnrichmentError("context and URI target paths differ")
        predicate = example.get("predicate_element")
        subject = example.get("nearest_subject_element")
        identifier = example.get("nearest_identifier_element")

        def ancestry(item: Any) -> dict[str, str] | None:
            if item is None:
                return None
            if not isinstance(item, dict):
                raise ContextEnrichmentError("context ancestry is invalid")
            ancestry_item = cast("dict[str, Any]", item)
            address = ancestry_item.get("occurrence")
            if not isinstance(address, str):
                raise ContextEnrichmentError("context ancestry is invalid")
            return {
                "element_qname": str(ancestry_item.get("qname", "unknown")),
                "occurrence_sha256": _digest(address),
            }

        row = dict(uri_case)
        row["source_context"] = {
            "document_scope": stratum.get("document_scope"),
            "xml_base_context": stratum.get("xml_base_context"),
            "predicate_element": ancestry(predicate),
            "nearest_subject_element": ancestry(subject),
            "nearest_identifier_element": ancestry(identifier),
            "same_member_literal_candidate_target_count": len(targets),
            "same_member_literal_candidate_targets": targets,
            "uri_target_matches_context_candidate": (
                True if uri_target_hash is not None else None
            ),
        }
        enriched.append(row)

    report = dict(reconciliation)
    report["schema_id"] = (
        "global-medicines-atlas.pbs-uri-reference-review-context-packet"
    )
    report["schema_version"] = 1
    report["status"] = "value_free_context_enriched_semantics_unreviewed"
    report["context_screen_receipt_sha256"] = screen_file_sha256
    report["context_payload_sha256"] = payload_digest
    report["context_examples_bound"] = len(enriched)
    report["source_values_emitted"] = False
    report["cases"] = enriched
    encoded = json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        "report": report,
        "report_sha256": hashlib.sha256(encoded).hexdigest(),
    }
