"""Append existing-source metadata from GitHub Actions with Hub CAS."""

# Fixed gh argument arrays use PATH on the GitHub-hosted runner; no shell input.
# The optional hosted SDK is imported only after local execution is refused.
# ruff: file-ignore[subprocess-without-shell-equals-true, start-process-with-partial-path]

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed gh commands, no shell
import sys
import tempfile
import time
from http import HTTPStatus
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urljoin

import httpx

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_metadata_append import (
    MetadataAppend,
    ObjectDigest,
)
from global_medicines_atlas.federation_metadata_hosted import (
    MAX_RECEIPT_CHARS,
    REPOSITORY,
    PublicSnapshot,
    execute_metadata_append,
    require_hosted_main,
)
from global_medicines_atlas.federation_reader import HOSTS

MAX_OBJECT_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_OBJECTS = 10000
WORKER_ARGUMENT_COUNT = 7
MAX_DOWNLOAD_SECONDS = 900


class HubTransport:
    """Actual anonymous restoration and single-add CAS Hub transport."""

    def __init__(self, cache: Path) -> None:
        sdk = importlib.import_module("huggingface_hub")
        self.public: Any = sdk.HfApi(token=False)
        self.cache = cache

    def head(self, dataset: str) -> str:
        info = self.public.dataset_info(dataset, timeout=30)
        if info.private or info.gated:
            raise ValueError("target is not public and non-gated")
        return str(info.sha)

    def download_object(
        self,
        dataset: str,
        revision: str,
        path: str,
        limit: int,
        *,
        timeout: int = 60,
    ) -> Path:
        """Restore one object through the existing isolated bounded reader."""
        return self._download(dataset, revision, path, limit, timeout=timeout)

    def _download(
        self,
        dataset: str,
        revision: str,
        path: str,
        limit: int = MAX_OBJECT_BYTES,
        *,
        timeout: int = 60,
    ) -> Path:
        """Kill the isolated reader at the absolute wall-clock deadline."""
        if type(timeout) is not int or not 1 <= timeout <= MAX_DOWNLOAD_SECONDS:
            raise ValueError("download timeout outside supported bound")
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--download-worker",
                    dataset,
                    revision,
                    path,
                    str(limit),
                    str(self.cache),
                    str(timeout),
                ],
                timeout=timeout,
                capture_output=True,
                text=True,
                check=True,
                env={
                    key: value
                    for key, value in os.environ.items()
                    if key not in {"HF_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"}
                },
            )
        except subprocess.TimeoutExpired, subprocess.CalledProcessError:
            raise ValueError(
                "anonymous download failed or exceeded deadline"
            ) from None
        target = Path(result.stdout.strip())
        if target.parent != self.cache:
            raise ValueError("download worker returned invalid cache path")
        return target

    def _download_worker(
        self,
        dataset: str,
        revision: str,
        path: str,
        limit: int = MAX_OBJECT_BYTES,
        *,
        timeout: int = 60,
    ) -> Path:
        url = (
            f"https://huggingface.co/datasets/{dataset}/resolve/{revision}/"
            + quote(path)
        )
        target = self.cache / hashlib.sha256(url.encode()).hexdigest()
        if type(timeout) is not int or not 1 <= timeout <= MAX_DOWNLOAD_SECONDS:
            raise ValueError("download timeout outside supported bound")
        policy = AcquisitionPolicy(allowed_hosts=HOSTS, timeout_seconds=timeout)
        deadline = time.monotonic() + timeout
        with httpx.Client(
            transport=BoundIPAddressTransport(policy=policy),
            trust_env=False,
            timeout=timeout,
            follow_redirects=False,
            headers={"Accept-Encoding": "identity"},
        ) as client:
            for _ in range(4):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("download deadline exceeded")
                client.cookies.clear()
                with client.stream("GET", url, timeout=remaining) as response:
                    if response.is_redirect:
                        url = urljoin(url, response.headers["location"])
                        continue
                    self._save_response(response, target, limit, deadline)
                    return target
        raise ValueError("anonymous redirect bound exceeded")

    @staticmethod
    def _save_response(
        response: httpx.Response, target: Path, limit: int, deadline: float
    ) -> None:
        if (
            response.status_code != HTTPStatus.OK
            or response.headers.get("content-encoding", "identity")
            != "identity"
        ):
            raise ValueError("anonymous response status or encoding invalid")
        size = 0
        with target.open("wb") as stream:
            # No chunk accumulation: inspect each transport read for deadline
            # and size before writing it, including a slow-dribbling response.
            for chunk in response.iter_raw():
                size += len(chunk)
                if size > limit or time.monotonic() > deadline:
                    raise ValueError("download byte/time bound exceeded")
                stream.write(chunk)

    def snapshot(self, dataset: str, revision: str) -> PublicSnapshot:
        info = self.public.dataset_info(
            dataset, revision=revision, files_metadata=True, timeout=30
        )
        if info.sha != revision or info.private or info.gated:
            raise ValueError("anonymous source revision mismatch")
        siblings = info.siblings
        if not siblings or len(siblings) > MAX_OBJECTS:
            raise ValueError("invalid source sibling denominator")
        total = 0
        objects: list[ObjectDigest] = []
        for item in siblings:
            size = item.size
            if type(size) is not int or not 0 <= size <= MAX_OBJECT_BYTES:
                raise ValueError("source object size outside bound")
            total += size
            if total > MAX_TOTAL_BYTES:
                raise ValueError("source snapshot exceeds total byte bound")
            # Validate remote path before passing it to a cache downloader.
            ObjectDigest(item.rfilename, size, "0" * 64)
        for item in siblings:
            path = self._download(dataset, revision, item.rfilename, item.size)
            if path.stat().st_size != item.size:
                raise ValueError("restored source size differs")
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            objects.append(ObjectDigest(item.rfilename, item.size, digest))
        return PublicSnapshot(
            revision=revision,
            private=False,
            gated=False,
            objects=tuple(objects),
        )

    def append(self, plan: MetadataAppend) -> str:
        # Recheck the actual process context before touching authentication.
        require_hosted_main(os.environ.get("GITHUB_SHA", ""))
        sdk = importlib.import_module("huggingface_hub")

        token = os.environ.get("HF_TOKEN")
        if not token:
            raise ValueError("protected publication credential unavailable")
        result = sdk.HfApi(token=token).create_commit(
            repo_id=plan.dataset,
            repo_type="dataset",
            operations=[
                sdk.CommitOperationAdd(
                    path_in_repo=plan.addition.path,
                    path_or_fileobj=plan.payload,
                )
            ],
            parent_commit=plan.parent_revision,
            commit_message="Append receipt-bound Australian source metadata",
        )
        return str(result.oid)

    def metadata(self, dataset: str, revision: str, path: str) -> bytes:
        restored = self._download(dataset, revision, path, 1024 * 1024)
        if restored.stat().st_size > 1024 * 1024:
            raise ValueError("metadata readback too large")
        return restored.read_bytes()


