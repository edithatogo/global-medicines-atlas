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
    assert len(sources) == mbs["observed_unique_payload_count"] == 86
    assert len({source["sha256"] for source in sources}) == 86
    manifest_paths = [
        path for source in sources for path in source["manifest_paths"]
    ]
    assert (
        len(manifest_paths) == mbs["observed_manifest_path_entry_count"] == 90
    )
    assert len(set(manifest_paths)) == 90
    assert all(
        source["identity_status"] == "verified_in_current_pinned_root_manifest"
        for source in sources
    )
    assert report["readback"]["mbs"]["current_revision"] == (
        "da83cad9116e2f9a5b927be7b080e9a5e5ea6998"
    )
    assert report["readback"]["mbs"]["manifest_sha256"] == (
        "68e6bb97ee43117b860ff1c57e625a00075c734e933d08b3cd67de673432d055"
    )
    assert mbs["expected_source_denominator_complete"] is False
    assert report["acceptance"]["m109_accepted"] is False
    assert (
        report["boundaries"]["source_payload_bytes_requested_or_downloaded"]
        is False
    )
    by_path = {
        path: (source["sha256"], source["bytes"])
        for source in sources
        for path in source["manifest_paths"]
    }
    assert by_path[
        "raw/mbs/legacy/2024-07/MBS-2024.07-Group-P7-Genetics.xlsx"
    ] == (
        "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8",
        87727,
    )
    assert by_path[
        "raw/mbs/releases/Downloads-250101/MBS-XML-20250101.xml"
    ] == (
        "3736a72716158fc034705ede4e695dc470ccc98daff48b0533601eef2458340e",
        8165147,
    )
    assert by_path[
        "raw/mbs/releases/Downloads-250301/MBS-XML-20250301.XML"
    ] == (
        "15140d523b1ea70dc1fd4bdf2b9bbc66cf6af8233315b6fbd61e097df8b21a12",
        8149632,
    )
    assert by_path[
        "raw/mbs/releases/Downloads-251101/MBS-XML-20251101.XML"
    ] == (
        "d738fd6eb0a8a60f276787ec6eab9f860e3de4bfefdd8c81ed5ab83eae1d8624",
        8215464,
    )
    assert by_path[
        "raw/mbs/releases/Downloads-251101/MBS-XML-20251101 Version 2.XML"
    ] == (
        "875a45e690d86925c5531e6d2d1bd692e8235935bd01423b623ba5801fa1c441",
        8215371,
    )
    august = next(
        source for source in sources if source.get("source_era") == "2026-08-01"
    )
    assert august["manifest_paths"] == [
        "raw/mbs/releases/2026-08-01/c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565.xml",
        "raw/mbs/releases/Downloads-20260801/MBS-XML-20260801.XML",
    ]
    assert august["sha256"] == (
        "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565"
    )
    assert august["bytes"] == 8293331


def test_m109_inventory_tracks_latest_mbs_archive_metadata_readback() -> None:
    report = _json(
        "quality/qualifications/australian-m109-source-era-identities-20261017.json"
    )
    m108 = _json(
        "quality/qualifications/australian-m108-derived-products-20261017.json"
    )
    latest = m108["latest_mbs_archive_append_readback"]
    mbs = report["mbs"]
    readback = report["readback"]["mbs"]

    assert readback["current_revision"] == latest["revision"]
    assert readback["manifest_sha256"] == latest["root_manifest_sha256"]
    assert (
        readback["manifest_file_count"] == latest["root_manifest_object_count"]
    )
    assert mbs["expected_source_denominator_complete"] is False
    assert report["acceptance"]["m109_accepted"] is False

    observed_paths = {
        path for source in mbs["sources"] for path in source["manifest_paths"]
    }
    assert {
        "raw/mbs/releases/Downloads-250101/MBS-XML-20250101.xml",
        "raw/mbs/releases/Downloads-250301/MBS-XML-20250301.XML",
        "raw/mbs/releases/Downloads-251101/MBS-XML-20251101.XML",
        "raw/mbs/releases/Downloads-251101/MBS-XML-20251101 Version 2.XML",
    } <= observed_paths


def test_august_six_table_handoff_keeps_rights_and_candidate_state_separate() -> (
    None
):
    m108 = _json(
        "quality/qualifications/australian-m108-derived-products-20261017.json"
    )
    handoff = m108["august_2026_six_table_operation_assessment"]
    source = handoff["source"]
    authority = handoff["authorization"]
    destination = handoff["proposed_destination"]

    assert (
        source["archive_revision"] == "da83cad9116e2f9a5b927be7b080e9a5e5ea6998"
    )
    assert source["sha256"] == (
        "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565"
    )
    assert source["official_release_match"] is True
    assert authority["raw_archive_approval"].endswith("comment-5467052330")
    assert authority["derived_output_authority"] == "absent"
    assert authority["publication_performed"] is False
    assert (
        destination["identity_status"]
        == "proposal_only_not_created_or_admitted"
    )
    outputs = destination["outputs"]
    assert [output["table"] for output in outputs] == [
        "services",
        "hierarchy",
        "descriptions",
        "fees",
        "benefits",
        "caps",
    ]
    assert all(output["rows"] == 6046 for output in outputs)
    assert (
        handoff["candidate_diagnostics"]["run_39032003723"][
            "field_semantics_accepted"
        ]
        is False
    )
    assert "source-owner clarification" in handoff["smallest_next_action"]
    assert "keep derived outputs blocked" in handoff["smallest_next_action"]


