"""Integrity and scope checks for the value-free M-107 PBS link crosswalk."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import scripts.reconcile_australian_historical_coverage as history_coverage
import scripts.reconcile_pbs_m107_existing_archive as existing_archive
from scripts.build_pbs_m107_link_crosswalk import validate_public_tree_readback
from scripts.pbs_m107_receipt_binding import validate_pbs_receipt_binding

REPORT = Path(
    "quality/qualifications/australian-pbs-m107-link-crosswalk-20261018.json"
)
INDEX = Path(
    "quality/qualifications/australian-pbs-schedule-index-metadata-20261018.json"
)
IDENTITIES = Path(
    "quality/qualifications/australian-m109-source-era-identities-20261017.json"
)
RIGHTS = Path("quality/qualifications/source-rights-review-ledger.json")
M112 = Path(
    "quality/qualifications/australian-m112-per-object-gate-reconciliation-20261018-pbs-receipt-binding.json"
)
READBACK = Path(
    "quality/qualifications/australian-pbs-m107-known-object-manifest-readback-20261018.json"
)
PUBLIC_TREE = Path(
    "quality/qualifications/australian-pbs-m107-public-tree-readback-20261018.json"
)
EXISTING_ARCHIVE_REPORT = Path(
    "quality/qualifications/australian-pbs-m107-existing-archive-crosswalk-20261115.json"
)


def test_existing_pbs_archive_crosswalk_preserves_identity_and_privacy() -> (
    None
):
    report = existing_archive.build_report()
    assert report == json.loads(
        EXISTING_ARCHIVE_REPORT.read_text(encoding="utf-8")
    )
    assert report["result"] == {
        "official_link_occurrences": 316,
        "previously_unresolved_occurrences": 315,
        "newly_matched_occurrences": 311,
        "newly_matched_distinct_urls": 310,
        "newly_matched_distinct_archive_paths": 310,
        "matched_occurrences": 312,
        "matched_distinct_urls": 311,
        "matched_distinct_archive_paths": 312,
        "matched_reimbursement_b1_records": 311,
        "unmatched_occurrences": 4,
        "new_unique_admissions": 0,
    }
    assert all(value is False for value in report["boundaries"].values())
    links = report["links"]
    unresolved = [
        row for row in links if row["identity_status"] == "unresolved"
    ]
    assert len(unresolved) == 4
    assert all(not row["candidates"] for row in unresolved)
    assert all(
        row["publisher_head_observation"]["status"] == 200 for row in unresolved
    )
    candidates = [candidate for row in links for candidate in row["candidates"]]
    assert all(
        candidate["payload_read_qualified"] is False for candidate in candidates
    )
    assert all(
        candidate["v4_admission"] == "not_performed" for candidate in candidates
    )
    reimbursement = [
        candidate
        for candidate in candidates
        if candidate["dataset"] == existing_archive.prior.DATASET
    ]
    assert all(
        candidate["observed_sensitivity"]
        == existing_archive.UNKNOWN_SENSITIVITY
        for candidate in reimbursement
    )
    assert all(
        candidate["consumer_check"] == "not_performed_privacy_gate_blocked"
        for candidate in reimbursement
    )
    mirrors = next(
        row["candidates"] for row in links if len(row["candidates"]) == 2
    )
    assert {candidate["dataset"] for candidate in mirrors} == {
        existing_archive.SOURCE_ARCHIVE,
        existing_archive.prior.DATASET,
    }
    assert (
        len({
            (candidate["sha256"], candidate["byte_count"])
            for candidate in mirrors
        })
        == 1
    )
    source = next(
        candidate
        for candidate in mirrors
        if candidate["dataset"] == existing_archive.SOURCE_ARCHIVE
    )
    assert (
        source["rights_conflict"]
        == "receipt_permitted_claim_source_ledger_unknown"
    )
    assert source["privacy_gate"] == "not_qualified_in_selected_evidence"


def test_existing_pbs_crosswalk_requires_exact_url_and_unique_identity() -> (
    None
):
    source = {
        "source_locator": "https://www.pbs.gov.au/publication/schedule/a.zip?variant=3",
        "dataset": "example",
        "path": "raw/a.zip",
        "sha256": "a" * 64,
        "byte_count": 50,
    }
    indexed = existing_archive._candidate_index([source])
    assert (
        indexed.get(source["source_locator"].replace("variant=3", "variant=2"))
        is None
    )
    with pytest.raises(ValueError, match="duplicate archive identity"):
        existing_archive._candidate_index([source, source.copy()])


def test_existing_pbs_crosswalk_rejects_wrong_b1_url_or_digest() -> None:
    url = "https://www.pbs.gov.au/publication/schedule/a.zip?variant=3"
    event = {
        "retrieval": {"uri": url, "status": "succeeded"},
        "payload_sha256": "a" * 64,
    }
    existing_archive._validate_b1_event(event, url=url, digest="a" * 64)
    with pytest.raises(ValueError, match="identity differs"):
        existing_archive._validate_b1_event(
            event, url=url.replace("variant=3", "variant=2"), digest="a" * 64
        )
    with pytest.raises(ValueError, match="identity differs"):
        existing_archive._validate_b1_event(event, url=url, digest="b" * 64)


def test_existing_pbs_crosswalk_rejects_privacy_promotion() -> None:
    batch = json.loads(
        Path(existing_archive.INPUTS["batch"][0]).read_text(encoding="utf-8")
    )
    row = next(
        item
        for item in batch["objects"]
        if item["representation"] == "raw_source_payload"
    )
    rights = json.loads(
        Path(existing_archive.INPUTS["rights"][0]).read_text(encoding="utf-8")
    )
    source = next(
        item
        for item in rights["pbs_raw_redistribution_permission"]["objects"]
        if item["path"] == row["path"]
    )
    row["ready_for_payload_read"] = True
    with pytest.raises(ValueError, match="privacy gate differs"):
        existing_archive._reimbursement_candidate(
            Path.cwd(), source, row, url=source["source_locator"]
        )


def test_four_link_observation_is_not_an_identity_or_absence_claim() -> None:
    observation = json.loads(
        Path(existing_archive.INPUTS["observation"][0]).read_text(
            encoding="utf-8"
        )
    )
    assert len(existing_archive._probe_index(observation)) == 4
    assert observation["boundaries"]["missing_objects_declared_absent"] is False
    observation["publisher_probe"]["response_bodies_read"] = True
    with pytest.raises(ValueError, match="boundary differs"):
        existing_archive._probe_index(observation)


def _binding_inputs() -> tuple[dict, dict, dict, dict, dict]:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))
    rights = json.loads(RIGHTS.read_text(encoding="utf-8"))
    m112 = json.loads(M112.read_text(encoding="utf-8"))
    readback = json.loads(READBACK.read_text(encoding="utf-8"))
    pbs_rights = next(
        item
        for item in rights["entries"]
        if item["source_id"] == "au-pbs-historical-xml"
    )
    return index, identities, m112, readback, pbs_rights


def _refresh_readback_digest(readback: dict) -> None:
    unsigned = dict(readback)
    unsigned.pop("canonical_sha256", None)
    unsigned.pop("canonical_byte_count", None)
    canonical = json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    readback["canonical_sha256"] = hashlib.sha256(canonical).hexdigest()
    readback["canonical_byte_count"] = len(canonical)


def _report() -> dict[str, object]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _public_tree_binding_inputs() -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any]
]:
    identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))
    source = next(
        item
        for item in identities["pbs"]["sources"]
        if item["source_era"] == "2026-04-01-xml-v3"
    )
    tree = json.loads(PUBLIC_TREE.read_text(encoding="utf-8"))
    return identities, source, tree


def _validate_public_tree(
    tree: dict[str, Any],
    identities: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    return validate_public_tree_readback(
        tree,
        expected_revision=identities["readback"]["pbs"]["current_revision"],
        expected_source_path=source["archive"]["path"],
        expected_source_bytes=source["archive"]["bytes"],
        expected_source_sha256=source["archive"]["sha256"],
    )


def test_pbs_m107_crosswalk_is_complete_for_observed_schedule_links() -> None:
    report = _report()
    digest = report["digest"]
    assert isinstance(digest, dict)
    expected = digest.pop("value")
    canonical = json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(canonical).hexdigest() == expected

    scope = report["scope"]
    links = report["links"]
    assert isinstance(scope, dict)
    assert isinstance(links, list)
    assert len(links) == 316
    assert scope["official_schedule_link_count"] == len(links)
    assert scope["distinct_schedule_periods"] == 197
    assert scope["known_public_object_link_count"] == 1
    assert scope["public_archive_raw_file_count"] == 1
    assert scope["exact_official_url_to_b1_receipt_metadata_count"] == 1
    assert scope["unresolved_archive_identity_link_count"] == 315
    assert all(link["source_payload_requested"] is False for link in links)


def test_pbs_m107_crosswalk_binds_the_complete_public_raw_tree_inventory() -> (
    None
):
    report = _report()
    inventory = report["public_archive_inventory"]

    assert inventory["dataset"] == "edithatogo/australian-pbs-source-archive"
    assert inventory["revision"] == "48fd7345fb09277bb5b85644dba72804633a2abb"
    assert inventory["tree_http_status"] == 200
    assert inventory["tree_response_bytes"] == 2388
    assert inventory["tree_response_sha256"] == (
        "6e85e905b139d04c84f77f42de988866ecf0ab780c7d5e2a1388a5348a5da33a"
    )
    assert inventory["file_count"] == 9
    raw_files = inventory["raw_files"]
    assert raw_files == [
        {
            "path": "raw/2026-04-01/2026-04-01-XML-V3.zip",
            "bytes": 11156706,
            "sha256": "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20",
            "sha256_evidence": "independent_manifest_and_receipt_readback",
            "official_url": (
                "https://www.pbs.gov.au/publication/schedule/2026/04/"
                "2026-04-01-XML-V3.zip?variant=3"
            ),
            "url_binding_status": "exact_official_url_to_b1_receipt_metadata",
        }
    ]
    assert inventory["source_payload_bytes_read"] == 0
    assert inventory["response_body_retained"] is True
    assert inventory["interpretation"] == (
        "The pinned public tree contains one raw schedule path; other official "
        "links remain unresolved, not absent."
    )
    input_digests = {item["path"]: item["sha256"] for item in report["inputs"]}
    assert (
        input_digests[
            "quality/qualifications/australian-pbs-m107-public-tree-readback-20261018.json"
        ]
        == hashlib.sha256(PUBLIC_TREE.read_bytes()).hexdigest()
    )


def test_public_tree_readback_rejects_an_unpinned_revision() -> None:
    identities, source, tree = _public_tree_binding_inputs()
    tree["revision"] = "0" * 40

    with pytest.raises(ValueError, match="revision differs"):
        _validate_public_tree(tree, identities, source)


def test_public_tree_readback_rejects_changed_raw_path_or_size() -> None:
    identities, source, tree = _public_tree_binding_inputs()
    raw = next(
        item for item in tree["files"] if item["path"].startswith("raw/")
    )
    raw["bytes"] += 1

    with pytest.raises(
        ValueError, match="inventory differs from response body"
    ):
        _validate_public_tree(tree, identities, source)


def test_public_tree_readback_rejects_duplicate_paths() -> None:
    identities, source, tree = _public_tree_binding_inputs()
    tree["files"].append(dict(tree["files"][0]))
    tree["file_count"] += 1

    with pytest.raises(ValueError, match="duplicate paths"):
        _validate_public_tree(tree, identities, source)


def test_public_tree_readback_rejects_fabricated_non_raw_inventory_row() -> (
    None
):
    identities, source, tree = _public_tree_binding_inputs()
    tree["files"][0]["bytes"] += 1

    with pytest.raises(ValueError, match="differs from response body"):
        _validate_public_tree(tree, identities, source)


def test_public_tree_readback_rejects_response_body_digest_mismatch() -> None:
    identities, source, tree = _public_tree_binding_inputs()
    tree["tree"]["response_body_base64"] = "W10="

    with pytest.raises(ValueError, match="does not match its response digest"):
        _validate_public_tree(tree, identities, source)


def test_pbs_m107_crosswalk_keeps_identity_rights_and_absence_claims_bounded() -> (
    None
):
    report = _report()
    scope = report["scope"]
    assert isinstance(scope, dict)
    assert scope["source_payloads_read"] is False
    assert scope["rights_concluded"] is False
    assert scope["m107_accepted"] is False

    links = report["links"]
    assert isinstance(links, list)
    known = [
        link
        for link in links
        if link["archive_identity_status"]
        == "date_format_label_match_to_known_public_object"
    ]
    assert len(known) == 1
    assert known[0]["source_receipt_binding"]["status"] == (
        "exact_official_url_to_b1_receipt_metadata"
    )
    assert known[0]["known_object"]["path"] == (
        "raw/2026-04-01/2026-04-01-XML-V3.zip"
    )
    assert (
        known[0]["known_object"]["m112_disposition"] == "deferred_not_admitted"
    )
    assert all(
        link["rights"]["disposition"] == "catalogue_only" for link in links
    )
    assert all(
        link["archive_identity_status"] != "source_absent" for link in links
    )

    interpretation = report["interpretation"]
    assert isinstance(interpretation, dict)
    assert (
        "exact official URL-to-B1-receipt join"
        in interpretation["known_object_match_boundary"]
    )
    assert "not evidence" in interpretation["unresolved_boundary"]


def test_pbs_receipt_binding_matches_exact_url_but_keeps_rights_conflict_open() -> (
    None
):
    binding = validate_pbs_receipt_binding(*_binding_inputs())

    assert binding["status"] == "exact_official_url_to_b1_receipt_metadata"
    assert binding["official_url"] == (
        "https://www.pbs.gov.au/publication/schedule/2026/04/"
        "2026-04-01-XML-V3.zip?variant=3"
    )
    assert binding["b1_receipt"]["payload_sha256"] == (
        "f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20"
    )
    assert binding["rights_reconciliation_status"] == (
        "receipt_permitted_claim_source_ledger_unknown"
    )
    assert binding["m112_object_remains_deferred"] is True
    assert binding["m112_v4_admission"] is False
    assert binding["m112_consumer_canary"] is False


def test_pbs_receipt_binding_rejects_url_or_digest_mismatch() -> None:
    index, identities, m112, readback, rights = _binding_inputs()
    readback["source_receipt"]["final_uri"] = (
        "https://example.invalid/other.zip"
    )
    _refresh_readback_digest(readback)

    with pytest.raises(ValueError, match="source URL bindings"):
        validate_pbs_receipt_binding(index, identities, m112, readback, rights)

    index, identities, m112, readback, rights = _binding_inputs()
    readback["source_receipt"]["payload"]["sha256"] = "0" * 64
    _refresh_readback_digest(readback)
    with pytest.raises(ValueError, match="payload identities"):
        validate_pbs_receipt_binding(index, identities, m112, readback, rights)


def test_pbs_receipt_binding_requires_anonymous_raw_object_digest_readback() -> (
    None
):
    index, identities, m112, readback, rights = _binding_inputs()
    pbs_object = next(
        item
        for item in m112["objects"]
        if item["path"] == "raw/2026-04-01/2026-04-01-XML-V3.zip"
    )
    pbs_object["identity"]["anonymous_digest_readback"] = False

    with pytest.raises(ValueError, match="anonymous raw-object digest"):
        validate_pbs_receipt_binding(index, identities, m112, readback, rights)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("acquisition_id", "0" * 64),
        ("receipt_id", "substituted-receipt"),
        ("path", "bronze/other/source-receipt.json"),
        ("sha256", "0" * 64),
    ],
)
def test_pbs_binding_rejects_rehashed_unbound_receipt_identity(
    field: str, value: str
) -> None:
    index, identities, m112, readback, rights = _binding_inputs()
    readback["source_receipt"][field] = value
    _refresh_readback_digest(readback)

    with pytest.raises(ValueError, match="manifest receipt reference"):
        validate_pbs_receipt_binding(index, identities, m112, readback, rights)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("acquisition_id", "0" * 64),
        ("path", "bronze/other/source-receipt.json"),
        ("sha256", "0" * 64),
        ("retrieved_at", "2026-01-01T00:00:00Z"),
    ],
)
def test_pbs_binding_rejects_rehashed_manifest_receipt_reference(
    field: str, value: str
) -> None:
    index, identities, m112, readback, rights = _binding_inputs()
    readback["manifest_source_receipt"][field] = value
    _refresh_readback_digest(readback)

    with pytest.raises(ValueError, match="manifest receipt reference"):
        validate_pbs_receipt_binding(index, identities, m112, readback, rights)


def _historical_fixture() -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    base = "raw/pbs/utilisation/legacy/item/identity/report.zip"
    version = "a" * 64
    raw_path = f"raw/pbs/utilisation/legacy/item/identity/versions/{version}/report.zip"
    receipt_path = raw_path.replace("raw/", "bronze/", 1) + ".receipt.json"
    resources = [
        {
            "source_id": "au-pbs-item",
            "category": "legacy_pbs_item",
            "url": "https://example.invalid/report.zip",
            "filename": "report.zip",
            "archive_path": base,
            "period_label": "historical",
        }
    ]
    manifest = [
        {
            "kind": "raw_payload",
            "source_id": "au-pbs-item",
            "path": raw_path,
            "sha256": version,
            "bytes": 10,
        },
        {
            "kind": "b1_receipt",
            "source_id": "au-pbs-item",
            "path": receipt_path,
            "sha256": "b" * 64,
            "bytes": 2,
        },
    ]
    tree = [
        {
            "path": raw_path,
            "size": 10,
            "git_oid": "c" * 40,
            "lfs_sha256": version,
        },
        {
            "path": receipt_path,
            "size": 2,
            "git_oid": "d" * 40,
            "lfs_sha256": None,
        },
    ]
    return resources, manifest, tree


def test_historical_resource_reconciliation_preserves_versions_and_evidence() -> (
    None
):
    resources, manifest, tree = _historical_fixture()
    report = history_coverage.match_pbs_resources(resources, manifest, tree)
    assert len(report) == 1
    assert report[0]["match_status"] == "matched_manifest_and_tree"
    assert (
        report[0]["matches"][0]["payload_tree_check"] == "lfs_sha256_and_size"
    )
    assert report[0]["matches"][0]["receipt_tree_check"] == "git_blob_and_size"
    assert report[0]["matches"][0]["receipt_content_checked"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_source",
        "wrong_version",
        "missing_receipt",
        "wrong_lfs",
        "missing_tree",
    ],
)
def test_historical_resource_reconciliation_fails_closed(mutation: str) -> None:
    resources, manifest, tree = _historical_fixture()
    if mutation == "wrong_source":
        manifest[0]["source_id"] = "other-source"
    elif mutation == "wrong_version":
        manifest[0]["sha256"] = "f" * 64
    elif mutation == "missing_receipt":
        manifest.pop()
    elif mutation == "wrong_lfs":
        tree[0]["lfs_sha256"] = "0" * 64
    else:
        tree.pop()
    with pytest.raises(ValueError, match=r"differ|missing|unmatched"):
        history_coverage.match_pbs_resources(resources, manifest, tree)


def test_historical_resource_reconciliation_keeps_distinct_versions() -> None:
    resources, manifest, tree = _historical_fixture()
    raw_path = resources[0]["archive_path"]
    receipt_path = raw_path.replace("raw/", "bronze/", 1) + ".receipt.json"
    manifest.extend([
        {
            "kind": "raw_payload",
            "source_id": "au-pbs-item",
            "path": raw_path,
            "sha256": "e" * 64,
            "bytes": 11,
        },
        {
            "kind": "b1_receipt",
            "source_id": "au-pbs-item",
            "path": receipt_path,
            "sha256": "f" * 64,
            "bytes": 3,
        },
    ])
    tree.extend([
        {"path": raw_path, "size": 11, "git_oid": "1" * 40, "lfs_sha256": None},
        {
            "path": receipt_path,
            "size": 3,
            "git_oid": "2" * 40,
            "lfs_sha256": None,
        },
    ])
    matches = history_coverage.match_pbs_resources(resources, manifest, tree)[
        0
    ]["matches"]
    assert len(matches) == 2
    assert {item["sha256"] for item in matches} == {"a" * 64, "e" * 64}
    assert {item["payload_tree_check"] for item in matches} == {
        "lfs_sha256_and_size",
        "git_blob_and_size",
    }


def test_mbs_historical_index_comparison_rejects_changed_git_identity() -> None:
    resources = [
        {
            "current_archive_receipt": True,
            "source_url": "https://example.invalid/source.xml",
            "page_label": "fixture",
            "matching_archive_receipts": [
                {
                    "archive_path": "raw/source.xml",
                    "receipt_path": "bronze/source.json",
                    "payload_sha256": "a" * 64,
                }
            ],
        }
    ]
    old = [
        {
            "path": "raw/source.xml",
            "size": 12,
            "git_oid": "1" * 40,
            "lfs_sha256": None,
        },
        {
            "path": "bronze/source.json",
            "size": 2,
            "git_oid": "2" * 40,
            "lfs_sha256": None,
        },
    ]
    current = [dict(row) for row in old]
    assert history_coverage.match_mbs_resources(resources, current, old)[0][
        "same_git_objects_and_sizes_at_both_revisions"
    ]
    current[0]["git_oid"] = "3" * 40
    with pytest.raises(ValueError, match="tree identity differs"):
        history_coverage.match_mbs_resources(resources, current, old)


@pytest.mark.parametrize(
    "match_kind", ["output_id", "lfs_digest", "parquet_size"]
)
def test_historical_delta_screen_rejects_possible_matches(
    match_kind: str,
) -> None:
    candidate = {
        "output_id": "a" * 64,
        "parquet_sha256": "b" * 64,
        "parquet_bytes": 101,
    }
    changed = {
        "path": "unrelated/file.txt",
        "git_oid": "c" * 40,
        "lfs_sha256": None,
        "size": 10,
    }
    history_coverage.screen_derived_delta([changed], [candidate])
    if match_kind == "output_id":
        changed["path"] = f"new/{candidate['output_id']}.parquet"
    elif match_kind == "lfs_digest":
        changed["lfs_sha256"] = candidate["parquet_sha256"]
    else:
        changed["path"] = "new/file.parquet"
        changed["size"] = candidate["parquet_bytes"]
    with pytest.raises(ValueError, match="possible historical workbook output"):
        history_coverage.screen_derived_delta([changed], [candidate])


def test_historical_coverage_report_retains_scope_and_limitations() -> None:
    report = json.loads(Path(history_coverage.OUTPUT).read_bytes())
    pbs = report["pbs_utilisation"]
    assert pbs["discovered_resources"] == pbs["matched_resources"] == 505
    assert pbs["authorized_additional_subset"] == 120
    assert pbs["matched_payload_paths"] == pbs["paired_receipts"] == 508
    assert pbs["payload_lfs_digest_checks"] == 121
    assert pbs["payload_git_blob_size_checks"] == 387
    assert pbs["multiple_path_resources"] == 3
    assert pbs["multiple_path_resources_with_distinct_digests"] == 2
    assert pbs["multiple_path_resources_with_one_digest"] == 1
    assert report["mbs_schedule"]["indexed_xml_links"] == 82
    assert (
        report["historical_workbook_output_search"]["candidate_outputs"] == 91
    )
    assert (
        report["historical_workbook_output_search"][
            "new_possible_matches_in_checked_deltas"
        ]
        == 0
    )
    assert report["open_coverage"]["m107"] == "blocked"
    assert len(report["open_coverage"]["pbs_schedule_unmatched"]) == 4
    assert not any(report["boundaries"].values())
