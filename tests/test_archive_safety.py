from __future__ import annotations

import gzip
import stat
import tarfile
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from global_medicines_atlas.archive_safety import (
    ArchivePolicy,
    ArchiveSafetyError,
    extract_tar,
    extract_zip,
    inspect_gzip,
    inspect_tar,
    inspect_zip,
)

pytestmark = pytest.mark.edge


def _zip(entries: list[tuple[zipfile.ZipInfo | str, bytes]]) -> bytes:
    stream = BytesIO()
    with zipfile.ZipFile(
        stream, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for name, payload in entries:
            archive.writestr(name, payload)
    return stream.getvalue()


def _tar(entries: list[tuple[str, bytes]]) -> bytes:
    stream = BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, payload in entries:
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            archive.addfile(info, BytesIO(payload))
    return stream.getvalue()


def _gzip(payload: bytes) -> bytes:
    stream = BytesIO()
    with gzip.GzipFile(fileobj=stream, mode="wb") as handle:
        handle.write(payload)
    return stream.getvalue()


def _tar_special(
    name: str,
    typeflag: bytes,
    *,
    linkname: str = "",
) -> bytes:
    stream = BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        info = tarfile.TarInfo(name=name)
        info.type = typeflag
        info.linkname = linkname
        archive.addfile(info)
    return stream.getvalue()


@pytest.mark.parametrize(
    "name",
    [
        "../escape.txt",
        "/absolute.txt",
        "C:/drive.txt",
        "safe/../../escape.txt",
        r"..\escape.txt",
    ],
)
def test_extract_zip_rejects_traversal(tmp_path: Path, name: str) -> None:
    payload = _zip([(name, b"unsafe")])

    with pytest.raises(ArchiveSafetyError, match="unsafe member path"):
        extract_zip(payload, tmp_path / "out")


def test_extract_zip_rejects_symlink(tmp_path: Path) -> None:
    link = zipfile.ZipInfo("link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16

    with pytest.raises(ArchiveSafetyError, match="symlink"):
        extract_zip(_zip([(link, b"target")]), tmp_path / "out")


@pytest.mark.parametrize(
    "name",
    [
        "safe/file.txt:payload",
        "CON",
        "data/prn.txt",
        "data/COM1.csv",
        "data/trailing.",
        "data/trailing ",
    ],
)
def test_extract_zip_rejects_windows_ambiguous_names(
    tmp_path: Path,
    name: str,
) -> None:
    with pytest.raises(ArchiveSafetyError, match="unsafe member path"):
        extract_zip(_zip([(name, b"x")]), tmp_path / "out")


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("Data/file.txt", "data/FILE.TXT"),
        ("source/a", "SOURCE/a"),
    ],
)
def test_extract_zip_rejects_portable_name_collisions(
    tmp_path: Path,
    first: str,
    second: str,
) -> None:
    with pytest.raises(ArchiveSafetyError, match="duplicate archive member"):
        extract_zip(
            _zip([(first, b"a"), (second, b"b")]),
            tmp_path / "out",
        )


def test_extract_zip_enforces_entry_and_ratio_limits(tmp_path: Path) -> None:
    with pytest.raises(ArchiveSafetyError, match="entry count"):
        extract_zip(
            _zip([("a", b"a"), ("b", b"b")]),
            tmp_path / "entries",
            policy=ArchivePolicy(max_entries=1),
        )

    with pytest.raises(ArchiveSafetyError, match="decompression ratio"):
        extract_zip(
            _zip([("large.txt", b"0" * 20_000)]),
            tmp_path / "ratio",
            policy=ArchivePolicy(max_decompression_ratio=2),
        )


def test_extract_zip_enforces_nesting_and_total_size(tmp_path: Path) -> None:
    with pytest.raises(ArchiveSafetyError, match="nesting depth"):
        extract_zip(
            _zip([("a/b/c.txt", b"x")]),
            tmp_path / "depth",
            policy=ArchivePolicy(max_path_depth=2),
        )

    with pytest.raises(ArchiveSafetyError, match="uncompressed bytes"):
        extract_zip(
            _zip([("a", b"123"), ("b", b"456")]),
            tmp_path / "size",
            policy=ArchivePolicy(max_total_uncompressed_bytes=5),
        )


