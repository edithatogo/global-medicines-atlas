#!/usr/bin/env python3
"""Append one already-published, rights-qualified MBS object to the public root manifest."""

# ruff: file-ignore[suspicious-subprocess-import, subprocess-without-shell-equals-true, start-process-with-partial-path, too-many-statements, too-many-locals] -- hosted transaction uses fixed gh argv and an optional SDK

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import shutil
import subprocess  # fixed gh argv only
from datetime import UTC, datetime
from io import BytesIO
from operator import itemgetter
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path(
    "quality/qualifications/australian-m112-root-manifest-append-contract-20261017.json"
)
AUTHORIZATION = Path(
    "quality/qualifications/australian-mbs-harvest-publication-authorization.json"
)
RELEASE_CONTRACT = Path(
    "quality/qualifications/mbs-current-release-contract.json"
)
SOURCE_RECEIPT = Path(
    "quality/qualifications/australian-mbs-bronze-source-receipt-20261004.json"
)
OBJECT_INVENTORY = Path(
    "quality/qualifications/australian-m112-object-inventory-20260930.json"
)
REPOSITORY = "edithatogo/global-medicines-atlas"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sibling_matches(sibling: Any, obj: dict[str, Any]) -> bool:
    return (
        sibling is not None
        and sibling.size == obj["bytes"]
        and sibling.blob_id == obj["expected_blob_id"]
    )


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object at {path}")
    return cast("dict[str, Any]", value)


def verify_static_authority(
    contract: dict[str, Any], root: Path = ROOT
) -> None:
    """Bind the one-object append to existing approved MBS evidence."""
    references = contract.get("evidence_inputs")
    if not isinstance(references, dict):
        raise TypeError("Append contract is missing evidence input digests")
    references = cast("dict[str, Any]", references)
    expected = {
        "publication_authorization": AUTHORIZATION,
        "release_contract": RELEASE_CONTRACT,
        "source_receipt": SOURCE_RECEIPT,
        "object_inventory": OBJECT_INVENTORY,
    }
    for key, path in expected.items():
        reference = references.get(key)
        if not isinstance(reference, dict):
            raise TypeError(f"Append contract has an invalid {key} reference")
        reference = cast("dict[str, Any]", reference)
        if reference.get("path") != path.as_posix():
            raise ValueError(f"Append contract has an invalid {key} reference")
        if sha256_bytes((root / path).read_bytes()) != reference.get("sha256"):
            raise ValueError(f"Approved {key} evidence changed")

    authorization = read_json(root / AUTHORIZATION)
    release = read_json(root / RELEASE_CONTRACT)
    receipt = read_json(root / SOURCE_RECEIPT)
    inventory = read_json(root / OBJECT_INVENTORY)
    obj = contract.get("object")
    if not isinstance(obj, dict):
        raise TypeError("Append contract object is missing")
    obj = cast("dict[str, Any]", obj)
    if (
        authorization.get("external_publication_authorized") is not True
        or authorization.get("maintainer_asserted_redistribution_permission")
        is not True
        or authorization.get("dataset") != contract.get("dataset")
        or "au-mbs" not in authorization.get("allowed_sources", [])
        or "monthly_schedule_xml" not in authorization.get("categories", [])
    ):
        raise ValueError(
            "Existing MBS publication authority does not cover this object"
        )
    if (
        release.get("publication_authorized") is not True
        or release.get("source_id") != "au-mbs"
        or release.get("effective_date") != "2026-08-01"
    ):
        raise ValueError(
            "Exact MBS release contract does not authorize this object"
        )
    b2 = receipt.get("b2")
    if not isinstance(b2, dict):
        raise TypeError("Accepted MBS source receipt has no B2 identity")
    b2 = cast("dict[str, Any]", b2)
    receipt_matches_object = all([
        receipt.get("rights_state") == "permitted",
        receipt.get("admission_state") == "accepted",
        receipt.get("content_id") == obj.get("sha256"),
        b2.get("byte_count") == obj.get("bytes"),
        b2.get("external_reference", "").endswith("/" + str(obj.get("path"))),
        b2.get("payload_sha256") == obj.get("sha256"),
    ])
    if not receipt_matches_object:
        raise ValueError("Accepted MBS source receipt does not bind the object")
    records = inventory.get("raw_source_payload_candidates")
    if not isinstance(records, list):
        raise TypeError("M-112 object inventory is missing its object rows")
    records = cast("list[Any]", records)
    matched = [
        record for record in records if record.get("path") == obj.get("path")
    ]
    if len(matched) != 1 or (
        matched[0].get("bytes") != obj.get("bytes")
        or matched[0].get("hub_git_blob_oid") != obj.get("expected_blob_id")
    ):
        raise ValueError(
            "M-112 object inventory does not bind the public object"
        )


