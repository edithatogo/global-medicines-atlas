"""Tests for Australian PBS/MBS harvesting discovery, staging, and fail-closed contracts."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

import pytest

from global_medicines_atlas.australian_harvesting import (
    ALLOWED_AUSTRALIAN_HARVEST_DOMAINS,
    ALLOWED_MBS_DOMAINS,
    ALLOWED_MEDICARE_STATISTICS_DOMAINS,
    ALLOWED_PBS_DOMAINS,
    DiscoveredHarvestResource,
    GovernedRedirectHandler,
    build_cumulative_harvest_manifest,
    build_harvest_manifest,
    discover_health_gov_medicare_workbooks,
    discover_mbs_schedule_resources,
    discover_mbs_utilisation_resources,
    discover_pbs_dos_resources,
    discover_pbs_expenditure_resources,
    fetch_url_bytes_governed,
    stage_harvest_payload,
    validate_resources_against_contract,
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

    # Test failing verification on tampered data with same size but wrong digest
    corrupted = dict(stored)
    corrupted["raw/mbs/mbs.xml"] = b"X" * len(data)
    with pytest.raises(
        RuntimeError, match=r"Anonymous restore digest mismatch"
    ):
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
        == "mbs_group_statistics"
    )
    assert by_filename["mbs-group-2016-july.csv"].period_label.startswith(
        "2016_"
    )
    assert (
        by_filename["mbs-historical-1993-2015.zip"].category
        == "mbs_group_statistics"
    )
    assert by_filename["mbs-historical-1993-2015.zip"].period_label.startswith(
        "historical_"
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


def test_discover_pbs_dos_misc_and_duplicate() -> None:
    html = """
    <a href="/files/dos-jul-2025-to-jun-2026-phrmcy-type.csv">1</a>
    <a href="/files/dos-jul-2025-to-jun-2026-phrmcy-type.csv">Duplicate</a>
    <a href="/files/random-supplement.csv">Random</a>
    """
    res = discover_pbs_dos_resources(html)
    assert len(res) == 2
    assert res[1].category == "pbs_utilisation_supplement"
    assert res[1].period_label == "other"


def test_discover_pbs_expenditure_subpage_error_and_skip() -> None:
    def failing_fetcher(_url: str) -> str:
        raise OSError("Network failure")

    index_html = '<a href="expenditure-prescriptions-2025">2025</a>'
    res = discover_pbs_expenditure_resources(index_html, failing_fetcher)
    assert res == []

    def non_exp_fetcher(_url: str) -> str:
        return '<a href="something_else.xlsx">Else</a>'

    res2 = discover_pbs_expenditure_resources(index_html, non_exp_fetcher)
    assert res2 == []


def test_discover_mbs_schedule_subpage_error_and_filtering() -> None:
    def failing_fetcher(_url: str) -> str:
        raise OSError("MBS failure")

    index_html = '<a href="Downloads-240801">Old 6-digit</a><a href="Downloads-other">Invalid</a>'
    res = discover_mbs_schedule_resources(index_html, failing_fetcher)
    assert res == []

    def mock_fetcher(_url: str) -> str:
        return (
            '<a href="/files/MBS-XML-20260801.XML">XML</a>'
            '<a href="/files/rss.xml">RSS</a>'
            '<a href="/files/unknown.zip">Unknown</a>'
        )

    index_html2 = '<a href="Downloads-20260801">August</a>'
    res2 = discover_mbs_schedule_resources(index_html2, mock_fetcher)
    assert len(res2) == 1
    assert res2[0].category == "monthly_schedule_xml"


def test_discover_mbs_utilisation_demographics_and_edge_cases() -> None:
    mock_demographics = {
        "result": {
            "resources": [
                {
                    "name": "Demographics CSV",
                    "url": "https://data.gov.au/download/demographics.csv",
                },
                {"name": "Empty URL", "url": ""},
            ]
        }
    }
    urls = [
        "https://www.health.gov.au/files/misc-stats.xlsx",
        "https://www.health.gov.au/files/misc-stats.xlsx",
    ]
    res = discover_mbs_utilisation_resources(
        data_gov_demographics_json=mock_demographics,
        health_gov_urls=urls,
        max_historical_files=1,
    )
    assert len(res) == 2
    assert res[0].category == "medicare_statistics_supplement"
    assert res[1].category == "mbs_demographics_statistics"


def test_verify_anonymous_restore_size_mismatch() -> None:
    manifest = {"files": [{"path": "test.txt", "bytes": 100, "sha256": "abc"}]}
    with pytest.raises(RuntimeError, match=r"size mismatch"):
        verify_anonymous_restore(
            "test/ds",
            manifest,
            anonymous_downloader=lambda _repo, _p: b"short",
        )


def test_verify_anonymous_restore_empty_rejected() -> None:
    with pytest.raises(ValueError, match=r"Cannot verify empty manifest"):
        verify_anonymous_restore(
            "test/ds",
            {"files": [], "file_count": 0},
            anonymous_downloader=lambda _repo, _p: b"",
        )


def test_build_harvest_manifest_rejects_empty() -> None:
    with pytest.raises(
        ValueError, match=r"Cannot build harvest manifest from empty stages"
    ):
        build_harvest_manifest("test/ds", [])


def test_governed_redirect_handler_blocks_unauthorized() -> None:
    handler = GovernedRedirectHandler(ALLOWED_PBS_DOMAINS)

    req = urllib.request.Request("https://www.pbs.gov.au/file.csv")
    with pytest.raises(PermissionError, match=r"Redirect destination host"):
        handler.redirect_request(
            req,
            fp=None,
            code=302,
            msg="Found",
            headers={},
            newurl="https://evil-unapproved.com/file.csv",
        )


def test_validate_resources_against_contract() -> None:
    valid_res = [
        DiscoveredHarvestResource(
            source_id="au-pbs-dos-utilisation",
            category="date_of_supply_monthly_prescriptions",
            url="https://www.pbs.gov.au/dos.csv",
            filename="dos.csv",
            archive_path="raw/pbs/dos.csv",
        )
    ]
    contract = validate_resources_against_contract(
        PBS_AUTH_FILE,
        "edithatogo/australian-pbs-utilisation-archive",
        valid_res,
    )
    assert contract["external_publication_authorized"] is True

    # Bad source ID
    bad_source = [
        DiscoveredHarvestResource(
            source_id="unauthorized-source",
            category="date_of_supply_monthly_prescriptions",
            url="https://www.pbs.gov.au/dos.csv",
            filename="dos.csv",
            archive_path="raw/pbs/dos.csv",
        )
    ]
    with pytest.raises(PermissionError, match=r"source_id .* is not permitted"):
        validate_resources_against_contract(
            PBS_AUTH_FILE,
            "edithatogo/australian-pbs-utilisation-archive",
            bad_source,
        )

    # Bad category
    bad_cat = [
        DiscoveredHarvestResource(
            source_id="au-pbs-dos-utilisation",
            category="unauthorized_category",
            url="https://www.pbs.gov.au/dos.csv",
            filename="dos.csv",
            archive_path="raw/pbs/dos.csv",
        )
    ]
    with pytest.raises(PermissionError, match=r"category .* is not permitted"):
        validate_resources_against_contract(
            PBS_AUTH_FILE,
            "edithatogo/australian-pbs-utilisation-archive",
            bad_cat,
        )

    # Bad domain
    bad_domain = [
        DiscoveredHarvestResource(
            source_id="au-pbs-dos-utilisation",
            category="date_of_supply_monthly_prescriptions",
            url="https://unauthorized-domain.com/dos.csv",
            filename="dos.csv",
            archive_path="raw/pbs/dos.csv",
        )
    ]
    with pytest.raises(PermissionError, match=r"host .* is not permitted"):
        validate_resources_against_contract(
            PBS_AUTH_FILE,
            "edithatogo/australian-pbs-utilisation-archive",
            bad_domain,
        )

    # Mismatched dataset
    with pytest.raises(ValueError, match=r"Contract dataset"):
        validate_resources_against_contract(
            PBS_AUTH_FILE,
            "wrong/dataset",
            valid_res,
        )


def test_build_cumulative_harvest_manifest(tmp_path: Path) -> None:
    data = b"PAYLOAD"
    res = DiscoveredHarvestResource(
        source_id="au-mbs",
        category="monthly_schedule_xml",
        url="https://www.mbsonline.gov.au/test.xml",
        filename="test.xml",
        archive_path="raw/mbs/test.xml",
    )
    stage = stage_harvest_payload(
        res,
        tmp_path,
        data_reader=lambda _u: data,
        allowed_domains=ALLOWED_MBS_DOMAINS,
    )
    existing_manifest = {
        "files": [
            {
                "path": "raw/mbs/prior_release.xml",
                "bytes": 500,
                "sha256": "0" * 64,
                "kind": "raw_payload",
            }
        ]
    }
    cumulative = build_cumulative_harvest_manifest(
        "test/dataset", [stage], existing_manifest
    )
    assert cumulative["file_count"] == 3  # 1 prior + 1 new payload + 1 receipt
    paths = {f["path"] for f in cumulative["files"]}
    assert "raw/mbs/prior_release.xml" in paths
    assert "raw/mbs/test.xml" in paths
    assert "bronze/mbs/test.xml.receipt.json" in paths


def test_discover_health_gov_medicare_workbooks() -> None:
    mock_html = '<html><body><a href="/sites/default/files/test.xlsx">File</a></body></html>'
    found = discover_health_gov_medicare_workbooks(
        subpage_fetcher=lambda _u: mock_html,
        candidate_slugs=["https://www.health.gov.au/page1"],
    )
    assert len(found) == 1
    assert found[0] == "https://www.health.gov.au/sites/default/files/test.xlsx"

    # Test fallback
    fallback = ["https://fallback.com/file.xlsx"]
    found_fallback = discover_health_gov_medicare_workbooks(
        subpage_fetcher=lambda _u: "",
        candidate_slugs=["https://www.health.gov.au/empty"],
        fallback_urls=fallback,
    )
    assert found_fallback == fallback

    # Test default candidate generation
    found_default = discover_health_gov_medicare_workbooks(
        subpage_fetcher=lambda _u: (
            '<html><a href="/sites/default/files/auto.xlsx">F</a></html>'
        ),
        candidate_slugs=None,
    )
    assert len(found_default) >= 1
    assert "auto.xlsx" in found_default[0]


def test_fetch_url_bytes_governed_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(PermissionError, match=r"Initial host"):
        fetch_url_bytes_governed("https://unauthorized-initial.com/file.csv")

    class FakeResp:
        def __init__(self, final_url: str, data: bytes) -> None:
            self._final_url = final_url
            self._data = data

        def geturl(self) -> str:
            return self._final_url

        def read(self) -> bytes:
            return self._data

        def __enter__(self) -> FakeResp:
            return self

        def __exit__(self, *args: object) -> None:
            pass

    class FakeOpener:
        def __init__(self, final_url: str, data: bytes) -> None:
            self.final_url = final_url
            self.data = data

        def open(self, _req: object, timeout: int = 120) -> FakeResp:
            _ = timeout
            return FakeResp(self.final_url, self.data)

    def _good_opener(_h: object) -> FakeOpener:
        return FakeOpener("https://www.pbs.gov.au/resolved.csv", b"DATA")

    def _bad_opener(_h: object) -> FakeOpener:
        return FakeOpener("https://evil-unapproved.com/redirected.csv", b"DATA")

    monkeypatch.setattr("urllib.request.build_opener", _good_opener)
    content, final_url = fetch_url_bytes_governed(
        "https://www.pbs.gov.au/initial.csv"
    )
    assert content == b"DATA"
    assert final_url == "https://www.pbs.gov.au/resolved.csv"

    # Final URL unapproved
    monkeypatch.setattr("urllib.request.build_opener", _bad_opener)
    with pytest.raises(PermissionError, match=r"Final response host"):
        fetch_url_bytes_governed("https://www.pbs.gov.au/initial.csv")


def test_stage_harvest_payload_tuple_reader(tmp_path: Path) -> None:
    res = DiscoveredHarvestResource(
        source_id="au-pbs-dos-utilisation",
        category="date_of_supply_monthly_prescriptions",
        url="https://www.pbs.gov.au/initial.csv",
        filename="initial.csv",
        archive_path="raw/pbs/initial.csv",
    )
    # Valid redirect
    stage = stage_harvest_payload(
        res,
        tmp_path,
        data_reader=lambda _u: (
            b"content",
            "https://data.pbs.gov.au/resolved.csv",
        ),
        allowed_domains=ALLOWED_PBS_DOMAINS,
    )
    assert stage.receipt.final_url == "https://data.pbs.gov.au/resolved.csv"

    # Invalid resolved domain
    with pytest.raises(ValueError, match=r"Resolved redirect domain"):
        stage_harvest_payload(
            res,
            tmp_path,
            data_reader=lambda _u: (
                b"content",
                "https://evil.com/resolved.csv",
            ),
            allowed_domains=ALLOWED_PBS_DOMAINS,
        )


def test_validate_resources_against_contract_flags(tmp_path: Path) -> None:
    res = [
        DiscoveredHarvestResource(
            source_id="au-pbs-dos-utilisation",
            category="date_of_supply_monthly_prescriptions",
            url="https://www.pbs.gov.au/dos.csv",
            filename="dos.csv",
            archive_path="raw/pbs/dos.csv",
        )
    ]
    # Missing contract
    with pytest.raises(FileNotFoundError):
        validate_resources_against_contract(
            tmp_path / "nonexistent.json", "ds", res
        )

    base = {
        "external_publication_authorized": True,
        "dataset": "test/ds",
        "visibility": "public",
        "gated": False,
        "allowed_sources": ["au-pbs-dos-utilisation"],
        "allowed_domains": ["www.pbs.gov.au"],
        "categories": ["date_of_supply_monthly_prescriptions"],
    }
    p = tmp_path / "contract.json"

    # Not authorized
    p.write_text(json.dumps({**base, "external_publication_authorized": False}))
    with pytest.raises(
        PermissionError, match=r"external_publication_authorized is False"
    ):
        validate_resources_against_contract(p, "test/ds", res)

    # Not public
    p.write_text(json.dumps({**base, "visibility": "private"}))
    with pytest.raises(
        ValueError, match=r"Contract visibility must be 'public'"
    ):
        validate_resources_against_contract(p, "test/ds", res)

    # Gated
    p.write_text(json.dumps({**base, "gated": True}))
    with pytest.raises(ValueError, match=r"Contract gated flag must be False"):
        validate_resources_against_contract(p, "test/ds", res)
