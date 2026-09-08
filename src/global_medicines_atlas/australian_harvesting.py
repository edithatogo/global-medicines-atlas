"""Governed discovery, staging, and verification for Australian PBS/MBS harvesting.

Separates policy schedule/listing data from empirical utilisation data.
Adheres strictly to the Global Medicines Atlas fail-closed contracts.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

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
AUSTRALIAN_FY_START_MONTH: Final[int] = 7
MEDICARE_Q1_PUBLICATION_MONTH: Final[int] = 11

DEFAULT_HARVEST_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 (compatible; GlobalMedicinesAtlas/1.0)"
)
DEFAULT_HARVEST_HEADERS: Final[dict[str, str]] = {
    "User-Agent": DEFAULT_HARVEST_USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/octet-stream,*/*;q=0.8"
    ),
    "Accept-Language": "en-AU,en-US;q=0.9,en;q=0.8",
}


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
    final_url: str = ""


class GovernedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """HTTP redirect handler that enforces domain whitelisting on every redirect hop."""

    def __init__(self, allowed_domains: frozenset[str] | set[str]):
        super().__init__()
        self.allowed_domains = {d.lower() for d in allowed_domains}

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        parsed = urllib.parse.urlparse(newurl)
        if parsed.netloc.lower() not in self.allowed_domains:
            raise PermissionError(
                f"Redirect destination host '{parsed.netloc}' is not in allowed domains: "
                f"{sorted(self.allowed_domains)}"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _validate_final_host(
    final_url: str, allowed_domains: frozenset[str]
) -> None:
    final_parsed = urllib.parse.urlparse(final_url)
    if final_parsed.netloc.lower() not in allowed_domains:
        raise PermissionError(
            f"Final response host '{final_parsed.netloc}' is not in allowed domains: "
            f"{sorted(allowed_domains)}"
        )


def _fetch_via_curl_fallback(
    url: str,
    allowed_domains: frozenset[str],
    req_headers: dict[str, str],
    timeout: int,
) -> tuple[bytes, str]:
    curl_path = shutil.which("curl")
    if not curl_path:
        raise ConnectionError("curl not available for network fallback")
    curl_timeout = min(timeout, 30)
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
    try:
        curl_cmd = [
            curl_path,
            "-sSL",
            "--proto",
            "=https,http",
            "--proto-redir",
            "=https,http",
            "--max-time",
            str(curl_timeout),
            "-o",
            str(tmp_path),
            "-w",
            "%{url_effective}",
            url,
        ]
        for k, v in req_headers.items():
            curl_cmd.extend(["-H", f"{k}: {v}"])
        proc = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            curl_cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and tmp_path.exists():
            final_url = proc.stdout.strip() or url
            _validate_final_host(final_url, allowed_domains)
            content = tmp_path.read_bytes()
            if content:
                return content, final_url
    finally:
        tmp_path.unlink(missing_ok=True)
    raise ConnectionError(f"Network retrieval failed for {url}")


def fetch_url_bytes_governed(
    url: str,
    allowed_domains: frozenset[str] = ALLOWED_AUSTRALIAN_HARVEST_DOMAINS,
    user_agent: str = DEFAULT_HARVEST_USER_AGENT,
    headers: dict[str, str] | None = None,
    timeout: int = 45,
) -> tuple[bytes, str]:
    """Fetch URL bytes fail-closed, validating initial host and every redirect hop.

    Returns (content_bytes, final_resolved_url).
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() not in allowed_domains:
        raise PermissionError(
            f"Initial host '{parsed.netloc}' is not in allowed domains: "
            f"{sorted(allowed_domains)}"
        )
    opener = urllib.request.build_opener(
        GovernedRedirectHandler(allowed_domains)
    )
    req_headers = dict(DEFAULT_HARVEST_HEADERS)
    if user_agent:
        req_headers["User-Agent"] = user_agent
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers)  # ruff: ignore[suspicious-url-open-usage]
    try:
        with opener.open(req, timeout=timeout) as resp:
            final_url = str(resp.geturl())
            content = bytes(resp.read())
    except PermissionError:
        raise
    except TimeoutError, urllib.error.URLError, ConnectionError, OSError:
        return _fetch_via_curl_fallback(
            url, allowed_domains, req_headers, timeout
        )
    _validate_final_host(final_url, allowed_domains)
    return content, final_url


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