def persist_receipt(document: dict[str, Any], directory: Path) -> str:
    """Persist a metadata-only receipt for the current Actions artifact."""
    body = json.dumps(document, sort_keys=True, separators=(",", ":"))
    if len(body) > MAX_RECEIPT_CHARS:
        raise ValueError("receipt exceeds supported artifact size")
    status = document.get("status")
    if not isinstance(status, str) or not re.fullmatch(
        r"[a-z][a-z0-9_]{0,63}", status
    ):
        raise ValueError("receipt status is not a safe filename")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
        or not re.fullmatch(r"[0-9]+", run_id)
    ):
        raise ValueError(
            "receipt persistence requires the exact hosted Actions run"
        )
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    filename = f"{status}-{digest}.json"
    path = directory / filename
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    observed = json.loads(path.read_text(encoding="utf-8"))
    if json.dumps(observed, sort_keys=True, separators=(",", ":")) != body:
        raise ValueError("workflow receipt file readback differs")
    return f"https://github.com/{REPOSITORY}/actions/runs/{run_id}"


class IntentPreparedError(Exception):
    """Stop after writing a pre-append intent for workflow artifact retention."""


def persist_transaction_receipt(
    document: dict[str, Any],
    directory: Path,
    *,
    prepare_only: bool = False,
    prepublished_intent: Path | None = None,
) -> str:
    """Require the exact intent to round-trip through a hosted artifact first."""
    if document.get("status") == "intent":
        if prepare_only:
            persist_receipt(document, directory)
            raise IntentPreparedError
        if prepublished_intent is None:
            raise ValueError("append requires a retained pre-append intent")
        matches = tuple(prepublished_intent.glob("intent-*.json"))
        if len(matches) != 1:
            raise ValueError(
                "pre-append artifact must contain one intent receipt"
            )
        observed = json.loads(matches[0].read_text(encoding="utf-8"))
        if observed != document:
            raise ValueError(
                "pre-append artifact differs from current transaction"
            )
        expected_url = (
            f"https://github.com/{REPOSITORY}/actions/runs/"
            f"{os.environ.get('GITHUB_RUN_ID', '')}"
        )
        if document.get("run_url") != expected_url:
            raise ValueError(
                "pre-append intent belongs to another workflow run"
            )
        return expected_url
    return persist_receipt(document, directory)


