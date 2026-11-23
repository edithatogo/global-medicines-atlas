"""Transfer the approved current openFDA index from GitHub Actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import zipfile
from datetime import UTC, datetime
from http import HTTPStatus
from importlib import import_module
from itertools import batched
from operator import itemgetter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import httpx

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.data_layer_archive import (
    HuggingFaceAnonymousArtifactVerifier,
)
from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main,
)
from global_medicines_atlas.publication_transport import (
    ArtifactBinding,
    PublicationDestination,
    PublicationPlan,
    PublicationTarget,
    PublicationTransportReceipt,
    PublicationTransportState,
    authorization_from_environment,
    verify_publication,
)

BATCH = "openfda-all-20261120"
REPOSITORY = f"edithatogo/global-medicines-atlas-{BATCH}"
CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "quality/source-batches"
    / BATCH
    / "manifest.json"
)
INDEX_URL = "https://api.fda.gov/download.json"
ZIP_ROOT = "https://download.open.fda.gov/"
BATCH_SIZE = 8
MAX_ZIP_BYTES = 512 * 1024 * 1024
MAX_REGULAR_BYTES = 256 * 1024 * 1024
SOURCE_TIMEOUT = 90
TRANSIENT_STATUSES = {408, 429, 500, 502, 503, 504}


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def index_paths(index: bytes, contract: dict[str, Any]) -> tuple[str, ...]:
    """Return the unique approved FDA ZIP paths from the pinned index."""
    if hashlib.sha256(index).hexdigest() != contract["source_index_sha256"]:
        raise ValueError("FDA index SHA-256 has changed")
    index_data = json.loads(index)
    domains = index_data["results"]
    if (
        index_data["meta"]["last_updated"] != contract["source_index_date"]
        or sum(map(len, domains.values())) != contract["expected_endpoints"]
    ):
        raise ValueError(
            "FDA index date or endpoint count differs from approval"
        )
    paths: list[str] = []
    for endpoints in domains.values():
        for endpoint in endpoints.values():
            for item in endpoint["partitions"]:
                url = item["file"]
                path = url.removeprefix(ZIP_ROOT)
                if url != ZIP_ROOT + path or not re.fullmatch(
                    r"[A-Za-z0-9_./-]+\.json\.zip", path
                ):
                    raise ValueError("FDA index contains an unapproved ZIP URL")
                paths.append(ArtifactBinding.path_is_safe(path))
    if len(paths) != contract["expected_payload_count"] or len(paths) != len(
        set(paths)
    ):
        raise ValueError("FDA ZIP paths are incomplete or non-unique")
    return tuple(sorted(paths))


def download_zip(
    client: httpx.Client, path: str, destination: Path
) -> dict[str, Any]:
    """Read one original ZIP and bind its bytes and HTTP provenance."""
    sha256 = hashlib.sha256()
    size = 0
    url = ZIP_ROOT + path
    with (
        client.stream("GET", url) as response,
        destination.open("wb") as output,
    ):
        response.raise_for_status()
        if response.status_code != HTTPStatus.OK:
            raise ValueError(f"FDA did not return a complete ZIP: {path}")
        length = response.headers.get("Content-Length")
        for block in response.iter_raw():
            size += len(block)
            if size > MAX_ZIP_BYTES:
                raise ValueError(f"FDA ZIP exceeds the size bound: {path}")
            output.write(block)
            sha256.update(block)
    if (length is not None and size != int(length)) or not zipfile.is_zipfile(
        destination
    ):
        raise ValueError(f"FDA response has an invalid length or ZIP: {path}")
    return {
        "path": path,
        "sha256": sha256.hexdigest(),
        "size": size,
        "source_url": url,
        "source_etag": response.headers.get("ETag"),
        "source_last_modified": response.headers.get("Last-Modified"),
        "retrieved_at": datetime.now(UTC).isoformat(),
    }


def fetch_zip(
    client: httpx.Client, path: str, destination: Path
) -> dict[str, Any]:
    """Retry transient, read-only source failures before binding bytes."""
    for delay in (2, 4):
        try:
            return download_zip(client, path, destination)
        except (httpx.TransportError, httpx.HTTPStatusError) as error:
            if (
                isinstance(error, httpx.HTTPStatusError)
                and error.response.status_code not in TRANSIENT_STATUSES
            ):
                raise
            print(f"Retrying FDA read of {path} after {error}", flush=True)
            time.sleep(delay)
    return download_zip(client, path, destination)


def preupload_zips(
    api: Any, hub: Any, client: httpx.Client, paths: tuple[str, ...]
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Transfer bounded batches and retain exact commit operations."""
    operations: list[Any] = []
    records: list[dict[str, Any]] = []
    regular_bytes = 0
    for batch in batched(paths, BATCH_SIZE, strict=False):
        with TemporaryDirectory(prefix="openfda-") as scratch:
            additions: list[Any] = []
            for position, path in enumerate(batch):
                destination = Path(scratch) / f"{position}.zip"
                records.append(fetch_zip(client, path, destination))
                additions.append(
                    hub.CommitOperationAdd(
                        path_in_repo=path, path_or_fileobj=destination
                    )
                )
            api.preupload_lfs_files(
                REPOSITORY, additions=additions, repo_type="dataset"
            )
            # The SDK drops uploaded LFS input paths. Preserve small regular
            # Git files before releasing this batch's scratch directory.
            for addition in additions:
                if isinstance(addition.path_or_fileobj, (str, Path)):
                    source = Path(addition.path_or_fileobj)
                    regular_bytes += source.stat().st_size
                    if regular_bytes > MAX_REGULAR_BYTES:
                        raise ValueError(
                            "FDA ZIPs exceed the regular Git limit"
                        )
                    addition.path_or_fileobj = source.read_bytes()
            operations.extend(additions)
        print(f"Staged {len(records)}/{len(paths)} FDA ZIPs", flush=True)
    return operations, records


