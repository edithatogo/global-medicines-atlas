#!/usr/bin/env python3
"""Publish the approved Australian discovery metadata update through Actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from operator import itemgetter
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, SchemaError, ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ruff: file-ignore[module-import-not-at-top-of-file] -- make the repository package importable for direct Actions execution
from scripts.qualify_hf_public_registry_gap import (
    build_gap_record,
    observe_public_state,
)

APPROVAL_PATH = Path(
    "quality/qualifications/"
    "hf-public-metadata-publication-approval-20261001.json"
)
REGISTRY = "edithatogo/dataset-estate-registry"
POLICY_DESCRIPTION = (
    "Australian MBS and PBS source and derived evidence. Collection membership "
    "is for discovery and does not grant source rights, authorize publication, "
    "or establish federation acceptance. Source scope, rights, and "
    "qualification remain recorded per dataset and object."
)
HEOR_EXISTING_NOTES = {
    "edithatogo/reimbursement-atlas": (
        "Metadata-only reimbursement atlas; origin remains unresolved in the "
        "registry."
    ),
    "edithatogo/australian-mbs-source-archive": None,
    "edithatogo/australian-pbs-source-archive": None,
}
HEOR_NZ_NOTE = (
    "Checksum-pinned NZ health appropriations medallion dataset; manifest "
    "SHA-256 9a33babda857b0aa7c60a6012000cf1e730fed729781cb8ceb6e7a4714cae40e; "
    "revision 9b85bac06597d4435fd078f6bed0f30bb008542b."
)
POLICY_OLD_DESCRIPTION = (
    "Reserved for future Australian policy datasets; kept private while empty."
)
EXPECTED_PUBLIC_GAP_COUNT = 26
EXPECTED_AUSTRALIAN_MEMBER_COUNT = 5


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _metadata_digest(value: object) -> str:
    canonical = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return _sha256(canonical)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_validators(schema_value: object) -> tuple[Any, Any]:
    if not isinstance(schema_value, dict):
        raise TypeError("registry schema is not an object")
    schema = cast("dict[str, Any]", schema_value)
    properties_value = schema.get("properties")
    if not isinstance(properties_value, dict):
        raise TypeError("registry schema properties are missing")
    properties = cast("dict[str, Any]", properties_value)
    datasets_value = properties.get("datasets")
    if not isinstance(datasets_value, dict):
        raise TypeError("registry datasets schema is missing")
    datasets = cast("dict[str, Any]", datasets_value)
    entry_schema = datasets.get("items")
    if not isinstance(entry_schema, dict):
        raise TypeError("registry entry schema is missing")
    entry_schema_mapping = cast("dict[str, Any]", entry_schema)
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator.check_schema(entry_schema_mapping)
    except SchemaError:
        raise ValueError("pinned registry schema is invalid") from None
    return Draft202012Validator(schema), Draft202012Validator(
        entry_schema_mapping
    )


def _validate_schema(schema: Any, value: object) -> None:
    schema.validate(value)


def _require(condition: bool, message: str) -> None:  # ruff: ignore[boolean-type-hint-positional-argument] -- internal assertion
    if not condition:
        raise ValueError(message)


def prepare_target_catalog(  # ruff: ignore[too-many-locals, too-many-statements] -- bounded catalog transformation
    baseline_catalog_bytes: bytes,
    schema_bytes: bytes,
    gap_record: dict[str, Any],
    approval: dict[str, Any],
) -> bytes:
    """Build a deterministic catalog from the exact approved public-only gap."""
    registry_cfg = cast("dict[str, Any]", approval["registry"])
    observation = cast("dict[str, Any]", gap_record["observation"])
    gap_registry = cast("dict[str, Any]", gap_record["registry"])
    _require(
        _sha256(baseline_catalog_bytes)
        == registry_cfg["baseline_catalog_sha256"]
        == gap_registry["catalog_sha256"],
        "registry baseline catalog digest changed",
    )
    _require(
        gap_registry["revision"] == registry_cfg["baseline_revision"],
        "gap qualification does not use the approved registry revision",
    )
    _require(
        observation["anonymous"] is True
        and observation["stable_double_scan"] is True
        and observation["source_payload_bytes_read"] is False
        and observation["source_values_read"] is False,
        "gap qualification exceeds the approved metadata-only boundary",
    )
    _require(
        observation["public_dataset_metadata_sha256"]
        == registry_cfg["expected_public_dataset_metadata_sha256"]
        and observation["public_collection_metadata_sha256"]
        == registry_cfg["expected_public_collection_metadata_sha256"],
        "public estate no longer matches the approved observation",
    )
    _require(
        gap_registry["private_dataset_identities_emitted"] is False,
        "private identities must not enter this publication",
    )

    schema = json.loads(schema_bytes)
    baseline = json.loads(baseline_catalog_bytes)
    _require(isinstance(schema, dict), "registry schema is not an object")
    _require(isinstance(baseline, dict), "registry catalog is not an object")
    validators = _schema_validators(schema)
    _validate_schema(validators[0], baseline)
    entries_raw = baseline.get("datasets")
    _require(isinstance(entries_raw, list), "registry datasets is not an array")
    entries = cast("list[dict[str, Any]]", entries_raw)
    by_id = {entry.get("repo_id"): entry for entry in entries}
    _require(
        len(by_id) == len(entries), "registry contains duplicate identities"
    )

    expected_mismatches = {
        row["repo_id"]: (row["from"], row["to"])
        for row in cast(
            "list[dict[str, str]]",
            registry_cfg["access_mismatch_reconciliation"],
        )
    }
    observed_mismatches = {
        row["repo_id"]: (
            row["registry_access"],
            row["observed_public_access"],
        )
        for row in cast(
            "list[dict[str, str]]",
            gap_registry["public_access_mismatches"],
        )
    }
    _require(
        observed_mismatches == expected_mismatches,
        "public access mismatches differ from approved corrections",
    )
    for repo_id, (old_access, new_access) in expected_mismatches.items():
        _require(repo_id in by_id, "access correction identity is missing")
        _require(
            by_id[repo_id].get("access") == old_access
            and new_access == "public",
            "access correction no longer matches its approved baseline",
        )
        by_id[repo_id]["access"] = new_access

    drafts = cast(
        "list[dict[str, Any]]",
        gap_registry["conservative_public_registry_draft_entries"],
    )
    missing = cast(
        "list[dict[str, Any]]",
        gap_registry["missing_current_public_datasets"],
    )
    _require(
        len(drafts) == EXPECTED_PUBLIC_GAP_COUNT
        and len(missing) == EXPECTED_PUBLIC_GAP_COUNT,
        "public coverage denominator changed",
    )
    missing_by_id = {row["repo_id"]: row for row in missing}
    _require(len(missing_by_id) == len(missing), "missing dataset IDs repeat")
    for draft in drafts:
        entry = cast("dict[str, Any]", draft["catalog_entry"])
        repo_id = entry.get("repo_id")
        _require(isinstance(repo_id, str), "draft has no repository identity")
        _require(repo_id not in by_id, "draft would overwrite an existing row")
        live_row = missing_by_id.get(repo_id)
        if live_row is None:
            raise ValueError("draft is outside the observed gap")
        _require(
            draft.get("observed_revision") == live_row.get("revision")
            and live_row.get("current_visibility") == "public"
            and live_row.get("rights_and_source_scope") == "not_assessed",
            "draft identity or fail-closed state differs from the live gap",
        )
        _require(
            entry.get("family") == "unclassified"
            and entry.get("role") == "unclassified_public_dataset"
            and entry.get("origin_repository") is None
            and entry.get("status") == "not_assessed"
            and entry.get("rights_status") == "source_specific_review_required"
            and entry.get("viewer_status") == "not_verified",
            "draft contains an unsupported source, role, rights, or viewer claim",
        )
        _validate_schema(validators[1], entry)
        by_id[repo_id] = entry

    preserved_ids = cast(
        "list[str]", registry_cfg["unmatched_existing_entries_to_preserve"]
    )
    for repo_id in preserved_ids:
        _require(repo_id in by_id, "unmatched registry row was removed")
        original = next(
            (row for row in entries_raw if row.get("repo_id") == repo_id), None
        )
        _require(
            original == by_id[repo_id], "unmatched registry row was modified"
        )

    baseline["datasets"] = sorted(
        by_id.values(), key=lambda entry: cast("str", entry["repo_id"])
    )
    try:
        _validate_schema(validators[0], baseline)
    except ValidationError:
        raise ValueError(
            "target registry catalog failed pinned schema"
        ) from None
    return (json.dumps(baseline, indent=2, ensure_ascii=False) + "\n").encode()


def _collection_items(collection: Any) -> dict[str, dict[str, Any]]:
    """Normalize collection item objects without logging owner metadata."""
    items: dict[str, dict[str, Any]] = {}
    for item in collection.items:
        repo_id = cast("str", item.item_id)
        _require(repo_id not in items, "collection contains duplicate items")
        items[repo_id] = {
            "object_id": item.item_object_id,
            "type": item.item_type,
            "note": item.note,
        }
    return items


@dataclass(frozen=True, slots=True)
class PreparedPublication:
    registry_cfg: dict[str, Any]
    scope: dict[str, Any]
    gap_record: dict[str, Any]
    baseline_catalog: bytes
    registry_schema: bytes
    target_catalog: bytes
    target_catalog_sha: str
    scope_path: Path
    gap_path: Path


def _prepare_publication(
    approval: dict[str, Any], download: Any
) -> PreparedPublication:
    registry_cfg = cast("dict[str, Any]", approval["registry"])
    scope = cast("dict[str, Any]", approval["candidate_scope"])
    scope_path = ROOT / cast("str", scope["scope_assessment_path"])
    _require(
        _sha256(scope_path.read_bytes()) == scope["scope_assessment_sha256"],
        "approved Australian scope assessment changed",
    )
    scope_document = cast("dict[str, Any]", _load_json(scope_path))
    source_proposal = cast(
        "dict[str, Any]", scope_document["policy_aus_change_proposal"]
    )
    _require(
        source_proposal["collection_slug"] == scope["policy_aus_slug"]
        and source_proposal["proposed_collection_note"]
        == scope["policy_aus_collection_note"]
        and source_proposal["proposed_dataset_members"] == scope["members"]
        and scope_document["collections"][
            "health_economics_and_outcomes_research"
        ]["slug"]
        == scope["heor_slug"],
        "approved collection target differs from its pinned scope assessment",
    )

    baseline_revision = cast("str", registry_cfg["baseline_revision"])
    baseline_path = download(
        repo_id=REGISTRY,
        filename=cast("str", registry_cfg["catalog_path"]),
        repo_type="dataset",
        revision=baseline_revision,
        token=False,
    )
    schema_path = download(
        repo_id=REGISTRY,
        filename=cast("str", registry_cfg["schema_path"]),
        repo_type="dataset",
        revision=baseline_revision,
        token=False,
    )
    baseline_catalog = Path(baseline_path).read_bytes()
    schema_bytes = Path(schema_path).read_bytes()
    _require(
        _sha256(schema_bytes) == registry_cfg["schema_sha256"],
        "pinned public registry schema changed",
    )
    gap_path = ROOT / cast("str", registry_cfg["gap_qualification_path"])
    _require(
        _sha256(gap_path.read_bytes())
        == registry_cfg["gap_qualification_sha256"],
        "approved public gap qualification changed",
    )
    gap_record = cast("dict[str, Any]", _load_json(gap_path))
    target_catalog = prepare_target_catalog(
        baseline_catalog, schema_bytes, gap_record, approval
    )
    target_catalog_sha = _sha256(target_catalog)
    _require(
        target_catalog_sha == registry_cfg["target_catalog_sha256"],
        "generated catalog differs from the approved target digest",
    )
    return PreparedPublication(
        registry_cfg=registry_cfg,
        scope=scope,
        gap_record=gap_record,
        baseline_catalog=baseline_catalog,
        registry_schema=schema_bytes,
        target_catalog=target_catalog,
        target_catalog_sha=target_catalog_sha,
        scope_path=scope_path,
        gap_path=gap_path,
    )


def _validate_current_public_estate(
    prepared: PreparedPublication, approval: dict[str, Any]
) -> None:
    datasets, collections = observe_public_state()
    baseline_info = cast("dict[str, Any]", prepared.gap_record["observation"])
    public_dataset_map = _validate_candidate_heads(datasets, approval)
    fresh = build_gap_record(
        datasets,
        collections,
        prepared.baseline_catalog,
        prepared.registry_schema,
        observed_at=datetime.now(UTC),
        registry_revision=cast(
            "str", prepared.registry_cfg["baseline_revision"]
        ),
    )
    fresh_observation = cast("dict[str, Any]", fresh["observation"])
    _require(
        fresh_observation["public_dataset_count"]
        in {
            baseline_info["public_dataset_count"],
            baseline_info["public_dataset_count"] + 1,
        }
        and fresh_observation["public_collection_count"]
        in {
            baseline_info["public_collection_count"],
            baseline_info["public_collection_count"] + 1,
        },
        "public estate counts changed outside the approved update",
    )
    validate_normalized_public_state(
        datasets, collections, prepared.gap_record, approval
    )
    _require(
        len(public_dataset_map) == fresh_observation["public_dataset_count"],
        "public dataset inventory is incomplete",
    )


def _validate_candidate_heads(
    datasets: list[dict[str, Any]], approval: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    by_id = {row["repo_id"]: row for row in datasets}
    scope = cast("dict[str, Any]", approval["candidate_scope"])
    members = cast("list[dict[str, str]]", scope["members"])
    _require(
        len(members) == EXPECTED_AUSTRALIAN_MEMBER_COUNT,
        "approved Australian collection scope changed",
    )
    for member in members:
        live = by_id.get(member["dataset"])
        if live is None:
            raise ValueError("candidate dataset is not public")
        _require(
            live["revision"] == member["revision"] and live["gated"] is False,
            "candidate dataset revision or access changed",
        )
    return by_id


def _reconcile_collection(
    token: str,
    *,
    slug: str,
    desired_notes: dict[str, str],
    expected_members: set[str],
    baseline_notes: dict[str, str | None],
    desired_description: str | None = None,
    previous_description: str | None = None,
) -> Any:
    from huggingface_hub import (  # ruff: ignore[import-outside-top-level] -- optional publisher SDK; ty: ignore[unresolved-import]
        add_collection_item,
        get_collection,
        update_collection_item,
        update_collection_metadata,
    )

    collection = get_collection(slug, token=token)
    actual = _collection_items(collection)
    allowed = expected_members | set(desired_notes)
    _require(
        set(actual).issubset(allowed),
        "collection contains an out-of-scope item; preserving it and stopping",
    )
    for repo_id, item in actual.items():
        _require(item["type"] == "dataset", "collection has a non-dataset item")
        if repo_id in desired_notes and item["note"] != desired_notes[repo_id]:
            _require(
                item["note"] == baseline_notes.get(repo_id),
                "collection note differs from both approved baseline and target",
            )
    if slug.endswith(
        "health-economics-and-outcomes-research-6a2e9986698340a8c8f4e4b4"
    ):
        _require(
            expected_members.issubset(actual),
            "HEOR required members changed; refusing to recreate them",
        )
        _require(
            set(actual) - set(desired_notes)
            == expected_members - set(desired_notes),
            "HEOR out-of-scope membership changed",
        )
        nz = actual.get("edithatogo/nz-health-appropriations")
        _require(
            nz is not None and nz["note"] == HEOR_NZ_NOTE,
            "New Zealand member or its note changed; preserving and stopping",
        )
    for repo_id, note in desired_notes.items():
        item = actual.get(repo_id)
        if item is None:
            add_collection_item(
                collection_slug=slug,
                item_id=repo_id,
                item_type="dataset",
                note=note,
                exists_ok=False,
                token=token,
            )
        elif item["note"] != note:
            update_collection_item(
                collection_slug=slug,
                item_object_id=item["object_id"],
                note=note,
                token=token,
            )
    if desired_description is not None:
        current_description = collection.description
        _require(
            current_description in {previous_description, desired_description},
            "Policy AUS description changed outside the approved transition",
        )
        update_collection_metadata(
            collection_slug=slug,
            description=desired_description,
            private=collection.private,
            token=token,
        )
    return get_collection(slug, token=token)


def _verify_collection(
    collection: Any,
    *,
    slug: str,
    private: bool,
    description: str | None,
    expected_notes: dict[str, str],
    preserved_notes: dict[str, str] | None = None,
) -> None:
    _require(collection.slug == slug, "collection slug readback differs")
    _require(
        collection.private is private, "collection visibility readback differs"
    )
    if description is not None:
        _require(
            collection.description == description,
            "collection description readback differs",
        )
    items = _collection_items(collection)
    expected = {**expected_notes, **(preserved_notes or {})}
    _require(
        set(items) == set(expected), "collection membership readback differs"
    )
    for repo_id, note in expected.items():
        _require(
            items[repo_id]["type"] == "dataset",
            "collection contains a non-dataset item",
        )
        _require(
            items[repo_id]["note"] == note, "collection note readback differs"
        )


def validate_actions_context(env: dict[str, str]) -> None:
    """Fail closed on all local or non-main upload attempts."""
    _require(
        env.get("GITHUB_ACTIONS") == "true",
        "publication is permitted only from GitHub Actions",
    )
    _require(
        env.get("GITHUB_REF") == "refs/heads/main",
        "publication requires the protected main branch",
    )
    _require(
        env.get("GMA_MAINTAINER_PUBLICATION_APPROVED")
        == "yes-i-approve-publication",
        "explicit publication dispatch approval is required",
    )
    _require(bool(env.get("HF_TOKEN")), "required Hub token is unavailable")


def validate_normalized_public_state(
    datasets: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    baseline_gap: dict[str, Any],
    approval: dict[str, Any],
) -> None:
    """Allow only this exact publication's changes over the pinned public state."""
    registry_cfg = cast("dict[str, Any]", approval["registry"])
    scope = cast("dict[str, Any]", approval["candidate_scope"])
    normalized_datasets = [dict(row) for row in datasets]
    registry_rows = [
        row for row in normalized_datasets if row["repo_id"] == REGISTRY
    ]
    _require(len(registry_rows) == 1, "public registry identity is ambiguous")
    registry_rows[0]["revision"] = registry_cfg["baseline_revision"]
    baseline_observation = cast("dict[str, Any]", baseline_gap["observation"])
    _require(
        _metadata_digest(normalized_datasets)
        == baseline_observation["public_dataset_metadata_sha256"],
        "public dataset estate changed outside the approved registry write",
    )

    baseline_rows = cast(
        "list[dict[str, Any]]", baseline_gap["public_collections"]
    )
    baseline_by_slug = {row["slug"]: row for row in baseline_rows}
    current_by_slug = {row["slug"]: row for row in collections}
    _require(
        len(current_by_slug) == len(collections),
        "public collection listing contains duplicate identities",
    )
    policy_slug = cast("str", scope["policy_aus_slug"])
    allowed_slugs = set(baseline_by_slug) | {policy_slug}
    _require(
        set(current_by_slug).issubset(allowed_slugs)
        and set(baseline_by_slug).issubset(
            set(current_by_slug) | {policy_slug}
        ),
        "public collection set changed outside the approved update",
    )
    normalized_collections: list[dict[str, Any]] = []
    heor_slug = cast("str", scope["heor_slug"])
    for slug, row in current_by_slug.items():
        if slug == policy_slug:
            continue
        if slug == heor_slug:
            _require(slug in baseline_by_slug, "HEOR baseline is missing")
            normalized_collections.append(baseline_by_slug[slug])
        else:
            normalized_collections.append(row)
    _require(
        _metadata_digest(sorted(normalized_collections, key=itemgetter("slug")))
        == baseline_observation["public_collection_metadata_sha256"],
        "public collections changed outside the approved HEOR update",
    )


