"""Governed discovery, staging, and verification for Australian PBS/MBS harvesting.

Separates policy schedule/listing data from empirical utilisation data.
Adheres strictly to the Global Medicines Atlas fail-closed contracts.
"""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

ALLOWED_PBS_DOMAINS = frozenset({
    "www.pbs.gov.au",
    "pbs.gov.au",
    "data.pbs.gov.au",
})
ALLOWED_MBS_DOMAINS = frozenset({"www.mbsonline.gov.au", "mbsonline.gov.au"})
ALLOWED_MEDICARE_STATISTICS_DOMAINS = frozenset({
    "www.health.gov.au",
    "health.gov.au",
    "data.gov.au",
})
ALLOWED_AUSTRALIAN_HARVEST_DOMAINS = (
    ALLOWED_PBS_DOMAINS
    | ALLOWED_MBS_DOMAINS
    | ALLOWED_MEDICARE_STATISTICS_DOMAINS
)


class DiscoveredHarvestResource(BaseModel):
    """One discovered remote resource candidate for harvesting."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    category: str
    url: str
    filename: str
    archive_path: str
    period_label: str = ""


class HarvestPayloadReceipt(BaseModel):
    """B1 acquisition receipt for a single harvested payload."""

    model_config = ConfigDict(frozen=True)

    schema_id: str = "global-medicines-atlas.australian-harvest-receipt"
    schema_version: int = 1
    source_id: str
    category: str
    source_url: str
    archive_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(ge=0)
    period_label: str = ""
    retrieved_at: str


@dataclass(frozen=True)
class HarvestStageResult:
    """Staged local payload and its verified B1 receipt."""

    resource: DiscoveredHarvestResource
    staged_payload_path: Path
    staged_receipt_path: Path
    receipt: HarvestPayloadReceipt


def discover_pbs_dos_resources(
    html: str,
    base_url: str = "https://www.pbs.gov.au/statistics/dos-and-dop/dos-and-dop",
) -> list[DiscoveredHarvestResource]:
    """Discover PBS Date of Supply (DOS) dispensing utilisation files from HTML."""
    links = re.findall(
        r"href=[\"\']([^\"\']+\.(?:csv|xlsx?|zip))[\"\']", html, re.IGNORECASE
    )
    discovered: list[DiscoveredHarvestResource] = []
    seen: set[str] = set()

    for rel in sorted(links):
        full_url = urllib.parse.urljoin(base_url, rel)
        filename = full_url.split("/")[-1]
        if filename in seen:
            continue
        seen.add(filename)

        if "dos-" in filename.lower() and filename.lower().endswith(".csv"):
            period = filename.replace("dos-", "").replace(
                "-phrmcy-type.csv", ""
            )
            archive_path = f"raw/pbs/utilisation/dos/{filename}"
            category = "date_of_supply_monthly_prescriptions"
        elif "pbs-item-drug-map" in filename.lower():
            period = "reference"
            archive_path = f"raw/pbs/utilisation/reference/{filename}"
            category = "item_drug_mapping"
        elif "dos-" in filename.lower() and filename.lower().endswith(".xlsx"):
            period = filename.replace("dos-", "").replace(".xlsx", "")
            archive_path = f"raw/pbs/utilisation/summary/{filename}"
            category = "date_of_supply_multiyear_summary"
        elif "dop-" in filename.lower():
            period = "processing_historical"
            archive_path = f"raw/pbs/utilisation/dop/{filename}"
            category = "date_of_processing_historical"
        else:
            period = "other"
            archive_path = f"raw/pbs/utilisation/misc/{filename}"
            category = "pbs_utilisation_supplement"

        discovered.append(
            DiscoveredHarvestResource(
                source_id="au-pbs-dos-utilisation",
                category=category,
                url=full_url,
                filename=filename,
                archive_path=archive_path,
                period_label=period,
            )
        )
    return discovered


def discover_pbs_expenditure_resources(
    index_html: str,
    subpage_fetcher: Callable[[str], str],
    base_url: str = (
        "https://www.pbs.gov.au/statistics/expenditure-prescriptions/"
        "pbs-expenditure-and-prescriptions"
    ),
    max_subpages: int = 3,
) -> list[DiscoveredHarvestResource]:
    """Discover PBS Annual Expenditure workbooks across annual subpages."""
    subpage_links = re.findall(
        r"href=[\"\'](expenditure-prescriptions[^\"]*|pbs-expenditure[^\"]*)[\"\']",
        index_html,
        re.IGNORECASE,
    )

    def _exp_sort_key(subpage: str) -> tuple[int, str]:
        years = [int(y) for y in re.findall(r"(?:19|20)\d{2}", subpage)]
        return (max(years) if years else 0, subpage)

    unique_subpages = sorted(
        set(subpage_links), key=_exp_sort_key, reverse=True
    )[:max_subpages]
    discovered: list[DiscoveredHarvestResource] = []
    seen: set[str] = set()

    for sp in unique_subpages:
        sp_url = urllib.parse.urljoin(base_url, sp)
        try:
            sp_html = subpage_fetcher(sp_url)
        except OSError, TimeoutError, ValueError:
            continue

        files = re.findall(
            r"href=[\"\']([^\"\']+\.(?:xlsx?|csv))[\"\']",
            sp_html,
            re.IGNORECASE,
        )
        for f in sorted(set(files)):
            full_url = urllib.parse.urljoin(sp_url, f)
            filename = full_url.split("/")[-1]
            if filename in seen:
                continue
            seen.add(filename)

            # Match primary expenditure spreadsheets
            if any(k in filename.lower() for k in ["expenditure", "exp-prs"]):
                archive_path = f"raw/pbs/expenditure/{filename}"
                discovered.append(
                    DiscoveredHarvestResource(
                        source_id="au-pbs-expenditure",
                        category="annual_expenditure_and_prescriptions_report",
                        url=full_url,
                        filename=filename,
                        archive_path=archive_path,
                        period_label=sp,
                    )
                )
    return discovered


def discover_mbs_schedule_resources(
    index_html: str,
    subpage_fetcher: Callable[[str], str],
    base_url: str = (
        "https://www.mbsonline.gov.au/internet/mbsonline/publishing.nsf/Content/Downloads"
    ),
    max_releases: int = 3,
) -> list[DiscoveredHarvestResource]:
    """Discover monthly MBS schedule releases from mbsonline.gov.au."""
    release_pages = re.findall(
        r"href=[\"\']([^\"\']*Downloads-(?:20\d{6}|\d{6})[^\"]*)[\"\']",
        index_html,
        re.IGNORECASE,
    )

    def _mbs_sort_key(page: str) -> tuple[int, str]:
        m8 = re.search(r"Downloads-([12]\d{7})", page, re.IGNORECASE)
        if m8:
            return (int(m8.group(1)), page)
        m6 = re.search(r"Downloads-(\d{6})", page, re.IGNORECASE)
        if m6:
            return (20000000 + int(m6.group(1)), page)
        return (0, page)

    unique_releases = sorted(
        set(release_pages), key=_mbs_sort_key, reverse=True
    )[:max_releases]
    discovered: list[DiscoveredHarvestResource] = []
    seen: set[str] = set()

    for rp in unique_releases:
        rp_url = urllib.parse.urljoin(base_url, rp)
        try:
            rp_html = subpage_fetcher(rp_url)
        except OSError, TimeoutError, ValueError:
            continue

        files = re.findall(
            r"href=[\"\']([^\"\']+\.(?:xml|csv|txt|zip))[\"\']",
            rp_html,
            re.IGNORECASE,
        )
        for f in sorted(set(files)):
            # Skip RSS feeds, templates, and styles
            if any(
                skip in f.lower()
                for skip in ["rss", "latestnews", "template", ".css"]
            ):
                continue
            full_url = urllib.parse.urljoin(rp_url, f)
            filename = urllib.parse.unquote(full_url.split("/")[-1])
            if filename in seen:
                continue
            seen.add(filename)

            if "mbs-xml" in filename.lower() and filename.lower().endswith(
                ".xml"
            ):
                cat = "monthly_schedule_xml"
                arch_path = f"raw/mbs/releases/{rp}/{filename}"
            elif "basic service description" in filename.lower():
                cat = "basic_service_description"
                arch_path = f"raw/mbs/bsd/{rp}/{filename}"
            elif "rvg" in filename.lower():
                cat = "relative_value_guide"
                arch_path = f"raw/mbs/rvg/{rp}/{filename}"
            else:
                continue

            discovered.append(
                DiscoveredHarvestResource(
                    source_id="au-mbs",
                    category=cat,
                    url=full_url,
                    filename=filename,
                    archive_path=arch_path,
                    period_label=rp,
                )
            )
    return discovered


def discover_mbs_utilisation_resources(
    data_gov_group_json: dict[str, Any] | None = None,
    data_gov_demographics_json: dict[str, Any] | None = None,
    health_gov_urls: list[str] | None = None,
    max_historical_files: int = 5,
) -> list[DiscoveredHarvestResource]:
    """Discover MBS utilisation files across data.gov.au and Health.gov.au."""
    discovered: list[DiscoveredHarvestResource] = []
    seen: set[str] = set()

    if health_gov_urls:
        for url in health_gov_urls:
            filename = url.split("/")[-1]
            if filename in seen:
                continue
            seen.add(filename)
            fn_lower = filename.lower()
            if "quarterly" in fn_lower:
                cat = "medicare_quarterly_statistics_state_territory"
                arch_path = f"raw/mbs/utilisation/quarterly/{filename}"
            elif "annual" in fn_lower:
                cat = "medicare_annual_statistics_state_territory"
                arch_path = f"raw/mbs/utilisation/annual/{filename}"
            elif "year-to-date" in fn_lower or "ytd" in fn_lower:
                cat = "medicare_ytd_summary_tables"
                arch_path = f"raw/mbs/utilisation/ytd/{filename}"
            else:
                cat = "medicare_statistics_supplement"
                arch_path = f"raw/mbs/utilisation/misc/{filename}"

            discovered.append(
                DiscoveredHarvestResource(
                    source_id="au-health-medicare-statistics",
                    category=cat,
                    url=url,
                    filename=filename,
                    archive_path=arch_path,
                    period_label="current",
                )
            )

    def _process_ckan_resources(
        ckan_dict: dict[str, Any],
        source_id: str,
        default_cat: str,
        path_prefix: str,
    ) -> None:
        count = 0
        resources = ckan_dict.get("result", {}).get("resources", [])
        for res in resources:
            if count >= max_historical_files:
                break
            url = res.get("url", "")
            name = res.get("name", "")
            if not url:
                continue
            filename = url.split("/")[-1]
            if not filename or filename in seen:
                continue
            seen.add(filename)

            cat = default_cat
            if "historical" in name.lower() or "historical" in url.lower():
                cat = f"{default_cat}_historical"
            elif "2016" in name or "2016" in url:
                cat = f"{default_cat}_2016"

            discovered.append(
                DiscoveredHarvestResource(
                    source_id=source_id,
                    category=cat,
                    url=url,
                    filename=filename,
                    archive_path=f"raw/mbs/utilisation/{path_prefix}/{filename}",
                    period_label=name[:50],
                )
            )
            count += 1

    if data_gov_group_json:
        _process_ckan_resources(
            data_gov_group_json,
            source_id="au-data-gov-mbs-group",
            default_cat="mbs_group_statistics",
            path_prefix="group",
        )

    if data_gov_demographics_json:
        _process_ckan_resources(
            data_gov_demographics_json,
            source_id="au-data-gov-mbs-demographics",
            default_cat="mbs_demographics_statistics",
            path_prefix="demographics",
        )

    return discovered


def stage_harvest_payload(
    resource: DiscoveredHarvestResource,
    work_dir: Path,
    data_reader: Callable[[str], bytes],
    allowed_domains: frozenset[str] = ALLOWED_AUSTRALIAN_HARVEST_DOMAINS,
) -> HarvestStageResult:
    """Download and stage a discovered payload fail-closed, producing its B1 receipt."""
    parsed = urllib.parse.urlparse(resource.url)
    if parsed.netloc.lower() not in allowed_domains:
        raise ValueError(
            f"Domain {parsed.netloc} not permitted in allowed_domains"
        )

    content = data_reader(resource.url)
    if not content:
        raise ValueError(f"Payload from {resource.url} was empty")

    sha256 = hashlib.sha256(content).hexdigest()
    byte_count = len(content)

    payload_file = work_dir / resource.archive_path
    payload_file.parent.mkdir(parents=True, exist_ok=True)
    payload_file.write_bytes(content)

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = HarvestPayloadReceipt(
        source_id=resource.source_id,
        category=resource.category,
        source_url=resource.url,
        archive_path=resource.archive_path,
        sha256=sha256,
        byte_count=byte_count,
        period_label=resource.period_label,
        retrieved_at=now,
    )

    receipt_relpath = (
        resource.archive_path.replace("raw/", "bronze/") + ".receipt.json"
    )
    receipt_file = work_dir / receipt_relpath
    receipt_file.parent.mkdir(parents=True, exist_ok=True)
    receipt_file.write_text(
        receipt.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )

    return HarvestStageResult(
        resource=resource,
        staged_payload_path=payload_file,
        staged_receipt_path=receipt_file,
        receipt=receipt,
    )


def build_harvest_manifest(
    dataset: str,
    stages: list[HarvestStageResult],
) -> dict[str, Any]:
    """Generate manifest dictionary for all staged files in a harvest run."""
    files: list[dict[str, Any]] = []
    for s in stages:
        files.append({
            "path": s.resource.archive_path,
            "bytes": s.receipt.byte_count,
            "sha256": s.receipt.sha256,
            "kind": "raw_payload",
            "source_id": s.receipt.source_id,
            "category": s.receipt.category,
        })
        receipt_path = (
            s.resource.archive_path.replace("raw/", "bronze/") + ".receipt.json"
        )
        receipt_bytes = s.staged_receipt_path.stat().st_size
        receipt_sha = hashlib.sha256(
            s.staged_receipt_path.read_bytes()
        ).hexdigest()
        files.append({
            "path": receipt_path,
            "bytes": receipt_bytes,
            "sha256": receipt_sha,
            "kind": "b1_receipt",
            "source_id": s.receipt.source_id,
        })

    manifest: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.harvest-manifest",
        "schema_version": 1,
        "dataset": dataset,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "file_count": len(files),
        "files": sorted(files, key=lambda x: str(x["path"])),
    }
    return manifest


def verify_anonymous_restore(
    dataset: str,
    manifest: dict[str, Any],
    anonymous_downloader: Callable[[str, str], bytes],
) -> dict[str, Any]:
    """Fail-closed verification: downloads every manifest object anonymously and checks SHA-256."""
    verified_files: list[dict[str, Any]] = []
    for item in manifest.get("files", []):
        path = item["path"]
        expected_sha = item["sha256"]
        expected_bytes = item["bytes"]

        downloaded_bytes = anonymous_downloader(dataset, path)
        if len(downloaded_bytes) != expected_bytes:
            raise RuntimeError(
                f"Anonymous restore size mismatch for {path}: "
                f"got {len(downloaded_bytes)}, expected {expected_bytes}"
            )
        actual_sha = hashlib.sha256(downloaded_bytes).hexdigest()
        if actual_sha != expected_sha:
            raise RuntimeError(
                f"Anonymous restore digest mismatch for {path}: "
                f"got {actual_sha}, expected {expected_sha}"
            )
        verified_files.append({
            "path": path,
            "bytes": expected_bytes,
            "sha256": actual_sha,
            "status": "digest_verified",
        })

    return {
        "status": "all_objects_anonymously_verified",
        "dataset": dataset,
        "verified_count": len(verified_files),
        "verified_files": verified_files,
    }
