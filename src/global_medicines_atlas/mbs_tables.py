"""Receipt-bound, source-specific admission of simple historical MBS tables."""

from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
from typing import Literal

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import Field, model_validator

from .adapters._receipt import provenance_from_receipt
from .models import FrozenModel, Provenance
from .receipts import SourceReceipt

MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_TABLES = 32
MAX_ROWS = 10000
MAX_COLUMNS = 256


class TableContract(FrozenModel):
    """An explicit schema per table, in source document order."""

    table_id: str = Field(min_length=1)
    columns: tuple[str, ...] = Field(min_length=1, max_length=MAX_COLUMNS)

    @model_validator(mode="after")
    def unique_named_columns(self) -> TableContract:
        """Require an unambiguous schema rather than silently renaming."""
        if any(not name.strip() for name in self.columns) or len(
            set(self.columns)
        ) != len(self.columns):
            raise ValueError("table columns must be nonempty and unique")
        return self


class MbsHtmlTable(FrozenModel):
    """Separate source-native table, never a medicine or merged CSV."""

    source_id: Literal["au-mbs"] = "au-mbs"
    table_id: str = Field(min_length=1)
    table_ordinal: int = Field(ge=0)
    schema_era: Literal["historical-simple-html-v1"] = (
        "historical-simple-html-v1"
    )
    columns: tuple[str, ...] = Field(min_length=1, max_length=MAX_COLUMNS)
    rows: tuple[tuple[str | None, ...], ...] = Field(
        min_length=1, max_length=MAX_ROWS
    )
    provenance: Provenance

    @model_validator(mode="after")
    def validate_table_shape(self) -> MbsHtmlTable:
        """Keep serialized table consumers behind the same schema boundary."""
        TableContract(table_id=self.table_id, columns=self.columns)
        if any(
            len(row) != len(self.columns)
            or not any(value is not None for value in row)
            for row in self.rows
        ):
            raise ValueError(
                "table rows must be nonempty and match schema width"
            )
        return self


class _Tables(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[tuple[str | None, ...]]] = []
        self.table: list[tuple[str | None, ...]] | None = None
        self.row: list[str | None] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag == "table":
            if self.table is not None or len(self.tables) >= MAX_TABLES:
                raise ValueError("nested or excessive tables are unsupported")
            self.table = []
        elif self.table is not None and tag == "tr":
            if self.row is not None:
                raise ValueError("unclosed table row")
            self.row = []
        elif self.table is not None and tag in {"th", "td"}:
            if self.row is None or self.cell is not None:
                raise ValueError("cell outside row or unclosed table cell")
            if any(
                name in {"rowspan", "colspan"} and value != "1"
                for name, value in attrs
            ):
                raise ValueError(
                    "table spans require a separate source profile"
                )
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.table is None:
            return
        if tag in {"th", "td"}:
            if self.cell is None or self.row is None:
                raise ValueError("unexpected table cell terminator")
            self.row.append("".join(self.cell).strip() or None)
            self.cell = None
            if len(self.row) > MAX_COLUMNS:
                raise ValueError("table column bound exceeded")
        elif tag == "tr":
            if self.cell is not None or self.row is None:
                raise ValueError("unclosed table cell or unexpected row end")
            self.table.append(tuple(self.row))
            self.row = None
            if len(self.table) > MAX_ROWS:
                raise ValueError("table row bound exceeded")
        elif tag == "table":
            if self.row is not None or self.cell is not None:
                raise ValueError("unclosed table row or cell")
            self.tables.append(self.table)
            self.table = None


def parse_mbs_html_tables(
    payload: bytes,
    receipt: SourceReceipt,
    contracts: tuple[TableContract, ...],
) -> tuple[MbsHtmlTable, ...]:
    """Admit simple tables only when all source-ordered contracts match.

    Unsupported layouts fail closed; their immutable raw source is retained
    for a future profile rather than silently flattened or discarded.
    """
    if len(payload) > MAX_HTML_BYTES:
        raise ValueError("HTML table byte bound exceeded")
    if not contracts or len({item.table_id for item in contracts}) != len(
        contracts
    ):
        raise ValueError("table contracts must be nonempty and unique")
    provenance = provenance_from_receipt(
        receipt,
        payload,
        source_id="au-mbs",
        jurisdiction="AUS",
        transformation="mbs-historical-simple-html-v1",
    )
    parser = _Tables()
    parser.feed(payload.decode("utf-8"))
    parser.close()
    if parser.table is not None:
        raise ValueError("unclosed table")
    if len(parser.tables) != len(contracts):
        raise ValueError("HTML table count does not match schema contracts")
    result: list[MbsHtmlTable] = []
    for index, (table, contract) in enumerate(
        zip(parser.tables, contracts, strict=True)
    ):
        if not table or table[0] != contract.columns:
            raise ValueError("HTML table header schema drift")
        rows = tuple(
            row for row in table[1:] if any(value is not None for value in row)
        )
        if not rows:
            raise ValueError("HTML table must have nonempty data rows")
        if any(len(row) != len(contract.columns) for row in rows):
            raise ValueError("HTML table row width does not match schema")
        result.append(
            MbsHtmlTable(
                table_id=contract.table_id,
                table_ordinal=index,
                columns=contract.columns,
                rows=rows,
                provenance=provenance,
            )
        )
    return tuple(result)


def mbs_html_table_parquet(table: MbsHtmlTable) -> bytes:
    """Project one table deterministically without mixing source schemas."""
    schema = pa.schema(
        [pa.field(name, pa.string()) for name in table.columns],
        metadata={
            "source_id": table.source_id,
            "table_id": table.table_id,
            "table_ordinal": str(table.table_ordinal),
            "schema_era": table.schema_era,
            "provenance": table.provenance.model_dump_json(),
        },
    )
    arrays = [
        pa.array([row[index] for row in table.rows], type=pa.string())
        for index in range(len(table.columns))
    ]
    output = BytesIO()
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        pa.Table.from_arrays(arrays, schema=schema),
        output,
        compression="zstd",
        version="2.6",
        use_dictionary=False,
    )
    return output.getvalue()
