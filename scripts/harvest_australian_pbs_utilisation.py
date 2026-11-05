#!/usr/bin/env python3
"""Governed Australian PBS Utilisation harvesting CLI.

Discovers and stages Date of Supply (DOS) prescription utilisation CSVs
and Annual Expenditure reports, uploading to Hugging Face exclusively from
GitHub Actions with anonymous clean-room verification.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.australian_harvesting import (
    ALLOWED_PBS_DOMAINS,
    DiscoveredHarvestResource,
    GovernedRedirectHandler,
    HarvestStageResult,
    build_cumulative_harvest_manifest,
    build_harvest_manifest,
    discover_pbs_dos_resources,
    discover_pbs_expenditure_resources,
    fetch_url_bytes_governed,
    stage_harvest_payload,
    validate_resources_against_contract,
    verify_anonymous_restore,
)

DATASET = "edithatogo/australian-pbs-utilisation-archive"
PAYLOAD_DOMAINS = ALLOWED_PBS_DOMAINS | frozenset({"data.gov.au"})
MAX_RAW_BYTES = 256 * 1024 * 1024
USER_AGENT = "GlobalMedicinesAtlas-PBSUtilisationHarvester/1.0"


def fetch_url_bytes(url: str) -> tuple[bytes, str]:
    return fetch_url_bytes_governed(
        url, allowed_domains=ALLOWED_PBS_DOMAINS, user_agent=USER_AGENT
    )


def fetch_url_text(url: str) -> str:
    content, _final_url = fetch_url_bytes(url)
    return content.decode("utf-8", errors="ignore")


def _extract_period_year(filename: str) -> int:
    years = [int(y) for y in re.findall(r"(?:19|20)\d{2}", filename)]
    return max(years) if years else 0


def discover_selected_resources(
    *, backfill_all: bool = False
) -> list[DiscoveredHarvestResource]:
    dos_html = fetch_url_text(
        "https://www.pbs.gov.au/statistics/dos-and-dop/dos-and-dop"
    )
    dos = discover_pbs_dos_resources(dos_html)

    exp_html = fetch_url_text(
        "https://www.pbs.gov.au/statistics/expenditure-prescriptions/pbs-expenditure-and-prescriptions"
    )
    exp = discover_pbs_expenditure_resources(
        exp_html,
        subpage_fetcher=fetch_url_text,
        max_subpages=64 if backfill_all else 2,
        include_documents=backfill_all,
    )
    all_res = dos + exp

    if backfill_all:
        frozen = json.loads(
            Path(
                "quality/qualifications/australian-pbs-backfill-authorized-resources-20261105.json"
            ).read_text(encoding="utf-8")
        )
        all_res.extend(
            DiscoveredHarvestResource(**r) for r in frozen["resources"]
        )
        return all_res

    dos_files = [
        r for r in dos if r.category == "date_of_supply_monthly_prescriptions"
    ]
    sorted_dos_periods = sorted(
        {_extract_period_year(r.filename) for r in dos_files},
        reverse=True,
    )
    top_periods = set(sorted_dos_periods[:2])

    selected: list[DiscoveredHarvestResource] = []
    for r in all_res:
        if r.category == "item_drug_mapping":
            selected.append(r)
        elif r.category == "date_of_supply_monthly_prescriptions":
            if _extract_period_year(r.filename) in top_periods:
                selected.append(r)
        elif r.category in {
            "date_of_supply_multiyear_summary",
            "annual_expenditure_and_prescriptions_report",
        }:
            selected.append(r)
    return selected


def fetch_payload(url: str) -> tuple[bytes, str]:
    """Read at most 256 MiB through a redirect-host governed connection."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in PAYLOAD_DOMAINS:
        raise ValueError("Payload URL must use HTTPS and an authorized host")
    opener = urllib.request.build_opener(
        GovernedRedirectHandler(PAYLOAD_DOMAINS)
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # ruff: ignore[suspicious-url-open-usage]
    with opener.open(request, timeout=90) as response:
        length_header = response.headers.get("Content-Length")
        expected_length = (
            int(length_header) if length_header is not None else None
        )
        if (
            expected_length is not None
            and not 0 <= expected_length <= MAX_RAW_BYTES
        ):
            raise ValueError("Advertised payload size exceeds raw bound")
        content = response.read(MAX_RAW_BYTES + 1)
        if len(content) > MAX_RAW_BYTES:
            raise ValueError("Raw payload exceeds 256 MiB bound")
        if expected_length is not None and len(content) != expected_length:
            raise ValueError("Truncated response: Content-Length mismatch")
        if "text/html" in response.headers.get("Content-Type", "").lower():
            raise ValueError("HTML response is not an aggregate data file")
        return content, str(response.url)


def inspect_raw_zip(payload: bytes, url: str) -> dict[str, Any]:
    """Inventory bounded source ZIP members without extracting source values."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = archive.infolist()
        member_limit = 20_000
        if (
            len(members) > member_limit
            or sum(m.file_size for m in members) > 4 * 1024**3
        ):
            raise ValueError("Historical ZIP exceeds raw archive bounds")
        return {
            "source_url": url,
            "members": [
                {"path": m.filename, "bytes": m.file_size, "crc32": m.CRC}
                for m in members
            ],
        }


def stage_resources(
    resources: list[DiscoveredHarvestResource], stage_dir: Path
) -> tuple[list[HarvestStageResult], dict[str, Any]]:
    """Stage immutable raw versions, retaining individual acquisition failures."""
    if not resources:
        raise ValueError("Cannot stage empty resources")
    stage_dir.mkdir(parents=True, exist_ok=True)
    stages: list[HarvestStageResult] = []
    failures: list[dict[str, str]] = []
    archive_inventory: list[dict[str, Any]] = []
    for resource in resources:
        try:  # ruff: ignore[too-many-statements-in-try-clause]
            payload, final_url = fetch_payload(resource.url)
            if resource.filename.lower().endswith(".zip"):
                archive_inventory.append(inspect_raw_zip(payload, resource.url))
            digest = hashlib.sha256(payload).hexdigest()
            parent = Path(resource.archive_path).parent
            versioned = resource.model_copy(
                update={
                    "archive_path": str(
                        parent / "versions" / digest / resource.filename
                    )
                }
            )
            stage = stage_harvest_payload(
                versioned,
                stage_dir,
                data_reader=lambda _url, data=payload, target=final_url: (
                    data,
                    target,
                ),
                allowed_domains=PAYLOAD_DOMAINS,
                raw_archive=True,
            )
            stages.append(stage)
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            failures.append({
                "source_id": resource.source_id,
                "filename": resource.filename,
                "error": str(exc),
            })
        print(
            f"Acquisition {len(stages) + len(failures)}/{len(resources)}",
            flush=True,
        )
    coverage = {
        "coverage_status": "partial" if failures else "complete",
        "failed_resources": failures,
    }
    (stage_dir / "coverage.json").write_text(
        json.dumps(coverage, indent=2) + "\n", encoding="utf-8"
    )
    manifest = build_harvest_manifest(DATASET, stages)
    manifest["run_coverage"] = coverage
    manifest["archive_inventory"] = archive_inventory
    (stage_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return stages, manifest


def _check_public_repo(info: Any) -> None:
    if info.private or info.gated:
        raise RuntimeError("Dataset must be anonymously public and non-gated")


def _fetch_existing_manifest(
    sdk: Any, public_api: Any, dataset: str
) -> tuple[str | None, dict[str, Any] | None]:
    try:
        info = public_api.dataset_info(dataset, files_metadata=True)
        _check_public_repo(info)
        parent_commit = str(info.sha)
    except Exception:
        return None, None

    try:
        cached = sdk.hf_hub_download(
            repo_id=dataset,
            repo_type="dataset",
            filename="manifest.json",
            revision=parent_commit,
            token=False,
        )
        return parent_commit, json.loads(
            Path(cached).read_text(encoding="utf-8")
        )
    except Exception:
        return parent_commit, None


def publish_to_huggingface(
    stages: list[HarvestStageResult],
    manifest: dict[str, Any],
    stage_dir: Path,
    hf_token: str,
) -> tuple[str, dict[str, Any]]:
    if not stages or manifest.get("file_count", 0) <= 0:
        raise ValueError("Cannot publish an empty harvest")

    sdk: Any = importlib.import_module("huggingface_hub")
    api: Any = sdk.HfApi(token=hf_token)
    public_api: Any = sdk.HfApi(token=False)

    parent_commit, existing_manifest = _fetch_existing_manifest(
        sdk, public_api, DATASET
    )
    if parent_commit is None or existing_manifest is None:
        raise RuntimeError("Existing archive parent could not be qualified")
    existing_files = {
        f["path"]: f for f in (existing_manifest or {}).get("files", [])
    }
    stages = [
        stage
        for stage in stages
        if existing_files.get(stage.resource.archive_path, {}).get("sha256")
        != stage.receipt.sha256
    ]
    if not stages:
        raise RuntimeError("No new immutable payloads; archive unchanged")
    cumulative_manifest = build_cumulative_harvest_manifest(
        DATASET,
        stages,
        existing_manifest,
        run_coverage=manifest.get("run_coverage"),
    )
    manifest_path = stage_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(cumulative_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    operations: list[Any] = []
    for s in stages:
        operations.append(
            sdk.CommitOperationAdd(
                path_in_repo=s.resource.archive_path,
                path_or_fileobj=str(s.staged_payload_path),
            )
        )
        receipt_path = (
            s.resource.archive_path.replace("raw/", "bronze/") + ".receipt.json"
        )
        operations.append(
            sdk.CommitOperationAdd(
                path_in_repo=receipt_path,
                path_or_fileobj=str(s.staged_receipt_path),
            )
        )
    operations.append(
        sdk.CommitOperationAdd(
            path_in_repo="manifest.json",
            path_or_fileobj=str(manifest_path),
        )
    )

    commit_res: Any = api.create_commit(
        repo_id=DATASET,
        repo_type="dataset",
        parent_commit=parent_commit,
        commit_message="Harvest Australian PBS utilisation data (DOS & annual reports)",
        operations=operations,
    )
    published_revision = str(commit_res.oid)

    def anonymous_get(repo: str, filepath: str) -> bytes:
        cached = cast(
            "str",
            sdk.hf_hub_download(
                repo_id=repo,
                repo_type="dataset",
                revision=published_revision,
                filename=filepath,
                token=False,
            ),
        )
        return Path(cached).read_bytes()

    verify_anonymous_restore(
        DATASET, cumulative_manifest, anonymous_downloader=anonymous_get
    )
    return published_revision, cumulative_manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Harvest Australian PBS utilisation data"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover resources without staging",
    )
    parser.add_argument(
        "--stage-dir", type=Path, default=Path("build/harvest/pbs_utilisation")
    )
    parser.add_argument(
        "--publish-hosted",
        action="store_true",
        help="Publish staged files to Hugging Face (Actions only)",
    )
    parser.add_argument(
        "--backfill-all",
        action="store_true",
        help="Stage all historical annual files instead of just rolling year",
    )
    parser.add_argument(
        "--receipt-output",
        type=Path,
        default=Path("build/pbs-utilisation-harvest-receipt.json"),
    )
    args = parser.parse_args()

    contract_path = Path(
        "quality/qualifications/australian-pbs-utilisation-publication-authorization.json"
    )
    backfill_enabled = (
        args.backfill_all or os.environ.get("BACKFILL_ALL") == "1"
    )
    resources = discover_selected_resources(backfill_all=backfill_enabled)
    validate_resources_against_contract(contract_path, DATASET, resources)
    print(f"Selected {len(resources)} PBS utilisation resources.")

    if args.dry_run:
        return 0

    if args.publish_hosted and not os.environ.get("GITHUB_ACTIONS"):
        raise PermissionError(
            "--publish-hosted is permitted only within GitHub Actions runners."
        )

    stages, manifest = stage_resources(resources, args.stage_dir)
    print(
        f"Staged {len(stages)} payloads. Manifest has {manifest['file_count']} objects."
    )

    if not args.publish_hosted:
        return 0

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        raise ValueError(
            "HF_TOKEN environment variable required for hosted publication"
        )

    revision, final_manifest = publish_to_huggingface(
        stages, manifest, args.stage_dir, hf_token
    )

    receipt_record = {
        "schema_id": "global-medicines-atlas.australian-pbs-utilisation-harvest-receipt",
        "dataset": DATASET,
        "revision": revision,
        "workflow_run": os.environ.get("GITHUB_RUN_ID", "local"),
        "workflow_commit": os.environ.get("GITHUB_SHA", "local"),
        "anonymous_digest_verification": "passed",
        "verified_file_count": final_manifest["file_count"],
        "temporary_source_bytes_removed": False,
        "run_coverage": manifest.get("run_coverage"),
        "archive_inventory": manifest.get("archive_inventory"),
    }
    args.receipt_output.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_output.write_text(
        json.dumps(receipt_record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
