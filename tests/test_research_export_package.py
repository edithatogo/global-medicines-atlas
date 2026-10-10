import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest

from global_medicines_atlas.research_export_package import (
    build_research_export_package,
    verify_research_export_package,
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
_PACKAGE_TIME = (1980, 1, 1, 0, 0, 0)


def _rewrite_archive(
    archive_bytes: bytes,
    *,
    replacements: dict[str, bytes] | None = None,
    extra: tuple[tuple[str, bytes], ...] = (),
    compression: int = ZIP_STORED,
    comment: bytes = b"",
) -> bytes:
    replacements = replacements or {}
    with ZipFile(BytesIO(archive_bytes)) as source:
        documents = {
            name: replacements.get(name, source.read(name))
            for name in source.namelist()
        }
    documents.update(extra)
    output = BytesIO()
    with ZipFile(output, mode="w", compression=compression) as target:
        target.comment = comment
        for name, content in documents.items():
            info = ZipInfo(name, date_time=_PACKAGE_TIME)
            info.compress_type = compression
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            target.writestr(info, content)
    return output.getvalue()


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
    ("url_before", "url_after", "artifact_revision"),
    [
        (_REVISION, "b" * 40, "b" * 40),
        ("silver/benefits.parquet", "silver/other.parquet", None),
        ("example/source/resolve", "example/other/resolve", None),
    ],
    ids=("revision", "path", "dataset-identity"),
)
@pytest.mark.unit
def test_research_export_package_rejects_source_binding_mismatch(
    url_before: str,
    url_after: str,
    artifact_revision: str | None,
) -> None:
    manifest, crate, lineage = _inputs()
    lineage = lineage.model_copy(
        update={
            "artifacts": tuple(
                ResearchLineageArtifact(
                    identifier=artifact.identifier,
                    role=artifact.role,
                    public_url=artifact.public_url.replace(
                        url_before, url_after
                    ),
                    sha256=artifact.sha256,
                    revision=artifact_revision,
                )
                if artifact.role == "input"
                else artifact
                for artifact in lineage.artifacts
            )
        }
    )

    with pytest.raises(ValueError, match="source identity, path, revision"):
        build_research_export_package(
            manifest=manifest,
            crate=crate,
            lineage=lineage,
        )


@pytest.mark.e2e
def test_research_export_package_rebuilds_from_saved_archive() -> None:
    manifest, crate, lineage = _inputs()
    original = build_research_export_package(
        manifest=manifest,
        crate=crate,
        lineage=lineage,
    )

    rebuilt = verify_research_export_package(original.archive_bytes())

    assert rebuilt.archive_bytes() == original.archive_bytes()
    assert rebuilt.sha256() == original.sha256()


@pytest.mark.parametrize(
    ("member", "replacement", "extra"),
    [
        (
            "manifest.json",
            b'{"schema_id":"first","schema_id":"second"}',
            (),
        ),
        (
            "ro-crate-metadata.json",
            None,
            (("unexpected.txt", b"unexpected"),),
        ),
    ],
)
@pytest.mark.edge
def test_research_export_package_clean_room_verifier_rejects_ambiguous_input(
    member: str,
    replacement: bytes | None,
    extra: tuple[tuple[str, bytes], ...],
) -> None:
    manifest, crate, lineage = _inputs()
    original = build_research_export_package(
        manifest=manifest,
        crate=crate,
        lineage=lineage,
    )
    replacements = {} if replacement is None else {member: replacement}
    altered = _rewrite_archive(
        original.archive_bytes(),
        replacements=replacements,
        extra=extra,
    )

    with pytest.raises(ValueError, match="research export"):
        verify_research_export_package(altered)


@pytest.mark.parametrize(
    "archive",
    [b"", b"not a zip archive", b"x" * (8 * 1024 * 1024 + 1)],
)
@pytest.mark.edge
def test_research_export_package_verifier_rejects_invalid_archive_bytes(
    archive: bytes,
) -> None:
    with pytest.raises(ValueError, match=r"research export|invalid"):
        verify_research_export_package(archive)


@pytest.mark.parametrize(
    ("replacement", "compression", "comment"),
    [
        (b"{", ZIP_STORED, b""),
        (b"[]", ZIP_STORED, b""),
        (b"{}", ZIP_STORED, b""),
        (None, ZIP_STORED, b"comment"),
        (None, ZIP_DEFLATED, b""),
    ],
)
@pytest.mark.edge
def test_research_export_package_verifier_rejects_malformed_members(
    replacement: bytes | None,
    compression: int,
    comment: bytes,
) -> None:
    manifest, crate, lineage = _inputs()
    original = build_research_export_package(
        manifest=manifest,
        crate=crate,
        lineage=lineage,
    )
    changed = _rewrite_archive(
        original.archive_bytes(),
        replacements=(
            {"manifest.json": replacement} if replacement is not None else None
        ),
        compression=compression,
        comment=comment,
    )

    with pytest.raises(ValueError, match=r"research export|invalid"):
        verify_research_export_package(changed)


@pytest.mark.parametrize(
    "field",
    ["@context", "@graph", "dataset_id"],
)
@pytest.mark.edge
def test_research_export_package_verifier_rejects_invalid_metadata_shape(
    field: str,
) -> None:
    manifest, crate, lineage = _inputs()
    original = build_research_export_package(
        manifest=manifest,
        crate=crate,
        lineage=lineage,
    )
    with ZipFile(BytesIO(original.archive_bytes())) as archive:
        crate_document = json.loads(archive.read("ro-crate-metadata.json"))
    if field == "@context":
        crate_document[field] = "unexpected"
    elif field == "@graph":
        crate_document[field] = "not a graph"
    else:
        crate_document = {field: "unexpected"}
    changed = _rewrite_archive(
        original.archive_bytes(),
        replacements={
            "ro-crate-metadata.json": json.dumps(crate_document).encode()
        },
    )

    with pytest.raises(ValueError, match=r"research export|invalid"):
        verify_research_export_package(changed)


@pytest.mark.edge
def test_research_export_package_verifier_rejects_noncanonical_json() -> None:
    manifest, crate, lineage = _inputs()
    original = build_research_export_package(
        manifest=manifest,
        crate=crate,
        lineage=lineage,
    )
    with ZipFile(BytesIO(original.archive_bytes())) as archive:
        payload = json.loads(archive.read("manifest.json"))
    changed = _rewrite_archive(
        original.archive_bytes(),
        replacements={"manifest.json": json.dumps(payload, indent=2).encode()},
    )

    with pytest.raises(ValueError, match="not canonical"):
        verify_research_export_package(changed)


@pytest.mark.edge
def test_research_export_package_verifier_rejects_corrupt_member_crc() -> None:
    manifest, crate, lineage = _inputs()
    archive = build_research_export_package(
        manifest=manifest,
        crate=crate,
        lineage=lineage,
    ).archive_bytes()
    corrupted = archive.replace(b'"@context"', b'"@contexT"', 1)
    assert corrupted != archive

    with pytest.raises(ValueError, match="CRC"):
        verify_research_export_package(corrupted)


@pytest.mark.parametrize(
    "malformation",
    [
        "short_graph",
        "non_object_row",
        "dataset_identity",
        "distribution_type",
        "distribution_item",
        "distribution_identity",
        "row_type",
        "required_text",
    ],
)
@pytest.mark.edge
def test_research_export_package_verifier_rejects_invalid_crate_graph(
    malformation: str,
) -> None:
    manifest, crate, lineage = _inputs()
    original = build_research_export_package(
        manifest=manifest,
        crate=crate,
        lineage=lineage,
    )
    with ZipFile(BytesIO(original.archive_bytes())) as archive:
        crate_document = json.loads(archive.read("ro-crate-metadata.json"))
    graph = crate_document["@graph"]
    dataset = graph[0]
    if malformation == "short_graph":
        crate_document["@graph"] = []
    elif malformation == "non_object_row":
        graph[1] = "not an object"
    elif malformation == "dataset_identity":
        dataset["@id"] = "wrong"
    elif malformation == "distribution_type":
        dataset["distribution"] = "not a list"
    elif malformation == "distribution_item":
        dataset["distribution"] = [1]
    elif malformation == "distribution_identity":
        dataset["distribution"] = ["different.parquet"]
    elif malformation == "row_type":
        graph[1]["@type"] = "Thing"
    else:
        dataset.pop("name")
    changed = _rewrite_archive(
        original.archive_bytes(),
        replacements={
            "ro-crate-metadata.json": json.dumps(crate_document).encode()
        },
    )

    with pytest.raises(ValueError, match=r"research export|invalid"):
        verify_research_export_package(changed)


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
