"""Exercise and archive the governed Bronze acquisition corpus."""

from __future__ import annotations

import json
import shutil
import tarfile
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Literal

from pydantic import Field

from .bronze_admission import BronzeAdmissionRecord, BronzeAdmissionState
from .bronze_fixture_landing import (
    BronzeFixtureLandingManifest,
    land_governed_fixtures,
)
from .bronze_landing import PAYLOAD_DIR, RECEIPT_DIR
from .bronze_recovery import (
    BronzeRecoveryEvidence,
    RecoveryScenario,
    reconstruct_bronze,
    write_recovery_evidence,
)
from .models import FrozenModel
from .source_catalog import load_source_catalog
from .source_landing_factory import SourceLandingQueue

ARCHIVE_FILENAME = "bronze-source-acquisition-corpus.tar"
MANIFEST_FILENAME = "bronze-source-acquisition-corpus.manifest.json"
CHECKSUM_FILENAME = "SHA256SUMS"


class BronzeCorpusArchiveManifest(FrozenModel):
    """Machine-verifiable boundary and result of one corpus exercise."""

    schema_id: Literal["global-medicines-atlas.bronze-corpus-archive"] = (
        "global-medicines-atlas.bronze-corpus-archive"
    )
    schema_version: Literal[1] = 1
    exercised_at: datetime
    evidence_class: Literal["synthetic_fixture_only"] = "synthetic_fixture_only"
    live_source_coverage_claimed: Literal[False] = False
    external_publication_performed: Literal[False] = False
    catalog_source_count: int = Field(ge=1)
    landing_queue_source_count: int = Field(ge=1)
    queue_state_counts: dict[str, int]
    exercised_source_count: int = Field(ge=1)
    acquisition_count: int = Field(ge=1)
    accepted_admission_count: int = Field(ge=1)
    unexercised_source_count: int = Field(ge=0)
    source_ids: tuple[str, ...]
    recovery_scenarios: tuple[str, ...]
    recovery_evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    fixture_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    archive_filename: Literal["bronze-source-acquisition-corpus.tar"] = (
        ARCHIVE_FILENAME
    )
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    archive_byte_count: int = Field(ge=1)


@dataclass(frozen=True, slots=True)
class _CorpusExercise:
    fixture_manifest: BronzeFixtureLandingManifest
    fixture_manifest_bytes: bytes
    recovery: BronzeRecoveryEvidence
    accepted: int


@dataclass(frozen=True, slots=True)
class _CorpusInventory:
    queue: SourceLandingQueue
    catalog_ids: frozenset[str]


def _exercise_fixture_corpus(
    repository_root: Path,
    corpus: Path,
    exercised_at: datetime,
) -> _CorpusExercise:
    bronze = corpus / "bronze"
    clean_room = corpus / "clean-room"
    evidence = corpus / "evidence"
    evidence.mkdir(parents=True)
    fixture_manifest = land_governed_fixtures(
        repository_root,
        bronze_root=bronze,
        retrieved_at=exercised_at,
    )
    fixture_bytes = fixture_manifest.canonical_json() + b"\n"
    (evidence / "fixture-landing-manifest.json").write_bytes(fixture_bytes)
    admissions = tuple(
        BronzeAdmissionRecord.model_validate_json(path.read_bytes())
        for path in sorted((bronze / "admissions").rglob("*.json"))
    )
    accepted = sum(
        record.state is BronzeAdmissionState.ACCEPTED for record in admissions
    )
    if accepted != len(fixture_manifest.landings):
        raise ValueError("every governed fixture acquisition must be admitted")
    _copy_evidentiary_truth(bronze, clean_room)
    recovery = reconstruct_bronze(
        clean_room,
        fail_closed_on_incomplete=True,
    )
    if len(recovery.landings) != len(fixture_manifest.landings):
        raise ValueError(
            "clean-room recovery did not rebuild every acquisition"
        )
    if RecoveryScenario.CLEAN_ROOM_REBUILD.value not in recovery.scenarios:
        raise ValueError("clean-room recovery scenario was not exercised")
    write_recovery_evidence(
        recovery,
        evidence / "clean-room-recovery-evidence.json",
    )
    return _CorpusExercise(
        fixture_manifest=fixture_manifest,
        fixture_manifest_bytes=fixture_bytes,
        recovery=recovery,
        accepted=accepted,
    )


def _copy_evidentiary_truth(source: Path, destination: Path) -> None:
    for folder in (PAYLOAD_DIR, RECEIPT_DIR):
        origin = source / folder
        if origin.is_dir():
            shutil.copytree(origin, destination / folder)


