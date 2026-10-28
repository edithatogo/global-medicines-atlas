"""Focused checks for the bounded PBS reference case receipt."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import global_medicines_atlas.pbs_reference_case_adjudication as adjudication
from global_medicines_atlas.pbs_reference_case_adjudication import (
    ADJUDICATION_PATH,
    PACKET_PATH,
    URI_RECONCILIATION_PATH,
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


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("[]", "envelope is not an object"),
        (json.dumps({"report": []}), "report is not an object"),
    ],
)
def test_receipt_reader_rejects_non_object_envelope_and_report(
    tmp_path: Path, payload: str, message: str
) -> None:
    for relative in (PACKET_PATH, URI_RECONCILIATION_PATH):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((_ROOT / relative).read_bytes())
    destination = tmp_path / ADJUDICATION_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(payload, encoding="utf-8")

    with pytest.raises(TypeError, match=message):
        validate_reference_case_adjudication(tmp_path)


def test_reader_rejects_envelope_digest_drift(tmp_path: Path) -> None:
    destination = tmp_path / ADJUDICATION_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps({"report": {}, "report_sha256": "0" * 64}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="report digest differs"):
        adjudication._read_envelope(tmp_path, ADJUDICATION_PATH)


def test_value_guard_checks_nested_objects_and_lists() -> None:
    with pytest.raises(ValueError, match="must not contain source values"):
        adjudication._validate_no_source_values({
            "outer": [{"REFERENCE_VALUE": "withheld"}]
        })


def test_packet_and_uri_contracts_reject_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packet_bytes = (_ROOT / PACKET_PATH).read_bytes()
    packet_report = json.loads(packet_bytes)["report"]
    monkeypatch.setattr(adjudication, "PACKET_FILE_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="pinned PBS reference packet"):
        adjudication._validate_packet_contract(packet_report, packet_bytes)

    uri_bytes = (_ROOT / URI_RECONCILIATION_PATH).read_bytes()
    uri_report = json.loads(uri_bytes)["report"]
    monkeypatch.setattr(
        adjudication,
        "URI_RECONCILIATION_FILE_SHA256",
        "0" * 64,
    )
    with pytest.raises(ValueError, match="pinned PBS URI reconciliation"):
        adjudication._validate_uri_contract(
            uri_report,
            uri_bytes,
            packet_bytes,
            json.loads(packet_bytes)["report_sha256"],
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("denominator", "denominator differs"),
        ("duplicate_case_id", "case identities differ"),
        ("occurrence_binding", "occurrence binding differs"),
        ("semantic_boundary", "semantic boundary differs"),
        ("pointer_role", "unsupported structural pointer role"),
        ("reference_digest", "case occurrence digest differs"),
        ("target_digest", "case target digest differs"),
        ("negative_control", "no-target control changed"),
        ("candidate_binding", "candidate target binding differs"),
    ],
)
def test_builder_rejects_case_invariant_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    packet_bytes = (_ROOT / PACKET_PATH).read_bytes()
    uri_bytes = (_ROOT / URI_RECONCILIATION_PATH).read_bytes()
    packet_envelope = deepcopy(json.loads(packet_bytes))
    uri_envelope = deepcopy(json.loads(uri_bytes))
    packet_cases = packet_envelope["report"]["cases"]
    uri_cases = uri_envelope["report"]["cases"]
    uri_by_id = {case["case_id"]: case for case in uri_cases}

    if mutation == "denominator":
        monkeypatch.setattr(adjudication, "CASE_COUNT", 47)
    elif mutation == "duplicate_case_id":
        packet_cases[-1]["case_id"] = packet_cases[0]["case_id"]
    else:
        candidate = next(
            case
            for case in packet_cases
            if case["category"] != adjudication.NO_TARGET_CATEGORY
        )
        negative = next(
            case
            for case in packet_cases
            if case["category"] == adjudication.NO_TARGET_CATEGORY
        )
        uri_case = uri_by_id[candidate["case_id"]]
        if mutation == "occurrence_binding":
            uri_case["category"] = "changed"
        elif mutation == "semantic_boundary":
            uri_case["edges_emitted"] = True
        elif mutation == "pointer_role":
            uri_case["structural_role"] = "unsupported"
        elif mutation == "reference_digest":
            uri_case["reference_occurrence_sha256"] = "0" * 64
        elif mutation == "target_digest":
            uri_case["target_occurrence_sha256"] = "0" * 64
        elif mutation == "negative_control":
            negative["target_multiplicity"] = 1
            uri_by_id[negative["case_id"]]["target_multiplicity"] = 1
        elif mutation == "candidate_binding":
            candidate["target_multiplicity"] = 2
            uri_case["target_multiplicity"] = 2

    monkeypatch.setattr(
        adjudication,
        "_read_envelope",
        lambda _root, relative: (
            (packet_bytes, packet_envelope)
            if relative == PACKET_PATH
            else (uri_bytes, uri_envelope)
        ),
    )
    monkeypatch.setattr(
        adjudication, "_validate_packet_contract", lambda *_: None
    )
    monkeypatch.setattr(adjudication, "_validate_uri_contract", lambda *_: None)

    with pytest.raises(ValueError, match=message):
        build_reference_case_adjudication(tmp_path)


def test_validator_rejects_receipt_content_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {"expected": True}
    monkeypatch.setattr(
        adjudication,
        "build_reference_case_adjudication",
        lambda _root: expected,
    )
    monkeypatch.setattr(
        adjudication, "_canonical_sha256", lambda _report: "pinned"
    )
    monkeypatch.setattr(
        adjudication,
        "_read_envelope",
        lambda _root, _relative: (
            b"receipt",
            {"report": {"different": True}, "report_sha256": "pinned"},
        ),
    )

    with pytest.raises(ValueError, match="content differs"):
        validate_reference_case_adjudication(_ROOT)


def test_validator_detects_receipt_bytes_changed_during_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {"safe": True}
    raw = b"bytes captured before concurrent change"
    envelope = {
        "report": expected,
        "report_sha256": _canonical_sha256(expected),
    }
    monkeypatch.setattr(
        adjudication,
        "build_reference_case_adjudication",
        lambda _root: expected,
    )
    monkeypatch.setattr(
        adjudication,
        "_read_envelope",
        lambda _root, _relative: (raw, envelope),
    )

    with pytest.raises(ValueError, match="bytes changed during validation"):
        validate_reference_case_adjudication(_ROOT)


def test_writer_emits_canonical_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = {"safe": "value-free"}
    monkeypatch.setattr(
        adjudication, "build_reference_case_adjudication", lambda _root: report
    )

    (tmp_path / ADJUDICATION_PATH).parent.mkdir(parents=True)
    destination = adjudication.write_reference_case_adjudication(tmp_path)
    envelope = json.loads(destination.read_text(encoding="utf-8"))
    assert destination == tmp_path / ADJUDICATION_PATH
    assert envelope == {
        "report": report,
        "report_sha256": _canonical_sha256(report),
    }
