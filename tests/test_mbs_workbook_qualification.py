"""Workbook qualification is loss-aware and tested without live payloads."""

import hashlib
import json
from io import BytesIO
from zipfile import ZipFile

import httpx
import pyarrow as pa
import pytest
from test_mbs_workbook_silver import (
    _payload,  # ruff: ignore[import-private-name] -- shared synthetic builder
    _receipt,  # ruff: ignore[import-private-name] -- shared synthetic builder
)

from global_medicines_atlas import mbs_workbook_qualification as qualification
from global_medicines_atlas.mbs_workbook_qualification import (
    acquire_hosted_workbook,
    qualify_workbook_cells,
)


def test_qualification_preserves_all_sheet_denominators() -> None:
    payload = _payload()
    result = qualify_workbook_cells(payload, _receipt(payload))
    assert result["cells"] == 30
    assert result["sheet_count"] == 4
    assert result["parquet_roundtrip_verified"] is True
    sheets = result["sheets"]
    assert isinstance(sheets, list)
    assert [sheet["cells"] for sheet in sheets] == [10, 10, 10, 0]
    assert sheets[0]["formula_cells"] == 2
    assert sheets[0]["error_cells"] == 1
    assert sheets[0]["conversion_statuses"]["converted"] == 3
    assert sheets[0]["header_candidates"][0]["display_value"] == "Element"
    assert "synthetic-token" not in json.dumps(result)
    assert result["qualification"] == "storage_candidate_only"


def test_invalid_conversion_is_counted_without_losing_source() -> None:
    payload = _payload('<c r="J2" t="n"><v>1e999999</v></c>')
    result = qualify_workbook_cells(payload, _receipt(payload))
    assert result["sheets"][0]["conversion_statuses"]["unrepresentable"] == 1
    assert result["sheets"][0]["cells"] == 11


def test_qualification_rejects_receipt_mismatch() -> None:
    payload = _payload()
    with pytest.raises(ValueError, match="source bytes"):
        qualify_workbook_cells(payload, _receipt(b"wrong"))


def test_native_epoch_and_styles_are_reported_not_interpreted() -> None:
    output = BytesIO()
    with ZipFile(BytesIO(_payload())) as source, ZipFile(output, "w") as dest:
        for entry in source.infolist():
            value = source.read(entry)
            if entry.filename == "xl/workbook.xml":
                value = value.replace(
                    b"<sheets>", b'<workbookPr date1904="1"/><sheets>'
                )
            dest.writestr(entry, value)
        dest.writestr(
            "xl/styles.xml",
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts><cellXfs><xf numFmtId="164" applyNumberFormat="1"/></cellXfs></styleSheet>',
        )
    payload = output.getvalue()
    result = qualify_workbook_cells(payload, _receipt(payload))
    evidence = result["format_evidence"]
    assert evidence["workbook_properties"] == {"date1904": "1"}
    assert evidence["number_formats"][0]["formatCode"] == "dd/mm/yyyy"
    assert evidence["cell_formats"][0]["style_index"] == 0
    assert evidence["interpretation"] == "native_attributes_only"
    assert result["domain_mapping_qualified"] is False


def test_live_acquisition_fails_locally_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    def reject(_request: httpx.Request) -> httpx.Response:
        pytest.fail("network reached before hosted guard")

    with (
        httpx.Client(transport=httpx.MockTransport(reject)) as client,
        pytest.raises(ValueError, match="requires main Actions"),
    ):
        acquire_hosted_workbook(client)


@pytest.mark.parametrize("body", [b"fixture", b"changed", b"too-long-payload"])
def test_hosted_acquisition_checks_exact_size_and_digest(
    monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "edithatogo/global-medicines-atlas")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setattr(qualification, "LEGACY_P7_BYTES", 7)
    monkeypatch.setattr(
        qualification,
        "LEGACY_P7_SHA256",
        hashlib.sha256(b"fixture").hexdigest(),
    )

    def response(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == qualification.PUBLIC_WORKBOOK_URI
        assert "authorization" not in request.headers
        return httpx.Response(200, content=body)

    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        if body == b"fixture":
            assert acquire_hosted_workbook(client) == body
        else:
            with pytest.raises(ValueError, match=r"(identity|size)"):
                acquire_hosted_workbook(client)


def test_roundtrip_corruption_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        qualification.pq,
        "read_table",
        lambda *_args, **_kwargs: pa.table({"corrupt": [1]}),
    )
    payload = _payload()
    with pytest.raises(ValueError, match="roundtrip"):
        qualify_workbook_cells(payload, _receipt(payload))


def test_dropped_cells_fail_denominator_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        qualification,
        "iter_workbook_silver_batches",
        lambda *_args, **_kwargs: iter(()),
    )
    payload = _payload()
    with pytest.raises(ValueError, match="denominator"):
        qualify_workbook_cells(payload, _receipt(payload))


def test_later_rows_are_not_mislabeled_header_candidates() -> None:
    payload = _payload('<c r="J3" t="inlineStr"><is><t>not header</t></is></c>')
    result = qualify_workbook_cells(payload, _receipt(payload))
    assert result["sheets"][0]["cells"] == 11
    assert len(result["sheets"][0]["header_candidates"]) == 10
