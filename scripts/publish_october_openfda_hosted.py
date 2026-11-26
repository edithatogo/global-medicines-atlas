"""Publish and verify the approved October openFDA archive from Actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- bare Git reads at the frozen public revision.
import sys
import time
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http import HTTPStatus
from importlib import import_module
from ipaddress import IPv4Address, IPv4Network
from itertools import chain
from operator import attrgetter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, BinaryIO, NamedTuple, cast
from urllib.parse import quote, urlsplit

import httpx
from scripts.publish_bulk_archive import (
    CARD_NAME,
    MANIFEST_NAME,
    artifact_manifest_bytes,
    build_card,
)
from scripts.publish_fresh_openfda import source_retry_after

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
    DestinationPolicyError,
)
from global_medicines_atlas.data_layer_archive import (
    AnonymousReadbackHTTPError,
    AnonymousReadbackTimeoutError,
    HuggingFaceAnonymousArtifactVerifier,
)
from global_medicines_atlas.federation_metadata_hosted import (
    require_hosted_main,
)
from global_medicines_atlas.publication_transport import (
    ArtifactBinding,
    ArtifactVerification,
    PublicationDestination,
    PublicationPlan,
    PublicationTarget,
    PublicationTransportReceipt,
    PublicationTransportState,
    authorization_from_environment,
    verify_publication,
)

BATCH = "openfda-all-20261030"
REPOSITORY = f"edithatogo/global-medicines-atlas-{BATCH}"
MANIFEST = ArtifactBinding(
    relative_path="ARTIFACT-MANIFEST.json",
    sha256="e5944a52ffc93121fd11d182fcafd70aedd7f43cc8806801eaf0dc80a22933a6",
    size=872268,
)
PLAN_SHA256 = "1c63f597717bcbcb4753a644f7e7d07387e6f9cac9740833fb7c915ad1456ed0"
FDA_ZIP_ORIGIN = "https://download.open.fda.gov/"
ONLINE_SOURCES = (
    Path(__file__).resolve().parents[1]
    / "quality/source-batches"
    / BATCH
    / "online-sources.json"
)
COMPLETION_PATHS = frozenset({CARD_NAME, MANIFEST_NAME})
WAYBACK_CAPTURES = {
    "other/historicaldocument/other-historicaldocument-0001-of-0001.json.zip": (
        "20260501030408",
        "20250629204308",
        "20250602082201",
    ),
}
SOURCE_PORT = 18043
TAILSCALE_IPV4 = IPv4Network("100.64.0.0/10")
COMMIT_BYTES = 512 * 1024**2
COMMIT_FILES = 4
SOURCE_REQUEST_BYTES = 1024**2
SOURCE_CONNECTIONS = 8
SOURCE_REQUEST_SECONDS = 150
PUBLICATION_CHECKPOINT_SECONDS = 4 * 60 * 60 + 40 * 60
MAX_READBACK_WAIT_SECONDS = 600
TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}


class BatchResult(NamedTuple):
    """A complete publication or a resumable, committed checkpoint."""

    revision: str
    complete: bool
    newly_committed: int


class CheckpointDeadlineError(Exception):
    """Stop an unfinished source read before the hosted job expires."""


class TransientOctoberError(RuntimeError):
    """An interrupted operation can resume from the pinned public inventory."""


def transient_reason(error: Exception) -> str | None:
    """Classify temporary transport failures without logging URLs or tokens."""
    if isinstance(error, TransientOctoberError):
        return str(error)
    if isinstance(error, socket.gaierror) and error.errno == socket.EAI_AGAIN:
        return "temporary DNS failure"
    # HTTPX and the optional Hub SDK's Requests client both expose this status.
    status = getattr(getattr(error, "response", None), "status_code", None)
    if isinstance(status, int):
        return f"HTTP {status}" if status in TRANSIENT_STATUS else None
    if isinstance(
        error,
        (
            httpx.NetworkError,
            httpx.TimeoutException,
            httpx.RemoteProtocolError,
            AnonymousReadbackTimeoutError,
            TimeoutError,
        ),
    ):
        return type(error).__name__
    requests_errors = sys.modules.get("requests.exceptions")
    if (
        requests_errors is not None
        and isinstance(
            error,
            (
                requests_errors.Timeout,
                requests_errors.ConnectionError,
                requests_errors.ChunkedEncodingError,
            ),
        )
        and not isinstance(error, requests_errors.SSLError)
    ):
        return type(error).__name__
    return None


def source_origin(value: str) -> str:
    """Accept only the dedicated port at a literal private Tailscale address."""
    try:
        parsed = urlsplit(value)
        address = IPv4Address(parsed.hostname or "")
        port = parsed.port
    except ValueError:
        raise ValueError(
            "October source must use its private Tailscale port"
        ) from None
    if (
        (parsed.scheme, port) != ("http", SOURCE_PORT)
        or parsed.path not in {"", "/"}
        or any((
            parsed.username is not None,
            parsed.password is not None,
            parsed.query,
            parsed.fragment,
        ))
        or address not in TAILSCALE_IPV4
    ):
        raise ValueError("October source must use its private Tailscale port")
    return f"http://{address}:{SOURCE_PORT}/"


def archive_plan(manifest: bytes) -> PublicationPlan:
    """Rebuild the exact publication plan retained by the October run."""
    if (len(manifest), hashlib.sha256(manifest).hexdigest()) != (
        MANIFEST.size,
        MANIFEST.sha256,
    ):
        raise ValueError("October manifest differs from the approved archive")
    document = json.loads(manifest)
    artifacts = [MANIFEST]
    artifacts.extend(
        ArtifactBinding(
            relative_path=item["path"], sha256=item["sha256"], size=item["size"]
        )
        for item in document["artifacts"]
    )
    plan = PublicationPlan(
        release_version=BATCH,
        target=PublicationTarget(
            destination=PublicationDestination.HUGGING_FACE,
            repository=REPOSITORY,
            revision="main",
            public_base_url=f"https://huggingface.co/datasets/{REPOSITORY}",
        ),
        artifacts=tuple(sorted(artifacts, key=attrgetter("relative_path"))),
    )
    if plan.sha256() != PLAN_SHA256:
        raise ValueError(
            "October publication plan differs from the saved receipt"
        )
    return plan


def download_range_once(
    client: httpx.Client,
    artifact: ArtifactBinding,
    stream: BinaryIO,
    start: int,
    end: int,
    *,
    publication_deadline: float | None = None,
) -> None:
    """Read a source range into its exact position in the staging file."""
    path = quote(artifact.relative_path, safe="/")
    ranged = (start, end) != (0, artifact.size)
    expected_status = HTTPStatus.PARTIAL_CONTENT if ranged else HTTPStatus.OK
    headers = {"Range": f"bytes={start}-{end - 1}"} if ranged else {}
    request_deadline = time.monotonic() + SOURCE_REQUEST_SECONDS
    position = stream.seek(start)
    with client.stream("GET", path, headers=headers) as response:
        response.raise_for_status()
        if response.status_code != expected_status or (
            ranged
            and response.headers.get("Content-Range")
            != f"bytes {start}-{end - 1}/{artifact.size}"
        ):
            raise ValueError(
                f"October source range differs: {artifact.relative_path}"
            )
        for chunk in response.iter_raw():
            now = time.monotonic()
            if publication_deadline is not None and now >= publication_deadline:
                raise CheckpointDeadlineError
            if now > request_deadline:
                raise httpx.ReadTimeout("October source request timed out")
            position += len(chunk)
            if position > end:
                raise ValueError(
                    f"October source sent excess bytes: {artifact.relative_path}"
                )
            stream.write(chunk)
    if position != end:
        raise httpx.ReadError(
            f"Incomplete October source file: {artifact.relative_path}"
        )


def download_artifact(
    client: httpx.Client,
    artifact: ArtifactBinding,
    output: Path,
    *,
    publication_deadline: float | None = None,
) -> None:
    """Retry interrupted ranges and verify the assembled file SHA-256."""
    with output.open("wb") as stream:
        stream.truncate(artifact.size)

    def read_range(start: int) -> None:
        end = min(start + SOURCE_REQUEST_BYTES, artifact.size)
        with output.open("r+b") as stream:
            for wait in (2, 4, 0):
                if (
                    publication_deadline is not None
                    and time.monotonic() >= publication_deadline
                ):
                    raise CheckpointDeadlineError
                try:
                    download_range_once(
                        client,
                        artifact,
                        stream,
                        start,
                        end,
                        publication_deadline=publication_deadline,
                    )
                except httpx.HTTPError as error:
                    reason = transient_reason(error)
                    if (
                        reason is not None
                        and publication_deadline is not None
                        and time.monotonic() >= publication_deadline
                    ):
                        raise CheckpointDeadlineError from error
                    if reason is None:
                        detail = (
                            f"HTTP {error.response.status_code}"
                            if isinstance(error, httpx.HTTPStatusError)
                            else type(error).__name__
                        )
                        raise ValueError(
                            f"October source read failed: {artifact.relative_path} "
                            f"at byte {start} ({detail})"
                        ) from None
                    if not wait:
                        raise TransientOctoberError(
                            f"October source {artifact.relative_path} at byte {start}: {reason}"
                        ) from None
                    time.sleep(wait)
                else:
                    break

    starts = range(0, max(artifact.size, 1), SOURCE_REQUEST_BYTES)
    with ThreadPoolExecutor(max_workers=SOURCE_CONNECTIONS) as executor:
        for _ in executor.map(
            read_range, starts, buffersize=SOURCE_CONNECTIONS
        ):
            pass
    with output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != artifact.sha256:
        raise ValueError(
            f"October source checksum differs: {artifact.relative_path}"
        )


def commit_groups(
    artifacts: Iterable[ArtifactBinding],
) -> Iterator[tuple[ArtifactBinding, ...]]:
    """Keep each upload within both the runner's disk and Hub commit limits."""
    group: list[ArtifactBinding] = []
    size = 0
    for artifact in artifacts:
        if artifact.size > COMMIT_BYTES:
            raise ValueError(
                f"October source file exceeds the batch limit: {artifact.relative_path}"
            )
        if len(group) == COMMIT_FILES or size + artifact.size > COMMIT_BYTES:
            yield tuple(group)
            group = []
            size = 0
        group.append(artifact)
        size += artifact.size
    if group:
        yield tuple(group)


