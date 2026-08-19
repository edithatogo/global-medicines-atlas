"""Fail-closed extraction for untrusted ZIP source archives."""

from __future__ import annotations

import gzip
import hashlib
import stat
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath


class ArchiveSafetyError(ValueError):
    """An archive violated an extraction safety policy."""


@dataclass(frozen=True, slots=True)
class ArchivePolicy:
    """Resource and path limits for ZIP extraction."""

    max_archive_bytes: int = 256 * 1024 * 1024
    max_entries: int = 10_000
    max_entry_uncompressed_bytes: int = 512 * 1024 * 1024
    max_total_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024
    max_decompression_ratio: float = 200.0
    max_path_depth: int = 16
    chunk_bytes: int = 1024 * 1024


DEFAULT_ARCHIVE_POLICY = ArchivePolicy()
ZIP_UNIX_SYSTEM = 3
WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)


@dataclass(frozen=True, slots=True)
class ExtractedMember:
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ExtractionReceipt:
    archive_sha256: str
    members: tuple[ExtractedMember, ...]
    total_uncompressed_bytes: int


def _member_path(name: str, policy: ArchivePolicy) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(
            ":" in part
            or part.endswith((".", " "))
            or part.rstrip(" .").split(".", maxsplit=1)[0].upper()
            in WINDOWS_RESERVED_NAMES
            for part in path.parts
        )
    ):
        raise ArchiveSafetyError(f"unsafe member path: {name}")
    if len(path.parts) > policy.max_path_depth:
        raise ArchiveSafetyError(f"archive nesting depth exceeded: {name}")
    return path


def _portable_path_key(path: PurePosixPath) -> tuple[str, ...]:
    return tuple(part.rstrip(" .").casefold() for part in path.parts)


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return info.create_system == ZIP_UNIX_SYSTEM and stat.S_ISLNK(
        info.external_attr >> 16
    )


def _validate_members(
    archive: zipfile.ZipFile,
    policy: ArchivePolicy,
) -> list[tuple[zipfile.ZipInfo, PurePosixPath]]:
    infos = archive.infolist()
    if len(infos) > policy.max_entries:
        raise ArchiveSafetyError("archive entry count limit exceeded")
    total = 0
    members: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
    seen: set[tuple[str, ...]] = set()
    for info in infos:
        path = _member_path(info.filename, policy)
        portable_key = _portable_path_key(path)
        if portable_key in seen:
            raise ArchiveSafetyError(f"duplicate archive member: {path}")
        seen.add(portable_key)
        if info.flag_bits & 0x1:
            raise ArchiveSafetyError("encrypted archive members are forbidden")
        if _is_symlink(info):
            raise ArchiveSafetyError("archive symlink members are forbidden")
        if info.file_size > policy.max_entry_uncompressed_bytes:
            raise ArchiveSafetyError("archive member byte limit exceeded")
        total += info.file_size
        if total > policy.max_total_uncompressed_bytes:
            raise ArchiveSafetyError(
                "archive total uncompressed bytes limit exceeded"
            )
        if (info.file_size > 0 and info.compress_size == 0) or (
            info.compress_size > 0
            and info.file_size / info.compress_size
            > policy.max_decompression_ratio
        ):
            raise ArchiveSafetyError("archive decompression ratio exceeded")
        if not info.is_dir():
            members.append((info, path))
    return members


def _extract_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    target: Path,
    policy: ArchivePolicy,
) -> ExtractedMember:
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    written = 0
    with archive.open(info) as source, target.open("xb") as output:
        while block := source.read(policy.chunk_bytes):
            written += len(block)
            if written > info.file_size:
                raise ArchiveSafetyError(
                    "archive member exceeded declared size"
                )
            digest.update(block)
            output.write(block)
    if written != info.file_size:
        raise ArchiveSafetyError("archive member size did not match directory")
    return ExtractedMember(
        path="",
        sha256=digest.hexdigest(),
        size_bytes=written,
    )


