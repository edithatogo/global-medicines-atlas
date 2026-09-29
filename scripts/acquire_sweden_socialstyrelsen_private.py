#!/usr/bin/env python3
"""Acquire the approved Socialstyrelsen aggregate through GitHub Actions only."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import tomllib
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import httpx

from global_medicines_atlas.reuse_gate import (
    ReuseGateDecision,
    evaluate_reuse_gate,
)
from global_medicines_atlas.source_catalog import load_source_catalog
from global_medicines_atlas.sweden_socialstyrelsen_acquisition import (
    CHECKSUM,
    MANIFEST,
    PRIVATE_ARCHIVE,
    PRIVATE_DATASET,
    SOURCE_ID,
    SwedenQuery,
    exercise_sweden_private_acquisition,
    require_sweden_authorization,
)

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION = (
    ROOT
    / "quality/qualifications/nordic-utilisation-acquisition-authorization.json"
)
OUT = ROOT / "build/socialstyrelsen-private"
HTTP_OK = 200
MAX_RESPONSE_BYTES = 25_000_000


def fetch_socialstyrelsen_response(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "sdb.socialstyrelsen.se":
        raise ValueError(
            "Socialstyrelsen API host is outside the approved allowlist"
        )
    with httpx.Client(timeout=45, follow_redirects=False) as client:
        response = client.get(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "GlobalMedicinesAtlas/1.0",
            },
        )
    if response.status_code != HTTP_OK:
        raise RuntimeError(
            f"Socialstyrelsen API returned HTTP {response.status_code}"
        )
    data = response.content
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("Socialstyrelsen response exceeds the 25 MB bound")
    return data


def _reuse_decision(token: str) -> ReuseGateDecision:
    """Search every declared maintainer surface before fetching result data."""
    sdk = importlib.import_module("huggingface_hub")
    api = sdk.HfApi(token=token)
    with (ROOT / ".context/ecosystem.toml").open("rb") as stream:
        ecosystem = tomllib.load(stream)
    github_index: dict[str, tuple[str, ...]] = {}
    for resource in ecosystem.get("github", []):
        repository = resource["repository"]
        revision = resource["snapshot"]
        url = f"https://api.github.com/repos/{repository}/git/trees/{revision}?recursive=1"
        with urlopen(url, timeout=60) as response:
            document = json.load(response)
        github_index[repository] = tuple(
            item["path"] for item in document["tree"]
        )
    huggingface_index: dict[str, tuple[str, ...]] = {}
    huggingface_revisions: dict[str, str] = {}
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
        huggingface_index[repository] = tuple(entry.path for entry in entries)
        huggingface_revisions[repository] = info.sha
    return evaluate_reuse_gate(
        SOURCE_ID,
        repository_root=ROOT,
        catalog=load_source_catalog(),
        github_index=github_index,
        huggingface_index=huggingface_index,
        huggingface_revisions=huggingface_revisions,
    )


def _upload_private_archive(output: Path, token: str) -> str:
    """Create or verify private non-gated retention and the exact object set."""
    sdk = importlib.import_module("huggingface_hub")
    errors = importlib.import_module("huggingface_hub.errors")
    api = sdk.HfApi(token=token)
    try:
        existing = api.dataset_info(PRIVATE_DATASET)
    except errors.RepositoryNotFoundError:
        existing = None
    if existing is not None and (not existing.private or existing.gated):
        raise RuntimeError(
            "Sweden destination must remain private and non-gated"
        )
    if existing is None:
        api.create_repo(
            PRIVATE_DATASET,
            repo_type="dataset",
            private=True,
            exist_ok=False,
        )
    for filename in (PRIVATE_ARCHIVE, MANIFEST, CHECKSUM):
        api.upload_file(
            path_or_fileobj=output / filename,
            path_in_repo=filename,
            repo_id=PRIVATE_DATASET,
            repo_type="dataset",
            commit_message="Retain authorized Socialstyrelsen aggregate privately",
        )
    info = api.dataset_info(PRIVATE_DATASET)
    if not info.private or info.gated or not info.sha:
        raise RuntimeError(
            "Sweden private archive visibility verification failed"
        )
    names = {item.rfilename for item in info.siblings}
    expected = {PRIVATE_ARCHIVE, MANIFEST, CHECKSUM, ".gitattributes"}
    if names != expected:
        raise RuntimeError("Sweden private archive object set drifted")
    hosted = sdk.hf_hub_download(
        repo_id=PRIVATE_DATASET,
        filename=PRIVATE_ARCHIVE,
        repo_type="dataset",
        token=token,
        revision=info.sha,
        force_download=True,
    )
    hosted_bytes = Path(hosted).read_bytes()
    expected_checksum = next(
        line.split()[0]
        for line in (output / CHECKSUM).read_text(encoding="utf-8").splitlines()
        if line.endswith(PRIVATE_ARCHIVE)
    )
    if sha256(hosted_bytes).hexdigest() != expected_checksum:
        raise RuntimeError("authenticated hosted archive digest did not match")
    if len(hosted_bytes) != (output / PRIVATE_ARCHIVE).stat().st_size:
        raise RuntimeError(
            "authenticated hosted archive byte count did not match"
        )
    return info.sha


def main() -> int:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit(
            "Socialstyrelsen acquisition is permitted only in GitHub Actions"
        )
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN is required for private retention")
    require_sweden_authorization(AUTHORIZATION)
    query = SwedenQuery()
    reuse = _reuse_decision(token)
    payloads = tuple(
        fetch_socialstyrelsen_response(url) for url in query.source_urls()
    )
    manifest = exercise_sweden_private_acquisition(
        payloads=payloads,
        output_dir=OUT,
        authorization_path=AUTHORIZATION,
        reuse_decision=reuse,
        query=query,
    )
    revision = _upload_private_archive(OUT, token)
    shutil.rmtree(OUT)
    print(
        json.dumps(
            {
                "source_id": SOURCE_ID,
                "acquisition_id": manifest.acquisition_id,
                "payload_sha256": list(manifest.payload_sha256),
                "payload_byte_count": list(manifest.payload_byte_count),
                "archive_sha256": manifest.archive_sha256,
                "archive_byte_count": manifest.archive_byte_count,
                "private_dataset": PRIVATE_DATASET,
                "private_revision": revision,
                "public_release_authorized": False,
                "external_publication_authorized": False,
                "private_hosted_digest_verified": True,
                "temporary_source_bytes_removed": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
