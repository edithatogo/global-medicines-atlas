#!/usr/bin/env python3
"""Acquire one authorized Medstat export from GitHub Actions only."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import tomllib
from pathlib import Path
from urllib.request import urlopen

from global_medicines_atlas.medstat_private_acquisition import (
    CHECKSUM,
    MANIFEST,
    PRIVATE_ARCHIVE,
    PRIVATE_DATASET,
    SOURCE_ID,
    MedstatQuery,
    exercise_medstat_private_acquisition,
)
from global_medicines_atlas.reuse_gate import (
    ReuseGateDecision,
    evaluate_reuse_gate,
)
from global_medicines_atlas.source_catalog import load_source_catalog

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/nordic-utilisation-acquisition-authorization.json"
)
_HTTP_OK = 200


def _download(url: str) -> bytes:
    """Fetch the export through Chromium when the endpoint rejects urllib."""
    sync_api = importlib.import_module("playwright.sync_api")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "Chrome/140.0.0.0 Safari/537.36"
                )
            )
            with page.expect_download(timeout=180_000) as download_info:
                try:
                    response = page.goto(url, timeout=180_000)
                except sync_api.Error as error:
                    if "Download is starting" not in str(error):
                        raise
                else:
                    status = (
                        "no response"
                        if response is None
                        else str(response.status)
                    )
                    raise RuntimeError(
                        f"Medstat export did not start a download: {status}"
                    )
            path = download_info.value.path()
            if path is None:
                raise RuntimeError("Medstat export download has no local path")
            return Path(path).read_bytes()
        finally:
            browser.close()


def _github_index() -> dict[str, tuple[str, ...]]:
    """Read pinned maintainer repository trees before acquiring source bytes."""
    with (ROOT / ".context/ecosystem.toml").open("rb") as stream:
        ecosystem = tomllib.load(stream)
    index: dict[str, tuple[str, ...]] = {}
    for resource in ecosystem.get("github", []):
        repository = resource["repository"]
        revision = resource["snapshot"]
        url = f"https://api.github.com/repos/{repository}/git/trees/{revision}?recursive=1"
        with urlopen(url, timeout=60) as response:
            document = json.load(response)
        index[repository] = tuple(item["path"] for item in document["tree"])
    return index


def _huggingface_index() -> tuple[dict[str, tuple[str, ...]], dict[str, str]]:
    """Read declared Hugging Face repository trees before acquisition."""
    sdk = importlib.import_module("huggingface_hub")
    with (ROOT / ".context/ecosystem.toml").open("rb") as stream:
        ecosystem = tomllib.load(stream)
    api = sdk.HfApi()
    index: dict[str, tuple[str, ...]] = {}
    revisions: dict[str, str] = {}
    for resource in ecosystem.get("hugging_face", []):
        repository = resource["repository"]
        info = api.dataset_info(repository)
        if not info.sha:
            raise RuntimeError("Hugging Face reuse repository has no revision")
        entries = api.list_repo_tree(
            repository,
            repo_type="dataset",
            revision=info.sha,
            recursive=True,
        )
        index[repository] = tuple(entry.path for entry in entries)
        revisions[repository] = info.sha
    return index, revisions


def _reuse_decision() -> ReuseGateDecision:
    """Evaluate all required discovery surfaces before the Medstat download."""
    huggingface_index, huggingface_revisions = _huggingface_index()
    return evaluate_reuse_gate(
        SOURCE_ID,
        repository_root=ROOT,
        catalog=load_source_catalog(),
        github_index=_github_index(),
        huggingface_index=huggingface_index,
        huggingface_revisions=huggingface_revisions,
    )


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
    reuse_decision = _reuse_decision()
    payload = _download(query.export_url())
    manifest = exercise_medstat_private_acquisition(
        payload=payload,
        output_dir=output,
        authorization_path=AUTHORIZATION,
        query=query,
        reuse_decision=reuse_decision,
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
