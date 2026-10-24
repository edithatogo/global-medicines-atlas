"""Fail-closed tests for the value-free PBS reference review packet."""

from __future__ import annotations

import json
from typing import Any

import pytest

from global_medicines_atlas.pbs_reference_review_packet import (
    MAX_PACKET_CASES,
    prepare_reference_review_packet,
)

_PBS = "{http://schema.pbs.gov.au/}"


def _example(
    index: int, multiplicity: int, *, target_base: str = "no_xml_base"
) -> dict[str, Any]:
    return {
        "reference_occurrence": f"/{_PBS}root/1/{_PBS}edge/{index}/attributes/href",
        "predicate_element": {
            "occurrence": f"/{_PBS}root/1/{_PBS}edge/{index}",
            "qname": f"{_PBS}edge",
        },
        "nearest_subject_element": None,
        "nearest_identifier_element": None,
        "target_multiplicity": multiplicity,
        "targets": [
            {
                "occurrence": f"/{_PBS}root/1/{_PBS}target/{target}",
                "qname": f"{_PBS}target",
                "xml_base_context": target_base,
            }
            for target in range(min(10, multiplicity))
        ],
    }


def _stratum(
    kind: str,
    status: str,
    shape: str,
    index: int,
    *,
    base: str = "no_xml_base",
    multiplicity: int = 0,
    no_base_candidates: int = 0,
    target_base: str = "no_xml_base",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "match_status": status,
        "predicate_element_qname": f"{_PBS}edge",
        "nearest_subject_element_qname": "none",
        "nearest_identifier_element_qname": "none",
        "xml_base_context": base,
        "literal_shape": shape,
        "occurrences": 1,
        "unique_target_occurrences": int(status == "unique_exact_literal"),
        "ambiguous_target_occurrences": int(
            status == "ambiguous_exact_literal"
        ),
        "no_xml_base_exact_target_occurrences": no_base_candidates,
        "unique_exact_literal_no_xml_base_candidates": no_base_candidates,
        "examples_omitted": 0,
        "examples": [_example(index, multiplicity, target_base=target_base)],
    }


def _meaning_report() -> dict[str, Any]:
    rows = [
        _stratum(
            "xlink_href",
            "unique_exact_literal",
            "fragment",
            1,
            multiplicity=1,
            no_base_candidates=1,
        ),
        _stratum(
            "xlink_href",
            "unique_exact_literal",
            "fragment",
            2,
            base="xml_base_present",
            multiplicity=1,
        ),
        _stratum(
            "xlink_href",
            "ambiguous_exact_literal",
            "fragment",
            3,
            multiplicity=2,
        ),
        _stratum("xlink_href", "no_exact_literal", "fragment", 4),
        _stratum("xlink_href", "empty_literal", "empty", 5),
        _stratum(
            "xlink_href", "unsupported_reference_form", "relative_or_other", 6
        ),
        _stratum(
            "rdf_resource",
            "unique_exact_literal",
            "absolute_looking",
            7,
            multiplicity=1,
            no_base_candidates=1,
        ),
    ]
    return {
        "schema_id": "global-medicines-atlas.pbs-reference-meaning-review",
        "schema_version": 3,
        "status": "source_context_screen_reconciled_semantic_links_unqualified",
        "source": {
            "dataset": "edithatogo/australian-pbs-source-archive",
            "revision": "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7",
            "member_sha256": "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43",
            "screen_run_id": "40063458639",
            "screen_workflow_commit": "3d975e71f51037206ad5b5d08e013dabef16f042",
            "screen_receipt_sha256": "a" * 64,
        },
        "exact_source_screen": {
            "references": len(rows),
            "per_kind": {
                "rdf_resource": {
                    "reference_fields": 1,
                    "status_counts": {"unique_exact_literal": 1},
                    "semantic_links_qualified": False,
                },
                "xlink_href": {
                    "reference_fields": 6,
                    "status_counts": {
                        "unique_exact_literal": 2,
                        "ambiguous_exact_literal": 1,
                        "no_exact_literal": 1,
                        "empty_literal": 1,
                        "unsupported_reference_form": 1,
                    },
                    "semantic_links_qualified": False,
                },
            },
        },
        "source_context_screen": {
            "schema_id": "global-medicines-atlas.pbs-reference-context-screen",
            "schema_version": 1,
            "reference_occurrences": len(rows),
            "strata_count": len(rows),
            "examples_emitted": len(rows),
            "examples_omitted": 0,
            "unique_exact_literal_no_xml_base_candidates": 2,
            "strata": rows,
            "uri_resolution_performed": False,
            "literal_values_emitted": False,
            "raw_source_emitted": False,
            "semantic_relationships_qualified": False,
            "external_targets_fetched": 0,
        },
        "scope": {"semantic_relationships_qualified": False},
    }


def test_review_packet_separates_candidate_examples_and_controls_without_edges():
    packet = prepare_reference_review_packet(_meaning_report())

    assert packet["status"] == (
        "source_context_examples_unreviewed_semantic_links_unqualified"
    )
    assert len(packet["cases"]) == 7
    assert packet["candidate_occurrences_by_category"] == {
        "ambiguous_target_negative_control": 1,
        "empty_literal_negative_control": 1,
        "no_target_negative_control": 1,
        "unique_fragment_literal_candidate": 1,
        "unique_literal_candidate_requires_uri_review": 1,
        "unsupported_form_negative_control": 1,
        "xml_base_abstention_control": 1,
    }
    candidate = next(
        case
        for case in packet["cases"]
        if case["category"] == "unique_fragment_literal_candidate"
    )
    assert candidate["target_multiplicity"] == 1
    assert candidate["uri_resolution"] == "not_performed"
    assert candidate["link_role"] == "not_recorded_in_context_profile"
    assert candidate["target_type_meaning"] == "not_established"
    assert all(
        not case["semantic_relationship_qualified"] for case in packet["cases"]
    )
    assert packet["calibration"]["source_cases_reviewed"] == 0
    assert packet["calibration"]["semantic_relationships_qualified"] is False
    assert "private-target" not in json.dumps(packet)


