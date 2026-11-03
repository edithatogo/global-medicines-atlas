from __future__ import annotations

import io
import zipfile

import pytest

from global_medicines_atlas.orange_book_events import product_events


def payload(rows: str) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "products.txt",
            "Appl_Type~Appl_No~Product_No~Approval_Date\n" + rows,
        )
    return stream.getvalue()


def test_product_keys_dates_and_uncertainty():
    concepts = {f"us-drugsfda:ANDA000001:{n:03}" for n in range(1, 6)}
    result = product_events(
        payload(
            "A~1~1~Jan 02, 2001\nA~1~1~Jan 02, 2001\n"
            "A~1~2~Approved prior to Jan 1, 1982\n"
            "A~1~3~Jan 02, 2001\nA~1~3~Jan 03, 2001\n"
            "N~1~4~Jan 02, 2001\nA~1~5~Feb 31, 2001\n"
        ),
        concepts,
    )
    assert result[0]["approval_date"] == "2001-01-02"
    assert [x["qualification"] for x in result] == [
        "exact_product_approval_date",
        "non_exact_native_date",
        "conflicting_dates",
        "unmatched",
        "non_exact_native_date",
    ]
    assert all(x["validity_interval"] is None for x in result)
    assert all(not x["continuing_approval_established"] for x in result)
    assert result == product_events(
        payload(
            "A~1~1~Jan 02, 2001\nA~1~1~Jan 02, 2001\n"
            "A~1~2~Approved prior to Jan 1, 1982\n"
            "A~1~3~Jan 02, 2001\nA~1~3~Jan 03, 2001\n"
            "N~1~4~Jan 02, 2001\nA~1~5~Feb 31, 2001\n"
        ),
        concepts,
    )


def test_missing_schema_rejected():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("products.txt", "Appl_No~Product_No\n1~1\n")
    with pytest.raises(ValueError, match="schema"):
        product_events(stream.getvalue(), set())
