"""Publish only the approved incremental donor histories from hosted main."""

# Fixed git/gh argument arrays; no donor code is checked out or executed.
# ruff: file-ignore[subprocess-without-shell-equals-true, start-process-with-partial-path]
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] -- fixed argv only
import tempfile
from pathlib import Path
from typing import Any

from publish_source_metadata import (
    HubTransport,
    persist_receipt,
    read_acknowledgement,
)

from global_medicines_atlas.donor_delta import (
    BASELINES,
    ChangedFile,
    DeltaObservation,
)
from global_medicines_atlas.donor_history_hosted import execute_history_append
from global_medicines_atlas.donor_history_publication import (
    EXACT_HEADS,
    DonorHistoryPublicationContract,
    HistoryAppendPlan,
    HistoryArchiveState,
    HistoryExtension,
    HistoryObject,
    HistoryVerification,
    RestoredHistory,
    observation_digest,
    require_donor_history_hosted_authority,
)
from global_medicines_atlas.federation_metadata_hosted import (
    REPOSITORY,
    require_hosted_main,
)

DATASET = "edithatogo/australian-mbs-source-archive"
ROOT = Path(__file__).resolve().parents[1]
MAX_HEADER_LINE = 4096
MAX_DELTA_PATHS = 256


def git(directory: Path, *args: str) -> str:
    """Run bounded Git without user hooks, config or inherited credentials."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"HF_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"}
    }
    environment.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT="0",
    )
    try:
        return subprocess.check_output(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "credential.helper=",
                "-C",
                str(directory),
                *args,
            ],
            text=True,
            timeout=120,
            stderr=subprocess.PIPE,
            env=environment,
        ).strip()
    except subprocess.CalledProcessError as error:
        # Expose only Git diagnostic identifiers, never source paths or text.
        codes = sorted(
            set(re.findall(r": ([a-z][A-Za-z]+):", error.stderr or ""))
        )
        raise ValueError(
            f"bounded donor Git operation failed (exit {error.returncode}; "
            f"diagnostics {','.join(codes) or 'unclassified'})"
        ) from None
    except subprocess.TimeoutExpired:
        raise ValueError(
            "bounded donor Git operation failed (timeout)"
        ) from None


def gh(endpoint: str) -> Any:
    """Read bounded GitHub metadata through the hosted credential."""
    return json.loads(
        subprocess.check_output(
            ["gh", "api", endpoint],
            text=True,
            timeout=30,
        )
    )


def object_info(path: str, file: Path) -> HistoryObject:
    """Hash an exact nonempty generated or anonymously restored object."""
    with file.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return HistoryObject(
        path=path, sha256=digest, byte_count=file.stat().st_size
    )


def prerequisites(file: Path) -> tuple[str, ...]:
    """Inspect only bounded bundle headers, never pack contents."""
    with file.open("rb") as stream:
        header = stream.readline(1024)
        if header != b"# v2 git bundle\n":
            raise ValueError("unsupported Git bundle version")
        result: list[str] = []
        for _ in range(MAX_DELTA_PATHS):
            line = stream.readline(MAX_HEADER_LINE)
            if line == b"\n":
                return tuple(result)
            if not line or len(line) >= MAX_HEADER_LINE:
                break
            if line.startswith(b"-"):
                result.append(line[1:41].decode("ascii"))
    raise ValueError("unbounded Git bundle header")


class DonorTransport:
    """Append-only Hub writes with independent Git and anonymous restore checks."""

    def __init__(
        self, workspace: Path, contract: DonorHistoryPublicationContract
    ) -> None:
        self.workspace = workspace
        self.contract = contract
        cache = workspace / "anonymous"
        cache.mkdir()
        self.hub = HubTransport(cache)
        self.generated: dict[str, Path] = {}

    def head(self) -> str:
        return self.hub.head(DATASET)

    def observations(self) -> tuple[DeltaObservation, ...]:
        result: list[DeltaObservation] = []
        for repository, head in EXACT_HEADS:
            if gh(f"repos/{repository}/commits/main")["sha"] != head:
                raise ValueError("donor default head drifted")
            baseline = BASELINES[repository]
            comparison = gh(f"repos/{repository}/compare/{baseline}...{head}")
            if (
                comparison["status"] != "ahead"
                or len(comparison["files"]) >= MAX_DELTA_PATHS
            ):
                raise ValueError("unsupported donor comparison denominator")
            result.append(
                DeltaObservation(
                    repository=repository,
                    baseline=baseline,
                    head=head,
                    ancestry="ahead",
                    files=tuple(
                        ChangedFile(
                            path=item["filename"],
                            blob=item["sha"],
                            status=item["status"],
                        )
                        for item in comparison["files"]
                    ),
                )
            )
        return tuple(result)

    def snapshot(self, revision: str) -> HistoryArchiveState:
        snapshot = self.hub.snapshot(DATASET, revision)
        if snapshot.private is not False or snapshot.gated is not False:
            raise ValueError("archive snapshot is not public")
        return HistoryArchiveState(
            dataset=DATASET,
            revision=snapshot.revision,
            private=False,
            gated=False,
            objects=tuple(
                HistoryObject(
                    path=obj.path, sha256=obj.sha256, byte_count=obj.byte_count
                )
                for obj in snapshot.objects
            ),
        )

    def prepare(self) -> HistoryAppendPlan:
        before = self.snapshot(self.head())
        extensions: list[HistoryExtension] = []
        for observed in self.observations():
            name = observed.repository.split("/")[1]
            repository = self.workspace / name
            git(
                self.workspace,
                "clone",
                "--bare",
                "--quiet",
                f"https://github.com/{observed.repository}.git",
                str(repository),
            )
            git(
                repository,
                "merge-base",
                "--is-ancestor",
                observed.baseline,
                observed.head,
            )
            delta = git(
                repository,
                "diff",
                "--name-status",
                "--no-renames",
                observed.baseline,
                observed.head,
            ).splitlines()
            files: list[ChangedFile] = []
            for line in delta:
                status, path = line.split("\t")
                if status not in {"A", "M"}:
                    raise ValueError("unsupported donor change status")
                files.append(
                    ChangedFile(
                        path=path,
                        status="added" if status == "A" else "modified",
                        blob=git(
                            repository, "rev-parse", f"{observed.head}:{path}"
                        ),
                    )
                )
            if tuple(files) != observed.files:
                raise ValueError("independent Git delta differs from GitHub")
            git(
                repository,
                "update-ref",
                "refs/archive/extension",
                observed.head,
            )
            bundle = self.workspace / f"{name}.bundle"
            git(
                repository,
                "bundle",
                "create",
                "--version=2",
                str(bundle),
                "refs/archive/extension",
                f"^{observed.baseline}",
            )
            if prerequisites(bundle) != (observed.baseline,):
                raise ValueError("incremental history prerequisites differ")
            bundle_path = f"history/{name}-{observed.head}.bundle"
            sidecar_path = (
                f"provenance/donor-deltas/{name}-{observed.head}.json"
            )
            sidecar = self.workspace / f"{name}.json"
            bundle_info = object_info(bundle_path, bundle)
            sidecar.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "observation": observed.model_dump(mode="json"),
                        "delta_sha256": observation_digest(observed),
                        "bundle": bundle_info.model_dump(),
                        "prerequisites": [observed.baseline],
                    },
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            )
            self.generated.update({bundle_path: bundle, sidecar_path: sidecar})
            extensions.append(
                HistoryExtension(
                    observation=observed,
                    delta_sha256=observation_digest(observed),
                    bundle=bundle_info,
                    manifest=object_info(sidecar_path, sidecar),
                )
            )
        return HistoryAppendPlan(before=before, extensions=tuple(extensions))

    def append(self, plan: HistoryAppendPlan) -> str:
        require_hosted_main(os.environ.get("GITHUB_SHA", ""))
        require_donor_history_hosted_authority(self.contract)
        sdk = importlib.import_module("huggingface_hub")
        existing = {obj.path: obj for obj in plan.before.objects}
        additions: list[Any] = []
        for extension in plan.extensions:
            for obj in (extension.bundle, extension.manifest):
                if obj.path in existing:
                    if obj != existing[obj.path]:
                        raise ValueError("existing history differs")
                    continue
                file = self.generated[obj.path]
                if object_info(obj.path, file) != obj:
                    raise ValueError("generated history changed before append")
                additions.append(
                    sdk.CommitOperationAdd(
                        path_in_repo=obj.path, path_or_fileobj=str(file)
                    )
                )
        if not additions:
            raise ValueError("empty history append forbidden")
        token = os.environ.get("HF_TOKEN")
        if not token:
            raise ValueError("protected publication credential unavailable")
        result = sdk.HfApi(token=token).create_commit(
            repo_id=DATASET,
            repo_type="dataset",
            operations=additions,
            parent_commit=plan.before.revision,
            commit_message="Preserve exact Australian donor history extensions",
        )
        return str(result.oid)

    def verify(
        self, plan: HistoryAppendPlan, revision: str
    ) -> HistoryVerification:
        after = self.snapshot(revision)
        objects = {obj.path: obj for obj in after.objects}
        anonymous: list[HistoryObject] = []
        restored: list[RestoredHistory] = []
        for extension in plan.extensions:
            observed = extension.observation
            name = observed.repository.split("/")[1]
            baseline_path = f"history/{name}-{observed.baseline}.bundle"
            paths = (
                baseline_path,
                extension.bundle.path,
                extension.manifest.path,
            )
            files: dict[str, Path] = {}
            for path in paths:
                files[path] = self.hub._download(DATASET, revision, path)  # pyright: ignore[reportPrivateUsage]
                obj = object_info(path, files[path])
                if obj != objects[path]:
                    raise ValueError("anonymous history digest differs")
                anonymous.append(obj)
            sidecar = json.loads(files[extension.manifest.path].read_text())
            if sidecar != {
                "schema_version": 1,
                "observation": observed.model_dump(mode="json"),
                "delta_sha256": extension.delta_sha256,
                "bundle": extension.bundle.model_dump(),
                "prerequisites": [observed.baseline],
            }:
                raise ValueError("anonymous sidecar differs from plan")
            restore = self.workspace / f"restore-{name}"
            restore.mkdir()
            git(restore, "init", "--bare", "--quiet")
            git(
                restore,
                "fetch",
                str(files[baseline_path]),
                "refs/archive/pinned:refs/archive/baseline",
            )
            if (
                git(restore, "rev-parse", "refs/archive/baseline")
                != observed.baseline
            ):
                raise ValueError("restored baseline differs")
            bundle = files[extension.bundle.path]
            required = prerequisites(bundle)
            git(restore, "bundle", "verify", str(bundle))
            git(
                restore,
                "fetch",
                str(bundle),
                "refs/archive/extension:refs/archive/extension",
            )
            if (
                git(restore, "rev-parse", "refs/archive/extension")
                != observed.head
            ):
                raise ValueError("restored extension head differs")
            git(
                restore,
                "merge-base",
                "--is-ancestor",
                observed.baseline,
                observed.head,
            )
            git(restore, "update-ref", "--no-deref", "HEAD", observed.head)
            git(restore, "fsck", "--full", "--strict")
            restored.append(
                RestoredHistory(
                    repository=observed.repository,
                    head=observed.head,
                    baseline=observed.baseline,
                    baseline_bundle_sha256=objects[baseline_path].sha256,
                    bundle_sha256=extension.bundle.sha256,
                    delta_sha256=extension.delta_sha256,
                    prerequisites=required,
                    baseline_is_ancestor=True,
                    clean_restore=True,
                )
            )
        return HistoryVerification(
            plan=plan,
            parent_revision=plan.before.revision,
            after=after,
            anonymous_objects=tuple(anonymous),
            restored=tuple(restored),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--recovery-receipt", default="")
    args = parser.parse_args()
    require_hosted_main(args.exact_commit)
    contract = DonorHistoryPublicationContract.model_validate_json(
        (
            ROOT
            / "quality/qualifications/australian-donor-history-publication-contract.json"
        ).read_text()
    )
    require_donor_history_hosted_authority(contract)
    if gh(f"repos/{REPOSITORY}/commits/main")["sha"] != args.exact_commit:
        raise ValueError("reviewed main has advanced")
    acknowledgement = (
        read_acknowledgement(args.recovery_receipt)
        if args.recovery_receipt
        else None
    )
    receipts = ROOT / "build/donor-history-receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="gma-donor-history-"))
    result = execute_history_append(
        contract,
        exact_commit=args.exact_commit,
        transport=DonorTransport(workspace, contract),
        persist=lambda document: persist_receipt(document, receipts),
        acknowledgement=acknowledgement,
    )
    shutil.rmtree(workspace)
    (receipts / "result.json").write_text(
        json.dumps({**result, "temporary_cache_removed": True}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
