"""Prepare exact permitted NZULM members; publish only from hosted main."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast
from zipfile import ZipFile

from scripts.publish_ema_snapshot import SnapshotUploader

from global_medicines_atlas.data_layer_archive import (
    HuggingFaceAnonymousArtifactVerifier,
)
from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main,
)
from global_medicines_atlas.publication_transport import (
    ArtifactBinding,
    PublicationDestination,
    PublicationPlan,
    PublicationTarget,
    PublicationTransportState,
    authorization_from_environment,
    execute_publication,
    prepare_publication,
    verify_publication,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "quality/source-batches/nzulm-2023-recovered"


def digest(path: Path) -> str:
    """Hash a source without changing it."""
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def prepare_snapshot(
    source: Path, output: Path, *, contract: Path = CONTRACT
) -> PublicationPlan:
    """Verify the source and copy only approved members, never extract all."""
    manifest = cast(
        "dict[str, Any]", json.loads((contract / "manifest.json").read_text())
    )
    archive = manifest["source_archive"]
    if manifest["publication_approved"] is not True or (
        source.stat().st_size != archive["size_bytes"]
        or digest(source) != archive["sha256"]
    ):
        raise ValueError("source differs from the approved archive")
    rows = cast("list[dict[str, Any]]", manifest["files"])
    approved = {str(row["member"]) for row in rows}
    excluded = {str(row["member"]) for row in manifest["excluded_members"]}
    if len(approved) != len(rows) or approved & excluded:
        raise ValueError("duplicate or overlapping publication membership")
    output.mkdir(parents=True, exist_ok=False)
    with ZipFile(source) as bundle:
        names = bundle.namelist()
        if (
            len(names) != archive["member_count"]
            or len(names) != len(set(names))
            or set(names) != approved | excluded
        ):
            raise ValueError("archive member inventory differs")
        for row in rows:
            member = str(row["member"])
            binding = ArtifactBinding(
                relative_path=str(row["path"]),
                sha256=str(row["sha256"]),
                size=int(row["size_bytes"]),
            )
            if (
                member != PurePosixPath(member).name
                or "\\" in member
                or binding.relative_path != f"data/{member}"
                or bundle.getinfo(member).file_size != binding.size
            ):
                raise ValueError("unsafe or changed approved member")
            target = output / binding.relative_path
            target.parent.mkdir(exist_ok=True)
            # Reading to EOF also validates the original ZIP member CRC.
            with bundle.open(member) as stream, target.open("xb") as handle:
                shutil.copyfileobj(stream, handle, 1024 * 1024)
            if target.stat().st_size != binding.size or (
                digest(target) != binding.sha256
            ):
                raise ValueError("approved member digest differs")
    for name in ("README.md", "rights.json", "manifest.json"):
        shutil.copyfile(contract / name, output / name)
    paths = tuple(
        sorted(
            str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()
        )
    )
    plan, _ = prepare_publication(
        root=output,
        relative_paths=paths,
        release_version="nzulm-2023-recovered-20261102",
        target=PublicationTarget(
            destination=PublicationDestination.HUGGING_FACE,
            repository=str(manifest["repository"]),
            revision="main",
            public_base_url=(
                "https://huggingface.co/datasets/" + str(manifest["repository"])
            ),
        ),
        recorded_at=datetime.now(UTC),
    )
    return plan


def publish_snapshot(source: Path, output: Path, exact_commit: str) -> int:
    """Retain intent, perform one upload, then verify every object anonymously."""
    require_hosted_main(exact_commit)
    plan = prepare_snapshot(source, output)
    receipts = output.parent / "publication-receipts"
    receipts.mkdir(exist_ok=False)
    (receipts / "plan.json").write_text(plan.model_dump_json(indent=2) + "\n")
    (receipts / "intent.json").write_text(
        json.dumps(
            {
                "commit": exact_commit,
                "run_id": os.environ["GITHUB_RUN_ID"],
                "plan_sha256": plan.sha256(),
                "repository": plan.target.repository,
            },
            indent=2,
        )
        + "\n"
    )
    uploaded = execute_publication(
        plan=plan,
        authorization=authorization_from_environment(os.environ),
        root=output,
        uploader=SnapshotUploader(repository=plan.target.repository),
        recorded_at=datetime.now(UTC),
    )
    (receipts / "uploaded.json").write_text(
        uploaded.model_dump_json(indent=2) + "\n"
    )
    if uploaded.state is not PublicationTransportState.UPLOADED:
        return 1
    verified = verify_publication(
        plan=plan,
        uploaded_receipt=uploaded,
        verifier=HuggingFaceAnonymousArtifactVerifier(timeout_seconds=120),
        recorded_at=datetime.now(UTC),
    )
    (receipts / "verified.json").write_text(
        verified.model_dump_json(indent=2) + "\n"
    )
    return int(verified.state is not PublicationTransportState.PUBLIC)


def main() -> int:
    """Prepare locally or publish the exact approved source from Actions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--exact-commit", default="")
    args = parser.parse_args()
    if args.publish:
        return publish_snapshot(args.source, args.output, args.exact_commit)
    print(prepare_snapshot(args.source, args.output).sha256())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
