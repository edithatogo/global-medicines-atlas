#!/usr/bin/env python3
"""Record an anonymous, metadata-only public Hub registry-gap observation."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from operator import itemgetter
from pathlib import Path
from typing import Any, cast
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, SchemaError, ValidationError

OWNER = "edithatogo"
REGISTRY = f"{OWNER}/dataset-estate-registry"
API_BASE = "https://huggingface.co/api"
RAW_BASE = "https://huggingface.co/datasets"
USER_AGENT = "global-medicines-atlas-public-registry-audit/1.0"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
LISTING_LIMIT = 100
REVISION_LENGTH = 40
DEFAULT_OUTPUT = Path(
    "quality/qualifications/hf-public-registry-gap-20261001.json"
)


def _read_url(url: str) -> bytes:
    """Read a bounded official public Hub response without credentials."""
    if not url.startswith((API_BASE + "/", RAW_BASE + "/")):
        raise ValueError("unexpected Hub endpoint")
    request = Request(url, headers={"User-Agent": USER_AGENT})  # ruff: ignore[suspicious-url-open-usage] -- allowlisted HTTPS host and path
    try:
        with urlopen(request, timeout=30) as response:  # ruff: ignore[suspicious-url-open-usage] -- allowlisted HTTPS host and path
            final_url = urlsplit(cast("str", response.geturl()))
            if (
                final_url.scheme != "https"
                or final_url.hostname != "huggingface.co"
            ):
                raise ValueError("public Hub request left the official host")
            content = response.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, URLError) as error:
        raise ValueError("public Hub metadata request failed") from error
    if len(content) > MAX_RESPONSE_BYTES:
        raise ValueError("public Hub metadata response exceeded bound")
    return content


def _json(url: str) -> Any:
    return json.loads(_read_url(url))


def _digest(value: object) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def _contains_remote_ref(value: object) -> bool:
    """Reject schema references that could trigger unbounded network access."""
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        return "$ref" in value or any(
            _contains_remote_ref(item) for item in mapping.values()
        )
    if isinstance(value, list):
        return any(
            _contains_remote_ref(item) for item in cast("list[object]", value)
        )
    return False


def _catalog_validators(
    schema: object,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build validators for both the catalog document and its entry items."""
    if not isinstance(schema, dict) or _contains_remote_ref(
        cast("dict[object, object]", schema)
    ):
        raise ValueError("pinned registry schema is malformed or referenced")
    schema_mapping = cast("dict[str, Any]", schema)
    properties = schema_mapping.get("properties")
    properties_mapping = (
        cast("dict[str, Any]", properties)
        if isinstance(properties, dict)
        else {}
    )
    datasets = properties_mapping.get("datasets")
    datasets_mapping = (
        cast("dict[str, Any]", datasets) if isinstance(datasets, dict) else {}
    )
    entry_schema = datasets_mapping.get("items")
    if not isinstance(entry_schema, dict):
        raise TypeError("pinned registry schema has no dataset item schema")
    try:
        Draft202012Validator.check_schema(schema_mapping)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        Draft202012Validator.check_schema(cast("dict[str, Any]", entry_schema))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    except SchemaError:
        raise ValueError("pinned registry schema is invalid") from None
    return (schema_mapping, cast("dict[str, Any]", entry_schema))


def _validate_schema(schema: dict[str, Any], value: object) -> None:
    """Validate JSON against a checked, local Draft 2020-12 schema."""
    Draft202012Validator(schema).validate(value)  # pyright: ignore[reportUnknownMemberType]


