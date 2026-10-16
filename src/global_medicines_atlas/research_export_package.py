"""Compose deterministic, metadata-only research export archives.

The archive binds a query snapshot manifest, RO-Crate, Croissant metadata,
and lineage receipt. Referenced source and result objects remain in their
governed data-plane locations and are never copied into the package.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from typing import Any, cast
from urllib.parse import urlsplit
from zipfile import ZIP_STORED, BadZipFile, ZipFile, ZipInfo

from pydantic import ValidationError

from .research_exports import (
    ExportSource,
    QuerySnapshotManifest,
    canonical_manifest_bytes,
    manifest_sha256,
)
from .research_lineage import ResearchLineageReceipt
from .research_package import (
    CrateDistribution,
    ResearchCrate,
    build_research_crate,
)
from .strict_json import unique_json_object

_PACKAGE_DOCUMENTS = (
    "croissant.json",
    "lineage.json",
    "manifest.json",
    "ro-crate-metadata.json",
)
_MAX_PACKAGE_BYTES = 8 * 1024 * 1024
_MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
_MAX_PACKAGE_DATE = (1980, 1, 1, 0, 0, 0)
_MIN_CRATE_GRAPH_ITEMS = 2


@dataclass(frozen=True)
class ResearchExportPackage:
    """A reproducible ZIP containing only bound export metadata documents."""

    documents: tuple[tuple[str, bytes], ...]

    def archive_bytes(self) -> bytes:
        """Serialize all metadata documents with stable ZIP metadata."""
        output = BytesIO()
        with ZipFile(output, mode="w", compression=ZIP_STORED) as archive:
            for name, content in self.documents:
                entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = ZIP_STORED
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, content)
        return output.getvalue()

    def sha256(self) -> str:
        """Return the archive's content address."""
        return hashlib.sha256(self.archive_bytes()).hexdigest()


def build_research_export_package(
    *,
    manifest: QuerySnapshotManifest,
    crate: ResearchCrate,
    lineage: ResearchLineageReceipt,
) -> ResearchExportPackage:
    """Bind and compose matching manifest, crate, and lineage metadata."""
    export_id = manifest_sha256(manifest)
    if crate.identifier != export_id or lineage.export_id != export_id:
        raise ValueError(
            "crate and lineage must bind the query manifest export id"
        )

    input_artifacts = tuple(
        artifact for artifact in lineage.artifacts if artifact.role == "input"
    )
    for source in manifest.sources:
        matching_source = any(
            artifact.sha256 == source.sha256
            and (artifact.revision or lineage.revision) == source.revision
            and _lineage_input_binds_source(artifact.public_url, source)
            for artifact in input_artifacts
        )
        if not matching_source:
            raise ValueError(
                "lineage inputs must bind each manifest source identity, "
                "path, revision, and digest"
            )

    output_digests = {
        artifact.identifier: artifact.sha256
        for artifact in lineage.artifacts
        if artifact.role == "output"
    }
    for distribution in crate.distributions:
        if output_digests.get(distribution.identifier) != distribution.sha256:
            raise ValueError(
                "crate distributions must bind matching lineage outputs"
            )
    if manifest.result_sha256 not in output_digests.values():
        raise ValueError("lineage outputs must bind the query result digest")

    documents = (
        ("croissant.json", crate.canonical_croissant_bytes()),
        ("lineage.json", lineage.canonical_bytes()),
        ("manifest.json", canonical_manifest_bytes(manifest)),
        ("ro-crate-metadata.json", crate.canonical_jsonld_bytes()),
    )
    return ResearchExportPackage(documents=documents)


def _lineage_input_binds_source(public_url: str, source: ExportSource) -> bool:
    """Check that an input URL identifies one manifest source object."""
    path_parts = tuple(
        part for part in urlsplit(public_url).path.split("/") if part
    )
    try:
        resolve_index = path_parts.index("resolve")
    except ValueError:
        return False
    dataset_parts = tuple(part for part in source.dataset_id.split("/") if part)
    source_path_parts = tuple(part for part in source.path.split("/") if part)
    return (
        bool(dataset_parts)
        and path_parts[:resolve_index][-len(dataset_parts) :] == dataset_parts
        and path_parts[resolve_index + 1 :]
        == (source.revision, *source_path_parts)
    )


def verify_research_export_package(
    archive_bytes: bytes,
) -> ResearchExportPackage:
    """Rebuild and verify an export package from its saved archive alone.

    No network access or source/result payloads are needed. All ZIP members,
    JSON documents, bound digests, and canonical archive bytes are checked.
    """
    if not archive_bytes or len(archive_bytes) > _MAX_PACKAGE_BYTES:
        raise ValueError("research export package exceeds its byte budget")

    try:
        documents = _read_package_documents(archive_bytes)
    except BadZipFile, OSError, RuntimeError, EOFError:
        raise ValueError("invalid research export package archive") from None

    try:
        manifest, crate, lineage = _parse_package_metadata(documents)
    except KeyError, TypeError, ValidationError:
        raise ValueError(
            "research export package metadata is invalid"
        ) from None

    rebuilt = build_research_export_package(
        manifest=manifest,
        crate=crate,
        lineage=lineage,
    )
    if rebuilt.archive_bytes() != archive_bytes:
        raise ValueError("research export package is not canonical")
    return rebuilt


