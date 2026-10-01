"""Fail-closed tests for the approved metadata-only Hub transaction."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

import pytest
from scripts import publish_hf_public_metadata as publisher
from scripts import qualify_hf_public_registry_gap as audit


def _entry(repo_id: str, access: str) -> dict[str, Any]:
    return {
        "repo_id": repo_id,
        "family": "fixture",
        "role": "fixture",
        "canonical_repo_id": repo_id,
        "origin_repository": None,
        "upstream_source": "Fixture only.",
        "status": "fixture",
        "access": access,
        "rights_status": "source_specific_review_required",
        "viewer_status": "not_verified",
    }


def _schema() -> dict[str, Any]:
    item = {
        "type": "object",
        "required": [
            "repo_id",
            "family",
            "role",
            "canonical_repo_id",
            "status",
            "access",
            "rights_status",
            "viewer_status",
        ],
        "properties": {
            "repo_id": {"type": "string"},
            "family": {"type": "string"},
            "role": {"type": "string"},
            "canonical_repo_id": {"type": "string"},
            "origin_repository": {"type": ["string", "null"]},
            "upstream_source": {"type": "string"},
            "status": {"type": "string"},
            "access": {"enum": ["public", "private", "gated"]},
            "rights_status": {"type": "string"},
            "viewer_status": {"type": "string"},
        },
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["datasets"],
        "properties": {"datasets": {"type": "array", "items": item}},
    }


def _case() -> tuple[bytes, bytes, dict[str, Any], dict[str, Any]]:
    gated_id = "owner/public-but-catalog-gated"
    private_id = "owner/public-but-catalog-private"
    unmatched_id = "edithatogo/gfjd-source-archive"
    private_existing_id = "owner/preexisting-private-row"
    baseline = {
        "datasets": [
            _entry(gated_id, "gated"),
            _entry(private_id, "private"),
            _entry(unmatched_id, "public"),
            _entry(private_existing_id, "private"),
        ]
    }
    baseline_bytes = (json.dumps(baseline, indent=2) + "\n").encode()
    schema_bytes = json.dumps(_schema()).encode()
    datasets = [
        {"repo_id": gated_id, "revision": "a" * 40, "gated": False},
        {"repo_id": private_id, "revision": "b" * 40, "gated": False},
        *[
            {
                "repo_id": f"owner/missing-{index:02d}",
                "revision": f"{index:040x}",
                "gated": False,
            }
            for index in range(26)
        ],
    ]
    collections: list[dict[str, Any]] = [
        {
            "slug": "owner/existing-public",
            "title": "Existing",
            "description": "Preserve.",
            "gated": False,
            "members": [],
        }
    ]
    record = audit.build_gap_record(
        datasets,
        collections,
        baseline_bytes,
        schema_bytes,
        observed_at=datetime(2026, 10, 1, tzinfo=UTC),
        registry_revision="c" * 40,
    )
    record["registry"]["revision"] = "c" * 40
    record["observation"]["public_dataset_metadata_sha256"] = "d" * 64
    record["observation"]["public_collection_metadata_sha256"] = "e" * 64
    approval = {
        "registry": {
            "baseline_revision": "c" * 40,
            "baseline_catalog_sha256": hashlib.sha256(
                baseline_bytes
            ).hexdigest(),
            "expected_public_dataset_metadata_sha256": "d" * 64,
            "expected_public_collection_metadata_sha256": "e" * 64,
            "access_mismatch_reconciliation": [
                {"repo_id": gated_id, "from": "gated", "to": "public"},
                {"repo_id": private_id, "from": "private", "to": "public"},
            ],
            "unmatched_existing_entries_to_preserve": [unmatched_id],
        }
    }
    return baseline_bytes, schema_bytes, record, approval


def test_target_catalog_adds_only_unknown_public_placeholders_and_access_fixes() -> (
    None
):
    baseline, schema, gap, approval = _case()
    target = json.loads(
        publisher.prepare_target_catalog(baseline, schema, gap, approval)
    )
    rows = {row["repo_id"]: row for row in target["datasets"]}

    assert len(rows) == 30
    assert rows["owner/public-but-catalog-gated"]["access"] == "public"
    assert rows["owner/public-but-catalog-private"]["access"] == "public"
    assert rows["edithatogo/gfjd-source-archive"] == _entry(
        "edithatogo/gfjd-source-archive", "public"
    )
    assert rows["owner/preexisting-private-row"]["access"] == "private"
    for index in range(26):
        entry = rows[f"owner/missing-{index:02d}"]
        assert entry["family"] == "unclassified"
        assert entry["origin_repository"] is None
        assert entry["rights_status"] == "source_specific_review_required"
        assert entry["viewer_status"] == "not_verified"
        assert entry["status"] == "not_assessed"


def test_target_catalog_rejects_stale_public_observation() -> None:
    baseline, schema, gap, approval = _case()
    gap["observation"]["public_dataset_metadata_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="public estate"):
        publisher.prepare_target_catalog(baseline, schema, gap, approval)


def test_target_catalog_rejects_access_change_outside_pinned_scope() -> None:
    baseline, schema, gap, approval = _case()
    gap["registry"]["public_access_mismatches"][0]["registry_access"] = "public"
    with pytest.raises(ValueError, match="access mismatches"):
        publisher.prepare_target_catalog(baseline, schema, gap, approval)


def test_target_catalog_rejects_rights_or_role_claims_in_placeholders() -> None:
    baseline, schema, gap, approval = _case()
    gap["registry"]["conservative_public_registry_draft_entries"][0][
        "catalog_entry"
    ]["rights_status"] = "open"
    with pytest.raises(ValueError, match="unsupported source"):
        publisher.prepare_target_catalog(baseline, schema, gap, approval)


def test_local_publication_fails_closed_before_accessing_hub() -> None:
    with pytest.raises(ValueError, match="only from GitHub Actions"):
        publisher.validate_actions_context({
            "GITHUB_ACTIONS": "false",
            "GITHUB_REF": "refs/heads/main",
            "GMA_MAINTAINER_PUBLICATION_APPROVED": "yes-i-approve-publication",
            "HF_TOKEN": "test-only-placeholder",
        })


def test_non_main_or_unapproved_actions_run_fails_closed() -> None:
    base = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REF": "refs/heads/feature",
        "GMA_MAINTAINER_PUBLICATION_APPROVED": "yes-i-approve-publication",
        "HF_TOKEN": "test-only-placeholder",
    }
    with pytest.raises(ValueError, match="protected main"):
        publisher.validate_actions_context(base)
    base["GITHUB_REF"] = "refs/heads/main"
    base["GMA_MAINTAINER_PUBLICATION_APPROVED"] = "no"
    with pytest.raises(ValueError, match="approval"):
        publisher.validate_actions_context(base)
