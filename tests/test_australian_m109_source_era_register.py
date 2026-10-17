import json
from pathlib import Path


def _json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_m109_register_covers_known_source_era_families() -> None:
    document = Path(
        "docs/qualification/australian-m109-source-era-register.md"
    ).read_text(encoding="utf-8")

    for era in (
        "MBS July 2025 XML v3",
        "MBS July 2024 Group P7 workbook",
        "PBS 2026-04-01 XML V3 archive member",
        "PBS G2B XML 1.8",
        "Alternate PBS XML 2.12",
        "PBS XML 3.x historical releases",
        "Current PBS public API / API CSV",
        "Minimal PBS fixture",
    ):
        assert era in document
    assert "PBS XML 2.8\u20132.12" in document


def test_m109_register_preserves_partial_and_rights_boundaries() -> None:
    document = Path(
        "docs/qualification/australian-m109-source-era-register.md"
    ).read_text(encoding="utf-8")

    assert "M-109 remains blocked" in document
    assert "Fixtures are not real-source evidence" in document
    assert "1,276 values are calendar-valid under both DMY and MDY" in document
    assert "no payload requested or acquired" in document
    assert (
        "project retention and external redistribution authority remain unresolved"
        in document
    )


def test_july_2025_mbs_parity_receipt_is_bound_without_overstating_acceptance() -> (
    None
):
    document = Path(
        "docs/qualification/australian-m109-source-era-register.md"
    ).read_text(encoding="utf-8")

    assert "38908829291" in document
    assert "12048749308" in document
    assert "mbs-source-silver-tables-parity-2025-07-v3.json" in document
    assert (
        "0743f6039e3da1d5bac05d013f3fd629d22da94df014033cdac66b0bb19ef5b6"
        in document
    )
    assert "5,989 rows per table" in document
    assert (
        "does not establish rights, production admission, publication, promotion"
        in document
    )
    assert "or full M-109 acceptance" in document


def test_m109_identity_inventory_records_current_pinned_sources_only() -> None:
    report = _json(
        "quality/qualifications/australian-m109-source-era-identities-20261017.json"
    )
    mbs = report["mbs"]
    sources = mbs["sources"]
    assert len(sources) == mbs["observed_exact_source_count"] == 8
    assert len({source["path"] for source in sources}) == 8
    manifest_paths = [
        path
        for source in sources
        for path in source.get("manifest_paths", [source["path"]])
    ]
    assert len(manifest_paths) == mbs["observed_manifest_path_entry_count"] == 9
    assert len(set(manifest_paths)) == 9
    assert all(
        source["identity_status"] == "verified_in_current_pinned_root_manifest"
        for source in sources
    )
    assert (
        report["readback"]["mbs"]["current_revision"]
        == "3d2d528439bddf6f42e8e700c88917f0960a9f38"
    )
    assert (
        report["readback"]["mbs"]["manifest_sha256"]
        == "7afe928933fece384f8459dd268fcd2c4f26c8325dc52577f7a1582e8d63a0ac"
    )
    assert mbs["expected_source_denominator_complete"] is False
    assert report["acceptance"]["m109_accepted"] is False
    assert (
        report["boundaries"]["source_payload_bytes_requested_or_downloaded"]
        is False
    )
    expected_mbs = {
        "raw/mbs/legacy/2024-07/MBS-2024.07-Group-P7-Genetics.xlsx": (
            "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8",
            87727,
        ),
        "raw/mbs/2025-07/MBS-XML-20250701-Version-3.XML": (
            "db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556",
            8194522,
        ),
        "raw/mbs/releases/Downloads-20260101/MBS-XML-20260101.XML": (
            "352448dc912b3e2125f2acd56b6094da13de7f229022a498c21848a0fcdc2299",
            8215319,
        ),
        "raw/mbs/releases/Downloads-20260301/MBS-XML-20260301.XML": (
            "252a06590143428ab49aca79302dc0f1e4e4c2726cf36859d1673e6521e31ded",
            8271558,
        ),
        "raw/mbs/releases/Downloads-20260301/MBS-XML-20260301-version 2.XML": (
            "e6ed9cf794a73e0a9d10c6ffca931f29cce899d720fb7377fe4f5d64dc2b9561",
            8271294,
        ),
        "raw/mbs/releases/Downloads-20260701/MBS-XML-20260701.XML": (
            "5834d849743a3eab2b8c03e826a5ed6a488a6f65cf4c4148da3ec227e5007805",
            8291891,
        ),
        "raw/mbs/releases/Downloads-20260801/MBS-XML-20260801.XML": (
            "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565",
            8293331,
        ),
        "raw/mbs/releases/Downloads-20261101/MBS-XML-20261101.XML": (
            "11ccca0f16826e5089ae451b51fafd42b2a2a436ac97eea593de077dc4200cc4",
            8297608,
        ),
    }
    assert {
        source["path"]: (source["sha256"], source["bytes"])
        for source in sources
    } == expected_mbs
    august = next(
        source for source in sources if source["source_era"] == "2026-08-01"
    )
    assert august["manifest_paths"] == [
        "raw/mbs/releases/2026-08-01/c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565.xml",
        "raw/mbs/releases/Downloads-20260801/MBS-XML-20260801.XML",
    ]
    assert august["sha256"] == (
        "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565"
    )
    assert august["bytes"] == 8293331


def test_m109_inventory_keeps_mbs_authorization_and_pbs_rights_separate() -> (
    None
):
    report = _json(
        "quality/qualifications/australian-m109-source-era-identities-20261017.json"
    )
    legacy = _json(
        "quality/qualifications/australian-health-legacy-publication-authorization.json"
    )
    harvest = _json(
        "quality/qualifications/australian-mbs-harvest-publication-authorization.json"
    )
    rights = _json("quality/qualifications/source-rights-review-ledger.json")
    legacy_payloads = {
        payload["archive_path"]: payload["sha256"]
        for donor in legacy["donors"]
        for payload in donor["payloads"]
    }
    for source in report["mbs"]["sources"]:
        if source["rights_basis_ref"] == "legacy_exact_payloads":
            assert legacy_payloads[source["path"]] == source["sha256"]
        else:
            assert "monthly_schedule_xml" in harvest["categories"]
    assert report["pbs"]["approved_for_m109_processing"] is False
    assert (
        report["pbs"]["rights_state"]
        == "unknown_per_source_rights_review_ledger"
    )
    pbs_rights = next(
        entry
        for entry in rights["entries"]
        if entry["source_id"] == "au-pbs-historical-xml"
    )
    assert pbs_rights["redistribute"] == "unknown"
    pbs_profile = _json(
        "quality/qualifications/pbs-v3-2026-04-01-date-profile-qualification-20260929.json"
    )
    pbs_source = report["pbs"]["sources"][0]
    assert (
        pbs_source["archive"]["path"] == pbs_profile["source"]["archive_path"]
    )
    assert (
        pbs_source["archive"]["sha256"]
        == pbs_profile["source"]["archive_sha256"]
    )
    assert pbs_source["archive"]["bytes"] == 11156706
    assert pbs_source["member"]["path"] == pbs_profile["source"]["member_path"]
    assert (
        pbs_source["member"]["sha256"] == pbs_profile["source"]["member_sha256"]
    )
    assert pbs_source["member"]["bytes"] == 313437585
    assert (
        pbs_source["manifest_sha256"]
        == pbs_profile["source"]["manifest_sha256"]
    )
    assert (
        report["acceptance"]["expected_source_era_denominator_complete"]
        is False
    )
