#!/usr/bin/env python3
"""Acquire one authorized Medstat export from GitHub Actions only."""

from __future__ import annotations

import importlib
import json
import os
import shutil
from pathlib import Path
from urllib.request import urlopen

from global_medicines_atlas.medstat_private_acquisition import (
    CHECKSUM,
    MANIFEST,
    PRIVATE_ARCHIVE,
    PRIVATE_DATASET,
    MedstatQuery,
    exercise_medstat_private_acquisition,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/nordic-utilisation-acquisition-authorization.json"
)


def _download(url: str) -> bytes:
    with urlopen(url, timeout=180) as response:  # ruff: ignore[suspicious-url-open-usage]
        return response.read()


def _upload_private_archive(output: Path, token: str) -> str:
    sdk = importlib.import_module("huggingface_hub")
    errors = importlib.import_module("huggingface_hub.errors")
    api = sdk.HfApi(token=token)
    try:
        existing = api.dataset_info(PRIVATE_DATASET)
    except errors.RepositoryNotFoundError:
        existing = None
    if existing is not None and (not existing.private or existing.gated):
        raise RuntimeError(
            "Medstat destination must remain private and non-gated"
        )
    if existing is None:
        api.create_repo(
            PRIVATE_DATASET,
            repo_type="dataset",
            private=True,
            exist_ok=False,
        )
    api.upload_folder(
        repo_id=PRIVATE_DATASET,
        repo_type="dataset",
        folder_path=output,
        commit_message="Retain authorized Medstat aggregate archive",
        delete_patterns=["*"],
    )
    info = api.dataset_info(PRIVATE_DATASET)
    if not info.private or info.gated or not info.sha:
        raise RuntimeError(
            "Medstat private archive visibility verification failed"
        )
    names = {sibling.rfilename for sibling in info.siblings}
    expected = {PRIVATE_ARCHIVE, MANIFEST, CHECKSUM, ".gitattributes"}
    if names != expected:
        raise RuntimeError("Medstat private archive object set drifted")
    return info.sha


def main() -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError(
            "Medstat source bytes may be acquired from GitHub Actions only"
        )
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is required for private Medstat retention")
    output = ROOT / "work" / "medstat-private"
    shutil.rmtree(output, ignore_errors=True)
    query = MedstatQuery()
    payload = _download(query.export_url())
    manifest = exercise_medstat_private_acquisition(
        payload=payload,
        output_dir=output,
        authorization_path=AUTHORIZATION,
        query=query,
    )
    revision = _upload_private_archive(output, token)
    receipt = {
        "source_id": manifest.source_id,
        "acquisition_id": manifest.acquisition_id,
        "payload_sha256": manifest.payload_sha256,
        "payload_byte_count": manifest.payload_byte_count,
        "archive_sha256": manifest.archive_sha256,
        "archive_byte_count": manifest.archive_byte_count,
        "private_dataset": manifest.private_dataset,
        "private_revision": revision,
        "public_release_authorized": False,
        "external_publication_authorized": False,
    }
    shutil.rmtree(output)
    if output.exists():
        raise RuntimeError("Medstat runner payload cleanup failed")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
