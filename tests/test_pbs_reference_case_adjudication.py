"""Focused checks for the bounded PBS reference case receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from global_medicines_atlas.pbs_reference_case_adjudication import (
    ADJUDICATION_PATH,
    build_reference_case_adjudication,
    validate_reference_case_adjudication,
)

_ROOT = Path(__file__).parents[1]


def _canonical_sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def test_receipt_is_bound_to_exact_packet_and_uri_reconciliation() -> None:
    report = validate_reference_case_adjudication(_ROOT)
    rebuilt = build_reference_case_adjudication(_ROOT)
    envelope = json.loads((_ROOT / ADJUDICATION_PATH).read_text())

    assert report == rebuilt == envelope["report"]
    assert envelope["report_sha256"] == _canonical_sha256(report)
    assert report["inputs"]["case_packet_file_sha256"] == (
        "c38840116e821dffe5b06e5df14b1d7140f9e4446fbf8c14ea009a9e8b732829"
    )
    assert report["inputs"]["uri_reconciliation_file_sha256"] == (
        "3698d217957c4d3263fce010d8ed6441c2050866052e1308fa352c6cd22772bb"
    )
    assert report["source"]["member_sha256"] == (
        "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
    )


def test_all_cases_keep_structural_and_semantic_dispositions_separate() -> None:
    report = build_reference_case_adjudication(_ROOT)
    cases = report["cases"]

    assert len(cases) == 46
    assert all(
        case["structural_pointer_role"]
        in {
            "rdf_resource_attribute",
            "xlink_href_attribute",
        }
        for case in cases
    )
    assert all(
        case["semantic_relationship_qualified"] is False for case in cases
    )
    assert all(case["edges_emitted"] is False for case in cases)
    assert report["review_scope"] == {
        "case_count": 46,
        "structural_pointer_roles_supported": 46,
        "no_target_hard_negatives": 11,
        "semantic_relationships_qualified": False,
        "edges_emitted": False,
        "precision_claimed": False,
        "recall_claimed": False,
        "corpus_generalizable_match_quality_claimed": False,
        "admission_or_clinical_meaning_claimed": False,
        "meaning": "structural roles and exact member-scoped resolution only; no semantic relationship adjudication",
    }
    assert all(case["missing_evidence"] for case in cases)


def test_eleven_no_target_cases_remain_scoped_hard_negatives() -> None:
    report = build_reference_case_adjudication(_ROOT)
    negatives = [case for case in report["cases"] if case["hard_negative"]]

    assert len(negatives) == 11
    assert all(
        case["category"] == "no_target_negative_control" for case in negatives
    )
    assert all(
        case["member_resolution"] == "absolute_uri_no_member_definition"
        for case in negatives
    )
    assert all(case["target_multiplicity"] == 0 for case in negatives)
    assert all(case["target_occurrence_sha256"] is None for case in negatives)
    assert all(
        case["disposition"] == "no_definition_in_pinned_member_hard_negative"
        for case in negatives
    )


def test_validator_rejects_semantic_promotion_in_receipt(
    tmp_path: Path,
) -> None:
    for relative in (
        ADJUDICATION_PATH,
        "quality/qualifications/pbs-native-reference-review-packet-20261025-40103169910.json",
        "quality/qualifications/pbs-native-reference-uri-review-reconciliation-20261025-40120162365.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((_ROOT / relative).read_bytes())

    destination = tmp_path / ADJUDICATION_PATH
    envelope = json.loads(destination.read_text())
    envelope["report"]["cases"][0]["semantic_relationship_qualified"] = True
    envelope["report_sha256"] = _canonical_sha256(envelope["report"])
    destination.write_text(json.dumps(envelope, indent=2) + "\n")

    with pytest.raises(ValueError, match="differs from pinned inputs"):
        validate_reference_case_adjudication(tmp_path)
