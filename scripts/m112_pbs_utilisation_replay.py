"""Bind metadata-only replay to six existing, rights-attested PBS B2 objects."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
QUAL = "quality/qualifications/"
DATASET = "edithatogo/australian-pbs-utilisation-archive"
REVISION = "9f1d53cd50eea251b326da42a96f3ac72ebce97a"
SOURCE_IDS = frozenset({"au-pbs-expenditure", "au-pbs-dos-utilisation"})
RIGHTS_STATE = (
    "maintainer_attested_exact_public_release_permission_for_pbs_"
    "utilisation_raw_object"
)
RIGHTS_LINEAGE = QUAL + (
    "australian-m112-pbs-utilisation-rights-lineage-reconciliation-20261028.json"
)
LINEAGE = QUAL + "australian-pbs-utilisation-landed-lineage-20261019.json"
RIGHTS_ATTESTATION = QUAL + (
    "australian-pbs-utilisation-six-object-rights-attestation-20261020.json"
)
FROZEN = QUAL + "australian-m112-frozen-object-inventory-20261018.json"
DIGEST_REPORT = QUAL + (
    "australian-m112-utilisation-digest-reconciliation-20261004.json"
)
SIDECARS = QUAL + (
    "australian-pbs-utilisation-receipt-sidecar-readback-20261019.json"
)
INPUT_DIGESTS = {
    RIGHTS_LINEAGE: "5050236f8aa68491f490ca35dd4425c3173eb54673c5072e6dcfac712cf62775",
    LINEAGE: "758db3eb852dafae15da6979d4ae6638f245a94e23232d901d3d9dde4322bd58",
    RIGHTS_ATTESTATION: "903c42f29ac7518a8be0525f0c1488b78d21f25ad051c9d108bfb2b3736b2968",
    FROZEN: "eaa1d84325c7672100398acf8116f0312369ca336d42ed21eee110452d3fefa4",
    DIGEST_REPORT: "408cdf7de7020b05253d155e29918ffab06ad875643d2fd321880a7fa29c7feb",
    SIDECARS: "01af630097026f924fcb78aef4e567f235d88925eb089a8293a9250ce0129374",
}
OBJECT_COUNT = 6
DENOMINATOR = 1759


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _read_bound(root: Path, relative: str, digest: str) -> dict[str, Any]:
    body = (root / relative).read_bytes()
    if _sha256(body) != digest:
        raise ValueError(f"PBS replay evidence digest mismatch: {relative}")
    value: object = json.loads(body)
    if not isinstance(value, dict):
        raise TypeError(f"expected PBS replay metadata object: {relative}")
    return cast("dict[str, Any]", value)


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed = {row["path"]: row for row in rows}
    if len(rows) != OBJECT_COUNT or len(indexed) != OBJECT_COUNT:
        raise ValueError("PBS replay evidence lacks six unique exact objects")
    return indexed


def _load(root: Path) -> dict[str, dict[str, Any]]:
    return {
        relative: _read_bound(root, relative, digest)
        for relative, digest in INPUT_DIGESTS.items()
    }


def _target(
    inputs: dict[str, dict[str, Any]],
    target_path: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    lineage = inputs[LINEAGE]
    digest_report = inputs[DIGEST_REPORT]
    rights_rows = _index(inputs[RIGHTS_LINEAGE]["objects"])
    lineage_rows = _index(lineage["objects"])
    sidecars = _index(inputs[SIDECARS]["objects"])
    verified = _index([
        row
        for row in digest_report["verified_objects"]
        if row["dataset"] == DATASET and row["revision"] == REVISION
    ])
    frozen = _index([
        row
        for row in inputs[FROZEN]["members"]
        if row["dataset"] == DATASET
        and row["approved_dataset_revision"] == REVISION
    ])
    path_sets = [
        set(rows)
        for rows in (
            rights_rows,
            lineage_rows,
            sidecars,
            verified,
            frozen,
        )
    ]
    if any(paths != path_sets[0] for paths in path_sets):
        raise ValueError("PBS replay evidence path denominators differ")
    if target_path not in rights_rows:
        raise ValueError(
            "target is not an exact PBS replay target; "
            "approved raw B2 path required"
        )
    row = rights_rows[target_path]
    landed = lineage_rows[target_path]
    receipt = sidecars[target_path]
    identity = verified[target_path]
    archives = [
        archive
        for archive in digest_report["archives"]
        if archive["dataset"] == DATASET and archive["revision"] == REVISION
    ]
    if len(archives) != 1:
        raise ValueError("PBS replay lacks its exact publication/restore pin")
    archive = archives[0]
    verification = archive["historical_verification_receipt"]
    if not all((
        inputs[RIGHTS_LINEAGE]["scope"]["frozen_denominator"] == DENOMINATOR,
        inputs[RIGHTS_LINEAGE]["scope"]["denominator_changed"] is False,
        row["dataset"] == landed["dataset"] == DATASET,
        row["revision"] == landed["revision"] == REVISION,
        row["rights_state"] == RIGHTS_STATE,
        row["b1_b2_lineage_complete"] is True,
        row["sha256"]
        == landed["content_sha256"]
        == receipt["sha256"]
        == identity["sha256"],
        row["byte_count"]
        == landed["byte_count"]
        == receipt["byte_count"]
        == identity["byte_count"],
        landed["source_id"] == receipt["source_id"] == identity["source_id"],
        landed["source_id"] in SOURCE_IDS,
        identity["matched_hosted_verified_manifest"] is True,
        archive["public"] is True,
        archive["gated"] is False,
        archive["raw_candidate_object_count"] == OBJECT_COUNT,
        verification["workflow_conclusion"] == "success",
        verification["anonymous_digest_verification"] == "passed",
        verification["temporary_source_bytes_removed"] is True,
        verification["verified_file_count"] == archive["manifest_object_count"],
        landed["receipt_sha256"] == receipt["receipt_sha256"],
        landed["source_url"] == receipt["source_url"],
        row["v4_admission"] is False,
        row["consumer_canary"] is False,
    )):
        raise ValueError("PBS replay rights, lineage or publication differs")
    return row, landed, receipt


def _lifecycle(
    root: Path,
    inputs: dict[str, dict[str, Any]],
    landed: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    bindings = inputs[LINEAGE]["output_bindings"]
    records: dict[str, dict[str, Any]] = {}
    for field in (
        "acquisition_event_path",
        "b2_manifest_path",
        "landed_admission_path",
    ):
        relative = landed[field]
        if (
            not relative.startswith("quality/bronze/")
            or not relative.endswith(".json")
            or ".." in Path(relative).parts
        ):
            raise ValueError(
                "PBS replay lifecycle must be local B1/B2 metadata"
            )
        try:
            records[field] = _read_bound(root, relative, bindings[relative])
        except ValueError as error:
            raise ValueError("PBS replay lifecycle digest mismatch") from error
    return records


def build_snapshot(  # ruff: ignore[too-many-locals] -- keep the exact B1/B2 identity join together
    root: Path,
    *,
    target_path: str,
) -> tuple[dict[str, Any], int]:
    """Build one frozen, metadata-only snapshot without reading source bytes."""
    inputs = _load(root)
    row, landed, receipt = _target(inputs, target_path)
    records = _lifecycle(root, inputs, landed)
    event = records["acquisition_event_path"]
    manifest = records["b2_manifest_path"]
    b2_rows = manifest["rows"]
    expected_url = (
        f"https://huggingface.co/datasets/{DATASET}/resolve/"
        f"{REVISION}/{target_path}"
    )
    if len(b2_rows) != 1 or not all((
        event["acquisition_id"] == landed["acquisition_id"],
        event["source_id"] == landed["source_id"],
        event["content_id"] == event["payload_sha256"] == row["sha256"],
        event["retrieval"]["status"] == "succeeded",
        event["retrieval"]["uri"] == receipt["source_url"],
        event["source_version"] == receipt["period_label"],
        b2_rows[0]["acquisition_id"] == event["acquisition_id"],
        b2_rows[0]["source_id"] == event["source_id"],
        b2_rows[0]["content_id"] == row["sha256"],
        b2_rows[0]["external_reference"] == expected_url,
        b2_rows[0]["state"] == "external_reference_only",
        b2_rows[0]["stratum"] == "B2",
        b2_rows[0]["source_native_bytes_immutable"] is True,
    )):
        raise ValueError("PBS replay B1/B2 identity differs")
    object_identity = {
        "dataset": DATASET,
        "revision": REVISION,
        "path": target_path,
    }
    logical_asset_id = _sha256(_canonical(object_identity))
    archive_period = f"filename-derived:{Path(target_path).name}"
    partition_id = _sha256(
        _canonical([
            event["source_id"],
            archive_period,
            logical_asset_id,
        ])
    )
    metadata = {
        "object_identity": object_identity,
        "acquisition_id": event["acquisition_id"],
        "lineage": landed,
        "evidence_bindings": INPUT_DIGESTS,
        "rights_evidence": row["rights_evidence"],
        "historical_acquisition_rights_state": event["rights_state"],
        "archive_period_basis": "exact filename; source values not inspected",
    }
    metadata_sha256 = _sha256(_canonical(metadata))
    snapshot_id = _sha256(
        _canonical([
            partition_id,
            row["sha256"],
            metadata_sha256,
        ])
    )
    return {
        "snapshot_id": snapshot_id,
        "source_id": event["source_id"],
        "source_version_id": event["source_version"],
        "partition_id": partition_id,
        "partition_value": f"{DATASET}@{REVISION}:{target_path}",
        "logical_asset_id": logical_asset_id,
        "source_url": receipt["source_url"],
        "archive_period": archive_period,
        "observation_status": "acquired",
        "payload_sha256": row["sha256"],
        "metadata_sha256": metadata_sha256,
        "idempotency_key": _sha256(_canonical([partition_id, snapshot_id])),
        "correction_sequence": 0,
        "supersedes_snapshot_id": None,
        "late_arriving": False,
        "replay_eligible": True,
        "rights_state": RIGHTS_STATE,
    }, cast("int", row["byte_count"])
