import hashlib
import json
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest

from global_medicines_atlas.frontier_attestation import (
    build_verification_cost_receipt,
    canonical_verification_cost_bytes,
    verify_verification_cost_receipt,
)
from global_medicines_atlas.frontier_merkle import (
    MerkleLeaf,
    build_merkle_manifest,
    canonical_merkle_manifest_bytes,
    merkle_root,
    verify_merkle_manifest,
)
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
def test_cross_dataset_package_binds_existing_public_revisions() -> None:  # ruff: ignore[too-many-locals]
    sources = (
        ExportSource(
            dataset_id="edithatogo/australian-mbs-source-archive",
            revision="44b25bfd87e44998c7c1da4c3930ad4447e9246f",
            path=("raw/mbs/releases/Downloads-20260801/MBS-XML-20260801.XML"),
            sha256="c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565",
            schema_id="gma.au.mbs.source-archive",
            schema_version="1",
        ),
        ExportSource(
            dataset_id="edithatogo/australian-pbs-source-archive",
            revision="48fd7345fb09277bb5b85644dba72804633a2abb",
            path="raw/2026-04-01/2026-04-01-XML-V3.zip",
            sha256="f3e7af3610637b85577d0518ef50d3be9e692888e9acd3b5897d313706365c20",
            schema_id="gma.au.pbs.source-archive",
            schema_version="1",
        ),
    )
    rows = [
        {"dataset_id": source.dataset_id, "source_sha256": source.sha256}
        for source in sources
    ]
    manifest = build_query_snapshot_manifest(
        query={"mode": "synthetic_existing_revision_binding"},
        result_rows=rows,
        sources=sources,
        generated_at=datetime(2026, 10, 10, tzinfo=UTC),
        generator_commit="synthetic-public-revision-binding-v1",
    )
    export_id = manifest_sha256(manifest)
    revision = "b" * 40
    result_url = (
        "https://huggingface.co/datasets/edithatogo/fixture-export/resolve/"
        f"{revision}/query-result.json"
    )
    batch_manifest = build_merkle_manifest((
        *(
            MerkleLeaf(
                dataset_id=source.dataset_id,
                revision=source.revision,
                path=source.path,
                sha256=source.sha256,
            )
            for source in sources
        ),
        MerkleLeaf(
            dataset_id="edithatogo/fixture-export",
            revision=revision,
            path="platinum/query-result.json",
            sha256=manifest.result_sha256,
        ),
    ))
    assert verify_merkle_manifest(batch_manifest)
    source_dataset_ids = {source.dataset_id for source in sources}
    source_leaves = tuple(
        leaf
        for leaf in batch_manifest.leaves
        if leaf.dataset_id in source_dataset_ids
    )
    assert {(leaf.dataset_id, leaf.revision) for leaf in source_leaves} == {
        (source.dataset_id, source.revision) for source in sources
    }
    assert (
        merkle_root(
            tuple(
                leaf.model_copy(update={"revision": "0" * 40})
                if leaf == source_leaves[0]
                else leaf
                for leaf in batch_manifest.leaves
            )
        )
        != batch_manifest.root_sha256
    )
    assert (
        merkle_root(
            tuple(
                leaf.model_copy(update={"dataset_id": "different/dataset"})
                if leaf == source_leaves[0]
                else leaf
                for leaf in batch_manifest.leaves
            )
        )
        != batch_manifest.root_sha256
    )
    merkle_payload = canonical_merkle_manifest_bytes(batch_manifest)
    cost_receipt = build_verification_cost_receipt(batch_manifest)
    cost_payload = canonical_verification_cost_bytes(cost_receipt)
    merkle_url = (
        "https://huggingface.co/datasets/edithatogo/fixture-export/resolve/"
        f"{revision}/merkle-manifest.json"
    )
    cost_url = (
        "https://huggingface.co/datasets/edithatogo/fixture-export/resolve/"
        f"{revision}/verification-cost.json"
    )
    crate = build_research_crate(
        identifier=export_id,
        name="Synthetic existing-revision identity package",
        version="1",
        dataset_url="https://huggingface.co/datasets/edithatogo/fixture-export",
        distributions=(
            CrateDistribution(
                identifier="query-result.json",
                name="Synthetic revision identity result",
                content_url=result_url,
                media_type="application/json",
                sha256=manifest.result_sha256,
            ),
            CrateDistribution(
                identifier="merkle-manifest.json",
                name="Source digest batch manifest",
                content_url=merkle_url,
                media_type="application/json",
                sha256=hashlib.sha256(merkle_payload).hexdigest(),
            ),
            CrateDistribution(
                identifier="verification-cost.json",
                name="Deterministic verification work receipt",
                content_url=cost_url,
                media_type="application/json",
                sha256=hashlib.sha256(cost_payload).hexdigest(),
            ),
        ),
    )
    lineage = build_research_lineage_receipt(
        export_id=export_id,
        revision=revision,
        artifacts=(
            *(
                ResearchLineageArtifact(
                    identifier=source.dataset_id,
                    role="input",
                    public_url=(
                        "https://huggingface.co/datasets/"
                        f"{source.dataset_id}/resolve/{source.revision}/"
                        f"{source.path}"
                    ),
                    sha256=source.sha256,
                    revision=source.revision,
                )
                for source in sources
            ),
            ResearchLineageArtifact(
                identifier="query-result.json",
                role="output",
                public_url=result_url,
                sha256=manifest.result_sha256,
            ),
            ResearchLineageArtifact(
                identifier="merkle-manifest.json",
                role="output",
                public_url=merkle_url,
                sha256=hashlib.sha256(merkle_payload).hexdigest(),
            ),
            ResearchLineageArtifact(
                identifier="verification-cost.json",
                role="output",
                public_url=cost_url,
                sha256=hashlib.sha256(cost_payload).hexdigest(),
            ),
        ),
    )

    package = build_research_export_package(
        manifest=manifest,
        crate=crate,
        lineage=lineage,
    )
    verified = verify_research_export_package(package.archive_bytes())
    verified_lineage = json.loads(dict(verified.documents)["lineage.json"])
    bound_inputs = {
        artifact["identifier"]: (
            artifact["revision"],
            artifact["sha256"],
            artifact["public_url"],
        )
        for artifact in verified_lineage["artifacts"]
        if artifact["role"] == "input"
    }

    assert lineage.schema_version == 2
    assert verify_merkle_manifest(batch_manifest)
    assert verify_verification_cost_receipt(batch_manifest, cost_receipt)
    assert cost_receipt.object_sha256_checks == 3
    assert cost_receipt.merkle_leaf_hashes == 3
    assert cost_receipt.merkle_pair_hashes == 3
    assert {leaf.sha256 for leaf in batch_manifest.leaves} == {
        *(source.sha256 for source in sources),
        manifest.result_sha256,
    }
    assert bound_inputs == {
        source.dataset_id: (
            source.revision,
            source.sha256,
            (
                "https://huggingface.co/datasets/"
                f"{source.dataset_id}/resolve/{source.revision}/{source.path}"
            ),
        )
        for source in sources
    }
    assert verified.archive_bytes() == package.archive_bytes()


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
