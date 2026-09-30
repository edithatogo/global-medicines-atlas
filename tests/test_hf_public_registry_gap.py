"""Public-only estate registry-gap reconciliation tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from scripts import qualify_hf_public_registry_gap as audit


def _catalog_entry(repo_id: str, access: str) -> dict[str, object]:
    return {
        "repo_id": repo_id,
        "family": "test",
        "role": "source_archive",
        "canonical_repo_id": repo_id,
        "origin_repository": None,
        "upstream_source": "Test fixture only.",
        "status": "test_fixture",
        "access": access,
        "rights_status": "source_specific_review_required",
        "viewer_status": "not_verified",
    }


def _catalog_schema() -> dict[str, object]:
    entry_properties: dict[str, object] = {
        key: {"type": "string"}
        for key in (
            "repo_id",
            "family",
            "role",
            "canonical_repo_id",
            "status",
            "rights_status",
            "viewer_status",
        )
    }
    entry_properties["origin_repository"] = {"type": ["string", "null"]}
    entry_properties["upstream_source"] = {"type": "string"}
    entry_properties["access"] = {"enum": ["public", "private", "gated"]}
    entry_schema = {
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
        "properties": entry_properties,
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["datasets"],
        "properties": {"datasets": {"type": "array", "items": entry_schema}},
    }


def test_gap_record_excludes_private_registry_identities() -> None:
    datasets = [
        {"repo_id": "owner/known", "revision": "a" * 40, "gated": False},
        {"repo_id": "owner/missing", "revision": "b" * 40, "gated": False},
    ]
    collections: list[dict[str, Any]] = [
        {
            "slug": "owner/public-collection",
            "title": "Public Collection",
            "description": "Public metadata only.",
            "gated": False,
            "members": [],
        }
    ]
    catalog = {
        "datasets": [
            _catalog_entry("owner/known", "public"),
            _catalog_entry("owner/private-secret-name", "private"),
        ]
    }

    result = audit.build_gap_record(
        datasets,
        collections,
        json.dumps(catalog).encode(),
        json.dumps(_catalog_schema()).encode(),
        observed_at=datetime(2026, 10, 1, tzinfo=UTC),
        registry_revision="c" * 40,
    )

    encoded = json.dumps(result)
    assert "owner/private-secret-name" not in encoded
    assert (
        result["registry"][
            "private_entry_count_excluded_from_identity_comparison"
        ]
        == 1
    )
    assert result["registry"]["missing_current_public_dataset_count"] == 1
    assert result["registry"]["missing_current_public_datasets"] == [
        {
            "repo_id": "owner/missing",
            "revision": "b" * 40,
            "gated": False,
            "current_visibility": "public",
            "rights_and_source_scope": "not_assessed",
            "registry_metadata_proposal": "draft_unclassified_for_review",
        }
    ]
    draft = result["registry"]["conservative_public_registry_draft_entries"][0]
    draft_entry = draft["catalog_entry"]
    assert set(draft_entry) == {
        "repo_id",
        "family",
        "role",
        "canonical_repo_id",
        "origin_repository",
        "upstream_source",
        "status",
        "access",
        "rights_status",
        "viewer_status",
    }
    assert draft_entry["family"] == "unclassified"
    assert draft_entry["role"] == "unclassified_public_dataset"
    assert draft_entry["rights_status"] == "source_specific_review_required"
    assert draft_entry["origin_repository"] is None
    assert draft["observed_revision"] == "b" * 40


def test_public_access_mismatch_is_not_hidden_as_a_match() -> None:
    catalog = {"datasets": [_catalog_entry("owner/gated", "public")]}
    result = audit.build_gap_record(
        [{"repo_id": "owner/gated", "revision": "a" * 40, "gated": "manual"}],
        [],
        json.dumps(catalog).encode(),
        json.dumps(_catalog_schema()).encode(),
        observed_at=datetime(2026, 10, 1, tzinfo=UTC),
        registry_revision="c" * 40,
    )
    assert result["registry"]["missing_current_public_dataset_count"] == 0
    assert result["registry"]["public_access_mismatch_count"] == 1
    assert result["registry"]["public_access_mismatches"] == [
        {
            "repo_id": "owner/gated",
            "registry_access": "public",
            "observed_public_access": "gated",
        }
    ]


def test_anonymous_scans_must_match(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def datasets() -> list[dict[str, object]]:
        nonlocal calls
        calls += 1
        return [
            {"repo_id": "owner/data", "revision": str(calls), "gated": False}
        ]

    monkeypatch.setattr(audit, "_public_datasets", datasets)
    monkeypatch.setattr(audit, "_public_collections", list)
    with pytest.raises(ValueError, match="changed between scans"):
        audit.observe_public_state()


def test_registry_file_is_bound_to_current_public_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision = "a" * audit.REVISION_LENGTH
    monkeypatch.setattr(
        audit,
        "_public_datasets",
        lambda: [
            {"repo_id": audit.REGISTRY, "revision": revision, "gated": False}
        ],
    )
    monkeypatch.setattr(
        audit,
        "_read_url",
        cast("Callable[[str], bytes]", lambda url: url.encode()),  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
    )

    catalog, schema = audit._registry_catalog(revision)  # pyright: ignore[reportPrivateUsage]
    assert catalog.endswith(f"resolve/{revision}/catalog.json".encode())
    assert schema.endswith(f"resolve/{revision}/catalog.schema.json".encode())
    with pytest.raises(ValueError, match="differs"):
        audit._registry_catalog("b" * audit.REVISION_LENGTH)  # pyright: ignore[reportPrivateUsage]