def add_publication_metadata(
    hub: Any,
    operations: list[Any],
    records: list[dict[str, Any]],
    contract: dict[str, Any],
    index: bytes,
) -> PublicationPlan:
    """Add the FDA index, per-file receipts and public dataset metadata."""
    card = (
        "---\nlicense: other\ntags:\n- fda\n- regulatory\n---\n\n"
        f"# openFDA bulk archive {contract['source_index_date']}\n\n"
        f"This archive contains {len(records)} unmodified FDA ZIPs across "
        f"{contract['expected_endpoints']} openFDA endpoints. GitHub Actions "
        "retrieved the files from FDA. The artifact manifest records each "
        "source URL, retrieval time, byte count and SHA-256 digest.\n\n"
        "[openFDA downloads](https://open.fda.gov/apis/downloads/) · "
        "[FDA terms](https://open.fda.gov/terms/)\n"
    )
    metadata = {
        "FDA-DOWNLOAD-INDEX.json": index,
        "README.md": card.encode(),
        "rights.json": json_bytes(contract["rights"]),
    }
    records.extend(
        {
            "path": path,
            "sha256": hashlib.sha256(body).hexdigest(),
            "size": len(body),
        }
        for path, body in metadata.items()
    )
    manifest = json_bytes({
        **contract,
        "artifact_count": len(records),
        "artifact_bytes": sum(record["size"] for record in records),
        "artifacts": sorted(records, key=itemgetter("path")),
    })
    metadata["ARTIFACT-MANIFEST.json"] = manifest
    records.append({
        "path": "ARTIFACT-MANIFEST.json",
        "sha256": hashlib.sha256(manifest).hexdigest(),
        "size": len(manifest),
    })
    operations.extend(
        hub.CommitOperationAdd(path_in_repo=path, path_or_fileobj=body)
        for path, body in metadata.items()
    )
    return PublicationPlan(
        release_version=BATCH,
        target=PublicationTarget(
            destination=PublicationDestination.HUGGING_FACE,
            repository=REPOSITORY,
            revision="main",
            public_base_url=f"https://huggingface.co/datasets/{REPOSITORY}",
        ),
        artifacts=tuple(
            ArtifactBinding(
                relative_path=record["path"],
                sha256=record["sha256"],
                size=record["size"],
            )
            for record in sorted(records, key=itemgetter("path"))
        ),
        allow_identical_content=True,
    )


