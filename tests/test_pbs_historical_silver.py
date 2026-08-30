"""Historical member Silver preserves source identity without aliases."""

from io import BytesIO
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_au_pbs_v3 import (
    _zip,  # ruff: ignore[import-private-name] -- synthetic fixture
)
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- synthetic fixture
)
from test_pbs_silver import XML

from global_medicines_atlas import pbs_historical_silver as historical
from global_medicines_atlas.australian_source_contracts import (
    SourceFieldBinding,
)
from global_medicines_atlas.pbs_member_identity import (
    PbsXmlMemberBinding,
    build_pbs_xml_member_binding,
)
from global_medicines_atlas.pbs_silver import iter_pbs_silver_batches
from global_medicines_atlas.receipts import SourceReceipt

PATH = "release/SCH-fixture.xml"
SOURCE = "au-pbs-historical-xml"


def table(size: int = 2) -> pa.Table:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    return pa.Table.from_batches(
        list(
            historical.iter_pbs_historical_silver_batches(
                archive, XML, parent, binding, rows_per_batch=size
            )
        )
    )


def test_native_slots_parity_and_complete_lineage() -> None:
    result = table()
    rows = result.to_pylist()
    original = pa.Table.from_batches(
        list(iter_pbs_silver_batches(XML, _receipt(XML, "au-pbs")))
    ).to_pylist()
    native_columns = (
        "source_field_id",
        "source_ordinal",
        "source_sha256",
        "record_id",
        "path",
        "schema_path",
        "value",
        "state",
    )
    assert [[r[k] for k in native_columns] for r in rows] == [
        [r[k] for k in native_columns] for r in original
    ]
    metadata = result.schema.metadata
    binding = PbsXmlMemberBinding.model_validate_json(
        metadata[b"member_binding"]
    )
    assert binding.source.source_id == SOURCE
    assert metadata[b"source_id"] == SOURCE.encode()
    assert (
        metadata[b"source_receipt_sha256"]
        == binding.parent_receipt_sha256.encode()
    )
    assert metadata[b"conversion"] == b"none"
    assert metadata[b"qualification"] == b"candidate"
    assert all(r["source_id"] == SOURCE for r in rows)
    assert all(
        r["receipt_sha256"] == binding.parent_receipt_sha256 for r in rows
    )
    assert all(r["member_binding_sha256"] == binding.digest() for r in rows)
    assert all(
        r["archive_sha256"] == binding.archive_payload.sha256 for r in rows
    )
    assert all(r["member_path"] == PATH for r in rows)
    assert any(r["value"] == "001.2300" for r in rows)
    assert len([r for r in rows if r["value"] == "00123A"]) == 2
    output = BytesIO()
    pq.write_table(result, output)
    assert pq.read_table(BytesIO(output.getvalue())).equals(
        result, check_metadata=True
    )


@pytest.mark.parametrize("size", [1, 3, 4096])
def test_batch_boundaries_preserve_output(size: int) -> None:
    # ZIP fixture timestamps can differ; use one archive for both runs.
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)

    def run(n: int) -> pa.Table:
        return pa.Table.from_batches(
            list(
                historical.iter_pbs_historical_silver_batches(
                    archive, XML, parent, binding, rows_per_batch=n
                )
            )
        )

    assert run(size).equals(run(2), check_metadata=True)


@pytest.mark.parametrize(
    "case",
    [
        "archive",
        "member",
        "parent",
        "source",
        "binding",
        "missing_binding",
        "missing_parent",
        "missing_archive",
        "missing_member",
    ],
)
def test_no_output_before_all_lineage_validated(case: str) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    member = XML
    if case == "archive":
        archive += b"changed"
    elif case == "member":
        member += b"changed"
    elif case == "parent":
        parent = parent.model_copy(update={"receipt_id": "wrong"})
    elif case == "source":
        parent = _receipt(archive, "au-pbs")
    elif case == "binding":
        binding = binding.model_copy(update={"parent_receipt_sha256": "f" * 64})
    elif case == "missing_binding":
        binding = cast("PbsXmlMemberBinding", None)
    elif case == "missing_parent":
        parent = cast("SourceReceipt", None)
    elif case == "missing_archive":
        archive = cast("bytes", None)
    else:
        member = cast("bytes", None)
    iterator = historical.iter_pbs_historical_silver_batches(
        archive, member, parent, binding
    )
    with pytest.raises((ValueError, TypeError), match=r"match|source|required"):
        next(iterator)


def test_ordinary_source_contract_stays_strict() -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    with pytest.raises(ValueError, match="source"):
        list(iter_pbs_silver_batches(XML, parent))
    with pytest.raises(ValueError, match="source_id"):
        SourceFieldBinding(
            source_id=SOURCE, source_sha256="a" * 64, schema_era="fixture"
        )


@pytest.mark.parametrize("size", [0, 4097, True])
def test_invalid_batch_size_rejected(size: int) -> None:
    with pytest.raises(ValueError, match="batch size"):
        table(size)


def test_encoded_byte_budget_flush_and_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)

    def batches() -> list[pa.RecordBatch]:
        return list(
            historical.iter_pbs_historical_silver_batches(
                archive, XML, parent, binding, rows_per_batch=4096
            )
        )

    baseline = pa.Table.from_batches(batches())
    monkeypatch.setattr(historical, "MAX_BATCH_BYTES", 4000)
    assert len(batches()) > 1
    assert pa.Table.from_batches(batches()).equals(
        baseline, check_metadata=True
    )
    monkeypatch.setattr(historical, "MAX_BATCH_BYTES", 1)
    with pytest.raises(ValueError, match="byte limit"):
        batches()