def _public_datasets() -> list[dict[str, Any]]:
    url = (
        f"{API_BASE}/datasets?author={OWNER}&limit=100"
        "&expand[]=sha&expand[]=private&expand[]=gated"
    )
    rows = _json(url)
    if not isinstance(rows, list):
        raise TypeError("public dataset listing must be an array")
    rows = cast("list[object]", rows)
    if len(rows) >= LISTING_LIMIT:
        raise ValueError("public dataset listing is malformed or truncated")
    result: list[dict[str, Any]] = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            raise TypeError("public dataset entry must be an object")
        row = cast("dict[str, Any]", raw_row)
        identity = row.get("id")
        revision = row.get("sha")
        if not isinstance(identity, str) or not identity.startswith(
            f"{OWNER}/"
        ):
            raise ValueError("public dataset identity is invalid")
        if row.get("private") is not False:
            raise ValueError(
                "anonymous dataset listing included non-public data"
            )
        if not isinstance(revision, str) or len(revision) != REVISION_LENGTH:
            raise ValueError("public dataset revision is invalid")
        if any(char not in "0123456789abcdef" for char in revision):
            raise ValueError("public dataset revision is invalid")
        gated = row.get("gated")
        if gated not in {False, True, "auto", "manual"}:
            raise ValueError("public dataset gating state is invalid")
        result.append({
            "repo_id": identity,
            "revision": revision,
            "gated": gated,
        })
    if len({row["repo_id"] for row in result}) != len(result):
        raise ValueError("duplicate public dataset identity")
    return sorted(result, key=itemgetter("repo_id"))


def _public_collections() -> list[dict[str, Any]]:
    rows = _json(f"{API_BASE}/collections?owner={OWNER}&limit=100")
    if not isinstance(rows, list):
        raise TypeError("public collection listing must be an array")
    rows = cast("list[object]", rows)
    if len(rows) >= LISTING_LIMIT:
        raise ValueError("public collection listing is malformed or truncated")
    result: list[dict[str, Any]] = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            raise TypeError("public collection entry must be an object")
        row = cast("dict[str, Any]", raw_row)
        if row.get("private") is not False:
            raise ValueError("anonymous collection listing is not public-only")
        slug = row.get("slug")
        items = row.get("items")
        items = (
            cast("list[object]", items) if isinstance(items, list) else items
        )
        if (
            not isinstance(slug, str)
            or not slug.startswith(f"{OWNER}/")
            or not isinstance(items, list)
        ):
            raise ValueError("public collection metadata is malformed")
        members: list[dict[str, Any]] = []
        for raw_item in cast("list[object]", items):
            if not isinstance(raw_item, dict):
                raise TypeError("public collection member must be an object")
            item = cast("dict[str, Any]", raw_item)
            item_id = item.get("id")
            item_type = item.get("type")
            note = item.get("note")
            note_mapping = (
                cast("dict[str, Any]", note) if isinstance(note, dict) else {}
            )
            note_text = note_mapping.get("text")
            if (
                item_type not in {"dataset", "collection"}
                or not isinstance(item_id, str)
                or not isinstance(note_text, str | None)
            ):
                raise ValueError("public collection member fields are invalid")
            members.append({
                "item_type": item_type,
                "item_id": item_id,
                "note": note_text,
            })
        result.append({
            "slug": slug,
            "title": row.get("title"),
            "description": row.get("description"),
            "gated": row.get("gating"),
            "members": members,
        })
    if len({row["slug"] for row in result}) != len(result):
        raise ValueError("duplicate public collection identity")
    return sorted(result, key=itemgetter("slug"))


def _registry_catalog(revision: str) -> tuple[bytes, bytes]:
    """Read the catalog and its schema from the exact public registry head."""
    rows = _public_datasets()
    registry_rows = [row for row in rows if row["repo_id"] == REGISTRY]
    if len(registry_rows) != 1 or registry_rows[0]["revision"] != revision:
        raise ValueError("registry head differs from the requested revision")
    if registry_rows[0]["gated"] is not False:
        raise ValueError("registry must be public and non-gated")
    base = f"{RAW_BASE}/{REGISTRY}/resolve/{revision}"
    return (
        _read_url(f"{base}/catalog.json"),
        _read_url(f"{base}/catalog.schema.json"),
    )


