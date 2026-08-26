"""Resolve and validate official Open Medic annual archive releases."""

from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
from typing import Final
from urllib.parse import parse_qs, urljoin, urlparse
from zipfile import BadZipFile, ZipFile

import pyarrow as pa
import pyarrow.csv as pacsv
from pydantic import AnyHttpUrl, Field, TypeAdapter

from .bronze_landing import SourceRecordBatch
from .iceberg_ready import IcebergPartitionPolicy
from .models import FrozenModel

OFFICIAL_HOST: Final = "open-data-assurance-maladie.ameli.fr"
EXPECTED_YEARS: Final = tuple(range(2014, 2026))
REFUSAL_MARKER: Final = b"chargements atteinte"
SOURCE_ID: Final = "fr-open-medic"
PARSER_IDENTITY: Final = "fr-open-medic-csv-iso8859-1-v1"
_REQUIRED_COLUMNS: Final = frozenset({
    "atc1",
    "atc2",
    "atc3",
    "atc4",
    "atc5",
    "cip13",
    "top_gen",
    "gen_num",
    "age",
    "sexe",
    "ben_reg",
    "psp_spe",
    "boites",
    "rem",
    "bse",
})
_OPTIONAL_LABEL_COLUMNS: Final = frozenset({
    "l_atc1",
    "l_atc2",
    "l_atc3",
    "l_atc4",
    "l_atc5",
    "l_cip13",
})


class OpenMedicRelease(FrozenModel):
    """One exact official annual Open Medic release."""

    year: int = Field(ge=2014, le=2025)
    archive_url: AnyHttpUrl
    filename: str


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.casefold() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.hrefs.append(href)


def resolve_open_medic_release(
    page: bytes, *, page_url: str, year: int
) -> OpenMedicRelease:
    """Resolve the short-lived official archive URL from a token page."""
    if year not in EXPECTED_YEARS:
        raise ValueError("Open Medic year is outside the reviewed series")
    parser = _Links()
    parser.feed(page.decode("iso-8859-1"))
    expected = f"Open_MEDIC_Base_Complete/OPEN_MEDIC_{year}.zip"
    matches: list[str] = []
    for href in parser.hrefs:
        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        query = parse_qs(parsed.query)
        official_endpoint = (
            parsed.scheme == "https"
            and parsed.hostname == OFFICIAL_HOST
            and parsed.path.endswith("/medicaments/download_file.php")
        )
        exact_resource = (
            query.get("file") == [expected]
            and len(query.get("token", [])) == 1
            and query["token"][0]
        )
        if official_endpoint and exact_resource:
            matches.append(absolute)
    if len(matches) != 1:
        raise ValueError("expected one exact official Open Medic archive link")
    return OpenMedicRelease(
        year=year,
        archive_url=TypeAdapter(AnyHttpUrl).validate_python(matches[0]),
        filename=f"OPEN_MEDIC_{year}.zip",
    )


def inspect_open_medic_archive(payload: bytes, *, year: int) -> tuple[str, ...]:
    """Reject limiter responses and unsafe or year-mismatched ZIP payloads."""
    if REFUSAL_MARKER in payload:
        raise ValueError("Open Medic upstream download limit refusal")
    try:
        with ZipFile(BytesIO(payload)) as archive:
            names = tuple(sorted(archive.namelist()))
            if not names or archive.testzip() is not None:
                raise ValueError("Open Medic archive integrity check failed")
    except BadZipFile as error:
        raise ValueError("Open Medic payload is not a ZIP archive") from error
    if not any(str(year) in name for name in names):
        raise ValueError(
            "Open Medic archive does not identify its release year"
        )
    return names


def _csv_member(payload: bytes, *, year: int) -> tuple[str, tuple[str, ...]]:
    names = inspect_open_medic_archive(payload, year=year)
    csv_names = tuple(
        name for name in names if name.casefold().endswith(".csv")
    )
    expected = f"OPEN_MEDIC_{year}.CSV"
    if csv_names != (expected,):
        raise ValueError("Open Medic archive must contain one exact annual CSV")
    with ZipFile(BytesIO(payload)) as archive, archive.open(expected) as member:
        header = member.readline().decode("iso-8859-1").rstrip("\r\n")
    columns = tuple(header.split(";"))
    folded = tuple(column.casefold() for column in columns)
    if len(folded) != len(set(folded)):
        raise ValueError("Open Medic CSV column names must be unique")
    observed = frozenset(folded)
    if not _REQUIRED_COLUMNS.issubset(observed):
        raise ValueError("Open Medic CSV is missing required source columns")
    if observed - _REQUIRED_COLUMNS - _OPTIONAL_LABEL_COLUMNS:
        raise ValueError("Open Medic CSV contains unreviewed source columns")
    return expected, columns


def open_medic_source_record_batch(
    source_id: str, payload: bytes, media_hint: str
) -> SourceRecordBatch | None:
    """Project one annual source-native CSV without semantic normalization."""
    if source_id != SOURCE_ID or media_hint != "zip":
        return None
    names = inspect_open_medic_archive(payload, year=_year_from_names(payload))
    year = _year_from_member(names[0])
    member_name, columns = _csv_member(payload, year=year)
    column_types = {column: pa.string() for column in columns}
    with (
        ZipFile(BytesIO(payload)) as archive,
        archive.open(member_name) as member,
    ):
        table = pacsv.read_csv(
            member,
            read_options=pacsv.ReadOptions(
                block_size=16 * 1024 * 1024,
                encoding="iso-8859-1",
            ),
            parse_options=pacsv.ParseOptions(delimiter=";"),
            convert_options=pacsv.ConvertOptions(
                column_types=column_types,
                null_values=[],
                strings_can_be_null=False,
            ),
        )
    if table.num_rows == 0:
        raise ValueError("Open Medic CSV must contain source records")
    table = table.append_column(
        "source_release_year",
        pa.array([year] * table.num_rows, type=pa.int16()),
    )
    table = table.append_column(
        "source_row_number",
        pa.array(range(1, table.num_rows + 1), type=pa.int64()),
    )
    return SourceRecordBatch(
        table=table,
        parser_identity=PARSER_IDENTITY,
        record_id_column="source_row_number",
        # ``source_release_year`` is a source-native integer, not a temporal
        # Iceberg field. Large recurring products therefore use the standard
        # acquisition-month fallback while retaining the native year column.
        partition_policy=IcebergPartitionPolicy(recurring=True),
    )


def _year_from_member(name: str) -> int:
    prefix = "OPEN_MEDIC_"
    suffix = ".CSV"
    if not name.startswith(prefix) or not name.endswith(suffix):
        raise ValueError("Open Medic CSV member name is not canonical")
    raw_year = name.removeprefix(prefix).removesuffix(suffix)
    if not raw_year.isdigit() or int(raw_year) not in EXPECTED_YEARS:
        raise ValueError("Open Medic CSV member year is outside reviewed scope")
    return int(raw_year)


def _year_from_names(payload: bytes) -> int:
    try:
        with ZipFile(BytesIO(payload)) as archive:
            csv_names = tuple(
                name
                for name in archive.namelist()
                if name.casefold().endswith(".csv")
            )
    except BadZipFile as error:
        raise ValueError("Open Medic payload is not a ZIP archive") from error
    if len(csv_names) != 1:
        raise ValueError("Open Medic archive must contain one annual CSV")
    return _year_from_member(csv_names[0])