def _generate_medicare_candidate_slugs(now: datetime) -> list[str]:
    """Generate prioritized candidate publication URLs on health.gov.au."""
    current_fy_end = (
        now.year + 1 if now.month >= AUSTRALIAN_FY_START_MONTH else now.year
    )
    fy_start = (
        current_fy_end
        if now.month >= MEDICARE_Q1_PUBLICATION_MONTH
        else current_fy_end - 1
    )
    fy_list = [
        f"{y - 1}-{str(y)[2:]}" for y in range(current_fy_end - 1, fy_start + 1)
    ]
    quarters = ("june", "march", "december", "september")

    slugs: list[str] = []
    for fy in reversed(fy_list):
        slugs.append(
            f"https://www.health.gov.au/resources/publications/medicare-annual-statistics-state-and-territory-2009-10-to-{fy}?language=en"
        )
        slugs.extend([
            f"https://www.health.gov.au/resources/publications/medicare-quarterly-statistics-state-and-territory-{q}-quarter-{fy}?language=en"
            for q in quarters
        ])
        slugs.extend([
            f"https://www.health.gov.au/resources/publications/medicare-statistics-year-to-date-summary-tables-july-to-{m}-{fy}?language=en"
            for m in quarters
        ])
    return slugs


def discover_health_gov_medicare_workbooks(
    subpage_fetcher: Callable[[str], str] | None = None,
    candidate_slugs: list[str] | None = None,
    fallback_urls: list[str] | None = None,
) -> list[str]:
    """Dynamically discover current Medicare statistics Excel workbooks from health.gov.au."""
    discovered_urls: list[str] = []
    seen: set[str] = set()

    if subpage_fetcher is not None:
        if candidate_slugs is None:
            candidate_slugs = _generate_medicare_candidate_slugs(
                datetime.now(UTC)
            )

        found_quarter_fy: set[str] = set()
        found_ytd_fy: set[str] = set()
        for page_url in candidate_slugs:
            m_q = re.search(
                r"medicare-quarterly-statistics.*-(20\d{2}-\d{2})", page_url
            )
            if m_q and m_q.group(1) in found_quarter_fy:
                continue
            m_ytd = re.search(
                r"medicare-statistics-year-to-date.*-(20\d{2}-\d{2})", page_url
            )
            if m_ytd and m_ytd.group(1) in found_ytd_fy:
                continue

            try:
                page_html = subpage_fetcher(page_url)
            except (OSError, TimeoutError, ValueError):
                continue
            xlsx_links = re.findall(
                r"href=[\"\']([^\"\']+\.xlsx)[\"\']",
                page_html,
                re.IGNORECASE,
            )
            has_xlsx = False
            for link in xlsx_links:
                full = urllib.parse.urljoin(page_url, link)
                if full not in seen:
                    seen.add(full)
                    discovered_urls.append(full)
                    has_xlsx = True
            if has_xlsx:
                if m_q:
                    found_quarter_fy.add(m_q.group(1))
                if m_ytd:
                    found_ytd_fy.add(m_ytd.group(1))

    if not discovered_urls and fallback_urls:
        return fallback_urls
    return discovered_urls


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

            period = name[:50]
            if "historical" in name.lower() or "historical" in url.lower():
                period = f"historical_{period}"
            elif "2016" in name or "2016" in url:
                period = f"2016_{period}"

            discovered.append(
                DiscoveredHarvestResource(
                    source_id=source_id,
                    category=default_cat,
                    url=url,
                    filename=filename,
                    archive_path=f"raw/mbs/utilisation/{path_prefix}/{filename}",
                    period_label=period,
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
    data_reader: Callable[[str], bytes | tuple[bytes, str]],
    allowed_domains: frozenset[str] = ALLOWED_AUSTRALIAN_HARVEST_DOMAINS,
) -> HarvestStageResult:
    """Download and stage a discovered payload fail-closed, producing its B1 receipt."""
    parsed = urllib.parse.urlparse(resource.url)
    if parsed.netloc.lower() not in allowed_domains:
        raise ValueError(
            f"Domain {parsed.netloc} not permitted in allowed_domains"
        )

    read_result = data_reader(resource.url)
    final_url = resource.url
    if isinstance(read_result, tuple):
        content, resolved_url = read_result
        resolved_parsed = urllib.parse.urlparse(resolved_url)
        if resolved_parsed.netloc.lower() not in allowed_domains:
            raise ValueError(
                f"Resolved redirect domain '{resolved_parsed.netloc}' not permitted in allowed_domains"
            )
        final_url = resolved_url
    else:
        content = read_result

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
        final_url=final_url,
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
    if not stages:
        raise ValueError("Cannot build harvest manifest from empty stages.")
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


def build_cumulative_harvest_manifest(
    dataset: str,
    stages: list[HarvestStageResult],
    existing_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge newly staged harvest files with an existing dataset snapshot manifest."""
    new_manifest = build_harvest_manifest(dataset, stages)
    files_by_path: dict[str, dict[str, Any]] = {}

    if existing_manifest:
        for f in existing_manifest.get("files", []):
            files_by_path[f["path"]] = f

    for f in new_manifest["files"]:
        files_by_path[f["path"]] = f

    merged_files = sorted(files_by_path.values(), key=lambda x: str(x["path"]))
    return {
        "schema_id": "global-medicines-atlas.harvest-manifest",
        "schema_version": 1,
        "dataset": dataset,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "file_count": len(merged_files),
        "files": merged_files,
    }


def verify_anonymous_restore(
    dataset: str,
    manifest: dict[str, Any],
    anonymous_downloader: Callable[[str, str], bytes],
) -> dict[str, Any]:
    """Fail-closed verification: downloads every manifest object anonymously and checks SHA-256."""
    files = manifest.get("files", [])
    file_count = manifest.get("file_count", len(files))
    if not files or file_count <= 0:
        raise ValueError(
            f"Cannot verify empty manifest for {dataset}; at least one file required"
        )

    verified_files: list[dict[str, Any]] = []
    for item in files:
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


def validate_resources_against_contract(
    contract_path: Path,
    dataset: str,
    resources: list[DiscoveredHarvestResource],
) -> dict[str, Any]:
    """Validate authorization contract flags, dataset, visibility, and every resource fail-closed."""
    if not contract_path.exists():
        raise FileNotFoundError(
            f"Missing authorization contract at {contract_path}"
        )
    contract: dict[str, Any] = json.loads(
        contract_path.read_text(encoding="utf-8")
    )
    if not contract.get("external_publication_authorized"):
        raise PermissionError(
            f"external_publication_authorized is False in contract {contract_path}"
        )
    if contract.get("dataset") != dataset:
        raise ValueError(
            f"Contract dataset '{contract.get('dataset')}' does not match target dataset '{dataset}'"
        )
    if contract.get("visibility") != "public":
        raise ValueError(
            f"Contract visibility must be 'public', got '{contract.get('visibility')}'"
        )
    if contract.get("gated") is not False:
        raise ValueError("Contract gated flag must be False")

    allowed_sources = set(contract.get("allowed_sources", []))
    allowed_domains = {d.lower() for d in contract.get("allowed_domains", [])}
    allowed_categories = set(contract.get("categories", []))

    for res in resources:
        if res.source_id not in allowed_sources:
            raise PermissionError(
                f"Resource source_id '{res.source_id}' is not permitted by contract {contract_path}. "
                f"Allowed sources: {sorted(allowed_sources)}"
            )
        if res.category not in allowed_categories:
            raise PermissionError(
                f"Resource category '{res.category}' is not permitted by contract {contract_path}. "
                f"Allowed categories: {sorted(allowed_categories)}"
            )
        parsed_url = urllib.parse.urlparse(res.url)
        if parsed_url.netloc.lower() not in allowed_domains:
            raise PermissionError(
                f"Resource URL host '{parsed_url.netloc}' is not permitted by contract {contract_path}. "
                f"Allowed domains: {sorted(allowed_domains)}"
            )
    return contract