def test_extract_zip_writes_only_verified_regular_files(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "out"
    receipt = extract_zip(
        _zip([("data/a.txt", b"a"), ("data/b.txt", b"bb")]),
        destination,
    )

    assert [item.path for item in receipt.members] == [
        "data/a.txt",
        "data/b.txt",
    ]
    assert receipt.total_uncompressed_bytes == 3
    assert (destination / "data/a.txt").read_bytes() == b"a"


def test_extract_tar_rejects_traversal_and_extracts_regular_files(
    tmp_path: Path,
) -> None:
    with pytest.raises(ArchiveSafetyError, match="unsafe member path"):
        extract_tar(_tar([("../escape.txt", b"unsafe")]), tmp_path / "bad")
    destination = tmp_path / "tar-out"
    receipt = extract_tar(_tar([("data/a.txt", b"a")]), destination)
    assert receipt.members[0].path == "data/a.txt"
    assert (destination / "data/a.txt").read_bytes() == b"a"


def test_extract_zip_publication_failure_exposes_no_partial_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "out"
    original_replace = Path.replace

    def fail_publication(path: Path, target: Path) -> Path:
        if path.name == "payload" and target == destination:
            raise OSError("injected publication failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_publication)

    with pytest.raises(OSError, match="injected publication failure"):
        extract_zip(
            _zip([("one/a.txt", b"a"), ("two/b.txt", b"b")]),
            destination,
        )

    assert not destination.exists()
    assert not list(tmp_path.glob(".out.extract-*"))


@given(
    st.sampled_from(["CON", "PRN", "AUX", "NUL", "COM1", "LPT9"]),
    st.sampled_from(["", ".txt", ".csv"]),
)
def test_extract_zip_rejects_generated_reserved_names(
    reserved: str,
    suffix: str,
) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        destination = (
            Path(temporary) / f"out-{reserved}-{suffix.replace('.', '')}"
        )
        with pytest.raises(ArchiveSafetyError, match="unsafe member path"):
            extract_zip(
                _zip([(f"safe/{reserved}{suffix}", b"x")]),
                destination,
            )


def test_inspect_zip_and_tar_enforce_byte_limits() -> None:
    tiny = ArchivePolicy(max_archive_bytes=1)
    with pytest.raises(ArchiveSafetyError, match="archive byte limit"):
        inspect_zip(_zip([("a.txt", b"a")]), tiny)
    with pytest.raises(ArchiveSafetyError, match="archive byte limit"):
        inspect_tar(_tar([("a.txt", b"a")]), tiny)
    with pytest.raises(ArchiveSafetyError, match="archive byte limit"):
        inspect_gzip(_gzip(b"a"), tiny)


def test_inspect_zip_rejects_invalid_payload() -> None:
    with pytest.raises(ArchiveSafetyError, match="not a valid ZIP"):
        inspect_zip(b"not-a-zip")


def test_inspect_tar_rejects_hostile_and_oversized_members() -> None:
    with pytest.raises(ArchiveSafetyError, match="entry count"):
        inspect_tar(
            _tar([("a", b"a"), ("b", b"b")]),
            ArchivePolicy(max_entries=1),
        )
    with pytest.raises(ArchiveSafetyError, match="symlink"):
        inspect_tar(_tar_special("link", tarfile.SYMTYPE, linkname="t"))
    with pytest.raises(ArchiveSafetyError, match="special archive members"):
        inspect_tar(_tar_special("fifo", tarfile.FIFOTYPE))
    with pytest.raises(ArchiveSafetyError, match="duplicate archive member"):
        inspect_tar(_tar([("Data/a.txt", b"a"), ("data/A.TXT", b"b")]))
    with pytest.raises(ArchiveSafetyError, match="member byte limit"):
        inspect_tar(
            _tar([("a.txt", b"abc")]),
            ArchivePolicy(max_entry_uncompressed_bytes=2),
        )
    with pytest.raises(ArchiveSafetyError, match="uncompressed bytes"):
        inspect_tar(
            _tar([("a", b"123"), ("b", b"456")]),
            ArchivePolicy(max_total_uncompressed_bytes=5),
        )


def test_inspect_tar_skips_directories_and_rejects_ratio() -> None:
    stream = BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        directory = tarfile.TarInfo(name="data")
        directory.type = tarfile.DIRTYPE
        archive.addfile(directory)
        info = tarfile.TarInfo(name="data/a.txt")
        info.size = 1
        archive.addfile(info, BytesIO(b"a"))
    assert inspect_tar(stream.getvalue()) == 1

    compressed = BytesIO()
    with tarfile.open(fileobj=compressed, mode="w:gz") as archive:
        info = tarfile.TarInfo(name="large.txt")
        payload = b"0" * 20_000
        info.size = len(payload)
        archive.addfile(info, BytesIO(payload))
    with pytest.raises(ArchiveSafetyError, match="decompression ratio"):
        inspect_tar(
            compressed.getvalue(),
            ArchivePolicy(max_decompression_ratio=2),
        )


def test_inspect_tar_and_gzip_reject_corrupt_streams() -> None:
    with pytest.raises(ArchiveSafetyError, match="not a valid tar"):
        inspect_tar(b"not-a-tar")
    with pytest.raises(ArchiveSafetyError, match="gzip stream is corrupted"):
        inspect_gzip(b"\x1f\x8bnot-gzip")


def test_inspect_gzip_enforces_expanded_size_and_ratio() -> None:
    payload = _gzip(b"0" * 20_000)
    with pytest.raises(ArchiveSafetyError, match="expanded size limit"):
        inspect_gzip(
            payload,
            ArchivePolicy(
                max_total_uncompressed_bytes=100,
                max_decompression_ratio=1_000_000,
            ),
        )
    with pytest.raises(ArchiveSafetyError, match="decompression ratio"):
        inspect_gzip(payload, ArchivePolicy(max_decompression_ratio=2))


def test_extract_tar_rejects_existing_or_symlink_destination(
    tmp_path: Path,
) -> None:
    payload = _tar([("a.txt", b"a")])
    existing = tmp_path / "exists"
    existing.mkdir()
    with pytest.raises(ArchiveSafetyError, match="must not exist"):
        extract_tar(payload, existing)
    linked = tmp_path / "linked"
    linked.symlink_to(tmp_path / "missing")
    with pytest.raises(ArchiveSafetyError, match="must not be a symlink"):
        extract_tar(payload, linked)
    with pytest.raises(ArchiveSafetyError, match="not a valid tar"):
        extract_tar(b"not-a-tar", tmp_path / "out")


def test_extract_tar_rejects_unreadable_or_mismatched_members(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = tarfile.TarFile.extractfile

    def unreadable(
        _self: tarfile.TarFile,
        _member: tarfile.TarInfo,
    ) -> None:
        return None

    monkeypatch.setattr(tarfile.TarFile, "extractfile", unreadable)
    with pytest.raises(ArchiveSafetyError, match="could not be read"):
        extract_tar(_tar([("a.txt", b"a")]), tmp_path / "unread")

    def extra_bytes(
        self: tarfile.TarFile,
        member: tarfile.TarInfo,
    ) -> BytesIO | None:
        handle = original(self, member)
        if handle is None:
            return None
        return BytesIO(handle.read() + b"overflow")

    monkeypatch.setattr(tarfile.TarFile, "extractfile", extra_bytes)
    with pytest.raises(ArchiveSafetyError, match="exceeded declared size"):
        extract_tar(_tar([("a.txt", b"a")]), tmp_path / "overflow")

    def short_bytes(
        _self: tarfile.TarFile,
        _member: tarfile.TarInfo,
    ) -> BytesIO:
        return BytesIO(b"")

    monkeypatch.setattr(tarfile.TarFile, "extractfile", short_bytes)
    with pytest.raises(ArchiveSafetyError, match="did not match directory"):
        extract_tar(_tar([("a.txt", b"a")]), tmp_path / "short")