def validate_collection_transitions(
    policy: Any,
    heor: Any,
    approval: dict[str, Any],
) -> None:
    """Check owner-visible collection state before the first external write."""
    scope = cast("dict[str, Any]", approval["candidate_scope"])
    members = cast("list[dict[str, str]]", scope["members"])
    policy_notes = {row["dataset"]: row["note"] for row in members}
    _require(
        policy.slug == scope["policy_aus_slug"], "Policy AUS identity changed"
    )
    _require(policy.title == "Policy AUS", "Policy AUS title changed")
    _require(
        policy.private in {True, False}, "Policy AUS visibility is invalid"
    )
    _require(
        policy.description
        in {POLICY_OLD_DESCRIPTION, scope["policy_aus_collection_note"]},
        "Policy AUS description changed outside this transaction",
    )
    policy_items = _collection_items(policy)
    _require(
        set(policy_items).issubset(set(policy_notes)),
        "Policy AUS contains an out-of-scope item",
    )
    for dataset, item in policy_items.items():
        _require(item["type"] == "dataset", "Policy AUS contains a non-dataset")
        _require(
            item["note"] in {None, policy_notes[dataset]},
            "Policy AUS item note differs from the approved transition",
        )
    if not policy.private:
        _require(
            set(policy_items) == set(policy_notes)
            and all(
                policy_items[dataset]["note"] == note
                for dataset, note in policy_notes.items()
            )
            and policy.description == scope["policy_aus_collection_note"],
            "public Policy AUS is not already at the exact approved state",
        )

    _require(heor.slug == scope["heor_slug"], "HEOR identity changed")
    _require(heor.private is False, "HEOR visibility changed")
    _require(
        heor.description
        == "Registry-driven view of health-economics, reimbursement, "
        "outcomes-research, and related evidence datasets.",
        "HEOR description changed outside this transaction",
    )
    heor_items = _collection_items(heor)
    existing = set(
        cast("list[str]", scope["expected_heor_existing_dataset_members"])
    )
    allowed = existing | set(policy_notes)
    _require(
        set(heor_items).issubset(allowed) and existing.issubset(heor_items),
        "HEOR membership changed outside this transaction",
    )
    _require(
        heor_items["edithatogo/nz-health-appropriations"]["note"]
        == HEOR_NZ_NOTE,
        "HEOR New Zealand member or note changed",
    )
    old_notes = {
        **HEOR_EXISTING_NOTES,
        "edithatogo/australian-mbs-source-archive": None,
        "edithatogo/australian-pbs-source-archive": None,
    }
    for dataset, item in heor_items.items():
        _require(item["type"] == "dataset", "HEOR contains a non-dataset")
        if dataset in policy_notes:
            _require(
                item["note"] in {old_notes.get(dataset), policy_notes[dataset]},
                "HEOR item note differs from the approved transition",
            )
        else:
            _require(
                dataset == "edithatogo/nz-health-appropriations",
                "HEOR contains an unapproved member",
            )


