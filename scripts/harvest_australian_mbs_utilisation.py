#!/usr/bin/env python3
"""Governed Australian MBS Utilisation harvesting CLI.

Discovers and stages Department of Health Medicare statistics workbooks
and data.gov.au MBS group and demographic utilisation datasets, uploading
to Hugging Face exclusively from GitHub Actions with anonymous clean-room verification.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.australian_harvesting import (
    ALLOWED_MEDICARE_STATISTICS_DOMAINS,
    DiscoveredHarvestResource,
    HarvestStageResult,
    build_harvest_manifest,
    discover_mbs_utilisation_resources,
    stage_harvest_payload,
    verify_anonymous_restore,
)

DATASET = "edithatogo/australian-mbs-utilisation-archive"
USER_AGENT = "GlobalMedicinesAtlas-MBSUtilisationHarvester/1.0"

HEALTH_GOV_MEDICARE_FILES = [
    "https://www.health.gov.au/sites/default/files/2026-08/medicare-quarterly-statistics-state-and-territory-june-quarter-2025-26.xlsx",
    "https://www.health.gov.au/sites/default/files/2026-08/medicare-annual-statistics-state-and-territory-2009-10-to-2024-25.xlsx",
    "https://www.health.gov.au/sites/default/files/2026-08/medicare-statistics-year-to-date-summary-tables-july-to-june-2025-26.xlsx",
]

DATA_GOV_MBS_GROUP_API = (
    "https://data.gov.au/data/api/3/action/package_show?id=medicare-benefits-schedule-mbs-group"
)
DATA_GOV_MBS_DEMOGRAPHICS_API = (
    "https://data.gov.au/data/api/3/action/package_show?id=medicare-benefits-schedule-mbs-group-by-patient-demographics-report"
)


def fetch_url_bytes(url: str) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported scheme: {parsed.scheme}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # ruff: ignore[suspicious-url-open-usage]
    with urllib.request.urlopen(req, timeout=120) as resp:  # ruff: ignore[suspicious-url-open-usage]
        return resp.read()


def fetch_url_json(url: str) -> dict[str, Any]:
    raw = fetch_url_bytes(url)
    return json.loads(raw.decode("utf-8", errors="ignore"))


def check_contract(contract_path: Path) -> None:
    if not contract_path.exists():
        raise FileNotFoundError(f"Missing authorization contract at {contract_path}")
    contract: dict[str, Any] = json.loads(contract_path.read_text(encoding="utf-8"))
    if not contract.get("external_publication_authorized"):
        raise PermissionError("external_publication_authorized is False in contract")


def discover_selected_resources(*, backfill_all: bool = False) -> list[DiscoveredHarvestResource]:
    group_json = None
    demographics_json = None
    try:
        group_json = fetch_url_json(DATA_GOV_MBS_GROUP_API)
    except Exception as exc:
        print(f"Warning: could not fetch MBS group API from data.gov.au: {exc}", file=sys.stderr)

    if backfill_all:
        try:
            demographics_json = fetch_url_json(DATA_GOV_MBS_DEMOGRAPHICS_API)
        except Exception as exc:
            print(f"Warning: could not fetch MBS demographics API: {exc}", file=sys.stderr)

    max_hist = 20 if backfill_all else 2
    return discover_mbs_utilisation_resources(
        data_gov_group_json=group_json,
        data_gov_demographics_json=demographics_json,
        health_gov_urls=HEALTH_GOV_MEDICARE_FILES,
        max_historical_files=max_hist,
    )


def stage_resources(
    resources: list[DiscoveredHarvestResource], stage_dir: Path
) -> tuple[list[HarvestStageResult], dict[str, Any]]:
    stage_dir.mkdir(parents=True, exist_ok=True)
    stages: list[HarvestStageResult] = []
    for r in resources:
        stage = stage_harvest_payload(
            r,
            stage_dir,
            data_reader=fetch_url_bytes,
            allowed_domains=ALLOWED_MEDICARE_STATISTICS_DOMAINS,
        )
        stages.append(stage)

    manifest = build_harvest_manifest(DATASET, stages)
    manifest_path = stage_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return stages, manifest


def _check_public_repo(info: Any) -> None:
    if info.private or info.gated:
        raise RuntimeError("Dataset must be anonymously public and non-gated")


def publish_to_huggingface(
    stages: list[HarvestStageResult],
    manifest: dict[str, Any],
    stage_dir: Path,
    hf_token: str,
) -> str:
    sdk: Any = importlib.import_module("huggingface_hub")
    api: Any = sdk.HfApi(token=hf_token)
    public_api: Any = sdk.HfApi(token=False)

    try:
        info: Any = public_api.dataset_info(DATASET, files_metadata=True)
        _check_public_repo(info)
        parent_commit: str | None = str(info.sha)
    except Exception:
        api.create_repo(repo_id=DATASET, repo_type="dataset", private=False)
        parent_commit = None

    operations: list[Any] = []
    for s in stages:
        operations.append(sdk.CommitOperationAdd(path_in_repo=s.resource.archive_path, path_or_fileobj=str(s.staged_payload_path)))
        receipt_path = s.resource.archive_path.replace("raw/", "bronze/") + ".receipt.json"
        operations.append(sdk.CommitOperationAdd(path_in_repo=receipt_path, path_or_fileobj=str(s.staged_receipt_path)))
    operations.append(sdk.CommitOperationAdd(path_in_repo="manifest.json", path_or_fileobj=str(stage_dir / "manifest.json")))

    commit_res: Any = api.create_commit(
        repo_id=DATASET,
        repo_type="dataset",
        parent_commit=parent_commit,
        commit_message="Harvest Australian MBS utilisation data (Medicare statistics and group reports)",
        operations=operations,
    )
    published_revision = str(commit_res.oid)

    def anonymous_get(repo: str, filepath: str) -> bytes:
        cached = cast("str", sdk.hf_hub_download(repo_id=repo, repo_type="dataset", revision=published_revision, filename=filepath, token=False))
        return Path(cached).read_bytes()

    verify_anonymous_restore(DATASET, manifest, anonymous_downloader=anonymous_get)
    return published_revision


def main() -> int:
    parser = argparse.ArgumentParser(description="Harvest Australian MBS utilisation data")
    parser.add_argument("--dry-run", action="store_true", help="Discover resources without staging")
    parser.add_argument("--stage-dir", type=Path, default=Path("build/harvest/mbs_utilisation"))
    parser.add_argument("--publish-hosted", action="store_true", help="Publish staged files to Hugging Face (Actions only)")
    parser.add_argument("--backfill-all", action="store_true", help="Stage all historical demographic/group files")
    parser.add_argument("--receipt-output", type=Path, default=Path("build/mbs-utilisation-harvest-receipt.json"))
    args = parser.parse_args()

    contract_path = Path("quality/qualifications/australian-mbs-utilisation-publication-authorization.json")
    check_contract(contract_path)

    backfill_enabled = args.backfill_all or os.environ.get("BACKFILL_ALL") == "1"
    resources = discover_selected_resources(backfill_all=backfill_enabled)
    print(f"Selected {len(resources)} MBS utilisation resources.")

    if args.dry_run:
        return 0

    if args.publish_hosted and not os.environ.get("GITHUB_ACTIONS"):
        raise PermissionError("--publish-hosted is permitted only within GitHub Actions runners.")

    stages, manifest = stage_resources(resources, args.stage_dir)
    print(f"Staged {len(stages)} payloads. Manifest has {manifest['file_count']} objects.")

    if not args.publish_hosted:
        return 0

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        raise ValueError("HF_TOKEN environment variable required for hosted publication")

    revision = publish_to_huggingface(stages, manifest, args.stage_dir, hf_token)

    receipt_record = {
        "schema_id": "global-medicines-atlas.australian-mbs-utilisation-harvest-receipt",
        "dataset": DATASET,
        "revision": revision,
        "workflow_run": os.environ.get("GITHUB_RUN_ID", "local"),
        "workflow_commit": os.environ.get("GITHUB_SHA", "local"),
        "anonymous_digest_verification": "passed",
        "verified_file_count": manifest["file_count"],
        "temporary_source_bytes_removed": False,
    }
    args.receipt_output.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_output.write_text(json.dumps(receipt_record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
