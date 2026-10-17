"""Bind the hosted July metadata append to the M-112 per-object report."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
BASE = "quality/qualifications/"
SOURCE_REPORT = (
    f"{BASE}australian-m112-per-object-gate-reconciliation-20261018.json"
)
CONTRACT = f"{BASE}australian-m112-july-metadata-append-contract-20261018.json"
READBACK = f"{BASE}australian-mbs-july-metadata-hosted-readback-20261018.json"
AUTHORIZATION = f"{BASE}australian-mbs-harvest-publication-authorization.json"
OUTPUT = (
    f"{BASE}australian-m112-per-object-gate-reconciliation-"
    "20261018-post-july-readback.json"
)
JULY_GROUP = "au-mbs-july-2026-raw-object-paths"
EXACT_RIGHTS_STATE = "authorized_exact_source_release_permitted"
EXPECTED_SOURCE_ID = "au-mbs"
EXPECTED_DENOMINATOR = 1759
EXPECTED_JULY_OBJECTS = 4
EXPECTED_METADATA_ADDITIONS = 16


def _read(path: str) -> dict[str, Any]:
    value: object = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object in {path}")
    return cast("dict[str, Any]", value)


def _digest(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _binding(path: str) -> dict[str, str]:
    return {"path": path, "sha256": _digest(path)}


def _unique_index(
    rows: list[dict[str, Any]],
    key: str,
    expected_count: int,
    label: str,
) -> dict[str, dict[str, Any]]:
    """Index an exact-size cohort while rejecting duplicate identities."""
    identities = [row[key] for row in rows]
    if len(rows) != expected_count or len(set(identities)) != expected_count:
        raise ValueError(
            f"{label} count or identities are not exact and unique"
        )
    return {row[key]: row for row in rows}


def _validate_readback(  # ruff: ignore[too-many-branches, too-many-statements, too-many-locals] -- independent receipt gates are intentionally explicit
    report: dict[str, Any],
    contract: dict[str, Any],
    authorization: dict[str, Any],
    readback: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Reject a stale, widened, or internally inconsistent hosted receipt."""
    report_digest = hashlib.sha256(
        (ROOT / SOURCE_REPORT).read_bytes()
    ).hexdigest()
    if contract["m112_gate_report"] != {
        "path": SOURCE_REPORT,
        "sha256": report_digest,
    }:
        raise ValueError("July contract does not bind the frozen M-112 report")
    if readback["dataset"] != contract["dataset"]:
        raise ValueError("hosted readback names a different dataset")
    if readback["parent_revision"] != contract["expected_parent_revision"]:
        raise ValueError("hosted readback parent revision differs")
    if readback["workflow"]["contract_sha256"] != _digest(CONTRACT):
        raise ValueError("hosted workflow receipt does not bind the contract")
    if readback["workflow"]["authorization_sha256"] != _digest(AUTHORIZATION):
        raise ValueError("hosted workflow receipt does not bind authorization")
    if not authorization["external_publication_authorized"]:
        raise ValueError("source publication authorization is absent")
    if readback["workflow"]["status"] != "anonymously_verified":
        raise ValueError("hosted append is not anonymously verified")

    manifest = readback["manifest_readback"]
    gates = readback["gates"]
    boundaries = readback["boundaries"]
    if (
        manifest["parent_sha256"] != contract["expected_parent_manifest_sha256"]  # ruff: ignore[too-many-boolean-expressions] -- manifest identity and preservation are separate gates
        or manifest["parent_file_count"]
        != contract["expected_parent_file_count"]
        or manifest["file_count"] != contract["expected_parent_file_count"] + 16
        or manifest["parent_rows_preserved"] is not True
        or manifest["new_paths_exactly_match_receipt"] is not True
        or manifest["new_paths_count"] != EXPECTED_METADATA_ADDITIONS
    ):
        raise ValueError("hosted root-manifest readback diverges")
    if (
        gates["anonymous_digest_verification"] != "passed"  # ruff: ignore[too-many-boolean-expressions] -- every hosted publication state is independent
        or gates["anonymous_metadata_readback"] != "passed"
        or gates["source_objects_preserved"] is not True
        or gates["temporary_hosted_cache_removed"] is not True
        or gates["accepted_admissions"] != 0
        or gates["v4_admissions"] != 0
        or gates["consumer_canaries"] != 0
        or gates["landed_only"] is not True
        or gates["result_public"] is not True
        or gates["result_gated"] is not False
    ):
        raise ValueError(
            "hosted readback reports a different publication state"
        )
    if (
        boundaries["raw_source_bytes_read_by_hosted_verifier"] is not True  # ruff: ignore[too-many-boolean-expressions] -- all source-byte and admission boundaries must hold
        or boundaries["raw_source_bytes_read_locally"] is not False
        or boundaries["raw_source_bytes_retained_locally"] is not False
        or boundaries["raw_source_bytes_uploaded"] is not False
        or boundaries["approved_denominator_changed"] is not False
        or boundaries["rights_scope_expanded"] is not False
        or boundaries["v4_admission_performed"] is not False
        or boundaries["consumer_canaries_performed"] is not False
        or boundaries["m112_accepted"] is not False
    ):
        raise ValueError("hosted readback crosses an M-112 boundary")

    if report["scope"]["approved_denominator"] != EXPECTED_DENOMINATOR:
        raise ValueError("approved M-112 denominator changed")
    if len(report["objects"]) != EXPECTED_DENOMINATOR:
        raise ValueError("M-112 object denominator is incomplete")
    report_identities = {
        (row["dataset"], row["path"]) for row in report["objects"]
    }
    if len(report_identities) != EXPECTED_DENOMINATOR:
        raise ValueError(
            "M-112 object denominator contains duplicate identities"
        )

    contract_objects = _unique_index(
        contract["objects"],
        "archive_path",
        EXPECTED_JULY_OBJECTS,
        "contract cohort",
    )
    hosted_objects = _unique_index(
        readback["objects"],
        "archive_path",
        EXPECTED_JULY_OBJECTS,
        "hosted object cohort",
    )
    raw_digests = _unique_index(
        readback["raw_object_digests"],
        "path",
        EXPECTED_JULY_OBJECTS,
        "raw digest cohort",
    )
    if set(contract_objects) != set(hosted_objects) or set(
        contract_objects
    ) != set(raw_digests):
        raise ValueError(
            "hosted July cohort does not equal the four-object contract"
        )
    metadata = _unique_index(
        readback["metadata_additions"],
        "path",
        EXPECTED_METADATA_ADDITIONS,
        "metadata addition cohort",
    )
    for addition in metadata.values():
        if addition["manifest_row_matches"] is not True:
            raise ValueError(
                "metadata addition does not match its manifest row"
            )

    report_rows = {
        (row["dataset"], row["path"]): row for row in report["objects"]
    }
    result: dict[str, dict[str, Any]] = {}
    referenced_metadata_paths: set[str] = set()
    for path, expected in contract_objects.items():
        observed = hosted_objects[path]
        digest = raw_digests[path]
        if (
            digest["bytes"] != expected["bytes"]  # ruff: ignore[too-many-boolean-expressions] -- all hosted raw identity fields must match
            or digest["sha256"] != expected["sha256"]
            or observed["bytes"] != expected["bytes"]
            or observed["sha256"] != expected["sha256"]
            or observed["category"] != expected["category"]
            or observed["git_blob_oid"] != expected["git_blob_oid"]
            or observed["raw_manifest_row_preserved"] is not True
        ):
            raise ValueError(
                f"hosted raw digest or identity differs for {path}"
            )
        row = report_rows.get((contract["dataset"], path))
        if (
            row is None
            or row["approved_denominator_member"] is not True
            or row["disposition"] != "deferred_not_admitted"
            or row["preserved_deferral_group"]
            != "au-mbs-six-exact-receipt-and-authorization-gaps"
        ):
            raise ValueError(
                f"July MBS path is not the expected deferred row: {path}"
            )
        chain = (
            ("b1_acquisition", "b1_acquisition_event"),
            ("b1_source_receipt", "b1_receipt"),
            ("landed_admission", "b1_landed_admission"),
            ("b2_raw_reference", "b2_raw_reference"),
        )
        for link_name, expected_kind in chain:
            link = observed[link_name]
            addition = metadata.get(link["path"])
            if (
                addition is None
                or addition["sha256"] != link["sha256"]
                or addition["kind"] != expected_kind
                or addition["source_id"] != EXPECTED_SOURCE_ID
            ):
                raise ValueError(
                    f"July lifecycle metadata identity or digest differs for {path}"
                )
            referenced_metadata_paths.add(link["path"])
        if (
            observed["b1_acquisition"]["payload_sha256"] != expected["sha256"]  # ruff: ignore[too-many-boolean-expressions] -- every B1/B2 lifecycle field is independently required
            or observed["b1_acquisition"]["rights_state"] != "permitted"
            or observed["b1_source_receipt"]["content_sha256"]
            != expected["sha256"]
            or observed["b1_source_receipt"]["byte_count"] != expected["bytes"]
            or observed["landed_admission"]["state"] != "landed"
            or observed["landed_admission"]["reviewer_status"] != "unreviewed"
            or observed["b2_raw_reference"]["content_id"] != expected["sha256"]
            or observed["b2_raw_reference"]["state"]
            != "external_reference_only"
            or observed["b2_raw_reference"]["byte_count"] is not None
            or observed["b2_raw_reference"]["payload_sha256"] is not None
        ):
            raise ValueError(f"July B1/B2 lifecycle state differs for {path}")
        result[path] = {**observed, "revision": readback["revision"]}
    if referenced_metadata_paths != set(metadata):
        raise ValueError(
            "hosted metadata additions are not the exact lifecycle cohort"
        )
    return result