def _write_registry_catalog(
    api: Any,
    public_api: Any,
    prepared: PreparedPublication,
    *,
    add_operation: Any,
    download: Any,
) -> str:
    registry_cfg = prepared.registry_cfg
    current = public_api.dataset_info(REGISTRY)
    current_revision = cast("str", current.sha)
    current_path = download(
        repo_id=REGISTRY,
        filename=cast("str", registry_cfg["catalog_path"]),
        repo_type="dataset",
        revision=current_revision,
        token=False,
    )
    current_catalog = Path(current_path).read_bytes()
    if current_revision == registry_cfg["baseline_revision"]:
        _require(
            _sha256(current_catalog) == registry_cfg["baseline_catalog_sha256"],
            "registry baseline changed before compare-and-swap",
        )
        result = api.create_commit(
            repo_id=REGISTRY,
            repo_type="dataset",
            revision="main",
            parent_commit=current_revision,
            commit_message="Reconcile public estate metadata",
            commit_description=(
                "Append public-only, fail-closed catalog entries and reconcile "
                "observed access metadata. No source payloads or rights claims."
            ),
            operations=[
                add_operation(
                    path_in_repo=cast("str", registry_cfg["catalog_path"]),
                    path_or_fileobj=prepared.target_catalog,
                )
            ],
        )
        return cast("str", result.oid)
    _require(
        _sha256(current_catalog) == prepared.target_catalog_sha,
        "registry has an unexpected revision; no overwrite performed",
    )
    return current_revision


