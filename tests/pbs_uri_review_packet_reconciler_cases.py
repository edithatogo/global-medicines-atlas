"""Synthetic contract checks for fail-closed PBS URI packet reconciliation."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from global_medicines_atlas import (
    pbs_uri_review_packet_reconciler as uri_reconciler,
)
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


def _refresh_uri_receipt(
    inputs: tuple[Path, Path, str, dict[str, Any]],
) -> tuple[Path, Path, str, dict[str, Any]]:
    packet, receipt, _, report = inputs
    receipt.write_text(
        json.dumps(_seal(report), sort_keys=True, indent=2) + "\n"
    )
    return (
        packet,
        receipt,
        hashlib.sha256(receipt.read_bytes()).hexdigest(),
        report,
    )


def _mutate_pinned_packet(
    inputs: tuple[Path, Path, str, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> tuple[Path, Path, str, dict[str, Any]]:
    packet_path, receipt_path, _, uri_report = inputs
    envelope = json.loads(packet_path.read_text())
    packet = envelope["report"]
    cases = packet["cases"]
    if mutation == "not_list":
        packet["cases"] = None
    elif mutation == "wrong_count":
        packet["cases"] = cases[:-1]
    elif mutation == "not_mapping":
        cases[0] = None
    elif mutation == "invalid_id":
        cases[0]["case_id"] = "bad"
    elif mutation == "duplicate_id":
        cases[1]["case_id"] = cases[0]["case_id"]
    elif mutation == "missing_occurrence":
        cases[0].pop("reference_occurrence")
    elif mutation == "semantic_escalation":
        cases[0]["semantic_relationship_qualified"] = True
    elif mutation == "target_meaning":
        cases[0]["target_type_meaning"] = "medicine"
    elif mutation == "adjudication":
        cases[0]["adjudication"] = "accepted"
    elif mutation == "missing_source":
        packet.pop("source")
    sealed = _seal(packet)
    packet_path.write_text(json.dumps(sealed, sort_keys=True, indent=2) + "\n")
    packet_digest = hashlib.sha256(packet_path.read_bytes()).hexdigest()
    monkeypatch.setattr(uri_reconciler, "PACKET_SHA256", packet_digest)
    monkeypatch.setattr(
        uri_reconciler, "PACKET_REPORT_SHA256", sealed["report_sha256"]
    )
    binding = uri_report["review_packet_binding"]
    binding["packet_file_sha256"] = packet_digest
    uri_report = _seal(uri_report)["report"]
    inputs = (packet_path, receipt_path, inputs[2], uri_report)
    return _refresh_uri_receipt(inputs)


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


def test_writes_new_derived_packet(tmp_path: Path):
    target = tmp_path / "nested" / "derived.json"
    envelope = _seal({"status": "value_free"})
    write_new_envelope(envelope, target)
    assert json.loads(target.read_text()) == envelope


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not-json", "input envelope cannot be read"),
        ("[]", "input envelope shape is invalid"),
        ('{"report": []}', "input envelope shape is invalid"),
        (
            '{"report": {}, "report_sha256": "bad"}',
            "canonical report digest is missing",
        ),
    ],
)
def test_load_envelope_rejects_malformed_inputs(
    tmp_path: Path, payload: str, message: str
):
    path = tmp_path / "envelope.json"
    path.write_text(payload)
    with pytest.raises(ReconciliationError, match=message):
        uri_reconciler._load_envelope(path)  # pyright: ignore[reportPrivateUsage]


def test_load_envelope_rejects_missing_file(tmp_path: Path):
    with pytest.raises(
        ReconciliationError, match="input envelope cannot be read"
    ):
        uri_reconciler._load_envelope(  # pyright: ignore[reportPrivateUsage]
            tmp_path / "missing.json"
        )


def test_report_digest_rejects_non_json_value():
    with pytest.raises(ReconciliationError, match="not canonical JSON data"):
        uri_reconciler._canonical_report_digest(  # pyright: ignore[reportPrivateUsage]
            {"bad": object()}
        )


@pytest.mark.parametrize(
    ("mapping", "key", "value", "message"),
    [
        (None, "status", "passed", "status does not match"),
        ({}, "status", "passed", "status does not match"),
    ],
)
def test_required_rejects_invalid_mapping(
    mapping: Any, key: str, value: Any, message: str
):
    with pytest.raises(ReconciliationError, match=message):
        uri_reconciler._required(  # pyright: ignore[reportPrivateUsage]
            mapping, key, value, "status"
        )


@pytest.mark.parametrize(
    ("argument", "message"),
    [
        ("run", "expected run ID is invalid"),
        ("commit", "expected commit is invalid"),
        ("digest", "expected URI receipt digest is invalid"),
    ],
)
def test_rejects_invalid_expected_arguments(
    tmp_path: Path, argument: str, message: str
):
    inputs = _inputs(tmp_path)
    packet, receipt, digest, _ = inputs
    kwargs: dict[str, str] = {
        "expected_run_id": RUN_ID,
        "expected_commit": COMMIT,
        "expected_uri_receipt_sha256": digest,
    }
    if argument == "run":
        kwargs["expected_run_id"] = "not-a-run"
    elif argument == "commit":
        kwargs["expected_commit"] = "bad"
    else:
        kwargs["expected_uri_receipt_sha256"] = "bad"
    with pytest.raises(ReconciliationError, match=message):
        reconcile_uri_review_packet(packet, receipt, **kwargs)


def test_rejects_wrong_packet_filename(tmp_path: Path):
    inputs = _inputs(tmp_path)
    packet, receipt, digest, _ = inputs
    wrong_name = tmp_path / "other-packet.json"
    shutil.copyfile(packet, wrong_name)
    with pytest.raises(ReconciliationError, match="packet filename"):
        reconcile_uri_review_packet(
            wrong_name,
            receipt,
            expected_run_id=RUN_ID,
            expected_commit=COMMIT,
            expected_uri_receipt_sha256=digest,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("not_list", "packet case count differs"),
        ("wrong_count", "packet case count differs"),
        ("not_mapping", "packet case shape is invalid"),
        ("invalid_id", "packet case identity is invalid"),
        ("duplicate_id", "packet case identity is duplicated"),
        ("missing_occurrence", "packet case identity is duplicated"),
        ("semantic_escalation", "packet semantic state is escalated"),
        ("target_meaning", "packet target meaning is not unresolved"),
        ("adjudication", "packet case is not unreviewed"),
        ("missing_source", "pinned packet source binding is missing"),
    ],
)
def test_rejects_invalid_pinned_packet_cases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
):
    inputs = _mutate_pinned_packet(_inputs(tmp_path), monkeypatch, mutation)
    packet, receipt, digest, _ = inputs
    with pytest.raises(ReconciliationError, match=message):
        reconcile_uri_review_packet(
            packet,
            receipt,
            expected_run_id=RUN_ID,
            expected_commit=COMMIT,
            expected_uri_receipt_sha256=digest,
        )


@pytest.mark.parametrize(
    ("location", "mutation", "message"),
    [
        ("binding", "missing", "URI case binding is missing"),
        ("binding", "not_mapping", "URI case binding is missing"),
        ("qualification", "missing", "URI case binding is missing"),
        ("qualification", "not_mapping", "URI case binding is missing"),
        ("rows", "not_list", "URI case binding count differs"),
        ("rows", "wrong_count", "URI case binding count differs"),
    ],
)
def test_rejects_missing_uri_case_binding_structures(
    tmp_path: Path,
    location: str,
    mutation: str,
    message: str,
):
    inputs = _inputs(tmp_path)
    packet, receipt, _, report = inputs
    if location == "binding":
        if mutation == "missing":
            report.pop("review_packet_binding")
        else:
            report["review_packet_binding"] = None
    elif location == "qualification":
        if mutation == "missing":
            report.pop("qualification")
        else:
            report["qualification"] = None
    elif mutation == "not_list":
        report["qualification"]["review_case_uri_bindings"] = None
    else:
        report["qualification"]["review_case_uri_bindings"].pop()
    refreshed = _refresh_uri_receipt((packet, receipt, inputs[2], report))
    packet, receipt, digest, _ = refreshed
    with pytest.raises(ReconciliationError, match=message):
        reconcile_uri_review_packet(
            packet,
            receipt,
            expected_run_id=RUN_ID,
            expected_commit=COMMIT,
            expected_uri_receipt_sha256=digest,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("not_mapping", "URI case binding shape is invalid"),
        ("invalid_occurrence_hash", "URI occurrence digest is invalid"),
        ("unsupported_kind", "URI reference kind is invalid"),
        ("mismatched_kind", "URI reference kind differs from packet"),
        ("unsupported_role", "URI structural role is invalid"),
        ("mismatched_role", "URI structural role differs from packet"),
        ("invalid_reference_qname", "URI reference QName is missing"),
        ("invalid_resolution", "URI resolution outcome is missing"),
        ("invalid_target_hash", "URI target occurrence digest is invalid"),
        ("invalid_target_qname", "URI target QName is invalid"),
        ("incomplete_target", "URI target identity is incomplete"),
    ],
)
def test_rejects_invalid_uri_case_rows(
    tmp_path: Path,
    mutation: str,
    message: str,
):
    inputs = _inputs(tmp_path)
    packet, receipt, _, report = inputs
    rows = report["qualification"]["review_case_uri_bindings"]
    if mutation == "not_mapping":
        rows[0] = None
    elif mutation == "invalid_occurrence_hash":
        rows[0]["reference_occurrence_sha256"] = "bad"
    elif mutation == "unsupported_kind":
        rows[0]["reference_kind"] = "other"
    elif mutation == "mismatched_kind":
        rows[0]["reference_kind"] = (
            "xlink_href"
            if rows[0]["reference_kind"] == "rdf_resource"
            else "rdf_resource"
        )
    elif mutation == "unsupported_role":
        rows[0]["structural_role"] = "other"
    elif mutation == "mismatched_role":
        rows[0]["structural_role"] = (
            "xlink_href_attribute"
            if rows[0]["structural_role"] == "rdf_resource_attribute"
            else "rdf_resource_attribute"
        )
    elif mutation == "invalid_reference_qname":
        rows[0]["reference_element_qname"] = "invalid qname"
    elif mutation == "invalid_resolution":
        rows[0]["uri_resolution"] = "not-a-resolution"
    elif mutation == "invalid_target_hash":
        rows[0]["target_occurrence_sha256"] = "bad"
    elif mutation == "invalid_target_qname":
        rows[0]["target_element_qname"] = "invalid qname"
    else:
        rows[0]["target_element_qname"] = None
    refreshed = _refresh_uri_receipt((packet, receipt, inputs[2], report))
    packet, receipt, digest, _ = refreshed
    with pytest.raises(ReconciliationError, match=message):
        reconcile_uri_review_packet(
            packet,
            receipt,
            expected_run_id=RUN_ID,
            expected_commit=COMMIT,
            expected_uri_receipt_sha256=digest,
        )
