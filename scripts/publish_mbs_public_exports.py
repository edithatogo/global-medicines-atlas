"""Append digest-approved native MBS report packs exclusively from Actions.

Deterministic stored ZIPs retain original HTML bytes and digest-shared aliases.
A final read-only hosted audit verifies every object in the cumulative archive.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import io
import json
import lzma
import os
import re
import zipfile
from http import HTTPStatus
from operator import itemgetter
from pathlib import Path
from typing import Any, cast

import httpx
from scripts.harvest_australian_pbs_utilisation import (
    fetch_existing_harvest_manifest,
)

from global_medicines_atlas.australian_harvesting import (
    DiscoveredHarvestResource,
    HarvestStageResult,
    build_cumulative_harvest_manifest,
    stage_harvest_payload,
    verify_anonymous_restore,
)

DATASET = "edithatogo/australian-mbs-utilisation-archive"
CONTRACT = Path("quality/qualifications/mbs-public-packs-20261106.json")
MAX_ENCODED = 60_000
MAX_SEGMENT = 45_000
MAX_EXPANDED = 128 * 1024 * 1024
MAX_OBJECTS = 10_000
MAX_MEMBERS = 100_000
PAIR_SIZE = 2


def require_hosted() -> None:
    """Refuse local, fork, scheduled and non-main publication attempts."""
    required = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": "edithatogo/global-medicines-atlas",
    }
    if any(os.environ.get(key) != value for key, value in required.items()):
        raise PermissionError(
            "MBS publication requires this repository's Actions main"
        )


def canonical(value: Any) -> bytes:
    """Serialize the reviewed transport/index deterministically."""
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def make_pack(document: dict[str, Any]) -> bytes:
    """Keep native bytes and safe logical aliases in a portable stored ZIP."""
    objects: dict[str, str] = document["objects"]
    members: list[dict[str, Any]] = document["members"]
    if not objects or len(objects) > MAX_OBJECTS or len(members) > MAX_MEMBERS:
        raise ValueError("MBS pack member bound violated")
    native: dict[str, bytes] = {}
    for digest, text in objects.items():
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("MBS pack digest name invalid")
        payload = text.encode("latin1")
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError("MBS pack native digest mismatch")
        native[f"objects/{digest}.html"] = payload
    identities: set[tuple[str, str]] = set()
    for member in members:
        identity = (member["cohort"], member["name"])
        if (
            identity in identities
            or re.fullmatch(r"[\w .()\-]+\.html", member["name"]) is None
            or Path(member["name"]).name != member["name"]
            or re.fullmatch(r"[a-z0-9-]{1,80}", member["cohort"]) is None
        ):
            raise ValueError("MBS pack unsafe or duplicate alias")
        identities.add(identity)
        if member["sha256"] not in objects:
            raise ValueError("MBS pack alias lacks native bytes")
        if len(native[f"objects/{member['sha256']}.html"]) != member["bytes"]:
            raise ValueError("MBS pack alias byte count mismatch")
    if {member["sha256"] for member in members} != set(objects):
        raise ValueError("MBS pack contains an unreferenced object")
    native["members.json"] = canonical({
        "schema_version": 1,
        "representation": "unmodified native HTML with digest-shared aliases",
        "members": members,
    })
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_STORED
    ) as archive:
        for name, payload in sorted(native.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o600 << 16
            archive.writestr(info, payload)
    return output.getvalue()


def decode_pack(encoded: str, expected: dict[str, Any]) -> bytes:
    """Check bounded transport and reviewed digests before writing any bytes."""
    compressed = base64.b64decode(encoded, validate=True)
    decoder = lzma.LZMADecompressor(memlimit=128 * 1024 * 1024)
    raw = decoder.decompress(compressed, max_length=MAX_EXPANDED + 1)
    if len(raw) > MAX_EXPANDED or not decoder.eof or decoder.unused_data:
        raise ValueError("MBS expansion bound or stream invalid")
    if hashlib.sha256(raw).hexdigest() != expected["input_sha256"]:
        raise ValueError("MBS input differs from reviewed public cohort")
    document = json.loads(raw)
    if len(document["members"]) != expected["members"]:
        raise ValueError("MBS logical member count mismatch")
    payload = make_pack(document)
    if (
        hashlib.sha256(payload).hexdigest() != expected["sha256"]
        or len(payload) != expected["bytes"]
    ):
        raise ValueError("MBS archive differs from reviewed public pack")
    return payload


def snapshot(sdk: Any, contract: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Require an existing public exact parent with all baseline objects intact."""
    parent, existing = fetch_existing_harvest_manifest(
        sdk, sdk.HfApi(token=False), DATASET
    )
    if parent is None or existing is None or existing.get("dataset") != DATASET:
        raise RuntimeError("MBS existing public parent unavailable")
    files = {item["path"]: item for item in existing["files"]}
    if any(
        files.get(item["path"]) != item for item in contract["baseline_files"]
    ):
        raise RuntimeError("MBS original archive object metadata changed")
    return parent, existing


