"""Synthetic contract checks for fail-closed PBS URI packet reconciliation."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from global_medicines_atlas.pbs_uri_review_packet_reconciler import (
    PACKET_FILENAME,
    ReconciliationError,
    reconcile_uri_review_packet,
    write_new_envelope,
)

ROOT = Path(__file__).parents[1]
PACKET = ROOT / "quality/qualifications" / PACKET_FILENAME
RUN_ID = "40199999999"
COMMIT = "a" * 40
PINNED_V1_URI_RECEIPT_SHA256 = (
    "ac53a6d8fc79f8491d261d4e8bd552daa4e7d58c4ecd51ee780dbaf72d16e583"
)


def _seal(report: dict[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256(
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    return {"report": report, "report_sha256": digest}


def _inputs(tmp_path: Path) -> tuple[Path, Path, str, dict[str, Any]]:
    packet_path = tmp_path / PACKET_FILENAME
    shutil.copyfile(PACKET, packet_path)
    packet = json.loads(packet_path.read_text())["report"]
    uri_rows = [
        {
            "case_id": case["case_id"],
            "reference_occurrence_sha256": hashlib.sha256(
                case["reference_occurrence"].encode()
            ).hexdigest(),
            "reference_kind": case["kind"],
            "structural_role": "xlink_href_attribute"
            if case["kind"] == "xlink_href"
            else "rdf_resource_attribute",
            "reference_element_qname": "pbs:administrative-advice-reference",
            "uri_resolution": "same_member_unique_id"
            if case["kind"] == "xlink_href"
            else "absolute_uri_unique_candidate",
            "target_element_qname": "pbs:administrative-advice",
            "target_occurrence_sha256": "b" * 64,
            "semantic_review_state": "pending",
            "adjudication": "unreviewed",
            "semantic_relationship_qualified": False,
        }
        for case in packet["cases"]
    ]
    report = {
        "status": "passed",
        "operation": "pbs-native-uri-screen",
        "workflow_commit": COMMIT,
        "run_id": RUN_ID,
        "schema_id": "global-medicines-atlas.pbs-native-uri-screen",
        "schema_version": 2,
        "dataset": "edithatogo/australian-pbs-source-archive",
        "revision": "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7",
        "member_path": "sch-2026-04-01-r1.xml",
        "member_sha256": "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43",
        "member_size_bytes": 313_437_585,
        "uri_resolution_performed": True,
        "semantic_relationships_qualified": False,
        "source_values_emitted": False,
        "publication_performed": False,
        "external_targets_fetched": 0,
        "admissions_created": 0,
        "canaries_performed": 0,
        "new_sources_added": 0,
        "review_packet_binding": {
            "packet_file": PACKET_FILENAME,
            "packet_file_sha256": hashlib.sha256(
                packet_path.read_bytes()
            ).hexdigest(),
            "packet_screen_run_id": packet["source"]["screen_run_id"],
            "packet_screen_receipt_sha256": packet["source"][
                "screen_receipt_sha256"
            ],
            "packet_case_count": 46,
            "packet_cases_reviewed": 0,
        },
        "qualification": {
            "schema_id": "global-medicines-atlas.pbs-native-uri-screen",
            "schema_version": 2,
            "uri_resolution_performed": True,
            "review_case_count": 46,
            "review_cases_adjudicated": 0,
            "semantic_relationships_qualified": False,
            "review_case_sampling_is_probability_based": False,
            "uri_values_emitted": False,
            "literal_values_emitted": False,
            "payload_emitted": False,
            "external_targets_fetched": 0,
            "precision_claimed": False,
            "review_case_uri_bindings": uri_rows,
        },
    }
    uri_path = tmp_path / "uri-receipt.json"
    uri_path.write_text(
        json.dumps(_seal(report), sort_keys=True, indent=2) + "\n"
    )
    return (
        packet_path,
        uri_path,
        hashlib.sha256(uri_path.read_bytes()).hexdigest(),
        report,
    )


def _reconcile(
    inputs: tuple[Path, Path, str, dict[str, Any]],
) -> dict[str, Any]:
    packet, receipt, digest, _ = inputs
    return reconcile_uri_review_packet(
        packet,
        receipt,
        expected_run_id=RUN_ID,
        expected_commit=COMMIT,
        expected_uri_receipt_sha256=digest,
    )


def test_reconciles_all_cases_to_value_free_pending_structural_packet(
    tmp_path: Path,
):
    inputs = _inputs(tmp_path)
    envelope = _reconcile(inputs)
    report = envelope["report"]
    assert report["case_count"] == 46
    assert report["uri_run_id"] == RUN_ID
    assert report["uri_workflow_commit"] == COMMIT
    assert report["semantic_relationships_qualified"] is False
    assert report["edges_emitted"] is False
    assert report["precision_claimed"] is report["recall_claimed"] is False
    assert all(
        case["semantic_review_state"] == "pending" for case in report["cases"]
    )
    assert all(case["adjudication"] == "unreviewed" for case in report["cases"])
    assert all(
        case["semantic_relationship_qualified"] is False
        for case in report["cases"]
    )
    assert all(
        case["target_type_meaning"] == "not_established"
        for case in report["cases"]
    )
    assert all(case["edges_emitted"] is False for case in report["cases"])
    assert "synthetic.example" not in json.dumps(envelope)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", 1, "URI screen schema version"),
        ("status", "failed", "URI screen status"),
        ("operation", "other", "URI screen operation"),
        ("workflow_commit", "c" * 40, "URI workflow commit"),
        ("run_id", "17", "URI run ID"),
        ("member_path", "other.xml", "URI member path"),
        ("member_sha256", "d" * 64, "URI member digest"),
        ("member_size_bytes", 1, "URI member size"),
        ("uri_resolution_performed", False, "URI resolution state"),
        ("semantic_relationships_qualified", True, "URI semantic state"),
    ],
)
def test_rejects_receipt_contract_mismatch(
    tmp_path: Path, field: str, value: Any, message: str
):
    inputs = _inputs(tmp_path)
    packet, receipt, _, report = inputs
    report[field] = value
    receipt.write_text(
        json.dumps(_seal(report), sort_keys=True, indent=2) + "\n"
    )
    with pytest.raises(ReconciliationError, match=message):
        reconcile_uri_review_packet(
            packet,
            receipt,
            expected_run_id=RUN_ID,
            expected_commit=COMMIT,
            expected_uri_receipt_sha256=hashlib.sha256(
                receipt.read_bytes()
            ).hexdigest(),
        )


def test_rejects_current_pinned_v1_actions_receipt(tmp_path: Path):
    packet, _, _, _ = _inputs(tmp_path)
    receipt = (
        ROOT
        / "quality/qualifications/pbs-native-reference-uri-screen-20261025-40110616327.json"
    )
    assert (
        hashlib.sha256(receipt.read_bytes()).hexdigest()
        == PINNED_V1_URI_RECEIPT_SHA256
    )
    with pytest.raises(ReconciliationError, match="URI screen schema version"):
        reconcile_uri_review_packet(
            packet,
            receipt,
            expected_run_id="40110616327",
            expected_commit="e5145eca0698bbc275c3497431ba0f179261e458",
            expected_uri_receipt_sha256=PINNED_V1_URI_RECEIPT_SHA256,
        )


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "extra", "occurrence", "escalation"]
)
def test_rejects_non_bijective_or_escalated_case_binding(
    tmp_path: Path, mutation: str
):
    packet, receipt, _, report = _inputs(tmp_path)
    rows = report["qualification"]["review_case_uri_bindings"]
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[-1] = dict(rows[0])
    elif mutation == "extra":
        rows[-1]["case_id"] = "f" * 64
    elif mutation == "occurrence":
        rows[0]["reference_occurrence_sha256"] = "0" * 64
    else:
        rows[0]["semantic_relationship_qualified"] = True
    receipt.write_text(
        json.dumps(_seal(report), sort_keys=True, indent=2) + "\n"
    )
    with pytest.raises(ReconciliationError):
        reconcile_uri_review_packet(
            packet,
            receipt,
            expected_run_id=RUN_ID,
            expected_commit=COMMIT,
            expected_uri_receipt_sha256=hashlib.sha256(
                receipt.read_bytes()
            ).hexdigest(),
        )


def test_rejects_bad_canonical_digest_and_wrong_expected_receipt_bytes(
    tmp_path: Path,
):
    packet, receipt, _, _ = _inputs(tmp_path)
    envelope = json.loads(receipt.read_text())
    envelope["report"]["run_id"] = "7"
    receipt.write_text(json.dumps(envelope))
    with pytest.raises(
        ReconciliationError, match="canonical report digest differs"
    ):
        reconcile_uri_review_packet(
            packet,
            receipt,
            expected_run_id=RUN_ID,
            expected_commit=COMMIT,
            expected_uri_receipt_sha256=hashlib.sha256(
                receipt.read_bytes()
            ).hexdigest(),
        )
    envelope["report_sha256"] = hashlib.sha256(
        json.dumps(
            envelope["report"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    receipt.write_text(json.dumps(envelope))
    with pytest.raises(ReconciliationError, match="URI receipt bytes digest"):
        reconcile_uri_review_packet(
            packet,
            receipt,
            expected_run_id=RUN_ID,
            expected_commit=COMMIT,
            expected_uri_receipt_sha256="0" * 64,
        )


def test_rejects_packet_bytes_that_differ_from_pinned_identity(tmp_path: Path):
    packet, receipt, digest, _ = _inputs(tmp_path)
    packet.write_bytes(packet.read_bytes() + b" ")
    with pytest.raises(ReconciliationError, match="packet bytes digest"):
        reconcile_uri_review_packet(
            packet,
            receipt,
            expected_run_id=RUN_ID,
            expected_commit=COMMIT,
            expected_uri_receipt_sha256=digest,
        )


def test_never_overwrites_existing_derived_packet(tmp_path: Path):
    target = tmp_path / "derived.json"
    target.write_text("keep")
    with pytest.raises(ReconciliationError, match="existing output"):
        write_new_envelope({"report": {}, "report_sha256": "0" * 64}, target)
    assert target.read_text() == "keep"
