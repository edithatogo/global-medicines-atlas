"""Adjudicate a pinned PBS URI sample for structural match behavior only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

RECONCILIATION_FILENAME = (
    "pbs-native-reference-uri-review-reconciliation-20261025-40120162365.json"
)
RECONCILIATION_SHA256 = (
    "3698d217957c4d3263fce010d8ed6441c2050866052e1308fa352c6cd22772bb"
)
RECONCILIATION_REPORT_SHA256 = (
    "31e22bbda75bb7da755af0d09ed29c93477a9da08a5c50ed499dc6bc23dcd4fa"
)
PACKET_SHA256 = (
    "c38840116e821dffe5b06e5df14b1d7140f9e4446fbf8c14ea009a9e8b732829"
)
PACKET_REPORT_SHA256 = (
    "885960352dcee9e70f12ac3aa843d5129b75a2c44b16263835ff5bc7b57a5c6b"
)
URI_RECEIPT_SHA256 = (
    "4a296004773c57d7c0a6d73aacc6fd67b052fc3e1900a96badb0948193a7b411"
)
URI_REPORT_SHA256 = (
    "475655fd08abf4681908452ec9e76c6654904d697d10d702c6283c2490afde59"
)
URI_RUN_ID = "40120162365"
URI_WORKFLOW_COMMIT = "7084ee19081b6c5ce1ce5e2b6941125a446e8ee0"
SOURCE_MEMBER_SHA256 = (
    "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
)
SOURCE_REVISION = "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7"
CASE_COUNT = 46
DIGEST_LENGTH = 64
UNIQUE_OUTCOMES = {
    "same_member_unique_id": 17,
    "absolute_uri_unique_candidate": 18,
}
NEGATIVE_CONTROL_COUNT = 11


class StructuralReviewError(ValueError):
    """Fixed, value-free validation failure."""


def _digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == DIGEST_LENGTH
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical_digest(value: Any) -> str:
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise StructuralReviewError(
            "input report is not canonical JSON"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _load_reconciliation(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        envelope = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StructuralReviewError(
            "pinned reconciliation cannot be read"
        ) from exc
    if hashlib.sha256(raw).hexdigest() != RECONCILIATION_SHA256:
        raise StructuralReviewError("pinned reconciliation bytes differ")
    if not isinstance(envelope, dict):
        raise StructuralReviewError("pinned reconciliation shape differs")
    envelope_dict = cast("dict[str, Any]", envelope)
    if not isinstance(envelope_dict.get("report"), dict):
        raise StructuralReviewError("pinned reconciliation shape differs")
    report = cast("dict[str, Any]", envelope_dict["report"])
    if envelope_dict.get("report_sha256") != RECONCILIATION_REPORT_SHA256:
        raise StructuralReviewError(
            "pinned reconciliation report digest differs"
        )
    if _canonical_digest(report) != RECONCILIATION_REPORT_SHA256:
        raise StructuralReviewError("reconciliation report digest is invalid")
    expected = {
        "schema_id": "global-medicines-atlas.pbs-uri-reference-review-packet",
        "schema_version": 1,
        "status": "structural_uri_diagnostics_unreviewed_semantics_unqualified",
        "dataset": "edithatogo/australian-pbs-source-archive",
        "member_path": "sch-2026-04-01-r1.xml",
        "member_size_bytes": 313_437_585,
        "source_packet_sha256": PACKET_SHA256,
        "source_packet_report_sha256": PACKET_REPORT_SHA256,
        "uri_receipt_sha256": URI_RECEIPT_SHA256,
        "uri_receipt_report_sha256": URI_REPORT_SHA256,
        "uri_run_id": URI_RUN_ID,
        "uri_workflow_commit": URI_WORKFLOW_COMMIT,
        "revision": SOURCE_REVISION,
        "member_sha256": SOURCE_MEMBER_SHA256,
        "case_count": CASE_COUNT,
        "semantic_relationships_qualified": False,
        "source_values_emitted": False,
        "edges_emitted": False,
        "precision_claimed": False,
        "recall_claimed": False,
    }
    if any(report.get(key) != value for key, value in expected.items()):
        raise StructuralReviewError("source and receipt binding differs")
    return report


def review_structural_match_behavior(root: Path) -> dict[str, Any]:
    """Return bounded, value-free structural review for exactly 46 cases."""
    report = _load_reconciliation(
        root / "quality/qualifications" / RECONCILIATION_FILENAME
    )
    cases_value = report.get("cases")
    if not isinstance(cases_value, list):
        raise StructuralReviewError("pinned case inventory differs")
    cases = cast("list[Any]", cases_value)
    if len(cases) != CASE_COUNT:
        raise StructuralReviewError("pinned case inventory differs")

    reviewed: list[dict[str, Any]] = []
    counts = {
        "same_member_unique_id": 0,
        "absolute_uri_unique_candidate": 0,
        "no_member_definition": 0,
    }
    seen: set[str] = set()
    for value in cases:
        if not isinstance(value, dict):
            raise StructuralReviewError("pinned case shape differs")
        case = cast("dict[str, Any]", value)
        case_id = case.get("case_id")
        occurrence_hash = case.get("reference_occurrence_sha256")
        outcome = case.get("uri_resolution")
        multiplicity = case.get("target_multiplicity")
        identity_invalid = (
            not _digest(case_id)
            or case_id in seen
            or not _digest(occurrence_hash)
        )
        limits_invalid = (
            case.get("adjudication") != "unreviewed"
            or case.get("semantic_relationship_qualified") is not False
            or case.get("edges_emitted") is not False
            or case.get("target_type_meaning") != "not_established"
            or case.get("reference_xml_base_context") != "no_xml_base"
        )
        if identity_invalid or limits_invalid:
            raise StructuralReviewError("pinned case identity or limits differ")
        seen.add(cast("str", case_id))

        if outcome in UNIQUE_OUTCOMES:
            if (
                multiplicity != 1
                or case.get("target_occurrence_sha256") is None
                or not _digest(case.get("target_occurrence_sha256"))
                or case.get("target_xml_base_context") != "no_xml_base"
            ):
                raise StructuralReviewError(
                    "unique-target case is not eligible"
                )
            counts[cast("str", outcome)] += 1
            reviewed.append({
                "case_id": case_id,
                "reference_occurrence_sha256": occurrence_hash,
                "target_occurrence_sha256": case["target_occurrence_sha256"],
                "structural_disposition": "unique_same_member_target",
                "relationship_label": "source_declared_reference_pointer",
                "candidate_edge_emitted": False,
            })
        elif outcome == "absolute_uri_no_member_definition":
            if (
                multiplicity != 0
                or case.get("target_occurrence_sha256") is not None
                or case.get("target_xml_base_context") is not None
            ):
                raise StructuralReviewError(
                    "negative control has target evidence"
                )
            counts["no_member_definition"] += 1
            reviewed.append({
                "case_id": case_id,
                "reference_occurrence_sha256": occurrence_hash,
                "target_occurrence_sha256": None,
                "structural_disposition": "unresolved_negative_control",
                "relationship_label": None,
                "candidate_edge_emitted": False,
            })
        else:
            raise StructuralReviewError(
                "case outcome is outside pinned review scope"
            )

    if counts != {
        **UNIQUE_OUTCOMES,
        "no_member_definition": NEGATIVE_CONTROL_COUNT,
    }:
        raise StructuralReviewError("pinned outcome distribution differs")

    return {
        "schema_id": "global-medicines-atlas.pbs-uri-structural-review",
        "schema_version": 1,
        "status": "bounded_structural_match_behavior_reviewed",
        "source_binding": {
            "dataset": report["dataset"],
            "revision": SOURCE_REVISION,
            "member_sha256": SOURCE_MEMBER_SHA256,
            "packet_sha256": PACKET_SHA256,
            "uri_receipt_sha256": URI_RECEIPT_SHA256,
            "uri_receipt_report_sha256": URI_REPORT_SHA256,
            "uri_run_id": URI_RUN_ID,
            "uri_workflow_commit": URI_WORKFLOW_COMMIT,
            "reconciliation_file_sha256": RECONCILIATION_SHA256,
            "reconciliation_report_sha256": RECONCILIATION_REPORT_SHA256,
        },
        "case_count": CASE_COUNT,
        "outcome_counts": {
            "same_member_unique_id": counts["same_member_unique_id"],
            "absolute_uri_unique_candidate": counts[
                "absolute_uri_unique_candidate"
            ],
            "no_member_definition_negative_controls": counts[
                "no_member_definition"
            ],
        },
        "review_scope": "structural_match_behavior_calibration_only",
        "sampling_is_probability_based": False,
        "source_declared_reference_pointer_rule": {
            "accepted_structural_cases": 35,
            "eligible_when": [
                "exact_pinned_packet_receipt_run_and_source_binding",
                "unique_target_within_same_member",
                "target_multiplicity_equals_one",
                "reference_and_target_have_no_xml_base",
            ],
            "label_is_not_a_graph_predicate": True,
        },
        "limitations": {
            "source_or_target_domain_meaning_asserted": False,
            "clinical_meaning_asserted": False,
            "graph_subject_or_predicate_semantics_asserted": False,
            "precision_claimed": False,
            "recall_claimed": False,
            "generalized_to_corpus": False,
            "raw_literals_or_uri_values_emitted": False,
            "external_targets_fetched": 0,
            "new_sources_added": 0,
            "semantic_relationships_qualified": False,
            "edges_emitted": False,
        },
        "cases": reviewed,
    }
