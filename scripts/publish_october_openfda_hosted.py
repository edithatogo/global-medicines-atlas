"""Publish the approved October openFDA archive from a private source."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from importlib import import_module
from ipaddress import IPv4Address, IPv4Network
from operator import attrgetter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast
from urllib.parse import quote, urlsplit

import httpx

from global_medicines_atlas.data_layer_archive import (
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
SOURCE_PORT = 18043
TAILSCALE_IPV4 = IPv4Network("100.64.0.0/10")
COMMIT_BYTES = 4 * 1024**3
COMMIT_FILES = 64
TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}


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


def download_once(
    client: httpx.Client, artifact: ArtifactBinding, output: Path
) -> None:
    """Copy one bounded source object and verify its original digest."""
    size = 0
    digest = hashlib.sha256()
    with (
        client.stream(
            "GET", quote(artifact.relative_path, safe="/")
        ) as response,
        output.open("wb") as stream,
    ):
        response.raise_for_status()
        if response.status_code != HTTPStatus.OK:
            raise ValueError(
                f"Incomplete October source file: {artifact.relative_path}"
            )
        for chunk in response.iter_raw():
            size += len(chunk)
            if size > artifact.size:
                raise ValueError(
                    f"October source file grew: {artifact.relative_path}"
                )
            digest.update(chunk)
            stream.write(chunk)
    if size != artifact.size or digest.hexdigest() != artifact.sha256:
        raise ValueError(
            f"October source checksum differs: {artifact.relative_path}"
        )


def download_artifact(
    client: httpx.Client, artifact: ArtifactBinding, output: Path
) -> None:
    """Retry transient source reads without writing to the archive."""
    for wait in (2, 4, 0):
        try:
            download_once(client, artifact, output)
        except httpx.HTTPError as error:
            if not wait or (
                isinstance(error, httpx.HTTPStatusError)
                and error.response.status_code not in TRANSIENT_STATUS
            ):
                raise ValueError(
                    f"October source read failed: {artifact.relative_path}"
                ) from None
            time.sleep(wait)
        else:
            return


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
    if path in {"README.md", MANIFEST.relative_path}:
        return 2, path
    return 1, path


def remaining_artifacts(
    api: Any, hub: Any, plan: PublicationPlan
) -> tuple[str, list[ArtifactBinding]]:
    """Resume only from a Hub revision containing approved, matching files."""
    info = api.repo_info(REPOSITORY, repo_type="dataset", revision="main")
    head = str(info.sha)
    if info.private is not False or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError(
            "October destination must be the existing public dataset"
        )
    remaining = {
        artifact.relative_path: artifact for artifact in plan.artifacts
    }
    verifier = HuggingFaceAnonymousArtifactVerifier()
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
            verifier.verify_artifact(
                target=plan.target, revision=head, artifact=artifact
            )
        elif (entry.lfs.sha256, entry.lfs.size) != (
            artifact.sha256,
            artifact.size,
        ):
            raise ValueError(
                f"October destination checksum differs: {entry.path}"
            )
    return head, sorted(remaining.values(), key=publication_order)


def publish_batches(
    api: Any, hub: Any, client: httpx.Client, plan: PublicationPlan
) -> str:
    """Upload and commit verified batches, leaving durable resume points."""
    head, remaining = remaining_artifacts(api, hub, plan)
    count = len(plan.artifacts) - len(remaining)
    for group in commit_groups(remaining):
        with TemporaryDirectory(prefix="openfda-october-") as scratch:
            additions: list[Any] = []
            for position, artifact in enumerate(group):
                source = Path(scratch) / str(position)
                download_artifact(client, artifact, source)
                additions.append(
                    hub.CommitOperationAdd(
                        path_in_repo=artifact.relative_path,
                        path_or_fileobj=source,
                    )
                )
            result = api.create_commit(
                REPOSITORY,
                repo_type="dataset",
                revision="main",
                parent_commit=head,
                operations=additions,
                commit_message=f"Archive October openFDA files {count + 1} to {count + len(group)}",
            )
        head = str(result.oid)
        if not re.fullmatch(r"[0-9a-f]{40}", head):
            raise ValueError(
                "Hugging Face did not return an immutable October revision"
            )
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
    return head


def publish(output: Path, exact_commit: str) -> None:
    """Authorize this exact archive, keep receipts and publish from Actions."""
    if not authorization_from_environment(
        dict(os.environ)
    ).permits_external_write:
        raise PermissionError("October archive publication requires approval")
    with (
        httpx.Client(
            base_url=source_origin(os.environ["GMA_OCTOBER_SOURCE_URL"]),
            headers={"Accept-Encoding": "identity"},
            follow_redirects=False,
            trust_env=False,
            timeout=90,
        ) as client,
        TemporaryDirectory(prefix="openfda-october-manifest-") as scratch,
    ):
        path = Path(scratch) / MANIFEST.relative_path
        download_artifact(client, MANIFEST, path)
        plan = archive_plan(path.read_bytes())
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
        hub = cast("Any", import_module("huggingface_hub.hf_api"))
        api = hub.HfApi(token=os.environ["HF_TOKEN"])
        revision = publish_batches(api, hub, client, plan)
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
    """Identify the artifact on a checksum or download failure."""

    def verify_artifact(
        self,
        *,
        target: PublicationTarget,
        revision: str,
        artifact: ArtifactBinding,
    ) -> ArtifactVerification:
        for wait in (2, 4):
            try:
                return super().verify_artifact(
                    target=target, revision=revision, artifact=artifact
                )
            except httpx.TransportError:
                time.sleep(wait)
        try:
            return super().verify_artifact(
                target=target, revision=revision, artifact=artifact
            )
        except ValueError, httpx.HTTPError:
            print(
                f"October readback failed for {artifact.relative_path}",
                flush=True,
            )
            raise


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
    verified = verify_publication(
        plan=plan,
        uploaded_receipt=uploaded,
        verifier=OctoberReadback(timeout_seconds=120),
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
    require_hosted_main(args.exact_commit)
    if os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise ValueError("October publication requires a GitHub-hosted runner")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.phase == "verify":
        return verify(args.output, args.exact_commit)
    publish(args.output, args.exact_commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
