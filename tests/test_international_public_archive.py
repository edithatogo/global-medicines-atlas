"""International publication-candidate boundary tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from global_medicines_atlas.international_public_archive import (
    PENDING_SOURCES,
    SOURCE_CANDIDATE_RIGHTS,
    InternationalPublicationCandidateManifest,
    build_international_publication_candidate,
)


def _staging(root: Path) -> Path:
    for source_id in SOURCE_CANDIDATE_RIGHTS:
        directory = (
            root / "rxnorm-identifiers"
            if source_id in {"global-rxnorm", "us-rxnorm-api"}
            else root / source_id
        )
        directory.mkdir(parents=True, exist_ok=True)
        name = (
            "rxcui-identifiers.json"
            if source_id in {"global-rxnorm", "us-rxnorm-api"}
            else f"{source_id}.bin"
        )
        (directory / name).write_bytes(source_id.encode())
    return root


def test_builds_archive_and_keeps_failures_explicit(tmp_path: Path) -> None:
    output = tmp_path / "output"
    manifest = build_international_publication_candidate(
        _staging(tmp_path / "staging"), output
    )
    assert manifest.archived_source_count == 10
    assert len(manifest.pending_sources) == 3
    assert len({item.source_id for item in manifest.files}) == 10
    assert manifest.publication_approved is False
    assert "complete source coverage" in (output / "README.md").read_text()


def test_rejects_rxnorm_source_vocabulary_bytes(tmp_path: Path) -> None:
    staging = _staging(tmp_path / "staging")
    (staging / "rxnorm-identifiers/source-vocabulary.rrf").write_bytes(b"no")
    with pytest.raises(ValueError, match="prohibited"):
        build_international_publication_candidate(staging, tmp_path / "output")


def test_candidate_cannot_encode_publication_approval(tmp_path: Path) -> None:
    manifest = build_international_publication_candidate(
        _staging(tmp_path / "staging"), tmp_path / "output"
    )
    with pytest.raises(ValueError, match="cannot encode publication approval"):
        InternationalPublicationCandidateManifest.model_validate({
            **manifest.model_dump(),
            "publication_approved": True,
        })


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"files": []}, "each acquired source"),
        ({"pending_sources": {}}, "pending source set"),
        ({"archived_source_count": 9}, "count is inconsistent"),
    ],
)
def test_manifest_rejects_scope_drift(
    tmp_path: Path, updates: dict[str, object], message: str
) -> None:
    manifest = build_international_publication_candidate(
        _staging(tmp_path / "staging"), tmp_path / "output"
    )
    with pytest.raises(ValueError, match=message):
        InternationalPublicationCandidateManifest.model_validate({
            **manifest.model_dump(),
            **updates,
        })


def test_builder_rejects_existing_output_and_missing_source(
    tmp_path: Path,
) -> None:
    staging = _staging(tmp_path / "staging")
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(FileExistsError):
        build_international_publication_candidate(staging, existing)

    source_id = next(iter(set(SOURCE_CANDIDATE_RIGHTS) - set(PENDING_SOURCES)))
    source_dir = (
        staging / "rxnorm-identifiers"
        if source_id in {"global-rxnorm", "us-rxnorm-api"}
        else staging / source_id
    )
    for path in source_dir.iterdir():
        path.unlink()
    with pytest.raises(ValueError, match="no acquired files"):
        build_international_publication_candidate(staging, tmp_path / "missing")
