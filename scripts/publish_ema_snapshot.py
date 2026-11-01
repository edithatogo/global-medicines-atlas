"""Publish the exact approved EMA snapshot from protected GitHub Actions."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.data_layer_archive import (
    HuggingFaceAnonymousArtifactVerifier,
)
from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main,
)
from global_medicines_atlas.publication_transport import (
    PublicationPlan,
    PublicationTransportState,
    authorization_from_environment,
    bind_artifacts,
    execute_publication,
    verify_publication,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "quality/qualifications/ema-publication-20261030"
DATASET = "edithatogo/global-medicines-atlas-ema-bronze-20261029"
PAYLOAD = "payloads/eu-ema-json/medicines-output-medicines_json-report_en.json"


class SnapshotUploader:
    """One new public dataset and one content-bound commit; no upload retries."""

    def __init__(self, repository: str = DATASET) -> None:
        self.repository = repository

    def upload_folder(
        self, *, repository: str, folder: Path, commit_message: str
    ) -> str:
        require_hosted_main(os.environ.get("GITHUB_SHA", ""))
        if repository != self.repository:
            raise ValueError("EMA publication target differs")
        hub = cast("Any", import_module("huggingface_hub"))
        api = hub.HfApi(token=os.environ["HF_TOKEN"])
        api.create_repo(
            repo_id=repository,
            repo_type="dataset",
            private=False,
            exist_ok=False,
        )
        parent = api.dataset_info(repository).sha
        result = api.upload_folder(
            repo_id=repository,
            repo_type="dataset",
            folder_path=folder,
            commit_message=commit_message,
            parent_commit=parent,
        )
        return str(result.oid)


def prepare_snapshot(artifact: Path, output: Path) -> PublicationPlan:
    """Restore only the approved bytes and metadata into a fresh package."""
    plan = PublicationPlan.model_validate_json(
        (EVIDENCE / "publication-plan.json").read_bytes()
    )
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(artifact / PAYLOAD, output / "medicines.json")
    for name in ("README.md", "retrieval.json"):
        shutil.copyfile(EVIDENCE / name, output / name)
    paths = tuple(item.relative_path for item in plan.artifacts)
    if bind_artifacts(output, paths) != plan.artifacts:
        raise ValueError("restored package does not match approved snapshot")
    return plan


def main(argv: list[str] | None = None) -> int:
    """Prepare offline or execute only the approved hosted publication."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--exact-commit", default="")
    args = parser.parse_args(argv)
    if args.publish:
        require_hosted_main(args.exact_commit)
    plan = prepare_snapshot(args.artifact, args.output)
    if not args.publish:
        print(plan.sha256())
        return 0
    receipt_dir = args.output.parent / "publication-receipts"
    receipt_dir.mkdir(exist_ok=True)
    (receipt_dir / "intent.json").write_text(
        json.dumps(
            {
                "target": DATASET,
                "plan_sha256": plan.sha256(),
                "commit": args.exact_commit,
                "run_id": os.environ.get("GITHUB_RUN_ID"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    uploaded = execute_publication(
        plan=plan,
        authorization=authorization_from_environment(os.environ),
        root=args.output,
        uploader=SnapshotUploader(),
        recorded_at=datetime.now(UTC),
    )
    (receipt_dir / "uploaded.json").write_text(
        uploaded.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    if uploaded.state is not PublicationTransportState.UPLOADED:
        return 1
    verified = verify_publication(
        plan=plan,
        uploaded_receipt=uploaded,
        verifier=HuggingFaceAnonymousArtifactVerifier(timeout_seconds=120),
        recorded_at=datetime.now(UTC),
    )
    (receipt_dir / "verified.json").write_text(
        verified.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    print(verified.state.value)
    return int(verified.state is not PublicationTransportState.PUBLIC)


if __name__ == "__main__":
    raise SystemExit(main())