def test_august_predecessor_comparison_is_bounded_and_non_promoting() -> None:
    m108 = _json(
        "quality/qualifications/australian-m108-derived-products-20261017.json"
    )
    handoff = m108["august_2026_six_table_operation_assessment"]
    plan = handoff["predecessor_comparison_plan"]
    predecessor = plan["exact_predecessor"]

    assert plan["status"] == (
        "exact_main_aggregate_comparison_complete_semantics_unqualified"
    )
    assert predecessor["edition"] == "MBS-XML-20260701.XML"
    assert predecessor["official_publication_date"] == "2026-05-28"
    assert predecessor["effective_date"] == "2026-07-01"
    assert predecessor["sha256"] == (
        "5834d849743a3eab2b8c03e826a5ed6a488a6f65cf4c4148da3ec227e5007805"
    )
    assert plan["authorization"]["derived_output_authority"] == (
        "absent; this comparison does not authorize derived Parquet distribution"
    )
    assert plan["implementation"]["script"] == (
        "scripts/compare_mbs_source_eras.py"
    )
    assert plan["implementation"]["full_profile"]["failed"] == 1
    assert "monthly_schedule_xml" in plan["rights_references"]["boundary"]
    assert (
        "keep record keys and source values in memory" in plan["procedure"][2]
    )
    assert plan["failure_and_recovery"]["mismatch_or_timeout"].startswith(
        "Mark the comparison incomplete"
    )
    readback = plan["exact_main_readback"]
    assert readback["commit"] == ("f6cccb0beb66d5a1322149f33dc61820eea05166")
    assert readback["workflow_run"].endswith("/39047005443")
    assert readback["matched_records"] == 6045
    assert readback["added_records"] == 1
    assert readback["removed_records"] == 0
    assert readback["semantics_accepted"] is False
    assert readback["m109_accepted"] is False
    assert (
        "do not establish that field meanings remained unchanged"
        in plan["interpretation_boundary"]
    )


def test_exact_main_predecessor_comparison_receipt_stays_aggregate_only() -> (
    None
):
    report = _json(
        "quality/qualifications/"
        "australian-m109-july-august-predecessor-comparison-20261018.json"
    )

    assert report["status"] == "aggregate_comparison_complete"
    assert report["exact_commit"] == (
        "f6cccb0beb66d5a1322149f33dc61820eea05166"
    )
    assert [release["record_count"] for release in report["releases"]] == [
        6045,
        6046,
    ]
    assert all(
        release["archive_official_identity_match"] is True
        for release in report["releases"]
    )
    comparison = report["comparison"]
    assert comparison["matched_record_count"] == 6045
    assert comparison["added_record_count"] == 1
    assert comparison["removed_record_count"] == 0
    assert comparison["changed_record_count"] == 5445
    assert report["source_identifiers_emitted"] is False
    assert report["source_values_retained"] is False
    assert report["silver_generated"] is False
    assert report["semantics_accepted"] is False
    assert report["m109_accepted"] is False


def test_field_guide_semantic_history_preserves_the_unresolved_boundary() -> (
    None
):
    report = _json(
        "quality/qualifications/"
        "australian-mbs-field-guide-semantic-history-20261018.json"
    )

    assert report["status"] == (
        "documented_wording_delta_and_source_conflict_observed_history_gap_open"
    )
    item_change, emsn_cap = report["field_comparisons"]
    assert item_change["field"] == "ItemChange"
    assert "item number" in item_change["november_2013_description"]
    assert "change to the item" in item_change["february_2022_description"]
    assert emsn_cap["field"] == "EMSNCap"
    assert "N means no current" in emsn_cap["current_official_help_page"]
    assert "Y means a current" in emsn_cap["february_2022_pdf"]
    assert "conflicts" in emsn_cap["finding"]
    assert report["unresolved_history"]["release_semantics_qualified"] is False
    assert (
        report["qualification_boundaries"]["source_release_mapping_selected"]
        is False
    )
    assert report["qualification_boundaries"]["semantic_promotion"] is False
    assert report["qualification_boundaries"]["m109_accepted"] is False


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
        assert source["rights_basis_refs"]
        for path in source["manifest_paths"]:
            if path in legacy_payloads:
                assert legacy_payloads[path] == source["sha256"]
            if path.endswith((".xml", ".XML")) and "releases/" in path:
                assert "monthly_schedule_xml" in source[
                    "rights_basis_refs"
                ] or (
                    path == "raw/mbs/2025-07/MBS-XML-20250701-Version-3.XML"
                    and "legacy_exact_payloads" in source["rights_basis_refs"]
                )
        if "monthly_schedule_xml" in source["rights_basis_refs"]:
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
