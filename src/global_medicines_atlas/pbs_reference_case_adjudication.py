"""Build and validate a value-free PBS reference case review receipt.

This receipt accepts only the structural pointer attribute role and the exact
member-scoped resolution outcome already bound by the retained URI packet. It
abstains from semantic relationship qualification for every case.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

PACKET_PATH = (
    "quality/qualifications/"
    "pbs-native-reference-review-packet-20261025-40103169910.json"
)
URI_RECONCILIATION_PATH = (
    "quality/qualifications/"
    "pbs-native-reference-uri-review-reconciliation-20261025-40120162365.json"
)
ADJUDICATION_PATH = (
    "quality/qualifications/"
    "pbs-native-reference-case-adjudication-20261025-v1.json"
)
DATASET = "edithatogo/australian-pbs-source-archive"
REVISION = "31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7"
MEMBER_PATH = "sch-2026-04-01-r1.xml"
MEMBER_SHA256 = (
    "73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43"
)
CASE_COUNT = 46
PACKET_FILE_SHA256 = (
    "c38840116e821dffe5b06e5df14b1d7140f9e4446fbf8c14ea009a9e8b732829"
)
PACKET_REPORT_SHA256 = (
    "885960352dcee9e70f12ac3aa843d5129b75a2c44b16263835ff5bc7b57a5c6b"
)
URI_RECONCILIATION_FILE_SHA256 = (
    "3698d217957c4d3263fce010d8ed6441c2050866052e1308fa352c6cd22772bb"
)
URI_RECONCILIATION_REPORT_SHA256 = (
    "31e22bbda75bb7da755af0d09ed29c93477a9da08a5c50ed499dc6bc23dcd4fa"
)
NO_TARGET_CATEGORY = "no_target_negative_control"
_FORBIDDEN_KEYS = {
    "literal",
    "value",
    "uri",
    "reference_value",
    "raw_source",
}
_POINTER_ROLES = {"rdf_resource_attribute", "xlink_href_attribute"}
_NO_TARGET_RESOLUTION = "absolute_uri_no_member_definition"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha256(value: dict[str, Any]) -> str:
    return _sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    )


def _read_envelope(
    root: Path, relative_path: str
) -> tuple[bytes, dict[str, Any]]:
    raw = (root / relative_path).read_bytes()
    decoded: object = json.loads(raw)
    if not isinstance(decoded, dict):
        raise TypeError(f"{relative_path} envelope is not an object")
    envelope = cast("dict[str, Any]", decoded)
    report_value = envelope.get("report")
    if not isinstance(report_value, dict):
        raise TypeError(f"{relative_path} report is not an object")
    report = cast("dict[str, Any]", report_value)
    if envelope.get("report_sha256") != _canonical_sha256(report):
        raise ValueError(f"{relative_path} report digest differs")
    return raw, envelope


def _validate_no_source_values(value: object) -> None:
    if isinstance(value, dict):
        members = cast("dict[object, object]", value)
        if any(
            isinstance(key, str) and key.casefold() in _FORBIDDEN_KEYS
            for key in members
        ):
            raise ValueError("adjudication must not contain source values")
        for nested in members.values():
            _validate_no_source_values(nested)
    elif isinstance(value, list):
        for nested in cast("list[object]", value):
            _validate_no_source_values(nested)


def _validate_packet_contract(
    packet_report: dict[str, Any], packet_bytes: bytes
) -> None:
    source = cast("dict[str, Any]", packet_report.get("source"))
    expected_report = {
        "schema_id": "global-medicines-atlas.pbs-reference-review-packet",
        "schema_version": 1,
        "status": "source_context_examples_unreviewed_semantic_links_unqualified",
    }
    expected_source = {
        "dataset": DATASET,
        "revision": REVISION,
        "member_sha256": MEMBER_SHA256,
    }
    if (
        any(
            packet_report.get(key) != value
            for key, value in expected_report.items()
        )
        or any(
            source.get(key) != value for key, value in expected_source.items()
        )
        or packet_report.get("calibration", {}).get(
            "semantic_relationships_qualified"
        )
        is not False
        or _sha256(packet_bytes) != PACKET_FILE_SHA256
        or _canonical_sha256(packet_report) != PACKET_REPORT_SHA256
    ):
        raise ValueError("pinned PBS reference packet contract differs")


def _validate_uri_contract(
    uri_report: dict[str, Any],
    uri_bytes: bytes,
    packet_bytes: bytes,
    packet_report_sha256: str,
) -> None:
    expected = {
        "schema_id": "global-medicines-atlas.pbs-uri-reference-review-packet",
        "schema_version": 1,
        "status": "structural_uri_diagnostics_unreviewed_semantics_unqualified",
        "dataset": DATASET,
        "revision": REVISION,
        "member_path": MEMBER_PATH,
        "member_sha256": MEMBER_SHA256,
        "source_packet_sha256": _sha256(packet_bytes),
        "source_packet_report_sha256": packet_report_sha256,
        "semantic_relationships_qualified": False,
        "edges_emitted": False,
        "source_values_emitted": False,
        "precision_claimed": False,
        "recall_claimed": False,
    }
    if (
        any(uri_report.get(key) != value for key, value in expected.items())
        or _canonical_sha256(uri_report) != URI_RECONCILIATION_REPORT_SHA256
        or _sha256(uri_bytes) != URI_RECONCILIATION_FILE_SHA256
    ):
        raise ValueError("pinned PBS URI reconciliation contract differs")


def build_reference_case_adjudication(root: Path) -> dict[str, Any]:  # ruff: ignore[too-many-locals] - the report binds two envelopes, source identities, and the case reconciliation in one deterministic pass
    """Create the case receipt from the exact retained packet and URI report."""
    packet_bytes, packet_envelope = _read_envelope(root, PACKET_PATH)
    uri_bytes, uri_envelope = _read_envelope(root, URI_RECONCILIATION_PATH)
    packet_report = cast("dict[str, Any]", packet_envelope["report"])
    uri_report = cast("dict[str, Any]", uri_envelope["report"])

    _validate_packet_contract(packet_report, packet_bytes)
    _validate_uri_contract(
        uri_report, uri_bytes, packet_bytes, packet_envelope["report_sha256"]
    )

    packet_cases = cast("list[dict[str, Any]]", packet_report["cases"])
    uri_cases = cast("list[dict[str, Any]]", uri_report["cases"])
    if len(packet_cases) != CASE_COUNT or len(uri_cases) != CASE_COUNT:
        raise ValueError(
            f"reference case denominator differs from {CASE_COUNT}"
        )
    packet_by_id = {case["case_id"]: case for case in packet_cases}
    uri_by_id = {case["case_id"]: case for case in uri_cases}
    if len(packet_by_id) != CASE_COUNT or set(packet_by_id) != set(uri_by_id):
        raise ValueError("packet and URI case identities differ")

    rows: list[dict[str, Any]] = []
    for packet_case in packet_cases:
        case_id = packet_case["case_id"]
        uri_case = uri_by_id[case_id]
        bound_fields = (
            "category",
            "kind",
            "reference_occurrence",
            "source_element_qname",
            "target_multiplicity",
            "target_occurrence",
        )
        if any(
            packet_case.get(field) != uri_case.get(field)
            for field in bound_fields
        ):
            raise ValueError(f"case occurrence binding differs: {case_id}")
        if (
            uri_case.get("semantic_relationship_qualified") is not False
            or uri_case.get("edges_emitted") is not False
            or uri_case.get("adjudication") != "unreviewed"
            or uri_case.get("semantic_review_state") != "pending"
            or uri_case.get("target_type_meaning") != "not_established"
        ):
            raise ValueError(f"case semantic boundary differs: {case_id}")
        pointer_role = uri_case.get("structural_role")
        expected_pointer_role = {
            "rdf_resource": "rdf_resource_attribute",
            "xlink_href": "xlink_href_attribute",
        }.get(packet_case["kind"])
        if (
            pointer_role not in _POINTER_ROLES
            or pointer_role != expected_pointer_role
        ):
            raise ValueError(f"unsupported structural pointer role: {case_id}")
        if uri_case.get("reference_occurrence_sha256") != _sha256(
            packet_case["reference_occurrence"].encode()
        ):
            raise ValueError(f"case occurrence digest differs: {case_id}")
        target_occurrence = uri_case.get("target_occurrence")
        if uri_case.get("target_occurrence_sha256") != (
            _sha256(target_occurrence.encode()) if target_occurrence else None
        ):
            raise ValueError(f"case target digest differs: {case_id}")

        is_no_target = packet_case.get("category") == NO_TARGET_CATEGORY
        if is_no_target:
            if (
                uri_case.get("target_multiplicity") != 0
                or uri_case.get("target_occurrence") is not None
                or uri_case.get("target_occurrence_sha256") is not None
                or uri_case.get("uri_resolution") != _NO_TARGET_RESOLUTION
                or packet_case["category"] != NO_TARGET_CATEGORY
            ):
                raise ValueError(f"no-target control changed: {case_id}")
            disposition = "no_definition_in_pinned_member_hard_negative"
            missing = [
                "No same-member target definition exists for this exact scanned reference.",
                "No source value or external target was retained or fetched; this does not establish that the relationship is false outside this member.",
                "Predicate meaning and target meaning are not established.",
            ]
        else:
            if (
                uri_case.get("target_multiplicity") != 1
                or not uri_case.get("target_occurrence")
                or not uri_case.get("target_occurrence_sha256")
                or packet_case["category"]
                not in {
                    "unique_fragment_literal_candidate",
                    "unique_literal_candidate_requires_uri_review",
                }
                or uri_case.get("uri_resolution")
                != {
                    "unique_fragment_literal_candidate": "same_member_unique_id",
                    "unique_literal_candidate_requires_uri_review": "absolute_uri_unique_candidate",
                }[packet_case["category"]]
            ):
                raise ValueError(f"candidate target binding differs: {case_id}")
            disposition = (
                "structural_pointer_role_supported_semantics_abstained"
            )
            missing = [
                "Source-native reference value was intentionally not retained in the packet.",
                "The reviewed context does not establish the source predicate's domain relationship meaning.",
                "The target type meaning and semantic correctness of the relationship are not established.",
            ]
        rows.append({
            "case_id": case_id,
            "category": packet_case["category"],
            "reference_kind": packet_case["kind"],
            "reference_occurrence_sha256": uri_case[
                "reference_occurrence_sha256"
            ],
            "structural_pointer_role": pointer_role,
            "structural_role_evidence": "exact occurrence-bound role in the retained URI reconciliation; attribute QName and kind agree",
            "member_resolution": uri_case["uri_resolution"],
            "target_multiplicity": uri_case["target_multiplicity"],
            "target_occurrence_sha256": uri_case.get(
                "target_occurrence_sha256"
            ),
            "disposition": disposition,
            "hard_negative": is_no_target,
            "semantic_relationship_qualified": False,
            "edges_emitted": False,
            "missing_evidence": missing,
        })

    hard_negatives = sum(row["hard_negative"] for row in rows)
    report: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.pbs-native-reference-case-adjudication",
        "schema_version": 1,
        "status": "structural_pointer_roles_bounded_semantics_abstained",
        "source": {
            "dataset": DATASET,
            "revision": REVISION,
            "member_path": MEMBER_PATH,
            "member_sha256": MEMBER_SHA256,
            "member_values_read": False,
            "new_sources": 0,
        },
        "inputs": {
            "case_packet_path": PACKET_PATH,
            "case_packet_file_sha256": _sha256(packet_bytes),
            "case_packet_report_sha256": packet_envelope["report_sha256"],
            "uri_reconciliation_path": URI_RECONCILIATION_PATH,
            "uri_reconciliation_file_sha256": _sha256(uri_bytes),
            "uri_reconciliation_report_sha256": uri_envelope["report_sha256"],
            "uri_workflow_run_id": uri_report["uri_run_id"],
            "uri_workflow_commit": uri_report["uri_workflow_commit"],
            "source_packet_bytes_bound_by_uri_reconciliation": True,
        },
        "review_scope": {
            "case_count": len(rows),
            "structural_pointer_roles_supported": len(rows),
            "no_target_hard_negatives": hard_negatives,
            "semantic_relationships_qualified": False,
            "edges_emitted": False,
            "precision_claimed": False,
            "recall_claimed": False,
            "corpus_generalizable_match_quality_claimed": False,
            "admission_or_clinical_meaning_claimed": False,
            "meaning": "structural roles and exact member-scoped resolution only; no semantic relationship adjudication",
        },
        "cases": rows,
    }
    _validate_no_source_values(report)
    return report


def validate_reference_case_adjudication(root: Path) -> dict[str, Any]:
    """Validate the checked-in v1 artifact against its exact retained inputs."""
    expected = build_reference_case_adjudication(root)
    raw, envelope = _read_envelope(root, ADJUDICATION_PATH)
    if _canonical_sha256(expected) != envelope["report_sha256"]:
        raise ValueError(
            "reference case adjudication differs from pinned inputs"
        )
    if envelope["report"] != expected:
        raise ValueError("reference case adjudication content differs")
    _validate_no_source_values(envelope)
    if _sha256(raw) != _sha256((root / ADJUDICATION_PATH).read_bytes()):
        raise ValueError(
            "reference case adjudication bytes changed during validation"
        )
    return expected


def write_reference_case_adjudication(root: Path) -> Path:
    """Write a canonical, digest-wrapped artifact from the retained evidence."""
    report = build_reference_case_adjudication(root)
    envelope = {
        "report": report,
        "report_sha256": _canonical_sha256(report),
    }
    destination = root / ADJUDICATION_PATH
    destination.write_text(
        json.dumps(envelope, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination
