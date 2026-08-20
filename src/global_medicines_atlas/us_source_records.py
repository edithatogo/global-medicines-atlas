"""Source-native Bronze records for authorized U.S. payload families."""

# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import csv
import zipfile
from collections.abc import Iterable, Mapping
from hashlib import sha256
from io import BytesIO, StringIO

import orjson
import pyarrow as pa

from .archive_safety import inspect_zip
from .bronze_landing import SourceRecordBatch

_OPENFDA_IDENTIFIERS: dict[str, tuple[str, ...]] = {
    "us-openfda-drugsfda": ("application_number",),
    "us-openfda-enforcement": ("recall_number", "event_id"),
    "us-openfda-faers": ("safetyreportid", "safetyreportversion"),
    "us-openfda-ndc": ("product_ndc",),
    "us-openfda-nsde": ("package_ndc11", "package_ndc"),
    "us-fda-drug-shortages": (
        "package_ndc",
        "initial_posting_date",
        "update_date",
    ),
}
_DRUGSFDA_MEMBERS = frozenset({
    "ActionTypes_Lookup.txt",
    "ApplicationDocs.txt",
    "Applications.txt",
    "ApplicationsDocsType_Lookup.txt",
    "Join_Submission_ActionTypes_Lookup.txt",
    "MarketingStatus.txt",
    "MarketingStatus_Lookup.txt",
    "Products.txt",
    "SubmissionClass_Lookup.txt",
    "SubmissionPropertyType.txt",
    "Submissions.txt",
    "TE.txt",
})
_ORANGE_BOOK_MEMBERS = frozenset({
    "exclusivity.txt",
    "patent.txt",
    "products.txt",
})
_NSDE_MEMBERS = frozenset({
    "Comprehensive_NDC_SPL_Data_Elements_File.csv",
})
_ARCHIVE_SPECS: dict[str, tuple[frozenset[str], str]] = {
    "us-drugsfda": (_DRUGSFDA_MEMBERS, "\t"),
    "us-fda-orange-book": (_ORANGE_BOOK_MEMBERS, "~"),
    "us-fda-nsde": (_NSDE_MEMBERS, ","),
}
_TECHNICAL_COLUMNS = (
    "source_record_key",
    "source_member",
    "source_table",
    "source_row_number",
    "source_field_count",
)
_UNLABELLED_FIELD_PREFIX = "source_unlabelled_field_"


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return {str(key): item for key, item in value.items()}


def _native_identity(
    record: Mapping[str, object],
    fields: tuple[str, ...],
    row_number: int,
) -> str:
    values = [str(record[field]) for field in fields if record.get(field)]
    if values:
        return ":".join(values)
    digest = sha256(orjson.dumps(dict(record), option=orjson.OPT_SORT_KEYS))
    return f"row:{row_number}:{digest.hexdigest()}"