def _apply_july_rows(
    report: dict[str, Any],
    contract: dict[str, Any],
    observed: dict[str, dict[str, Any]],
) -> None:
    rows = {(row["dataset"], row["path"]): row for row in report["objects"]}
    for spec in contract["objects"]:
        path = spec["archive_path"]
        row = rows[contract["dataset"], path]
        proof = observed[path]
        row["revision"] = proof["revision"]
        identity = row["identity"]
        if (
            identity["git_blob_oid"] != spec["git_blob_oid"]
            or identity["byte_count"] != spec["bytes"]
            or identity["git_blob_and_size_match"] is not True
        ):
            raise ValueError(f"July raw identity differs for {path}")
        identity.update({
            "sha256_evidence": "anonymous_digest_readback",
            "sha256": spec["sha256"],
            "anonymous_digest_readback": True,
            "digest_evidence": _binding(READBACK),
        })
        row["rights"] = {
            "state": EXACT_RIGHTS_STATE,
            "evidence": _binding(READBACK),
            "decision_evidence": _binding(AUTHORIZATION),
        }
        row["b1_b2_lineage"] = {
            "complete": True,
            "state": (
                "Complete for the raw B1/B2 object: the source receipt, "
                "successful acquisition event, landed unreviewed admission, "
                "external-reference-only B2 manifest, and anonymous digest "
                "readback are bound to this exact July payload. Producer "
                "projection lineage remains separate."
            ),
            "evidence": _binding(READBACK),
        }
        row["preserved_deferral_group"] = JULY_GROUP
        row["v4_admission"] = False
        row["consumer_canary"] = False
        row["disposition"] = "deferred_not_admitted"