def validate_manifest(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Validate the existing harvest-manifest envelope and return unique path rows."""
    if (
        manifest.get("schema_id") != "global-medicines-atlas.harvest-manifest"
        or manifest.get("schema_version") != 1
        or not isinstance(manifest.get("files"), list)
        or manifest.get("file_count") != len(manifest["files"])
    ):
        raise ValueError("Public MBS root manifest has an unsupported shape")
    files = cast("list[Any]", manifest["files"])
    rows: dict[str, dict[str, Any]] = {}
    for value in files:
        if not isinstance(value, dict):
            raise TypeError("Public root manifest contains an invalid file row")
        value = cast("dict[str, Any]", value)
        if not isinstance(value.get("path"), str):
            raise TypeError("Public root manifest contains an invalid file row")
        if value["path"] in rows:
            raise ValueError("Public root manifest contains duplicate paths")
        rows[value["path"]] = value
    return rows


def build_updated_manifest(
    manifest: dict[str, Any], contract: dict[str, Any], *, generated_at: str
) -> tuple[dict[str, Any], bool]:
    """Append exactly one immutable object row; return (manifest, changed)."""
    rows = validate_manifest(manifest)
    obj = contract["object"]
    path = obj["path"]
    expected_row = {
        "path": path,
        "bytes": obj["bytes"],
        "sha256": obj["sha256"],
        "kind": "raw_payload",
        "source_id": "au-mbs",
        "category": "monthly_schedule_xml",
    }
    alias = rows.get(obj["preserved_alias_path"])
    expected_alias = {
        "sha256": obj["sha256"],
        "bytes": obj["bytes"],
        "kind": "raw_payload",
        "source_id": "au-mbs",
        "category": "monthly_schedule_xml",
    }
    if alias is None or any(
        alias.get(key) != value for key, value in expected_alias.items()
    ):
        raise ValueError(
            "Existing historical alias no longer binds the same object"
        )

    existing = rows.get(path)
    if existing is not None:
        if existing != expected_row:
            raise ValueError(
                "Root manifest already has a conflicting object row"
            )
        return manifest, False

    updated = dict(manifest)
    updated["files"] = sorted(
        [*manifest["files"], expected_row], key=itemgetter("path")
    )
    updated["file_count"] = len(updated["files"])
    updated["generated_at"] = generated_at
    return updated, True


def _require_hosted_main(exact_commit: str) -> None:
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_SHA") != exact_commit
    ):
        raise ValueError(
            "MBS root manifest publication requires the exact main Actions run"
        )
    current = subprocess.check_output(
        ["gh", "api", f"repos/{REPOSITORY}/commits/main", "--jq", ".sha"],
        text=True,
        timeout=30,
    ).strip()
    if current != exact_commit:
        raise ValueError("Default branch advanced beyond the authorized commit")


def publish(exact_commit: str, receipt_path: Path) -> dict[str, Any]:
    """Append one manifest row by CAS and verify it with anonymous metadata reads."""
    _require_hosted_main(exact_commit)
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise ValueError("Protected HF_TOKEN is unavailable")
    contract = read_json(ROOT / CONTRACT)
    verify_static_authority(contract)
    hub = cast("Any", importlib.import_module("huggingface_hub"))
    commit_operation_add = hub.CommitOperationAdd
    hf_api = hub.HfApi
    hf_hub_download = hub.hf_hub_download

    dataset = cast("str", contract["dataset"])
    expected_parent = cast("str", contract["expected_parent_revision"])
    expected_manifest_hash = cast(
        "str", contract["expected_parent_manifest_sha256"]
    )
    expected_file_count = cast("int", contract["expected_parent_file_count"])
    cache = ROOT / "build" / "m112-root-manifest-cache"
    cache.mkdir(parents=True, exist_ok=True)
    public = hf_api(token=False)
    writer = hf_api(token=token)
    before: Any = public.dataset_info(dataset, files_metadata=True)
    if before.private or before.gated:
        raise ValueError(
            "MBS dataset must remain anonymously public and ungated"
        )
    siblings: dict[str, Any] = {
        item.rfilename: item for item in before.siblings
    }
    obj = contract["object"]
    target = siblings.get(obj["path"])
    alias = siblings.get(obj["preserved_alias_path"])
    if not _sibling_matches(target, obj) or not _sibling_matches(alias, obj):
        raise ValueError(
            "Public object or preserved alias identity has drifted"
        )

    def fetch_manifest(revision: str) -> bytes:
        path = cast(
            "str",
            hf_hub_download(
                repo_id=dataset,
                repo_type="dataset",
                filename="manifest.json",
                revision=revision,
                token=False,
                cache_dir=cache,
            ),
        )
        return Path(path).read_bytes()

    before_revision = cast("str", before.sha)
    before_bytes = fetch_manifest(before_revision)
    before_hash = sha256_bytes(before_bytes)
    before_manifest = cast("dict[str, Any]", json.loads(before_bytes))
    rows = validate_manifest(before_manifest)
    existing = rows.get(obj["path"])
    result_revision: str
    result_bytes: bytes
    status: str
    if existing is not None:
        updated, changed = build_updated_manifest(
            before_manifest,
            contract,
            generated_at=before_manifest["generated_at"],
        )
        if changed:
            raise ValueError("Manifest idempotency check is inconsistent")
        result_revision = before_revision
        result_bytes = before_bytes
        status = "already_present_and_verified"
    else:
        if (
            before_revision != expected_parent
            or before_hash != expected_manifest_hash
            or len(rows) != expected_file_count
        ):
            raise ValueError(
                "MBS root manifest changed; refresh the exact snapshot before retrying"
            )
        updated, changed = build_updated_manifest(
            before_manifest,
            contract,
            generated_at=(
                datetime
                .now(UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            ),
        )
        if not changed or len(updated["files"]) != len(rows) + 1:
            raise ValueError("Append plan did not add exactly one metadata row")
        result_bytes = (
            json.dumps(updated, indent=2, sort_keys=True) + "\n"
        ).encode()
        response = writer.create_commit(
            repo_id=dataset,
            repo_type="dataset",
            parent_commit=before_revision,
            commit_message="Append verified August 2026 MBS source identity to root manifest",
            operations=[
                commit_operation_add(
                    path_in_repo="manifest.json",
                    path_or_fileobj=BytesIO(result_bytes),
                )
            ],
        )
        result_revision = str(response.oid)
        status = "appended_and_verified"

    after: Any = public.dataset_info(
        dataset, revision=result_revision, files_metadata=True
    )
    if after.private or after.gated or after.sha != result_revision:
        raise ValueError(
            "Updated MBS dataset is not anonymously public at the result revision"
        )
    after_siblings: dict[str, Any] = {
        item.rfilename: item for item in after.siblings
    }
    after_target = after_siblings.get(obj["path"])
    after_alias = after_siblings.get(obj["preserved_alias_path"])
    if not _sibling_matches(after_target, obj) or not _sibling_matches(
        after_alias, obj
    ):
        raise ValueError(
            "Public object identity changed during manifest append"
        )
    anonymous_bytes = fetch_manifest(result_revision)
    after_hash = sha256_bytes(anonymous_bytes)
    if anonymous_bytes != result_bytes:
        raise ValueError(
            "Anonymous manifest readback differs from the committed bytes"
        )
    after_manifest = cast("dict[str, Any]", json.loads(anonymous_bytes))
    after_rows = validate_manifest(after_manifest)
    if after_rows.get(obj["path"]) != {
        "path": obj["path"],
        "bytes": obj["bytes"],
        "sha256": obj["sha256"],
        "kind": "raw_payload",
        "source_id": "au-mbs",
        "category": "monthly_schedule_xml",
    }:
        raise ValueError(
            "Anonymous root manifest readback did not include the exact object"
        )

    after_target = cast("Any", after_target)
    receipt: dict[str, Any] = {
        "schema_id": "global-medicines-atlas.australian-m112-root-manifest-append-receipt",
        "schema_version": 1,
        "status": status,
        "github_commit": exact_commit,
        "github_run": f"https://github.com/{REPOSITORY}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}",
        "dataset": dataset,
        "before_revision": before.sha,
        "after_revision": result_revision,
        "before_manifest_sha256": before_hash,
        "after_manifest_sha256": after_hash,
        "file_count_before": len(rows),
        "file_count_after": len(after_rows),
        "object": {
            "path": obj["path"],
            "sha256": obj["sha256"],
            "bytes": obj["bytes"],
            "hub_git_blob_oid": after_target.blob_id,
        },
        "preserved_alias_path": obj["preserved_alias_path"],
        "metadata_only": True,
        "source_payload_bytes_read": False,
        "rights_changed": False,
        "admission_changed": False,
        "denominator_changed": False,
        "m112_accepted": False,
        "anonymous_manifest_readback": "passed",
        "public_object_identity_readback": "passed",
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(cache)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    args = parser.parse_args()
    receipt = publish(args.exact_commit, args.receipt_output)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
