"""Synthetic read-side declaration checks never establish qualification."""

import json
from io import BytesIO
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_mbs_schema_profile import profiled
from test_mbs_silver import (
    _receipt,  # ruff: ignore[import-private-name] - synthetic fixture reuse
    _xml,  # ruff: ignore[import-private-name] - synthetic fixture reuse
)

import global_medicines_atlas.mbs_schema_profile_consumer as consumer
from global_medicines_atlas.mbs_schema_profile import DECLARATION_METADATA_KEY


def sample():
    payload = _xml("<ScheduleFee>001.00</ScheduleFee>", count=2)
    return profiled(payload)[0], _receipt(payload)


def read(batch, receipt, **kwargs):
    return consumer.read_mbs_schema_profile(
        batch,
        receipt,
        table="fees",
        expected_profile="synthetic-mbs-xml-v1",
        **kwargs,
    )


def replace(batch, raw):
    return batch.replace_schema_metadata({
        **batch.schema.metadata,
        DECLARATION_METADATA_KEY: raw,
    })


def test_reads_exact_declaration_without_changing_batch():
    batch, receipt = sample()
    before = batch.to_pylist(), batch.schema
    result = read(batch, receipt)
    assert result.status == "declared"
    assert result.b1_sha256 == receipt.digest()
    assert result.b2_sha256 == receipt.payload.sha256
    assert (batch.to_pylist(), batch.schema) == before
    with pytest.raises(ValueError, match="frozen"):
        result.status = "qualified"


@pytest.mark.parametrize(
    "raw",
    [
        b"x" * (40 * 1024 + 1),
        b'{"x":{}}',
        b'{"x":[]}',
        b'{"x":' + b"[" * 1000,
        b"[]",
    ],
)
def test_rejects_bounds_and_nesting_before_json_parser(raw):
    batch, receipt = sample()
    with (
        patch.object(consumer.json, "loads", side_effect=AssertionError),
        pytest.raises(ValueError, match="invalid MBS schema profile"),
    ):
        read(replace(batch, raw), receipt)


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b'{"x":"a","x":"b"}',
        b'{"x":NaN}',
        b"\xff",
        b'{"x":"secret',
        b'{"x":1} garbage',
    ],
)
def test_rejects_malformed_json_without_input_disclosure(raw):
    batch, receipt = sample()
    with pytest.raises(ValueError, match="invalid MBS schema profile") as error:
        read(replace(batch, raw), receipt)
    assert str(error.value) == "invalid MBS schema profile"
    assert error.value.__cause__ is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_revision", "different"),
        ("source_id", "au-pbs"),
        ("b1_sha256", "f" * 64),
        ("b2_sha256", "f" * 64),
        ("comparison_schema_profile", "different"),
        ("status", "qualified"),
        ("schema_version", True),
        ("extra", "secret"),
    ],
)
def test_rejects_substituted_declaration(field, value):
    batch, receipt = sample()
    document = json.loads(batch.schema.metadata[DECLARATION_METADATA_KEY])
    document[field] = value
    with pytest.raises(ValueError, match="invalid MBS schema profile"):
        read(replace(batch, json.dumps(document).encode()), receipt)


def test_empty_batch_checks_metadata_but_does_not_claim_completeness():
    batch, receipt = sample()
    result = read(batch.slice(0, 0), receipt)
    assert result.status == "declared"
    with pytest.raises(ValueError, match="invalid MBS schema profile"):
        read(batch.slice(0, 0), receipt.model_copy(update={"payload": {}}))


def test_rejects_wrong_row_lineage():
    batch, receipt = sample()
    index = batch.schema.get_field_index("source_sha256")
    changed = batch.set_column(
        index, batch.schema.field(index), pa.array(["f" * 64, "f" * 64])
    )
    with pytest.raises(ValueError, match="invalid MBS schema profile"):
        read(changed, receipt)


