from __future__ import annotations

import stat
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from global_medicines_atlas.archive_safety import (
    ArchivePolicy,
    ArchiveSafetyError,
    extract_zip,
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
        extract_zip(payload, tmp_path)


def test_extract_zip_rejects_symlink(tmp_path: Path) -> None:
    link = zipfile.ZipInfo("link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16

    with pytest.raises(ArchiveSafetyError, match="symlink"):
        extract_zip(_zip([(link, b"target")]), tmp_path)


def test_extract_zip_enforces_entry_and_ratio_limits(tmp_path: Path) -> None:
    with pytest.raises(ArchiveSafetyError, match="entry count"):
        extract_zip(
            _zip([("a", b"a"), ("b", b"b")]),
            tmp_path,
            policy=ArchivePolicy(max_entries=1),
        )

    with pytest.raises(ArchiveSafetyError, match="decompression ratio"):
        extract_zip(
            _zip([("large.txt", b"0" * 20_000)]),
            tmp_path,
            policy=ArchivePolicy(max_decompression_ratio=2),
        )


def test_extract_zip_enforces_nesting_and_total_size(tmp_path: Path) -> None:
    with pytest.raises(ArchiveSafetyError, match="nesting depth"):
        extract_zip(
            _zip([("a/b/c.txt", b"x")]),
            tmp_path,
            policy=ArchivePolicy(max_path_depth=2),
        )

    with pytest.raises(ArchiveSafetyError, match="uncompressed bytes"):
        extract_zip(
            _zip([("a", b"123"), ("b", b"456")]),
            tmp_path,
            policy=ArchivePolicy(max_total_uncompressed_bytes=5),
        )


def test_extract_zip_writes_only_verified_regular_files(
    tmp_path: Path,
) -> None:
    receipt = extract_zip(
        _zip([("data/a.txt", b"a"), ("data/b.txt", b"bb")]),
        tmp_path,
    )

    assert [item.path for item in receipt.members] == [
        "data/a.txt",
        "data/b.txt",
    ]
    assert receipt.total_uncompressed_bytes == 3
    assert (tmp_path / "data/a.txt").read_bytes() == b"a"
