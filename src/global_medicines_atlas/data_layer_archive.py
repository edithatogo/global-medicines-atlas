"""Inventory and package the no-credential data layer for archival."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Protocol

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import Field

from .models import FrozenModel
from .publication_transport import PublicationDestination, PublicationTarget
from .source_catalog import MedicineDataSource, load_source_catalog
from .source_profiles import AuthenticationMode

CATALOGUE_REPOSITORY = "edithatogo/global-medicines-atlas-catalogue"
CATALOGUE_PUBLIC_URL = (
    "https://huggingface.co/datasets/"
    "edithatogo/global-medicines-atlas-catalogue"
)
ARCHIVE_REVISION = "data-layer-archive-v1"
FIXTURE_PROVENANCE_NOTE = "representative_fixture_not_live_coverage"
MAX_ARCHIVAL_FILE_BYTES = 1_000_000
HF_TOKEN_SECRET_NAME = "HF_TOKEN"  # ruff: ignore[hardcoded-password-string]
RESTRICTED_PATH_PREFIXES = (
    "vendor/",
    "vendor/nzmedicines",
)
_SYNTHETIC_FIXTURES = (
    "tests/fixtures/global_adapters/canada.json",
    "tests/fixtures/global_adapters/european_union.json",
    "tests/fixtures/global_adapters/japan.json",
    "tests/fixtures/global_adapters/united_kingdom.json",
)
_EXTRA_PUBLIC_FIXTURES = ("tests/fixtures/rxnorm/manifest.json",)
_GOVERNED_FIXTURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("au-artg", ("tests/fixtures/adapters/au_artg.csv",)),
    ("au-pbs-historical-xml", ("tests/fixtures/adapters/au_pbs.xml",)),
    (
        "ca-dpd",
        (
            "tests/fixtures/native/ca/dpd_api.json",
            "tests/fixtures/native/ca/dpd_bulk.csv",
        ),
    ),
    ("ca-noc", ("tests/fixtures/native/ca/noc_extract.csv",)),
    ("eu-ema-medicines", ("tests/fixtures/native/eu/ema_medicines.csv",)),
    ("eu-union-register", ("tests/fixtures/native/eu/union_register.xml",)),
    ("gb-mhra-products", ("tests/fixtures/native/gb/mhra_products.csv",)),
    ("gb-nice-ta", ("tests/fixtures/native/gb/nice_appraisals.xml",)),
    ("jp-mhlw-nhi-price", ("tests/fixtures/native/jp/mhlw_nhi_prices.csv",)),
    ("jp-pmda-approvals", ("tests/fixtures/native/jp/pmda_approvals.csv",)),
    (
        "nz-medsafe-products",
        ("tests/fixtures/adapters/nz_medsafe_registry.csv",),
    ),
    (
        "nz-pharmac-schedule-xml",
        ("tests/fixtures/adapters/nz_pharmac_schedule.xml",),
    ),
    (
        "us-cms-partd-formulary",
        ("tests/fixtures/us/cms_partd_formulary.csv",),
    ),
    ("us-drugsfda", ("tests/fixtures/us/drugsfda_api.json",)),
    (
        "global-rxnorm",
        ("src/global_medicines_atlas/data/rxnorm_bootstrap.json",),
    ),
)
_CATALOG_RELATIVE = (
    "src/global_medicines_atlas/data/medicine_source_catalog.json"
)
_SCHEMA_RELATIVE = "schemas/international-resource-v5.json"
_CARD_RELATIVE = "docs/publication/huggingface-catalogue-card.md"
_IDENTITIES_RELATIVE = "quality/qualifications/publication-identities.json"
_RIGHTS_MATRIX_RELATIVE = (
    "quality/qualifications/source-rights-disposition.json"
)
_DATA_LICENSE_RELATIVE = "DATA_LICENSE.md"
_SOURCE_RIGHTS_RELATIVE = "docs/data-sources/SOURCE_RIGHTS.md"


class AccessClass(StrEnum):
    """Whether a source can be reached without credentials."""

    PUBLIC_NO_CREDENTIAL = "public_no_credential"
    CREDENTIAL_RESTRICTED = "credential_restricted"


class ArchivalDisposition(StrEnum):
    """What this archival may publish for one source."""

    CATALOG_AND_FIXTURE = "catalog_and_fixture"
    CATALOG_METADATA_ONLY = "catalog_metadata_only"


class HuggingFaceAuthError(RuntimeError):
    """Raised when Hugging Face identity cannot be resolved."""

    def __init__(self, message: str, *, missing_secret: str) -> None:
        super().__init__(message)
        self.missing_secret = missing_secret


class DatasetUploader(Protocol):
    """Upload a prepared folder and return a remote revision."""

    def upload_folder(
        self,
        *,
        repository: str,
        folder: Path,
        commit_message: str,
    ) -> str: ...


class SourceArchiveRow(FrozenModel):
    """One catalogued source and its archival classification."""

    source_id: str = Field(min_length=1)
    jurisdictions: str = Field(min_length=1)
    authority: str = Field(min_length=1)
    dimension: str = Field(min_length=1)
    authentication: str = Field(min_length=1)
    access_class: AccessClass
    rights_status: str = Field(min_length=1)
    interface_status: str = Field(min_length=1)
    integration_layer: str = Field(min_length=1)
    qualification_state: str = Field(min_length=1)
    archival_disposition: ArchivalDisposition
    skip_reason: str
    fixture_paths: str
    evidence_limit: str = Field(min_length=1)
    fixture_provenance: str


class DataLayerInventory(FrozenModel):
    """Complete, sorted inventory of the governed data layer."""

    schema_id: str = "global-medicines-atlas.data-layer-inventory"
    schema_version: int = 1
    generated_at: str
    public_no_credential_count: int = Field(ge=0)
    credential_restricted_count: int = Field(ge=0)
    sources: tuple[SourceArchiveRow, ...] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class ArchiveFile:
    """One packaged archival member."""

    relative_path: str
    content: bytes

    def read_text(self, encoding: str = "utf-8") -> str:
        """Decode UTF-8 archival text."""

        return self.content.decode(encoding)


@dataclass(frozen=True, slots=True)
class DataLayerArchivePackage:
    """Deterministic archival tree bound to the catalogue identity."""

    files: tuple[ArchiveFile, ...]
    target: PublicationTarget
    inventory: DataLayerInventory

    def file(self, path: str) -> ArchiveFile:
        """Return one packaged file by relative path."""

        for item in self.files:
            if item.relative_path == path:
                return item
        raise KeyError(path)


def classify_source_access(mode: AuthenticationMode) -> AccessClass:
    """Treat any non-public authentication as credential-restricted."""

    if mode is AuthenticationMode.NONE:
        return AccessClass.PUBLIC_NO_CREDENTIAL
    return AccessClass.CREDENTIAL_RESTRICTED


def assert_no_restricted_artifacts(
    relative_paths: tuple[str, ...],
    *,
    root: Path | None = None,
) -> None:
    """Reject licensed vendor trees and oversized payloads."""

    for relative_path in relative_paths:
        posix = PurePosixPath(relative_path)
        if posix.is_absolute() or ".." in posix.parts:
            raise ValueError(f"unsafe archival path: {relative_path}")
        if _is_restricted_path(relative_path):
            raise ValueError(f"restricted archival path: {relative_path}")
        if root is None:
            continue
        candidate = root / relative_path
        if candidate.is_file() and candidate.stat().st_size > (
            MAX_ARCHIVAL_FILE_BYTES
        ):
            raise ValueError(
                f"archival artifact exceeds {MAX_ARCHIVAL_FILE_BYTES} bytes: "
                f"{relative_path}"
            )


def inventory_data_layer(root: Path) -> DataLayerInventory:
    """Classify every catalog source without fetching live dumps."""

    fixture_index = _fixture_index()
    rows = tuple(
        _row_for_source(source, fixture_index, root)
        for source in load_source_catalog()
    )
    public = sum(
        1
        for row in rows
        if row.access_class is AccessClass.PUBLIC_NO_CREDENTIAL
    )
    restricted = len(rows) - public
    return DataLayerInventory(
        generated_at="2026-08-19",
        public_no_credential_count=public,
        credential_restricted_count=restricted,
        sources=rows,
    )


def build_data_layer_archive(
    root: Path, destination: Path
) -> DataLayerArchivePackage:
    """Materialise catalogue, inventory, and governed fixture bytes."""

    inventory = inventory_data_layer(root)
    members: dict[str, bytes] = {
        "README.md": _read_text(root, _CARD_RELATIVE),
        "medicine_source_catalog.json": _read_text(root, _CATALOG_RELATIVE),
        "international-resource-v5.json": _read_text(root, _SCHEMA_RELATIVE),
        "DATA_LICENSE.md": _read_text(root, _DATA_LICENSE_RELATIVE),
        "SOURCE_RIGHTS.md": _read_text(root, _SOURCE_RIGHTS_RELATIVE),
        "metadata/publication-identities.json": _read_text(
            root, _IDENTITIES_RELATIVE
        ),
        "metadata/source-rights-disposition.json": _read_text(
            root, _RIGHTS_MATRIX_RELATIVE
        ),
        "inventory/source-inventory.json": _canonical_json(
            inventory.model_dump(mode="json")
        ),
        "inventory/source-inventory.parquet": _inventory_parquet(inventory),
    }
    for relative_path, packaged_path in _eligible_fixture_copies(inventory):
        payload = (root / relative_path).read_bytes()
        if len(payload) > MAX_ARCHIVAL_FILE_BYTES:
            raise ValueError(
                f"archival artifact exceeds {MAX_ARCHIVAL_FILE_BYTES} bytes: "
                f"{relative_path}"
            )
        members[packaged_path] = payload
    skipped = tuple(
        row.source_id
        for row in inventory.sources
        if row.archival_disposition is ArchivalDisposition.CATALOG_METADATA_ONLY
    )
    members["inventory/archival-manifest.json"] = _canonical_json({
        "catalogue_repository": CATALOGUE_REPOSITORY,
        "fixture_provenance": FIXTURE_PROVENANCE_NOTE,
        "generated_at": inventory.generated_at,
        "live_source_dump_downloaded": False,
        "public_no_credential_count": inventory.public_no_credential_count,
        "credential_restricted_count": inventory.credential_restricted_count,
        "skipped_source_ids": list(skipped),
        "source_count": len(inventory.sources),
    })
    checksums = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {path}\n"
        for path, content in sorted(members.items())
    ).encode()
    members["SHA256SUMS"] = checksums
    assert_no_restricted_artifacts(tuple(sorted(members)))
    destination.mkdir(parents=True, exist_ok=True)
    files: list[ArchiveFile] = []
    for relative_path, content in sorted(members.items()):
        output = destination / relative_path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        files.append(ArchiveFile(relative_path, content))
    target = PublicationTarget(
        destination=PublicationDestination.HUGGING_FACE,
        repository=CATALOGUE_REPOSITORY,
        revision=ARCHIVE_REVISION,
        public_base_url=CATALOGUE_PUBLIC_URL,
    )
    return DataLayerArchivePackage(
        files=tuple(files),
        target=target,
        inventory=inventory,
    )


def resolve_huggingface_identity(
    environment: Mapping[str, str] | None = None,
) -> str:
    """Probe Hugging Face CLI identity without reading secret files."""

    env = dict(os.environ if environment is None else environment)
    attempts = (
        ("hf", "auth", "whoami"),
        ("huggingface-cli", "whoami"),
    )
    errors: list[str] = []
    for command in attempts:
        executable = shutil.which(command[0])
        if executable is None:
            errors.append(f"{command[0]}-missing")
            continue
        try:
            completed = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
                (executable, *command[1:]),
                check=True,
                capture_output=True,
                shell=False,
                text=True,
                env=env,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            errors.append(type(error).__name__)
            continue
        identity = completed.stdout.strip().splitlines()
        if identity:
            return identity[0]
        errors.append("empty-identity")
    if env.get(HF_TOKEN_SECRET_NAME):
        return "env-token-present"
    raise HuggingFaceAuthError(
        "Hugging Face identity is unavailable after three probes; "
        f"{HF_TOKEN_SECRET_NAME} is the missing secret",
        missing_secret=HF_TOKEN_SECRET_NAME,
    )


class HuggingFaceCliUploader:
    """Upload through the maintainer-authenticated Hugging Face CLI."""

    def upload_folder(
        self,
        *,
        repository: str,
        folder: Path,
        commit_message: str,
    ) -> str:
        """Upload a prepared folder and return the public revision."""

        resolve_huggingface_identity()
        attempts = (
            (
                "hf",
                "upload",
                repository,
                str(folder),
                ".",
                "--repo-type",
                "dataset",
                "--commit-message",
                commit_message,
            ),
            (
                "huggingface-cli",
                "upload",
                repository,
                str(folder),
                ".",
                "--repo-type",
                "dataset",
                "--commit-message",
                commit_message,
            ),
        )
        last_error: Exception | None = None
        for command in attempts:
            executable = shutil.which(command[0])
            if executable is None:
                last_error = FileNotFoundError(command[0])
                continue
            try:
                subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
                    (executable, *command[1:]),
                    check=True,
                    capture_output=True,
                    shell=False,
                    text=True,
                )
                last_error = None
                break
            except (OSError, subprocess.CalledProcessError) as error:
                last_error = error
        if last_error is not None:
            raise HuggingFaceAuthError(
                "Hugging Face upload failed after CLI attempts; "
                f"{HF_TOKEN_SECRET_NAME} is the missing secret",
                missing_secret=HF_TOKEN_SECRET_NAME,
            ) from last_error
        return _public_dataset_revision(repository)


def _public_dataset_revision(repository: str) -> str:
    response = httpx.get(
        f"https://huggingface.co/api/datasets/{repository}",
        headers={"Accept": "application/json"},
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    revision = payload.get("sha")
    if not isinstance(revision, str) or not revision.strip():
        raise HuggingFaceAuthError(
            "Hugging Face revision was not publicly observable",
            missing_secret=HF_TOKEN_SECRET_NAME,
        )
    return revision.strip()


def _row_for_source(
    source: MedicineDataSource,
    fixture_index: dict[str, tuple[str, ...]],
    root: Path,
) -> SourceArchiveRow:
    access = classify_source_access(source.authentication)
    fixtures = tuple(
        path
        for path in fixture_index.get(source.source_id, ())
        if not _is_restricted_path(path) and (root / path).is_file()
    )
    skip_reason = ""
    disposition = ArchivalDisposition.CATALOG_METADATA_ONLY
    if access is AccessClass.CREDENTIAL_RESTRICTED:
        if source.source_id == "nz-nzulm-bulk":
            skip_reason = "credentials_and_restricted_bytes"
        else:
            skip_reason = "credentials_required"
    elif fixtures:
        disposition = ArchivalDisposition.CATALOG_AND_FIXTURE
    return SourceArchiveRow(
        source_id=source.source_id,
        jurisdictions=",".join(source.jurisdictions),
        authority=source.authority,
        dimension=source.dimension.value,
        authentication=source.authentication.value,
        access_class=access,
        rights_status=source.rights_status,
        interface_status=source.interface_status.value,
        integration_layer=source.integration_layer.value,
        qualification_state=source.qualification_state.value,
        archival_disposition=disposition,
        skip_reason=skip_reason,
        fixture_paths=",".join(fixtures),
        evidence_limit=source.evidence_limit,
        fixture_provenance=FIXTURE_PROVENANCE_NOTE,
    )


def _fixture_index() -> dict[str, tuple[str, ...]]:
    indexed: dict[str, list[str]] = {}
    for source_id, paths in _GOVERNED_FIXTURES:
        indexed[source_id] = [
            path for path in paths if not _is_restricted_path(path)
        ]
    indexed.setdefault("global-rxnorm", [])
    indexed["global-rxnorm"].extend(_EXTRA_PUBLIC_FIXTURES)
    return {key: tuple(paths) for key, paths in indexed.items()}


def _eligible_fixture_copies(
    inventory: DataLayerInventory,
) -> tuple[tuple[str, str], ...]:
    copies: list[tuple[str, str]] = []
    for row in inventory.sources:
        if row.archival_disposition is not (
            ArchivalDisposition.CATALOG_AND_FIXTURE
        ):
            continue
        for relative_path in filter(None, row.fixture_paths.split(",")):
            name = PurePosixPath(relative_path).name
            copies.append((relative_path, f"fixtures/{row.source_id}/{name}"))
    for relative_path in _SYNTHETIC_FIXTURES:
        name = PurePosixPath(relative_path).name
        copies.append((relative_path, f"fixtures/synthetic/{name}"))
    return tuple(copies)


def _is_restricted_path(relative_path: str) -> bool:
    posix = relative_path.replace("\\", "/")
    return posix == "vendor" or posix.startswith("vendor/")


def _read_text(root: Path, relative_path: str) -> bytes:
    return (root / relative_path).read_bytes()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _inventory_parquet(inventory: DataLayerInventory) -> bytes:
    payload = [row.model_dump(mode="json") for row in inventory.sources]
    table = pa.Table.from_pylist(payload)
    table = table.replace_schema_metadata({
        b"schema_name": b"global-medicines-atlas.data-layer-inventory",
        b"schema_version": b"1",
        b"fixture_provenance": FIXTURE_PROVENANCE_NOTE.encode(),
    })
    sink = pa.BufferOutputStream()
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        table,
        sink,
        compression="zstd",
        compression_level=9,
        data_page_version="2.0",
        use_dictionary=False,
        write_page_index=False,
        write_statistics=True,
        version="2.6",
    )
    return sink.getvalue().to_pybytes()
