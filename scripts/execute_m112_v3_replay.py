"""Execute one exact M-112 raw-B2 replay by digest, without reading payload values."""

# ruff: file-ignore[too-many-branches,too-many-locals,too-many-statements] -- exact hosted replay needs explicit fail-closed gate sequence

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

if __package__:
    from .qualify_m112_v3_replay import OUTPUT as PLAN_PATH
    from .qualify_m112_v3_replay import ROOT, V3_SCHEMA
else:
    from qualify_m112_v3_replay import OUTPUT as PLAN_PATH
    from qualify_m112_v3_replay import ROOT, V3_SCHEMA

REPOSITORY = "edithatogo/global-medicines-atlas"
DATASET = "edithatogo/australian-mbs-utilisation-archive"
REVISION = "dee9a5b0580dfe394474dc26b372559462e157e7"
TARGET_PATH = "raw/mbs/utilisation/group/mbs-group-2016hr-july.xlsx"
COMMIT_LENGTH = 40
SUPPORTED_SOURCE_IDS = frozenset({
    "au-data-gov-mbs-group",
    "au-data-gov-mbs-demographics",
})


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_identity(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count


def _read_json(path: Path) -> dict[str, Any]:
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast("dict[str, Any]", value)


def _target_identity(snapshot: dict[str, Any]) -> tuple[str, str, str]:
    """Parse and constrain the exact public M-112 MBS raw-B2 locator."""
    prefix = f"{DATASET}@{REVISION}:"
    partition_value = snapshot.get("partition_value")
    if not isinstance(partition_value, str) or not partition_value.startswith(
        prefix
    ):
        raise ValueError(
            "replay plan differs from the approved M-112 dataset pin"
        )
    target_path = partition_value[len(prefix) :]
    if (
        not target_path.startswith("raw/mbs/utilisation/")
        or ".." in Path(target_path).parts
        or "\\" in target_path
        or not target_path
    ):
        raise ValueError("replay plan target must be an approved raw B2 path")
    return DATASET, REVISION, target_path


def execute(
    plan: dict[str, Any],
    *,
    work_dir: Path,
    output_path: Path,
    workflow_commit: str,
    workflow_run_id: str,
    workflow_run_attempt: str,
    download: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """Verify one public B2 payload and rebuild a deterministic registration."""
    if work_dir.exists() and any(work_dir.iterdir()):
        raise ValueError("replay work directory must be empty")
    if work_dir.resolve() == output_path.resolve() or work_dir.resolve() in (
        output_path.resolve().parents
    ):
        raise ValueError(
            "replay receipt must be outside the temporary payload directory"
        )
    if download is None:
        hub = importlib.import_module("huggingface_hub")
        download = cast("Callable[..., str]", hub.hf_hub_download)

    snapshots_value = plan.get("snapshots")
    replay_plan_value = plan.get("replay_plan")
    if not isinstance(replay_plan_value, dict):
        raise TypeError("replay plan metadata must be an object")
    steps_value = cast("dict[str, Any]", replay_plan_value).get("steps")
    if plan.get("vocabulary_version") != "3.0.0":
        raise ValueError("replay plan must use vocabulary version 3")
    if not isinstance(snapshots_value, list):
        raise TypeError("replay snapshots must be an array")
    snapshots = cast("list[Any]", snapshots_value)
    if len(snapshots) != 1:
        raise ValueError("replay plan must contain exactly one v3 snapshot")
    if not isinstance(snapshots[0], dict):
        raise TypeError("replay snapshot must be an object")
    if not isinstance(steps_value, list):
        raise TypeError("replay steps must be an array")
    steps = cast("list[Any]", steps_value)
    if len(steps) != 1:
        raise ValueError("replay plan must contain exactly one v3 step")
    if not isinstance(steps[0], dict):
        raise TypeError("replay step must be an object")
    snapshot = cast("dict[str, Any]", snapshots[0])
    step = cast("dict[str, Any]", steps[0])
    dataset, revision, target_path = _target_identity(snapshot)
    validator = cast("Any", Draft202012Validator(_read_json(ROOT / V3_SCHEMA)))
    validator.validate({
        key: value for key, value in plan.items() if key != "scope"
    })
    replay_plan = cast("dict[str, Any]", plan["replay_plan"])
    plan_content = {
        key: replay_plan[key]
        for key in (
            "schema_version",
            "deterministic",
            "eligible_snapshot_count",
            "steps",
        )
    }
    if _sha256(_canonical(plan_content)) != replay_plan.get("plan_sha256"):
        raise ValueError("replay plan digest is invalid")
    contracts_value = plan.get("contracts")
    if not isinstance(contracts_value, list):
        raise TypeError("replay plan contracts must be an array")
    contracts = cast("list[Any]", contracts_value)
    if len(contracts) != 1:
        raise ValueError("replay plan must contain exactly one v3 contract")
    contract_value = contracts[0]
    if not isinstance(contract_value, dict):
        raise TypeError("replay contract must be an object")
    contract = cast("dict[str, Any]", contract_value)
    source_id = snapshot.get("source_id")
    replay_identity_is_valid = all((
        source_id in SUPPORTED_SOURCE_IDS,
        contract.get("source_id") == source_id,
        contract.get("contract_id")
        == f"{source_id}:historical-backfill-replay:v1",
        snapshot.get("payload_sha256") is not None,
        snapshot.get("replay_eligible") is True,
        step.get("candidate_only") is True,
        step.get("hosted_replay_status") == "pending",
    ))
    if not replay_identity_is_valid:
        raise ValueError("replay plan target is not eligible for hosted replay")
    expected_digest = snapshot.get("payload_sha256")
    expected_bytes = step.get("expected_byte_count")
    if (
        step.get("expected_payload_sha256") != expected_digest
        or not isinstance(expected_digest, str)
        or not isinstance(expected_bytes, int)
        or expected_bytes < 1
    ):
        raise ValueError(
            "replay plan differs from the approved exact B2 identity"
        )
    expected_snapshot_id = _sha256(
        _canonical([
            snapshot["partition_id"],
            expected_digest,
            snapshot["metadata_sha256"],
        ])
    )
    if (
        snapshot.get("snapshot_id") != expected_snapshot_id
        or snapshot.get("idempotency_key")
        != _sha256(_canonical([snapshot["partition_id"], expected_snapshot_id]))
        or step.get("snapshot_id") != expected_snapshot_id
        or step.get("partition_id") != snapshot.get("partition_id")
    ):
        raise ValueError(
            "replay snapshot identity or idempotency key is invalid"
        )
    if len(workflow_commit) != COMMIT_LENGTH:
        raise ValueError("hosted workflow identity is invalid")
    if any(char not in "0123456789abcdef" for char in workflow_commit):
        raise ValueError("hosted workflow identity is invalid")
    if not workflow_run_id.isdecimal() or int(workflow_run_id) < 1:
        raise ValueError("hosted workflow identity is invalid")
    if not workflow_run_attempt.isdecimal() or int(workflow_run_attempt) < 1:
        raise ValueError("hosted workflow identity is invalid")

    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        retrieved = download(
            repo_id=dataset,
            repo_type="dataset",
            filename=target_path,
            revision=revision,
            token=False,
            local_dir=str(work_dir),
            force_download=True,
        )
        payload_path = Path(retrieved).resolve()
        try:
            payload_path.relative_to(work_dir.resolve())
        except ValueError as error:
            raise ValueError(
                "anonymous download escaped the temporary work directory"
            ) from error
        if not payload_path.is_file():
            raise ValueError(
                "anonymous download did not materialize the expected object"
            )
        observed_digest, observed_bytes = _file_identity(payload_path)
        if (
            observed_digest != expected_digest
            or observed_bytes != expected_bytes
        ):
            raise ValueError(
                "anonymous replay payload digest or byte count differs"
            )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    registration = {
        "schema_version": "m112-raw-b2-replay-registration-v1",
        "snapshot_id": snapshot["snapshot_id"],
        "partition_id": snapshot["partition_id"],
        "source_id": snapshot["source_id"],
        "source_version_id": snapshot["source_version_id"],
        "archive_period": snapshot["archive_period"],
        "logical_asset_id": snapshot["logical_asset_id"],
        "payload_sha256": observed_digest,
        "byte_count": observed_bytes,
        "metadata_sha256": snapshot["metadata_sha256"],
        "rights_state": snapshot["rights_state"],
        "idempotency_key": snapshot["idempotency_key"],
        "operation": "append_only_idempotent_raw_b2_registration",
        "payload_values_read": False,
    }
    registration_sha256 = _sha256(_canonical(registration))
    temporary_bytes_removed = not work_dir.exists()
    if not temporary_bytes_removed:
        raise RuntimeError("temporary source bytes remain after replay")

    receipt = {
        "schema_id": "global-medicines-atlas.m112-v3-replay-execution-receipt",
        "schema_version": 1,
        "status": "passed",
        "candidate_only": True,
        "scope": {
            "dataset": dataset,
            "revision": revision,
            "path": target_path,
            "sha256": observed_digest,
            "byte_count": observed_bytes,
        },
        "replay": {
            "vocabulary_version": "3.0.0",
            "plan_sha256": _sha256(_canonical(plan)),
            "snapshot_id": snapshot["snapshot_id"],
            "partition_id": snapshot["partition_id"],
            "registration_sha256": registration_sha256,
            "registration": registration,
        },
        "verification": {
            "anonymous": True,
            "token_free": True,
            "payload_values_read": False,
            "temporary_source_bytes_removed": temporary_bytes_removed,
        },
        "hosted_workflow": {
            "repository": REPOSITORY,
            "commit": workflow_commit,
            "run_id": int(workflow_run_id),
            "run_attempt": int(workflow_run_attempt),
            "run_url": (
                f"https://github.com/{REPOSITORY}/actions/runs/{workflow_run_id}"
            ),
        },
        "boundaries": {
            "v4_admission_performed": False,
            "m112_consumer_canary_performed": False,
            "public_dataset_mutation": False,
            "source_values_or_rows_included": False,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(
        json.dumps(
            receipt, ensure_ascii=False, sort_keys=True, indent=2
        ).encode()
        + b"\n"
    )
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=ROOT / PLAN_PATH)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workflow-commit", required=True)
    parser.add_argument("--workflow-run-id", required=True)
    parser.add_argument("--workflow-run-attempt", required=True)
    args = parser.parse_args(argv)
    plan_value: Any = json.loads(args.plan.read_text(encoding="utf-8"))
    if not isinstance(plan_value, dict):
        raise TypeError("v3 replay plan must be a JSON object")
    receipt = execute(
        cast("dict[str, Any]", plan_value),
        work_dir=args.work_dir,
        output_path=args.output,
        workflow_commit=args.workflow_commit,
        workflow_run_id=args.workflow_run_id,
        workflow_run_attempt=args.workflow_run_attempt,
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "path": receipt["scope"]["path"],
                "sha256": receipt["scope"]["sha256"],
                "byte_count": receipt["scope"]["byte_count"],
                "temporary_source_bytes_removed": receipt["verification"][
                    "temporary_source_bytes_removed"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