def publication_order(artifact: ArtifactBinding) -> tuple[int, str]:
    """Publish rights before payloads and the complete archive manifest last."""
    path = artifact.relative_path
    if path == "rights.json":
        return 0, path
    if path in COMPLETION_PATHS:
        return 2, path
    return 1, path


def public_revision(api: Any) -> str:
    """Pin the existing public dataset before reading inventory."""
    info = api.repo_info(REPOSITORY, repo_type="dataset", revision="main")
    head = str(info.sha)
    if info.private is not False or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError(
            "October destination must be the existing public dataset"
        )
    return head


def remaining_artifacts(
    api: Any, hub: Any, plan: PublicationPlan
) -> tuple[str, list[ArtifactBinding]]:
    """Resume only from a Hub revision containing approved, matching files."""
    head = public_revision(api)
    remaining = {
        artifact.relative_path: artifact for artifact in plan.artifacts
    }
    git_files: list[ArtifactBinding] = []
    entries: Iterable[Any] = api.list_repo_tree(
        REPOSITORY, repo_type="dataset", revision=head, recursive=True
    )
    for entry in entries:
        if (
            not isinstance(entry, hub.RepoFile)
            or entry.path == ".gitattributes"
        ):
            continue
        artifact = remaining.pop(entry.path, None)
        if artifact is None or entry.size != artifact.size:
            raise ValueError(
                f"Unexpected October destination file: {entry.path}"
            )
        if entry.lfs is None:
            git_files.append(artifact)
        elif (entry.lfs.sha256, entry.lfs.size) != (
            artifact.sha256,
            artifact.size,
        ):
            raise ValueError(
                f"October destination checksum differs: {entry.path}"
            )
    if git_files:
        verify_git_checkpoint(plan.target, head, git_files)
    return head, sorted(remaining.values(), key=publication_order)


