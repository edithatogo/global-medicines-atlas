"""Acquire an approved finite source batch and publish from hosted main only."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from scripts.publish_ema_snapshot import SnapshotUploader
from scripts.source_download_batch import DownloadSelection, run_batch

from global_medicines_atlas.data_layer_archive import (
    HuggingFaceAnonymousArtifactVerifier,
)
from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main,
)
from global_medicines_atlas.publication_transport import (
    PublicationDestination,
    PublicationTarget,
    authorization_from_environment,
    execute_publication,
    prepare_publication,
    verify_publication,
)
from global_medicines_atlas.source_catalog import load_source_catalog

ROOT = Path(__file__).resolve().parents[1]


def publish_batch(manifest_path: Path, output: Path, exact_commit: str) -> int:
    """Publish only a committed, approved batch; stop before writes on drift."""
    require_hosted_main(exact_commit)
    manifest_path = manifest_path.resolve()
    if not manifest_path.is_relative_to(ROOT / "quality/source-batches"):
        raise ValueError(
            "publication requires a committed source-batch manifest"
        )
    manifest = json.loads(manifest_path.read_text())
    if manifest["publication_approved"] is not True:
        raise ValueError("batch publication is not approved")
    selections = tuple(
        DownloadSelection.model_validate(row)
        for row in json.loads((manifest_path.parent / "batch.json").read_text())
    )
    results = run_batch(
        selections,
        sources=load_source_catalog(),
        output=output / "acquisition",
        repository_root=ROOT,
        execute=True,
    )
    if any(row["state"] != "acquired_local" for row in results):
        return 1
    package = output / "package"
    package.mkdir()
    for selection in selections:
        source = output / "acquisition" / selection.source_id
        receipt = json.loads((source / "receipt.json").read_text())
        expected = manifest.get("expected_payloads", {}).get(
            selection.source_id
        )
        if expected is not None and receipt["payload"] != expected:
            raise ValueError(
                f"approved snapshot changed: {selection.source_id}"
            )
        target = package / selection.source_id
        target.mkdir()
        for name in ("payload.bin", "receipt.json"):
            shutil.copyfile(source / name, target / name)
    for name in ("README.md", "rights.json"):
        shutil.copyfile(manifest_path.parent / name, package / name)
    paths = tuple(
        sorted(
            str(p.relative_to(package))
            for p in package.rglob("*")
            if p.is_file()
        )
    )
    target = PublicationTarget(
        destination=PublicationDestination.HUGGING_FACE,
        repository=manifest["repository"],
        revision="main",
        public_base_url="https://huggingface.co/datasets/"
        + manifest["repository"],
    )
    plan, _ = prepare_publication(
        root=package,
        relative_paths=paths,
        release_version=manifest["batch_id"],
        target=target,
        recorded_at=datetime.now(UTC),
    )
    receipts = output / "publication-receipts"
    receipts.mkdir()
    (receipts / "plan.json").write_text(plan.model_dump_json(indent=2) + "\n")
    (receipts / "intent.json").write_text(
        json.dumps(
            {
                "commit": exact_commit,
                "run_id": os.environ["GITHUB_RUN_ID"],
                "plan_sha256": plan.sha256(),
                "repository": target.repository,
            },
            indent=2,
        )
        + "\n"
    )
    uploaded = execute_publication(
        plan=plan,
        authorization=authorization_from_environment(os.environ),
        root=package,
        uploader=SnapshotUploader(repository=target.repository),
        recorded_at=datetime.now(UTC),
    )
    (receipts / "uploaded.json").write_text(
        uploaded.model_dump_json(indent=2) + "\n"
    )
    verified = verify_publication(
        plan=plan,
        uploaded_receipt=uploaded,
        verifier=HuggingFaceAnonymousArtifactVerifier(timeout_seconds=120),
        recorded_at=datetime.now(UTC),
    )
    (receipts / "verified.json").write_text(
        verified.model_dump_json(indent=2) + "\n"
    )
    return int(verified.state.value != "public")


def main() -> int:
    """Execute one approved batch, never publish locally or retry a write."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exact-commit", required=True)
    args = parser.parse_args()
    return publish_batch(args.manifest, args.output, args.exact_commit)


if __name__ == "__main__":
    raise SystemExit(main())