def publish(output: Path, exact_commit: str) -> None:
    """Publish only the pinned, approved snapshot from a protected dispatch."""
    require_hosted_main(exact_commit)
    contract = json.loads(CONTRACT.read_bytes())
    if (
        contract["publication_approved"] is not True
        or contract["repository"] != REPOSITORY
        or contract["source_url"] != INDEX_URL
        or not authorization_from_environment(
            dict(os.environ)
        ).permits_external_write
    ):
        raise PermissionError("Fresh FDA snapshot publication is not approved")
    policy = AcquisitionPolicy(
        allowed_hosts=("api.fda.gov", "download.open.fda.gov"),
        timeout_seconds=SOURCE_TIMEOUT,
    )
    with httpx.Client(
        transport=BoundIPAddressTransport(policy=policy),
        follow_redirects=False,
        timeout=SOURCE_TIMEOUT,
        headers={"Accept-Encoding": "identity"},
    ) as client:
        index = client.get(INDEX_URL).raise_for_status().content
        paths = index_paths(index, contract)
        intent = {
            "commit": exact_commit,
            "run_id": os.environ["GITHUB_RUN_ID"],
            "repository": REPOSITORY,
            "source_index_sha256": contract["source_index_sha256"],
        }
        (output / "source-intent.json").write_bytes(json_bytes(intent))
        hub = cast("Any", import_module("huggingface_hub"))
        api = hub.HfApi(token=os.environ["HF_TOKEN"])
        api.create_repo(
            REPOSITORY, repo_type="dataset", private=False, exist_ok=True
        )
        repo = api.repo_info(REPOSITORY, repo_type="dataset")
        if (
            repo.private
            or not repo.sha
            or api.list_repo_files(
                REPOSITORY, repo_type="dataset", revision=repo.sha
            )
            != [".gitattributes"]
        ):
            raise ValueError("Destination must be the new public FDA dataset")
        operations, records = preupload_zips(api, hub, client, paths)
        index_paths(client.get(INDEX_URL).raise_for_status().content, contract)
    plan = add_publication_metadata(hub, operations, records, contract, index)
    (output / "plan.json").write_text(plan.model_dump_json(indent=2))
    intent["plan_sha256"] = plan.sha256()
    (output / "intent.json").write_bytes(json_bytes(intent))
    result = api.create_commit(
        REPOSITORY,
        repo_type="dataset",
        parent_commit=repo.sha,
        operations=operations,
        commit_message=f"Archive {BATCH}",
    )
    uploaded = PublicationTransportReceipt(
        plan_sha256=plan.sha256(),
        artifact_sha256=tuple(item.sha256 for item in plan.artifacts),
        target=plan.target,
        state=PublicationTransportState.UPLOADED,
        recorded_at=datetime.now(UTC),
        remote_revision=result.oid,
        allow_identical_content=plan.allow_identical_content,
    )
    (output / "uploaded.json").write_text(uploaded.model_dump_json(indent=2))


def verify(output: Path, exact_commit: str) -> int:
    """Read back the exact published revision with no Hub credentials."""
    require_hosted_main(exact_commit)
    plan = PublicationPlan.model_validate_json(
        (output / "plan.json").read_bytes()
    )
    intent = json.loads((output / "intent.json").read_bytes())
    if (
        plan.target.repository != REPOSITORY
        or intent["commit"] != exact_commit
        or intent["run_id"] != os.environ["GITHUB_RUN_ID"]
        or intent["plan_sha256"] != plan.sha256()
    ):
        raise ValueError("Publication receipts do not match this Actions run")
    uploaded = PublicationTransportReceipt.model_validate_json(
        (output / "uploaded.json").read_bytes()
    )
    verified = verify_publication(
        plan=plan,
        uploaded_receipt=uploaded,
        verifier=HuggingFaceAnonymousArtifactVerifier(timeout_seconds=3600),
        recorded_at=datetime.now(UTC),
    )
    (output / "verified.json").write_text(verified.model_dump_json(indent=2))
    return int(verified.state is not PublicationTransportState.PUBLIC)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("publish", "verify"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exact-commit", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.phase == "verify":
        return verify(args.output, args.exact_commit)
    publish(args.output, args.exact_commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