def verify_git_checkpoint(
    target: PublicationTarget, revision: str, files: list[ArtifactBinding]
) -> None:
    """Fetch ordinary Git blobs once. A bare fetch never downloads LFS payloads."""
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("Git is required to read the October checkpoint")
    with TemporaryDirectory(prefix="october-git-") as directory:

        def git(*arguments: str) -> bytes:
            return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] -- fixed Git commands, frozen paths, no shell.
                [
                    executable,
                    "-c",
                    "credential.helper=",
                    "-c",
                    "http.followRedirects=false",
                    *arguments,
                ],
                cwd=directory,
                check=True,
                capture_output=True,
                timeout=120,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            ).stdout

        git("init", "--bare", "--quiet")
        try:
            git(
                "fetch",
                "--quiet",
                "--no-tags",
                "--depth=1",
                target.public_base_url,
                revision,
            )
        except subprocess.CalledProcessError, subprocess.TimeoutExpired:
            print(
                "Git checkpoint unavailable; checking the same public revision over HTTPS.",
                flush=True,
            )
            verifier = OctoberReadback(timeout_seconds=120)
            for artifact in files:
                verifier.verify_artifact(
                    target=target, revision=revision, artifact=artifact
                )
            return
        for artifact in files:
            body = git(
                "cat-file", "blob", f"{revision}:{artifact.relative_path}"
            )
            if (len(body), hashlib.sha256(body).hexdigest()) != (
                artifact.size,
                artifact.sha256,
            ):
                raise ValueError(
                    f"October destination checksum differs: {artifact.relative_path}"
                )


