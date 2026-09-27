"""Validate the exact approved CMS Part D Bronze qualification."""

from __future__ import annotations

import json
from collections import Counter
from hashlib import sha256
from pathlib import Path

SOURCE_IDS = frozenset({"us-cms-partd-formulary", "us-cms-partd-spending"})
RECORDS_SHA256 = (
    "0b363147a625d056b640a9806520abcfb773dec085d6d2c4b8a0878644008f19"
)
FAMILY_COUNTS = {"formulary": 30, "spending": 3}
PAYLOAD_COUNT = 33
PROJECTION_COUNT = 631
RIGHTS_RELATIVE = (
    "quality/qualifications/cms-partd-rights-preflight-20260821.json"
)
RAW_RELATIVE = (
    "quality/qualifications/cms-partd-public-huggingface-20260829.json"
)
RECORDS_RELATIVE = (
    "quality/qualifications/cms-partd-source-record-qualification-20260927.json"
)


def qualified_cms_sources(
    rights_path: Path,
    raw_path: Path,
    records_path: Path,
) -> set[str]:
    """Return both source IDs only while rights and receipts remain exact."""
    rights = json.loads(rights_path.read_text(encoding="utf-8"))
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    record_bytes = records_path.read_bytes()
    records = json.loads(record_bytes)
    checks = (
        frozenset(rights["source_ids"]) == SOURCE_IDS,
        rights["maintainer_decision"] == "approved_public_2026-08-27",
        all(
            rights[key]
            for key in (
                "acquisition_authorized",
                "internal_retention_authorized",
                "public_release_authorized",
                "external_publication_authorized",
            )
        ),
        raw["immutable_revision"] == records["raw_revision"],
        raw["payload_count"] == PAYLOAD_COUNT,
        raw["formulary_release_count"] == FAMILY_COUNTS["formulary"],
        raw["spending_resource_count"] == FAMILY_COUNTS["spending"],
        raw["anonymous_digest_match"] is True,
        raw["clean_room_recovered_payload_count"] == PAYLOAD_COUNT,
        sha256(record_bytes).hexdigest() == RECORDS_SHA256,
        records["schema_id"]
        == "global-medicines-atlas.cms-partd-source-record-qualification",
        records["payload_count"] == PAYLOAD_COUNT,
        records["source_record_projection_count"] == PROJECTION_COUNT,
        records["source_values_preserved_as_strings"] is True,
        records["cross_plan_year_schema_equivalence_claimed"] is False,
        records["runner_source_bytes_retained"] is False,
        len(records["shards"]) == PAYLOAD_COUNT,
        Counter(item["family"] for item in records["shards"]) == FAMILY_COUNTS,
    )
    if not all(checks):
        raise ValueError("CMS Part D rights or public qualification drifted")
    return set(SOURCE_IDS)
