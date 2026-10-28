"""Streaming member inventories preserve identities without disclosing names."""

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

import pytest

from global_medicines_atlas import mbs_archive_members as module
from global_medicines_atlas.archive_safety import DEFAULT_ARCHIVE_POLICY
from global_medicines_atlas.mbs_archive_inventory import (
    BoundArchive,
    load_archives,
)
from global_medicines_atlas.mbs_archive_members import profile_archive_members


def fixture(tmp_path):
    path = tmp_path / "source.zip"
    with ZipFile(path, "w", compression=ZIP_STORED) as archive:
        archive.writestr("SYNTHETIC.csv", b"A,B\n1,2\n")
        archive.writestr(
            "native.xls", bytes.fromhex("d0cf11e0a1b11ae1") + b"synthetic"
        )
        archive.writestr("native.xlsx", b"PK\x03\x04synthetic")
    source = BoundArchive(
        "synthetic/archive",
        "1" * 40,
        "raw/synthetic.zip",
        hashlib.sha256(path.read_bytes()).hexdigest(),
        path.stat().st_size,
        "synthetic",
        "2" * 64,
        "3" * 64,
        "4" * 64,
        "unprofiled",
        None,
        None,
        None,
    )
    return path, source


def test_every_member_has_digest_size_and_nonsemantic_container_hint(tmp_path):
    path, source = fixture(tmp_path)
    report = profile_archive_members(path, source)
    assert report["member_count"] == 3
    assert {row["magic_kind"] for row in report["members"]} == {
        "unknown",
        "compound-document-signature",
        "zip-container-signature",
    }
    assert report["member_formats_qualified"] is False
    assert "SYNTHETIC" not in json.dumps(report)
    assert report == profile_archive_members(path, source)


def test_identity_is_verified_before_member_read(tmp_path):
    path, source = fixture(tmp_path)
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match=r"size|digest"):
        profile_archive_members(path, source)


@pytest.mark.parametrize(
    "field",
    ["source_path", "source_sha256", "source_bytes", "dataset", "revision"],
)
def test_larger_limit_requires_every_exact_source_identity_component(field):
    root = Path(__file__).resolve().parents[1]
    source = next(
        source
        for source in load_archives(root)
        if "2008-2012" in source.source_path
    )
    selected = module.archive_policy(source)
    assert selected.max_archive_bytes == source.source_bytes
    assert {
        name: value
        for name, value in asdict(selected).items()
        if name != "max_archive_bytes"
    } == {
        name: value
        for name, value in asdict(DEFAULT_ARCHIVE_POLICY).items()
        if name != "max_archive_bytes"
    }
    changed = replace(
        source,
        **{
            field: source.source_bytes + 1
            if field == "source_bytes"
            else "different"
        },
    )
    assert module.archive_policy(changed) == DEFAULT_ARCHIVE_POLICY


def test_prior_inventory_mismatch_does_not_return_partial_report(tmp_path):
    path, source = fixture(tmp_path)
    source = replace(source, prior_member_count=1)
    with pytest.raises(ValueError, match="prior member inventory"):
        profile_archive_members(path, source)
    assert list(tmp_path.iterdir()) == [path]


def test_report_limit_rejects_without_truncating(tmp_path, monkeypatch):
    path, source = fixture(tmp_path)
    monkeypatch.setattr(module, "MAX_REPORT_BYTES", 1)
    with pytest.raises(ValueError, match="report byte bound"):
        profile_archive_members(path, source)


@pytest.mark.parametrize(
    ("prefix", "kind"),
    [
        (b"%PDF-1", "pdf-signature"),
        (b"\x1f\x8b", "gzip-signature"),
        (b"BZh9", "bzip2-signature"),
        (b"PK\x05\x06", "zip-container-signature"),
    ],
)
def test_prefix_classification_does_not_claim_table_format(prefix, kind):
    assert module._magic(prefix) == kind


def test_windows_native_member_paths_are_verified_without_extraction(tmp_path):
    path = tmp_path / "source.zip"
    with ZipFile(path, "w", compression=ZIP_STORED) as archive:
        archive.writestr("folder\\native.csv", b"a,b\n")
    source = BoundArchive(
        "synthetic/archive",
        "1" * 40,
        "raw/synthetic.zip",
        hashlib.sha256(path.read_bytes()).hexdigest(),
        path.stat().st_size,
        "synthetic",
        "2" * 64,
        "3" * 64,
        "4" * 64,
        "unprofiled",
        None,
        None,
        None,
    )
    report = profile_archive_members(path, source)
    assert (
        report["members"][0]["verified_relative_path_sha256"]
        == hashlib.sha256(b"folder/native.csv").hexdigest()
    )
    assert list(tmp_path.iterdir()) == [path]