def check_fda_zip(
    client: httpx.Client,
    artifact: ArtifactBinding,
    destination: Path,
    url: str,
    *,
    check_head: bool = True,
) -> dict[str, str | int]:
    """Compare a candidate in runner scratch space to its frozen binding."""
    if check_head:
        header = client.head(url)
        length = header.headers.get("Content-Length")
        if (
            header.status_code != HTTPStatus.OK
            or length is None
            or not length.isdecimal()
        ):
            return {
                "status": "unavailable",
                "http_status": header.status_code,
                "reason": "HEAD did not provide a usable length",
            }
        if (size := int(length)) != artifact.size:
            return {"status": "size_mismatch", "bytes": size}
    size = 0
    digest = hashlib.sha256()
    with (
        client.stream("GET", url) as response,
        destination.open("wb") as stream,
    ):
        if response.status_code != HTTPStatus.OK:
            return {
                "status": "unavailable",
                "http_status": response.status_code,
            }
        for block in response.iter_raw():
            size += len(block)
            if size > artifact.size:
                return {"status": "size_mismatch", "bytes_at_least": size}
            digest.update(block)
            stream.write(block)
    if size != artifact.size:
        return {"status": "size_mismatch", "bytes": size}
    sha256 = digest.hexdigest()
    status = "match" if sha256 == artifact.sha256 else "digest_mismatch"
    return {"status": status, "bytes": size, "sha256": sha256}


def probe_online_zip(
    client: httpx.Client,
    artifact: ArtifactBinding,
    destination: Path,
    url: str,
    *,
    check_head: bool = True,
) -> dict[str, str | int]:
    """Record the exact public source and transport outcome for the candidate."""
    result: dict[str, str | int]
    try:
        result = check_fda_zip(
            client, artifact, destination, url, check_head=check_head
        )
    except (httpx.TransportError, DestinationPolicyError) as error:
        result = {"status": "unavailable", "reason": type(error).__name__}
    return result | {"source_url": url}


def reviewed_sources(path: Path, plan: PublicationPlan) -> dict[str, str]:
    """Accept direct public HTTPS URLs only for files in the frozen plan."""
    document = json.loads(path.read_bytes())
    planned = {artifact.relative_path for artifact in plan.artifacts}
    if not isinstance(document, dict):
        raise TypeError("October online sources must map archive paths to URLs")
    sources: dict[str, str] = {}
    for target, url in cast("dict[str, object]", document).items():
        if (
            target not in planned
            or not isinstance(url, str)
            or not re.fullmatch(
                r"https://[a-zA-Z0-9.-]+(?::443)?/[^\s?#\\]+", url
            )
        ):
            raise ValueError(
                "October online source is outside the frozen plan or is not direct HTTPS"
            )
        sources[target] = url
    return sources


def rebuild_completion_metadata(plan: PublicationPlan) -> dict[str, bytes]:
    """Reproduce the final card and manifest from committed October evidence."""
    contract = json.loads(
        ONLINE_SOURCES.with_name("manifest.json").read_bytes()
    )
    artifacts: list[dict[str, Any]] = [
        {
            "path": artifact.relative_path,
            "size": artifact.size,
            "sha256": artifact.sha256,
        }
        for artifact in plan.artifacts
        if artifact.relative_path != MANIFEST_NAME
    ]
    return {
        CARD_NAME: build_card(contract).encode(),
        MANIFEST_NAME: artifact_manifest_bytes(contract, artifacts),
    }


