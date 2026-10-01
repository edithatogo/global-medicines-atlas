"""Public-only estate registry-gap reconciliation tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any, cast
from urllib.request import Request

import pytest
from scripts import qualify_hf_public_registry_gap as audit


class _Response:
    def __init__(self, url: str, content: bytes) -> None:
        self.url = url
        self.content = content

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def geturl(self) -> str:
        return self.url

    def read(self, size: int = -1) -> bytes:
        return self.content[:size]


def _response_factory(url: str, content: bytes) -> Callable[..., object]:
    def open_response(
        _request: object, *, timeout: float
    ) -> AbstractContextManager[_Response]:
        del timeout
        return _Response(url, content)

    return open_response


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


def test_public_dataset_scan_is_complete_sorted_and_revision_pinned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    rows: list[dict[str, object]] = [
        {
            "id": "edithatogo/z-dataset",
            "private": False,
            "gated": False,
            "sha": "b" * audit.REVISION_LENGTH,
        },
        {
            "id": "edithatogo/a-dataset",
            "private": False,
            "gated": "auto",
            "sha": "a" * audit.REVISION_LENGTH,
        },
    ]

    def observe(url: str) -> list[dict[str, object]]:
        calls.append(url)
        return rows

    monkeypatch.setattr(audit, "_json", observe)

    result = audit._public_datasets()  # pyright: ignore[reportPrivateUsage]

    assert calls == [
        (
            f"{audit.API_BASE}/datasets?author={audit.OWNER}&limit=100"
            "&expand[]=sha&expand[]=private&expand[]=gated"
        )
    ]
    assert result == [
        {
            "repo_id": "edithatogo/a-dataset",
            "revision": "a" * audit.REVISION_LENGTH,
            "gated": "auto",
        },
        {
            "repo_id": "edithatogo/z-dataset",
            "revision": "b" * audit.REVISION_LENGTH,
            "gated": False,
        },
    ]


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ([{"id": "edithatogo/private", "private": True}], "non-public"),
        ([{"id": "other/dataset", "private": False}], "identity"),
        (
            [
                {
                    "id": "edithatogo/dataset",
                    "private": False,
                    "sha": "z" * 40,
                    "gated": False,
                }
            ],
            "revision",
        ),
        (
            [
                {
                    "id": "edithatogo/dataset",
                    "private": False,
                    "sha": "a" * 40,
                    "gated": "unknown",
                }
            ],
            "gating state",
        ),
        (
            [
                {
                    "id": "edithatogo/dataset",
                    "private": False,
                    "sha": "a" * 40,
                    "gated": False,
                },
                {
                    "id": "edithatogo/dataset",
                    "private": False,
                    "sha": "a" * 40,
                    "gated": False,
                },
            ],
            "duplicate",
        ),
        (
            [
                {
                    "id": f"edithatogo/dataset-{index:03d}",
                    "private": False,
                    "sha": f"{index:040x}",
                    "gated": False,
                }
                for index in range(audit.LISTING_LIMIT)
            ],
            "truncated",
        ),
    ],
)
def test_public_dataset_scan_rejects_incomplete_or_unsafe_rows(
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict[str, object]],
    message: str,
) -> None:
    monkeypatch.setattr(audit, "_json", lambda _url: rows)
    with pytest.raises(ValueError, match=message):
        audit._public_datasets()  # pyright: ignore[reportPrivateUsage]


def test_public_collection_scan_is_complete_sorted_and_preserves_notes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        {
            "slug": "edithatogo/z-collection",
            "title": "Z",
            "description": "Preserve this public description.",
            "private": False,
            "gating": False,
            "items": [
                {
                    "id": "edithatogo/dataset-z",
                    "type": "dataset",
                    "note": {"text": "Approved discovery note."},
                }
            ],
        },
        {
            "slug": "edithatogo/a-collection",
            "title": "A",
            "description": None,
            "private": False,
            "gating": False,
            "items": [
                {
                    "id": "edithatogo/dataset-a",
                    "type": "dataset",
                    "note": None,
                }
            ],
        },
    ]
    detail_rows = {
        "edithatogo/z-collection": {
            **rows[0],
            "items": [
                {
                    "id": "edithatogo/dataset-z",
                    "type": "dataset",
                    "note": {"text": "Approved discovery note."},
                },
                {
                    "id": "edithatogo/dataset-z2",
                    "type": "dataset",
                    "note": None,
                },
            ],
        },
        "edithatogo/a-collection": {
            **rows[1],
            "items": [
                {
                    "id": "edithatogo/dataset-a",
                    "type": "dataset",
                    "note": None,
                }
            ],
        },
    }

    def read_json(url: str) -> object:
        if url == f"{audit.API_BASE}/collections?owner={audit.OWNER}&limit=100":
            return rows
        slug = url.removeprefix(f"{audit.API_BASE}/collections/")
        return detail_rows[slug]

    monkeypatch.setattr(audit, "_json", read_json)

    result = audit._public_collections()  # pyright: ignore[reportPrivateUsage]

    assert result == [
        {
            "slug": "edithatogo/a-collection",
            "title": "A",
            "description": None,
            "gated": False,
            "members": [
                {
                    "item_type": "dataset",
                    "item_id": "edithatogo/dataset-a",
                    "note": None,
                }
            ],
        },
        {
            "slug": "edithatogo/z-collection",
            "title": "Z",
            "description": "Preserve this public description.",
            "gated": False,
            "members": [
                {
                    "item_type": "dataset",
                    "item_id": "edithatogo/dataset-z",
                    "note": "Approved discovery note.",
                },
                {
                    "item_type": "dataset",
                    "item_id": "edithatogo/dataset-z2",
                    "note": None,
                },
            ],
        },
    ]


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (
            {"slug": "edithatogo/private", "private": True, "items": []},
            "not public-only",
        ),
        (
            {"slug": "other/collection", "private": False, "items": []},
            "malformed",
        ),
        (
            {
                "slug": "edithatogo/collection?token=secret",
                "private": False,
                "items": [],
            },
            "malformed",
        ),
        (
            {
                "slug": "edithatogo/nested/collection",
                "private": False,
                "items": [],
            },
            "malformed",
        ),
        (
            {
                "slug": "edithatogo/collection",
                "private": False,
                "items": [
                    {"id": "edithatogo/data", "type": "model", "note": None}
                ],
            },
            "member fields",
        ),
    ],
)
def test_public_collection_scan_rejects_unsafe_or_malformed_rows(
    monkeypatch: pytest.MonkeyPatch,
    row: dict[str, object],
    message: str,
) -> None:
    monkeypatch.setattr(
        audit,
        "_json",
        lambda _url: [row] if "?owner=" in _url else row,
    )
    with pytest.raises(ValueError, match=message):
        audit._public_collections()  # pyright: ignore[reportPrivateUsage]


def test_public_collection_scan_rejects_duplicates_and_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate = {
        "slug": "edithatogo/collection",
        "private": False,
        "items": [],
    }
    monkeypatch.setattr(
        audit,
        "_json",
        lambda _url: [duplicate, duplicate] if "?owner=" in _url else duplicate,
    )
    with pytest.raises(ValueError, match="duplicate"):
        audit._public_collections()  # pyright: ignore[reportPrivateUsage]

    rows = [
        {
            "slug": f"edithatogo/collection-{index:03d}",
            "private": False,
            "items": [],
        }
        for index in range(audit.LISTING_LIMIT)
    ]
    monkeypatch.setattr(
        audit,
        "_json",
        lambda _url: rows if "?owner=" in _url else duplicate,
    )
    with pytest.raises(ValueError, match="truncated"):
        audit._public_collections()  # pyright: ignore[reportPrivateUsage]


def test_read_url_rejects_redirect_outside_official_https_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        audit,
        "urlopen",
        _response_factory("https://attacker.example/steal", b"metadata"),
    )
    with pytest.raises(ValueError, match="left the official host"):
        audit._read_url(f"{audit.API_BASE}/datasets")  # pyright: ignore[reportPrivateUsage]


def test_public_metadata_reads_send_no_authorization_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[object] = []

    def open_response(request: object, *, timeout: float) -> _Response:
        del timeout
        observed.append(request)
        return _Response(f"{audit.API_BASE}/datasets", b"[]")

    monkeypatch.setattr(audit, "urlopen", open_response)

    assert audit._read_url(f"{audit.API_BASE}/datasets") == b"[]"  # pyright: ignore[reportPrivateUsage]
    assert len(observed) == 1
    request = cast("Request", observed[0])
    assert request.get_header("Authorization") is None
    assert request.get_header("Cookie") is None


def test_read_url_rejects_response_over_the_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        audit,
        "urlopen",
        _response_factory(
            f"{audit.API_BASE}/datasets",
            b"x" * (audit.MAX_RESPONSE_BYTES + 1),
        ),
    )
    with pytest.raises(ValueError, match="exceeded bound"):
        audit._read_url(f"{audit.API_BASE}/datasets")  # pyright: ignore[reportPrivateUsage]
