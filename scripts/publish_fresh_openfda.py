"""Transfer the approved current openFDA index from GitHub Actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import zipfile
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
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

BATCHES = Path(__file__).resolve().parents[1] / "quality/source-batches"
BATCH_PATTERN = re.compile(r"openfda-([0-9]{8})")
INDEX_URL = "https://api.fda.gov/download.json"
ZIP_ROOT = "https://download.open.fda.gov/"
BATCH_SIZE = 8
CHECKPOINT_SIZE = 128
MAX_ZIP_BYTES = 512 * 1024 * 1024
MAX_REGULAR_BYTES = 256 * 1024 * 1024
SOURCE_TIMEOUT = 90
TRANSIENT_STATUSES = {408, 429, 500, 502, 503, 504}
PROGRESS = "ARCHIVE-PROGRESS.json"
MANIFEST = "ARTIFACT-MANIFEST.json"
INDEX_FILE = "FDA-DOWNLOAD-INDEX.json"
METADATA = {INDEX_FILE, "README.md", "rights.json"}
VERIFIED_TAG = "archive-verified"


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def require_archive_run(exact_commit: str) -> None:
    """Restrict the publisher to the hosted default branch and its two triggers."""
    require_hosted_main(exact_commit, events=("workflow_dispatch", "schedule"))
    if os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise ValueError("openFDA publication requires a GitHub-hosted runner")


def approved_contract(batch: str) -> dict[str, Any]:
    """Load a dated, explicitly approved batch from the workflow commit."""
    parsed = BATCH_PATTERN.fullmatch(batch)
    if parsed is None:
        raise ValueError("openFDA batch must have the form openfda-YYYYMMDD")
    contract = json.loads((BATCHES / batch / "manifest.json").read_bytes())
    scope = {
        "batch_id": batch,
        "repository": f"edithatogo/global-medicines-atlas-{batch}",
        "source_url": INDEX_URL,
        "source_index_date": date.fromisoformat(parsed[1]).isoformat(),
        "excluded_endpoint": "device/udi",
    }
    if (
        contract.get("publication_approved") is not True
        or not contract.get("approval_reference")
        or any(contract.get(key) != value for key, value in scope.items())
        or re.fullmatch(
            r"[0-9a-f]{64}", contract.get("source_index_sha256", "")
        )
        is None
    ):
        raise ValueError("openFDA batch lacks a matching publication approval")
    return contract


def fda_client() -> httpx.Client:
    """Read the index and original ZIPs from FDA over the qualified transport."""
    policy = AcquisitionPolicy(
        allowed_hosts=("api.fda.gov", "download.open.fda.gov"),
        timeout_seconds=SOURCE_TIMEOUT,
    )
    return httpx.Client(
        transport=BoundIPAddressTransport(policy=policy),
        follow_redirects=False,
        timeout=SOURCE_TIMEOUT,
        headers={"Accept-Encoding": "identity"},
    )


def index_paths(index: bytes, contract: dict[str, Any]) -> tuple[str, ...]:
    """Return the unique approved FDA ZIP paths from the pinned index."""
    if hashlib.sha256(index).hexdigest() != contract["source_index_sha256"]:
        raise ValueError("FDA index SHA-256 has changed")
    index_data = json.loads(index)
    domains = index_data["results"]
    if (
        index_data["meta"]["last_updated"] != contract["source_index_date"]
        or sum(map(len, domains.values())) != contract["indexed_endpoints"]
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
    if len(paths) != contract["indexed_payload_count"] or len(paths) != len(
        set(paths)
    ):
        raise ValueError("FDA ZIP paths are incomplete or non-unique")
    excluded_prefix = f"{contract['excluded_endpoint']}/"
    selected = tuple(
        sorted(path for path in paths if not path.startswith(excluded_prefix))
    )
    if (
        len(selected) != contract["expected_payload_count"]
        or len(paths) - len(selected) != contract["excluded_payload_count"]
    ):
        raise ValueError("FDA ZIP paths differ from the approved coverage")
    return selected


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


def source_retry_after(response: httpx.Response) -> float | None:
    """Read the source's retry interval in seconds or as an HTTP date."""
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        value = value.strip()
        if value.isascii() and value.isdecimal():
            return float(int(value))
        retry_at = parsedate_to_datetime(value)
    except TypeError, ValueError, OverflowError:
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())