def _refresh_aggregates(report: dict[str, Any]) -> None:
    objects = report["objects"]
    report["deferral_group_counts"] = dict(
        sorted(
            Counter(row["preserved_deferral_group"] for row in objects).items()
        )
    )
    report["scope"].update({
        "reconciled_paths": len(objects),
        "denominator_changed": False,
        "preserved_deferrals": sum(
            row["disposition"] == "deferred_not_admitted" for row in objects
        ),
        "v4_admitted": sum(row["v4_admission"] for row in objects),
        "consumer_canaries_passed": sum(
            row["consumer_canary"] for row in objects
        ),
    })
    report["aggregate_gates"].update({
        "all_current_tree_identity_and_size_matches": sum(
            row["identity"]["current_tree_path_present"]
            and row["identity"]["git_blob_and_size_match"]
            for row in objects
        ),
        "paths_with_sha256_metadata_or_binding": sum(
            row["identity"]["sha256"] is not None
            or row["identity"]["sha256_evidence"] != "missing"
            for row in objects
        ),
        "paths_with_anonymous_digest_readback": sum(
            row["identity"]["anonymous_digest_readback"] for row in objects
        ),
        "paths_with_exact_scope_rights_decision_and_public_readback": (
            report["aggregate_gates"][
                "paths_with_exact_scope_rights_decision_and_public_readback"
            ]
        ),
        "paths_with_complete_b1_b2_lineage": sum(
            row["b1_b2_lineage"]["complete"] for row in objects
        ),
        "paths_admitted_to_v4": sum(row["v4_admission"] for row in objects),
        "paths_with_consumer_canary": sum(
            row["consumer_canary"] for row in objects
        ),
        "paths_with_exact_source_release_rights": sum(
            row["rights"]["state"] == EXACT_RIGHTS_STATE for row in objects
        ),
    })


