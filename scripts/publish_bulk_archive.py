"""Publish a completed bulk acquisition archive from hosted main only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping
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
    PublicationDestination,
    PublicationTarget,
    authorization_from_environment,
    execute_publication,
    inventory_publication_files,
    prepare_publication,
    verify_publication,
)

ROOT = Path(__file__).resolve().parents[1]
BATCHES = ROOT / "quality/source-batches"
CARD_NAME = "README.md"
RIGHTS_NAME = "rights.json"
MANIFEST_NAME = "ARTIFACT-MANIFEST.json"
CHUNK_BYTES = 8 * 1024 * 1024
DEFAULT_VERIFICATION_TIMEOUT_SECONDS = 3600


def digest(path: Path) -> str:
    """Hash one artifact without loading it into memory."""
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
            result.update(chunk)
    return result.hexdigest()


def load_contract(manifest_path: Path) -> dict[str, Any]:
    """Read one committed, explicitly approved bulk-archive contract."""
    resolved = manifest_path.resolve()
    if not resolved.is_relative_to(BATCHES):
        raise ValueError(
            "publication requires a committed source-batch manifest"
        )
    manifest = cast("dict[str, Any]", json.loads(resolved.read_text()))
    if manifest.get("publication_approved") is not True:
        raise ValueError("bulk archive publication is not approved")
    return manifest


def payload_paths(root: Path, manifest: Mapping[str, Any]) -> tuple[str, ...]:
    """Select the payload members of an archive without trusting the tree."""
    suffix = str(manifest["payload_suffix"])
    return tuple(
        path
        for path in inventory_publication_files(root)
        if path.endswith(suffix)
    )


def assert_archive_matches_contract(
    root: Path, manifest: Mapping[str, Any]
) -> tuple[str, ...]:
    """Refuse an archive that drifted from its approved inventory."""
    payloads = payload_paths(root, manifest)
    if len(payloads) != int(manifest["expected_payload_count"]):
        raise ValueError("archive payload count differs from the contract")
    total = sum((root / path).stat().st_size for path in payloads)
    if total != int(manifest["expected_payload_bytes"]):
        raise ValueError("archive payload bytes differ from the contract")
    recorded = cast(
        "Mapping[str, str]", manifest.get("recorded_payload_digests", {})
    )
    for path, expected in sorted(recorded.items()):
        if digest(root / path) != expected:
            raise ValueError(f"recorded payload digest differs: {path}")
    return payloads


def build_card(manifest: Mapping[str, Any]) -> str:
    """Render the dataset card from the committed contract alone."""
    rights = cast("Mapping[str, str]", manifest["rights"])
    lines = [
        "---",
        f"pretty_name: {manifest['pretty_name']}",
        "license: other",
        "language:",
        "- en",
        "tags:",
        "- medicines",
        "- regulatory",
        "- fda",
        "---",
        "",
        f"# {manifest['pretty_name']}",
        "",
        str(manifest["description"]),
        "",
        "## Source",
        "",
        f"- Authority: {manifest['source_authority']}",
        f"- Source URL: {manifest['source_url']}",
        f"- Retrieval date: {manifest['retrieval_date']}",
        f"- Snapshot identity: `{manifest['snapshot_id']}`",
        f"- Schema version: `{manifest['schema_version']}`",
        "",
        "## Rights",
        "",
        f"- Licence: {rights['licence']}",
        f"- Terms: {rights['terms']}",
        f"- Required attribution: {rights['attribution']}",
        f"- Redistribution decision: {rights['redistribution']}",
        "",
        "## What this archive contains",
        "",
        (
            f"- {manifest['expected_payload_count']} payload files, "
            f"{manifest['expected_payload_bytes']} bytes, source-native and "
            "unmodified."
        ),
        f"- {manifest['fields_and_transformations']}",
        "",
        "## What this archive is not",
        "",
    ]
    lines.extend(f"- {item}" for item in manifest["not_included"])
    lines.append("")
    return "\n".join(lines)


def write_publication_metadata(
    root: Path, manifest: Mapping[str, Any]
) -> tuple[str, ...]:
    """Write card, rights and artifact manifest, then bind the full root."""
    (root / CARD_NAME).write_text(
        build_card(manifest), encoding="utf-8", newline="\n"
    )
    (root / RIGHTS_NAME).write_text(
        json.dumps(
            {
                "batch_id": manifest["batch_id"],
                **cast("Mapping[str, Any]", manifest["rights"]),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    body_paths = tuple(
        path
        for path in inventory_publication_files(root)
        if path != MANIFEST_NAME
    )
    artifacts = [
        {
            "path": path,
            "size": (root / path).stat().st_size,
            "sha256": digest(root / path),
        }
        for path in body_paths
    ]
    (root / MANIFEST_NAME).write_text(
        json.dumps(
            {
                "schema_id": (
                    "global-medicines-atlas.published-artifact-manifest"
                ),
                "schema_version": 1,
                "batch_id": manifest["batch_id"],
                "repository": manifest["repository"],
                "snapshot_id": manifest["snapshot_id"],
                "source_authority": manifest["source_authority"],
                "source_url": manifest["source_url"],
                "retrieval_date": manifest["retrieval_date"],
                "rights": manifest["rights"],
                "artifact_count": len(artifacts),
                "artifact_bytes": sum(item["size"] for item in artifacts),
                "artifacts": artifacts,
            },
            indent=1,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return inventory_publication_files(root)


class HuggingFaceFolderUploader:
    """Create the public dataset and upload one prepared folder."""

    def __init__(self, repository: str) -> None:
        self.repository = repository

    def upload_folder(
        self, *, repository: str, folder: Path, commit_message: str
    ) -> str:
        """Upload the prepared folder and return the created commit."""
        require_hosted_main(os.environ.get("GITHUB_SHA", ""))
        if repository != self.repository:
            raise ValueError("bulk publication target differs")
        hub = cast("Any", import_module("huggingface_hub"))
        api = hub.HfApi(token=os.environ["HF_TOKEN"])
        api.create_repo(
            repo_id=repository,
            repo_type="dataset",
            private=False,
            exist_ok=True,
        )
        result = api.upload_folder(
            repo_id=repository,
            repo_type="dataset",
            folder_path=folder,
            commit_message=commit_message,
            multi_commits=True,
            multi_commits_verbose=True,
        )
        return str(result.oid)


def publish_bulk_archive(
    manifest_path: Path,
    archive_root: Path,
    output: Path,
    exact_commit: str,
    *,
    publish: bool = False,
    verification_timeout_seconds: int = DEFAULT_VERIFICATION_TIMEOUT_SECONDS,
) -> int:
    """Prepare, then optionally upload, one approved bulk archive."""
    require_hosted_main(exact_commit)
    manifest = load_contract(manifest_path)
    assert_archive_matches_contract(archive_root, manifest)
    paths = write_publication_metadata(archive_root, manifest)
    target = PublicationTarget(
        destination=PublicationDestination.HUGGING_FACE,
        repository=str(manifest["repository"]),
        revision="main",
        public_base_url=(
            "https://huggingface.co/datasets/" + str(manifest["repository"])
        ),
    )
    plan, _ = prepare_publication(
        root=archive_root,
        release_version=str(manifest["batch_id"]),
        target=target,
        relative_paths=paths,
        recorded_at=datetime.now(UTC),
    )
    receipts = output / "publication-receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    (receipts / "plan.json").write_text(
        plan.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (receipts / "intent.json").write_text(
        json.dumps(
            {
                "commit": exact_commit,
                "run_id": os.environ.get("GITHUB_RUN_ID", ""),
                "plan_sha256": plan.sha256(),
                "repository": target.repository,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if not publish:
        return 0
    uploaded = execute_publication(
        plan=plan,
        authorization=authorization_from_environment(dict(os.environ)),
        root=archive_root,
        uploader=HuggingFaceFolderUploader(repository=target.repository),
        recorded_at=datetime.now(UTC),
    )
    (receipts / "uploaded.json").write_text(
        uploaded.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    verified = verify_publication(
        plan=plan,
        uploaded_receipt=uploaded,
        verifier=HuggingFaceAnonymousArtifactVerifier(
            timeout_seconds=verification_timeout_seconds
        ),
        recorded_at=datetime.now(UTC),
    )
    (receipts / "verified.json").write_text(
        verified.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return int(verified.state.value != "public")


def main() -> int:
    """Execute one approved bulk archive, never publish locally."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument(
        "--verification-timeout-seconds",
        type=int,
        default=DEFAULT_VERIFICATION_TIMEOUT_SECONDS,
    )
    args = parser.parse_args()
    return publish_bulk_archive(
        args.manifest,
        args.archive_root.resolve(strict=True),
        args.output,
        args.exact_commit,
        publish=args.publish,
        verification_timeout_seconds=args.verification_timeout_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