def check_online_groups(
    client: httpx.Client,
    missing: Iterable[ArtifactBinding],
    sources: Mapping[str, str],
    prepared: Mapping[str, bytes] | None = None,
) -> Iterator[
    tuple[dict[str, dict[str, str | int]], list[tuple[ArtifactBinding, Path]]]
]:
    """Stage a bounded group and yield only exact bytes for possible upload."""
    prepared = prepared or {}
    for group in commit_groups(missing):
        with TemporaryDirectory(prefix="openfda-october-online-") as scratch:
            results: dict[str, dict[str, str | int]] = {}
            matched: list[tuple[ArtifactBinding, Path]] = []
            for index, artifact in enumerate(group):
                destination = Path(scratch) / str(index)
                if (body := prepared.get(artifact.relative_path)) is not None:
                    sha256 = hashlib.sha256(body).hexdigest()
                    if (len(body), sha256) == (artifact.size, artifact.sha256):
                        destination.write_bytes(body)
                        matched.append((artifact, destination))
                        results[artifact.relative_path] = {
                            "status": "match",
                            "bytes": len(body),
                            "sha256": sha256,
                            "source": "committed October plan and publication contract",
                        }
                        continue
                path = quote(artifact.relative_path, safe="/")
                url = FDA_ZIP_ORIGIN + path
                reviewed = sources.get(artifact.relative_path)
                candidates = [(reviewed, False)] if reviewed else []
                if artifact.relative_path.endswith(".json.zip"):
                    candidates.append((url, True))
                    candidates.extend(
                        (f"https://web.archive.org/web/{stamp}id_/{url}", True)
                        for stamp in WAYBACK_CAPTURES.get(
                            artifact.relative_path, ()
                        )
                    )
                result: dict[str, str | int] = {"status": "unavailable"}
                for candidate, check_head in candidates:
                    result = probe_online_zip(
                        client,
                        artifact,
                        destination,
                        candidate,
                        check_head=check_head,
                    )
                    if result["status"] == "match":
                        break
                results[artifact.relative_path] = result
                if result["status"] == "match":
                    matched.append((artifact, destination))
            yield results, matched


def commit_artifacts(
    api: Any, hub: Any, head: str, files: list[tuple[ArtifactBinding, Path]]
) -> str:
    """Append approved files while holding the observed destination revision."""
    operations = [
        hub.CommitOperationAdd(
            path_in_repo=artifact.relative_path, path_or_fileobj=source
        )
        for artifact, source in files
    ]
    try:
        result = api.create_commit(
            REPOSITORY,
            repo_type="dataset",
            revision="main",
            parent_commit=head,
            operations=operations,
            commit_message=f"Archive {len(files)} verified October openFDA files",
        )
    except Exception as error:
        # The Hub may have accepted the commit before its response was lost.
        # A new attempt must reconcile the public tree before any further write.
        cause: BaseException | None = error
        while isinstance(cause, Exception):
            if (reason := transient_reason(cause)) is not None:
                raise TransientOctoberError(
                    f"October batch commit outcome requires reconciliation: {reason}"
                ) from None
            cause = cause.__cause__
        raise
    revision = str(result.oid)
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError(
            "Hugging Face did not return an immutable October revision"
        )
    return revision


def recover_online(
    output: Path, exact_commit: str, *, publish_matches: bool
) -> None:
    """Check FDA copies and optionally append verified bytes under the existing approval."""
    if (
        publish_matches
        and not authorization_from_environment(
            dict(os.environ)
        ).permits_external_write
    ):
        raise PermissionError("October archive publication requires approval")
    plan = PublicationPlan.model_validate_json(
        (output / "plan.json").read_bytes()
    )
    if plan.sha256() != PLAN_SHA256:
        raise ValueError("October plan differs from the approved inventory")
    sources = reviewed_sources(ONLINE_SOURCES, plan)
    hub = cast("Any", import_module("huggingface_hub.hf_api"))
    head, missing = remaining_artifacts(hub.HfApi(token=False), hub, plan)
    writer = (
        hub.HfApi(token=os.environ["HF_TOKEN"]) if publish_matches else None
    )
    record_intent(output, plan, exact_commit)
    final_revision = recover_fda_zips(
        output / "online.json",
        plan,
        head,
        missing,
        writer,
        hub,
        exact_commit,
        sources=sources,
        prepared=rebuild_completion_metadata(plan),
    )
    if writer is not None and set(
        writer.list_repo_files(
            REPOSITORY, repo_type="dataset", revision=final_revision
        )
    ) == {".gitattributes"} | {
        artifact.relative_path for artifact in plan.artifacts
    }:
        record_upload(output, plan, final_revision)


