"""Source-faithful parsing tests for French public tabular payloads."""

from __future__ import annotations

import pytest

from global_medicines_atlas.french_source_records import (
    french_source_record_batch,
)


@pytest.mark.parametrize("encoding", ["utf-8", "cp1252"])
def test_preserves_unlabelled_tabular_fields_and_row_order(
    encoding: str,
) -> None:
    payload = "1\tcafé\r\n\r\n2\tthé\r\n".encode(encoding)
    batch = french_source_record_batch("fr-bdpm", payload)

    assert batch.parser_identity == "gma:fr-bdpm:tabular-text:v1"
    assert batch.record_id_column == "source_record_key"
    assert batch.table.to_pylist() == [
        {
            "source_record_key": "row:1",
            "source_row_number": 1,
            "source_field_count": 2,
            "source_unlabelled_field_1": "1",
            "source_unlabelled_field_2": "café",
        },
        {
            "source_record_key": "row:3",
            "source_row_number": 3,
            "source_field_count": 2,
            "source_unlabelled_field_1": "2",
            "source_unlabelled_field_2": "thé",
        },
    ]


def test_rejects_non_french_source_and_opaque_bytes() -> None:
    with pytest.raises(ValueError, match="unsupported French source"):
        french_source_record_batch("eu-union-register", b"1\tvalue\n")
    with pytest.raises(ValueError, match="NUL"):
        french_source_record_batch("fr-bdpm-smr-asmr", b"1\x00\tvalue\n")
