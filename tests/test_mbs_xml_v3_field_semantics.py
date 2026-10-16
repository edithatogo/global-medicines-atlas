from pathlib import Path

from global_medicines_atlas.adapters.au_mbs import MBS_NATIVE_FIELDS


def test_mbs_v3_semantics_document_covers_native_field_denominator() -> None:
    document = Path(
        "docs/qualification/mbs-xml-v3-field-semantics.md"
    ).read_text(encoding="utf-8")

    assert all(f"`{field}`" in document for field in MBS_NATIVE_FIELDS)
    assert (
        "db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556"
        in document
    )
    assert "239,560 field occurrences" in document
    assert "M-109 remains partial and blocked" in document


def test_mbs_v3_semantics_document_keeps_other_eras_separate() -> None:
    document = Path(
        "docs/qualification/mbs-xml-v3-field-semantics.md"
    ).read_text(encoding="utf-8")

    assert "not carried to the P7 workbook or another" in document
    assert (
        "PBS April 2026 XML v3 has an exact date grammar profile only"
        in document
    )
    assert "current API payload has been requested or" in document
    assert "acquired; this document does not authorize it" in document