def _read_package_documents(archive_bytes: bytes) -> dict[str, bytes]:
    with ZipFile(BytesIO(archive_bytes), mode="r") as archive:
        members = archive.infolist()
        names = tuple(member.filename for member in members)
        if names != _PACKAGE_DOCUMENTS:
            raise ValueError("research export package member set is invalid")
        if archive.comment:
            raise ValueError("research export package comment is invalid")
        if any(_invalid_member_metadata(member) for member in members):
            raise ValueError(
                "research export package member metadata is invalid"
            )
        if archive.testzip() is not None:
            raise ValueError("research export package CRC is invalid")
        return {member.filename: archive.read(member) for member in members}


def _invalid_member_metadata(member: ZipInfo) -> bool:
    return any((
        member.is_dir(),
        member.file_size > _MAX_DOCUMENT_BYTES,
        member.compress_type != ZIP_STORED,
        member.file_size != member.compress_size,
        member.date_time != _MAX_PACKAGE_DATE,
        bool(member.flag_bits & 1),
    ))


def _parse_package_metadata(
    documents: dict[str, bytes],
) -> tuple[QuerySnapshotManifest, ResearchCrate, ResearchLineageReceipt]:
    manifest_document = _json_document(documents["manifest.json"])
    manifest = QuerySnapshotManifest.model_validate(manifest_document)
    crate_document = _json_document(documents["ro-crate-metadata.json"])
    crate = _crate_from_jsonld(crate_document, manifest)
    lineage_document = _json_document(documents["lineage.json"])
    lineage = ResearchLineageReceipt.model_validate(lineage_document)
    return manifest, crate, lineage


def _json_document(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=unique_json_object)
    except json.JSONDecodeError, UnicodeDecodeError, ValueError:
        raise ValueError("research export package JSON is invalid") from None
    if not isinstance(value, dict):
        raise TypeError("research export package JSON must be an object")
    return cast("dict[str, Any]", value)


def _crate_from_jsonld(
    document: dict[str, Any], manifest: QuerySnapshotManifest
) -> ResearchCrate:
    """Recover the typed crate model from its canonical RO-Crate document."""
    raw_graph = document.get("@graph")
    if document.get("@context") != "https://w3id.org/ro/crate/1.1/context":
        raise ValueError("research export RO-Crate graph is invalid")
    if not isinstance(raw_graph, list):
        raise TypeError("research export RO-Crate graph must be a list")
    graph = cast("list[Any]", raw_graph)
    if len(graph) < _MIN_CRATE_GRAPH_ITEMS:
        raise ValueError("research export RO-Crate graph is invalid")
    if not all(isinstance(item, dict) for item in graph):
        raise ValueError("research export RO-Crate graph is invalid")
    graph = cast("list[dict[str, Any]]", graph)
    dataset = graph[0]
    if dataset.get("@id") != "./" or dataset.get("@type") != "Dataset":
        raise ValueError("research export RO-Crate dataset is invalid")
    rows = graph[1:]
    identifiers = [_required_string(row, "@id") for row in rows]
    raw_distribution_ids = dataset.get("distribution")
    if not isinstance(raw_distribution_ids, list):
        raise TypeError("research export RO-Crate distributions must be a list")
    distribution_ids = cast("list[Any]", raw_distribution_ids)
    if not all(isinstance(item, str) for item in distribution_ids):
        raise ValueError("research export RO-Crate distributions are invalid")
    distribution_ids = cast("list[str]", distribution_ids)
    if identifiers != distribution_ids or len(identifiers) != len(
        set(identifiers)
    ):
        raise ValueError("research export RO-Crate distributions are invalid")
    distributions = tuple(
        CrateDistribution(
            identifier=_required_string(row, "@id"),
            name=_required_string(row, "name"),
            content_url=_required_string(row, "contentUrl"),
            media_type=_required_string(row, "encodingFormat"),
            sha256=_required_string(row, "sha256"),
        )
        for row in rows
        if row.get("@type") == "https://schema.org/DataDownload"
    )
    if len(distributions) != len(rows):
        raise ValueError("research export RO-Crate distribution is invalid")
    return build_research_crate(
        identifier=manifest_sha256(manifest),
        name=_required_string(dataset, "name"),
        version=_required_string(dataset, "version"),
        dataset_url=_required_string(dataset, "url"),
        distributions=distributions,
    )


def _required_string(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise TypeError(f"research export RO-Crate {key} must be text")
    return value
