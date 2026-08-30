"""Typed table admission must not concatenate heterogeneous donor data."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest

from global_medicines_atlas import mbs_tables
from global_medicines_atlas.mbs_compatibility import (
    historical_targets,
    rehearse_probes,
)
from global_medicines_atlas.mbs_tables import (
    TableContract,
    mbs_html_table_parquet,
    parse_mbs_html_tables,
)
from global_medicines_atlas.receipts import SourceReceipt
from global_medicines_atlas.reuse_gate import acquire_new_decision

HTML = b"""<html><table><tr><th>Item</th><th>Benefit</th></tr>
<tr><td>00104</td><td>42.50</td></tr></table>
<table><tr><th>Month</th><th>Participants</th></tr>
<tr><td>202401</td><td>123</td></tr></table></html>"""
CONTRACTS = (
    TableContract(table_id="item-benefits", columns=("Item", "Benefit")),
    TableContract(table_id="participants", columns=("Month", "Participants")),
)


def _receipt(tmp_path: Path, payload: bytes) -> SourceReceipt:
    result = rehearse_probes(
        historical_targets((), 202401, 202401),
        tmp_path,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, content=payload, headers={"content-type": "text/html"}
            )
        ),
        reuse_decision=acquire_new_decision("au-mbs"),
        clock=lambda: datetime(2026, 8, 30, tzinfo=UTC),
        sleep=lambda _: None,
    )
    receipt = result.attempts[0]
    assert isinstance(receipt, SourceReceipt)
    return receipt


def test_heterogeneous_tables_keep_separate_schema_and_source(
    tmp_path: Path,
) -> None:
    tables = parse_mbs_html_tables(HTML, _receipt(tmp_path, HTML), CONTRACTS)
    assert len(tables) == 2
    assert tables[0].table_id == "item-benefits"
    assert tables[1].table_id == "participants"
    assert tables[0].rows == (("00104", "42.50"),)
    assert tables[1].rows == (("202401", "123"),)
    assert (
        tables[0].provenance.source_sha256 == tables[1].provenance.source_sha256
    )
    assert tables[1].table_ordinal == 1
    payload = mbs_html_table_parquet(tables[0])
    assert payload == mbs_html_table_parquet(tables[0])
    restored = pq.read_table(BytesIO(payload))
    assert restored.to_pylist() == [{"Item": "00104", "Benefit": "42.50"}]
    assert restored.schema.metadata[b"table_id"] == b"item-benefits"


@pytest.mark.parametrize(
    "payload",
    [
        b"<html>maintenance</html>",
        HTML.replace(b"Benefit", b"Changed"),
        HTML.replace(b"<td>42.50</td>", b""),
        HTML.replace(b"</table>", b"", 1),
        HTML.replace(b"<td>42.50", b'<td colspan="2">42.50'),
    ],
)
def test_no_data_drift_or_unsupported_layout_fails(
    tmp_path: Path, payload: bytes
) -> None:
    with pytest.raises(ValueError, match=r"table|schema|row|span"):
        parse_mbs_html_tables(payload, _receipt(tmp_path, payload), CONTRACTS)


def test_digest_mismatch_is_not_admission(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="match source bytes"):
        parse_mbs_html_tables(HTML + b" ", _receipt(tmp_path, HTML), CONTRACTS)


def test_duplicate_table_contract_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unique"):
        parse_mbs_html_tables(
            HTML, _receipt(tmp_path, HTML), (CONTRACTS[0], CONTRACTS[0])
        )


def test_empty_rows_do_not_create_data(tmp_path: Path) -> None:
    payload = b"<table><tr><th>Item</th></tr><tr><td> </td></tr></table>"
    with pytest.raises(ValueError, match="nonempty"):
        parse_mbs_html_tables(
            payload,
            _receipt(tmp_path, payload),
            (TableContract(table_id="items", columns=("Item",)),),
        )


@pytest.mark.parametrize("columns", [("",), ("Item", "Item")])
def test_contract_headers_are_nonempty_and_unique(
    columns: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError, match="nonempty and unique"):
        TableContract(table_id="example", columns=columns)


@pytest.mark.parametrize(
    "payload",
    [
        b"<table><tr><tr>",
        b"<table><td>",
        b"<table><tr></td>",
        b"<table></tr>",
        b"<table><tr></table>",
        b"<table><tr><td></tr>",
    ],
)
def test_malformed_table_nesting_fails(tmp_path: Path, payload: bytes) -> None:
    with pytest.raises(ValueError, match=r"table|row|cell"):
        parse_mbs_html_tables(payload, _receipt(tmp_path, payload), CONTRACTS)


@pytest.mark.parametrize(
    "bound", ["MAX_HTML_BYTES", "MAX_TABLES", "MAX_ROWS", "MAX_COLUMNS"]
)
def test_table_resource_bounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bound: str
) -> None:
    receipt = _receipt(tmp_path, HTML)
    monkeypatch.setattr(mbs_tables, bound, 1)
    with pytest.raises(ValueError, match=r"bound|excessive"):
        parse_mbs_html_tables(HTML, receipt, CONTRACTS)


def test_inline_elements_and_entities_are_text_not_schema(
    tmp_path: Path,
) -> None:
    payload = HTML.replace(b"00104", b"<b>00</b>104 &amp; x")
    tables = parse_mbs_html_tables(
        payload, _receipt(tmp_path, payload), CONTRACTS
    )
    assert tables[0].rows[0][0] == "00104 & x"