@pytest.mark.parametrize(
    "kind", ["missing", "future", "both", "count", "bytes"]
)
def test_rejects_invalid_metadata_before_declaration_parser(kind):
    batch, receipt = sample()
    metadata = dict(batch.schema.metadata)
    if kind == "missing":
        metadata.pop(DECLARATION_METADATA_KEY)
    elif kind == "future":
        metadata[b"gma.mbs.schema_profile.v2"] = metadata.pop(
            DECLARATION_METADATA_KEY
        )
    elif kind == "both":
        metadata[b"gma.mbs.schema_profile.v2"] = b"{}"
    elif kind == "count":
        metadata.update({str(i).encode(): b"" for i in range(65)})
    else:
        metadata[b"large"] = b"x" * consumer.MAX_METADATA_BYTES
    with (
        patch.object(consumer.json, "loads", side_effect=AssertionError),
        pytest.raises(ValueError, match="invalid MBS schema profile"),
    ):
        read(batch.replace_schema_metadata(metadata), receipt)


@pytest.mark.parametrize("key", [b"schema_era", b"qualification", b"dimension"])
def test_empty_batch_rejects_wrong_metadata(key):
    batch, receipt = sample()
    with pytest.raises(ValueError, match="invalid MBS schema profile"):
        read(
            batch.slice(0, 0).replace_schema_metadata({
                **batch.schema.metadata,
                key: b"wrong",
            }),
            receipt,
        )


def test_row_and_byte_bounds_precede_lineage_materialization():
    batch, receipt = sample()
    too_many = (
        pa.Table.from_batches([batch] * 2049).combine_chunks().to_batches()[0]
    )
    with pytest.raises(ValueError, match="invalid MBS schema profile"):
        read(too_many, receipt)
    with (
        patch.object(consumer, "MAX_BATCH_BYTES", 1),
        pytest.raises(ValueError, match="invalid MBS schema profile"),
    ):
        read(batch, receipt)


def test_wrong_type_and_column_schema():
    batch, receipt = sample()
    for invalid in (
        None,
        batch.remove_column(0),
        batch.replace_schema_metadata(None),
    ):
        with pytest.raises(ValueError, match="invalid MBS schema profile"):
            read(invalid, receipt)


def test_round_trip_and_escaped_profile():
    batch, receipt = sample()
    profile = 'native {[]} \\" profile'
    document = json.loads(batch.schema.metadata[DECLARATION_METADATA_KEY])
    document["comparison_schema_profile"] = profile
    batch = replace(batch, json.dumps(document).encode())
    stream = BytesIO()
    pq.write_table(pa.Table.from_batches([batch]), stream)
    restored = pq.read_table(BytesIO(stream.getvalue())).to_batches()[0]
    result = consumer.read_mbs_schema_profile(
        restored, receipt, table="fees", expected_profile=profile
    )
    assert result.comparison_schema_profile == profile
    assert restored.equals(batch, check_metadata=True)


@pytest.mark.parametrize("raw", [b"", b"}", b"{}{}", b"{}}"])
def test_flat_preflight_rejects_invalid_delimiters(raw):
    batch, receipt = sample()
    with pytest.raises(ValueError, match="invalid MBS schema profile"):
        read(replace(batch, raw), receipt)


def test_defensive_parser_shape_recheck():
    batch, receipt = sample()
    with (
        patch.object(consumer.json, "loads", return_value=[]),
        pytest.raises(ValueError, match="invalid MBS schema profile"),
    ):
        read(batch, receipt)


def test_wrong_caller_profile_and_table():
    batch, receipt = sample()
    for profile in (None, True, "different", " synthetic-mbs-xml-v1"):
        with pytest.raises(ValueError, match="invalid MBS schema profile"):
            consumer.read_mbs_schema_profile(
                batch, receipt, table="fees", expected_profile=profile
            )
    with pytest.raises(ValueError, match="invalid MBS schema profile"):
        consumer.read_mbs_schema_profile(
            batch,
            receipt,
            table="services",
            expected_profile="synthetic-mbs-xml-v1",
        )