def build_report(
    source_report: dict[str, Any],
    contract: dict[str, Any],
    authorization: dict[str, Any],
    readback: dict[str, Any],
) -> dict[str, Any]:
    """Create a new per-object report without mutating the prior qualification."""
    observed = _validate_readback(
        source_report, contract, authorization, readback
    )
    report = deepcopy(source_report)
    _apply_july_rows(report, contract, observed)
    report.update({
        "recorded_at": "2026-10-18",
        "observed_at": "2026-10-18",
        "supersedes": SOURCE_REPORT,
        "inputs": [
            _binding(SOURCE_REPORT),
            _binding(CONTRACT),
            _binding(AUTHORIZATION),
            _binding(READBACK),
        ],
        "july_metadata_readback": {
            "dataset": readback["dataset"],
            "parent_revision": readback["parent_revision"],
            "revision": readback["revision"],
            "parent_manifest_sha256": readback["manifest_readback"][
                "parent_sha256"
            ],
            "manifest_sha256": readback["manifest_readback"]["sha256"],
            "updated_raw_paths": len(observed),
            "metadata_objects_verified": len(readback["metadata_additions"]),
            "workflow_run": readback["workflow"]["run_url"],
        },
        "boundaries": {
            **source_report["boundaries"],
            "approved_denominator_changed": False,
            "rights_decision_created_or_expanded": False,
            "source_payload_bytes_read": True,
            "source_payload_bytes_retained": False,
            "source_values_inspected": False,
            "source_payload_bytes_uploaded": False,
            "v4_admission_performed": False,
            "consumer_canaries_performed": False,
            "m112_federation_accepted": False,
            "projection_lineage_qualified": False,
        },
    })
    _refresh_aggregates(report)
    return report


def _serialize_report(report: dict[str, Any]) -> str:
    """Keep denominator rows compact and stable for review."""
    lines = ["{"]
    items = list(report.items())
    for index, (key, value) in enumerate(items):
        comma = "," if index < len(items) - 1 else ""
        if key == "objects":
            lines.append('  "objects": [')
            for row_index, row in enumerate(value):
                row_comma = "," if row_index < len(value) - 1 else ""
                lines.append(
                    "    "
                    + json.dumps(row, separators=(",", ":"), ensure_ascii=False)
                    + row_comma
                )
            lines.append(f"  ]{comma}")
            continue
        encoded = json.dumps(value, indent=2, ensure_ascii=False).splitlines()
        prefix = f"  {json.dumps(key)}: "
        if len(encoded) == 1:
            lines.append(f"{prefix}{encoded[0]}{comma}")
        else:
            lines.append(f"{prefix}{encoded[0]}")
            lines.extend(f"  {line}" for line in encoded[1:-1])
            lines.append(f"  {encoded[-1]}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Refresh the July M-112 object crosswalk from frozen readback evidence."""
    report = build_report(
        _read(SOURCE_REPORT),
        _read(CONTRACT),
        _read(AUTHORIZATION),
        _read(READBACK),
    )
    (ROOT / OUTPUT).write_text(_serialize_report(report), encoding="utf-8")


if __name__ == "__main__":
    main()
