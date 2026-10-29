"""Native member formats are parsed without names, values or semantic claims."""

import csv
import hashlib
import json
from dataclasses import replace
from io import BytesIO
from zipfile import ZIP_STORED, ZipFile

import pytest
from test_mbs_utilisation_rights_runner import (
    _streaming_fixture,  # ruff: ignore[import-private-name] -- synthetic workbook
)

from global_medicines_atlas import mbs_archive_formats as module
from global_medicines_atlas import mbs_streaming_workbook
from global_medicines_atlas.mbs_archive_formats import profile_archive_formats
from global_medicines_atlas.mbs_archive_inventory import BoundArchive


def fixture(tmp_path, *, malformed=False):
    workbook, _ = _streaming_fixture(tmp_path, mbs_streaming_workbook)
    path = tmp_path / "outer.zip"
    with ZipFile(path, "w", compression=ZIP_STORED) as archive:
        archive.writestr("SYNTHETIC.csv", b'A,B\n00123,"SYNTHETIC\nquoted"\n\n')
        archive.writestr(
            "SYNTHETIC.xlsx", b"PKbad" if malformed else workbook.read_bytes()
        )
    return path, BoundArchive(
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


def test_every_member_is_parsed_and_native_values_stay_private(tmp_path):
    path, source = fixture(tmp_path)
    report = profile_archive_formats(path, source)
    assert report["members_parsed"] == report["member_count"] == 2
    assert report["members_held"] == 0
    csv = next(
        item
        for item in report["members"]
        if item["declared_suffix_hint"] == ".csv"
    )
    assert csv["native_profile"]["records"] == 3
    assert csv["native_profile"]["native_fields"] == 4
    assert csv["native_profile"]["empty_records"] == 1
    assert "SYNTHETIC" not in json.dumps(report)
    assert "PRIVATE" not in json.dumps(report)
    assert report["semantics_qualified"] is False
    assert report["source_faithful_tables_qualified"] is False


def test_one_invalid_member_is_retained_as_a_coded_hold(tmp_path):
    path, source = fixture(tmp_path, malformed=True)
    report = profile_archive_formats(path, source)
    assert report["members_parsed"] == report["members_held"] == 1
    assert sum(item["status"] == "held" for item in report["members"]) == 1
    assert "PKbad" not in json.dumps(report)


def test_parent_identity_mismatch_fails_before_member_parsing(tmp_path):
    path, source = fixture(tmp_path)
    with pytest.raises(ValueError, match=r"digest|size"):
        profile_archive_formats(path, replace(source, source_sha256="0" * 64))


def test_member_identity_failure_cannot_be_downgraded_to_format_hold(
    tmp_path, monkeypatch
):
    def wrong(*_):
        raise module.MemberIdentityError("synthetic changed digest")

    path, source = fixture(tmp_path)
    monkeypatch.setattr(module, "_stage", wrong)
    with pytest.raises(module.MemberIdentityError, match="changed digest"):
        profile_archive_formats(path, source)


@pytest.mark.parametrize("change", ["digest", "short", "long", "bound"])
def test_member_staging_bounds_and_identity_are_fail_closed(
    tmp_path, monkeypatch, change
):
    payload = b"A,B\n"
    member = {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    if change == "digest":
        member["sha256"] = "0" * 64
    elif change == "short":
        payload = payload[:-1]
    elif change == "long":
        payload += b"extra"
    else:
        monkeypatch.setattr(module, "MAX_MEMBER_BYTES", 1)
    with pytest.raises(ValueError, match=r"identity|bound"):
        module._stage(BytesIO(payload), tmp_path / "private.bin", member)


@pytest.mark.parametrize(
    "change", ["columns", "record_bytes", "field_chars", "encoding", "grammar"]
)
def test_native_csv_rejects_invalid_or_unbounded_records_and_restores_limit(
    tmp_path, monkeypatch, change
):
    payload = b"A,B\n1,2\n"
    if change == "columns":
        monkeypatch.setattr(module, "MAX_COLUMNS", 1)
    elif change == "record_bytes":
        monkeypatch.setattr(module, "MAX_RECORD_BYTES", 1)
    elif change == "field_chars":
        monkeypatch.setattr(module, "MAX_FIELD_CHARS", 1)
        payload = b"too_long\n"
    elif change == "encoding":
        payload = b"\xff\n"
    else:
        payload = b'"unterminated\n'
    path = tmp_path / "private.csv"
    path.write_bytes(payload)
    before = csv.field_size_limit()
    with pytest.raises((ValueError, UnicodeError, csv.Error)):
        module.profile_native_csv(path)
    assert csv.field_size_limit() == before


def test_complete_report_bound_rejects_without_truncating_members(
    tmp_path, monkeypatch
):
    path, source = fixture(tmp_path)
    monkeypatch.setattr(module, "MAX_REPORT_BYTES", 1)
    with pytest.raises(ValueError, match="report-byte-bound"):
        profile_archive_formats(path, source)


def test_unsupported_format_is_a_visible_hold(tmp_path, monkeypatch):
    path, source = fixture(tmp_path)
    original = module.profile_archive_members

    def changed(*args):
        report = original(*args)
        for member in report["members"]:
            member["declared_suffix_hint"] = "unknown"
        return report

    monkeypatch.setattr(module, "profile_archive_members", changed)
    report = profile_archive_formats(path, source)
    assert report["members_held"] == 2
    assert report["all_native_format_profiles_passed"] is False


def test_changed_member_identity_set_fails_before_format_parse(
    tmp_path, monkeypatch
):
    path, source = fixture(tmp_path)
    original = module.profile_archive_members

    def changed(*args):
        report = original(*args)
        report["members"] = report["members"][:-1]
        return report

    monkeypatch.setattr(module, "profile_archive_members", changed)
    with pytest.raises(ValueError, match="identity-set"):
        profile_archive_formats(path, source)
