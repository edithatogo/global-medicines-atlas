"""Fail-closed inventory contracts for CMS Medicare Part D public data."""

from __future__ import annotations

import json
import stat
import tarfile
import zipfile
from datetime import date
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Literal, cast

from pydantic import AnyHttpUrl, Field, model_validator

from .models import FrozenModel

_CMS_HOST = "data.cms.gov"
_GOVERNMENT_WORKS = "https://www.usa.gov/government-works"
_CMS_ZIP_MAX_ENTRIES = 10_000
_CMS_ZIP_MAX_MEMBER_BYTES = 100 * 1024**3
_CMS_ZIP_MAX_EXPANDED_BYTES = 200 * 1024**3
_CMS_ZIP_MAX_RATIO = 200
_ZIP_UNIX_SYSTEM = 3
_STREAM_CHUNK_BYTES = 8 * 1024**2


class CMSPartDAuthorization(FrozenModel):
    """Maintainer authority binding both Prompt 31 CMS data families."""

    schema_id: Literal[
        "global-medicines-atlas.cms-partd-acquisition-authorization"
    ]
    schema_version: Literal[1]
    decision_date: date | None
    decision_status: Literal["pending", "approved_internal", "approved_public"]
    decision_basis: str = Field(min_length=1)
    acquisition_authorized: bool
    internal_retention_authorized: bool
    public_release_authorized: bool
    external_publication_authorized: bool
    formulary_catalog_url: AnyHttpUrl
    spending_catalog_url: AnyHttpUrl
    agreement_url: AnyHttpUrl
    license_url: AnyHttpUrl
    expected_formulary_release_count: Literal[30]
    expected_formulary_url_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_spending_resource_count: Literal[3]
    expected_spending_url_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_scope(self) -> CMSPartDAuthorization:
        urls = (
            self.formulary_catalog_url,
            self.spending_catalog_url,
            self.agreement_url,
        )
        if any(url.host not in {_CMS_HOST, "catalog.data.gov"} for url in urls):
            raise ValueError("CMS Part D evidence must stay on official hosts")
        if str(self.license_url).rstrip("/") != _GOVERNMENT_WORKS:
            raise ValueError("CMS Part D licence identity drifted")
        if self.decision_status == "pending":
            if (
                self.decision_date is not None
                or self.acquisition_authorized
                or self.internal_retention_authorized
                or self.public_release_authorized
                or self.external_publication_authorized
            ):
                raise ValueError(
                    "pending CMS Part D decision cannot authorize payloads"
                )
        elif self.decision_status == "approved_internal" and not all((
            self.decision_date is not None,
            self.acquisition_authorized,
            self.internal_retention_authorized,
            not self.public_release_authorized,
            not self.external_publication_authorized,
        )):
            raise ValueError(
                "approved CMS Part D acquisition requires dated authority"
            )
        elif self.decision_status == "approved_public" and not all((
            self.decision_date is not None,
            self.acquisition_authorized,
            self.internal_retention_authorized,
            self.public_release_authorized,
            self.external_publication_authorized,
        )):
            raise ValueError(
                "approved public CMS Part D authority requires acquisition, "
                "retention, release, and publication"
            )
        return self

    def require_payload_authority(self) -> None:
        """Raise unless internal acquisition and retention are approved."""
        if self.decision_status not in {"approved_internal", "approved_public"}:
            raise PermissionError(
                "CMS Part D payload acquisition decision is pending"
            )

    def require_publication_authority(self) -> None:
        """Raise unless public release and external publication are approved."""
        if (
            self.decision_status != "approved_public"
            or not self.public_release_authorized
            or not self.external_publication_authorized
        ):
            raise PermissionError("CMS Part D publication is not authorized")


class CMSPartDInventory(FrozenModel):
    """Exact current public resource inventory, without source payloads."""

    formulary_release_count: int
    formulary_urls: tuple[AnyHttpUrl, ...]
    spending_resource_count: int
    spending_urls: tuple[AnyHttpUrl, ...]


