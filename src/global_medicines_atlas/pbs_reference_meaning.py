"""Review exact-source PBS reference diagnostics without promoting links."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

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
DATASET = "edithatogo/australian-pbs-source-archive"
NATIVE_FIELDS = 18_208_758
REFERENCE_FIELDS_SHA256 = (
    "4a182e94b791fa0939792fe0159c8daca8ec2577c7f6f49a3de88378e5485793"
)
REFERENCE_KINDS = {"rdf_resource", "xlink_href"}
STATUSES = {
    "ambiguous_exact_literal",
    "empty_literal",
    "no_exact_literal",
    "unique_exact_literal",
    "unsupported_reference_form",
}
COMMIT_HEX_LENGTH = 40
SHA256_HEX_LENGTH = 64


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


def _read_receipt(
    root: Path, receipt_path: str | Path
) -> tuple[dict[str, Any], str]:
    path = Path(receipt_path)
    if not path.is_absolute():
        path = root / path
    raw = path.read_bytes()
    receipt_sha256 = _digest(raw)
    envelope = json.loads(raw)
    report = envelope["report"]
    if _canonical_digest(report) != envelope.get("report_sha256"):
        raise ValueError("PBS reference screen report digest differs")
    return envelope, receipt_sha256


def _validate_source(report: dict[str, Any]) -> dict[str, Any]:
    qualification = report["qualification"]
    contract = {
        "operation": report.get("operation"),
        "status": report.get("status"),
        "dataset": report.get("dataset"),
        "revision": report.get("revision"),
        "member_sha256": qualification.get("member_sha256"),
        "native_fields": qualification.get("native_fields"),
        "reference_fields_sha256": qualification.get("reference_fields_sha256"),
        "semantic_relationships_qualified": qualification.get(
            "semantic_relationships_qualified"
        ),
        "domain_semantics_qualified": qualification.get(
            "domain_semantics_qualified"
        ),
        "native_values_emitted": qualification.get("native_values_emitted"),
        "external_targets_fetched": qualification.get(
            "external_targets_fetched"
        ),
        "new_sources": qualification.get("new_sources"),
        "new_admissions": qualification.get("new_admissions"),
        "publications": qualification.get("publications"),
        "rights_conclusion_changed": report.get("rights_conclusion_changed"),
        "publication_performed": report.get("publication_performed"),
    }
    expected = {
        "operation": "pbs-native-reference-screen",
        "status": "passed",
        "dataset": DATASET,
        "revision": REVISION,
        "member_sha256": MEMBER_SHA256,
        "native_fields": NATIVE_FIELDS,
        "reference_fields_sha256": REFERENCE_FIELDS_SHA256,
        "semantic_relationships_qualified": False,
        "domain_semantics_qualified": False,
        "native_values_emitted": False,
        "external_targets_fetched": 0,
        "new_sources": 0,
        "new_admissions": 0,
        "publications": 0,
        "rights_conclusion_changed": False,
        "publication_performed": False,
    }
    if contract != expected:
        raise ValueError("PBS reference screen source contract differs")
    if (
        not isinstance(report.get("run_id"), str)
        or not report["run_id"].isdigit()
    ):
        raise ValueError("PBS reference screen run identity is invalid")
    workflow_commit = report.get("workflow_commit")
    if (
        not isinstance(workflow_commit, str)
        or re.fullmatch(r"[0-9a-f]{40}", workflow_commit) is None
    ):
        raise ValueError("PBS reference screen workflow commit is invalid")
    source_receipt_sha256 = report.get("source_receipt_file_sha256")
    if (
        not isinstance(source_receipt_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", source_receipt_sha256) is None
    ):
        raise ValueError("PBS source receipt digest is invalid")
    return qualification


def _validate_expected_run_identity(
    report: dict[str, Any], expected_exact_commit: str, expected_run_id: str
) -> None:
    """Bind a per-kind receipt to the caller's exact-main workflow run."""
    if re.fullmatch(r"[0-9a-f]{40}", expected_exact_commit) is None:
        raise ValueError("expected exact-main commit is invalid")
    if not expected_run_id.isdigit():
        raise ValueError("expected workflow run ID is invalid")
    if report.get("workflow_commit") != expected_exact_commit:
        raise ValueError("PBS reference screen workflow commit differs")
    if report.get("run_id") != expected_run_id:
        raise ValueError("PBS reference screen workflow run ID differs")


def _meaning_profile() -> dict[str, Any]:
    return {
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
    }


