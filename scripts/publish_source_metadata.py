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
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed gh commands, no shell
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
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

    def _download(
        self,
        dataset: str,
        revision: str,
        path: str,
        limit: int = MAX_OBJECT_BYTES,
    ) -> Path:
        """Kill the isolated reader at the absolute wall-clock deadline."""
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
                ],
                timeout=60,
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
    ) -> Path:
        url = (
            f"https://huggingface.co/datasets/{dataset}/resolve/{revision}/"
            + quote(path)
        )
        target = self.cache / hashlib.sha256(url.encode()).hexdigest()
        policy = AcquisitionPolicy(allowed_hosts=HOSTS, timeout_seconds=60)
        deadline = time.monotonic() + 60
        with httpx.Client(
            transport=BoundIPAddressTransport(policy=policy),
            trust_env=False,
            timeout=60,
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
            response.status_code != httpx.codes.OK
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
        objects = []
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
    """Persist and read back the exact public-safe issue receipt."""
    body = json.dumps(document, sort_keys=True, separators=(",", ":"))
    if len(body) > MAX_RECEIPT_CHARS:
        raise ValueError("durable issue receipt exceeds supported size")
    path = directory / f"{document['status']}.json"
    path.write_text(json.dumps({"body": body}))
    response = json.loads(
        subprocess.check_output(
            [
                "gh",
                "api",
                f"repos/{REPOSITORY}/issues/340/comments",
                "--method",
                "POST",
                "--input",
                str(path),
            ],
            text=True,
        )
    )
    observed = json.loads(
        subprocess.check_output(
            [
                "gh",
                "api",
                f"repos/{REPOSITORY}/issues/comments/{response['id']}",
            ],
            text=True,
        )
    )
    if (
        observed["body"] != body
        or observed["user"]["login"] != "github-actions[bot]"
    ):
        raise ValueError("durable issue receipt readback differs")
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return str(observed["html_url"])


def main() -> None:
    """Publish one reviewed source profile after exact-main workflow checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("mbs", "pbs"), required=True)
    parser.add_argument("--exact-commit", required=True)
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
    cache = Path(tempfile.mkdtemp(prefix="gma-source-metadata-"))
    result = execute_metadata_append(
        document,
        exact_commit=args.exact_commit,
        hub=HubTransport(cache),
        persist=lambda receipt: persist_receipt(receipt, receipts),
    )
    # Only successful durable anonymous verification permits source cache removal.
    shutil.rmtree(cache)
    (receipts / "result.json").write_text(
        json.dumps({**result, "temporary_cache_removed": True}, indent=2) + "\n"
    )


if __name__ == "__main__":
    if (
        len(sys.argv) == WORKER_ARGUMENT_COUNT
        and sys.argv[1] == "--download-worker"
    ):
        require_hosted_main(os.environ.get("GITHUB_SHA", ""))
        worker = object.__new__(HubTransport)
        worker.cache = Path(sys.argv[6])
        print(
            worker._download_worker(
                sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
            )
        )
    else:
        main()