def observe_public_state() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Require stable, complete anonymous public dataset and collection scans."""
    first = (_public_datasets(), _public_collections())
    second = (_public_datasets(), _public_collections())
    if first != second:
        raise ValueError("anonymous public estate changed between scans")
    return first


def _public_access_mismatches(
    datasets: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]
) -> list[dict[str, str]]:
    """Return public dataset access states that disagree with the catalog."""
    result: list[dict[str, str]] = []
    for row in datasets:
        entry = by_id.get(row["repo_id"])
        if entry is None:
            continue
        live_access = "gated" if row["gated"] else "public"
        if entry["access"] != live_access:
            result.append({
                "repo_id": row["repo_id"],
                "registry_access": entry["access"],
                "observed_public_access": live_access,
            })
    return result


def _draft_public_entries(
    datasets: list[dict[str, Any]], missing_ids: set[str]
) -> list[dict[str, Any]]:
    """Prepare fail-closed entries without claiming origin, rights or role."""
    return [
        {
            "catalog_entry": {
                "repo_id": row["repo_id"],
                "family": "unclassified",
                "role": "unclassified_public_dataset",
                "canonical_repo_id": row["repo_id"],
                "origin_repository": None,
                "upstream_source": (
                    "Not assessed; an exact upstream source is not claimed."
                ),
                "status": "not_assessed",
                "access": "gated" if row["gated"] else "public",
                "rights_status": "source_specific_review_required",
                "viewer_status": "not_verified",
            },
            "observed_revision": row["revision"],
        }
        for row in datasets
        if row["repo_id"] in missing_ids
    ]


def build_gap_record(  # ruff: ignore[too-many-locals] - one append-only evidence record
    datasets: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    catalog_bytes: bytes,
    catalog_schema_bytes: bytes,
    *,
    observed_at: datetime,
    registry_revision: str,
) -> dict[str, Any]:
    """Compare the public-only live denominator with the pinned catalog."""
    catalog = json.loads(catalog_bytes)
    if not isinstance(catalog, dict):
        raise TypeError("estate registry catalog must be an object")
    catalog_mapping = cast("dict[str, Any]", catalog)
    catalog_schema = json.loads(catalog_schema_bytes)
    schemas = _catalog_validators(catalog_schema)
    try:
        _validate_schema(schemas[0], catalog_mapping)
    except ValidationError:
        raise ValueError(
            "pinned registry catalog/schema validation failed"
        ) from None
    entries = catalog_mapping.get("datasets")
    if not isinstance(entries, list):
        raise TypeError("estate registry catalog datasets must be an array")
    entries = cast("list[object]", entries)
    by_id: dict[str, dict[str, Any]] = {}
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            raise TypeError("estate registry entry must be an object")
        entry = cast("dict[str, Any]", raw_entry)
        repo_id = entry.get("repo_id")
        access = entry.get("access")
        if not isinstance(repo_id, str) or access not in {
            "public",
            "private",
            "gated",
        }:
            raise ValueError("estate registry identity or access is invalid")
        if repo_id in by_id:
            raise ValueError("duplicate estate registry identity")
        by_id[repo_id] = entry

    live_ids = {row["repo_id"] for row in datasets}
    # Private catalog identities are intentionally excluded from this output.
    missing_ids = sorted(live_ids - set(by_id))
    missing_id_set = set(missing_ids)
    unmatched_public_ids = {
        repo_id
        for repo_id, entry in by_id.items()
        if entry["access"] != "private" and repo_id not in live_ids
    }
    private_entry_count = sum(
        entry["access"] == "private" for entry in by_id.values()
    )
    access_counts = {
        access: sum(entry["access"] == access for entry in by_id.values())
        for access in ("public", "gated", "private")
    }
    access_mismatches = _public_access_mismatches(datasets, by_id)
    draft_entries = _draft_public_entries(datasets, missing_id_set)
    try:
        for draft in draft_entries:
            _validate_schema(schemas[1], draft["catalog_entry"])
    except ValidationError:
        raise ValueError("draft registry entry failed pinned schema") from None

    return {
        "schema_id": "global-medicines-atlas.hf-public-registry-gap",
        "schema_version": 1,
        "observed_at": observed_at.astimezone(UTC).isoformat(),
        "observation": {
            "endpoint": "https://huggingface.co/api",
            "anonymous": True,
            "stable_double_scan": True,
            "source_payload_bytes_read": False,
            "source_values_read": False,
            "public_dataset_count": len(datasets),
            "public_collection_count": len(collections),
            "public_dataset_metadata_sha256": _digest(datasets),
            "public_collection_metadata_sha256": _digest(collections),
        },
        "registry": {
            "dataset": REGISTRY,
            "revision": registry_revision,
            "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
            "catalog_schema_sha256": hashlib.sha256(
                catalog_schema_bytes
            ).hexdigest(),
            "entry_count": len(entries),
            "catalog_access_counts": access_counts,
            "private_entry_count_excluded_from_identity_comparison": (
                private_entry_count
            ),
            "matched_current_public_dataset_count": len(live_ids & set(by_id)),
            "public_access_mismatch_count": len(access_mismatches),
            "public_access_mismatches": access_mismatches,
            "missing_current_public_datasets": [
                {
                    **row,
                    "current_visibility": "public",
                    "rights_and_source_scope": "not_assessed",
                    "registry_metadata_proposal": "draft_unclassified_for_review",
                }
                for row in datasets
                if row["repo_id"] in missing_id_set
            ],
            "missing_current_public_dataset_count": len(missing_ids),
            "conservative_public_registry_draft_entries": draft_entries,
            "proposed_entry_count_if_missing_public_rows_are_added": (
                len(entries) + len(missing_ids)
            ),
            "access_corrections_prepared_for_review": access_mismatches,
            "unmatched_nonprivate_registry_entry_count": len(
                unmatched_public_ids
            ),
            "unmatched_nonprivate_registry_entries_pending_review": [
                {
                    "repo_id": repo_id,
                    "registry_access": by_id[repo_id]["access"],
                    "disposition": "preserve_pending_human_review",
                }
                for repo_id in sorted(unmatched_public_ids)
            ],
            "private_dataset_identities_emitted": False,
            "stale_or_private_entry_disposition": (
                "preserve pending owner-visible reconciliation; no removal "
                "proposed"
            ),
        },
        "public_collections": collections,
        "boundaries": [
            (
                "Public membership and repository visibility do not establish "
                "source rights or federation acceptance."
            ),
            (
                "This metadata comparison authorizes no catalog upload, "
                "collection mutation, visibility change, deletion, or release."
            ),
            (
                "Rights, origin, family, role, payload state, and Viewer "
                "status remain unassessed for missing registry rows."
            ),
        ],
    }


def main() -> int:
    """Write a bounded public-only registry-gap qualification record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-revision", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if len(args.registry_revision) != REVISION_LENGTH or any(
        char not in "0123456789abcdef" for char in args.registry_revision
    ):
        raise ValueError("registry revision must be immutable")
    datasets, collections = observe_public_state()
    catalog_bytes, catalog_schema_bytes = _registry_catalog(
        args.registry_revision
    )
    record = build_gap_record(
        datasets,
        collections,
        catalog_bytes,
        catalog_schema_bytes,
        observed_at=datetime.now(UTC),
        registry_revision=args.registry_revision,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps({
            "public_datasets": record["observation"]["public_dataset_count"],
            "public_collections": record["observation"][
                "public_collection_count"
            ],
            "missing_registry_entries": record["registry"][
                "missing_current_public_dataset_count"
            ],
            "private_identities_emitted": False,
        })
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
