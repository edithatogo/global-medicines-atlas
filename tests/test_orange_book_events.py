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
    assert result[1]["approval_before_date"] == "1982-01-01"
    assert all(
        row["approval_before_date"] is None for row in (result[0], *result[2:])
    )
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


@pytest.mark.parametrize("row", ["A~1~1\n", "A~1~1~Jan 02, 2001~extra\n"])
def test_malformed_product_rows_fail_closed(row):
    with pytest.raises(ValueError, match="malformed"):
        product_events(payload(row), {"us-drugsfda:ANDA000001:001"})


def test_unsupported_or_malformed_native_keys_do_not_join():
    result = product_events(
        payload(
            "B~1~1~Jan 02, 2001\nA~bad~1~Jan 02, 2001\nA~1~bad~Jan 02, 2001\n"
        ),
        {"us-drugsfda:ANDA000001:001"},
    )
    assert result[0]["qualification"] == "unmatched"
    assert result[0]["approval_date"] is None


def test_ambiguous_and_oversized_members_fail_closed():
    for names in (("other.txt",), ("products.txt", "Products.txt")):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            for name in names:
                archive.writestr(name, "synthetic")
        with pytest.raises(ValueError, match=r"ambiguous|oversized"):
            product_events(stream.getvalue(), set())
    stream = io.BytesIO()
    with zipfile.ZipFile(
        stream, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        archive.writestr("products.txt", b"x" * (20 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="oversized"):
        product_events(stream.getvalue(), set())


def test_duplicate_required_headers_fail_closed():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "products.txt",
            "Appl_Type~Appl_No~Product_No~Approval_Date~Approval_Date\n",
        )
    with pytest.raises(ValueError, match="schema"):
        product_events(stream.getvalue(), set())
