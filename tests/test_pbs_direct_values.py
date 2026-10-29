"""Direct historical values preserve exact existing rows and Arrow metadata."""

import pyarrow as pa
import pytest
from test_au_pbs_v3 import (
    _zip,  # ruff: ignore[import-private-name] -- synthetic fixture
)
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name] -- synthetic receipt
)
from test_pbs_historical_silver import PATH, SOURCE
from test_pbs_native_values import price_payload
from test_pbs_value_package import inputs

from global_medicines_atlas import pbs_entities
from global_medicines_atlas.pbs_direct_values import (
    iter_direct_historical_value_batches,
)
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)
from global_medicines_atlas.pbs_native_values import (
    iter_pbs_historical_value_batches,
)
from global_medicines_atlas.pbs_value_package import (
    build_value_package,
    qualify_value_package_pair,
)


def test_direct_historical_producer_matches_complete_existing_table():
    args = inputs()
    expected = pa.Table.from_batches(
        list(iter_pbs_historical_value_batches(*args, rows_per_batch=1))
    )
    actual = pa.Table.from_batches(
        list(iter_direct_historical_value_batches(*args, rows_per_batch=3))
    )
    assert actual.equals(expected, check_metadata=True)


@pytest.mark.parametrize("size", [0, -1, 4097, True])
def test_direct_producer_rejects_invalid_batch_bounds(size):
    with pytest.raises(ValueError, match="batch size"):
        list(
            iter_direct_historical_value_batches(*inputs(), rows_per_batch=size)
        )


@pytest.mark.parametrize(
    "value", ["001.2300", "1.1234567891", "1e2", "", "   "]
)
def test_direct_complete_parity_includes_native_numeric_exceptions(value):
    xml = price_payload(value).replace(
        b"</pbs:pharmaceutical-item>",
        b'<unknown xml:id="repeat" a="">mixed<b/>tail</unknown></pbs:pharmaceutical-item>',
    )
    archive = _zip([(PATH, xml)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    args = archive, xml, parent, binding
    expected = pa.Table.from_batches(
        list(iter_pbs_historical_value_batches(*args, rows_per_batch=3))
    )
    actual = pa.Table.from_batches(
        list(iter_direct_historical_value_batches(*args, rows_per_batch=1))
    )
    assert actual.equals(expected, check_metadata=True)


def test_direct_lineage_failure_occurs_before_first_batch():
    archive, xml, parent, binding = inputs()
    with pytest.raises(ValueError, match="member"):
        next(
            iter_direct_historical_value_batches(
                archive, xml + b"changed", parent, binding
            )
        )


def test_direct_retains_element_field_bound(monkeypatch):
    monkeypatch.setattr(pbs_entities, "MAX_ELEMENT_FIELDS", 1)
    with pytest.raises(ValueError, match="field/byte limit"):
        list(iter_direct_historical_value_batches(*inputs()))


def test_direct_retains_entity_batch_byte_bound(monkeypatch):
    monkeypatch.setattr(pbs_entities, "MAX_BATCH_BYTES", 1)
    with pytest.raises(ValueError, match="batch byte limit"):
        list(iter_direct_historical_value_batches(*inputs()))


def test_direct_requires_original_parent_receipt():
    archive, xml, _, binding = inputs()
    with pytest.raises(TypeError, match="parent receipt"):
        next(iter_direct_historical_value_batches(archive, xml, None, binding))


def test_direct_pair_matches_existing_package_bytes_and_independent_restore(
    tmp_path,
):
    args = inputs()
    old = build_value_package(*args, tmp_path / "old")
    direct = qualify_value_package_pair(*args, tmp_path / "direct")
    assert direct["package"] == old
    assert (tmp_path / "old/values.parquet").read_bytes() == (
        tmp_path / "direct/first/values.parquet"
    ).read_bytes()
