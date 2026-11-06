"""Preserve the exact reviewed public Medicare/AIHW cohort from Actions only.

No OneDrive credentials, private paths or cohort-derived inputs are accepted.
Custodial transport is limited to the committed public-only digest allowlist. Reuse prior verified objects; verify every new pair and the unchanged
prior manifest before reporting completion.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import io
import json
import lzma
import os
import urllib.request
import zipfile
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts.harvest_australian_pbs_utilisation import (
    fetch_existing_harvest_manifest,
)
from scripts.publish_mbs_public_exports import (
    collect_segments,
    require_hosted,
    stage_segment,
)

from global_medicines_atlas.australian_harvesting import (
    DiscoveredHarvestResource,
    GovernedRedirectHandler,
    HarvestStageResult,
    build_cumulative_harvest_manifest,
    stage_harvest_payload,
    verify_anonymous_restore,
)

CONTRACT = Path(
    "quality/qualifications/remaining-public-archives-20261106.json"
)
HOSTS = frozenset({"data.gov.au", "www.aihw.gov.au", "www.health.gov.au"})
MAX_BYTES = 512 * 1024**2
MAX_MEMBERS = 20_000
MAX_CUSTODIAL_INPUT = 2_000_000


def digest_json(value: Any) -> str:
    """Bind a complete prior manifest independently of JSON whitespace."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def read_public_payload(url: str, limit: int) -> tuple[bytes, str]:
    """Use bounded GET; publisher HEAD may deny otherwise public downloads."""
    if urlparse(url).scheme != "https" or urlparse(url).netloc not in HOSTS:
        raise ValueError("Unapproved public source URL")
    if not 0 < limit <= MAX_BYTES:
        raise ValueError("Public download bound invalid")
    opener = urllib.request.build_opener(GovernedRedirectHandler(HOSTS))
    request = urllib.request.Request(  # ruff: ignore[suspicious-url-open-usage]
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; GlobalMedicinesAtlas/1.0)",
            "Referer": "https://www.aihw.gov.au/reports/medicines/pbs-monthly-data/data",
        },
    )
    with opener.open(request, timeout=180) as response:
        if response.status != HTTPStatus.OK or response.headers.get(
            "Content-Range"
        ):
            raise ValueError("Full public acquisition requires HTTP 200")
        length = response.headers.get("Content-Length")
        if length is not None and int(length) != limit:
            raise ValueError("Public Content-Length differs from review")
        if "html" in response.headers.get("Content-Type", "").lower():
            raise ValueError("HTML is not a reviewed statistical download")
        payload = response.read(limit + 1)
        if len(payload) != limit:
            raise ValueError("Public download length differs from review")
        return payload, str(response.url)


def validate_payload(payload: bytes, item: dict[str, Any]) -> None:
    """Reject byte substitution and unsafe/oversized ZIP metadata."""
    if (
        len(payload) != item["bytes"]
        or hashlib.sha256(payload).hexdigest() != item["sha256"]
    ):
        raise ValueError("Public bytes differ from reviewed digest")
    if item["resource"]["filename"].lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = archive.infolist()
            names = [m.filename for m in members]
            if (
                len(members) > MAX_MEMBERS
                or len(names) != len(set(names))
                or sum(m.file_size for m in members) > 4 * 1024**3
            ):
                raise ValueError("Public ZIP metadata exceeds approved bounds")