def stage_pack(
    payload: bytes,
    batch: str,
    expected: dict[str, Any],
    contract: dict[str, Any],
) -> HarvestStageResult:
    """Stage reviewed original responses, preserving the custodial-copy caveat."""
    resource = DiscoveredHarvestResource(
        source_id="au-mbs-custodial-public-reports",
        category="native_public_report_pack",
        url=contract["source_url"],
        filename=f"{batch}.zip",
        archive_path=expected["path"],
        period_label="Native report/query periods retained per member",
    )
    stage = stage_harvest_payload(
        resource,
        Path("build/harvest/mbs-public-packs"),
        lambda _url: payload,
        allowed_domains=frozenset({"data.gov.au"}),
        raw_archive=True,
    )
    receipt = json.loads(stage.staged_receipt_path.read_text(encoding="utf-8"))
    receipt.update({
        "provenance_limitation": contract["provenance"],
        "source_url_role": "publisher dataset landing page only",
        "retrieved_at_role": "hosted custodial-pack materialization",
        "archive_representation": "generated ZIP; original HTML unchanged",
        "reviewed_input_sha256": expected["input_sha256"],
        "logical_members": expected["members"],
    })
    stage.staged_receipt_path.write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    return stage


def commit_pack(
    sdk: Any, stage: HarvestStageResult, parent: str, existing: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Create one exact-parent append; never create a dataset or delete objects."""
    require_hosted()
    full = build_cumulative_harvest_manifest(DATASET, [stage], existing)
    manifest_path = stage.staged_payload_path.parents[0] / "manifest.json"
    manifest_path.write_text(json.dumps(full, indent=2), encoding="utf-8")
    receipt_path = (
        stage.resource.archive_path.replace("raw/", "bronze/") + ".receipt.json"
    )
    operations = [
        sdk.CommitOperationAdd(path_in_repo=remote, path_or_fileobj=str(local))
        for remote, local in (
            (stage.resource.archive_path, stage.staged_payload_path),
            (receipt_path, stage.staged_receipt_path),
            ("manifest.json", manifest_path),
        )
    ]
    result = sdk.HfApi(token=os.environ["HF_TOKEN"]).create_commit(
        repo_id=DATASET,
        repo_type="dataset",
        parent_commit=parent,
        commit_message=f"Preserve approved native MBS public report pack {stage.resource.filename}",
        operations=operations,
    )
    return str(result.oid), full


def append_pack(
    sdk: Any, stage: HarvestStageResult, parent: str, existing: dict[str, Any]
) -> tuple[str, dict[str, Any], dict[str, Any], bool]:
    """Reuse an already-present immutable pack, or append and verify its pair."""
    path = stage.resource.archive_path
    files = {item["path"]: item for item in existing["files"]}
    already_present = path in files
    if already_present and files[path]["sha256"] != stage.receipt.sha256:
        raise RuntimeError("MBS immutable path collision")
    revision, full = (
        (parent, existing)
        if already_present
        else commit_pack(sdk, stage, parent, existing)
    )
    paths = {path, path.replace("raw/", "bronze/") + ".receipt.json"}
    verification = {
        "files": [item for item in full["files"] if item["path"] in paths]
    }
    if len(verification["files"]) != PAIR_SIZE:
        raise RuntimeError("MBS pack/receipt verification pair incomplete")
    return revision, full, verification, already_present


def append_annotation(
    sdk: Any, parent: str, existing: dict[str, Any], expected: dict[str, Any]
) -> tuple[str, dict[str, Any], dict[str, Any], bool]:
    """Append reviewed public comparison metadata without replacing source bytes."""
    require_hosted()
    if (
        not expected["path"].startswith("metadata/reconciliation/")
        or ".." in Path(expected["path"]).parts
    ):
        raise ValueError(
            "MBS annotation must stay in comparison metadata scope"
        )
    payload = Path(expected["local_path"]).read_bytes()
    if (
        len(payload) != expected["bytes"]
        or hashlib.sha256(payload).hexdigest() != expected["sha256"]
    ):
        raise ValueError(
            "MBS annotation differs from reviewed public comparison"
        )
    addition = {
        "path": expected["path"],
        "bytes": len(payload),
        "sha256": expected["sha256"],
        "kind": "source_comparison_annotation",
        "source_id": "au-mbs-custodial-public-reports",
    }
    files = {item["path"]: item for item in existing["files"]}
    if len(files) != len(existing["files"]):
        raise RuntimeError("MBS duplicate prior manifest paths")
    present = addition["path"] in files
    if present:
        if files[addition["path"]] != addition:
            raise RuntimeError("MBS immutable annotation path collision")
        return parent, existing, {"files": [addition]}, True
    if parent != expected["parent_revision"]:
        raise RuntimeError(
            "MBS annotation parent differs from reviewed archive"
        )
    files[addition["path"]] = addition
    full = {
        **existing,
        "files": sorted(files.values(), key=itemgetter("path")),
        "file_count": len(files),
    }
    target = Path("build/harvest/mbs-comparison-metadata")
    target.mkdir(parents=True, exist_ok=True)
    local = target / "annotation.json"
    local.write_bytes(payload)
    manifest = target / "manifest.json"
    manifest.write_text(json.dumps(full, indent=2) + "\n", encoding="utf-8")
    operations = [
        sdk.CommitOperationAdd(
            path_in_repo=addition["path"], path_or_fileobj=str(local)
        ),
        sdk.CommitOperationAdd(
            path_in_repo="manifest.json", path_or_fileobj=str(manifest)
        ),
    ]
    result = sdk.HfApi(token=os.environ["HF_TOKEN"]).create_commit(
        repo_id=DATASET,
        repo_type="dataset",
        parent_commit=parent,
        commit_message="Record scoped original-report age-band reconciliation; preserve native sources",
        operations=operations,
    )
    return str(result.oid), full, {"files": [addition]}, False


def audit_manifest(existing: dict[str, Any], contract: dict[str, Any]) -> None:
    """Require every approved pack before the final full-archive restore."""
    files = {item["path"]: item for item in existing["files"]}
    for expected in contract["batches"].values():
        observed = files.get(expected["path"], {})
        if observed.get("sha256") != expected["sha256"]:
            raise RuntimeError("MBS approved pack missing before final audit")


def stage_segment(batch: str, contract: dict[str, Any]) -> None:
    """Retain only one digest-approved public transport segment in Actions."""
    encoded = os.environ["MBS_PUBLIC_BUNDLE"]
    if len(encoded) > MAX_ENCODED:
        raise ValueError("MBS encoded segment exceeds bound")
    payload = base64.b64decode(encoded, validate=True)
    expected = contract["segments"][batch]
    if (
        len(payload) != expected["bytes"]
        or hashlib.sha256(payload).hexdigest() != expected["sha256"]
    ):
        raise ValueError("MBS segment differs from reviewed public transport")
    target = Path("build/mbs-public-segment")
    target.mkdir(parents=True, exist_ok=True)
    (target / "segment.bin").write_bytes(payload)


def collect_segments(contract: dict[str, Any]) -> str:
    """Read successful exact-head Actions artifacts; check every segment digest."""
    runs = json.loads(os.environ["MBS_PUBLIC_RUNS"])
    if set(runs) != set(contract["segments"]):
        raise ValueError("MBS segment run inventory mismatch")
    api = (
        "https://api.github.com/repos/edithatogo/global-medicines-atlas/actions"
    )
    headers = {
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Accept": "application/vnd.github+json",
    }

    def get(url: str) -> bytes:
        if not url.startswith(api + "/"):
            raise ValueError("MBS artifact API target denied")
        with httpx.Client(timeout=120, follow_redirects=False) as client:
            response = client.get(url, headers=headers)
            if response.status_code == HTTPStatus.FOUND:
                target = httpx.URL(response.headers["location"])
                if target.scheme != "https" or not target.host.endswith(
                    ".blob.core.windows.net"
                ):
                    raise ValueError("MBS artifact redirect target denied")
                response = client.get(
                    target
                )  # Signed artifact URL receives no bearer.
            if response.status_code >= HTTPStatus.BAD_REQUEST:
                raise RuntimeError("MBS artifact read failed; URL withheld")
            return response.content

    parts: list[bytes] = []
    for name, expected in sorted(contract["segments"].items()):
        run_id = runs[name]
        if not isinstance(run_id, int):
            raise TypeError("MBS invalid run identity")
        run = json.loads(get(f"{api}/runs/{run_id}"))
        if (
            run.get("head_sha") != os.environ["GITHUB_SHA"]
            or run.get("conclusion") != "success"
            or run.get("event") != "workflow_dispatch"
            or run.get("path")
            != ".github/workflows/australian-mbs-utilisation-harvest.yml"
        ):
            raise ValueError(
                "MBS staged run is not a successful exact-head harvest"
            )
        artifacts = json.loads(get(f"{api}/runs/{run_id}/artifacts"))[
            "artifacts"
        ]
        matches = [
            item
            for item in artifacts
            if item["name"] == f"mbs-public-{name}" and not item["expired"]
        ]
        if len(matches) != 1:
            raise ValueError("MBS staged artifact missing or ambiguous")
        with zipfile.ZipFile(
            io.BytesIO(get(f"{api}/artifacts/{matches[0]['id']}/zip"))
        ) as archive:
            if (
                archive.namelist() != ["segment.bin"]
                or archive.getinfo("segment.bin").file_size > MAX_SEGMENT
            ):
                raise ValueError("MBS unexpected staged artifact layout")
            payload = archive.read("segment.bin")
        if (
            len(payload) != expected["bytes"]
            or hashlib.sha256(payload).hexdigest() != expected["sha256"]
        ):
            raise ValueError("MBS staged artifact digest mismatch")
        parts.append(payload)
    return base64.b64encode(b"".join(parts)).decode()


def main() -> None:
    """Append reviewed public metadata or a pack, or audit the archive."""
    require_hosted()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract["dataset"] != DATASET:
        raise ValueError("MBS publication target mismatch")
    batch = os.environ["MBS_PUBLIC_BATCH"]
    if batch.startswith("stage-"):
        stage_segment(batch, contract)
        return
    sdk: Any = importlib.import_module("huggingface_hub")
    parent, existing = snapshot(sdk, contract)
    revision, full, verification, already_present = (
        parent,
        existing,
        existing,
        False,
    )
    if batch == "verify-all":
        if os.environ.get("MBS_PUBLIC_BUNDLE"):
            raise ValueError("MBS final verification takes no source input")
        audit_manifest(existing, contract)
    elif batch in contract.get("annotations", {}):
        revision, full, verification, already_present = append_annotation(
            sdk, parent, existing, contract["annotations"][batch]
        )
    else:
        expected = contract["batches"][batch]
        payload = decode_pack(collect_segments(contract), expected)
        stage = stage_pack(payload, batch, expected, contract)
        revision, full, verification, already_present = append_pack(
            sdk, stage, parent, existing
        )

    def anonymous_get(repo: str, filename: str) -> bytes:
        local = cast(
            "str",
            sdk.hf_hub_download(
                repo_id=repo,
                repo_type="dataset",
                revision=revision,
                filename=filename,
                token=False,
            ),
        )
        return Path(local).read_bytes()

    if batch in contract.get("annotations", {}):
        observed = json.loads(anonymous_get(DATASET, "manifest.json"))
        if observed != full:
            raise RuntimeError("MBS anonymous manifest readback differs")
    verify_anonymous_restore(
        DATASET, verification, anonymous_downloader=anonymous_get
    )
    receipt = {
        "dataset": DATASET,
        "revision": revision,
        "batch": batch,
        "workflow_commit": os.environ["GITHUB_SHA"],
        "already_present": already_present,
        "anonymous_digest_verification": "passed",
        "verification_scope": (
            "full_archive"
            if batch == "verify-all"
            else "new_annotation_with_prior_manifest_preserved"
            if batch in contract.get("annotations", {})
            else "new_pack_and_receipt"
        ),
        "verified_file_count": len(verification["files"]),
        "archive_file_count": full["file_count"],
        "participant_files_published": 0,
        "temporary_source_bytes_removed": False,
    }
    if batch in contract.get("annotations", {}):
        receipt["anonymous_manifest_readback"] = "passed"
        receipt["prior_manifest_objects_preserved"] = len(existing["files"])
        receipt["prior_verified_archive_revision"] = contract["annotations"][
            batch
        ]["parent_revision"]
    Path("build").mkdir(exist_ok=True)
    Path("build/mbs-utilisation-harvest-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
