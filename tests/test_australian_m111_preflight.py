"""M-111 current-head identity remains separate from product admission."""

from __future__ import annotations

import json
from pathlib import Path


def _json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_m111_candidate_head_reconciles_without_claiming_consumer_acceptance() -> (
    None
):
    report = _json(
        "quality/qualifications/platinum-public-consumer-preflight-20261017.json"
    )
    m108 = _json(
        "quality/qualifications/australian-m108-derived-products-20261017.json"
    )
    gold = _json(
        "quality/qualifications/australian-mbs-gold-real-silver-qualification-20261017.json"
    )
    latest = m108["latest_mbs_archive_append_readback"]
    head = report["archive_head_readback"]
    product = report["pinned_public_product"]

    assert product["current_archive_revision"] == latest["revision"]
    assert head["current_revision"] == latest["revision"]
    assert head["root_manifest_sha256"] == latest["root_manifest_sha256"]
    assert (
        head["root_manifest_object_count"]
        == latest["root_manifest_object_count"]
    )
    assert head["nested_product_manifest_sha256"] == product["manifest_sha256"]
    assert head["nested_product_manifest_object_count"] == 8
    assert head["nested_product_manifest_inclusive_file_count"] == 9
    object_readback = head["object_readback"]
    assert object_readback["object_count"] == 8
    assert object_readback["sha256_and_size_verified_count"] == 8
    assert object_readback["parquet_or_source_payload_bytes_read"] == 0
    assert {obj["path"] for obj in object_readback["objects"]} == {
        obj["path"] for obj in gold["verified_objects"]
    } | {
        "silver/mbs/v4/2025-07-v3/source-receipt.json",
        "silver/mbs/v4/2025-07-v3/qualification.json",
    }
    assert all(obj["identity_verified"] for obj in object_readback["objects"])
    assert all(
        surface["successful_public_query_performed"] is False
        for surface in report["consumer_surfaces"].values()
        if "successful_public_query_performed" in surface
    )
    assert report["pinned_public_product"]["candidate_only"] is True
    assert report["pinned_public_product"]["independently_admitted"] is False
    assert report["boundaries"]["product_admission_changed"] is False
    assert report["boundaries"]["consumer_query_performed"] is False
