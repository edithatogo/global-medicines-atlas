"""Compose deterministic, metadata-only research export archives.

The archive binds a query snapshot manifest, RO-Crate, Croissant metadata,
and lineage receipt. Referenced source and result objects remain in their
governed data-plane locations and are never copied into the package.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from .research_exports import (
    QuerySnapshotManifest,
    canonical_manifest_bytes,
    manifest_sha256,
)
from .research_lineage import ResearchLineageReceipt
from .research_package import ResearchCrate


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

    input_digests = {
        artifact.sha256
        for artifact in lineage.artifacts
        if artifact.role == "input"
    }
    source_digests = {source.sha256 for source in manifest.sources}
    if not source_digests <= input_digests:
        raise ValueError(
            "lineage inputs must bind every manifest source digest"
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
