"""Tests for Australian PBS/MBS harvesting discovery, staging, and fail-closed contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from global_medicines_atlas.australian_harvesting import (
    ALLOWED_AUSTRALIAN_HARVEST_DOMAINS,
    ALLOWED_MBS_DOMAINS,
    ALLOWED_MEDICARE_STATISTICS_DOMAINS,
    ALLOWED_PBS_DOMAINS,
    DiscoveredHarvestResource,
    build_harvest_manifest,
    discover_mbs_schedule_resources,
    discover_mbs_utilisation_resources,
    discover_pbs_dos_resources,
    discover_pbs_expenditure_resources,
    stage_harvest_payload,
    verify_anonymous_restore,
)

ROOT = Path(__file__).resolve().parents[1]
PBS_AUTH_FILE = (
    ROOT
    / "quality/qualifications/australian-pbs-utilisation-publication-authorization.json"
)
MBS_AUTH_FILE = (
    ROOT
    / "quality/qualifications/australian-mbs-harvest-publication-authorization.json"
)
MBS_UTIL_AUTH_FILE = (
    ROOT
    / "quality/qualifications/australian-mbs-utilisation-publication-authorization.json"
)
PBS_WORKFLOW = ROOT / ".github/workflows/australian-pbs-utilisation-harvest.yml"
MBS_WORKFLOW = ROOT / ".github/workflows/australian-mbs-schedule-harvest.yml"
MBS_UTIL_WORKFLOW = (
    ROOT / ".github/workflows/australian-mbs-utilisation-harvest.yml"
)


SAMPLE_PBS_DOS_HTML = """
<html><body>
<a href="/statistics/dos-and-dop/files/dos-jul-2025-to-jun-2026-phrmcy-type.csv">DOS 2025-26</a>
<a href="/statistics/dos-and-dop/files/dos-jul-2024-to-jun-2025-phrmcy-type.csv">DOS 2024-25</a>
<a href="/statistics/dos-and-dop/files/pbs-item-drug-map.csv">Item Drug Map</a>
<a href="/statistics/dos-and-dop/files/dos-jul-2021-to-jun-2026.xlsx">Multiyear Summary</a>
<a href="/statistics/dos-and-dop/files/dop-ytd-jan-2018.zip">Historical DOP</a>
<a href="/about.html">About</a>
</body></html>
"""

SAMPLE_PBS_EXP_INDEX_HTML = """
<html><body>
<a href="expenditure-prescriptions-report-1-july-2024-30-june-2025">2024-25</a>
<a href="expenditure-prescriptions-report-1-july-2023-30-june-2024">2023-24</a>
</body></html>
"""

SAMPLE_PBS_EXP_SUBPAGE_HTML = """
<html><body>
<a href="/statistics/expenditure-prescriptions/2024-2025/Expenditure-prescriptions-report-tables-2024-25.XLSX">Tables</a>
<a href="/statistics/expenditure-prescriptions/2024-2025/report.pdf">Report</a>
</body></html>
"""

SAMPLE_MBS_INDEX_HTML = """
<html><body>
<a href="Downloads-20260801">August 2026</a>
<a href="Downloads-20260701">July 2026</a>
</body></html>
"""

SAMPLE_MBS_SUBPAGE_HTML = """
<html><body>
<a href="/files/MBS-XML-20260801.XML">MBS XML</a>
<a href="/files/Health%20Insurance%20Regulations%202018%20-%20Basic%20Service%20Description.csv">BSD CSV</a>
<a href="/files/RVG%20file%2020260801.TXT">RVG TXT</a>
<a href="/files/mbsonline.xml">RSS</a>
</body></html>
"""


def test_discover_pbs_dos_resources() -> None:
    resources = discover_pbs_dos_resources(SAMPLE_PBS_DOS_HTML)
    assert len(resources) == 5
    by_filename = {r.filename: r for r in resources}

    assert (
        by_filename["dos-jul-2025-to-jun-2026-phrmcy-type.csv"].category
        == "date_of_supply_monthly_prescriptions"
    )
    assert by_filename["pbs-item-drug-map.csv"].category == "item_drug_mapping"
    assert (
        by_filename["dos-jul-2021-to-jun-2026.xlsx"].category
        == "date_of_supply_multiyear_summary"
    )
    assert (
        by_filename["dop-ytd-jan-2018.zip"].category
        == "date_of_processing_historical"
    )
    assert (
        by_filename["dos-jul-2025-to-jun-2026-phrmcy-type.csv"].archive_path
        == "raw/pbs/utilisation/dos/dos-jul-2025-to-jun-2026-phrmcy-type.csv"
    )


def test_discover_pbs_expenditure_resources() -> None:
    def fake_subpage_fetcher(_url: str) -> str:
        return SAMPLE_PBS_EXP_SUBPAGE_HTML

    resources = discover_pbs_expenditure_resources(
        SAMPLE_PBS_EXP_INDEX_HTML, fake_subpage_fetcher, max_subpages=1
    )
    assert len(resources) == 1
    assert (
        resources[0].filename
        == "Expenditure-prescriptions-report-tables-2024-25.XLSX"
    )
    assert (
        resources[0].category == "annual_expenditure_and_prescriptions_report"
    )
    assert (
        resources[0].archive_path
        == "raw/pbs/expenditure/Expenditure-prescriptions-report-tables-2024-25.XLSX"
    )


def test_discover_mbs_schedule_resources() -> None:
    def fake_subpage_fetcher(_url: str) -> str:
        return SAMPLE_MBS_SUBPAGE_HTML

    resources = discover_mbs_schedule_resources(
        SAMPLE_MBS_INDEX_HTML, fake_subpage_fetcher, max_releases=1
    )
    assert len(resources) == 3
    cats = {r.category for r in resources}
    assert cats == {
        "monthly_schedule_xml",
        "basic_service_description",
        "relative_value_guide",
    }


def test_stage_harvest_payload_domain_check(tmp_path: Path) -> None:
    evil_resource = DiscoveredHarvestResource(
        source_id="au-pbs-dos-utilisation",
        category="date_of_supply_monthly_prescriptions",
        url="https://evil-server.example.com/malicious.csv",
        filename="malicious.csv",
        archive_path="raw/pbs/malicious.csv",
    )
    with pytest.raises(ValueError, match=r"Domain .* not permitted"):
        stage_harvest_payload(
            evil_resource,
            tmp_path,
            data_reader=lambda _url: b"content",
            allowed_domains=ALLOWED_PBS_DOMAINS,
        )


def test_stage_harvest_payload_empty_check(tmp_path: Path) -> None:
    empty_resource = DiscoveredHarvestResource(
        source_id="au-pbs-dos-utilisation",
        category="date_of_supply_monthly_prescriptions",
        url="https://www.pbs.gov.au/empty.csv",
        filename="empty.csv",
        archive_path="raw/pbs/empty.csv",
    )
    with pytest.raises(ValueError, match=r"Payload from .* was empty"):
        stage_harvest_payload(
            empty_resource,
            tmp_path,
            data_reader=lambda _url: b"",
            allowed_domains=ALLOWED_PBS_DOMAINS,
        )


def test_stage_harvest_payload_success_and_receipt(tmp_path: Path) -> None:
    data = b"ITEM_CODE,COUNT\n0001,10\n"
    expected_sha = hashlib.sha256(data).hexdigest()
    resource = DiscoveredHarvestResource(
        source_id="au-pbs-dos-utilisation",
        category="date_of_supply_monthly_prescriptions",
        url="https://www.pbs.gov.au/test.csv",
        filename="test.csv",
        archive_path="raw/pbs/test.csv",
        period_label="202601",
    )
    result = stage_harvest_payload(
        resource,
        tmp_path,
        data_reader=lambda _url: data,
        allowed_domains=ALLOWED_PBS_DOMAINS,
    )
    assert result.receipt.sha256 == expected_sha
    assert result.receipt.byte_count == len(data)
    assert result.staged_payload_path.read_bytes() == data

    receipt_json = json.loads(
        result.staged_receipt_path.read_text(encoding="utf-8")
    )
    assert receipt_json["sha256"] == expected_sha
    assert receipt_json["source_id"] == "au-pbs-dos-utilisation"


def test_build_harvest_manifest_and_verify_anonymous_restore(
    tmp_path: Path,
) -> None:
    data = b"MBS_XML_TEST_CONTENT"
    resource = DiscoveredHarvestResource(
        source_id="au-mbs",
        category="monthly_schedule_xml",
        url="https://www.mbsonline.gov.au/mbs.xml",
        filename="mbs.xml",
        archive_path="raw/mbs/mbs.xml",
        period_label="20260801",
    )
    stage = stage_harvest_payload(
        resource,
        tmp_path,
        data_reader=lambda _url: data,
        allowed_domains=ALLOWED_MBS_DOMAINS,
    )
    manifest = build_harvest_manifest("test/dataset", [stage])
    assert manifest["file_count"] == 2  # payload + B1 receipt
    paths = {f["path"] for f in manifest["files"]}
    assert "raw/mbs/mbs.xml" in paths
    assert "bronze/mbs/mbs.xml.receipt.json" in paths

    # Test passing verification
    stored = {
        "raw/mbs/mbs.xml": data,
        "bronze/mbs/mbs.xml.receipt.json": stage.staged_receipt_path.read_bytes(),
    }
    verification = verify_anonymous_restore(
        "test/dataset",
        manifest,
        anonymous_downloader=lambda _repo, path: stored[path],
    )
    assert verification["status"] == "all_objects_anonymously_verified"
    assert verification["verified_count"] == 2

    # Test failing verification on tampered data
    corrupted = dict(stored)
    corrupted["raw/mbs/mbs.xml"] = b"TAMPERED"
    with pytest.raises(RuntimeError, match=r"Anonymous restore .* mismatch"):
        verify_anonymous_restore(
            "test/dataset",
            manifest,
            anonymous_downloader=lambda _repo, path: corrupted[path],
        )


def test_pbs_utilisation_publication_authorization() -> None:
    auth = json.loads(PBS_AUTH_FILE.read_text(encoding="utf-8"))
    assert auth["external_publication_authorized"] is True
    assert auth["maintainer_asserted_redistribution_permission"] is True
    assert auth["dataset"] == "edithatogo/australian-pbs-utilisation-archive"
    assert auth["visibility"] == "public"
    assert auth["gated"] is False
    assert "github-actions-only-upload" in auth["required_controls"]
    assert (
        "anonymous-all-object-digest-verification" in auth["required_controls"]
    )


def test_mbs_harvest_publication_authorization() -> None:
    auth = json.loads(MBS_AUTH_FILE.read_text(encoding="utf-8"))
    assert auth["external_publication_authorized"] is True
    assert auth["maintainer_asserted_redistribution_permission"] is True
    assert auth["dataset"] == "edithatogo/australian-mbs-source-archive"
    assert auth["visibility"] == "public"
    assert auth["gated"] is False
    assert "github-actions-only-upload" in auth["required_controls"]


def test_mbs_utilisation_publication_authorization() -> None:
    auth = json.loads(MBS_UTIL_AUTH_FILE.read_text(encoding="utf-8"))
    assert auth["external_publication_authorized"] is True
    assert auth["maintainer_asserted_redistribution_permission"] is True
    assert auth["dataset"] == "edithatogo/australian-mbs-utilisation-archive"
    assert auth["visibility"] == "public"
    assert auth["gated"] is False
    assert "github-actions-only-upload" in auth["required_controls"]


def test_discover_mbs_utilisation_resources() -> None:
    mock_ckan = {
        "result": {
            "resources": [
                {
                    "name": "MBS Group Statistics Report - 2016 (YTD) csv",
                    "url": "https://data.gov.au/data/dataset/5335e112/download/mbs-group-2016-july.csv",
                },
                {
                    "name": "MBS Group Statistics Report - historical csv 1993-2015",
                    "url": "https://data.gov.au/data/dataset/5335e112/download/mbs-historical-1993-2015.zip",
                },
            ]
        }
    }
    mock_urls = [
        "https://www.health.gov.au/sites/default/files/2026-08/medicare-quarterly-statistics-state-and-territory-june-quarter-2025-26.xlsx",
        "https://www.health.gov.au/sites/default/files/2026-08/medicare-annual-statistics-state-and-territory-2009-10-to-2024-25.xlsx",
        "https://www.health.gov.au/sites/default/files/2026-08/medicare-statistics-year-to-date-summary-tables-july-to-june-2025-26.xlsx",
    ]

    discovered = discover_mbs_utilisation_resources(
        data_gov_group_json=mock_ckan,
        health_gov_urls=mock_urls,
    )
    assert len(discovered) == 5
    by_filename = {d.filename: d for d in discovered}

    assert (
        by_filename[
            "medicare-quarterly-statistics-state-and-territory-june-quarter-2025-26.xlsx"
        ].category
        == "medicare_quarterly_statistics_state_territory"
    )
    assert (
        by_filename[
            "medicare-annual-statistics-state-and-territory-2009-10-to-2024-25.xlsx"
        ].category
        == "medicare_annual_statistics_state_territory"
    )
    assert (
        by_filename[
            "medicare-statistics-year-to-date-summary-tables-july-to-june-2025-26.xlsx"
        ].category
        == "medicare_ytd_summary_tables"
    )
    assert (
        by_filename["mbs-group-2016-july.csv"].category
        == "mbs_group_statistics_2016"
    )
    assert (
        by_filename["mbs-historical-1993-2015.zip"].category
        == "mbs_group_statistics_historical"
    )


def test_medicare_statistics_domains() -> None:
    assert "www.health.gov.au" in ALLOWED_MEDICARE_STATISTICS_DOMAINS
    assert "data.gov.au" in ALLOWED_MEDICARE_STATISTICS_DOMAINS
    assert "www.health.gov.au" in ALLOWED_AUSTRALIAN_HARVEST_DOMAINS
    assert "data.gov.au" in ALLOWED_AUSTRALIAN_HARVEST_DOMAINS


def test_harvest_workflows_enforce_governed_controls() -> None:
    for wf_path, expected_dataset in [
        (PBS_WORKFLOW, "edithatogo/australian-pbs-utilisation-archive"),
        (MBS_WORKFLOW, "edithatogo/australian-mbs-source-archive"),
        (MBS_UTIL_WORKFLOW, "edithatogo/australian-mbs-utilisation-archive"),
    ]:
        text = wf_path.read_text(encoding="utf-8")
        assert "schedule:" in text
        assert "workflow_dispatch:" in text
        assert 'test "$GITHUB_REF" = refs/heads/main' in text
        assert 'test "$GITHUB_SHA" = "$REQUESTED_COMMIT"' in text
        assert expected_dataset in text
        assert "anonymous_digest_verification" in text
        assert "temporary_source_bytes_removed" in text
        assert "environment: australian-hf-publication" in text
