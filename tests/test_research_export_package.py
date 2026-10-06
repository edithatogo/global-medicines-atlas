import hashlib
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZipFile

import pytest

from global_medicines_atlas.research_export_package import (
    build_research_export_package,
)
from global_medicines_atlas.research_exports import (
    ExportSource,
    QuerySnapshotManifest,
    build_query_snapshot_manifest,
    manifest_sha256,
)
from global_medicines_atlas.research_lineage import (
    ResearchLineageArtifact,
    ResearchLineageReceipt,
    build_research_lineage_receipt,
)
from global_medicines_atlas.research_package import (
    CrateDistribution,
    ResearchCrate,
    build_research_crate,
)

_REVISION = "0" * 40


def _inputs() -> tuple[
    QuerySnapshotManifest, ResearchCrate, ResearchLineageReceipt
]:
    source = ExportSource(
        dataset_id="example/source",
        revision=_REVISION,
        path="silver/benefits.parquet",
        sha256="a" * 64,
        schema_id="gma.benefits",
        schema_version="4",
    )
    manifest = build_query_snapshot_manifest(
        query={"filters": {"jurisdiction": "AU"}},
        result_rows=[{"item_id": "1001"}],
        sources=[source],
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        generator_commit="abc1234",
    )
    export_id = manifest_sha256(manifest)
    distribution = CrateDistribution(
        identifier="benefits.parquet",
        name="Benefits query result",
        content_url=(
            "https://huggingface.co/datasets/example/exports/resolve/"
            f"{_REVISION}/benefits.parquet"
        ),
        media_type="application/vnd.apache.parquet",
        sha256=manifest.result_sha256,
    )
    crate = build_research_crate(
        identifier=export_id,
        name="Benefits research export",
        version="1",
        dataset_url="https://huggingface.co/datasets/example/exports",
        distributions=(distribution,),
    )
    lineage = build_research_lineage_receipt(
        export_id=export_id,
        revision=_REVISION,
        artifacts=(
            ResearchLineageArtifact(
                identifier="source:benefits",
                role="input",
                public_url=(
                    "https://huggingface.co/datasets/example/source/resolve/"
                    f"{_REVISION}/silver/benefits.parquet"
                ),
                sha256=source.sha256,
            ),
            ResearchLineageArtifact(
                identifier="benefits.parquet",
                role="output",
                public_url=distribution.content_url,
                sha256=manifest.result_sha256,
            ),
        ),
    )
    return manifest, crate, lineage


@pytest.mark.unit
def test_research_export_package_binds_all_metadata_and_is_deterministic() -> (
    None
):
    manifest, crate, lineage = _inputs()

    package = build_research_export_package(
        manifest=manifest,
        crate=crate,
        lineage=lineage,
    )
    archive = package.archive_bytes()

    assert package.sha256() == hashlib.sha256(archive).hexdigest()
    assert (
        archive
        == build_research_export_package(
            manifest=manifest,
            crate=crate,
            lineage=lineage,
        ).archive_bytes()
    )
    with ZipFile(BytesIO(archive)) as archive_file:
        assert archive_file.namelist() == [
            "croissant.json",
            "lineage.json",
            "manifest.json",
            "ro-crate-metadata.json",
        ]
        assert b"1001" not in b"".join(
            archive_file.read(name) for name in archive_file.namelist()
        )


@pytest.mark.parametrize(
    "mismatch",
    [
        "export_id",
        "source_digest",
        "crate_distribution_digest",
        "result_digest",
    ],
)
@pytest.mark.edge
def test_research_export_package_rejects_unbound_metadata(
    mismatch: str,
) -> None:
    manifest, crate, lineage = _inputs()
    if mismatch == "export_id":
        lineage = lineage.model_copy(update={"export_id": "b" * 64})
    elif mismatch == "source_digest":
        lineage = lineage.model_copy(
            update={
                "artifacts": tuple(
                    artifact.model_copy(update={"sha256": "c" * 64})
                    if artifact.role == "input"
                    else artifact
                    for artifact in lineage.artifacts
                )
            }
        )
    elif mismatch == "crate_distribution_digest":
        crate = crate.model_copy(
            update={
                "distributions": tuple(
                    distribution.model_copy(update={"sha256": "d" * 64})
                    for distribution in crate.distributions
                )
            }
        )
    else:
        crate = crate.model_copy(
            update={
                "distributions": tuple(
                    distribution.model_copy(update={"sha256": "d" * 64})
                    for distribution in crate.distributions
                )
            }
        )
        lineage = lineage.model_copy(
            update={
                "artifacts": tuple(
                    artifact.model_copy(update={"sha256": "d" * 64})
                    if artifact.role == "output"
                    else artifact
                    for artifact in lineage.artifacts
                )
            }
        )

    with pytest.raises(ValueError, match=r"bind|source|result"):
        build_research_export_package(
            manifest=manifest,
            crate=crate,
            lineage=lineage,
        )