def fetch_zip(
    client: httpx.Client, path: str, destination: Path
) -> dict[str, Any]:
    """Retry transient, read-only source failures before binding bytes."""
    for read_delay, rate_limit_delay in ((2, 300), (4, 600)):
        try:
            return download_zip(client, path, destination)
        except (httpx.TransportError, httpx.HTTPStatusError) as error:
            delay: float = read_delay
            if isinstance(error, httpx.HTTPStatusError):
                if error.response.status_code not in TRANSIENT_STATUSES:
                    raise
                if error.response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                    delay = (
                        source_retry_after(error.response) or rate_limit_delay
                    )
            print(
                f"Retrying FDA read of {path} in {delay:g} seconds after {error}",
                flush=True,
            )
            time.sleep(delay)
    return download_zip(client, path, destination)


def preupload_zips(
    api: Any,
    hub: Any,
    client: httpx.Client,
    repository: str,
    paths: tuple[str, ...],
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
                repository, additions=additions, repo_type="dataset"
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
        f"The {contract['excluded_payload_count']} ZIPs from "
        f"`{contract['excluded_endpoint']}` are omitted because they contain "
        "separately licensed Global Medical Device Nomenclature data.\n\n"
        "[openFDA downloads](https://open.fda.gov/apis/downloads/) · "
        "[FDA terms](https://open.fda.gov/terms/)\n"
    )
    metadata = {
        INDEX_FILE: index,
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
    metadata[MANIFEST] = manifest
    records.append({
        "path": MANIFEST,
        "sha256": hashlib.sha256(manifest).hexdigest(),
        "size": len(manifest),
    })
    operations.extend(
        hub.CommitOperationAdd(path_in_repo=path, path_or_fileobj=body)
        for path, body in metadata.items()
    )
    return publication_plan(contract, records)


def publication_plan(
    contract: dict[str, Any], records: list[dict[str, Any]]
) -> PublicationPlan:
    """Bind observed path, length and SHA-256 to the approved destination."""
    repository = contract["repository"]
    return PublicationPlan(
        release_version=contract["batch_id"],
        target=PublicationTarget(
            destination=PublicationDestination.HUGGING_FACE,
            repository=repository,
            revision="main",
            public_base_url=f"https://huggingface.co/datasets/{repository}",
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


def public_head(api: Any, repository: str) -> str | None:
    """Read the public default revision, or an as-yet unpublished destination."""
    try:
        info = api.repo_info(repository, repo_type="dataset")
    except import_module("huggingface_hub.errors").RepositoryNotFoundError:
        return None
    if (
        info.private is not False
        or getattr(info, "gated", False)
        or not re.fullmatch(r"[0-9a-f]{40}", info.sha or "")
    ):
        raise ValueError(
            "Destination must be a public FDA dataset at an exact revision"
        )
    return str(info.sha)


def is_verified(api: Any, contract: dict[str, Any], head: str | None) -> bool:
    """Recognize the immutable verified revision without redownloading its ZIPs."""
    verified = contract.get("verified_revision")
    if verified is None and head is not None:
        refs = api.list_repo_refs(contract["repository"], repo_type="dataset")
        verified = next(
            (
                tag.target_commit
                for tag in refs.tags
                if tag.name == VERIFIED_TAG
            ),
            None,
        )
    if verified is not None and verified != head:
        raise ValueError(
            "The public FDA dataset moved away from its verified revision"
        )
    return verified is not None


def index_scope(document: dict[str, Any], excluded_endpoint: str) -> str:
    """Summarize the online candidate without downloading any ZIPs."""
    partitions = {
        f"{domain}/{endpoint}": details["partitions"]
        for domain, endpoints in document["results"].items()
        for endpoint, details in endpoints.items()
    }
    return (
        f"The index lists {sum(map(len, partitions.values()))} ZIPs across "
        f"{len(partitions)} endpoints. The publisher excludes "
        f"{len(partitions.get(excluded_endpoint, ()))} device UDI ZIPs."
    )


def plan_run(output: Path, exact_commit: str, requested: str) -> None:
    """Report the current FDA index and select at most one approved batch."""
    require_archive_run(exact_commit)
    batch = requested or max(
        path.parent.name
        for path in BATCHES.glob("openfda-*/manifest.json")
        if BATCH_PATTERN.fullmatch(path.parent.name)
        and json.loads(path.read_bytes()).get("publication_approved") is True
    )
    contract = approved_contract(batch)
    hub = cast("Any", import_module("huggingface_hub"))
    api = hub.HfApi(token=False)
    repository = contract["repository"]
    head = public_head(api, repository)
    verified = is_verified(api, contract, head)
    with fda_client() as client:
        index = client.get(INDEX_URL).raise_for_status().content
    digest = hashlib.sha256(index).hexdigest()
    document = json.loads(index)
    index_date = date.fromisoformat(document["meta"]["last_updated"])
    matches = digest == contract["source_index_sha256"]
    if not matches:
        (output / "candidate-index.json").write_bytes(index)
    eligible = not verified and (
        matches
        or (
            head is not None
            and MANIFEST
            in api.list_repo_files(
                repository, repo_type="dataset", revision=head
            )
        )
    )
    status = (
        "Already verified"
        if verified
        else "Ready to resume"
        if eligible
        else "Waiting for the approved FDA index"
    )
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open(
        "a", encoding="utf-8"
    ) as summary:
        summary.write(
            f"### openFDA archive\n\nFDA index {index_date}, SHA-256 `{digest}`.\n\n"
        )
        summary.write(f"Approved batch `{batch}`. {status}.\n")
        summary.write(
            f"\n{index_scope(document, contract['excluded_endpoint'])}\n"
        )
        if not matches:
            summary.write(
                "\nThe current index differs from this approval and is retained for review.\n"
            )
    with Path(os.environ["GITHUB_OUTPUT"]).open(
        "a", encoding="utf-8"
    ) as outputs:
        outputs.write(f"batch={batch}\neligible={str(eligible).lower()}\n")


def archived_bytes(
    hub: Any, repository: str, revision: str, path: str
) -> bytes:
    """Read small publication metadata anonymously at a fixed Hub revision."""
    return Path(
        hub.hf_hub_download(
            repo_id=repository,
            filename=path,
            revision=revision,
            repo_type="dataset",
            token=False,
        )
    ).read_bytes()


def recover_plan(
    hub: Any, contract: dict[str, Any], head: str, files: set[str]
) -> PublicationPlan:
    """Recover the final inventory for verification without fetching from FDA."""
    repository = contract["repository"]
    index = archived_bytes(hub, repository, head, INDEX_FILE)
    expected = set(index_paths(index, contract)) | METADATA | {MANIFEST}
    body = archived_bytes(hub, repository, head, MANIFEST)
    document = json.loads(body)
    if any(
        document[key] != contract[key]
        for key in ("batch_id", "repository", "rights", "source_index_sha256")
    ):
        raise ValueError(
            "Published manifest differs from the approved FDA batch"
        )
    records = [
        *document["artifacts"],
        {
            "path": MANIFEST,
            "size": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        },
    ]
    plan = publication_plan(contract, records)
    if {
        item.relative_path for item in plan.artifacts
    } != expected or files != expected:
        raise ValueError(
            "Published FDA inventory differs from the approved index"
        )
    return plan


def checkpoint_records(
    api: Any,
    hub: Any,
    contract: dict[str, Any],
    head: str,
    paths: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Check an interrupted upload's committed path, size and digest inventory."""
    repository = contract["repository"]
    repo_file = import_module("huggingface_hub.hf_api").RepoFile
    entries = {
        entry.path: entry
        for entry in api.list_repo_tree(
            repository, repo_type="dataset", revision=head, recursive=True
        )
        if isinstance(entry, repo_file) and entry.path != ".gitattributes"
    }
    if not entries:
        return []
    if entries.pop(PROGRESS, None) is None:
        raise ValueError("The FDA destination has files without a checkpoint")
    progress = json.loads(archived_bytes(hub, repository, head, PROGRESS))
    records = progress["artifacts"]
    plan = publication_plan(contract, records)
    if (
        progress["source_index_sha256"] != contract["source_index_sha256"]
        or {item.relative_path for item in plan.artifacts} != entries.keys()
        or not entries.keys() <= set(paths)
    ):
        raise ValueError(
            "The FDA checkpoint differs from its approved inventory"
        )
    verifier = HuggingFaceAnonymousArtifactVerifier()
    for item in plan.artifacts:
        entry = entries[item.relative_path]
        if entry.size != item.size:
            raise ValueError(
                f"FDA checkpoint size differs for {item.relative_path}"
            )
        if entry.lfs is None:
            verifier.verify_artifact(
                target=plan.target, revision=head, artifact=item
            )
        elif (entry.lfs.sha256, entry.lfs.size) != (item.sha256, item.size):
            raise ValueError(
                f"FDA checkpoint checksum differs for {item.relative_path}"
            )
    return records


def commit_batch(
    api: Any, repository: str, head: str, operations: list[Any], message: str
) -> str:
    """Append to the inspected Hub revision with server-side parent protection."""
    result = api.create_commit(
        repository,
        repo_type="dataset",
        parent_commit=head,
        operations=operations,
        commit_message=message,
    )
    revision = str(result.oid)
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError(
            "Hugging Face did not return an immutable FDA revision"
        )
    return revision


def upload_remaining(
    api: Any, hub: Any, contract: dict[str, Any], head: str | None
) -> tuple[PublicationPlan, str]:
    """Commit small groups and retain their checkpoints on Hugging Face."""
    repository = contract["repository"]
    with fda_client() as client:
        index = client.get(INDEX_URL).raise_for_status().content
        paths = index_paths(index, contract)
        if head is None:
            api.create_repo(
                repository, repo_type="dataset", private=False, exist_ok=True
            )
            head = public_head(hub.HfApi(token=False), repository)
            if head is None:
                raise ValueError(
                    "The new FDA dataset is not yet publicly readable"
                )
        records = checkpoint_records(
            hub.HfApi(token=False), hub, contract, head, paths
        )
        existing = {record["path"] for record in records}
        for group in batched(
            (path for path in paths if path not in existing),
            CHECKPOINT_SIZE,
            strict=False,
        ):
            operations, additions = preupload_zips(
                api, hub, client, repository, group
            )
            index_paths(
                client.get(INDEX_URL).raise_for_status().content, contract
            )
            records.extend(additions)
            operations.append(
                hub.CommitOperationAdd(
                    path_in_repo=PROGRESS,
                    path_or_fileobj=json_bytes({
                        "source_index_sha256": contract["source_index_sha256"],
                        "rights": contract["rights"],
                        "artifacts": records,
                    }),
                )
            )
            head = commit_batch(
                api,
                repository,
                head,
                operations,
                f"Archive {len(records)}/{len(paths)} FDA ZIPs",
            )
            print(
                f"Archived {len(records)}/{len(paths)} FDA ZIPs at {head}",
                flush=True,
            )
        index_paths(client.get(INDEX_URL).raise_for_status().content, contract)
    final_operations = [hub.CommitOperationDelete(path_in_repo=PROGRESS)]
    plan = add_publication_metadata(
        hub, final_operations, records, contract, index
    )
    revision = commit_batch(
        api,
        repository,
        head,
        final_operations,
        f"Complete {plan.release_version}",
    )
    return plan, revision


def publish(output: Path, exact_commit: str, batch: str) -> None:
    """Resume an approved upload or rebuild the receipt for an uploaded batch."""
    require_archive_run(exact_commit)
    if not authorization_from_environment(
        dict(os.environ)
    ).permits_external_write:
        raise PermissionError("Fresh FDA snapshot publication is not approved")
    contract = approved_contract(batch)
    repository = contract["repository"]
    hub = cast("Any", import_module("huggingface_hub"))
    reader = hub.HfApi(token=False)
    head = public_head(reader, repository)
    if is_verified(reader, contract, head):
        return
    intent = {
        "commit": exact_commit,
        "run_id": os.environ["GITHUB_RUN_ID"],
        "repository": repository,
        "source_index_sha256": contract["source_index_sha256"],
    }
    (output / "source-intent.json").write_bytes(json_bytes(intent))
    files: set[str] = (
        set()
        if head is None
        else set(
            reader.list_repo_files(
                repository, repo_type="dataset", revision=head
            )
        )
        - {".gitattributes"}
    )
    if head is not None and MANIFEST in files:
        plan, revision = recover_plan(hub, contract, head, files), head
    else:
        api = hub.HfApi(token=os.environ["HF_TOKEN"])
        plan, revision = upload_remaining(api, hub, contract, head)
    (output / "plan.json").write_text(plan.model_dump_json(indent=2))
    intent["plan_sha256"] = plan.sha256()
    (output / "intent.json").write_bytes(json_bytes(intent))
    uploaded = PublicationTransportReceipt(
        plan_sha256=plan.sha256(),
        artifact_sha256=tuple(item.sha256 for item in plan.artifacts),
        target=plan.target,
        state=PublicationTransportState.UPLOADED,
        recorded_at=datetime.now(UTC),
        remote_revision=revision,
        allow_identical_content=plan.allow_identical_content,
    )
    (output / "uploaded.json").write_text(uploaded.model_dump_json(indent=2))


def verify(output: Path, exact_commit: str, batch: str) -> int:
    """Read back the exact published revision with no Hub credentials."""
    require_archive_run(exact_commit)
    contract = approved_contract(batch)
    plan = PublicationPlan.model_validate_json(
        (output / "plan.json").read_bytes()
    )
    intent = json.loads((output / "intent.json").read_bytes())
    if (
        plan.target.repository != contract["repository"]
        or intent["commit"] != exact_commit
        or intent["run_id"] != os.environ["GITHUB_RUN_ID"]
        or intent["plan_sha256"] != plan.sha256()
        or intent["source_index_sha256"] != contract["source_index_sha256"]
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


def mark_verified(output: Path, exact_commit: str, batch: str) -> None:
    """Keep the verified commit discoverable by future scheduled runs."""
    require_archive_run(exact_commit)
    if not authorization_from_environment(
        dict(os.environ)
    ).permits_external_write:
        raise PermissionError("Fresh FDA snapshot publication is not approved")
    contract = approved_contract(batch)
    receipt = PublicationTransportReceipt.model_validate_json(
        (output / "verified.json").read_bytes()
    )
    repository = contract["repository"]
    plan = PublicationPlan.model_validate_json(
        (output / "plan.json").read_bytes()
    )
    if (
        receipt.state is not PublicationTransportState.PUBLIC
        or receipt.target != plan.target
        or receipt.target.repository != repository
        or receipt.plan_sha256 != plan.sha256()
    ):
        raise ValueError(
            "A matching anonymous FDA verification receipt is required"
        )
    hub = cast("Any", import_module("huggingface_hub"))
    api = hub.HfApi(token=os.environ["HF_TOKEN"])
    reader = hub.HfApi(token=False)
    head = public_head(reader, repository)
    if head is None or head != receipt.remote_revision:
        raise ValueError(
            "Hugging Face moved before the verified revision could be marked"
        )
    api.create_tag(
        repository,
        repo_type="dataset",
        tag=VERIFIED_TAG,
        revision=head,
        exist_ok=True,
    )
    if not is_verified(reader, contract, head):
        raise ValueError("The verified FDA archive tag could not be read back")
    print(
        f"Verified {len(receipt.verified_artifacts)} artifacts at {receipt.verification_uri}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase", choices=("plan", "publish", "verify", "mark-verified")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--batch", default="")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.phase == "plan":
        plan_run(args.output, args.exact_commit, args.batch)
    elif args.phase == "verify":
        return verify(args.output, args.exact_commit, args.batch)
    elif args.phase == "mark-verified":
        mark_verified(args.output, args.exact_commit, args.batch)
    else:
        publish(args.output, args.exact_commit, args.batch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
