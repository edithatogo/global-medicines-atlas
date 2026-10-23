"""Review exact-source PBS reference diagnostics without promoting links."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCREEN_RECEIPT = (
    "quality/qualifications/"
    "pbs-native-reference-screen-20261022-39730665004.json"
)
SCREEN_RECEIPT_SHA256 = (
    "a1adda4e946365b98bf3febc03b9ae51acdae6db1569c7fc6606f8892c7ae48e"
)
MEMBER_SHA256 = (
    "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
)
NATIVE_DIGEST = (
    "890c607f0e8c9de95c37770610fdc51fd241ea97210ef5ea61d7ad22fd228a25"
)
REVISION = "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7"
NATIVE_FIELDS = 18_208_758


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_digest(value: dict[str, Any]) -> str:
    return _digest(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    )


def review_reference_meanings(root: Path) -> dict[str, Any]:
    """Bind safe reference meanings and calibration limits to existing evidence."""
    raw = (root / SCREEN_RECEIPT).read_bytes()
    if _digest(raw) != SCREEN_RECEIPT_SHA256:
        raise ValueError("PBS reference screen receipt digest differs")
    envelope = json.loads(raw)
    report = envelope["report"]
    if (
        _canonical_digest(report) != envelope["report_sha256"]
        or report["qualification"]["member_sha256"] != MEMBER_SHA256
        or report["qualification"]["native_fields"] != NATIVE_FIELDS
        or report["qualification"]["reference_fields_sha256"]
        != "4a182e94b791fa0939792fe0159c8daca8ec2577c7f6f49a3de88378e5485793"
        or report["qualification"]["semantic_relationships_qualified"]
        is not False
    ):
        raise ValueError("PBS reference screen source contract differs")

    counts = report["qualification"]["reference_status_counts"]
    matched = counts["unique_exact_literal"]
    total = report["qualification"]["reference_fields"]
    unmatched = counts["no_exact_literal"]
    if matched + unmatched != total or counts.keys() != {
        "unique_exact_literal",
        "no_exact_literal",
    }:
        raise ValueError("PBS reference screen match denominator differs")

    return {
        "schema_id": "global-medicines-atlas.pbs-reference-meaning-review",
        "schema_version": 1,
        "profile_id": "pbs-april-2026-source-local-reference-review-v1",
        "status": "lexical_candidates_reviewed_semantic_links_unqualified",
        "source": {
            "dataset": report["dataset"],
            "revision": report["revision"],
            "member_sha256": MEMBER_SHA256,
            "native_digest": NATIVE_DIGEST,
            "native_fields": report["qualification"]["native_fields"],
            "screen_run_id": report["run_id"],
            "screen_workflow_commit": report["workflow_commit"],
            "screen_receipt_sha256": SCREEN_RECEIPT_SHA256,
            "reference_fields_sha256": report["qualification"][
                "reference_fields_sha256"
            ],
        },
        "reference_kinds": {
            "rdf_resource_to_rdf_about": {
                "meaning": "RDF resource literal with a same-spelling RDF subject candidate",
                "screen_rule": "binary literal equality in the RDF namespace only",
                "missing_context": [
                    "effective xml:base on both occurrences",
                    "RDF graph/document scope",
                    "target type and predicate meaning",
                ],
                "semantic_links_qualified": False,
            },
            "xlink_fragment_to_xml_id": {
                "meaning": "XLink fragment literal with a same-spelling XML ID candidate",
                "screen_rule": "leading # removed only for nonempty fragment syntax, then binary equality in the XML-ID namespace",
                "missing_context": [
                    "effective xml:base and URI resolution",
                    "link role and source/target element types",
                    "fragment target semantics for this link occurrence",
                ],
                "semantic_links_qualified": False,
            },
            "item_xml_id": {
                "meaning": "source-local XML identifier literal",
                "screen_rule": "identifier occurrence and duplicate count only",
                "limits": [
                    "not a global PBS item key",
                    "not a terminology identity or medicine-equivalence assertion",
                ],
                "semantic_links_qualified": False,
            },
        },
        "exact_source_screen": {
            "definitions": report["qualification"]["definition_fields"],
            "references": total,
            "unique_exact_literal_candidates": matched,
            "no_exact_literal": unmatched,
            "ambiguous_definition_literals": report["qualification"][
                "ambiguous_definition_literals"
            ],
            "candidate_coverage_percent": round(100 * matched / total, 4),
            "interpretation": "candidate yield, not precision, recall, semantic validity, or relation accuracy",
            "per_kind_match_counts_available": False,
        },
        "calibration": {
            "method": "deterministic synthetic positive, negative, ambiguity and base-context controls",
            "controls": [
                "same-space exact literal yields a lexical candidate",
                "duplicate target literals are ambiguous and cannot produce a unique candidate",
                "missing, empty, case-different, namespace-different and unsupported forms do not match",
                "identical relative RDF literals under different xml:base contexts still yield a lexical candidate and must abstain from semantic promotion",
            ],
            "source_semantic_precision": "not estimable from aggregate-only source receipt",
            "promotion_rule": "abstain; no literal-only candidate is emitted as a semantic edge",
        },
        "scope": {
            "source_values_emitted": False,
            "new_sources": 0,
            "new_admissions": 0,
            "consumer_canaries": 0,
            "publications": 0,
            "semantic_relationships_qualified": False,
            "rights_conclusion_changed": False,
        },
    }