class CMSPartDArchiveMember(FrozenModel):
    """One source-native file retained inside a formulary release ZIP."""

    path: str = Field(min_length=1)
    byte_count: int = Field(ge=0)
    compressed_byte_count: int = Field(ge=0)
    crc32: str = Field(pattern=r"^[0-9a-f]{8}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CMSPartDPayloadEvidence(FrozenModel):
    """Streaming evidence for one exact CMS inventory payload."""

    url: AnyHttpUrl
    family: Literal["formulary", "spending"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)
    archive_members: tuple[CMSPartDArchiveMember, ...] = ()


class _JSONLD(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._active = False
        self._chunks: list[str] = []
        self.documents: list[dict[str, object]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() == "script" and dict(attrs).get("type") == (
            "application/ld+json"
        ):
            self._active = True
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._active:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._active:
            value = cast("object", json.loads("".join(self._chunks)))
            if isinstance(value, dict):
                self.documents.append(cast("dict[str, object]", value))
            self._active = False


def _resource_urls(payload: bytes) -> tuple[AnyHttpUrl, ...]:
    parser = _JSONLD()
    parser.feed(payload.decode("utf-8"))
    datasets = [
        item for item in parser.documents if item.get("@type") == "Dataset"
    ]
    if len(datasets) != 1:
        raise ValueError("expected one CMS Part D Dataset JSON-LD document")
    dataset = datasets[0]
    if dataset.get("license") != _GOVERNMENT_WORKS:
        raise ValueError("CMS Part D catalogue licence drifted")
    distributions = dataset.get("distribution")
    if not isinstance(distributions, list):
        raise TypeError("CMS Part D catalogue distributions are missing")
    urls: list[AnyHttpUrl] = []
    for distribution_value in cast("list[object]", distributions):
        if not isinstance(distribution_value, dict):
            raise TypeError("CMS Part D distribution must be an object")
        distribution = cast("dict[str, object]", distribution_value)
        raw_url = distribution.get("contentUrl")
        if not isinstance(raw_url, str):
            raise TypeError("CMS Part D distribution URL is missing")
        url = AnyHttpUrl(raw_url)
        if url.host != _CMS_HOST:
            raise ValueError(
                "CMS Part D distributions must stay on data.cms.gov"
            )
        urls.append(url)
    return tuple(sorted(urls, key=str))


def _digest(urls: tuple[AnyHttpUrl, ...]) -> str:
    return sha256(
        ("\n".join(str(url) for url in urls) + "\n").encode()
    ).hexdigest()


def _path_digest(path: Path) -> tuple[str, int]:
    digest = sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count


def _validate_cms_zip_info(
    info: zipfile.ZipInfo,
    *,
    observed: set[str],
    total_expanded_bytes: int,
) -> tuple[str, int]:
    member_path = _safe_member_path(info.filename)
    if member_path in observed:
        raise ValueError("CMS Part D archive contains duplicate member paths")
    observed.add(member_path)
    if info.flag_bits & 0x1:
        raise ValueError("CMS Part D archive contains an encrypted member")
    if info.create_system == _ZIP_UNIX_SYSTEM and stat.S_ISLNK(
        info.external_attr >> 16
    ):
        raise ValueError("CMS Part D archive contains a symbolic link")
    if info.file_size > _CMS_ZIP_MAX_MEMBER_BYTES:
        raise ValueError("CMS Part D archive member byte limit exceeded")
    total_expanded_bytes += info.file_size
    if total_expanded_bytes > _CMS_ZIP_MAX_EXPANDED_BYTES:
        raise ValueError("CMS Part D archive expanded byte limit exceeded")
    if (info.file_size > 0 and info.compress_size == 0) or (
        info.compress_size > 0
        and info.file_size / info.compress_size > _CMS_ZIP_MAX_RATIO
    ):
        raise ValueError("CMS Part D archive decompression ratio exceeded")
    return member_path, total_expanded_bytes


def _stream_cms_zip_member(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo
) -> str:
    digest = sha256()
    expanded_bytes = 0
    with archive.open(info) as member:
        while block := member.read(_STREAM_CHUNK_BYTES):
            expanded_bytes += len(block)
            if expanded_bytes > info.file_size:
                raise ValueError(
                    "CMS Part D archive member exceeded declared size"
                )
            digest.update(block)
    if expanded_bytes != info.file_size:
        raise ValueError("CMS Part D archive member size diverged")
    return digest.hexdigest()


def _safe_member_path(name: str) -> str:
    normalized = name.replace("\\", "/")
    member = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or ".." in member.parts
        or (member.parts and ":" in member.parts[0])
    ):
        raise ValueError("CMS Part D archive contains an unsafe member path")
    return normalized


def inspect_cms_partd_payload(
    path: Path,
    *,
    url: AnyHttpUrl,
    family: Literal["formulary", "spending"],
) -> CMSPartDPayloadEvidence:
    """Digest a payload without loading multi-gigabyte releases into memory."""
    digest, byte_count = _path_digest(path)
    members: list[CMSPartDArchiveMember] = []
    if family == "formulary":
        observed: set[str] = set()
        total_expanded_bytes = 0
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > _CMS_ZIP_MAX_ENTRIES:
                raise ValueError(
                    "CMS Part D archive entry count limit exceeded"
                )
            for info in infos:
                member_path, total_expanded_bytes = _validate_cms_zip_info(
                    info,
                    observed=observed,
                    total_expanded_bytes=total_expanded_bytes,
                )
                if not info.is_dir():
                    members.append(
                        CMSPartDArchiveMember(
                            path=member_path,
                            byte_count=info.file_size,
                            compressed_byte_count=info.compress_size,
                            crc32=f"{info.CRC:08x}",
                            sha256=_stream_cms_zip_member(archive, info),
                        )
                    )
        if not members:
            raise ValueError("CMS Part D formulary archive is empty")
    return CMSPartDPayloadEvidence(
        url=url,
        family=family,
        sha256=digest,
        byte_count=byte_count,
        archive_members=tuple(members),
    )


def write_cms_partd_private_archive(
    files: tuple[tuple[str, Path], ...], destination: Path
) -> tuple[str, int]:
    """Write a deterministic streaming archive without loading payloads."""
    if destination.exists():
        raise FileExistsError("CMS Part D private archive already exists")
    observed: set[str] = set()
    with tarfile.open(
        destination, mode="w", format=tarfile.PAX_FORMAT
    ) as archive:
        for relative, path in sorted(files):
            safe_relative = _safe_member_path(relative)
            if safe_relative in observed or not path.is_file():
                raise ValueError("CMS Part D archive input is invalid")
            observed.add(safe_relative)
            info = tarfile.TarInfo(f"corpus/{safe_relative}")
            info.uid = info.gid = info.mtime = 0
            info.uname = info.gname = ""
            info.mode = 0o600
            info.size = path.stat().st_size
            with path.open("rb") as handle:
                archive.addfile(info, handle)
    return _path_digest(destination)


def recover_cms_partd_private_archive(
    archive_path: Path,
    destination: Path,
    expected_sha256: dict[str, str],
) -> int:
    """Restore the private archive and verify every expected payload digest."""
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("CMS Part D recovery directory must be empty")
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, mode="r") as archive:
        expected_members = {
            f"corpus/{_safe_member_path(relative)}"
            for relative in expected_sha256
        }
        members = archive.getmembers()
        if {member.name for member in members} != expected_members or any(
            not member.isfile() for member in members
        ):
            raise ValueError("CMS Part D private archive inventory diverged")
        archive.extractall(destination, filter="data")
    recovered = 0
    for relative, expected in sorted(expected_sha256.items()):
        path = destination / "corpus" / _safe_member_path(relative)
        digest, _ = _path_digest(path)
        if digest != expected:
            raise ValueError("CMS Part D recovered payload digest diverged")
        recovered += 1
    return recovered


def parse_cms_partd_inventory(
    formulary_catalog: bytes,
    spending_catalog: bytes,
    *,
    authorization: CMSPartDAuthorization,
) -> CMSPartDInventory:
    """Bind the two official catalogues without downloading dataset payloads."""
    formulary = _resource_urls(formulary_catalog)
    spending = _resource_urls(spending_catalog)
    if (
        len(formulary) != authorization.expected_formulary_release_count
        or _digest(formulary) != authorization.expected_formulary_url_set_sha256
    ):
        raise ValueError("CMS Part D formulary release inventory drifted")
    if (
        len(spending) != authorization.expected_spending_resource_count
        or _digest(spending) != authorization.expected_spending_url_set_sha256
    ):
        raise ValueError("CMS Part D spending resource inventory drifted")
    if any(not str(url).endswith(".zip") for url in formulary):
        raise ValueError(
            "CMS Part D formulary inventory must contain ZIP releases"
        )
    if sum(str(url).endswith(".csv") for url in spending) != 1:
        raise ValueError("CMS Part D spending inventory must contain one CSV")
    return CMSPartDInventory(
        formulary_release_count=len(formulary),
        formulary_urls=formulary,
        spending_resource_count=len(spending),
        spending_urls=spending,
    )