def _preflight_collections(token: str, approval: dict[str, Any]) -> None:
    from huggingface_hub import (  # ruff: ignore[import-outside-top-level] -- optional publisher SDK; ty: ignore[unresolved-import]
        get_collection,
    )

    scope = cast("dict[str, Any]", approval["candidate_scope"])
    policy = get_collection(cast("str", scope["policy_aus_slug"]), token=token)
    heor = get_collection(cast("str", scope["heor_slug"]), token=token)
    validate_collection_transitions(policy, heor, approval)


def _update_collections(
    token: str, approval: dict[str, Any]
) -> tuple[int, int]:
    from huggingface_hub import (  # ruff: ignore[import-outside-top-level] -- optional publisher SDK; ty: ignore[unresolved-import]
        update_collection_metadata,
    )

    scope = cast("dict[str, Any]", approval["candidate_scope"])
    members = cast("list[dict[str, str]]", scope["members"])
    policy_notes = {row["dataset"]: row["note"] for row in members}
    heor_notes = dict(policy_notes)
    baseline_heor_notes = {
        "edithatogo/reimbursement-atlas": HEOR_EXISTING_NOTES[
            "edithatogo/reimbursement-atlas"
        ],
        "edithatogo/australian-mbs-source-archive": None,
        "edithatogo/australian-pbs-source-archive": None,
    }
    existing_heor = set(
        cast("list[str]", scope["expected_heor_existing_dataset_members"])
    )
    expected_heor = existing_heor | set(heor_notes)

    heor = _reconcile_collection(
        token,
        slug=cast("str", scope["heor_slug"]),
        desired_notes=heor_notes,
        expected_members=existing_heor,
        baseline_notes=baseline_heor_notes,
    )
    _verify_collection(
        heor,
        slug=cast("str", scope["heor_slug"]),
        private=False,
        description=None,
        expected_notes=heor_notes,
        preserved_notes={"edithatogo/nz-health-appropriations": HEOR_NZ_NOTE},
    )

    policy = _reconcile_collection(
        token,
        slug=cast("str", scope["policy_aus_slug"]),
        desired_notes=policy_notes,
        expected_members=set(),
        baseline_notes=dict.fromkeys(policy_notes),
        desired_description=cast("str", scope["policy_aus_collection_note"]),
        previous_description=POLICY_OLD_DESCRIPTION,
    )
    _verify_collection(
        policy,
        slug=cast("str", scope["policy_aus_slug"]),
        private=policy.private,
        description=cast("str", scope["policy_aus_collection_note"]),
        expected_notes=policy_notes,
    )
    update_collection_metadata(
        collection_slug=cast("str", scope["policy_aus_slug"]),
        description=cast("str", scope["policy_aus_collection_note"]),
        private=False,
        token=token,
    )
    return len(policy_notes), len(expected_heor)


