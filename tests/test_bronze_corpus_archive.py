"""Executable archive proof for the governed Bronze acquisition corpus."""

from __future__ import annotations

import json
import tarfile
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from scripts.exercise_bronze_corpus import main as exercise_main

from global_medicines_atlas.bronze_corpus_archive import (
    ARCHIVE_FILENAME,
    CHECKSUM_FILENAME,
    MANIFEST_FILENAME,
    BronzeCorpusArchiveManifest,
    build_bronze_corpus_archive,
)

ROOT = Path(__file__).resolve().parents[1]
EXERCISED_AT = datetime(2026, 8, 20, 6, 0, tzinfo=UTC)
WORKFLOW = ROOT / ".github" / "workflows" / "data-layer-archive.yml"


@pytest.mark.unit
def test_hosted_workflow_archives_corpus_without_implicit_publication() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "Exercise and archive governed Bronze corpus" in workflow
    assert "scripts/exercise_bronze_corpus.py" in workflow
    assert "sha256sum --check SHA256SUMS" in workflow
    assert "name: bronze-source-acquisition-corpus" in workflow
    publish = workflow[workflow.index("Publish to Hugging Face") :]
    assert "github.event_name == 'workflow_dispatch' && inputs.publish" in (
        publish
    )
    assert "github.event_name == 'push'" not in publish


@pytest.mark.integration
def test_corpus_archive_exercises_full_governed_bronze_path(
    tmp_path: Path,
) -> None:
    output = tmp_path / "archive"
    manifest = build_bronze_corpus_archive(
        ROOT,
        output,
        exercised_at=EXERCISED_AT,
    )

    assert manifest.catalog_source_count == 172
    assert manifest.landing_queue_source_count == 172
    assert sum(manifest.queue_state_counts.values()) == 172
    assert manifest.exercised_source_count == 16
    assert manifest.acquisition_count == 17
    assert manifest.accepted_admission_count == 17
    assert manifest.unexercised_source_count == 156
    assert manifest.live_source_coverage_claimed is False
    assert manifest.external_publication_performed is False
    assert "clean-room-rebuild" in manifest.recovery_scenarios

    archive = output / ARCHIVE_FILENAME
    assert sha256(archive.read_bytes()).hexdigest() == manifest.archive_sha256
    assert (output / CHECKSUM_FILENAME).read_text(encoding="utf-8") == (
        f"{manifest.archive_sha256}  {ARCHIVE_FILENAME}\n"
    )
    persisted = BronzeCorpusArchiveManifest.model_validate_json(
        (output / MANIFEST_FILENAME).read_bytes()
    )
    assert persisted == manifest
    with tarfile.open(archive, mode="r") as package:
        names = set(package.getnames())
    assert "corpus/evidence/fixture-landing-manifest.json" in names
    assert "corpus/evidence/clean-room-recovery-evidence.json" in names
    assert "corpus/evidence/bronze-source-landing-queue.json" in names
    assert any(name.startswith("corpus/bronze/payloads/") for name in names)
    assert any(name.startswith("corpus/bronze/parquet/") for name in names)
    assert any(name.startswith("corpus/bronze/lineage/") for name in names)
    assert any(name.startswith("corpus/bronze/admissions/") for name in names)
    assert any(
        name.startswith("corpus/clean-room/catalogue/") for name in names
    )


@pytest.mark.integration
def test_corpus_archive_is_repeatable_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    first = build_bronze_corpus_archive(
        ROOT,
        tmp_path / "first",
        exercised_at=EXERCISED_AT,
    )
    second = build_bronze_corpus_archive(
        ROOT,
        tmp_path / "second",
        exercised_at=EXERCISED_AT,
    )

    assert first.acquisition_count == second.acquisition_count == 17
    assert first.source_ids == second.source_ids
    with pytest.raises(FileExistsError, match="must be empty"):
        build_bronze_corpus_archive(
            ROOT,
            tmp_path / "first",
            exercised_at=EXERCISED_AT,
        )


@pytest.mark.integration
def test_corpus_archive_cli_executes_and_requires_aware_time(
    tmp_path: Path,
) -> None:
    output = tmp_path / "cli"
    assert exercise_main(["--output-dir", str(output)]) == 0
    payload = json.loads((output / MANIFEST_FILENAME).read_bytes())
    assert payload["acquisition_count"] == 17
    with pytest.raises(SystemExit):
        exercise_main([
            "--output-dir",
            str(tmp_path / "invalid"),
            "--exercised-at",
            "2026-08-20T06:00:00",
        ])