def read_acknowledgement(comment_id: str) -> dict[str, Any]:
    """Authenticate a bot CAS acknowledgement and its matching prior intent.

    This proves the workflow observed a CAS response, not independent Git
    ancestry. Missing acknowledgement after an ambiguous write stays blocked.
    """

    def read(identifier: str) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9]+", identifier):
            raise ValueError("invalid recovery receipt identifier")
        raw = subprocess.check_output(
            ["gh", "api", f"repos/{REPOSITORY}/issues/comments/{identifier}"],
            text=True,
            timeout=30,
        )
        if len(raw) > MAX_RECEIPT_CHARS * 2:
            raise ValueError("recovery receipt exceeds bound")
        observed = json.loads(raw)
        if (
            observed.get("user", {}).get("login") != "github-actions[bot]"
            or observed.get("issue_url")
            != f"https://api.github.com/repos/{REPOSITORY}/issues/340"
            or observed.get("html_url")
            != f"https://github.com/{REPOSITORY}/issues/340#issuecomment-{identifier}"
        ):
            raise ValueError(
                "recovery receipt is not authenticated issue evidence"
            )
        body = observed.get("body")
        if not isinstance(body, str) or len(body) > MAX_RECEIPT_CHARS:
            raise ValueError("recovery receipt body invalid")
        document = json.loads(body)
        if not isinstance(document, dict):
            raise TypeError("recovery receipt document invalid")
        return cast("dict[str, Any]", document)

    acknowledgement = read(comment_id)
    match = re.fullmatch(
        rf"https://github.com/{re.escape(REPOSITORY)}/issues/340#issuecomment-([0-9]+)",
        str(acknowledgement.get("intent_url", "")),
    )
    if match is None or acknowledgement.get("status") != "cas_acknowledged":
        raise ValueError("recovery acknowledgement missing prior intent")
    intent = read(match[1])
    expected = {
        **intent,
        "status": "cas_acknowledged",
        "revision": acknowledgement.get("revision"),
        "intent_url": acknowledgement["intent_url"],
        "parent_basis": "server_enforced_parent_commit",
    }
    if intent.get("status") != "intent" or acknowledgement != expected:
        raise ValueError("recovery acknowledgement differs from prior intent")
    return acknowledgement


def read_artifact_acknowledgement(
    run_id: str, artifact_directory: Path
) -> dict[str, Any]:
    """Read and bind a CAS acknowledgement from a downloaded run artifact."""
    if not re.fullmatch(r"[0-9]+", run_id):
        raise ValueError("invalid recovery run identifier")
    expected_run_url = f"https://github.com/{REPOSITORY}/actions/runs/{run_id}"

    def read_status(status: str) -> Any:
        matches = tuple(artifact_directory.glob(f"{status}-*.json"))
        if len(matches) == 1:
            return json.loads(matches[0].read_text())
        if not matches:
            legacy_path = artifact_directory / f"{status}.json"
            if legacy_path.is_file():
                return json.loads(legacy_path.read_text())
        raise ValueError(f"recovery artifact must contain one {status} receipt")

    intent = read_status("intent")
    acknowledgement = read_status("cas_acknowledged")
    if not isinstance(intent, dict) or not isinstance(acknowledgement, dict):
        raise TypeError("recovery artifact documents are invalid")
    intent_document = cast("dict[str, Any]", intent)
    acknowledgement_document = cast("dict[str, Any]", acknowledgement)
    run_metadata = json.loads(
        subprocess.check_output(
            ["gh", "api", f"repos/{REPOSITORY}/actions/runs/{run_id}"],
            text=True,
            timeout=30,
        )
    )
    if not isinstance(run_metadata, dict):
        raise TypeError("recovery Actions run metadata is invalid")
    run_document = cast("dict[str, Any]", run_metadata)
    prior_workflow_path = run_document.get("path")
    allowed_workflow_paths = {
        ".github/workflows/australian-source-metadata.yml@refs/heads/main",
        ".github/workflows/australian-donor-history.yml@refs/heads/main",
    }
    repository = run_document.get("repository")
    if not isinstance(repository, dict):
        raise TypeError("recovery Actions run repository is invalid")
    repository_document = cast("dict[str, Any]", repository)
    run_bindings = (
        run_document.get("id"),
        repository_document.get("full_name"),
        run_document.get("head_branch"),
        run_document.get("event"),
        run_document.get("head_sha"),
    )
    expected_bindings = (
        int(run_id),
        REPOSITORY,
        "main",
        "workflow_dispatch",
        intent_document.get("code_commit"),
    )
    if (
        run_bindings != expected_bindings
        or prior_workflow_path not in allowed_workflow_paths
    ):
        raise ValueError(
            "recovery artifact is not from an exact authorized main workflow run"
        )
    bindings = (
        intent_document.get("status"),
        intent_document.get("run_url"),
        acknowledgement_document.get("run_url"),
        acknowledgement_document.get("status"),
        acknowledgement_document.get("intent_url"),
        acknowledgement_document.get("parent_basis"),
    )
    if bindings != (
        "intent",
        expected_run_url,
        expected_run_url,
        "cas_acknowledged",
        expected_run_url,
        "server_enforced_parent_commit",
    ):
        raise ValueError(
            "recovery artifact does not bind the exact run intent and CAS acknowledgement"
        )
    expected: dict[str, Any] = {
        **intent_document,
        "status": "cas_acknowledged",
        "revision": acknowledgement_document.get("revision"),
        "intent_url": expected_run_url,
        "parent_basis": "server_enforced_parent_commit",
    }
    if acknowledgement_document != expected:
        raise ValueError(
            "recovery artifact acknowledgement differs from intent"
        )
    return acknowledgement_document


