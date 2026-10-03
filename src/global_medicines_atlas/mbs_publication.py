"""Hosted-only append publication with token-free exact-object verification."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Protocol

from .mbs_durable_landing import build_verified_mbs_lifecycle
from .mbs_release import (
    MbsReleaseContract,
    MbsReleaseStage,
    require_mbs_hosted_authority,
)
from .receipts import (
    EvidenceClass,
    RightsState,
    SourceReceipt,
    require_publication_permitted,
)


@dataclass(frozen=True)
class PublicArchiveState:
    revision: str
    paths: frozenset[str]
    private: bool
    gated: bool


class MbsPublicReader(Protocol):
    """Implementations must use an explicitly anonymous client."""

    def state(self, revision: str | None = None) -> PublicArchiveState: ...
    def read(self, revision: str, path: str) -> bytes: ...


class MbsArchiveAppender(Protocol):
    """Implementations add only these files with a compare-and-swap parent."""

    def append(
        self, files: Mapping[str, Path], *, parent_revision: str
    ) -> str: ...


def _validated_stage(
    stage: MbsReleaseStage,
    contract: MbsReleaseContract,
) -> tuple[dict[str, Path], dict[str, str]]:
    require_mbs_hosted_authority(contract)
    if stage.manifest.profile_state == "quarantined":
        raise ValueError(
            "quarantined raw response is outside qualified-file publication permission"
        )
    if (
        stage.manifest.contract != contract
        or stage.manifest.evidence_class is not EvidenceClass.LIVE
    ):
        raise ValueError(
            "publication requires the exact authorized live manifest"
        )
    expected = {item.path: item.sha256 for item in stage.manifest.objects}
    if (
        len(expected) != len(stage.manifest.objects)
        or stage.manifest_path in expected
    ):
        raise ValueError("duplicate manifest object path")
    expected[stage.manifest_path] = sha256(
        (stage.manifest.model_dump_json(indent=2) + "\n").encode()
    ).hexdigest()
    files: dict[str, Path] = {}
    for name, digest in expected.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError("unsafe archive object path")
        path = stage.path / name
        if path.is_symlink() or not path.resolve().is_relative_to(
            stage.path.resolve()
        ):
            raise ValueError("unsafe archive object symlink")
        if sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("staged object digest mismatch")
        files[name] = path
    if {
        path.relative_to(stage.path).as_posix()
        for path in stage.path.rglob("*")
        if path.is_file()
    } != set(files):
        raise ValueError("unmanifested staged object")
    for item in stage.manifest.objects:
        if item.role == "source_receipt":
            receipt = SourceReceipt.model_validate_json(
                files[item.path].read_bytes()
            )
            require_publication_permitted(receipt)
            if (
                receipt.evidence_class is not EvidenceClass.LIVE
                or receipt.source.source_id != contract.source_id
                or receipt.rights_state is not RightsState.PERMITTED
                or str(receipt.retrieval.uri) != str(contract.source_url)
                or receipt.payload.sha256
                not in {
                    raw.sha256
                    for raw in stage.manifest.objects
                    if raw.role == "raw"
                }
            ):
                raise ValueError(
                    "source receipt is not the authorized live acquisition"
                )
    return files, expected


def publish_mbs_stage(
    stage: MbsReleaseStage,
    contract: MbsReleaseContract,
    *,
    public: MbsPublicReader,
    writer: MbsArchiveAppender,
) -> dict[str, object]:
    """Never create/delete/publicize repos; append and verify an existing public archive."""
    files, expected = _validated_stage(stage, contract)
    before = public.state()
    if before.private or before.gated:
        raise ValueError("MBS destination must already be public and non-gated")
    for name in before.paths.intersection(files):
        if (
            sha256(public.read(before.revision, name)).hexdigest()
            != expected[name]
        ):
            raise ValueError(
                "append would overwrite a different existing object"
            )
    revision = writer.append(files, parent_revision=before.revision)
    after = public.state(revision)
    if (
        after.private
        or after.gated
        or after.revision != revision
        or after.paths != before.paths.union(files)
    ):
        raise ValueError(
            "anonymous exact revision or preserved sibling set differs"
        )
    for name, digest in expected.items():
        if sha256(public.read(revision, name)).hexdigest() != digest:
            raise ValueError("anonymous object digest mismatch")
    return {
        "schema_id": "global-medicines-atlas.mbs-hosted-publication",
        "dataset": contract.dataset,
        "revision": revision,
        "parent_revision": before.revision,
        "manifest_path": stage.manifest_path,
        "manifest_sha256": expected[stage.manifest_path],
        "verified_objects": len(expected),
        "legacy_paths_preserved": len(before.paths),
        "anonymous_digest_verification": "passed",
        "profile_state": stage.manifest.profile_state,
        "record_count": stage.manifest.record_count,
        "data_acquired": stage.manifest.profile_state == "accepted"
        and stage.manifest.record_count > 0,
        "temporary_source_bytes_removed": False,
    }


def publish_verified_mbs_lifecycle(
    receipt: SourceReceipt,
    contract: MbsReleaseContract,
    *,
    raw_archive_revision: str,
    raw_object_path: str,
    record_count: int,
    p7_record_count: int,
    decided_at: datetime,
    public: MbsPublicReader,
    writer: MbsArchiveAppender,
) -> dict[str, object]:
    """Append B1/B2 lifecycle metadata only after the raw revision verifies."""
    require_mbs_hosted_authority(contract)
    if (
        contract.dataset != "edithatogo/australian-mbs-source-archive"
        or receipt.source.source_id != contract.source_id
        or str(receipt.retrieval.uri) != str(contract.source_url)
        or str(receipt.rights_reference) != contract.authorization_reference
    ):
        raise ValueError(
            "source receipt differs from the authorized MBS contract"
        )
    before = public.state(raw_archive_revision)
    if (
        before.private
        or before.gated
        or before.revision != raw_archive_revision
    ):
        raise ValueError("raw MBS archive revision is not anonymously public")
    expected_raw_path = (
        f"raw/mbs/releases/2026-08-01/{receipt.payload.sha256}.xml"
    )
    if (
        raw_object_path != expected_raw_path
        or raw_object_path not in before.paths
    ):
        raise ValueError(
            "verified raw object is absent from the pinned revision"
        )
    if (
        sha256(public.read(raw_archive_revision, raw_object_path)).hexdigest()
        != receipt.payload.sha256
    ):
        raise ValueError(
            "pinned raw object no longer matches its source receipt"
        )
    objects = build_verified_mbs_lifecycle(
        receipt,
        raw_archive_revision=raw_archive_revision,
        raw_object_path=raw_object_path,
        decided_at=decided_at,
        record_count=record_count,
        p7_record_count=p7_record_count,
    )
    expected = {
        name: sha256(payload).hexdigest() for name, payload in objects.items()
    }
    if before.paths.intersection(objects):
        raise ValueError(
            "B1 lifecycle append would overwrite an existing object"
        )
    with TemporaryDirectory(prefix="gma-mbs-lifecycle-") as temporary:
        root = Path(temporary)
        files: dict[str, Path] = {}
        for name, payload in objects.items():
            relative = PurePosixPath(name)
            if relative.is_absolute() or ".." in relative.parts or "\\" in name:
                raise ValueError("unsafe lifecycle object path")
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            files[name] = path
        revision = writer.append(files, parent_revision=raw_archive_revision)
    after = public.state(revision)
    if (
        after.private
        or after.gated
        or after.revision != revision
        or after.paths != before.paths.union(objects)
    ):
        raise ValueError("anonymous MBS lifecycle append differs from manifest")
    for name, digest in expected.items():
        if sha256(public.read(revision, name)).hexdigest() != digest:
            raise ValueError(
                "anonymous MBS lifecycle digest verification failed"
            )
    return {
        "schema_id": "global-medicines-atlas.mbs-verified-lifecycle-publication",
        "dataset": "edithatogo/australian-mbs-source-archive",
        "raw_archive_revision": raw_archive_revision,
        "metadata_revision": revision,
        "verified_objects": len(objects),
        "object_sha256": expected,
        "anonymous_digest_verification": "passed",
    }
