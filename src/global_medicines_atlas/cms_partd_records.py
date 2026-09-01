"""Source-faithful, streaming CMS Part D record projections."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - fixed argv 7-Zip fallback
import tempfile
import zipfile
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from operator import itemgetter
from pathlib import Path, PurePosixPath
from typing import IO, Literal, cast

import pyarrow as pa
import pyarrow.parquet as pq

_TABULAR_SUFFIXES = {".csv", ".txt"}
_RESERVED = {
    "gma_payload_identity",
    "gma_outer_member_path",
    "gma_inner_member_path",
    "gma_source_row_number",
}
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_MIN_COLUMNS = 2
_COPY_CHUNK_BYTES = 1024 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CMS_PAYLOAD_COUNT = 33
_IDENTITY_PATH_INDEX = 2


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


@contextmanager
def _open_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    *,
    archive_path: Path,
) -> Generator[IO[bytes]]:
    """Open a ZIP member, including CMS Deflate64 variants via 7-Zip."""
    try:
        member = archive.open(info)
    except NotImplementedError:
        executable = shutil.which("7z") or shutil.which("7zz")
        if executable is None:
            raise ValueError(
                "CMS Part D Deflate64 projection requires 7-Zip"
            ) from None
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] - fixed argv
                [
                    executable,
                    "x",
                    "-so",
                    "-bd",
                    str(archive_path),
                    f"-i!{info.filename}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if process.stdout is None:
                raise RuntimeError(
                    "7-Zip stdout pipe was not created"
                ) from None
            copied = 0
            while block := process.stdout.read(_COPY_CHUNK_BYTES):
                copied += len(block)
                if copied > info.file_size:
                    process.kill()
                    raise ValueError(
                        "CMS Part D archive member exceeded declared size"
                    ) from None
                output.write(block)
            _, errors = process.communicate()
            if process.returncode != 0 or copied != info.file_size:
                detail = errors.decode("utf-8", errors="replace").strip()
                raise ValueError(
                    f"CMS Part D 7-Zip extraction failed: {detail}"
                ) from None
            output.seek(0)
            yield output
        return
    with member:
        yield member


@dataclass(frozen=True)
class CMSPartDProjection:
    """One projected source-native table and its durable evidence."""

    outer_member_path: str
    inner_member_path: str | None
    parquet_path: Path
    row_count: int
    column_count: int
    parquet_sha256: str


def _safe_member(path: str) -> str:
    member = PurePosixPath(path)
    if member.is_absolute() or ".." in member.parts or not member.name:
        raise ValueError("CMS Part D archive member path is unsafe")
    return member.as_posix()


def _delimiter(header: str) -> str:
    counts = {
        candidate: header.count(candidate) for candidate in ("\t", ",", "|")
    }
    delimiter, count = max(counts.items(), key=itemgetter(1))
    if count == 0:
        raise ValueError("CMS Part D table has no supported delimiter")
    return delimiter


def _project_stream(
    stream: IO[bytes],
    *,
    payload_identity: str,
    outer_member_path: str,
    inner_member_path: str | None,
    output: Path,
    batch_rows: int = 50_000,
) -> CMSPartDProjection:
    text = io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
    first = text.readline()
    if not first:
        raise ValueError("CMS Part D table is empty")
    delimiter = _delimiter(first)
    rows = csv.reader([first], delimiter=delimiter, strict=True)
    columns = next(rows)
    if (
        len(columns) < _MIN_COLUMNS
        or any(not column.strip() for column in columns)
        or len(columns) != len(set(columns))
        or _RESERVED.intersection(columns)
    ):
        raise ValueError("CMS Part D table headers must be nonempty and unique")

    metadata_columns = [
        "gma_payload_identity",
        "gma_outer_member_path",
        "gma_inner_member_path",
        "gma_source_row_number",
    ]
    schema = pa.schema(
        [(column, pa.string()) for column in columns]
        + [(column, pa.string()) for column in metadata_columns[:3]]
        + [(metadata_columns[3], pa.int64())]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = pq.ParquetWriter(output, schema, compression="zstd")
    reader = csv.reader(text, delimiter=delimiter, strict=True)
    batch: list[dict[str, object]] = []
    count = 0
    try:
        for count, values in enumerate(reader, start=1):
            if len(values) != len(columns):
                raise ValueError(
                    "CMS Part D source row width differs from its header"
                )
            row: dict[str, object] = dict(zip(columns, values, strict=True))
            row.update({
                "gma_payload_identity": payload_identity,
                "gma_outer_member_path": outer_member_path,
                "gma_inner_member_path": inner_member_path or "",
                "gma_source_row_number": count,
            })
            batch.append(row)
            if len(batch) >= batch_rows:
                writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                batch.clear()
        if batch:
            writer.write_table(pa.Table.from_pylist(batch, schema=schema))
    finally:
        writer.close()
    if count == 0:
        output.unlink(missing_ok=True)
        raise ValueError("CMS Part D table contains no source records")
    return CMSPartDProjection(
        outer_member_path=outer_member_path,
        inner_member_path=inner_member_path,
        parquet_path=output,
        row_count=count,
        column_count=len(columns),
        parquet_sha256=_file_sha256(output),
    )


def _project_json(
    stream: IO[bytes],
    *,
    payload_identity: str,
    outer_member_path: str,
    output: Path,
) -> CMSPartDProjection:
    try:
        raw: object = json.load(io.TextIOWrapper(stream, encoding="utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("CMS Part D spending JSON is invalid") from error
    if not isinstance(raw, list) or not raw:
        raise ValueError(
            "CMS Part D spending JSON must be a nonempty record list"
        )
    records: list[dict[str, str | None]] = []
    for candidate in cast("list[object]", raw):
        if not isinstance(candidate, dict):
            raise ValueError(  # ruff: ignore[type-check-without-type-error] - source schema validation
                "CMS Part D spending JSON records must be objects"
            )
        source_record = cast("dict[object, object]", candidate)
        if any(not isinstance(key, str) for key in source_record):
            raise ValueError("CMS Part D spending JSON records must be objects")
        record: dict[str, str | None] = {}
        for key, value in source_record.items():
            if value is not None and not isinstance(value, str):
                raise ValueError(
                    "CMS Part D spending JSON values must be strings or null"
                )
            record[str(key)] = value
        records.append(record)
    columns = tuple(dict.fromkeys(key for record in records for key in record))
    if (
        len(columns) < _MIN_COLUMNS
        or any(not column for column in columns)
        or _RESERVED.intersection(columns)
    ):
        raise ValueError("CMS Part D spending JSON fields are unusable")
    rows: list[dict[str, object]] = []
    for number, record in enumerate(records, start=1):
        row: dict[str, object] = {}
        for column in columns:
            value = record.get(column)
            row[column] = value
        row.update({
            "gma_payload_identity": payload_identity,
            "gma_outer_member_path": outer_member_path,
            "gma_inner_member_path": "",
            "gma_source_row_number": number,
        })
        rows.append(row)
    schema = pa.schema(
        [(column, pa.string()) for column in columns]
        + [
            ("gma_payload_identity", pa.string()),
            ("gma_outer_member_path", pa.string()),
            ("gma_inner_member_path", pa.string()),
            ("gma_source_row_number", pa.int64()),
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        pa.Table.from_pylist(rows, schema=schema), output, compression="zstd"
    )
    return CMSPartDProjection(
        outer_member_path=outer_member_path,
        inner_member_path=None,
        parquet_path=output,
        row_count=len(rows),
        column_count=len(columns),
        parquet_sha256=_file_sha256(output),
    )


def _projection_path(output: Path, outer: str, inner: str | None) -> Path:
    locator = f"{outer}!{inner or ''}"
    label = _SAFE_NAME.sub("-", PurePosixPath(inner or outer).stem).strip("-")
    return (
        output
        / f"{label[:80]}-{sha256(locator.encode()).hexdigest()[:16]}.parquet"
    )


def project_cms_partd_payload(
    payload: Path,
    *,
    family: Literal["formulary", "spending"],
    identity: str,
    output: Path,
) -> tuple[CMSPartDProjection, ...]:
    """Stream every eligible table to independent source-faithful Parquet."""
    projections: list[CMSPartDProjection] = []
    if family == "spending":
        with payload.open("rb") as stream:
            prefix = stream.read(64).lstrip()
            stream.seek(0)
            if prefix.startswith((b"[", b"{")):
                projection = _project_json(
                    stream,
                    payload_identity=identity,
                    outer_member_path=payload.name,
                    output=_projection_path(output, payload.name, None),
                )
            else:
                projection = _project_stream(
                    stream,
                    payload_identity=identity,
                    outer_member_path=payload.name,
                    inner_member_path=None,
                    output=_projection_path(output, payload.name, None),
                )
            projections.append(projection)
        return tuple(projections)

    with zipfile.ZipFile(payload) as outer_archive:
        for outer_info in outer_archive.infolist():
            outer_path = _safe_member(outer_info.filename)
            if (
                outer_info.is_dir()
                or PurePosixPath(outer_path).suffix.lower() != ".zip"
            ):
                continue
            with tempfile.NamedTemporaryFile() as inner_file:
                with _open_member(
                    outer_archive, outer_info, archive_path=payload
                ) as raw_inner:
                    shutil.copyfileobj(
                        raw_inner, inner_file, length=_COPY_CHUNK_BYTES
                    )
                inner_file.flush()
                inner_file.seek(0)
                inner_archive = zipfile.ZipFile(inner_file)
                for inner_info in inner_archive.infolist():
                    inner_path = _safe_member(inner_info.filename)
                    if (
                        inner_info.is_dir()
                        or PurePosixPath(inner_path).suffix.lower()
                        not in _TABULAR_SUFFIXES
                    ):
                        continue
                    with _open_member(
                        inner_archive,
                        inner_info,
                        archive_path=Path(inner_file.name),
                    ) as stream:
                        projections.append(
                            _project_stream(
                                stream,
                                payload_identity=identity,
                                outer_member_path=outer_path,
                                inner_member_path=inner_path,
                                output=_projection_path(
                                    output, outer_path, inner_path
                                ),
                            )
                        )
                inner_archive.close()
    if not projections:
        raise ValueError(
            "CMS Part D formulary archive has no nested tabular records"
        )
    return tuple(projections)


def projection_manifest_rows(
    projections: tuple[CMSPartDProjection, ...],
) -> Iterator[dict[str, object]]:
    """Yield stable manifest rows without exposing runner-local paths."""
    for projection in projections:
        yield {
            "outer_member_path": projection.outer_member_path,
            "inner_member_path": projection.inner_member_path or "",
            "parquet_filename": projection.parquet_path.name,
            "row_count": projection.row_count,
            "column_count": projection.column_count,
            "parquet_sha256": projection.parquet_sha256,
            "parquet_byte_count": projection.parquet_path.stat().st_size,
        }


def _raw_projection_inventory(
    raw_manifest: object,
) -> dict[str, tuple[str, str]]:
    if not isinstance(raw_manifest, dict):
        raise TypeError("CMS Part D raw manifest must be an object")
    manifest = cast("dict[str, object]", raw_manifest)
    raw_payloads = manifest.get("payloads")
    if not isinstance(raw_payloads, list):
        raise TypeError("CMS Part D raw manifest payloads must be a list")
    raw_payloads = cast("list[object]", raw_payloads)
    if len(raw_payloads) != _CMS_PAYLOAD_COUNT:
        raise ValueError("CMS Part D raw manifest must contain 33 payloads")
    expected: dict[str, tuple[str, str]] = {}
    for raw in raw_payloads:
        if not isinstance(raw, dict):
            raise TypeError("CMS Part D raw payload entries must be objects")
        raw = cast("dict[str, object]", raw)
        hub_path = raw.get("hub_path")
        family = raw.get("family")
        digest = raw.get("sha256")
        valid_fields = (
            not isinstance(hub_path, str)
            or not isinstance(family, str)
            or family not in {"formulary", "spending"}
            or not isinstance(digest, str)
            or _SHA256.fullmatch(digest) is None
        )
        if valid_fields:
            raise ValueError("CMS Part D raw payload identity is invalid")
        hub_path = _string(hub_path)
        family = _string(family)
        digest = _string(digest)
        parts = hub_path.split("/")
        if (
            len(parts) <= _IDENTITY_PATH_INDEX
            or _SHA256.fullmatch(parts[_IDENTITY_PATH_INDEX]) is None
        ):
            raise ValueError("CMS Part D raw payload path is invalid")
        identity = parts[_IDENTITY_PATH_INDEX]
        if identity in expected:
            raise ValueError("CMS Part D raw payload identities must be unique")
        expected[identity] = (family, digest)
    return expected


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _string(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("CMS Part D evidence field must be a string")
    return value


def _qualified_projection_rows(projections: object) -> int:
    if not isinstance(projections, list) or not projections:
        raise ValueError("CMS Part D projection entries must be nonempty")
    projections = cast("list[object]", projections)
    calculated_rows = 0
    filenames: set[str] = set()
    for projection in projections:
        if not isinstance(projection, dict):
            raise TypeError("CMS Part D projection entries must be objects")
        projection = cast("dict[str, object]", projection)
        filename = projection.get("parquet_filename")
        row_count = projection.get("row_count")
        byte_count = projection.get("parquet_byte_count")
        digest = projection.get("parquet_sha256")
        valid_name = (
            isinstance(filename, str)
            and PurePosixPath(filename).name == filename
            and filename not in filenames
        )
        valid_digest = isinstance(digest, str) and _SHA256.fullmatch(digest)
        if not (
            valid_name
            and _positive_int(row_count)
            and _positive_int(byte_count)
            and valid_digest
        ):
            raise ValueError("CMS Part D projection evidence is invalid")
        filename = _string(filename)
        row_count = cast("int", row_count)
        filenames.add(filename)
        calculated_rows += row_count
    return calculated_rows


def _qualified_shard(
    shard: object,
    expected: dict[str, tuple[str, str]],
    observed: set[str],
) -> dict[str, object]:
    if not isinstance(shard, dict):
        raise TypeError("CMS Part D projection shards must be objects")
    shard = cast("dict[str, object]", shard)
    identity = shard.get("identity")
    family = shard.get("family")
    valid_identity = (
        isinstance(identity, str)
        and identity in expected
        and identity not in observed
        and family == expected[identity][0]
    )
    valid_contract = (
        shard.get("schema_id")
        == "global-medicines-atlas.cms-partd-source-record-shard"
        and shard.get("schema_version") == 1
        and shard.get("source_values_preserved_as_strings") is True
        and shard.get("cross_plan_year_schema_equivalence_claimed") is False
    )
    if not valid_identity or not valid_contract:
        raise ValueError("CMS Part D projection shard is not qualified")
    projections = shard.get("projections")
    calculated_rows = _qualified_projection_rows(projections)
    projection_count = shard.get("source_record_projection_count")
    record_count = shard.get("source_record_count")
    if not isinstance(projections, list):
        raise TypeError("CMS Part D projection shard products must be a list")
    projection_list = cast("list[object]", projections)
    if (
        projection_count != len(projection_list)
        or not _positive_int(record_count)
        or calculated_rows != record_count
    ):
        raise ValueError("CMS Part D projection shard totals are invalid")
    qualified_identity = _string(identity)
    observed.add(qualified_identity)
    return {
        **shard,
        "raw_payload_sha256": expected[qualified_identity][1],
    }


def qualify_cms_partd_projections(
    raw_manifest: object,
    shards: object,
    *,
    qualified_at: str,
    raw_revision: str,
) -> dict[str, object]:
    """Bind source-record shards to the exact immutable raw inventory."""
    expected = _raw_projection_inventory(raw_manifest)

    if not isinstance(shards, list):
        raise TypeError("CMS Part D projection shards must be a list")
    shards = cast("list[object]", shards)
    if len(shards) != len(expected):
        raise ValueError("CMS Part D projection shards do not match raw count")
    observed: set[str] = set()
    normalized = [_qualified_shard(row, expected, observed) for row in shards]
    if observed != set(expected):
        raise ValueError("CMS Part D projection identities are incomplete")
    normalized.sort(key=lambda item: cast("str", item["identity"]))
    return {
        "schema_id": "global-medicines-atlas.cms-partd-source-record-qualification",
        "schema_version": 1,
        "qualified_at": qualified_at,
        "raw_revision": raw_revision,
        "payload_count": len(expected),
        "source_record_projection_count": sum(
            cast("int", row["source_record_projection_count"])
            for row in normalized
        ),
        "source_record_count": sum(
            cast("int", row["source_record_count"]) for row in normalized
        ),
        "source_values_preserved_as_strings": True,
        "cross_plan_year_schema_equivalence_claimed": False,
        "runner_source_bytes_retained": False,
        "shards": normalized,
    }


def projection_cli() -> None:
    """Run the hosted projection CLI without providing publication capability."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument(
        "--family", choices=("formulary", "spending"), required=True
    )
    parser.add_argument("--identity", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    projections = project_cms_partd_payload(
        args.payload,
        family=args.family,
        identity=args.identity,
        output=args.output,
    )
    payload = {
        "schema_id": "global-medicines-atlas.cms-partd-source-record-shard",
        "schema_version": 1,
        "identity": args.identity,
        "family": args.family,
        "source_record_projection_count": len(projections),
        "source_record_count": sum(item.row_count for item in projections),
        "projections": list(projection_manifest_rows(projections)),
        "source_values_preserved_as_strings": True,
        "cross_plan_year_schema_equivalence_claimed": False,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, sort_keys=True))  # ruff: ignore[print]