def test_review_packet_round_robin_keeps_positive_and_negative_controls_bounded():
    packet = prepare_reference_review_packet(_meaning_report(), max_cases=3)

    assert len(packet["cases"]) == 3
    assert [case["category"] for case in packet["cases"]] == [
        "unique_fragment_literal_candidate",
        "xml_base_abstention_control",
        "ambiguous_target_negative_control",
    ]
    assert packet["bounded_case_limit"] == 3


def test_review_packet_requires_valid_exact_source_and_screen_contract():
    report = _meaning_report()
    report["source"]["member_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="source binding differs"):
        prepare_reference_review_packet(report)

    report = _meaning_report()
    report["scope"]["semantic_relationships_qualified"] = True
    with pytest.raises(ValueError, match="preserve semantic abstention"):
        prepare_reference_review_packet(report)

    report = _meaning_report()
    report["source_context_screen"]["uri_resolution_performed"] = True
    with pytest.raises(ValueError, match="remain diagnostic"):
        prepare_reference_review_packet(report)


def test_review_packet_rejects_source_values_unknown_fields_and_bad_examples():
    report = _meaning_report()
    report["source_context_screen"]["strata"][0]["value"] = "secret"
    with pytest.raises(ValueError, match="contains source values"):
        prepare_reference_review_packet(report)

    report = _meaning_report()
    report["source_context_screen"]["strata"][0]["unexpected"] = "ignored"
    with pytest.raises(ValueError, match="stratum schema differs"):
        prepare_reference_review_packet(report)

    report = _meaning_report()
    report["source_context_screen"]["strata"][0]["examples"][0][
        "target_multiplicity"
    ] = 2
    with pytest.raises(
        ValueError, match="reference context target list differs"
    ):
        prepare_reference_review_packet(report)


def test_review_packet_rejects_bad_case_limits_and_unreconciled_reports():
    with pytest.raises(ValueError, match="case bound differs"):
        prepare_reference_review_packet(
            _meaning_report(), max_cases=MAX_PACKET_CASES + 1
        )

    report = _meaning_report()
    report["schema_version"] = 2
    with pytest.raises(ValueError, match="not source-context reconciled"):
        prepare_reference_review_packet(report)

    report = _meaning_report()
    report["exact_source_screen"]["references"] += 1
    with pytest.raises(ValueError, match="denominators differ"):
        prepare_reference_review_packet(report)


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        ("contract", "contract differs"),
        ("external_target", "fetched an external target"),
        ("strata_count", "strata differ"),
        ("example_bound", "examples exceed the bound"),
        ("kind", "kind differs"),
        ("match_status", "match status differs"),
        ("base", "base profile differs"),
        ("shape", "literal shape differs"),
        ("count", "stratum counts differ"),
        ("examples", "examples differ"),
        ("occurrence", "reference occurrence differs"),
        ("qname", "reference element QName differs"),
        ("target_base", "target base profile differs"),
    ],
)
def test_review_packet_rejects_malformed_context(  # ruff: ignore[too-many-branches] - keeps synthetic malformed cases explicit
    operation: str, message: str
) -> None:
    report = _meaning_report()
    context = report["source_context_screen"]
    row = context["strata"][0]
    example = row["examples"][0]
    if operation == "contract":
        context["schema_version"] = 2
    elif operation == "external_target":
        context["external_targets_fetched"] = 1
    elif operation == "strata_count":
        context["strata_count"] = 0
    elif operation == "example_bound":
        context["examples_emitted"] = 1001
    elif operation == "kind":
        row["kind"] = "unknown"
    elif operation == "match_status":
        row["match_status"] = "bad"
    elif operation == "base":
        row["xml_base_context"] = "bad"
    elif operation == "shape":
        row["literal_shape"] = "bad"
    elif operation == "count":
        row["occurrences"] = 0
    elif operation == "examples":
        row["examples"] = [{}] * 6
    elif operation == "occurrence":
        example["reference_occurrence"] = ""
    elif operation == "qname":
        example["predicate_element"]["qname"] = ""
    else:
        example["targets"][0]["xml_base_context"] = "bad"

    with pytest.raises((TypeError, ValueError), match=message):
        prepare_reference_review_packet(report)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("source", "screen_run_id"), "x", "source binding differs"),
        (("source", "screen_workflow_commit"), "bad", "source binding differs"),
        (("source", "screen_receipt_sha256"), "bad", "source binding differs"),
        (
            (
                "exact_source_screen",
                "per_kind",
                "rdf_resource",
                "status_counts",
            ),
            {"unique_exact_literal": 2},
            "status denominator differs",
        ),
    ],
)
def test_review_packet_rejects_bad_source_and_denominator(
    path: tuple[str, ...], value: object, message: str
) -> None:
    report = _meaning_report()
    target = report
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValueError, match=message):
        prepare_reference_review_packet(report)
