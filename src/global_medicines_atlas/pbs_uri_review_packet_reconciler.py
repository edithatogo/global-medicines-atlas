"""Reconcile a pinned PBS review packet with one v2 URI-screen receipt.

This produces value-free structural diagnostics only. It does not adjudicate
predicate meaning, qualify relationships, or estimate matcher performance.
"""

# These boolean arguments are expected receipt values compared by equality, not
# control flags; the finite fail-closed contract is intentionally kept together.
# ruff: file-ignore[boolean-positional-value-in-call]

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

PACKET_FILENAME = "pbs-native-reference-review-packet-20261025-40103169910.json"
PACKET_SHA256 = (
    "c38840116e821dffe5b06e5df14b1d7140f9e4446fbf8c14ea009a9e8b732829"
)
PACKET_REPORT_SHA256 = (
    "885960352dcee9e70f12ac3aa843d5129b75a2c44b16263835ff5bc7b57a5c6b"
)
PACKET_SCHEMA_ID = "global-medicines-atlas.pbs-reference-review-packet"
PACKET_CASE_COUNT = 46
URI_SCHEMA_ID = "global-medicines-atlas.pbs-native-uri-screen"
URI_SCHEMA_VERSION = 2
URI_OPERATION = "pbs-native-uri-screen"
URI_OUTCOMES = frozenset({
    "absolute_uri_ambiguous_candidate",
    "absolute_uri_no_member_definition",
    "absolute_uri_unique_candidate",
    "abstained_malformed_fragment",
    "abstained_xml_base_override",
    "ambiguous_id_target",
    "external_or_nonfragment_xlink_unresolved",
    "missing_id_target",
    "same_member_unique_id",
    "unresolved_invalid_uri",
    "unresolved_unknown_base",
})
DATASET = "edithatogo/australian-pbs-source-archive"
REVISION = "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7"
MEMBER_PATH = "sch-2026-04-01-r1.xml"
MEMBER_SHA256 = (
    "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
)
MEMBER_SIZE_BYTES = 313_437_585
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_QNAME = re.compile(
    r"(?:pbs|pbsdata|pbsext|skos|rdf):[A-Za-z_][A-Za-z0-9_.-]*\Z"
)


class ReconciliationError(ValueError):
    """A fixed, value-free validation error."""


