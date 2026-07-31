from __future__ import annotations

import stat
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
