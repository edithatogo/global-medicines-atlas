"""Prepare bounded, value-free PBS source-reference review packets.

The packet organizes source-context examples for review. It does not resolve
URIs, assign predicate meaning, estimate semantic precision, or qualify graph
relationships. Exact literal matches remain candidates until those checks are
supported by reviewed source evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, cast

DATASET = "edithatogo/australian-pbs-source-archive"
REVISION = "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7"
MEMBER_SHA256 = (
    "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
)
MAX_PACKET_CASES = 64
MAX_EXAMPLES_PER_STRATUM = 5
MAX_CONTEXT_STRATA = 10_000
MAX_CONTEXT_EXAMPLES = 1_000
MAX_CONTEXT_TARGETS_PER_EXAMPLE = 10
MIN_AMBIGUOUS_TARGETS = 2
STRATIFIED_CONTEXT_SCHEMA_VERSION = 2
STRATIFIED_CONTEXT_EXAMPLE_POLICY = (
    "up_to_five_value_free_examples_per_structural_stratum"
)
MEANING_REPORT_SCHEMA_VERSION = 3
MAX_OCCURRENCE_BYTES = 4096
MAX_QNAME_BYTES = 256
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_REFERENCE_KINDS = {"rdf_resource", "xlink_href"}
_MATCH_STATUSES = {
    "ambiguous_exact_literal",
    "empty_literal",
    "no_exact_literal",
    "unique_exact_literal",
    "unsupported_reference_form",
}
_LITERAL_SHAPES = {
    "absolute_looking",
    "empty",
    "fragment",
    "relative_or_other",
    "root_relative_looking",
    "scheme_looking",
}
_CONTEXT_FLAGS = (
    "uri_resolution_performed",
    "literal_values_emitted",
    "raw_source_emitted",
    "semantic_relationships_qualified",
)
_FORBIDDEN_KEYS = {
    "literal",
    "value",
    "uri",
    "reference_value",
    "raw_source",
}


def _object(value: object, message: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(message)
    members = cast("dict[object, object]", value)
    if any(not isinstance(key, str) for key in members):
        raise ValueError(message)
    return cast("dict[str, Any]", value)


def _bounded_text(value: object, limit: int, message: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode()) > limit:
        raise ValueError(message)
    return value


def _nonnegative_int(value: object, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(message)
    return value


def _validate_no_source_values(value: object) -> None:
    if isinstance(value, dict):
        members = cast("dict[object, object]", value)
        if any(
            isinstance(key, str) and key.casefold() in _FORBIDDEN_KEYS
            for key in members
        ):
            raise ValueError("reference review input contains source values")
        for nested in members.values():
            _validate_no_source_values(nested)
    elif isinstance(value, list):
        for nested in cast("list[object]", value):
            _validate_no_source_values(nested)


def _validate_context(  # ruff: ignore[too-many-branches, too-many-statements, too-many-locals] - validate the complete untrusted aggregate contract in one pass
    context_value: object, references: int
) -> dict[str, Any]:
    context = _object(context_value, "reference context must be an object")
    required = {
        "schema_id",
        "schema_version",
        "reference_occurrences",
        "strata_count",
        "examples_emitted",
        "examples_omitted",
        "unique_exact_literal_no_xml_base_candidates",
        "strata",
        *_CONTEXT_FLAGS,
        "external_targets_fetched",
    }
    version = context.get("schema_version")
    expected = required
    if version == STRATIFIED_CONTEXT_SCHEMA_VERSION:
        expected = required | {"example_selection_policy"}
    if set(context) != expected:
        raise ValueError("reference context schema differs")
    if (
        context["schema_id"]
        != "global-medicines-atlas.pbs-reference-context-screen"
        or isinstance(version, bool)
        or version not in {1, STRATIFIED_CONTEXT_SCHEMA_VERSION}
    ):
        raise ValueError("reference context contract differs")
    if (
        version == STRATIFIED_CONTEXT_SCHEMA_VERSION
        and context["example_selection_policy"]
        != STRATIFIED_CONTEXT_EXAMPLE_POLICY
    ):
        raise ValueError("reference context contract differs")
    for flag in _CONTEXT_FLAGS:
        if context[flag] is not False:
            raise ValueError("reference context must remain diagnostic")
    if context["external_targets_fetched"] != 0:
        raise ValueError("reference context fetched an external target")
    if context["reference_occurrences"] != references:
        raise ValueError("reference context denominator differs")
    rows_value = context["strata"]
    rows = cast("list[object]", rows_value)
    if not isinstance(rows_value, list) or len(rows) != context["strata_count"]:
        raise ValueError("reference context strata differ")
    if len(rows) > MAX_CONTEXT_STRATA:
        raise ValueError("reference context strata exceed the bound")
    if context["examples_emitted"] > MAX_CONTEXT_EXAMPLES:
        raise ValueError("reference context examples exceed the bound")
    _validate_no_source_values(context)
    occurrence_total = example_total = omitted_total = (
        no_base_candidate_total
    ) = 0
    for row_value in rows:
        row = _object(row_value, "reference context stratum must be an object")
        if set(row) != {
            "kind",
            "match_status",
            "predicate_element_qname",
            "nearest_subject_element_qname",
            "nearest_identifier_element_qname",
            "xml_base_context",
            "literal_shape",
            "occurrences",
            "unique_target_occurrences",
            "ambiguous_target_occurrences",
            "no_xml_base_exact_target_occurrences",
            "unique_exact_literal_no_xml_base_candidates",
            "examples_omitted",
            "examples",
        }:
            raise ValueError("reference context stratum schema differs")
        if row["kind"] not in _REFERENCE_KINDS:
            raise ValueError("reference context kind differs")
        if row["match_status"] not in _MATCH_STATUSES:
            raise ValueError("reference context match status differs")
        if row["xml_base_context"] not in {"no_xml_base", "xml_base_present"}:
            raise ValueError("reference context base profile differs")
        if row["literal_shape"] not in _LITERAL_SHAPES:
            raise ValueError("reference context literal shape differs")
        for name in (
            "predicate_element_qname",
            "nearest_subject_element_qname",
            "nearest_identifier_element_qname",
        ):
            if (
                not isinstance(row[name], str)
                or len(row[name].encode()) > MAX_QNAME_BYTES
            ):
                raise ValueError("reference context QName differs")
        counts = {
            name: _nonnegative_int(row[name], "reference context count differs")
            for name in (
                "occurrences",
                "unique_target_occurrences",
                "ambiguous_target_occurrences",
                "no_xml_base_exact_target_occurrences",
                "unique_exact_literal_no_xml_base_candidates",
                "examples_omitted",
            )
        }
        if counts["occurrences"] == 0 or any(
            counts[name] > counts["occurrences"]
            for name in (
                "unique_target_occurrences",
                "ambiguous_target_occurrences",
                "no_xml_base_exact_target_occurrences",
                "unique_exact_literal_no_xml_base_candidates",
            )
        ):
            raise ValueError("reference context stratum counts differ")
        examples_value = row["examples"]
        examples = cast("list[object]", examples_value)
        if (
            not isinstance(examples_value, list)
            or len(examples) > MAX_EXAMPLES_PER_STRATUM
        ):
            raise ValueError("reference context examples differ")
        occurrence_total += counts["occurrences"]
        example_total += len(examples)
        omitted_total += counts["examples_omitted"]
        no_base_candidate_total += counts[
            "unique_exact_literal_no_xml_base_candidates"
        ]
        for example_value in examples:
            example = _validate_example(example_value)
            multiplicity = example["target_multiplicity"]
            expected_multiplicity = (
                1 if row["match_status"] == "unique_exact_literal" else None
            )
            if (
                expected_multiplicity is not None
                and multiplicity != expected_multiplicity
            ):
                raise ValueError("unique reference example target differs")
            if (
                row["match_status"] == "ambiguous_exact_literal"
                and multiplicity < MIN_AMBIGUOUS_TARGETS
            ):
                raise ValueError("ambiguous reference example target differs")
            if (
                row["match_status"]
                in {
                    "empty_literal",
                    "no_exact_literal",
                    "unsupported_reference_form",
                }
                and multiplicity != 0
            ):
                raise ValueError("negative reference example target differs")
    if (
        occurrence_total != references
        or example_total != context["examples_emitted"]
        or omitted_total != context["examples_omitted"]
        or no_base_candidate_total
        != context["unique_exact_literal_no_xml_base_candidates"]
    ):
        raise ValueError("reference context denominator differs")
    return context


def _validate_example(value: object) -> dict[str, Any]:
    example = _object(value, "reference context example must be an object")
    if set(example) != {
        "reference_occurrence",
        "predicate_element",
        "nearest_subject_element",
        "nearest_identifier_element",
        "target_multiplicity",
        "targets",
    }:
        raise ValueError("reference context example schema differs")
    _bounded_text(
        example["reference_occurrence"],
        MAX_OCCURRENCE_BYTES,
        "reference occurrence differs",
    )
    for name in (
        "predicate_element",
        "nearest_subject_element",
        "nearest_identifier_element",
    ):
        member = example[name]
        if member is None and name != "predicate_element":
            continue
        record = _object(member, "reference context element must be an object")
        if set(record) != {"occurrence", "qname"}:
            raise ValueError("reference context element schema differs")
        _bounded_text(
            record["occurrence"],
            MAX_OCCURRENCE_BYTES,
            "reference element occurrence differs",
        )
        _bounded_text(
            record["qname"], MAX_QNAME_BYTES, "reference element QName differs"
        )
    multiplicity = _nonnegative_int(
        example["target_multiplicity"], "target multiplicity differs"
    )
    targets_value = example["targets"]
    targets = cast("list[object]", targets_value)
    if (
        not isinstance(targets_value, list)
        or len(targets) > MAX_CONTEXT_TARGETS_PER_EXAMPLE
    ):
        raise ValueError("reference context targets differ")
    if len(targets) != min(multiplicity, MAX_CONTEXT_TARGETS_PER_EXAMPLE):
        raise ValueError("reference context target list differs")
    for target_value in targets:
        target = _object(target_value, "reference target must be an object")
        if set(target) != {"occurrence", "qname", "xml_base_context"}:
            raise ValueError("reference target schema differs")
        _bounded_text(
            target["occurrence"],
            MAX_OCCURRENCE_BYTES,
            "target occurrence differs",
        )
        _bounded_text(target["qname"], MAX_QNAME_BYTES, "target QName differs")
        if target["xml_base_context"] not in {
            "no_xml_base",
            "xml_base_present",
        }:
            raise ValueError("target base profile differs")
    return example


def _case_category(  # ruff: ignore[too-many-return-statements] - each explicit branch names an auditable control class
    row: dict[str, Any], example: dict[str, Any]
) -> str:
    status = row["match_status"]
    if status == "empty_literal":
        return "empty_literal_negative_control"
    if status == "unsupported_reference_form":
        return "unsupported_form_negative_control"
    if status == "ambiguous_exact_literal":
        return "ambiguous_target_negative_control"
    if status == "no_exact_literal":
        return "no_target_negative_control"
    if row["kind"] == "xlink_href" and row["literal_shape"] == "fragment":
        if row["xml_base_context"] != "no_xml_base" or any(
            target["xml_base_context"] != "no_xml_base"
            for target in example["targets"]
        ):
            return "xml_base_abstention_control"
        return "unique_fragment_literal_candidate"
    return "unique_literal_candidate_requires_uri_review"


def _category_occurrences(context: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}

    def add(category: str, amount: int) -> None:
        if amount:
            counts[category] = counts.get(category, 0) + amount

    for row_value in cast("list[object]", context["strata"]):
        row = cast("dict[str, Any]", row_value)
        occurrences = row["occurrences"]
        status = row["match_status"]
        if status == "empty_literal":
            add("empty_literal_negative_control", occurrences)
        elif status == "unsupported_reference_form":
            add("unsupported_form_negative_control", occurrences)
        elif status == "ambiguous_exact_literal":
            add("ambiguous_target_negative_control", occurrences)
        elif status == "no_exact_literal":
            add("no_target_negative_control", occurrences)
        elif row["kind"] == "xlink_href" and row["literal_shape"] == "fragment":
            candidate_count = row["unique_exact_literal_no_xml_base_candidates"]
            add("unique_fragment_literal_candidate", candidate_count)
            add("xml_base_abstention_control", occurrences - candidate_count)
        else:
            add("unique_literal_candidate_requires_uri_review", occurrences)
    return dict(sorted(counts.items()))


def _valid_source_binding(source: dict[str, Any]) -> bool:
    run_id = source.get("screen_run_id")
    commit = source.get("screen_workflow_commit")
    receipt_digest = source.get("screen_receipt_sha256")
    return (
        source.get("dataset") == DATASET
        and source.get("revision") == REVISION
        and source.get("member_sha256") == MEMBER_SHA256
        and isinstance(run_id, str)
        and run_id.isdigit()
        and isinstance(commit, str)
        and re.fullmatch(r"[0-9a-f]{40}", commit) is not None
        and isinstance(receipt_digest, str)
        and _SHA256_RE.fullmatch(receipt_digest) is not None
    )


def prepare_reference_review_packet(  # ruff: ignore[too-many-branches, too-many-statements, too-many-locals] - sequential fail-closed validation and deterministic packet construction
    meaning_report: dict[str, Any], *, max_cases: int = MAX_PACKET_CASES
) -> dict[str, Any]:
    """Build a bounded review queue from a reconciled source-context report.

    The input must come from ``review_reference_meanings`` after validation of
    an exact hosted screen receipt. The output can prioritize occurrence
    review, but cannot infer semantic links or estimate precision.
    """
    if isinstance(max_cases, bool) or not 1 <= max_cases <= MAX_PACKET_CASES:
        raise ValueError("reference review case bound differs")
    report = _object(
        meaning_report, "reference meaning report must be an object"
    )
    if (
        report.get("schema_id")
        != "global-medicines-atlas.pbs-reference-meaning-review"
        or report.get("schema_version") != MEANING_REPORT_SCHEMA_VERSION
        or report.get("status")
        != "source_context_screen_reconciled_semantic_links_unqualified"
    ):
        raise ValueError(
            "reference meaning report is not source-context reconciled"
        )
    source = _object(
        report.get("source"), "reference report source must be an object"
    )
    if not _valid_source_binding(source):
        raise ValueError("reference report source binding differs")
    scope = _object(
        report.get("scope"), "reference report scope must be an object"
    )
    if scope.get("semantic_relationships_qualified") is not False:
        raise ValueError("reference report must preserve semantic abstention")
    screen = _object(
        report.get("exact_source_screen"),
        "reference source screen must be an object",
    )
    references = _nonnegative_int(
        screen.get("references"), "reference screen denominator differs"
    )
    per_kind = _object(
        screen.get("per_kind"), "reference kind counts must be an object"
    )
    kind_denominators = 0
    for kind in _REFERENCE_KINDS:
        kind_report = _object(per_kind.get(kind), "reference kind row differs")
        if kind_report.get("semantic_links_qualified") is not False:
            raise ValueError("reference kind must preserve semantic abstention")
        denominator = _nonnegative_int(
            kind_report.get("reference_fields"), "reference kind count differs"
        )
        status_counts = _object(
            kind_report.get("status_counts"),
            "reference kind status counts differ",
        )
        if (
            sum(
                _nonnegative_int(value, "reference kind status count differs")
                for value in status_counts.values()
            )
            != denominator
        ):
            raise ValueError("reference kind status denominator differs")
        kind_denominators += denominator
    if set(per_kind) != _REFERENCE_KINDS or kind_denominators != references:
        raise ValueError("reference kind denominators differ")
    context = _validate_context(report.get("source_context_screen"), references)
    cases_by_category: dict[str, list[dict[str, Any]]] = {}
    omitted_examples = 0
    for row_value in cast("list[object]", context["strata"]):
        row = cast("dict[str, Any]", row_value)
        omitted_examples += row["examples_omitted"]
        for example_value in cast("list[object]", row["examples"]):
            example = cast("dict[str, Any]", example_value)
            example_category = _case_category(row, example)
            predicate = cast("dict[str, Any]", example["predicate_element"])
            targets = cast("list[dict[str, Any]]", example["targets"])
            target = targets[0] if len(targets) == 1 else None
            case_material = {
                "kind": row["kind"],
                "category": example_category,
                "reference_occurrence": example["reference_occurrence"],
                "target_occurrence": target["occurrence"] if target else None,
            }
            case_id = hashlib.sha256(
                json.dumps(
                    [source["screen_receipt_sha256"], case_material],
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            case = {
                "case_id": case_id,
                **case_material,
                "source_element_qname": predicate["qname"],
                "target_element_qname": target["qname"] if target else None,
                "reference_xml_base_context": row["xml_base_context"],
                "target_xml_base_context": target["xml_base_context"]
                if target
                else None,
                "target_multiplicity": example["target_multiplicity"],
                "uri_resolution": "not_performed",
                "link_role": "not_recorded_in_context_profile",
                "target_type_meaning": "not_established",
                "adjudication": "unreviewed",
                "semantic_relationship_qualified": False,
            }
            cases_by_category.setdefault(example_category, []).append(case)
    category_order = (
        "unique_fragment_literal_candidate",
        "xml_base_abstention_control",
        "ambiguous_target_negative_control",
        "no_target_negative_control",
        "empty_literal_negative_control",
        "unsupported_form_negative_control",
        "unique_literal_candidate_requires_uri_review",
    )
    cases: list[dict[str, Any]] = []
    while len(cases) < max_cases:
        added = False
        for category in category_order:
            values = cases_by_category.get(category, [])
            if values:
                cases.append(values.pop(0))
                added = True
                if len(cases) == max_cases:
                    break
        if not added:
            break
    return {
        "schema_id": "global-medicines-atlas.pbs-reference-review-packet",
        "schema_version": 1,
        "status": "source_context_examples_unreviewed_semantic_links_unqualified",
        "source": {
            "dataset": source["dataset"],
            "revision": source["revision"],
            "member_sha256": source["member_sha256"],
            "screen_run_id": source["screen_run_id"],
            "screen_workflow_commit": source["screen_workflow_commit"],
            "screen_receipt_sha256": source["screen_receipt_sha256"],
        },
        "screen_denominator": references,
        "context_examples_emitted": context["examples_emitted"],
        "context_examples_omitted": omitted_examples,
        "bounded_case_limit": max_cases,
        "sampling_method": "deterministic source-order examples within context strata; not a probability sample",
        "candidate_occurrences_by_category": _category_occurrences(context),
        "cases": cases,
        "review_requirements": [
            "resolve URI syntax and effective base for each occurrence",
            "confirm the target is in the same source document and uniquely identified",
            "establish the XLink type/role or RDF predicate meaning",
            "establish the target element type meaning",
            "record reviewed positive and negative source cases before estimating match behavior",
        ],
        "calibration": {
            "source_cases_reviewed": 0,
            "source_semantic_precision": "not_estimable_without_reviewed_source_labels",
            "promotion_rule": "no literal candidate or review-packet case is emitted as a semantic edge",
            "semantic_relationships_qualified": False,
        },
        "scope": {
            "source_values_emitted": False,
            "raw_source_emitted": False,
            "new_sources": 0,
            "new_admissions": 0,
            "consumer_canaries": 0,
            "publications": 0,
            "semantic_relationships_qualified": False,
        },
    }
