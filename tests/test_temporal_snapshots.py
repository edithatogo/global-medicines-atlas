from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.snapshots import (
    FIXTURE_EVIDENCE_LABEL,
    SnapshotManifest,
    build_fixture_snapshot_manifest,
    canonical_json_bytes,
    verify_snapshot_manifest,
    write_snapshot_manifest,
)


def _fixture_files(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "fixtures"
    input_path = root / "inputs" / "assertions.json"
    output_path = root / "outputs" / "assertions.parquet"
    catalog_path = tmp_path / "medicine_source_catalog.json"
    input_path.parent.mkdir(parents=True)
    output_path.parent.mkdir(parents=True)
    input_path.write_text('{"fixture":true}\n', encoding="utf-8")
    output_path.write_bytes(b"fixture-parquet")
    catalog_path.write_text('{"sources":[]}\n', encoding="utf-8")
    return root, input_path, output_path, catalog_path


def _manifest(tmp_path: Path) -> SnapshotManifest:
    root, input_path, output_path, catalog_path = _fixture_files(tmp_path)
    return build_fixture_snapshot_manifest(
        fixture_root=root,
        input_paths=[input_path],
        output_paths=[output_path],
        source_catalog_path=catalog_path,
        dataset_schema_id="global-medicines-atlas.temporal-assertions",
        dataset_schema_version="2",
        transformation_command=[
            "python",
            "-m",
            "global_medicines_atlas.qualify",
            "--fixture-only",
        ],
        package_commit="abc1234",
    )


@pytest.mark.unit
def test_fixture_manifest_is_deterministic_and_explicit(tmp_path: Path) -> None:
    first = _manifest(tmp_path / "first")
    second = _manifest(tmp_path / "second")

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    payload = json.loads(canonical_json_bytes(first))
    assert payload["qualification_scope"] == FIXTURE_EVIDENCE_LABEL
    assert payload["dataset_schema_version"] == "2"
    assert [item["role"] for item in payload["artifacts"]] == ["input", "output"]
    assert all(len(item["sha256"]) == 64 for item in payload["artifacts"])
    assert len(payload["source_catalog_sha256"]) == 64


@pytest.mark.integration
def test_written_manifest_verifies_without_copying_payloads(tmp_path: Path) -> None:
    root, input_path, output_path, catalog_path = _fixture_files(tmp_path)
    manifest = build_fixture_snapshot_manifest(
        fixture_root=root,
        input_paths=[input_path],
        output_paths=[output_path],
        source_catalog_path=catalog_path,
        dataset_schema_id="temporal",
        dataset_schema_version="2",
        transformation_command=["python", "qualification.py"],
        package_commit="deadbeef",
    )
    destination = tmp_path / "qualification.json"

    write_snapshot_manifest(manifest, destination)

    assert (
        verify_snapshot_manifest(
            destination,
            fixture_root=root,
            source_catalog_path=catalog_path,
        )
        == manifest
    )
    assert not (destination.parent / "inputs").exists()
    assert not (destination.parent / "outputs").exists()


@pytest.mark.edge
def test_verification_rejects_tampered_fixture(tmp_path: Path) -> None:
    root, input_path, output_path, catalog_path = _fixture_files(tmp_path)
    manifest = build_fixture_snapshot_manifest(
        fixture_root=root,
        input_paths=[input_path],
        output_paths=[output_path],
        source_catalog_path=catalog_path,
        dataset_schema_id="temporal",
        dataset_schema_version="2",
        transformation_command=["qualify"],
        package_commit="deadbeef",
    )
    destination = write_snapshot_manifest(manifest, tmp_path / "manifest.json")
    output_path.write_bytes(b"tampered")

    with pytest.raises(ValueError, match="digest or size mismatch"):
        verify_snapshot_manifest(
            destination,
            fixture_root=root,
            source_catalog_path=catalog_path,
        )


@pytest.mark.edge
def test_verification_rejects_tampered_catalog(tmp_path: Path) -> None:
    root, input_path, output_path, catalog_path = _fixture_files(tmp_path)
    manifest = build_fixture_snapshot_manifest(
        fixture_root=root,
        input_paths=[input_path],
        output_paths=[output_path],
        source_catalog_path=catalog_path,
        dataset_schema_id="temporal",
        dataset_schema_version="2",
        transformation_command=["qualify"],
        package_commit="deadbeef",
    )
    destination = write_snapshot_manifest(manifest, tmp_path / "manifest.json")
    catalog_path.write_text('{"tampered":true}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="Source catalog digest"):
        verify_snapshot_manifest(
            destination,
            fixture_root=root,
            source_catalog_path=catalog_path,
        )


@pytest.mark.parametrize("segment", [".env", "restricted", "secrets"])
@pytest.mark.edge
def test_forbidden_fixture_paths_are_rejected(
    tmp_path: Path,
    segment: str,
) -> None:
    root, _, output_path, catalog_path = _fixture_files(tmp_path)
    forbidden = root / segment / "source.json"
    forbidden.parent.mkdir(parents=True)
    forbidden.write_text("sensitive", encoding="utf-8")

    with pytest.raises(ValueError, match="forbidden segments"):
        build_fixture_snapshot_manifest(
            fixture_root=root,
            input_paths=[forbidden],
            output_paths=[output_path],
            source_catalog_path=catalog_path,
            dataset_schema_id="temporal",
            dataset_schema_version="2",
            transformation_command=["qualify"],
            package_commit="deadbeef",
        )


@pytest.mark.edge
def test_artifacts_outside_fixture_root_are_rejected(tmp_path: Path) -> None:
    root, _, output_path, catalog_path = _fixture_files(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("not-a-fixture", encoding="utf-8")

    with pytest.raises(ValueError, match="outside the fixture root"):
        build_fixture_snapshot_manifest(
            fixture_root=root,
            input_paths=[outside],
            output_paths=[output_path],
            source_catalog_path=catalog_path,
            dataset_schema_id="temporal",
            dataset_schema_version="2",
            transformation_command=["qualify"],
            package_commit="deadbeef",
        )


@pytest.mark.unit
def test_manifest_requires_input_and_output_artifacts(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    payload = manifest.model_dump(mode="json")
    payload["artifacts"] = [
        artifact for artifact in payload["artifacts"] if artifact["role"] == "input"
    ]

    with pytest.raises(ValidationError, match="at least one output"):
        SnapshotManifest.model_validate(payload)
