"""Complete native CSV packages over frozen historical MBS archive members.

Original archive B1/B2 and content-addressed member evidence remain separate
from this rebuildable derivative. No source meaning, rights or admission is
established by a native package. Real source execution belongs on protected main.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from . import mbs_archive_formats as formats
from .mbs_archive_inventory import BoundArchive, load_archives
from .mbs_demographic_package import (
    candidate_parquet_writer,
    canonical_package_json,
    file_fingerprint,
)

INVENTORY_RECEIPTS: tuple[tuple[str, str], ...] = (
    (
        "quality/qualifications/mbs-historical-archive-members-0-20261022-39678641506.json",
        "137c650b41ad1278b06619c35a81fa748a805562ab91ebb837d22a4ae81a362f",
    ),
    (
        "quality/qualifications/mbs-historical-archive-members-1-20261022-39678641506.json",
        "c82be4b3afb26507b2295df24a02807aa413a3d660ae8331d844bbd58572d9fd",
    ),
    (
        "quality/qualifications/mbs-historical-archive-members-2-20261022-39678641506.json",
        "764c2fa382fc400b7f2708e81faf595e868eece73c157e68a2b458d07411b053",
    ),
    (
        "quality/qualifications/mbs-historical-archive-members-3-20261022-39678641506.json",
        "67e6f64a3e2b83c0b1dd1de3eaa985c607ffb342400576d4172c8ae5162deb3d",
    ),
    (
        "quality/qualifications/mbs-historical-archive-members-4-20261022-39678641506.json",
        "8bcd70f416c6aa0a0d19243f4d5d627785e8766d1b82258ecc90e57f09b8a3ff",
    ),
    (
        "quality/qualifications/mbs-historical-archive-members-5-20261022-39678641506.json",
        "bdd5747a13cb59e92f996cf61c93e873bc0ec5fa4713ca34e635cea5814ac26e",
    ),
)
EXPECTED_MEMBERS = 181
DATA_FILE = "records.parquet"
MANIFEST = "manifest.json"
MAX_BATCH_ROWS = 4096
MAX_PARQUET_BYTES = 4 * 1024**3
MAX_MANIFEST_BYTES = 1024 * 1024
BOUNDARIES = {
    "rights_qualified": False,
    "admitted": False,
    "published": False,
    "semantics_qualified": False,
}


@dataclass(frozen=True)
class FrozenMbsMember:
    """An existing archive member, without inventing an acquisition receipt."""

    source: BoundArchive
    ordinal: int
    sha256: str
    byte_count: int
    path_sha256: str
    suffix: str
    inventory_sha256: str


def load_frozen_members(root: Path) -> tuple[FrozenMbsMember, ...]:
    """Bind every retained member to exact inventory and original archive B1/B2."""
    members: list[FrozenMbsMember] = []
    for source, (path, digest) in zip(
        load_archives(root), INVENTORY_RECEIPTS, strict=True
    ):
        payload = (root / path).read_bytes()
        if hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError("MBS retained member inventory digest differs")
        report = json.loads(payload)
        result = report["result"]
        if (
            report["status"] != "passed"
            or report["dataset"] != source.dataset
            or report["revision"] != source.revision
        ):
            raise ValueError("MBS retained member inventory context differs")
        for name in (
            "source_path",
            "source_sha256",
            "source_bytes",
            "acquisition_id",
            "b1_sha256",
            "b2_sha256",
        ):
            if result[name] != getattr(source, name):
                raise ValueError("MBS retained member original lineage differs")
        if result["member_count"] != len(result["members"]) or result[
            "expanded_bytes"
        ] != sum(m["bytes"] for m in result["members"]):
            raise ValueError("MBS retained member denominator differs")
        for ordinal, member in enumerate(result["members"]):
            if member["ordinal"] != ordinal:
                raise ValueError("MBS retained member order differs")
            members.append(
                FrozenMbsMember(
                    source,
                    ordinal,
                    member["sha256"],
                    member["bytes"],
                    member["verified_relative_path_sha256"],
                    member["declared_suffix_hint"],
                    digest,
                )
            )
    if len(members) != EXPECTED_MEMBERS:
        raise ValueError("MBS frozen member cohort differs")
    return tuple(members)


def _bind(path: Path, member: FrozenMbsMember, native_path: str) -> None:
    if (
        member.suffix != ".csv"
        or type(member.byte_count) is not int
        or not 0 < member.byte_count <= formats.MAX_MEMBER_BYTES
    ):
        raise ValueError("MBS native CSV member format or byte bound differs")
    if (
        len(native_path.encode()) > 1024 * 1024
        or hashlib.sha256(native_path.encode()).hexdigest()
        != member.path_sha256
    ):
        raise ValueError("MBS native CSV member path identity differs")
    if path.is_symlink() or not path.is_file():
        raise ValueError("MBS native CSV member file type differs")
    if path.stat().st_size != member.byte_count or file_fingerprint(path) != {
        "sha256": member.sha256,
        "bytes": member.byte_count,
    }:
        raise ValueError("MBS native CSV member digest or size differs")


def _member_identity(member: FrozenMbsMember) -> str:
    """Keep distinct source objects and member paths distinct, even for aliases."""
    source = member.source
    identity = {
        "dataset": source.dataset,
        "revision": source.revision,
        "source_path": source.source_path,
        "source_sha256": source.source_sha256,
        "member_path_sha256": member.path_sha256,
        "member_sha256": member.sha256,
    }
    return hashlib.sha256(canonical_package_json(identity)).hexdigest()


def _schema(member: FrozenMbsMember, native_path: str) -> pa.Schema:
    return pa.schema(
        [
            pa.field("record_ordinal", pa.int64(), nullable=False),
            pa.field("native_record_id", pa.string(), nullable=False),
            pa.field(
                "native_fields",
                pa.list_(pa.field("element", pa.string(), nullable=False)),
                nullable=False,
            ),
        ],
        metadata={
            b"schema_name": b"global-medicines-atlas.mbs-historical-native-csv-records",
            b"schema_version": b"1",
            b"member_binding": canonical_package_json(asdict(member)),
            b"archive_verified_member_path": native_path.encode(),
            b"qualification": b"candidate",
            b"header_interpretation": b"unqualified-first-record-retained",
            b"numeric_and_date_interpretation": b"native-text-unresolved",
            b"patient_rates": b"unavailable",
            b"absence_interpretation": b"unknown",
            b"conversion": b"none",
            b"record_identity_scope": b"archive-object-member-path-and-content",
            b"cross_source_equivalence": b"unestablished",
        },
    )


def _batches(
    path: Path, member: FrozenMbsMember, native_path: str
) -> Iterator[pa.RecordBatch]:
    schema = _schema(member, native_path)
    identity = _member_identity(member)
    rows: list[dict[str, Any]] = []
    size = 0
    before = csv.field_size_limit(formats.MAX_FIELD_CHARS)
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            for ordinal, fields in enumerate(csv.reader(stream, strict=True)):
                row = {
                    "record_ordinal": ordinal,
                    "native_record_id": f"{identity}:/records/{ordinal}",
                    "native_fields": fields,
                }
                encoded_size = len(canonical_package_json(row))
                if (
                    len(fields) > formats.MAX_COLUMNS
                    or encoded_size > formats.MAX_RECORD_BYTES
                ):
                    raise ValueError("MBS native CSV record bound exceeded")
                if rows and (
                    len(rows) >= MAX_BATCH_ROWS
                    or size + encoded_size > formats.MAX_RECORD_BYTES
                ):
                    yield pa.RecordBatch.from_pylist(rows, schema=schema)
                    rows, size = [], 0
                rows.append(row)
                size += encoded_size
        if rows:
            yield pa.RecordBatch.from_pylist(rows, schema=schema)
    finally:
        csv.field_size_limit(before)


def _restored_profile(
    rows: Iterator[dict[str, Any]], member: FrozenMbsMember
) -> dict[str, Any]:
    identity = _member_identity(member)
    records = fields = empty = 0
    widths: Counter[int] = Counter()
    digest = hashlib.sha256()
    for row in rows:
        raw: object = row["native_fields"]
        if not isinstance(raw, list):
            raise TypeError("MBS native CSV restored field state differs")
        native = cast("list[object]", raw)
        if (
            row["record_ordinal"] != records
            or row["native_record_id"] != f"{identity}:/records/{records}"
            or any(not isinstance(value, str) for value in native)
        ):
            raise ValueError(
                "MBS native CSV restored identity or field state differs"
            )
        digest.update(
            json.dumps(
                [records, native], ensure_ascii=False, separators=(",", ":")
            ).encode()
            + b"\n"
        )
        records += 1
        fields += len(native)
        empty += not native
        widths[len(native)] += 1
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


def _parquet_fingerprint(output: Path) -> dict[str, Any]:
    if (output / DATA_FILE).stat().st_size > MAX_PARQUET_BYTES:
        raise ValueError("MBS native CSV package byte bound exceeded")
    return file_fingerprint(output / DATA_FILE)


def _manifest(
    output: Path, member: FrozenMbsMember, coverage: dict[str, Any]
) -> dict[str, Any]:
    identity = {
        "schema_id": "global-medicines-atlas.mbs-historical-native-csv-package",
        "schema_version": 1,
        "candidate_only": True,
        "member_binding": json.loads(canonical_package_json(asdict(member))),
        "coverage": coverage,
        "parquet": _parquet_fingerprint(output),
        "boundaries": dict(BOUNDARIES),
    }
    return {
        **identity,
        "output_id": hashlib.sha256(
            canonical_package_json(identity)
        ).hexdigest(),
    }


def verify_csv_package(
    output: Path, path: Path, member: FrozenMbsMember, native_path: str
) -> dict[str, Any]:
    """Verify exact schema/lineage and full native digest using a separate parse."""
    _bind(path, member, native_path)
    if {p.name for p in output.iterdir()} != {DATA_FILE, MANIFEST} or any(
        p.is_symlink() or not p.is_file() for p in output.iterdir()
    ):
        raise ValueError("MBS native CSV package inventory differs")
    if (output / MANIFEST).stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("MBS native CSV manifest byte bound exceeded")
    report = json.loads((output / MANIFEST).read_bytes())
    if report.get("parquet") != _parquet_fingerprint(output):
        raise ValueError("MBS native CSV package digest or size differs")
    parquet = pq.ParquetFile(output / DATA_FILE)
    if not parquet.schema_arrow.equals(
        _schema(member, native_path), check_metadata=True
    ):
        raise ValueError("MBS native CSV restored schema or lineage differs")
    rows = (
        row
        for batch in parquet.iter_batches(batch_size=1024)  # pyright: ignore[reportUnknownMemberType] -- unused Arrow selectors
        for row in batch.to_pylist()
    )  # pyright: ignore[reportUnknownMemberType] -- unused Arrow selectors
    actual = _restored_profile(rows, member)
    expected = formats.profile_native_csv(path)
    if actual != expected:
        raise ValueError(
            "MBS native CSV independent native coverage or parity differs"
        )
    if report != _manifest(output, member, expected):
        raise ValueError(
            "MBS native CSV package qualification or coverage differs"
        )
    _bind(path, member, native_path)
    return report


def build_csv_package(
    path: Path, member: FrozenMbsMember, native_path: str, output: Path
) -> dict[str, Any]:
    """Finalize only after complete native restore; never overwrite existing work."""
    if output.exists() or output.is_symlink():
        raise FileExistsError("MBS native CSV package already exists")
    _bind(path, member, native_path)
    expected = formats.profile_native_csv(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=".mbs-native-csv-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "package"
        staged.mkdir()
        with candidate_parquet_writer(
            staged / DATA_FILE, _schema(member, native_path)
        ) as writer:
            for batch in _batches(path, member, native_path):
                writer.write_batch(batch)
                if (staged / DATA_FILE).stat().st_size > MAX_PARQUET_BYTES:
                    raise ValueError(
                        "MBS native CSV package byte bound exceeded"
                    )
        report = _manifest(staged, member, expected)
        (staged / MANIFEST).write_bytes(canonical_package_json(report))
        verify_csv_package(staged, path, member, native_path)
        staged.rename(output)
    return report


def qualify_csv_member_package(
    path: Path, member: FrozenMbsMember, native_path: str
) -> dict[str, Any]:
    """Check two native packages and actual DuckDB record/field denominators.

    Private source names and values remain inside temporary Parquet metadata
    and arrays; the returned manifest binds them through the output digest.
    """
    with TemporaryDirectory(
        prefix="mbs-native-csv-qualification-"
    ) as temporary:
        root = Path(temporary)
        first = build_csv_package(path, member, native_path, root / "first")
        second = build_csv_package(path, member, native_path, root / "second")
        if first != second:
            raise ValueError("MBS native CSV independent builds differ")
        with duckdb.connect(":memory:") as connection:
            result = connection.execute(
                "SELECT count(*), coalesce(sum(len(native_fields)), 0) FROM read_parquet(?)",
                [str(root / "first" / DATA_FILE)],
            ).fetchone()
        expected = first["coverage"]
        if result is None or result != (
            expected["records"],
            expected["native_fields"],
        ):
            raise ValueError("MBS native CSV DuckDB denominators differ")
        return {
            "manifest": first,
            "two_builds_equal": True,
            "complete_native_restore_verified": True,
            "duckdb_records": result[0],
            "duckdb_native_fields": result[1],
            "native_values_or_names_emitted": False,
        }