def _canonical_report_digest(report: Any) -> str:
    try:
        encoded = json.dumps(
            report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReconciliationError("report is not canonical JSON data") from exc
    return hashlib.sha256(encoded).hexdigest()


def _load_envelope(path: Path) -> tuple[dict[str, Any], bytes, str]:
    try:
        raw = path.read_bytes()
        parsed: Any = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReconciliationError("input envelope cannot be read") from exc
    if not isinstance(parsed, dict):
        raise ReconciliationError("input envelope shape is invalid")
    envelope = cast("dict[str, Any]", parsed)
    report_value = envelope.get("report")
    if not isinstance(report_value, dict):
        raise ReconciliationError("input envelope shape is invalid")
    report = cast("dict[str, Any]", report_value)
    digest = envelope.get("report_sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ReconciliationError("canonical report digest is missing")
    if _canonical_report_digest(report) != digest:
        raise ReconciliationError("canonical report digest differs")
    return envelope, raw, hashlib.sha256(raw).hexdigest()


def _required(mapping: Any, key: str, value: Any, label: str) -> None:
    if not isinstance(mapping, dict):
        raise ReconciliationError(f"{label} does not match the pinned contract")
    mapping = cast("dict[str, Any]", mapping)
    if mapping.get(key) != value:
        raise ReconciliationError(f"{label} does not match the pinned contract")


def reconcile_uri_review_packet(  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements] -- keep exact receipt gates auditable together
    packet_path: Path,
    uri_receipt_path: Path,
    *,
    expected_run_id: str,
    expected_commit: str,
    expected_uri_receipt_sha256: str,
) -> dict[str, Any]:
    """Build a derived packet only after exact identity and case binding pass."""
    if packet_path.name != PACKET_FILENAME:
        raise ReconciliationError("packet filename is not the pinned packet")
    packet_envelope, _packet_bytes, packet_file_sha = _load_envelope(
        packet_path
    )
    _required(
        {"sha256": packet_file_sha},
        "sha256",
        PACKET_SHA256,
        "packet bytes digest",
    )
    _required(
        packet_envelope,
        "report_sha256",
        PACKET_REPORT_SHA256,
        "packet canonical report digest",
    )
    packet = packet_envelope["report"]
    _required(packet, "schema_id", PACKET_SCHEMA_ID, "packet schema")
    _required(packet, "schema_version", 1, "packet schema version")
    _required(
        packet,
        "status",
        "source_context_examples_unreviewed_semantic_links_unqualified",
        "packet status",
    )
    if not expected_run_id.isdecimal():
        raise ReconciliationError("expected run ID is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise ReconciliationError("expected commit is invalid")
    if not _SHA256.fullmatch(expected_uri_receipt_sha256):
        raise ReconciliationError("expected URI receipt digest is invalid")

    cases = packet.get("cases")
    if not isinstance(cases, list):
        raise ReconciliationError("pinned packet case count differs")
    packet_cases = cast("list[Any]", cases)
    if len(packet_cases) != PACKET_CASE_COUNT:
        raise ReconciliationError("pinned packet case count differs")
    _required(
        packet.get("scope", {}),
        "semantic_relationships_qualified",
        False,
        "packet semantic state",
    )
    _required(
        packet.get("calibration", {}),
        "semantic_relationships_qualified",
        False,
        "packet calibration state",
    )
    _required(
        packet,
        "sampling_method",
        "deterministic source-order examples within context strata; not a probability sample",
        "packet sampling method",
    )

    uri_envelope, _uri_bytes, uri_file_sha = _load_envelope(uri_receipt_path)
    _required(
        {"sha256": uri_file_sha},
        "sha256",
        expected_uri_receipt_sha256,
        "URI receipt bytes digest",
    )
    uri = uri_envelope["report"]
    _required(uri, "status", "passed", "URI screen status")
    _required(uri, "operation", URI_OPERATION, "URI screen operation")
    _required(uri, "workflow_commit", expected_commit, "URI workflow commit")
    _required(uri, "run_id", expected_run_id, "URI run ID")
    _required(uri, "schema_id", URI_SCHEMA_ID, "URI screen schema")
    _required(
        uri, "schema_version", URI_SCHEMA_VERSION, "URI screen schema version"
    )
    _required(uri, "dataset", DATASET, "URI dataset")
    _required(uri, "revision", REVISION, "URI source revision")
    _required(uri, "member_path", MEMBER_PATH, "URI member path")
    _required(uri, "member_sha256", MEMBER_SHA256, "URI member digest")
    _required(uri, "member_size_bytes", MEMBER_SIZE_BYTES, "URI member size")
    _required(uri, "uri_resolution_performed", True, "URI resolution state")
    _required(
        uri,
        "semantic_relationships_qualified",
        False,
        "URI semantic state",
    )
    _required(uri, "source_values_emitted", False, "URI value boundary")
    _required(uri, "publication_performed", False, "URI publication boundary")
    _required(uri, "new_sources_added", 0, "URI source boundary")
    _required(uri, "external_targets_fetched", 0, "URI external fetch boundary")
    _required(uri, "admissions_created", 0, "URI admission boundary")
    _required(uri, "canaries_performed", 0, "URI canary boundary")

    binding = uri.get("review_packet_binding")
    qualification = uri.get("qualification")
    if not isinstance(binding, dict) or not isinstance(qualification, dict):
        raise ReconciliationError("URI case binding is missing")
    binding = cast("dict[str, Any]", binding)
    qualification = cast("dict[str, Any]", qualification)
    _required(
        qualification, "schema_id", URI_SCHEMA_ID, "URI qualification schema"
    )
    _required(
        qualification,
        "schema_version",
        URI_SCHEMA_VERSION,
        "URI qualification schema version",
    )
    _required(
        qualification,
        "uri_resolution_performed",
        True,
        "URI qualification resolution state",
    )
    _required(
        qualification,
        "semantic_relationships_qualified",
        False,
        "URI qualification semantic state",
    )
    _required(qualification, "uri_values_emitted", False, "URI value boundary")
    _required(
        qualification, "literal_values_emitted", False, "URI literal boundary"
    )
    _required(qualification, "payload_emitted", False, "URI payload boundary")
    _required(
        qualification,
        "external_targets_fetched",
        0,
        "URI external fetch boundary",
    )
    _required(
        qualification, "precision_claimed", False, "URI precision boundary"
    )
    _required(binding, "packet_file", PACKET_FILENAME, "URI packet filename")
    _required(
        binding, "packet_file_sha256", PACKET_SHA256, "URI packet bytes digest"
    )
    _required(
        binding, "packet_case_count", PACKET_CASE_COUNT, "URI packet case count"
    )
    _required(binding, "packet_cases_reviewed", 0, "URI reviewed case count")
    packet_source = packet.get("source")
    if not isinstance(packet_source, dict):
        raise ReconciliationError("pinned packet source binding is missing")
    packet_source = cast("dict[str, Any]", packet_source)
    _required(
        binding,
        "packet_screen_run_id",
        packet_source.get("screen_run_id"),
        "URI packet source run binding",
    )
    _required(
        binding,
        "packet_screen_receipt_sha256",
        packet_source.get("screen_receipt_sha256"),
        "URI packet source receipt binding",
    )
    _required(
        qualification,
        "review_case_count",
        PACKET_CASE_COUNT,
        "URI qualification case count",
    )
    _required(
        qualification,
        "review_cases_adjudicated",
        0,
        "URI adjudicated case count",
    )
    _required(
        qualification,
        "review_case_sampling_is_probability_based",
        False,
        "URI sampling state",
    )
    uri_cases = qualification.get("review_case_uri_bindings")
    if not isinstance(uri_cases, list):
        raise ReconciliationError("URI case binding count differs")
    uri_case_rows = cast("list[Any]", uri_cases)
    if len(uri_case_rows) != PACKET_CASE_COUNT:
        raise ReconciliationError("URI case binding count differs")

    original_by_id: dict[str, dict[str, Any]] = {}
    for case_value in packet_cases:
        if not isinstance(case_value, dict):
            raise ReconciliationError("packet case shape is invalid")
        case = cast("dict[str, Any]", case_value)
        case_id = case.get("case_id")
        occurrence = case.get("reference_occurrence")
        if not isinstance(case_id, str) or not _SHA256.fullmatch(case_id):
            raise ReconciliationError("packet case identity is invalid")
        if case_id in original_by_id or not isinstance(occurrence, str):
            raise ReconciliationError(
                "packet case identity is duplicated or incomplete"
            )
        if case.get("semantic_relationship_qualified") is not False:
            raise ReconciliationError("packet semantic state is escalated")
        if case.get("target_type_meaning") != "not_established":
            raise ReconciliationError("packet target meaning is not unresolved")
        if case.get("adjudication") != "unreviewed":
            raise ReconciliationError("packet case is not unreviewed")
        original_by_id[case_id] = case

    uri_by_id: dict[str, dict[str, Any]] = {}
    for row_value in uri_case_rows:
        if not isinstance(row_value, dict):
            raise ReconciliationError("URI case binding shape is invalid")
        row = cast("dict[str, Any]", row_value)
        case_id = row.get("case_id")
        occurrence_hash = row.get("reference_occurrence_sha256")
        if not isinstance(case_id, str) or case_id in uri_by_id:
            raise ReconciliationError(
                "URI case identity is duplicated or invalid"
            )
        if not isinstance(occurrence_hash, str) or not _SHA256.fullmatch(
            occurrence_hash
        ):
            raise ReconciliationError("URI occurrence digest is invalid")
        original = original_by_id.get(case_id)
        if original is None:
            raise ReconciliationError(
                "URI case is not present in the pinned packet"
            )
        if (
            hashlib.sha256(
                original["reference_occurrence"].encode()
            ).hexdigest()
            != occurrence_hash
        ):
            raise ReconciliationError("URI occurrence binding differs")
        _required(row, "semantic_review_state", "pending", "URI review state")
        _required(row, "adjudication", "unreviewed", "URI adjudication")
        _required(
            row,
            "semantic_relationship_qualified",
            False,
            "URI case semantic state",
        )
        if row.get("reference_kind") not in {"rdf_resource", "xlink_href"}:
            raise ReconciliationError("URI reference kind is invalid")
        if row.get("reference_kind") != original.get("kind"):
            raise ReconciliationError("URI reference kind differs from packet")
        if row.get("structural_role") not in {
            "rdf_resource_attribute",
            "xlink_href_attribute",
        }:
            raise ReconciliationError("URI structural role is invalid")
        expected_role = (
            "xlink_href_attribute"
            if original["kind"] == "xlink_href"
            else "rdf_resource_attribute"
        )
        if row.get("structural_role") != expected_role:
            raise ReconciliationError("URI structural role differs from packet")
        reference_qname = row.get("reference_element_qname")
        if reference_qname != "other_or_unresolved" and (
            not isinstance(reference_qname, str)
            or not _QNAME.fullmatch(reference_qname)
        ):
            raise ReconciliationError("URI reference QName is missing")
        if row.get("uri_resolution") not in URI_OUTCOMES:
            raise ReconciliationError("URI resolution outcome is missing")
        target_hash = row.get("target_occurrence_sha256")
        if target_hash is not None and (
            not isinstance(target_hash, str)
            or not _SHA256.fullmatch(target_hash)
        ):
            raise ReconciliationError("URI target occurrence digest is invalid")
        target_qname = row.get("target_element_qname")
        if (
            target_qname is not None
            and target_qname != "other_or_unresolved"
            and (
                not isinstance(target_qname, str)
                or not _QNAME.fullmatch(target_qname)
            )
        ):
            raise ReconciliationError("URI target QName is invalid")
        if (target_hash is None) != (row.get("target_element_qname") is None):
            raise ReconciliationError("URI target identity is incomplete")
        uri_by_id[case_id] = row
    if uri_by_id.keys() != original_by_id.keys():
        raise ReconciliationError(
            "packet and URI case identities are not one-to-one"
        )

    derived_cases: list[dict[str, Any]] = []
    for case_value in packet_cases:
        case = cast("dict[str, Any]", case_value)
        row = uri_by_id[case["case_id"]]
        derived = dict(case)
        derived.update({
            "reference_occurrence_sha256": row["reference_occurrence_sha256"],
            "reference_kind": row.get("reference_kind"),
            "structural_role": row.get("structural_role"),
            "reference_element_qname": row.get("reference_element_qname"),
            "uri_resolution": row.get("uri_resolution"),
            "target_element_qname": row.get("target_element_qname"),
            "target_occurrence_sha256": row.get("target_occurrence_sha256"),
            "semantic_review_state": "pending",
            "adjudication": "unreviewed",
            "semantic_relationship_qualified": False,
            "target_type_meaning": "not_established",
            "edges_emitted": False,
        })
        derived_cases.append(derived)
    report = {
        "schema_id": "global-medicines-atlas.pbs-uri-reference-review-packet",
        "schema_version": 1,
        "status": "structural_uri_diagnostics_unreviewed_semantics_unqualified",
        "source_packet_sha256": packet_file_sha,
        "source_packet_report_sha256": packet_envelope["report_sha256"],
        "uri_receipt_sha256": uri_file_sha,
        "uri_receipt_report_sha256": uri_envelope["report_sha256"],
        "uri_run_id": expected_run_id,
        "uri_workflow_commit": expected_commit,
        "dataset": DATASET,
        "revision": REVISION,
        "member_path": MEMBER_PATH,
        "member_sha256": MEMBER_SHA256,
        "member_size_bytes": MEMBER_SIZE_BYTES,
        "case_count": len(derived_cases),
        "sampling_method": packet["sampling_method"],
        "sampling_is_probability_based": False,
        "semantic_relationships_qualified": False,
        "source_values_emitted": False,
        "edges_emitted": False,
        "precision_claimed": False,
        "recall_claimed": False,
        "target_type_meaning": "not_established",
        "cases": derived_cases,
    }
    return {"report": report, "report_sha256": _canonical_report_digest(report)}


def write_new_envelope(envelope: dict[str, Any], output: Path) -> None:
    """Write atomically without replacing any existing evidence file."""
    output.parent.mkdir(parents=True, exist_ok=True)
    data = (
        json.dumps(envelope, sort_keys=True, indent=2, ensure_ascii=False)
        + "\n"
    )
    try:
        with output.open("x", encoding="utf-8") as stream:
            stream.write(data)
    except FileExistsError as exc:
        raise ReconciliationError("existing output must be preserved") from exc