def snapshot(sdk: Any, expected: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Require the reviewed public parent and every prior manifest entry."""
    parent, existing = fetch_existing_harvest_manifest(
        sdk, sdk.HfApi(token=False), expected["dataset"]
    )
    if (
        parent is None
        or parent != expected["parent_revision"]
        or existing is None
        or existing.get("dataset") != expected["dataset"]
        or digest_json(existing) != expected["manifest_sha256"]
    ):
        raise RuntimeError("Public archive parent differs from review")
    files = existing["files"]
    if len({f["path"] for f in files}) != len(files):
        raise RuntimeError("Prior manifest has duplicate paths")
    return parent, existing


def stage_custodial(
    expected: dict[str, Any], stage_dir: Path
) -> list[HarvestStageResult]:
    """Validate exact public-only custodial bytes before staging original files."""
    require_hosted()
    if "custodial" not in expected:
        return []
    approved = expected["custodial"]
    encoded = collect_segments(approved)
    decoder = lzma.LZMADecompressor(memlimit=128 * 1024**2)
    raw = decoder.decompress(
        base64.b64decode(encoded, validate=True),
        max_length=MAX_CUSTODIAL_INPUT + 1,
    )
    if (
        len(raw) > MAX_CUSTODIAL_INPUT
        or not decoder.eof
        or decoder.unused_data
        or hashlib.sha256(raw).hexdigest() != approved["input_sha256"]
    ):
        raise ValueError("Custodial public input differs from review")
    pairs = json.loads(raw, object_pairs_hook=list)
    payloads = dict(pairs)
    if len(payloads) != len(pairs) or set(payloads) != set(approved["files"]):
        raise ValueError("Custodial public file set differs from review")
    stages: list[HarvestStageResult] = []
    for name, value in payloads.items():
        item = approved["files"][name]
        content = value.encode("latin1")
        validate_payload(content, item)
        resource = DiscoveredHarvestResource(**item["resource"])
        stage = stage_harvest_payload(
            resource,
            stage_dir,
            lambda _url, data=content: data,
            allowed_domains=HOSTS,
        )
        receipt = json.loads(
            stage.staged_receipt_path.read_text(encoding="utf-8")
        )
        receipt.update(
            provenance_limitation=approved["provenance"],
            source_url_role="publisher landing page only",
            retrieved_at_role="hosted custodial-copy materialization",
        )
        stage.staged_receipt_path.write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )
        stages.append(stage)
    return stages


def publish(
    sdk: Any, expected: dict[str, Any], stage_dir: Path
) -> dict[str, Any]:
    """Append only this committed cohort, then verify new pairs anonymously."""
    require_hosted()
    parent, existing = snapshot(sdk, expected)
    prior = {f["path"]: f for f in existing["files"]}
    prior_digests = {(f["sha256"], f["bytes"]) for f in prior.values()}
    stages = stage_custodial(expected, stage_dir)
    for item in expected["files"]:
        if (item["sha256"], item["bytes"]) in prior_digests:
            continue
        resource = DiscoveredHarvestResource(**item["resource"])
        if resource.archive_path in prior:
            raise RuntimeError("Immutable public path collision")
        payload, final_url = read_public_payload(resource.url, item["bytes"])
        validate_payload(payload, item)
        stage = stage_harvest_payload(
            resource,
            stage_dir,
            lambda _url, data=payload, target=final_url: (data, target),
            allowed_domains=HOSTS,
            raw_archive=True,
            raw_archive_max_bytes=MAX_BYTES,
        )
        stages.append(stage)
        print(f"Staged public object {len(stages)}", flush=True)
    if not stages:
        return {
            "dataset": expected["dataset"],
            "revision": parent,
            "new_payloads": 0,
            "status": "all reviewed digests already present",
        }
    full = build_cumulative_harvest_manifest(
        expected["dataset"], stages, existing
    )
    full_by_path = {f["path"]: f for f in full["files"]}
    if any(full_by_path.get(path) != value for path, value in prior.items()):
        raise RuntimeError("Prior public manifest changed")
    verification = {
        "files": [f for f in full["files"] if f["path"] not in prior]
    }
    if len(verification["files"]) != 2 * len(stages):
        raise RuntimeError("New public payload/receipt pairs incomplete")
    manifest_path = stage_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(full, indent=2) + "\n", encoding="utf-8"
    )
    operations: list[Any] = []
    for stage in stages:
        for remote, local in (
            (stage.resource.archive_path, stage.staged_payload_path),
            (
                stage.resource.archive_path.replace("raw/", "bronze/")
                + ".receipt.json",
                stage.staged_receipt_path,
            ),
        ):
            operations.append(
                sdk.CommitOperationAdd(
                    path_in_repo=remote, path_or_fileobj=str(local)
                )
            )
    operations.append(
        sdk.CommitOperationAdd(
            path_in_repo="manifest.json", path_or_fileobj=str(manifest_path)
        )
    )
    result = sdk.HfApi(token=os.environ["HF_TOKEN"]).create_commit(
        repo_id=expected["dataset"],
        repo_type="dataset",
        parent_commit=parent,
        commit_message="Preserve reviewed public Medicare and AIHW source files",
        operations=operations,
    )
    revision = str(result.oid)

    def anonymous_get(repo: str, path: str) -> bytes:
        cached = sdk.hf_hub_download(
            repo_id=repo,
            repo_type="dataset",
            revision=revision,
            filename=path,
            token=False,
        )
        return Path(cached).read_bytes()

    verify_anonymous_restore(expected["dataset"], verification, anonymous_get)
    if json.loads(anonymous_get(expected["dataset"], "manifest.json")) != full:
        raise RuntimeError("Anonymous cumulative manifest differs")
    return {
        "dataset": expected["dataset"],
        "revision": revision,
        "parent_revision": parent,
        "new_payloads": len(stages),
        "verified_file_count": len(verification["files"]),
        "prior_manifest_objects_preserved": len(prior),
        "archive_file_count": len(full["files"]),
        "anonymous_digest_verification": "passed",
        "verification_scope": "new pairs and complete prior manifest preservation",
        "prior_anonymous_verification_run": expected["prior_verification_run"],
        "participant_files_published": 0,
        "temporary_source_bytes_removed": False,
        "workflow_commit": os.environ["GITHUB_SHA"],
        "workflow_run": os.environ["GITHUB_RUN_ID"],
    }


def main() -> None:
    """Load only committed public files after checking the hosted-only guard."""
    require_hosted()
    destination = os.environ["PUBLIC_ARCHIVE_DESTINATION"]
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("external_publication_authorized") is not True:
        raise PermissionError("Public archive publication is not authorized")
    expected = contract["archives"][destination]
    if (
        expected["dataset"]
        != f"edithatogo/australian-{destination}-utilisation-archive"
    ):
        raise ValueError("Public archive destination mismatch")
    batch = os.environ.get("MBS_PUBLIC_BATCH", "")
    if batch.startswith("stage-remaining-"):
        stage_segment(batch, expected["custodial"])
        return
    sdk = importlib.import_module("huggingface_hub")
    receipt = publish(sdk, expected, Path("build/harvest/remaining-public"))
    Path(f"build/{destination}-utilisation-harvest-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