def recover_fda_zips(
    report_path: Path,
    plan: PublicationPlan,
    head: str,
    missing: list[ArtifactBinding],
    writer: Any,
    hub: Any,
    exact_commit: str,
    *,
    sources: Mapping[str, str] | None = None,
    prepared: Mapping[str, bytes] | None = None,
) -> str:
    """Save the observed availability and the anonymous readback of each appended batch."""
    mirrors = sources or {}
    prepared = prepared or {}
    candidates = [
        artifact
        for artifact in missing
        if artifact.relative_path.endswith(".json.zip")
        or artifact.relative_path in mirrors
        or artifact.relative_path in prepared
    ]
    pending = {artifact.relative_path for artifact in missing}
    print(
        f"Checking {len(candidates)} October recovery candidates",
        flush=True,
    )
    results: dict[str, dict[str, str | int]] = {}
    sidecars: dict[str, dict[str, str | int]] = {}
    batches: list[dict[str, object]] = []
    report: dict[str, object] = {
        "commit": exact_commit,
        "run_id": os.environ["GITHUB_RUN_ID"],
        "plan_sha256": PLAN_SHA256,
        "public_revision": head,
        "public_paths": len(plan.artifacts) - len(missing),
        "missing_metadata": [
            artifact.relative_path
            for artifact in missing
            if not artifact.relative_path.endswith(".json.zip")
        ],
        "zip_results": results,
        "metadata_results": sidecars,
        "published_batches": batches,
    }
    verifier = OctoberReadback(timeout_seconds=120)
    policy = AcquisitionPolicy(
        allowed_hosts=(
            "download.open.fda.gov",
            "web.archive.org",
            *(urlsplit(url).hostname or "" for url in mirrors.values()),
        )
    )
    with httpx.Client(
        base_url=FDA_ZIP_ORIGIN,
        transport=BoundIPAddressTransport(policy=policy),
        headers={"Accept-Encoding": "identity"},
        follow_redirects=False,
        trust_env=False,
        timeout=30,
    ) as client:
        for checked, matched in chain(
            check_online_groups(
                client,
                (
                    item
                    for item in candidates
                    if item.relative_path not in COMPLETION_PATHS
                ),
                mirrors,
            ),
            check_online_groups(
                client,
                (
                    item
                    for item in candidates
                    if item.relative_path in COMPLETION_PATHS
                ),
                mirrors,
                prepared,
            ),
        ):
            for path, result in checked.items():
                (results if path.endswith(".json.zip") else sidecars)[path] = (
                    result
                )
            if (
                checked.keys() <= COMPLETION_PATHS
                and pending - COMPLETION_PATHS
            ):
                continue
            if writer is not None and matched:
                head = commit_artifacts(writer, hub, head, matched)
                batch: dict[str, object] = {
                    "revision": head,
                    "paths": [
                        artifact.relative_path for artifact, _ in matched
                    ],
                }
                batches.append(batch)
                report_path.write_text(
                    json.dumps(report, indent=2) + "\n", encoding="utf-8"
                )
                batch["verified"] = [
                    verifier.verify_artifact(
                        target=plan.target, revision=head, artifact=artifact
                    ).model_dump(mode="json")
                    for artifact, _ in matched
                ]
                pending.difference_update(
                    artifact.relative_path for artifact, _ in matched
                )
                report_path.write_text(
                    json.dumps(report, indent=2) + "\n", encoding="utf-8"
                )
                print(
                    f"Verified {len(matched)} October files at {head}",
                    flush=True,
                )
    counts = Counter(result["status"] for result in results.values())
    report["zip_counts"] = counts
    report["missing_metadata"] = [
        artifact.relative_path
        for artifact in missing
        if not artifact.relative_path.endswith(".json.zip")
        and artifact.relative_path in pending
    ]
    report["completion_metadata_held"] = sorted(
        path
        for path, result in sidecars.items()
        if path in COMPLETION_PATHS
        and result["status"] == "match"
        and pending - COMPLETION_PATHS
    )
    report["resulting_revision"] = head
    report["recorded_at"] = datetime.now(UTC).isoformat()
    report_path.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(f"October FDA ZIP results {dict(counts)}", flush=True)
    return head