def _deduplicate_identities(identities: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    for identity in identities:
        counts[identity] = counts.get(identity, 0) + 1
    return [
        identity if counts[identity] == 1 else f"{identity}:row:{index}"
        for index, identity in enumerate(identities, start=1)
    ]


def _openfda_batch(source_id: str, payload: bytes) -> SourceRecordBatch:
    document = _object(orjson.loads(payload), "openFDA payload")
    results = document.get("results")
    if not isinstance(results, list):
        raise TypeError("openFDA results must be a list")
    records = [
        _object(item, f"openFDA result {index}")
        for index, item in enumerate(results, start=1)
    ]
    identities = _deduplicate_identities([
        _native_identity(record, _OPENFDA_IDENTIFIERS[source_id], index)
        for index, record in enumerate(records, start=1)
    ])
    if any("source_record_key" in record for record in records):
        raise ValueError("source payload collides with technical record key")
    table = pa.Table.from_pylist(records)
    table = table.add_column(
        0,
        "source_record_key",
        pa.array(identities, type=pa.string()),
    )
    return SourceRecordBatch(
        table=table,
        parser_identity=f"gma:{source_id}:openfda-json:v1",
        record_id_column="source_record_key",
    )


def _decode_member(payload: bytes) -> str:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return payload.decode("cp1252")


def _validated_header(header: list[str], member: str) -> list[str]:
    if not header:
        raise ValueError(f"archive member has no header: {member}")
    if any(not name for name in header):
        raise ValueError(f"archive member has an empty header: {member}")
    if len(header) != len(set(header)):
        raise ValueError(f"archive member has duplicate columns: {member}")
    collisions = set(header).intersection(_TECHNICAL_COLUMNS)
    collisions.update(
        name for name in header if name.startswith(_UNLABELLED_FIELD_PREFIX)
    )
    if collisions:
        raise ValueError(
            f"archive member collides with technical columns: {member}"
        )
    return header


def _header(
    reader: Iterable[list[str]], member: str
) -> tuple[list[str], list[list[str]]]:
    rows = list(reader)
    if not rows:
        raise ValueError(f"archive member has no header: {member}")
    header = _validated_header(rows[0], member)
    return header, rows[1:]


def _archive_batch(
    source_id: str,
    payload: bytes,
    expected_members: frozenset[str],
    delimiter: str,
) -> SourceRecordBatch:
    inspect_zip(payload)
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        member_names = frozenset(
            item.filename for item in archive.infolist() if not item.is_dir()
        )
        if member_names != expected_members:
            raise ValueError(
                f"{source_id} archive member set does not match contract"
            )
        native_columns: list[str] = []
        records: list[dict[str, str | int | None]] = []
        for member in sorted(member_names):
            text = _decode_member(archive.read(member))
            reader = csv.reader(StringIO(text, newline=""), delimiter=delimiter)
            header, rows = _header(reader, member)
            native_columns.extend(
                name for name in header if name not in native_columns
            )
            for row_number, values in enumerate(rows, start=1):
                if not values or (len(values) == 1 and not values[0]):
                    continue
                record: dict[str, str | int | None] = {
                    "source_record_key": f"{member}:{row_number}",
                    "source_member": member,
                    "source_row_number": row_number,
                    "source_field_count": len(values),
                }
                record.update(dict(zip(header, values, strict=False)))
                for offset, value in enumerate(values[len(header) :], start=1):
                    column = f"{_UNLABELLED_FIELD_PREFIX}{offset}"
                    if column not in native_columns:
                        native_columns.append(column)
                    record[column] = value
                records.append(record)
    schema = pa.schema([
        pa.field("source_record_key", pa.string(), nullable=False),
        pa.field("source_member", pa.string(), nullable=False),
        pa.field("source_row_number", pa.int64(), nullable=False),
        pa.field("source_field_count", pa.int64(), nullable=False),
        *(pa.field(name, pa.string()) for name in native_columns),
    ])
    return SourceRecordBatch(
        table=pa.Table.from_pylist(records, schema=schema),
        parser_identity=f"gma:{source_id}:fda-archive:v2",
        record_id_column="source_record_key",
    )


def _ndc_directory_batch(payload: bytes) -> SourceRecordBatch:
    """Project the current FDA NDC text-table family without XLS aliases."""
    inspect_zip(payload)
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        members = tuple(
            item.filename for item in archive.infolist() if not item.is_dir()
        )
        text_members = tuple(
            member for member in members if member.casefold().endswith(".txt")
        )
        if not text_members:
            raise ValueError("NDC directory archive has no text tables")
        unsupported = tuple(
            member
            for member in members
            if not member.casefold().endswith((".txt", ".xls"))
        )
        if unsupported:
            raise ValueError("NDC directory archive has unsupported members")
        native_columns: list[str] = []
        records: list[dict[str, str | int | None]] = []
        for member in sorted(text_members):
            reader = csv.reader(
                StringIO(_decode_member(archive.read(member)), newline=""),
                delimiter="\t",
            )
            header, rows = _header(reader, member)
            native_columns.extend(
                name for name in header if name not in native_columns
            )
            for row_number, values in enumerate(rows, start=1):
                if not values or (len(values) == 1 and not values[0]):
                    continue
                record: dict[str, str | int | None] = {
                    "source_record_key": f"{member}:{row_number}",
                    "source_member": member,
                    "source_row_number": row_number,
                    "source_field_count": len(values),
                }
                record.update(dict(zip(header, values, strict=False)))
                for offset, value in enumerate(values[len(header) :], start=1):
                    column = f"{_UNLABELLED_FIELD_PREFIX}{offset}"
                    if column not in native_columns:
                        native_columns.append(column)
                    record[column] = value
                records.append(record)
    schema = pa.schema([
        pa.field("source_record_key", pa.string(), nullable=False),
        pa.field("source_member", pa.string(), nullable=False),
        pa.field("source_row_number", pa.int64(), nullable=False),
        pa.field("source_field_count", pa.int64(), nullable=False),
        *(pa.field(name, pa.string()) for name in native_columns),
    ])
    return SourceRecordBatch(
        table=pa.Table.from_pylist(records, schema=schema),
        parser_identity="gma:us-fda-ndc-directory:text-archive:v1",
        record_id_column="source_record_key",
    )


_FAERS_TABLE_PREFIXES = {
    "DEMO": "demographic",
    "DRUG": "drug",
    "INDI": "indication",
    "OUTC": "outcome",
    "REAC": "reaction",
    "RPSR": "reporter",
    "THER": "therapy",
    "STAT": "statistics",
    "SIZE": "size",
    "DELE": "deleted_case",
}
_FAERS_CORE_TABLES = frozenset({
    "demographic",
    "drug",
    "indication",
    "outcome",
    "reaction",
    "reporter",
    "therapy",
})


def _faers_table(member: str) -> str | None:
    filename = member.rsplit("/", 1)[-1]
    if not filename.casefold().endswith(".txt"):
        return None
    if filename.casefold().endswith("deletedcases.txt"):
        return "deleted_case"
    prefix = filename[:4].upper()
    table = _FAERS_TABLE_PREFIXES.get(prefix)
    if table is None:
        raise ValueError(f"FAERS archive has unsupported text table: {member}")
    return table


def _faers_ascii_batch(payload: bytes) -> SourceRecordBatch:
    """Preserve every relational ASCII table without case-version collapse."""
    inspect_zip(payload)
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        members = tuple(
            item.filename for item in archive.infolist() if not item.is_dir()
        )
        table_members = tuple(
            (member, table)
            for member in members
            if (table := _faers_table(member)) is not None
        )
        observed_tables = frozenset(table for _, table in table_members)
        missing = _FAERS_CORE_TABLES - observed_tables
        if missing:
            raise ValueError(
                "FAERS archive is missing core tables: "
                + ", ".join(sorted(missing))
            )
        native_columns: list[str] = []
        records: list[dict[str, str | int | None]] = []
        for member, table in sorted(table_members):
            reader = csv.reader(
                StringIO(_decode_member(archive.read(member)), newline=""),
                delimiter="$",
            )
            try:
                header = _validated_header(next(reader), member)
            except StopIteration as error:
                raise ValueError(
                    f"archive member has no header: {member}"
                ) from error
            native_columns.extend(
                name for name in header if name not in native_columns
            )
            for row_number, values in enumerate(reader, start=1):
                if not values or (len(values) == 1 and not values[0]):
                    continue
                record: dict[str, str | int | None] = {
                    "source_record_key": f"{member}:{row_number}",
                    "source_member": member,
                    "source_table": table,
                    "source_row_number": row_number,
                    "source_field_count": len(values),
                }
                record.update(dict(zip(header, values, strict=False)))
                for offset, value in enumerate(values[len(header) :], start=1):
                    column = f"{_UNLABELLED_FIELD_PREFIX}{offset}"
                    if column not in native_columns:
                        native_columns.append(column)
                    record[column] = value
                records.append(record)
    schema = pa.schema([
        pa.field("source_record_key", pa.string(), nullable=False),
        pa.field("source_member", pa.string(), nullable=False),
        pa.field("source_table", pa.string(), nullable=False),
        pa.field("source_row_number", pa.int64(), nullable=False),
        pa.field("source_field_count", pa.int64(), nullable=False),
        *(pa.field(name, pa.string()) for name in native_columns),
    ])
    return SourceRecordBatch(
        table=pa.Table.from_pylist(records, schema=schema),
        parser_identity="gma:us-fda-faers:ascii-archive:v1",
        record_id_column="source_record_key",
    )


def _single_json_member(payload: bytes) -> bytes:
    inspect_zip(payload)
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        members = tuple(
            item.filename for item in archive.infolist() if not item.is_dir()
        )
        if len(members) != 1 or not members[0].casefold().endswith(".json"):
            raise ValueError(
                "openFDA bulk archive must contain one JSON member"
            )
        return archive.read(members[0])


def _rems_csv_batch(payload: bytes) -> SourceRecordBatch:
    """Preserve one official REMS relational CSV at its native grain."""
    rows = [
        row
        for row in csv.reader(
            StringIO(_decode_member(payload), newline=""), skipinitialspace=True
        )
        if row and any(value.strip() for value in row)
    ]
    if not rows:
        raise ValueError("REMS CSV has no header")
    header = _validated_header(rows[0], "REMS CSV")
    if "REMSID" not in header:
        raise ValueError("REMS CSV lacks REMSID")
    identity_columns = ["REMSID"]
    identity_columns.extend(
        candidate
        for candidate in ("VersionID", "REMS_Product_ID", "Application_Number")
        if candidate in header
    )
    records: list[dict[str, str | int | None]] = []
    identities: list[str] = []
    for row_number, values in enumerate(rows[1:], start=1):
        native = dict(zip(header, values, strict=False))
        identity = ":".join(
            native[column].strip()
            for column in identity_columns
            if native.get(column)
        )
        identities.append(identity or f"row:{row_number}")
        record: dict[str, str | int | None] = {
            "source_record_key": "",
            "source_row_number": row_number,
            "source_field_count": len(values),
        }
        record.update(native)
        records.append(record)
    for record, identity in zip(
        records, _deduplicate_identities(identities), strict=True
    ):
        record["source_record_key"] = identity
    schema = pa.schema([
        pa.field("source_record_key", pa.string(), nullable=False),
        pa.field("source_row_number", pa.int64(), nullable=False),
        pa.field("source_field_count", pa.int64(), nullable=False),
        *(pa.field(name, pa.string()) for name in header),
    ])
    return SourceRecordBatch(
        table=pa.Table.from_pylist(records, schema=schema),
        parser_identity="gma:us-fda-rems:relational-csv:v1",
        record_id_column="source_record_key",
    )


def us_source_record_batch(  # ruff: ignore[too-many-return-statements]
    source_id: str,
    payload: bytes,
    media_hint: str,
) -> SourceRecordBatch | None:
    """Project an authorized payload to source-native Bronze records."""

    if source_id in _OPENFDA_IDENTIFIERS:
        if media_hint == "zip":
            return _openfda_batch(source_id, _single_json_member(payload))
        if media_hint == "json":
            return _openfda_batch(source_id, payload)
        raise ValueError(f"{source_id} requires json or zip media")
    if source_id == "us-fda-ndc-directory":
        if media_hint != "zip":
            raise ValueError("us-fda-ndc-directory requires zip media")
        return _ndc_directory_batch(payload)
    if source_id == "us-fda-faers":
        if media_hint != "zip":
            raise ValueError("us-fda-faers requires zip media")
        return _faers_ascii_batch(payload)
    if source_id == "us-fda-rems":
        if media_hint != "csv":
            return None
        return _rems_csv_batch(payload)
    archive_spec = _ARCHIVE_SPECS.get(source_id)
    if archive_spec is not None:
        if media_hint != "zip":
            raise ValueError(f"{source_id} requires zip media")
        return _archive_batch(source_id, payload, *archive_spec)
    return None
