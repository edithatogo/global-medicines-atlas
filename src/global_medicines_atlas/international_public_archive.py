"""Build an exact-manifest public international source archive."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Final

from pydantic import Field, model_validator

from .models import FrozenModel

SOURCE_RIGHTS: Final = {
    "eu-union-register": "CC-BY-4.0",
    "fr-bdpm": "Etalab-2.0",
    "fr-bdpm-smr-asmr": "Etalab-2.0",
    "gb-emit": "OGL-3.0",
    "gb-nhs-drug-tariff": "OGL-3.0-with-exclusions",
    "gb-nice-medicines-utilisation": "OGL-3.0",
    "nz-pharmac-hml": "CC-BY-4.0",
    "nz-pharmac-schedule": "CC-BY-4.0",
    "nz-pharmac-schedule-xml": "CC-BY-4.0",
    "global-rxnorm": "NLM-created-RXCUI-identifiers-only",
    "us-rxnorm-api": "NLM-created-RXCUI-identifiers-only",
}
PENDING_SOURCES: Final = {
    "fr-open-medic": "upstream download-limit refusal",
    "nl-gipdatabank": "manual interactive export not reproducibly resolved",
}
RXNORM_INPUT_SHA256: Final = (
    "4ff92e469f5d188ac6f3e52a64ea78811a6f5206d6f603843258bed8cd6287f3"
)


class InternationalArchiveFile(FrozenModel):
    source_id: str
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)
    rights: str


class InternationalPublicArchiveManifest(FrozenModel):
    schema_id: str = "global-medicines-atlas.international-public-archive"
    schema_version: int = 1
    archived_source_count: int
    files: tuple[InternationalArchiveFile, ...]
    pending_sources: dict[str, str]
    rxnorm_input_sha256: str = RXNORM_INPUT_SHA256
    coverage_complete: bool = False

    @model_validator(mode="after")
    def source_sets_are_exact(
        self,
    ) -> InternationalPublicArchiveManifest:
        archived = {item.source_id for item in self.files}
        if archived != set(SOURCE_RIGHTS):
            raise ValueError("archive must cover each acquired source")
        if set(self.pending_sources) != set(PENDING_SOURCES):
            raise ValueError("pending source set must remain explicit")
        if self.archived_source_count != len(SOURCE_RIGHTS):
            raise ValueError("archived source count is inconsistent")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_international_public_archive(
    staging: Path, output: Path
) -> InternationalPublicArchiveManifest:
    """Package source bytes and the identifiers-only RxNorm projection."""

    if output.exists():
        raise FileExistsError(output)
    (output / "data").mkdir(parents=True)
    files: list[InternationalArchiveFile] = []
    for source_id, rights in sorted(SOURCE_RIGHTS.items()):
        source_dir = (
            staging / "rxnorm-identifiers"
            if source_id in {"global-rxnorm", "us-rxnorm-api"}
            else staging / source_id
        )
        candidates = tuple(
            path for path in sorted(source_dir.iterdir()) if path.is_file()
        )
        if not candidates:
            raise ValueError(f"no acquired files for {source_id}")
        target_dir = output / "data" / source_id
        target_dir.mkdir()
        for source in candidates:
            if (
                source_id in {"global-rxnorm", "us-rxnorm-api"}
                and source.name != "rxcui-identifiers.json"
            ):
                raise ValueError(
                    "RxNorm source vocabulary content is prohibited"
                )
            target = target_dir / source.name
            shutil.copyfile(source, target)
            files.append(
                InternationalArchiveFile(
                    source_id=source_id,
                    path=target.relative_to(output).as_posix(),
                    sha256=_sha256(target),
                    byte_count=target.stat().st_size,
                    rights=rights,
                )
            )
    manifest = InternationalPublicArchiveManifest(
        archived_source_count=len(SOURCE_RIGHTS),
        files=tuple(files),
        pending_sources=PENDING_SOURCES,
    )
    (output / "manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (output / "README.md").write_text(_dataset_card(), encoding="utf-8")
    return manifest


def _dataset_card() -> str:
    return """---
license: other
pretty_name: Global Medicines Atlas permissive international snapshots
tags:
- medicines
- regulatory
- open-data
---

# Permissive international medicine-source snapshots

This mixed-licence archive contains bounded source-native snapshots for eleven
catalogue source IDs. Rights and attribution are recorded per file in
`manifest.json`; users must comply with CC BY 4.0, Etalab Open Licence 2.0,
Open Government Licence 3.0, and source-specific exclusions.

RxNorm content is limited to NLM-created RXCUI identifiers. Source vocabulary
names and bytes are excluded. The NHS Drug Tariff must not be used to imply NHS
endorsement; separately licensed dm+d/SNOMED content is not licensed by this
archive.

Two permissive candidates remain explicit acquisition failures rather than
false archives: Open Medic 2025 was refused by the upstream download limiter,
and GIP requires an unresolved manual export. This is not complete source
coverage.
"""
