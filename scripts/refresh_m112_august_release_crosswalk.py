"""Refresh exact M-112 gates for the authorized August MBS raw release."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
BASE = "quality/qualifications/"
BASELINE = f"{BASE}australian-m112-per-object-gate-reconciliation-20261005.json"
LIFECYCLE = f"{BASE}australian-m112-mbs-lifecycle-crosswalk-20261004.json"
ROOT_READBACK = (
    f"{BASE}australian-m112-root-manifest-path-readback-20261017.json"
)
SOURCE_DIGEST = (
    f"{BASE}australian-m112-source-archive-digest-reconciliation-20261004.json"
)
ALIAS_READBACK = (
    f"{BASE}australian-m112-august-alias-anonymous-readback-20261018.json"
)
SOURCE_RECEIPT = f"{BASE}australian-mbs-bronze-source-receipt-20261004.json"
AUTHORIZATION = f"{BASE}australian-mbs-harvest-publication-authorization.json"
RELEASE_CONTRACT = f"{BASE}mbs-current-release-contract.json"
OUTPUT = f"{BASE}australian-m112-per-object-gate-reconciliation-20261018.json"

RAW_PATH = (
    "raw/mbs/releases/2026-08-01/"
    "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565.xml"
)
ALIAS_PATH = "raw/mbs/releases/Downloads-20260801/MBS-XML-20260801.XML"
PAYLOAD_SHA256 = (
    "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565"
)
PAYLOAD_BYTES = 8_293_331
DATASET = "edithatogo/australian-mbs-source-archive"
DENOMINATOR = 1759
ROOT_FILE_COUNT = 212
CURRENT_DATASET_REVISION = "da83cad9116e2f9a5b927be7b080e9a5e5ea6998"
CURRENT_MANIFEST_SHA256 = (
    "68e6bb97ee43117b860ff1c57e625a00075c734e933d08b3cd67de673432d055"
)
B2_REVISION = "abdf414cdea0127d3edda6f8af402d1a01139623"


def _read(path: str) -> dict[str, Any]:
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object in {path}")
    return cast("dict[str, Any]", value)


def _digest(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _binding(path: str) -> dict[str, str]:
    return {"path": path, "sha256": _digest(path)}


def _validate_scope(report: dict[str, Any], lifecycle: dict[str, Any]) -> None:
    if report["scope"]["approved_denominator"] != DENOMINATOR:
        raise ValueError("approved M-112 denominator changed")
    lifecycle_scope = lifecycle["scope"]
    if lifecycle_scope["approved_candidate_denominator"] != DENOMINATOR:
        raise ValueError("lifecycle evidence belongs to another denominator")
    expected = (DATASET, {RAW_PATH, ALIAS_PATH}, "raw_b1_b2_only", True)
    actual = (
        lifecycle_scope["dataset"],
        set(lifecycle_scope["paths"]),
        lifecycle["canonical_bronze_lifecycle"]["qualification_scope"],
        lifecycle["reconciliation"]["local_b1_b2_lifecycle_complete"],
    )
    if actual != expected:
        raise ValueError("August source lifecycle evidence diverges")


def _validate_authority(
    lifecycle: dict[str, Any],
    receipt: dict[str, Any],
    authorization: dict[str, Any],
    release_contract: dict[str, Any],
) -> None:
    source = lifecycle["canonical_bronze_lifecycle"]
    receipt_authority = receipt["authority"]
    actual = (
        source["content_sha256"],
        source["byte_count"],
        source["source_id"],
        receipt["source_id"],
        receipt["content_id"],
        receipt["qualification_state"],
        receipt["qualification_scope"],
        receipt["rights_state"],
        release_contract["source_id"],
        release_contract["dataset"],
        release_contract["effective_date"],
        release_contract["publication_authorized"],
        release_contract["authorization_reference"],
    )
    expected = (
        PAYLOAD_SHA256,
        PAYLOAD_BYTES,
        "au-mbs",
        "au-mbs",
        PAYLOAD_SHA256,
        "accepted",
        "raw_b1_b2_only",
        "permitted",
        "au-mbs",
        DATASET,
        "2026-08-01",
        True,
        receipt_authority["rights_issue"],
    )
    if actual != expected or "au-mbs" not in authorization["allowed_sources"]:
        raise ValueError("source receipt and authorization do not bind August")
    if not authorization["external_publication_authorized"]:
        raise ValueError("publication authorization is absent")
    if not authorization["maintainer_asserted_redistribution_permission"]:
        raise ValueError("maintainer redistribution permission is absent")
    if "monthly_schedule_xml" not in authorization["categories"]:
        raise ValueError("authorization does not cover monthly MBS XML")
    if receipt_authority["publication_authorization"] != AUTHORIZATION:
        raise ValueError("source receipt names a different authorization")
    if receipt_authority["rights_issue"] != (
        "https://github.com/edithatogo/global-medicines-atlas/issues/339"
        "#issuecomment-5467052330"
    ):
        raise ValueError("source receipt names a different rights decision")


def _validate_bronze_chain(
    receipt: dict[str, Any], source: dict[str, Any]
) -> None:
    files = receipt["files"]
    for name, binding in files.items():
        if _digest(binding["path"]) != binding["sha256"]:
            raise ValueError(f"canonical Bronze {name} digest differs")
    acquisition = _read(files["acquisition_event"]["path"])
    source_receipt = _read(files["source_receipt"]["path"])
    landed = _read(files["landed_admission"]["path"])
    accepted = _read(files["accepted_admission"]["path"])
    b2 = _read(files["b2_manifest"]["path"])
    raw_row = b2["rows"][0]
    expected_reference = (
        "https://huggingface.co/datasets/"
        f"{DATASET}/resolve/{B2_REVISION}/{RAW_PATH}"
    )
    actual = (
        source["archive_revision"],
        source["raw_reference"],
        acquisition["source_id"],
        acquisition["payload_sha256"],
        source_receipt["payload"]["sha256"],
        landed["state"],
        accepted["state"],
        accepted["supersedes_decision_id"],
        b2["row_count"],
        raw_row["content_id"],
        raw_row["source_id"],
        raw_row["state"],
        raw_row["stratum"],
        raw_row["external_reference"],
        receipt["b2"]["external_reference"],
        receipt["hosted_publication"]["source_archive_revision"],
    )
    expected = (
        B2_REVISION,
        expected_reference,
        "au-mbs",
        PAYLOAD_SHA256,
        PAYLOAD_SHA256,
        "landed",
        "accepted",
        landed["decision_id"],
        1,
        PAYLOAD_SHA256,
        "au-mbs",
        "external_reference_only",
        "B2",
        expected_reference,
        expected_reference,
        B2_REVISION,
    )
    if actual != expected:
        raise ValueError("canonical Bronze source or admission chain diverges")


def _validate_public_manifest(root_readback: dict[str, Any]) -> None:
    manifest = root_readback["root_manifest"]
    actual = (
        root_readback["dataset"],
        manifest["anonymous_readback"],
        manifest["file_count"],
        manifest["dataset_revision"],
        manifest["manifest_sha256"],
        root_readback["current_head_reconciliation"][
            "manifest_identity_for_both_august_paths_matches_prior_addendum"
        ],
    )
    expected = (
        DATASET,
        True,
        ROOT_FILE_COUNT,
        CURRENT_DATASET_REVISION,
        CURRENT_MANIFEST_SHA256,
        True,
    )
    if actual != expected:
        raise ValueError(
            "current public root-manifest identity is not verified"
        )
    rows = {
        row["path"]: row["manifest_row"] for row in root_readback["objects"]
    }
    for path in (RAW_PATH, ALIAS_PATH):
        row = rows.get(path)
        if row is None or (row["bytes"], row["sha256"]) != (
            PAYLOAD_BYTES,
            PAYLOAD_SHA256,
        ):
            raise ValueError(f"current root manifest does not bind {path}")


def _validate_payload_digest(report: dict[str, Any]) -> None:
    row = next(
        item
        for item in report["objects"]
        if item["dataset"] == DATASET and item["path"] == RAW_PATH
    )
    digest_report = _read(SOURCE_DIGEST)
    matches = [
        item
        for item in digest_report["verified_objects"]
        if item["dataset"] == DATASET and item["path"] == RAW_PATH
    ]
    if len(matches) != 1:
        raise ValueError("anonymous digest readback is not unique")
    identity = row["identity"]
    actual = (
        identity["sha256"],
        identity["byte_count"],
        identity["anonymous_digest_readback"],
        identity["digest_evidence"]["path"],
        matches[0]["sha256"],
        matches[0]["byte_count"],
        matches[0]["revision"],
        matches[0]["exact_manifest_join"],
    )
    expected = (
        PAYLOAD_SHA256,
        PAYLOAD_BYTES,
        True,
        SOURCE_DIGEST,
        PAYLOAD_SHA256,
        PAYLOAD_BYTES,
        "40891976f77ee5e7688edceed25c9ac98a77547e",
        True,
    )
    if actual != expected:
        raise ValueError("anonymous digest readback does not bind the raw path")


def _validate_alias_readback(report: dict[str, Any]) -> None:
    readback = _read(ALIAS_READBACK)
    actual = (
        readback["dataset"],
        readback["revision"],
        readback["path"],
        readback["request_url"],
        readback["method"],
        readback["http_status"],
        readback["anonymous"],
        readback["authorization_header_sent"],
        readback["byte_count"],
        readback["sha256"],
        readback["digest_method"],
        readback["payload_retained"],
        readback["source_values_inspected"],
    )
    expected = (
        DATASET,
        "40891976f77ee5e7688edceed25c9ac98a77547e",
        ALIAS_PATH,
        (
            "https://huggingface.co/datasets/"
            f"{DATASET}/resolve/40891976f77ee5e7688edceed25c9ac98a77547e/"
            f"{ALIAS_PATH}"
        ),
        "GET",
        200,
        True,
        False,
        PAYLOAD_BYTES,
        PAYLOAD_SHA256,
        "sha256_stream",
        False,
        False,
    )
    if actual != expected:
        raise ValueError("anonymous digest readback does not bind the alias")

    row = next(
        item
        for item in report["objects"]
        if item["dataset"] == DATASET and item["path"] == ALIAS_PATH
    )
    identity = row["identity"]
    identity.update({
        "sha256_evidence": "anonymous_digest_readback",
        "sha256": PAYLOAD_SHA256,
        "anonymous_digest_readback": True,
        "digest_evidence": _binding(ALIAS_READBACK),
    })


def _validate_alias_b1_b2_identity(
    report: dict[str, Any], lifecycle: dict[str, Any]
) -> None:
    """Require the alias to resolve to the exact canonical raw B1/B2 object."""
    by_path = {
        item["path"]: item
        for item in report["objects"]
        if item["dataset"] == DATASET
    }
    canonical = by_path[RAW_PATH]
    alias = by_path[ALIAS_PATH]
    canonical_identity = canonical["identity"]
    alias_identity = alias["identity"]
    lifecycle_identity = lifecycle["producer_archive_objects"]

    expected_identity = (
        PAYLOAD_SHA256,
        PAYLOAD_BYTES,
        True,
        "025c714ecd1fa69f91fdb4de002d285d47272e40",
    )
    canonical_actual = (
        canonical_identity["sha256"],
        canonical_identity["byte_count"],
        canonical_identity["anonymous_digest_readback"],
        canonical_identity["git_blob_oid"],
    )
    alias_actual = (
        alias_identity["sha256"],
        alias_identity["byte_count"],
        alias_identity["anonymous_digest_readback"],
        alias_identity["git_blob_oid"],
    )
    lifecycle_actual = (
        lifecycle_identity["source_sha256"],
        lifecycle_identity["byte_count"],
        lifecycle_identity["path_alias_git_blob_oid"],
    )
    if (
        canonical_actual != expected_identity
        or alias_actual != expected_identity
        or lifecycle_actual
        != (PAYLOAD_SHA256, PAYLOAD_BYTES, expected_identity[3])
        or lifecycle["reconciliation"]["source_identity_joined"] is not True
        or lifecycle["reconciliation"]["local_b1_b2_lifecycle_complete"]
        is not True
    ):
        raise ValueError(
            "August alias does not resolve to the canonical raw B1/B2 object"
        )


def _apply_object_crosswalk(report: dict[str, Any]) -> None:
    rows = [row for row in report["objects"] if row["dataset"] == DATASET]
    by_path = {row["path"]: row for row in rows}
    if (
        len(by_path) != len(rows)
        or not {RAW_PATH, ALIAS_PATH} <= by_path.keys()
    ):
        raise ValueError(
            "August paths are not unique members of the denominator"
        )
    for path in (RAW_PATH, ALIAS_PATH):
        row = by_path[path]
        if (
            not row["approved_denominator_member"]
            or row["disposition"] != "deferred_not_admitted"
        ):
            raise ValueError("August path disposition changed")
        row["rights"] = {
            "state": "authorized_exact_source_release_permitted",
            "evidence": _binding(SOURCE_RECEIPT),
            "decision_evidence": _binding(AUTHORIZATION),
        }
    by_path[RAW_PATH]["b1_b2_lineage"] = {
        "complete": True,
        "state": (
            "complete for the raw B1/B2 object: official source receipt, "
            "landed-to-accepted lifecycle, immutable B2 reference and anonymous "
            "digest readback are joined; producer projection lineage remains separate"
        ),
        "evidence": _binding(LIFECYCLE),
    }
    by_path[ALIAS_PATH]["b1_b2_lineage"] = {
        "complete": True,
        "state": (
            "complete for the shared raw B1/B2 payload object: the alias and "
            "canonical path have the same pinned Git blob, byte count, and "
            "SHA-256; the alias also has its own exact-revision anonymous "
            "digest readback. Historical producer-archive records remain "
            "preserved, and their separate projection lineage is unqualified"
        ),
        "evidence": {
            "canonical_object": {
                "archive_path": RAW_PATH,
                "payload_sha256": PAYLOAD_SHA256,
                "byte_count": PAYLOAD_BYTES,
                "git_blob_oid": "025c714ecd1fa69f91fdb4de002d285d47272e40",
            },
            "bronze_lifecycle": _binding(LIFECYCLE),
            "source_receipt": _binding(SOURCE_RECEIPT),
            "alias_anonymous_readback": _binding(ALIAS_READBACK),
        },
    }


def build_report() -> dict[str, Any]:
    """Reconcile existing evidence without acquisition, publication, or promotion."""
    report = _read(BASELINE)
    lifecycle = _read(LIFECYCLE)
    receipt = _read(SOURCE_RECEIPT)
    authorization = _read(AUTHORIZATION)
    _validate_scope(report, lifecycle)
    _validate_authority(
        lifecycle, receipt, authorization, _read(RELEASE_CONTRACT)
    )
    _validate_bronze_chain(receipt, lifecycle["canonical_bronze_lifecycle"])
    _validate_public_manifest(_read(ROOT_READBACK))
    _validate_payload_digest(report)
    _validate_alias_readback(report)
    _validate_alias_b1_b2_identity(report, lifecycle)
    _apply_object_crosswalk(report)

    report.update({
        "schema_id": "global-medicines-atlas.australian-m112-per-object-gate-reconciliation",
        "schema_version": 2,
        "observed_at": "2026-10-18",
        "supersedes": BASELINE,
        "inputs": [
            _binding(path)
            for path in (
                BASELINE,
                LIFECYCLE,
                ROOT_READBACK,
                SOURCE_DIGEST,
                ALIAS_READBACK,
                SOURCE_RECEIPT,
                AUTHORIZATION,
                RELEASE_CONTRACT,
            )
        ],
        "boundaries": {
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
    report["scope"].update({
        "reconciled_paths": len(report["objects"]),
        "denominator_changed": False,
        "preserved_deferrals": len(report["objects"]),
        "v4_admitted": 0,
        "consumer_canaries_passed": 0,
    })
    report["aggregate_gates"].update({
        "paths_with_anonymous_digest_readback": sum(
            row["identity"]["anonymous_digest_readback"]
            for row in report["objects"]
        ),
        "paths_with_exact_source_release_rights": 2,
        "paths_with_complete_b1_b2_lineage": 2,
        "paths_admitted_to_v4": 0,
        "paths_with_consumer_canary": 0,
    })
    return report


def _serialize_report(report: dict[str, Any]) -> str:
    """Keep each denominator row on one line, matching the prior ledger format."""
    items = list(report.items())
    lines = ["{"]
    for index, (key, value) in enumerate(items):
        comma = "," if index < len(items) - 1 else ""
        if key == "objects":
            lines.append('  "objects": [')
            for row_index, row in enumerate(value):
                row_comma = "," if row_index < len(value) - 1 else ""
                compact = json.dumps(
                    row, separators=(",", ":"), ensure_ascii=False
                )
                lines.append(f"    {compact}{row_comma}")
            lines.append(f"  ]{comma}")
            continue
        encoded = json.dumps(value, indent=2, ensure_ascii=False).splitlines()
        prefix = f"  {json.dumps(key)}: "
        if len(encoded) == 1:
            lines.append(f"{prefix}{encoded[0]}{comma}")
            continue
        lines.append(f"{prefix}{encoded[0]}")
        lines.extend(f"  {line}" for line in encoded[1:-1])
        lines.append(f"  {encoded[-1]}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> None:
    (ROOT / OUTPUT).write_text(
        _serialize_report(build_report()), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