def _verify_anonymous_readback(
    prepared: PreparedPublication,
    approval: dict[str, Any],
    *,
    get_collection: Any,
    download: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    scope = prepared.scope
    policy_notes = {
        row["dataset"]: row["note"]
        for row in cast("list[dict[str, str]]", scope["members"])
    }
    heor_notes = dict(policy_notes)
    policy_public = get_collection(
        cast("str", scope["policy_aus_slug"]), token=False
    )
    heor_public = get_collection(cast("str", scope["heor_slug"]), token=False)
    _verify_collection(
        policy_public,
        slug=cast("str", scope["policy_aus_slug"]),
        private=False,
        description=cast("str", scope["policy_aus_collection_note"]),
        expected_notes=policy_notes,
    )
    _verify_collection(
        heor_public,
        slug=cast("str", scope["heor_slug"]),
        private=False,
        description=None,
        expected_notes=heor_notes,
        preserved_notes={"edithatogo/nz-health-appropriations": HEOR_NZ_NOTE},
    )
    datasets, collections = observe_public_state()
    validate_normalized_public_state(
        datasets, collections, prepared.gap_record, approval
    )
    _validate_candidate_heads(datasets, approval)
    registry_row = next(
        (row for row in datasets if row["repo_id"] == REGISTRY), None
    )
    if registry_row is None:
        raise ValueError("registry missing from public estate")
    catalog_path = download(
        repo_id=REGISTRY,
        filename=cast("str", prepared.registry_cfg["catalog_path"]),
        repo_type="dataset",
        revision=cast("str", registry_row["revision"]),
        token=False,
    )
    _require(
        _sha256(Path(catalog_path).read_bytes()) == prepared.target_catalog_sha,
        "anonymous registry catalog digest differs from target",
    )
    _require(
        cast("str", scope["policy_aus_slug"])
        in {row["slug"] for row in collections},
        "Policy AUS is absent from anonymous public collection listing",
    )
    return datasets, collections, cast("str", registry_row["revision"])


def publish(approval: dict[str, Any]) -> dict[str, Any]:
    """Apply the exact guarded update, then verify public metadata readback."""
    validate_actions_context(dict(os.environ))
    from huggingface_hub import (  # ruff: ignore[import-outside-top-level] -- optional publisher SDK; ty: ignore[unresolved-import]
        CommitOperationAdd,
        HfApi,
        get_collection,
        hf_hub_download,
        whoami,
    )

    token = os.environ["HF_TOKEN"]
    _require(
        whoami(token=token).get("name") == "edithatogo",
        "Hub token is not for the approved owner",
    )
    api = HfApi(token=token)
    public_api = HfApi(token=False)
    prepared = _prepare_publication(approval, hf_hub_download)
    _validate_current_public_estate(prepared, approval)
    _preflight_collections(token, approval)
    write_revision = _write_registry_catalog(
        api,
        public_api,
        prepared,
        add_operation=CommitOperationAdd,
        download=hf_hub_download,
    )
    policy_count, heor_count = _update_collections(token, approval)
    datasets, collections, registry_revision = _verify_anonymous_readback(
        prepared,
        approval,
        get_collection=get_collection,
        download=hf_hub_download,
    )
    return {
        "status": "public_metadata_update_verified",
        "registry_revision": registry_revision,
        "registry_catalog_sha256": prepared.target_catalog_sha,
        "registry_entry_count": len(
            cast(
                "list[object]", json.loads(prepared.target_catalog)["datasets"]
            )
        ),
        "policy_aus_members": policy_count,
        "heor_members": heor_count,
        "public_dataset_count": len(datasets),
        "public_collection_count": len(collections),
        "public_dataset_metadata_sha256": _metadata_digest(datasets),
        "public_collection_metadata_sha256": _metadata_digest(collections),
        "approval_sha256": _sha256((ROOT / APPROVAL_PATH).read_bytes()),
        "scope_assessment_sha256": _sha256(prepared.scope_path.read_bytes()),
        "gap_qualification_sha256": _sha256(prepared.gap_path.read_bytes()),
        "baseline_registry_revision": prepared.registry_cfg[
            "baseline_revision"
        ],
        "baseline_catalog_sha256": prepared.registry_cfg[
            "baseline_catalog_sha256"
        ],
        "candidate_heads_unchanged": True,
        "rights_conclusion": False,
        "v4_admission": False,
        "source_payload_bytes_read": False,
        "source_values_read": False,
        "public_reads_stable": True,
        "write_revision": write_revision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the approved write (Actions/main/approval guards apply)",
    )
    parser.add_argument("--expected-approval-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if not args.apply:
        raise ValueError("this transaction requires the explicit --apply flag")
    approval = cast("dict[str, Any]", _load_json(ROOT / APPROVAL_PATH))
    _require(
        _sha256((ROOT / APPROVAL_PATH).read_bytes())
        == args.expected_approval_sha256,
        "approval manifest differs from the workflow-pinned digest",
    )
    _require(
        approval.get("schema_version") == 1, "approval schema version differs"
    )
    auth = cast("dict[str, Any]", approval.get("authorization"))
    _require(
        auth.get("status") == "approved",
        "maintainer metadata-publication approval is absent",
    )
    result = publish(approval)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    return 0


def _entrypoint() -> int:
    try:
        return main()
    except Exception as error:
        # Exception bodies from remote APIs can include untrusted server text.
        # Keep logs small and avoid echoing token-bearing request details.
        print(
            f"metadata publication failed closed ({type(error).__name__})",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(_entrypoint())
