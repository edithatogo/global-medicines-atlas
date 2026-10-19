"""Build a metadata-only v3 replay contract for one eligible M-112 raw B2 object.

The hosted execution step verifies the pinned anonymous B2 bytes by digest and
replays only the B1/B2 snapshot registration. It never parses source values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
ROLE_REPORT = (
    "quality/qualifications/"
    "australian-m112-v4-contract-role-evidence-qualification-20261020.json"
)
V3_SCHEMA = "contracts/medallion/v3/backfill-replay.schema.json"
OUTPUT = "quality/qualifications/australian-m112-v3-replay-plan-20261020.json"
TARGET_PATH = "raw/mbs/utilisation/group/mbs-group-2016hr-july.xlsx"
TARGET_DATASET = "edithatogo/australian-mbs-utilisation-archive"
TARGET_REVISION = "dee9a5b0580dfe394474dc26b372559462e157e7"
RIGHTS_STATE = "approved_exact_scope_CC_BY_3_0_AU_publicly_readback_verified"


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(root: Path, relative: str) -> dict[str, Any]:
    value: Any = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {relative}")
    return cast("dict[str, Any]", value)


def _verify_reference(root: Path, reference: Any) -> None:
    if not isinstance(reference, dict):
        raise TypeError("M-112 snapshot lacks a bound evidence reference")
    item = cast("dict[str, Any]", reference)
    path = item.get("path")
    expected = item.get("sha256")
    if not isinstance(path, str) or not isinstance(expected, str):
        raise TypeError("M-112 evidence reference is incomplete")
    candidate = root / path
    if not candidate.is_file() or _sha256(candidate.read_bytes()) != expected:
        raise ValueError(f"M-112 evidence reference digest mismatch: {path}")


def _candidate(report: dict[str, Any], target_path: str) -> dict[str, Any]:
    objects = report.get("objects")
    if not isinstance(objects, list):
        raise TypeError("M-112 role report lacks its object inventory")
    candidates: list[dict[str, Any]] = []
    for value in cast("list[Any]", objects):
        if not isinstance(value, dict):
            continue
        item = cast("dict[str, Any]", value)
        if (
            item.get("dataset") == TARGET_DATASET
            and item.get("revision") == TARGET_REVISION
            and item.get("path") == target_path
        ):
            candidates.append(item)
    if len(candidates) != 1:
        raise ValueError("exact M-112 v3 replay target is not unique")
    return candidates[0]


def _already_admitted(root: Path, candidate: dict[str, Any]) -> bool:
    """Reject a replay for a path already present in an exact v4 contract."""
    contracts = root.glob(
        "quality/qualifications/australian-m112-v4-*-raw-b2-contract.json"
    )
    for path in contracts:
        document = _read_json(root, path.relative_to(root).as_posix())
        location = document.get("location")
        if not isinstance(location, dict):
            continue
        identity = cast("dict[str, Any]", location)
        if all(
            identity.get(key) == candidate.get(key)
            for key in ("dataset", "revision", "path")
        ):
            return True
    return False


def _eligible_evidence(
    candidate: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if candidate.get("rights_state") != RIGHTS_STATE:
        raise ValueError("M-112 replay target lacks exact-scope rights")
    if candidate.get("anonymous_digest_readback") is not True:
        raise ValueError("M-112 replay target lacks anonymous digest readback")
    states = candidate.get("contract_role_states")
    if not isinstance(states, dict):
        raise TypeError("M-112 contract role states are not an object")
    if (
        cast("dict[str, Any]", states).get("lineage.inputs")
        != "qualified_b1_b2_only"
    ):
        raise ValueError("M-112 replay target lacks complete B1/B2 lineage")
    if (
        candidate.get("publication_candidate_receipt", {}).get(
            "contract_role_state"
        )
        != "candidate_receipt_available_unbound"
    ):
        raise ValueError("M-112 replay target lacks exact publication receipt")
    if (
        candidate.get("verification_candidate_receipt", {}).get(
            "contract_role_state"
        )
        != "candidate_receipt_available_unbound"
    ):
        raise ValueError("M-112 replay target lacks anonymous restore receipt")
    evidence = candidate.get("lineage_evidence")
    if not isinstance(evidence, dict):
        raise TypeError("M-112 replay target lacks lineage references")
    evidence = cast("dict[str, Any]", evidence)
    for key in (
        "source_receipt_path",
        "acquisition_event_path",
        "b2_manifest_path",
    ):
        path = evidence.get(key)
        if not isinstance(path, str):
            raise TypeError(f"M-112 lineage lacks {key}")
    rights = candidate.get("rights_decision")
    if not isinstance(rights, dict):
        raise TypeError("M-112 replay target lacks its exact rights decision")
    return evidence, cast("dict[str, Any]", rights)


def _source_paths(evidence: dict[str, Any]) -> tuple[str, str, str]:
    return (
        cast("str", evidence["source_receipt_path"]),
        cast("str", evidence["acquisition_event_path"]),
        cast("str", evidence["b2_manifest_path"]),
    )


def _validate_b1(
    receipt: dict[str, Any], event: dict[str, Any], candidate: dict[str, Any]
) -> None:
    if receipt.get("retrieval", {}).get("status") != "succeeded":
        raise ValueError("source receipt does not prove successful acquisition")
    payload = receipt.get("payload")
    if not isinstance(payload, dict):
        raise TypeError("source receipt payload identity is missing")
    payload = cast("dict[str, Any]", payload)
    if payload.get("sha256") != candidate.get("sha256") or payload.get(
        "byte_count"
    ) != candidate.get("bytes"):
        raise ValueError("B1 receipt differs from the pinned M-112 object")
    if (
        event.get("acquisition_id") != candidate.get("acquisition_id")
        or event.get("payload_sha256") != candidate.get("sha256")
        or event.get("retrieval", {}).get("status") != "succeeded"
    ):
        raise ValueError("B1 acquisition event differs from the pinned object")


def _validate_b2(
    root: Path,
    manifest: dict[str, Any],
    evidence: dict[str, Any],
    candidate: dict[str, Any],
    source_id: str,
    manifest_path: str,
    dataset: str,
    revision: str,
    target_path: str,
) -> None:
    rows_value = manifest.get("rows")
    if not isinstance(rows_value, list):
        raise TypeError("B2 external-reference manifest rows are missing")
    rows = cast("list[Any]", rows_value)
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError(
            "B2 external-reference manifest is not a single object"
        )
    manifest_row = cast("dict[str, Any]", rows[0])
    expected_locator = (
        f"https://huggingface.co/datasets/{dataset}/resolve/"
        f"{revision}/{target_path}"
    )
    if not all((
        manifest_row.get("source_id") == source_id,
        manifest_row.get("acquisition_id") == candidate.get("acquisition_id"),
        manifest_row.get("content_id") == candidate.get("sha256"),
        manifest_row.get("external_reference") == expected_locator,
        manifest_row.get("source_native_bytes_immutable") is True,
        manifest_row.get("state") == "external_reference_only",
        manifest_row.get("stratum") == "B2",
    )):
        raise ValueError("B2 manifest differs from the pinned M-112 object")
    if _sha256((root / manifest_path).read_bytes()) != evidence.get(
        "b2_manifest_sha256"
    ):
        raise ValueError("B2 manifest digest differs from the candidate report")


def _partition_metadata(
    root: Path,
    candidate: dict[str, Any],
    evidence: dict[str, Any],
    rights: dict[str, Any],
    source_id: str,
    source_receipt_path: str,
    acquisition_event_path: str,
    b2_manifest_path: str,
    target_path: str,
) -> dict[str, Any]:
    dataset = cast("str", candidate.get("dataset"))
    revision = cast("str", candidate.get("revision"))
    object_identity = {
        "dataset": dataset,
        "revision": revision,
        "path": target_path,
    }
    logical_asset_id = _sha256(_canonical(object_identity))
    # This filename-derived label does not claim payload temporal semantics.
    archive_period = (
        "filename-derived:mbs-group-2016hr-july.xlsx"
        if target_path == TARGET_PATH
        else f"filename-derived:{Path(target_path).name}"
    )
    partition_value = f"{dataset}@{revision}:{target_path}"
    partition_id = _sha256(
        _canonical([source_id, archive_period, logical_asset_id])
    )
    metadata = {
        "object_identity": object_identity,
        "acquisition_id": candidate.get("acquisition_id"),
        "source_receipt_path": source_receipt_path,
        "source_receipt_sha256": _sha256(
            (root / source_receipt_path).read_bytes()
        ),
        "acquisition_event_path": acquisition_event_path,
        "acquisition_event_sha256": _sha256(
            (root / acquisition_event_path).read_bytes()
        ),
        "b2_manifest_path": b2_manifest_path,
        "b2_manifest_sha256": evidence.get("b2_manifest_sha256"),
        "rights_decision": rights,
        "archive_period_basis": "exact source filename; payload not inspected",
    }
    return {
        "archive_period": archive_period,
        "logical_asset_id": logical_asset_id,
        "partition_id": partition_id,
        "partition_value": partition_value,
        "metadata_sha256": _sha256(_canonical(metadata)),
    }


def _snapshot_hashes(
    candidate: dict[str, Any], partition: dict[str, Any]
) -> dict[str, str]:
    payload_sha256 = cast("str", candidate["sha256"])
    snapshot_id = _sha256(
        _canonical([
            partition["partition_id"],
            payload_sha256,
            partition["metadata_sha256"],
        ])
    )
    return {
        "payload_sha256": payload_sha256,
        "snapshot_id": snapshot_id,
        "idempotency_key": _sha256(
            _canonical([partition["partition_id"], snapshot_id])
        ),
    }


def _snapshot(
    root: Path, candidate: dict[str, Any], target_path: str
) -> dict[str, Any]:
    evidence, rights = _eligible_evidence(candidate)
    receipt_path, event_path, manifest_path = _source_paths(evidence)

    receipt = _read_json(root, receipt_path)
    event = _read_json(root, event_path)
    manifest = _read_json(root, manifest_path)
    _verify_reference(root, rights)
    source_id = cast("str", receipt.get("source", {}).get("source_id"))
    _validate_b1(receipt, event, candidate)
    dataset = cast("str", candidate.get("dataset"))
    revision = cast("str", candidate.get("revision"))
    _validate_b2(
        root,
        manifest,
        evidence,
        candidate,
        source_id,
        manifest_path,
        dataset,
        revision,
        target_path,
    )
    partition = _partition_metadata(
        root,
        candidate,
        evidence,
        rights,
        source_id,
        receipt_path,
        event_path,
        manifest_path,
        target_path,
    )
    snapshot_hashes = _snapshot_hashes(candidate, partition)
    return {
        **partition,
        **snapshot_hashes,
        "source_id": source_id,
        "source_version_id": cast("str", receipt["source"]["catalog_version"]),
        "source_url": cast("str", receipt["retrieval"]["uri"]),
        "observation_status": "acquired",
        "correction_sequence": 0,
        "supersedes_snapshot_id": None,
        "late_arriving": False,
        "replay_eligible": True,
        "rights_state": RIGHTS_STATE,
    }


def qualify(
    root: Path = ROOT,
    *,
    target_path: str = TARGET_PATH,
    allow_existing: bool = False,
) -> dict[str, Any]:
    """Build and validate the one-object metadata replay contract."""
    report = _read_json(root, ROLE_REPORT)
    if report.get("contract", {}).get("version") != "4.1":
        raise ValueError("M-112 role report is not for v4.1")
    if (
        not target_path.startswith("raw/mbs/utilisation/")
        or ".." in Path(target_path).parts
        or "\\" in target_path
    ):
        raise ValueError("M-112 replay target must be an approved raw B2 path")
    candidate = _candidate(report, target_path)
    if candidate.get("rights_state") != RIGHTS_STATE:
        raise ValueError("M-112 replay target lacks exact-scope rights")
    if candidate.get("v4_admission_eligible") is True:
        raise ValueError("M-112 replay target is already admitted")
    if not allow_existing and _already_admitted(root, candidate):
        raise ValueError("M-112 replay target already has a v4 contract")
    snapshot = _snapshot(root, candidate, target_path)
    contract = {
        "contract_id": "au-data-gov-mbs-group:historical-backfill-replay:v1",
        "source_id": snapshot["source_id"],
        "partition_identity": [
            "source_id",
            "archive_period",
            "logical_asset_id",
        ],
        "snapshot_identity": [
            "partition_id",
            "payload_sha256",
            "metadata_sha256",
        ],
        "idempotency_rule": "partition_and_snapshot_sha256",
        "late_arrival_rule": "append_then_replay_partition",
        "correction_rule": "new_snapshot_never_overwrite",
        "supersession_rule": "explicit_acyclic_predecessor",
        "replay_order": ["partition_id", "correction_sequence", "snapshot_id"],
        "deterministic_output_rule": "canonical_json_sha256",
        "missing_payload_rule": "metadata_only_fail_closed",
    }
    steps = [
        {
            "action": "verify_and_rebuild_raw_b2_snapshot_registration",
            "snapshot_id": snapshot["snapshot_id"],
            "partition_id": snapshot["partition_id"],
            "expected_payload_sha256": snapshot["payload_sha256"],
            "expected_byte_count": candidate["bytes"],
            "source_payload_values": "not_read",
            "registration_semantics": "append_only_idempotent",
            "candidate_only": True,
            "hosted_replay_status": "pending",
            "v4_admission_performed": False,
            "m112_consumer_canary_performed": False,
        }
    ]
    plan_content = {
        "schema_version": "historical-replay-plan-v1",
        "deterministic": True,
        "eligible_snapshot_count": 1,
        "steps": steps,
    }
    document = {
        "vocabulary_version": "3.0.0",
        "contracts": [contract],
        "snapshots": [snapshot],
        "replay_plan": {
            **plan_content,
            "plan_sha256": _sha256(_canonical(plan_content)),
        },
    }
    schema = _read_json(root, V3_SCHEMA)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)  # pyright: ignore[reportUnknownMemberType]
    return document


def _canonical_document(document: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            document, ensure_ascii=False, sort_keys=True, indent=2
        ).encode("utf-8")
        + b"\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / OUTPUT)
    parser.add_argument("--target-path", default=TARGET_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = _canonical_document(
        qualify(
            target_path=args.target_path,
            allow_existing=args.check and args.target_path == TARGET_PATH,
        )
    )
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != expected:
            raise SystemExit(f"v3 replay plan is stale: {args.output}")
        print("v3 replay plan passed: one exact M-112 raw B2 candidate")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(expected)
    print(f"wrote {args.output} sha256={_sha256(expected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