def extract_zip(
    payload: bytes,
    destination: Path,
    *,
    policy: ArchivePolicy = DEFAULT_ARCHIVE_POLICY,
) -> ExtractionReceipt:
    """Validate then atomically extract regular files from a ZIP payload."""
    if len(payload) > policy.max_archive_bytes:
        raise ArchiveSafetyError("archive byte limit exceeded")
    if destination.is_symlink():
        raise ArchiveSafetyError("destination must not be a symlink")
    if destination.exists():
        raise ArchiveSafetyError("destination must not exist")
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        archive = zipfile.ZipFile(BytesIO(payload))
    except zipfile.BadZipFile as error:
        raise ArchiveSafetyError(
            "payload is not a valid ZIP archive"
        ) from error
    with archive:
        members = _validate_members(archive, policy)
        extracted: list[ExtractedMember] = []
        with tempfile.TemporaryDirectory(
            dir=destination.parent,
            prefix=f".{destination.name}.extract-",
        ) as temporary:
            staging = Path(temporary) / "payload"
            staging.mkdir()
            for info, relative in members:
                target = staging.joinpath(*relative.parts)
                result = _extract_member(archive, info, target, policy)
                extracted.append(
                    ExtractedMember(
                        path=relative.as_posix(),
                        sha256=result.sha256,
                        size_bytes=result.size_bytes,
                    )
                )
            staging.replace(destination)
    extracted.sort(key=lambda item: item.path)
    return ExtractionReceipt(
        archive_sha256=hashlib.sha256(payload).hexdigest(),
        members=tuple(extracted),
        total_uncompressed_bytes=sum(item.size_bytes for item in extracted),
    )


def inspect_zip(
    payload: bytes,
    policy: ArchivePolicy = DEFAULT_ARCHIVE_POLICY,
) -> int:
    """Validate ZIP members without extracting them."""

    if len(payload) > policy.max_archive_bytes:
        raise ArchiveSafetyError("archive byte limit exceeded")
    try:
        archive = zipfile.ZipFile(BytesIO(payload))
    except zipfile.BadZipFile as error:
        raise ArchiveSafetyError(
            "payload is not a valid ZIP archive"
        ) from error
    with archive:
        members = _validate_members(archive, policy)
    return len(members)


def _validate_tar_members(
    archive: tarfile.TarFile,
    policy: ArchivePolicy,
    payload_len: int,
) -> list[tuple[tarfile.TarInfo, PurePosixPath]]:
    infos = archive.getmembers()
    if len(infos) > policy.max_entries:
        raise ArchiveSafetyError("archive entry count limit exceeded")
    total = 0
    members: list[tuple[tarfile.TarInfo, PurePosixPath]] = []
    seen: set[tuple[str, ...]] = set()
    for info in infos:
        if info.issym() or info.islnk():
            raise ArchiveSafetyError("archive symlink members are forbidden")
        if not (info.isfile() or info.isdir()):
            raise ArchiveSafetyError("special archive members are forbidden")
        path = _member_path(info.name, policy)
        portable_key = _portable_path_key(path)
        if portable_key in seen:
            raise ArchiveSafetyError(f"duplicate archive member: {path}")
        seen.add(portable_key)
        if info.isdir():
            continue
        if info.size > policy.max_entry_uncompressed_bytes:
            raise ArchiveSafetyError("archive member byte limit exceeded")
        total += info.size
        if total > policy.max_total_uncompressed_bytes:
            raise ArchiveSafetyError(
                "archive total uncompressed bytes limit exceeded"
            )
        members.append((info, path))
    if payload_len > 0 and total / payload_len > policy.max_decompression_ratio:
        raise ArchiveSafetyError("archive decompression ratio exceeded")
    return members


def inspect_tar(
    payload: bytes,
    policy: ArchivePolicy = DEFAULT_ARCHIVE_POLICY,
) -> int:
    """Validate tar/tar.gz members without extracting them."""

    if len(payload) > policy.max_archive_bytes:
        raise ArchiveSafetyError("archive byte limit exceeded")
    try:
        with tarfile.open(fileobj=BytesIO(payload), mode="r:*") as archive:
            members = _validate_tar_members(archive, policy, len(payload))
    except (tarfile.TarError, OSError, EOFError) as error:
        raise ArchiveSafetyError(
            "payload is not a valid tar archive"
        ) from error
    return len(members)