def publish_batches(
    api: Any,
    hub: Any,
    client: httpx.Client,
    plan: PublicationPlan,
    *,
    prepared: Mapping[str, bytes] | None = None,
    deadline: float | None = None,
) -> BatchResult:
    """Upload and commit verified batches, leaving durable resume points."""
    prepared = prepared or {}
    head, remaining = remaining_artifacts(api, hub, plan)
    count = len(plan.artifacts) - len(remaining)
    initial_count = count

    def checkpoint() -> BatchResult:
        if count == initial_count:
            raise TimeoutError(
                "October publication made no checkpoint progress"
            )
        return BatchResult(
            revision=head,
            complete=False,
            newly_committed=count - initial_count,
        )

    def commit_group(group: tuple[ArtifactBinding, ...]) -> str:
        with TemporaryDirectory(prefix="openfda-october-") as scratch:
            sources = [
                Path(scratch) / str(position) for position in range(len(group))
            ]
            for artifact, source in zip(group, sources, strict=True):
                body = prepared.get(artifact.relative_path)
                if body is None:
                    download_artifact(
                        client,
                        artifact,
                        source,
                        publication_deadline=deadline,
                    )
                    continue
                if (len(body), hashlib.sha256(body).hexdigest()) != (
                    artifact.size,
                    artifact.sha256,
                ):
                    raise ValueError(
                        f"October rebuilt file differs: {artifact.relative_path}"
                    )
                source.write_bytes(body)
            return commit_artifacts(
                api, hub, head, list(zip(group, sources, strict=True))
            )

    for group in commit_groups(remaining):
        if deadline is not None and time.monotonic() >= deadline:
            return checkpoint()
        try:
            head = commit_group(group)
        except CheckpointDeadlineError:
            return checkpoint()
        count += len(group)
        print(
            f"Committed {count}/{len(plan.artifacts)} October files", flush=True
        )
    final_paths = set(
        api.list_repo_files(REPOSITORY, repo_type="dataset", revision=head)
    )
    if final_paths != {".gitattributes"} | {
        artifact.relative_path for artifact in plan.artifacts
    }:
        raise ValueError(
            "Final October revision does not match the archive inventory"
        )
    return BatchResult(
        revision=head, complete=True, newly_committed=count - initial_count
    )


def publish(output: Path, exact_commit: str) -> None:
    """Authorize this exact archive, keep receipts and publish from Actions."""
    if not authorization_from_environment(
        dict(os.environ)
    ).permits_external_write:
        raise PermissionError("October archive publication requires approval")
    plan = PublicationPlan.model_validate_json(
        (output / "plan.json").read_bytes()
    )
    if plan.sha256() != PLAN_SHA256:
        raise ValueError("October plan differs from the approved inventory")
    prepared = rebuild_completion_metadata(plan)
    if archive_plan(prepared[MANIFEST_NAME]) != plan:
        raise ValueError("Rebuilt October manifest differs from the saved plan")
    record_intent(output, plan, exact_commit)
    with (
        httpx.Client(
            base_url=source_origin(os.environ["GMA_OCTOBER_SOURCE_URL"]),
            headers={"Accept-Encoding": "identity"},
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(
                max_connections=SOURCE_CONNECTIONS,
                max_keepalive_connections=SOURCE_CONNECTIONS,
                keepalive_expiry=60,  # The private source keeps authenticated sockets for 65s.
            ),
            timeout=90,
        ) as client
    ):
        hub = cast("Any", import_module("huggingface_hub.hf_api"))
        api = hub.HfApi(token=os.environ["HF_TOKEN"])
        result = publish_batches(
            api,
            hub,
            client,
            plan,
            prepared=prepared,
            deadline=time.monotonic() + PUBLICATION_CHECKPOINT_SECONDS,
        )
    if result.complete:
        record_upload(output, plan, result.revision)
    else:
        (output / "checkpoint.json").write_text(
            json.dumps(
                {
                    "plan_sha256": plan.sha256(),
                    "remote_revision": result.revision,
                    "newly_committed": result.newly_committed,
                    "run_id": os.environ["GITHUB_RUN_ID"],
                },
                indent=2,
            )
        )


def record_intent(
    output: Path, plan: PublicationPlan, exact_commit: str
) -> None:
    """Bind a run to the full frozen plan before committing any bytes."""
    (output / "plan.json").write_text(plan.model_dump_json(indent=2))
    (output / "intent.json").write_text(
        json.dumps(
            {
                "commit": exact_commit,
                "run_id": os.environ["GITHUB_RUN_ID"],
                "plan_sha256": plan.sha256(),
            },
            indent=2,
        )
    )


def record_upload(output: Path, plan: PublicationPlan, revision: str) -> None:
    """Record a complete uploaded revision ready for independent readback."""
    receipt = PublicationTransportReceipt(
        plan_sha256=plan.sha256(),
        artifact_sha256=tuple(artifact.sha256 for artifact in plan.artifacts),
        target=plan.target,
        state=PublicationTransportState.UPLOADED,
        recorded_at=datetime.now(UTC),
        remote_revision=revision,
    )
    (output / "uploaded.json").write_text(receipt.model_dump_json(indent=2))


