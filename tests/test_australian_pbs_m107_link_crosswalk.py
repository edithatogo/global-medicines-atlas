"""Integrity and scope checks for the value-free M-107 PBS link crosswalk."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPORT = Path(
    "quality/qualifications/australian-pbs-m107-link-crosswalk-20261018.json"
)


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
        "does not establish URL-to-receipt lineage"
        in interpretation["known_object_match_boundary"]
    )
    assert "not evidence" in interpretation["unresolved_boundary"]