def main() -> None:
    """Publish one reviewed source profile after exact-main workflow checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("mbs", "pbs"), required=True)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--expected-parent-revision", required=True)
    parser.add_argument("--recovery-receipt", default="")
    parser.add_argument("--recovery-run-id", default="")
    parser.add_argument("--prepare-intent", action="store_true")
    parser.add_argument("--prepublished-intent", type=Path)
    args = parser.parse_args()
    require_hosted_main(args.exact_commit)
    # Independently bind the current repository default head before Hub writes.
    head = subprocess.check_output(
        [
            "gh",
            "api",
            f"repos/{REPOSITORY}/commits/main",
            "--jq",
            ".sha",
        ],
        text=True,
    ).strip()
    if head != args.exact_commit:
        raise ValueError("reviewed main has advanced")
    root = Path(__file__).resolve().parents[1]
    document = json.loads(
        (
            root
            / "tests/fixtures/federation_source_metadata"
            / f"valid-{args.source}.json"
        ).read_text()
    )
    receipts = root / "build/source-metadata-receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    if args.recovery_receipt and args.recovery_run_id:
        raise ValueError("select only one recovery receipt source")
    acknowledgement = (
        read_acknowledgement(args.recovery_receipt)
        if args.recovery_receipt
        else read_artifact_acknowledgement(
            args.recovery_run_id,
            root / "build/recovery-receipts",
        )
        if args.recovery_run_id
        else None
    )
    cache = Path(tempfile.mkdtemp(prefix="gma-source-metadata-"))
    if args.prepare_intent and (args.prepublished_intent or acknowledgement):
        raise ValueError(
            "intent preparation cannot use an artifact or recovery"
        )
    if args.prepublished_intent and acknowledgement:
        raise ValueError("select prepublished intent or recovery, not both")
    try:
        result = execute_metadata_append(
            document,
            exact_commit=args.exact_commit,
            expected_parent_revision=args.expected_parent_revision,
            hub=HubTransport(cache),
            persist=lambda receipt: persist_transaction_receipt(
                receipt,
                receipts,
                prepare_only=args.prepare_intent,
                prepublished_intent=args.prepublished_intent,
            ),
            acknowledgement=acknowledgement,
        )
    except IntentPreparedError:
        shutil.rmtree(cache)
        return
    # Only successful durable anonymous verification permits source cache removal.
    shutil.rmtree(cache)
    (receipts / "result.json").write_text(
        json.dumps({**result, "temporary_cache_removed": True}, indent=2) + "\n"
    )


if __name__ == "__main__":
    if (
        len(sys.argv) in {WORKER_ARGUMENT_COUNT, WORKER_ARGUMENT_COUNT + 1}
        and sys.argv[1] == "--download-worker"
    ):
        require_hosted_main(os.environ.get("GITHUB_SHA", ""))
        worker = object.__new__(HubTransport)
        worker.cache = Path(sys.argv[6])
        print(
            worker._download_worker(  # pyright: ignore[reportPrivateUsage]
                sys.argv[2],
                sys.argv[3],
                sys.argv[4],
                int(sys.argv[5]),
                timeout=int(sys.argv[7])
                if len(sys.argv) > WORKER_ARGUMENT_COUNT
                else 60,
            )
        )
    else:
        main()
