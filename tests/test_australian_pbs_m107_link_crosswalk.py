"""Integrity and scope checks for the value-free M-107 PBS link crosswalk."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
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
    assert inventory["response_body_retained"] is False
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

    with pytest.raises(ValueError, match="known B1/B2 identity"):
        _validate_public_tree(tree, identities, source)


def test_public_tree_readback_rejects_duplicate_paths() -> None:
    identities, source, tree = _public_tree_binding_inputs()
    tree["files"].append(dict(tree["files"][0]))
    tree["file_count"] += 1

    with pytest.raises(ValueError, match="duplicate paths"):
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