def _add_to_tar(
    archive: tarfile.TarFile,
    path: Path,
    *,
    root: Path,
) -> None:
    relative = path.relative_to(root).as_posix()
    info = tarfile.TarInfo(name=f"corpus/{relative}")
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    if path.is_dir():
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        archive.addfile(info)
        return
    payload = path.read_bytes()
    info.size = len(payload)
    info.mode = 0o644
    archive.addfile(info, BytesIO(payload))


def _write_archive(corpus: Path, destination: Path) -> None:
    with tarfile.open(destination, mode="w", format=tarfile.PAX_FORMAT) as tar:
        paths = sorted(
            corpus.rglob("*"),
            key=lambda item: item.relative_to(corpus).as_posix(),
        )
        for path in paths:
            if path.is_symlink():
                raise ValueError(
                    "Bronze corpus archive cannot contain symlinks"
                )
            _add_to_tar(tar, path, root=corpus)


def _load_queue(path: Path) -> SourceLandingQueue:
    return SourceLandingQueue.model_validate_json(path.read_bytes())


def _load_corpus_inventory(
    repository_root: Path,
    corpus: Path,
) -> _CorpusInventory:
    queue_path = (
        repository_root
        / "quality"
        / "qualifications"
        / "bronze-source-landing-queue.json"
    )
    queue = _load_queue(queue_path)
    catalog_ids = frozenset(
        source.source_id for source in load_source_catalog()
    )
    if catalog_ids != frozenset(item.source_id for item in queue.items):
        raise ValueError(
            "landing queue and source catalogue must be exhaustive"
        )
    evidence = corpus / "evidence"
    shutil.copy2(queue_path, evidence / queue_path.name)
    catalog_path = (
        repository_root
        / "src"
        / "global_medicines_atlas"
        / "data"
        / "medicine_source_catalog.json"
    )
    shutil.copy2(catalog_path, evidence / catalog_path.name)
    return _CorpusInventory(queue=queue, catalog_ids=catalog_ids)


def _archive_corpus(corpus: Path, output_dir: Path) -> tuple[str, int]:
    archive_path = output_dir / ARCHIVE_FILENAME
    _write_archive(corpus, archive_path)
    archive_bytes = archive_path.read_bytes()
    return sha256(archive_bytes).hexdigest(), len(archive_bytes)


def _build_manifest(
    exercise: _CorpusExercise,
    inventory: _CorpusInventory,
    *,
    exercised_at: datetime,
    archive_digest: str,
    archive_byte_count: int,
) -> BronzeCorpusArchiveManifest:
    state_counts = {
        state.value: count
        for state, count in inventory.queue.state_counts.items()
    }
    source_ids = tuple(sorted(exercise.fixture_manifest.source_ids))
    return BronzeCorpusArchiveManifest(
        exercised_at=exercised_at,
        catalog_source_count=len(inventory.catalog_ids),
        landing_queue_source_count=inventory.queue.source_count,
        queue_state_counts=dict(sorted(state_counts.items())),
        exercised_source_count=len(source_ids),
        acquisition_count=len(exercise.fixture_manifest.landings),
        accepted_admission_count=exercise.accepted,
        unexercised_source_count=len(inventory.catalog_ids - set(source_ids)),
        source_ids=source_ids,
        recovery_scenarios=tuple(sorted(exercise.recovery.scenarios)),
        recovery_evidence_digest=exercise.recovery.evidence_digest,
        fixture_manifest_sha256=sha256(
            exercise.fixture_manifest_bytes
        ).hexdigest(),
        archive_sha256=archive_digest,
        archive_byte_count=archive_byte_count,
    )


def build_bronze_corpus_archive(
    repository_root: Path,
    output_dir: Path,
    *,
    exercised_at: datetime,
) -> BronzeCorpusArchiveManifest:
    """Land, admit, reconstruct, and archive the governed fixture corpus."""

    if exercised_at.tzinfo is None:
        raise ValueError("exercised_at must include a timezone")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError("output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus = output_dir / "corpus"
    exercise = _exercise_fixture_corpus(
        repository_root,
        corpus,
        exercised_at,
    )

    inventory = _load_corpus_inventory(repository_root, corpus)
    archive_digest, archive_byte_count = _archive_corpus(corpus, output_dir)
    manifest = _build_manifest(
        exercise,
        inventory,
        exercised_at=exercised_at,
        archive_digest=archive_digest,
        archive_byte_count=archive_byte_count,
    )
    manifest_path = output_dir / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / CHECKSUM_FILENAME).write_text(
        f"{archive_digest}  {ARCHIVE_FILENAME}\n",
        encoding="utf-8",
    )
    return manifest
