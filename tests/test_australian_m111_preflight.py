"""M-111 current-head identity remains separate from product admission."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _json(path: str) -> dict[str, Any]:
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
    expected_tables = {
        obj["path"]: (obj["sha256"], obj["byte_count"])
        for obj in gold["verified_objects"]
    }
    observed_objects = {obj["path"]: obj for obj in object_readback["objects"]}
    assert {
        path: (
            observed_objects[path]["sha256"],
            observed_objects[path]["byte_count"],
        )
        for path in expected_tables
    } == expected_tables
    assert set(observed_objects) == set(expected_tables) | {
        "silver/mbs/v4/2025-07-v3/source-receipt.json",
        "silver/mbs/v4/2025-07-v3/qualification.json",
    }
    assert all(
        obj["identity_verified"] and obj["status"] == "resolved_200"
        for obj in object_readback["objects"]
    )
    assert all(
        surface["successful_public_query_performed"] is False
        for surface in report["consumer_surfaces"].values()
        if "successful_public_query_performed" in surface
    )
    assert report["pinned_public_product"]["candidate_only"] is True
    assert report["pinned_public_product"]["independently_admitted"] is False
    assert report["boundaries"]["product_admission_changed"] is False
    assert report["boundaries"]["consumer_query_performed"] is False


def test_m111_current_archive_head_refresh_preserves_candidate_only_boundary() -> (
    None
):
    report = _json(
        "quality/qualifications/platinum-public-consumer-preflight-20261018.json"
    )
    prior = _json(
        "quality/qualifications/platinum-public-consumer-preflight-20261017.json"
    )
    m112 = _json(
        "quality/qualifications/australian-mbs-july-metadata-hosted-readback-20261018.json"
    )
    product = report["pinned_public_product"]
    head = report["archive_head_readback"]
    prior_product = prior["pinned_public_product"]
    prior_head = prior["archive_head_readback"]
    root = m112["manifest_readback"]

    assert report["requirement"] == "M-111"
    assert product["dataset"] == m112["dataset"] == head["dataset"]
    assert product["current_archive_revision"] == m112["revision"]
    assert head["current_revision"] == m112["revision"]
    assert head["head_api_observation"]["private"] is False
    assert head["head_api_observation"]["gated"] is False
    assert head["head_api_observation"]["last_modified"] == (
        "2026-10-17T22:05:24.000Z"
    )
    assert head["root_manifest_path"] == "manifest.json"
    assert head["root_manifest_sha256"] == root["sha256"]
    assert head["root_manifest_object_count"] == root["file_count"] == 228
    assert head["root_manifest_bytes"] == 64792
    assert (
        product["publication_revision"] == prior_product["publication_revision"]
    )
    assert product["prefix"] == prior_product["prefix"]
    assert product["manifest_sha256"] == prior_product["manifest_sha256"]
    assert (
        head["nested_product_manifest_path"]
        == prior_head["nested_product_manifest_path"]
    )
    assert (
        head["nested_product_manifest_sha256"]
        == prior_head["nested_product_manifest_sha256"]
    )
    assert head["nested_product_manifest_bytes"] == 3827
    assert head["nested_product_manifest_object_count"] == 8
    assert head["nested_product_manifest_inclusive_file_count"] == 9

    readback = head["object_readback"]
    assert readback["object_count"] == 8
    assert readback["sha256_and_size_verified_count"] == 8
    assert readback["parquet_or_source_payload_bytes_read"] == 0
    assert readback["small_metadata_sidecar_bytes_read"] == 4181
    parquet = [
        row for row in readback["objects"] if row["path"].endswith(".parquet")
    ]
    sidecars = [
        row for row in readback["objects"] if row["path"].endswith(".json")
    ]
    assert len(parquet) == 6
    assert len(sidecars) == 2
    assert all(
        row["readback_method"] == "huggingface_tree_lfs_oid_and_head_size"
        for row in parquet
    )
    assert all(
        row["readback_method"] == "metadata_body_sha256_and_head_size"
        for row in sidecars
    )
    assert all(
        row["identity_verified"] and row["status"] == "resolved_200"
        for row in readback["objects"]
    )
    expected_tables = {
        row["path"]: (row["sha256"], row["bytes"]) for row in product["tables"]
    }
    observed_parquet = {
        row["path"]: (row["sha256"], row["byte_count"]) for row in parquet
    }
    assert observed_parquet == expected_tables

    assert product["candidate_only"] is True
    assert product["independently_admitted"] is False
    assert report["boundaries"]["product_admission_changed"] is False
    assert report["boundaries"]["consumer_query_performed"] is False
    assert (
        report["consumer_surfaces"]["export"]["anonymous_restore_performed"]
        is False
    )
