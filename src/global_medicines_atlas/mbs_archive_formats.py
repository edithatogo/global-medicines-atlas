"""Bounded native format profiles for exact, already inventoried MBS members.

These profiles establish parsing evidence, not header meanings, era equivalence
or complete source-faithful Silver tables. Private staging never uses an archive
member's native path as a filesystem destination.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import IO, Any
from zipfile import BadZipFile, ZipFile

from .mbs_archive_inventory import BoundArchive
from .mbs_archive_members import MAX_REPORT_BYTES, profile_archive_members
from .mbs_streaming_workbook import validate_streaming_workbook

MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_FIELD_CHARS = 1024 * 1024
MAX_RECORD_BYTES = 8 * 1024 * 1024
MAX_COLUMNS = 16384
CHUNK_BYTES = 1024 * 1024


class MemberIdentityError(ValueError):
    """A staged native member differs from the verified parent inventory."""


def _stage(
    stream: IO[bytes], destination: Path, member: dict[str, Any]
) -> None:
    if not 0 < member["bytes"] <= MAX_MEMBER_BYTES:
        raise ValueError("member-byte-bound")
    count = 0
    digest = hashlib.sha256()
    with destination.open("xb") as output:
        while block := stream.read(CHUNK_BYTES):
            count += len(block)
            if count > member["bytes"]:
                raise MemberIdentityError("member-identity")
            digest.update(block)
            output.write(block)
    if count != member["bytes"] or digest.hexdigest() != member["sha256"]:
        raise MemberIdentityError("member-identity")
    destination.chmod(0o400)


def profile_native_csv(path: Path) -> dict[str, Any]:
    """Account for every strict UTF-8 CSV record, including the first and empty.

    Preserve values only in a native-field digest. Header, numeric, date and
    suppression meanings remain unqualified. Restore the process CSV bound.
    """
    old_limit = csv.field_size_limit(MAX_FIELD_CHARS)
    records = fields = empty = 0
    widths: Counter[int] = Counter()
    digest = hashlib.sha256()
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            for ordinal, row in enumerate(csv.reader(stream, strict=True)):
                if len(row) > MAX_COLUMNS:
                    raise ValueError("csv-column-bound")
                encoded = json.dumps(
                    [ordinal, row], ensure_ascii=False, separators=(",", ":")
                ).encode()
                if len(encoded) > MAX_RECORD_BYTES:
                    raise ValueError("csv-record-byte-bound")
                digest.update(encoded + b"\n")
                records += 1
                fields += len(row)
                empty += not row
                widths[len(row)] += 1
    finally:
        csv.field_size_limit(old_limit)
    return {
        "profile": "mbs-native-csv-records-v1",
        "records": records,
        "native_fields": fields,
        "empty_records": empty,
        "record_widths": {str(k): v for k, v in sorted(widths.items())},
        "native_records_sha256": digest.hexdigest(),
        "header_qualified": False,
        "semantics_qualified": False,
    }


def _member_profile(path: Path, member: dict[str, Any]) -> dict[str, Any]:
    suffix = member["declared_suffix_hint"]
    if suffix == ".csv":
        return profile_native_csv(path)
    if suffix == ".xlsx":
        return validate_streaming_workbook(
            path,
            {
                "path": "member.xlsx",
                "sha256": member["sha256"],
                "byte_count": member["bytes"],
            },
        )
    raise ValueError("unsupported-native-format")


def profile_archive_formats(path: Path, source: BoundArchive) -> dict[str, Any]:
    """Profile all verified members; retain per-member coded holds without loss.

    The caller must stage real source archives immutably on protected runners.
    Every member is rehashed while privately staged. Outer integrity failures
    abort; member parser failures remain visible and cannot establish a pass.
    No source names, table values or exception text are emitted.
    """
    inventory = profile_archive_members(path, source)
    reports: list[dict[str, Any]] = []
    with (
        ZipFile(path) as archive,
        TemporaryDirectory(prefix="mbs-member-formats-") as temporary,
    ):
        lookup = {
            PurePosixPath(i.filename.replace("\\", "/")).as_posix(): i
            for i in archive.infolist()
            if not i.is_dir()
        }
        indexed = {
            hashlib.sha256(name.encode()).hexdigest(): info
            for name, info in lookup.items()
        }
        if set(indexed) != {
            member["verified_relative_path_sha256"]
            for member in inventory["members"]
        }:
            raise ValueError("archive-member-identity-set")
        for member in inventory["members"]:
            destination = Path(temporary) / f"member-{member['ordinal']}.bin"
            try:
                with archive.open(
                    indexed[member["verified_relative_path_sha256"]]
                ) as stream:
                    _stage(stream, destination, member)
                native = _member_profile(destination, member)
                result = {
                    **member,
                    "status": "parsed",
                    "native_profile": native,
                }
            except MemberIdentityError:
                raise
            except ValueError, UnicodeError, csv.Error, BadZipFile:
                result = {
                    **member,
                    "status": "held",
                    "hold_code": "native-format-or-resource-unqualified",
                }
            finally:
                if destination.exists():
                    destination.chmod(0o600)
                    destination.unlink()
            reports.append(result)
    parsed = sum(item["status"] == "parsed" for item in reports)
    report = {
        **inventory,
        "schema_id": "global-medicines-atlas.mbs-historical-native-format-inventory",
        "members": reports,
        "members_parsed": parsed,
        "members_held": len(reports) - parsed,
        "member_formats_qualified": False,
        "all_native_format_profiles_passed": parsed == len(reports),
        "source_faithful_tables_qualified": False,
        "semantics_qualified": False,
        "native_values_or_names_emitted": False,
    }
    if (
        len(json.dumps(report, sort_keys=True, separators=(",", ":")).encode())
        > MAX_REPORT_BYTES
    ):
        raise ValueError("native-format-report-byte-bound")
    return report


# Reuse identical digest/size checks and finite staging limits for native packages.
stage_bound_member = _stage
