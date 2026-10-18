"""Integrity and scope checks for the value-free M-107 PBS link crosswalk."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
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
    assert scope["exact_official_url_to_b1_receipt_metadata_count"] == 1
    assert scope["unresolved_archive_identity_link_count"] == 315
    assert all(link["source_payload_requested"] is False for link in links)


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