class OctoberReadback(HuggingFaceAnonymousArtifactVerifier):
    """Retry temporary reads and retain completed anonymous reads at one revision."""

    journal: Path | None = None
    prior: Mapping[str, ArtifactVerification] | None = None
    deadline: float | None = None
    interruption: str | None = None

    def verify_artifact(
        self,
        *,
        target: PublicationTarget,
        revision: str,
        artifact: ArtifactBinding,
    ) -> ArtifactVerification:
        if self.prior and artifact.relative_path in self.prior:
            # verify_publication also binds its URI, digest and size to this revision.
            return self.prior[artifact.relative_path]
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self.interruption = (
                "October anonymous readback reached its job checkpoint"
            )
            raise TransientOctoberError(self.interruption)
        for wait in (5, 30, 120, None):
            try:
                result = super().verify_artifact(
                    target=target, revision=revision, artifact=artifact
                )
            except Exception as error:
                reason = transient_reason(error)
                if reason is None:
                    detail = (
                        f"HTTP {error.response.status_code}"
                        if isinstance(error, AnonymousReadbackHTTPError)
                        else type(error).__name__
                    )
                    print(
                        f"October readback failed for {artifact.relative_path}: {detail}",
                        flush=True,
                    )
                    raise
                message = f"October readback {artifact.relative_path}: {reason}"
                if wait is None:
                    self.interruption = message
                    raise TransientOctoberError(message) from None
                delay = float(wait)
                if isinstance(error, AnonymousReadbackHTTPError):
                    delay = max(delay, source_retry_after(error.response) or 0)
                    if (
                        error.response.status_code
                        == HTTPStatus.TOO_MANY_REQUESTS
                    ):
                        delay = max(delay, 300)
                if delay > MAX_READBACK_WAIT_SECONDS or (
                    self.deadline is not None
                    and time.monotonic() + delay >= self.deadline
                ):
                    self.interruption = message
                    raise TransientOctoberError(message) from None
                print(f"{message}; retrying in {delay:g}s", flush=True)
                time.sleep(delay)
            else:
                if self.journal is not None:
                    with self.journal.open("a", encoding="utf-8") as stream:
                        stream.write(result.model_dump_json() + "\n")
                return result
        raise AssertionError("unreachable October readback retry state")


def verify(output: Path, exact_commit: str) -> int:
    """Verify the exact published revision anonymously on a second runner."""
    plan = PublicationPlan.model_validate_json(
        (output / "plan.json").read_bytes()
    )
    intent = json.loads((output / "intent.json").read_bytes())
    if (
        plan.sha256() != PLAN_SHA256
        or intent["plan_sha256"] != PLAN_SHA256
        or intent["run_id"] != os.environ["GITHUB_RUN_ID"]
        or intent["commit"] != exact_commit
    ):
        raise ValueError("October receipts do not match this Actions run")
    uploaded = PublicationTransportReceipt.model_validate_json(
        (output / "uploaded.json").read_bytes()
    )
    reader = OctoberReadback(timeout_seconds=120)
    head = uploaded.remote_revision or ""
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("October readback requires an immutable revision")
    reader.journal = output / f"readbacks-{head}.jsonl"
    prior: dict[str, ArtifactVerification] = {}
    for path in (output / "prior").glob(f"*/{reader.journal.name}"):
        for row in path.read_text(encoding="utf-8").splitlines():
            item = ArtifactVerification.model_validate_json(row)
            if prior.setdefault(item.relative_path, item) != item:
                raise ValueError("Conflicting October readback checkpoints")
    reader.prior = prior
    reader.deadline = time.monotonic() + PUBLICATION_CHECKPOINT_SECONDS
    print(f"Restored {len(prior)} anonymous readbacks for {head}", flush=True)
    verified = verify_publication(
        plan=plan,
        uploaded_receipt=uploaded,
        verifier=reader,
        recorded_at=datetime.now(UTC),
    )
    (output / "verified.json").write_text(verified.model_dump_json(indent=2))
    if reader.interruption is not None:
        raise TransientOctoberError(reader.interruption)
    return int(verified.state is not PublicationTransportState.PUBLIC)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=("publish", "verify", "verify-online", "publish-online"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exact-commit", required=True)
    args = parser.parse_args()
    require_hosted_main(args.exact_commit)
    if os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise ValueError("October publication requires a GitHub-hosted runner")
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        if args.phase == "verify":
            return verify(args.output, args.exact_commit)
        if args.phase in {"verify-online", "publish-online"}:
            recover_online(
                args.output,
                args.exact_commit,
                publish_matches=args.phase == "publish-online",
            )
        else:
            publish(args.output, args.exact_commit)
    except Exception as error:
        reason = transient_reason(error)
        if reason is None:
            raise
        print(f"Temporary October failure: {reason}", flush=True)
        with Path(os.environ["GITHUB_OUTPUT"]).open(
            "a", encoding="utf-8"
        ) as outputs:
            outputs.write("retryable=true\n")
        return os.EX_TEMPFAIL
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
