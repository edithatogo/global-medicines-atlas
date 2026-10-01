#!/usr/bin/env python3
"""Acquire one authorized historic NorPD report from GitHub Actions only."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import ssl
import tomllib
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import httpx

from global_medicines_atlas.norpd_private_acquisition import (
    CHECKSUM,
    MANIFEST,
    PRIVATE_ARCHIVE,
    PRIVATE_DATASET,
    REPORT_URL,
    SOURCE_ID,
    exercise_norpd_private_acquisition,
    require_norpd_authorization,
)
from global_medicines_atlas.receipts import (
    HttpRetrievalEvidence,
    http_retrieval_from_response,
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
OUT = ROOT / "build/norpd-private"
HTTP_OK = 200


def _reuse_decision(token: str) -> ReuseGateDecision:
    sdk = importlib.import_module("huggingface_hub")
    api = sdk.HfApi(token=token)
    with (ROOT / ".context/ecosystem.toml").open("rb") as stream:
        ecosystem = tomllib.load(stream)
    github_index: dict[str, tuple[str, ...]] = {}
    for resource in ecosystem.get("github", []):
        repository = resource["repository"]
        revision = resource["snapshot"]
        url = f"https://api.github.com/repos/{repository}/git/trees/{revision}?recursive=1"
        with urlopen(
            url, timeout=60, context=ssl.create_default_context()
        ) as response:
            document = json.load(response)
        github_index[repository] = tuple(
            item["path"] for item in document["tree"]
        )
    hf_index: dict[str, tuple[str, ...]] = {}
    revisions: dict[str, str] = {}
    for resource in ecosystem.get("hugging_face", []):
        repository = resource["repository"]
        info = api.dataset_info(repository)
        if not info.sha:
            raise RuntimeError("reuse repository has no pinned revision")
        entries = api.list_repo_tree(
            repository, repo_type="dataset", revision=info.sha, recursive=True
        )
        hf_index[repository] = tuple(entry.path for entry in entries)
        revisions[repository] = info.sha
    return evaluate_reuse_gate(
        SOURCE_ID,
        repository_root=ROOT,
        catalog=load_source_catalog(),
        github_index=github_index,
        huggingface_index=hf_index,
        huggingface_revisions=revisions,
    )


def _fetch_report() -> tuple[bytes, HttpRetrievalEvidence]:
    parsed = urlparse(REPORT_URL)
    if parsed.scheme != "https" or parsed.hostname != "www.fhi.no":
        raise ValueError("NorPD report host is outside the approved allowlist")
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        response = client.get(REPORT_URL, headers={"Accept": "application/pdf"})
    if response.status_code != HTTP_OK:
        raise RuntimeError(f"NIPH report returned HTTP {response.status_code}")
    payload = response.content
    evidence = http_retrieval_from_response(
        response,
        original_uri=REPORT_URL,
        observed_byte_length=len(payload),
        agent_version="gma-norpd-private/1",
    )
    return payload, evidence


def _upload_private_archive(token: str) -> str:
    sdk = importlib.import_module("huggingface_hub")
    errors = importlib.import_module("huggingface_hub.errors")
    api = sdk.HfApi(token=token)
    try:
        existing = api.dataset_info(PRIVATE_DATASET)
    except errors.RepositoryNotFoundError:
        existing = None
    if existing is not None and (not existing.private or existing.gated):
        raise RuntimeError(
            "NorPD destination must remain private and non-gated"
        )
    if existing is None:
        api.create_repo(
            PRIVATE_DATASET, repo_type="dataset", private=True, exist_ok=False
        )
    for filename in (PRIVATE_ARCHIVE, MANIFEST, CHECKSUM):
        api.upload_file(
            path_or_fileobj=OUT / filename,
            path_in_repo=filename,
            repo_id=PRIVATE_DATASET,
            repo_type="dataset",
            commit_message="Retain authorized historic NorPD report privately",
        )
    info = api.dataset_info(PRIVATE_DATASET)
    if not info.private or info.gated or not info.sha:
        raise RuntimeError(
            "NorPD private archive visibility verification failed"
        )
    names = {item.rfilename for item in info.siblings}
    if names != {PRIVATE_ARCHIVE, MANIFEST, CHECKSUM, ".gitattributes"}:
        raise RuntimeError("NorPD private archive object set drifted")
    hosted = sdk.hf_hub_download(
        repo_id=PRIVATE_DATASET,
        filename=PRIVATE_ARCHIVE,
        repo_type="dataset",
        token=token,
        revision=info.sha,
        force_download=True,
    )
    local_archive = OUT / PRIVATE_ARCHIVE
    remote_bytes = Path(hosted).read_bytes()
    if (
        sha256(remote_bytes).hexdigest()
        != sha256(local_archive.read_bytes()).hexdigest()
    ):
        raise RuntimeError("authenticated hosted archive digest did not match")
    if len(remote_bytes) != local_archive.stat().st_size:
        raise RuntimeError(
            "authenticated hosted archive byte count did not match"
        )
    return info.sha


def main() -> int:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit(
            "NorPD acquisition is permitted only in GitHub Actions"
        )
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN is required for private retention")
    require_norpd_authorization(AUTHORIZATION)
    reuse = _reuse_decision(token)
    payload, http_evidence = _fetch_report()
    manifest = exercise_norpd_private_acquisition(
        payload=payload,
        output_dir=OUT,
        authorization_path=AUTHORIZATION,
        reuse_decision=reuse,
        http_evidence=http_evidence,
    )
    revision = _upload_private_archive(token)
    try:
        shutil.rmtree(OUT)
    except OSError as error:
        raise RuntimeError(
            "temporary NorPD payload cleanup failed; discard this hosted runner"
        ) from error
    if OUT.exists():
        raise RuntimeError(
            "temporary NorPD payload directory remains after cleanup"
        )
    print(
        json.dumps(
            {
                "source_id": SOURCE_ID,
                "acquisition_id": manifest.acquisition_id,
                "report_period": manifest.report_period,
                "payload_sha256": manifest.payload_sha256,
                "payload_byte_count": manifest.payload_byte_count,
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
