"""Historical structural candidates preserve every archive/member binding."""

from io import BytesIO
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_au_pbs_v3 import _zip  # ruff: ignore[import-private-name]
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name]
)
from test_pbs_historical_silver import PATH, SOURCE
from test_pbs_silver import XML

from global_medicines_atlas import pbs_entities
from global_medicines_atlas.pbs_domain import iter_pbs_domain_batches
from global_medicines_atlas.pbs_entities import iter_pbs_entity_batches
from global_medicines_atlas.pbs_historical_projections import (
    iter_pbs_historical_domain_batches,
    iter_pbs_historical_entity_batches,
)
from global_medicines_atlas.pbs_historical_silver import (
    iter_pbs_historical_silver_batches,
)
from global_medicines_atlas.pbs_member_identity import (
    PbsXmlMemberBinding,
    build_pbs_xml_member_binding,
)

ROUTES = [
    iter_pbs_historical_domain_batches,
    iter_pbs_historical_entity_batches,
]


@pytest.mark.parametrize("route", ROUTES)
def test_lossless_lineage_and_parquet(route) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    result = pa.Table.from_batches(list(route(archive, XML, parent, binding)))
    metadata = result.schema.metadata
    assert metadata[b"member_binding"] == binding.canonical_json()
    assert metadata[b"source_id"] == SOURCE.encode()
    assert metadata[b"source_receipt_sha256"] == parent.digest().encode()
    assert metadata[b"qualification"] == b"candidate"
    assert metadata[b"conversion"] == b"none"
    native = pa.Table.from_batches(
        list(iter_pbs_historical_silver_batches(archive, XML, parent, binding))
    )
    rows = result.to_pylist()
    for row in rows:
        assert row["source_id"] == SOURCE
        assert row["receipt_sha256"] == parent.digest()
        assert row["archive_sha256"] == binding.archive_payload.sha256
        assert row["source_sha256"] == binding.member_payload.sha256
        assert row["member_binding_sha256"] == binding.digest()
        assert row["member_path"] == PATH
    if route is iter_pbs_historical_entity_batches:
        assert len({r["entity_id"] for r in rows}) == len(rows)
        assert [
            r["native_xml_id"] for r in rows if r["xml_id_state"] == "value"
        ] == ["00123A", "00123A"]
        assert any(r["native_text"] == " Before " for r in rows)
        assert any(r["native_tail"] == " after " for r in rows)
        assert any(r["text_state"] == "null" for r in rows)
        rows = [field for row in rows for field in row["native_fields"]]
    assert [
        {k: r[k] for k in native.column_names} for r in rows
    ] == native.to_pylist()
    assert any(
        r["value"] == "001.2300" and r["mapping_target"] == "unmapped"
        for r in rows
    )
    output = BytesIO()
    pq.write_table(result, output)
    assert pq.read_table(BytesIO(output.getvalue())).equals(
        result, check_metadata=True
    )
    for size in (1, 3, 4096):
        assert pa.Table.from_batches(
            list(route(archive, XML, parent, binding, rows_per_batch=size))
        ).equals(result, check_metadata=True)


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize(
    "case", ["missing", "binding", "archive", "member", "source"]
)
def test_reject_before_first_output(route, case: str) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    member = XML
    if case == "missing":
        binding = cast("PbsXmlMemberBinding", None)
    elif case == "binding":
        binding = binding.model_copy(update={"parent_receipt_sha256": "f" * 64})
    elif case == "archive":
        archive += b"changed"
    elif case == "member":
        member += b"changed"
    else:
        parent = _receipt(archive, "au-pbs")
    with pytest.raises((ValueError, TypeError), match=r"required|match|source"):
        next(route(archive, member, parent, binding))


@pytest.mark.parametrize(
    "route", [iter_pbs_domain_batches, iter_pbs_entity_batches]
)
def test_ordinary_route_rejects_historical_receipt(route) -> None:
    with pytest.raises(ValueError, match="source"):
        next(route(XML, _receipt(XML, SOURCE)))


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("size", [0, 4097, True])
def test_batch_size_guards(route, size: int) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    with pytest.raises(ValueError, match="batch size"):
        next(route(archive, XML, parent, binding, rows_per_batch=size))


@pytest.mark.parametrize(
    "bound", ["MAX_ELEMENT_FIELDS", "MAX_ELEMENT_BYTES", "MAX_BATCH_BYTES"]
)
def test_shared_entity_limits_remain_enforced(
    monkeypatch: pytest.MonkeyPatch, bound: str
) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    monkeypatch.setattr(pbs_entities, bound, 1)
    with pytest.raises(ValueError, match="limit"):
        list(iter_pbs_historical_entity_batches(archive, XML, parent, binding))
