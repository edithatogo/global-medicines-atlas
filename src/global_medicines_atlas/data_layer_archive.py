"""Inventory and package the no-credential data layer for archival."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Protocol
from urllib.parse import urlsplit

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import Field

from .adapters.us_acquisition import DRUGSFDA_API_URL, DRUGSFDA_BULK_URL
from .models import FrozenModel
from .publication_transport import PublicationDestination, PublicationTarget
from .source_catalog import MedicineDataSource, load_source_catalog
from .source_profiles import AuthenticationMode

CATALOGUE_REPOSITORY = "edithatogo/global-medicines-atlas-catalogue"
CATALOGUE_PUBLIC_URL = (
    "https://huggingface.co/datasets/"
    "edithatogo/global-medicines-atlas-catalogue"
)
ARCHIVE_REVISION = "data-layer-archive-v2"
ARCHIVE_WORKFLOW_RELATIVE = ".github/workflows/data-layer-archive.yml"
FIXTURE_PROVENANCE_NOTE = "representative_fixture_not_live_coverage"
LIVE_PUBLIC_PROVENANCE_NOTE = "live_public_artefact"
MAX_ARCHIVAL_FILE_BYTES = 1_000_000
MAX_LIVE_PAYLOAD_BYTES = 32 * 1024 * 1024
LIVE_RETRIEVAL_ATTEMPTS = 3
HTTP_CLIENT_ERROR_STATUS = 400
HF_TOKEN_SECRET_NAME = "HF_TOKEN"  # ruff: ignore[hardcoded-password-string]
HUGGINGFACE_EXTERNAL_GATE_FILENAME = "huggingface-external-gate.json"
HUGGINGFACE_HUB_PIN = "huggingface-hub==0.34.4"
ADAPTER_ALIASES = {
    "eu-ema-medicines": "eu-ema",
    "nz-medsafe-products": "nz-medsafe",
}
GOVERNED_BULK_URIS: dict[str, tuple[str, ...]] = {
    "us-drugsfda": (DRUGSFDA_BULK_URL, DRUGSFDA_API_URL),
}
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
    CATALOG_AND_LIVE_PAYLOAD = "catalog_and_live_payload"
    CATALOG_METADATA_ONLY = "catalog_metadata_only"


class AuthorityGroup(StrEnum):
    """Maintainer-scoped archival authorities."""

    FDA = "fda"
    EMA = "ema"
    TGA = "tga"
    MEDSAFE = "medsafe"
    OTHER = "other"


class PayloadKind(StrEnum):
    """How a scoped source payload was obtained."""

    NONE = "none"
    LIVE_PUBLIC = "live_public"
    REPRESENTATIVE_FIXTURE = "representative_fixture"
    METADATA_ONLY = "metadata_only"


SCOPED_AUTHORITY_GROUPS = frozenset({
    AuthorityGroup.FDA,
    AuthorityGroup.EMA,
    AuthorityGroup.TGA,
    AuthorityGroup.MEDSAFE,
})


class HuggingFaceAuthError(RuntimeError):
    """Raised when Hugging Face identity cannot be resolved."""

    def __init__(self, message: str, *, missing_secret: str) -> None:
        super().__init__(message)
        self.missing_secret = missing_secret


def huggingface_external_gate_stdout(record_name: str) -> dict[str, str]:
    """CLI payload that names a record file without logging secret fields."""

    return {
        "state": "blocked",
        "record": record_name,
        "reason": "huggingface-identity-unresolved",
    }


def write_huggingface_external_gate(directory: Path) -> Path:
    """Persist the named missing secret without printing exception secrets."""

    directory.mkdir(parents=True, exist_ok=True)
    output = directory / HUGGINGFACE_EXTERNAL_GATE_FILENAME
    output.write_text(
        json.dumps(
            {
                "state": "blocked",
                "missing_secret_name": HF_TOKEN_SECRET_NAME,
                "reason": "huggingface-identity-unresolved",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


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
    authority_group: AuthorityGroup
    dimension: str = Field(min_length=1)
    authentication: str = Field(min_length=1)
    access_class: AccessClass
    rights_status: str = Field(min_length=1)
    interface_status: str = Field(min_length=1)
    integration_layer: str = Field(min_length=1)
    qualification_state: str = Field(min_length=1)
    archival_disposition: ArchivalDisposition
    payload_kind: PayloadKind
    skip_reason: str
    fixture_paths: str
    evidence_limit: str = Field(min_length=1)
    fixture_provenance: str
    retrieval_uri: str = ""
    retrieved_at: str = ""
    payload_sha256: str = ""
    live_attempts: int = Field(default=0, ge=0)
    adapter_alias: str = ""


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
class RetrievedPayload:
    """Result of one public payload retrieval attempt series."""

    source_id: str
    uri: str
    content: bytes
    content_type: str
    retrieved_at: str
    attempts: int
    sha256: str
    kind: PayloadKind
    skip_reason: str
    filename: str = "public-artefact.bin"


class PayloadRetriever(Protocol):
    """Fetch one public source artefact without credentials."""

    def retrieve(self, source: MedicineDataSource) -> RetrievedPayload: ...


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


def classify_authority_group(source: MedicineDataSource) -> AuthorityGroup:
    """Map a catalog source to a scoped archival authority."""

    authority = source.authority.casefold()
    source_id = source.source_id
    jurisdictions = tuple(source.jurisdictions)
    if jurisdictions == ("USA",) and (
        "food and drug administration" in authority or "us fda" in authority
    ):
        return AuthorityGroup.FDA
    if source_id.startswith((
        "us-drugsfda",
        "us-fda-",
        "us-openfda-",
        "us-gsrs-",
    )):
        return AuthorityGroup.FDA
    if (
        authority == "european medicines agency"
        or source_id.startswith("eu-ema-")
        or source_id in {"eu-union-register", "eu-spor-rms-oms"}
    ):
        return AuthorityGroup.EMA
    if (
        authority == "therapeutic goods administration"
        or source_id.startswith("au-tga-")
        or source_id == "au-artg"
    ):
        return AuthorityGroup.TGA
    if authority == "medsafe" or source_id.startswith("nz-medsafe-"):
        return AuthorityGroup.MEDSAFE
    return AuthorityGroup.OTHER


def retrieval_uris_for_source(source: MedicineDataSource) -> tuple[str, ...]:
    """Return catalog and already-governed public retrieval URIs."""

    uris: list[str] = []
    candidates = (
        *GOVERNED_BULK_URIS.get(source.source_id, ()),
        None if source.download_url is None else str(source.download_url),
        None if source.api_url is None else str(source.api_url),
        str(source.landing_page),
    )
    for uri in candidates:
        if uri and uri not in uris:
            uris.append(uri)
    return tuple(uris)


def parse_authority_groups(raw: str) -> frozenset[AuthorityGroup]:
    """Parse a CLI authority list into scoped groups."""

    groups: list[AuthorityGroup] = []
    for part in raw.split(","):
        token = part.strip().casefold()
        if not token:
            continue
        groups.append(AuthorityGroup(token))
    selected = frozenset(groups)
    if not selected:
        return SCOPED_AUTHORITY_GROUPS
    unknown = selected - SCOPED_AUTHORITY_GROUPS
    if unknown:
        names = ", ".join(sorted(item.value for item in unknown))
        raise ValueError(f"unsupported archival authority: {names}")
    return selected


class HttpPayloadRetriever:
    """HTTPS retriever for public catalog surfaces."""

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        max_bytes: int = MAX_LIVE_PAYLOAD_BYTES,
        max_attempts: int = LIVE_RETRIEVAL_ATTEMPTS,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._max_bytes = max_bytes
        self._max_attempts = max_attempts
        self._timeout_seconds = timeout_seconds

    def retrieve(self, source: MedicineDataSource) -> RetrievedPayload:
        """Fetch the first successful public URI, else label a fixture."""

        retrieved_at = self._clock().isoformat()
        last_reason = "live_retrieval_failed_after_3_attempts"
        attempts = 0
        for uri in retrieval_uris_for_source(source):
            if not _uri_is_allowed(uri, source):
                last_reason = "host_not_in_catalog"
                continue
            for _attempt in range(1, self._max_attempts + 1):
                attempts += 1
                result = self._download(source.source_id, uri, retrieved_at)
                if result is None:
                    last_reason = "live_retrieval_failed_after_3_attempts"
                    continue
                if result.kind is PayloadKind.LIVE_PUBLIC:
                    return result
                last_reason = result.skip_reason
                return result
        return RetrievedPayload(
            source_id=source.source_id,
            uri=retrieval_uris_for_source(source)[0],
            content=b"",
            content_type="application/octet-stream",
            retrieved_at=retrieved_at,
            attempts=max(attempts, self._max_attempts),
            sha256="",
            kind=PayloadKind.REPRESENTATIVE_FIXTURE,
            skip_reason=last_reason,
        )

    def _download(
        self,
        source_id: str,
        uri: str,
        retrieved_at: str,
    ) -> RetrievedPayload | None:
        headers = {
            "User-Agent": (
                "GlobalMedicinesAtlas-archival/1 "
                "(https://github.com/edithatogo/global-medicines-atlas)"
            )
        }
        try:
            payload, content_type = self._get_bytes(uri, headers)
        except httpx.HTTPError, ValueError, OSError:
            return None
        if content_type == "live_file_too_large":
            return _failed_payload(
                source_id,
                uri,
                retrieved_at,
                1,
                "live_file_too_large",
            )
        if payload is None:
            return None
        filename = PurePosixPath(urlsplit(uri).path).name or (
            "public-artefact.bin"
        )
        if "." not in filename:
            filename = "public-artefact.bin"
        return RetrievedPayload(
            source_id=source_id,
            uri=uri,
            content=payload,
            content_type=content_type.split(";", 1)[0].strip(),
            retrieved_at=retrieved_at,
            attempts=1,
            sha256=hashlib.sha256(payload).hexdigest(),
            kind=PayloadKind.LIVE_PUBLIC,
            skip_reason="",
            filename=filename,
        )

    def _get_bytes(
        self, uri: str, headers: dict[str, str]
    ) -> tuple[bytes | None, str]:
        with (
            httpx.Client(
                transport=self._transport,
                follow_redirects=True,
                timeout=self._timeout_seconds,
                headers=headers,
            ) as client,
            client.stream("GET", uri) as response,
        ):
            if response.status_code >= HTTP_CLIENT_ERROR_STATUS:
                return None, ""
            content_type = response.headers.get(
                "content-type", "application/octet-stream"
            )
            length = response.headers.get("content-length")
            if length is not None and int(length) > self._max_bytes:
                return None, "live_file_too_large"
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > self._max_bytes:
                    return None, "live_file_too_large"
                chunks.append(chunk)
            return b"".join(chunks), content_type


def _failed_payload(
    source_id: str,
    uri: str,
    retrieved_at: str,
    attempts: int,
    skip_reason: str,
) -> RetrievedPayload:
    return RetrievedPayload(
        source_id=source_id,
        uri=uri,
        content=b"",
        content_type="application/octet-stream",
        retrieved_at=retrieved_at,
        attempts=attempts,
        sha256="",
        kind=PayloadKind.REPRESENTATIVE_FIXTURE,
        skip_reason=skip_reason,
    )


def _uri_is_allowed(uri: str, source: MedicineDataSource) -> bool:
    parsed = urlsplit(uri)
    if parsed.scheme.lower() != "https" or parsed.hostname is None:
        return False
    allowed = {urlsplit(str(source.landing_page)).hostname}
    if source.download_url is not None:
        allowed.add(urlsplit(str(source.download_url)).hostname)
    if source.api_url is not None:
        allowed.add(urlsplit(str(source.api_url)).hostname)
    allowed.update(
        urlsplit(extra).hostname
        for extra in GOVERNED_BULK_URIS.get(source.source_id, ())
    )
    return parsed.hostname.lower() in {host.lower() for host in allowed if host}


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


def inventory_data_layer(
    root: Path,
    *,
    retrieved: Mapping[str, RetrievedPayload] | None = None,
) -> DataLayerInventory:
    """Classify every catalog source without fetching live dumps."""

    fixture_index = _fixture_index()
    payloads = {} if retrieved is None else dict(retrieved)
    rows = tuple(
        _row_for_source(
            source,
            fixture_index,
            root,
            payloads.get(source.source_id),
        )
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
    root: Path,
    destination: Path,
    *,
    retriever: PayloadRetriever | None = None,
    authority_groups: frozenset[AuthorityGroup] | None = None,
) -> DataLayerArchivePackage:
    """Materialise catalogue, inventory, payloads, and governed fixtures."""

    scoped = (
        SCOPED_AUTHORITY_GROUPS
        if authority_groups is None
        else authority_groups
    )
    catalog = load_source_catalog()
    retrieved: dict[str, RetrievedPayload] = {}
    if retriever is not None:
        for source in catalog:
            group = classify_authority_group(source)
            if group not in scoped:
                continue
            if classify_source_access(source.authentication) is (
                AccessClass.CREDENTIAL_RESTRICTED
            ):
                continue
            retrieved[source.source_id] = retriever.retrieve(source)
    inventory = inventory_data_layer(root, retrieved=retrieved)
    members = _archive_members(root, catalog, inventory, retrieved, scoped)
    checksums = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {path}\n"
        for path, content in sorted(members.items())
    ).encode()
    members["SHA256SUMS"] = checksums
    assert_no_restricted_artifacts(tuple(sorted(members)))
    files = _write_members(destination, members)
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


def _archive_members(
    root: Path,
    catalog: tuple[MedicineDataSource, ...],
    inventory: DataLayerInventory,
    retrieved: Mapping[str, RetrievedPayload],
    scoped: frozenset[AuthorityGroup],
) -> dict[str, bytes]:
    catalog_by_id = {item.source_id: item for item in catalog}
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
    }
    for row in inventory.sources:
        if row.authority_group not in scoped:
            continue
        payload = retrieved.get(row.source_id)
        members[f"metadata/sources/{row.source_id}.json"] = _source_metadata(
            catalog_by_id[row.source_id], row, payload
        )
        if payload is not None and payload.kind is PayloadKind.LIVE_PUBLIC:
            name = payload.filename
            members[f"payloads/{row.source_id}/{name}"] = payload.content
    for relative_path, packaged_path in _eligible_fixture_copies(inventory):
        payload_bytes = (root / relative_path).read_bytes()
        if len(payload_bytes) > MAX_ARCHIVAL_FILE_BYTES:
            raise ValueError(
                f"archival artifact exceeds {MAX_ARCHIVAL_FILE_BYTES} bytes: "
                f"{relative_path}"
            )
        members[packaged_path] = payload_bytes
    skipped = [
        row.source_id
        for row in inventory.sources
        if row.archival_disposition is ArchivalDisposition.CATALOG_METADATA_ONLY
        or row.skip_reason
    ]
    live_ids = [
        row.source_id
        for row in inventory.sources
        if row.payload_kind is PayloadKind.LIVE_PUBLIC
    ]
    members["inventory/source-inventory.json"] = _canonical_json(
        inventory.model_dump(mode="json")
    )
    members["inventory/source-inventory.parquet"] = _inventory_parquet(
        inventory
    )
    members["inventory/archival-manifest.json"] = _canonical_json({
        "authority_groups": sorted(group.value for group in scoped),
        "catalogue_repository": CATALOGUE_REPOSITORY,
        "credential_restricted_count": inventory.credential_restricted_count,
        "fixture_provenance": FIXTURE_PROVENANCE_NOTE,
        "generated_at": inventory.generated_at,
        "live_payload_source_ids": live_ids,
        "live_source_dump_downloaded": bool(live_ids),
        "public_no_credential_count": inventory.public_no_credential_count,
        "publisher": "github-actions",
        "skipped_source_ids": skipped,
        "source_count": len(inventory.sources),
        "workflow": ARCHIVE_WORKFLOW_RELATIVE,
    })
    return members


def _write_members(
    destination: Path, members: Mapping[str, bytes]
) -> list[ArchiveFile]:
    destination.mkdir(parents=True, exist_ok=True)
    files: list[ArchiveFile] = []
    for relative_path, content in sorted(members.items()):
        output = destination / relative_path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        files.append(ArchiveFile(relative_path, content))
    return files


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
    retrieved: RetrievedPayload | None = None,
) -> SourceArchiveRow:
    access = classify_source_access(source.authentication)
    fixtures = tuple(
        path
        for path in fixture_index.get(source.source_id, ())
        if not _is_restricted_path(path) and (root / path).is_file()
    )
    skip_reason = ""
    disposition = ArchivalDisposition.CATALOG_METADATA_ONLY
    payload_kind = PayloadKind.NONE
    fixture_provenance = FIXTURE_PROVENANCE_NOTE
    retrieval_uri = ""
    retrieved_at = ""
    payload_sha256 = ""
    live_attempts = 0
    if access is AccessClass.CREDENTIAL_RESTRICTED:
        payload_kind = PayloadKind.METADATA_ONLY
        if source.source_id == "nz-nzulm-bulk":
            skip_reason = "credentials_and_restricted_bytes"
        else:
            skip_reason = "credentials_required"
    elif retrieved is not None and retrieved.kind is PayloadKind.LIVE_PUBLIC:
        disposition = ArchivalDisposition.CATALOG_AND_LIVE_PAYLOAD
        payload_kind = PayloadKind.LIVE_PUBLIC
        fixture_provenance = LIVE_PUBLIC_PROVENANCE_NOTE
        retrieval_uri = retrieved.uri
        retrieved_at = retrieved.retrieved_at
        payload_sha256 = retrieved.sha256
        live_attempts = retrieved.attempts
    elif retrieved is not None:
        payload_kind = PayloadKind.REPRESENTATIVE_FIXTURE
        skip_reason = retrieved.skip_reason
        live_attempts = retrieved.attempts
        retrieval_uri = retrieved.uri
        retrieved_at = retrieved.retrieved_at
        if fixtures:
            disposition = ArchivalDisposition.CATALOG_AND_FIXTURE
    elif fixtures:
        disposition = ArchivalDisposition.CATALOG_AND_FIXTURE
        payload_kind = PayloadKind.REPRESENTATIVE_FIXTURE
    return SourceArchiveRow(
        source_id=source.source_id,
        jurisdictions=",".join(source.jurisdictions),
        authority=source.authority,
        authority_group=classify_authority_group(source),
        dimension=source.dimension.value,
        authentication=source.authentication.value,
        access_class=access,
        rights_status=source.rights_status,
        interface_status=source.interface_status.value,
        integration_layer=source.integration_layer.value,
        qualification_state=source.qualification_state.value,
        archival_disposition=disposition,
        payload_kind=payload_kind,
        skip_reason=skip_reason,
        fixture_paths=",".join(fixtures),
        evidence_limit=source.evidence_limit,
        fixture_provenance=fixture_provenance,
        retrieval_uri=retrieval_uri,
        retrieved_at=retrieved_at,
        payload_sha256=payload_sha256,
        live_attempts=live_attempts,
        adapter_alias=ADAPTER_ALIASES.get(source.source_id, ""),
    )


def _source_metadata(
    source: MedicineDataSource,
    row: SourceArchiveRow,
    payload: RetrievedPayload | None,
) -> bytes:
    return _canonical_json({
        "adapter_alias": row.adapter_alias or None,
        "api_url": None if source.api_url is None else str(source.api_url),
        "authentication": row.authentication,
        "authority": row.authority,
        "authority_group": row.authority_group.value,
        "dimension": row.dimension,
        "documentation_url": str(source.documentation_url),
        "download_url": (
            None if source.download_url is None else str(source.download_url)
        ),
        "evidence_limit": row.evidence_limit,
        "formats": list(source.formats),
        "jurisdictions": list(source.jurisdictions),
        "landing_page": str(source.landing_page),
        "licence_or_rights": row.rights_status,
        "live_attempts": row.live_attempts,
        "native_identifier": source.native_identifier,
        "payload_bytes": 0 if payload is None else len(payload.content),
        "payload_kind": row.payload_kind.value,
        "payload_sha256": row.payload_sha256 or None,
        "retrieval_uri": row.retrieval_uri or None,
        "retrieved_at": row.retrieved_at or None,
        "rights_status": row.rights_status,
        "schema_notes": (
            "Source-native identifiers and dimension are preserved; "
            "regulatory, funding, formulary, and terminology stay independent."
        ),
        "skip_reason": row.skip_reason or None,
        "source_id": row.source_id,
    })


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