def _string_keyed_mapping(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    normalized: dict[str, object] = {}
    for key, item in cast("dict[object, object]", value).items():
        if not isinstance(key, str):
            return None
        normalized[key] = item
    return normalized


def _count_mapping(value: object, allowed: set[str]) -> dict[str, int] | None:
    mapping = _string_keyed_mapping(value)
    if mapping is None or not set(mapping) <= allowed:
        return None
    counts: dict[str, int] = {}
    for key, item in mapping.items():
        if isinstance(item, bool) or not isinstance(item, int) or item < 0:
            return None
        counts[key] = item
    return counts


def _validated_per_kind(
    qualification: dict[str, Any], counts: dict[str, int], references: int
) -> dict[str, Any] | None:
    per_kind = qualification.get("reference_kind_status_counts")
    if per_kind is None:
        return None
    per_kind_mapping = _string_keyed_mapping(per_kind)
    kind_totals = _count_mapping(
        qualification.get("reference_kind_counts"), REFERENCE_KINDS
    )
    if (
        per_kind_mapping is None
        or set(per_kind_mapping) != REFERENCE_KINDS
        or kind_totals is None
        or set(kind_totals) != REFERENCE_KINDS
    ):
        raise ValueError("PBS per-kind reference denominators are required")
    normalized: dict[str, Any] = {}
    summed: dict[str, int] = {}
    kind_reference_total = 0
    for kind in sorted(REFERENCE_KINDS):
        kind_counts = _count_mapping(per_kind_mapping[kind], STATUSES)
        if kind_counts is None or not kind_counts:
            raise ValueError("PBS per-kind reference status counts are invalid")
        denominator = sum(kind_counts.values())
        if denominator == 0 or kind_totals.get(kind) != denominator:
            raise ValueError("PBS per-kind reference denominator differs")
        kind_reference_total += denominator
        normalized[kind] = {
            "reference_fields": denominator,
            "status_counts": dict(sorted(kind_counts.items())),
            "semantic_links_qualified": False,
        }
        for status, value in kind_counts.items():
            summed[status] = summed.get(status, 0) + value
    if summed != counts or kind_reference_total != references:
        raise ValueError("PBS per-kind and aggregate denominators differ")
    return normalized


def review_reference_meanings(
    root: Path,
    receipt_path: str | Path = SCREEN_RECEIPT,
    *,
    require_per_kind: bool = False,
    expected_exact_commit: str | None = None,
    expected_run_id: str | None = None,
) -> dict[str, Any]:
    """Bind reviewed meanings to an exact hosted screen receipt.

    The legacy aggregate-only receipt remains readable for continuity. A new
    receipt can be required to include source reference counts by native kind;
    these are diagnostics only and never promote semantic links.
    """
    if receipt_path == SCREEN_RECEIPT:
        expected = root / receipt_path
        if expected.exists():
            raw = expected.read_bytes()
            if _digest(raw) != SCREEN_RECEIPT_SHA256:
                raise ValueError("PBS reference screen receipt digest differs")
    envelope, receipt_sha256 = _read_receipt(root, receipt_path)
    report = envelope["report"]
    if require_per_kind:
        if expected_exact_commit is None or expected_run_id is None:
            raise ValueError(
                "expected exact-main commit and workflow run ID are required"
            )
        _validate_expected_run_identity(
            report, expected_exact_commit, expected_run_id
        )
    qualification = _validate_source(report)
    counts = _count_mapping(
        qualification.get("reference_status_counts"), STATUSES
    )
    if counts is None or not {
        "unique_exact_literal",
        "no_exact_literal",
    } <= set(counts):
        raise ValueError("PBS reference screen aggregate counts are invalid")
    references = qualification.get("reference_fields")
    if (
        not isinstance(references, int)
        or isinstance(references, bool)
        or sum(counts.values()) != references
    ):
        raise ValueError("PBS reference screen match denominator differs")

    per_kind = qualification.get("reference_kind_status_counts")
    if per_kind is None:
        if require_per_kind:
            raise ValueError("PBS per-kind reference counts are required")
        normalized_per_kind = None
    else:
        normalized_per_kind = _validated_per_kind(
            qualification, counts, references
        )

    matched = counts.get("unique_exact_literal", 0)
    unmatched = counts.get("no_exact_literal", 0)
    return {
        "schema_id": "global-medicines-atlas.pbs-reference-meaning-review",
        "schema_version": 2 if normalized_per_kind is not None else 1,
        "profile_id": "pbs-april-2026-source-local-reference-review-v1",
        "status": "lexical_candidates_reviewed_semantic_links_unqualified",
        "source": {
            "dataset": report["dataset"],
            "revision": report["revision"],
            "member_sha256": MEMBER_SHA256,
            "native_digest": NATIVE_DIGEST,
            "native_fields": qualification["native_fields"],
            "screen_run_id": report["run_id"],
            "screen_workflow_commit": report["workflow_commit"],
            "screen_source_receipt_sha256": report[
                "source_receipt_file_sha256"
            ],
            "screen_receipt_sha256": receipt_sha256,
            "reference_fields_sha256": qualification["reference_fields_sha256"],
        },
        "reference_kinds": _meaning_profile(),
        "exact_source_screen": {
            "definitions": qualification["definition_fields"],
            "references": references,
            "unique_exact_literal_candidates": matched,
            "no_exact_literal": unmatched,
            "ambiguous_definition_literals": qualification[
                "ambiguous_definition_literals"
            ],
            "candidate_coverage_percent": round(100 * matched / references, 4),
            "interpretation": "candidate yield, not precision, recall, semantic validity, or relation accuracy",
            "per_kind_match_counts_available": normalized_per_kind is not None,
            "per_kind": normalized_per_kind,
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