def _count_gzip_bytes(
    handle: gzip.GzipFile,
    policy: ArchivePolicy,
    payload_len: int,
) -> int:
    read = 0
    while block := handle.read(policy.chunk_bytes):
        read += len(block)
        if read > policy.max_total_uncompressed_bytes:
            raise ArchiveSafetyError("gzip expanded size limit exceeded")
        if (
            payload_len > 0
            and read / payload_len > policy.max_decompression_ratio
        ):
            raise ArchiveSafetyError("archive decompression ratio exceeded")
    return read


def inspect_gzip(
    payload: bytes,
    policy: ArchivePolicy = DEFAULT_ARCHIVE_POLICY,
) -> int:
    """Expand gzip only up to policy limits; never return inflated bytes."""

    if len(payload) > policy.max_archive_bytes:
        raise ArchiveSafetyError("archive byte limit exceeded")
    try:
        with gzip.GzipFile(fileobj=BytesIO(payload), mode="rb") as handle:
            return _count_gzip_bytes(handle, policy, len(payload))
    except ArchiveSafetyError:
        raise
    except (OSError, EOFError) as error:
        raise ArchiveSafetyError("gzip stream is corrupted") from error


def _extract_tar_member(
    archive: tarfile.TarFile,
    info: tarfile.TarInfo,
    relative: PurePosixPath,
    staging: Path,
    policy: ArchivePolicy,
) -> ExtractedMember:
    target = staging.joinpath(*relative.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    extracted_file = archive.extractfile(info)
    if extracted_file is None:
        raise ArchiveSafetyError("tar member could not be read")
    digest = hashlib.sha256()
    written = 0
    with extracted_file, target.open("xb") as output:
        while block := extracted_file.read(policy.chunk_bytes):
            written += len(block)
            if written > info.size:
                raise ArchiveSafetyError(
                    "archive member exceeded declared size"
                )
            digest.update(block)
            output.write(block)
    if written != info.size:
        raise ArchiveSafetyError("archive member size did not match directory")
    return ExtractedMember(
        path=relative.as_posix(),
        sha256=digest.hexdigest(),
        size_bytes=written,
    )


def _publish_tar(
    archive: tarfile.TarFile,
    payload: bytes,
    destination: Path,
    policy: ArchivePolicy,
) -> list[ExtractedMember]:
    members = _validate_tar_members(archive, policy, len(payload))
    extracted: list[ExtractedMember] = []
    with tempfile.TemporaryDirectory(
        dir=destination.parent,
        prefix=f".{destination.name}.extract-",
    ) as temporary:
        staging = Path(temporary) / "payload"
        staging.mkdir()
        for info, relative in members:
            extracted.append(
                _extract_tar_member(archive, info, relative, staging, policy)
            )
        staging.replace(destination)
    return extracted


def extract_tar(
    payload: bytes,
    destination: Path,
    *,
    policy: ArchivePolicy = DEFAULT_ARCHIVE_POLICY,
) -> ExtractionReceipt:
    """Validate then atomically extract regular files from a tar payload."""

    if destination.is_symlink():
        raise ArchiveSafetyError("destination must not be a symlink")
    if destination.exists():
        raise ArchiveSafetyError("destination must not exist")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(fileobj=BytesIO(payload), mode="r:*") as opened:
            extracted = _publish_tar(opened, payload, destination, policy)
    except (tarfile.TarError, OSError, EOFError) as error:
        raise ArchiveSafetyError(
            "payload is not a valid tar archive"
        ) from error
    extracted.sort(key=lambda item: item.path)
    return ExtractionReceipt(
        archive_sha256=hashlib.sha256(payload).hexdigest(),
        members=tuple(extracted),
        total_uncompressed_bytes=sum(item.size_bytes for item in extracted),
    )
