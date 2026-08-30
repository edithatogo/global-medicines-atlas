"""Historical reference/date candidates never detach from source evidence."""

from datetime import date
from io import BytesIO
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from test_au_pbs_v3 import (
    _production_xml,  # ruff: ignore[import-private-name]
    _xml,  # ruff: ignore[import-private-name]
    _zip,  # ruff: ignore[import-private-name]
)
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name]
)
from test_pbs_historical_silver import PATH, SOURCE
from test_pbs_silver import XML

from global_medicines_atlas import pbs_dates, pbs_references
from global_medicines_atlas import pbs_historical_annotations as historical
from global_medicines_atlas.pbs_historical_projections import (
    iter_pbs_historical_entity_batches,
)
from global_medicines_atlas.pbs_member_identity import (
    PbsXmlMemberBinding,
    build_pbs_xml_member_binding,
)

ROUTES = [
    historical.iter_pbs_historical_reference_batches,
    historical.iter_pbs_historical_date_batches,
]


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("payload", [XML, _production_xml()])
def test_full_lineage_native_parity_and_portability(
    route, payload: bytes
) -> None:
    archive = _zip([(PATH, payload)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    native = pa.Table.from_batches(
        list(
            iter_pbs_historical_entity_batches(
                archive, payload, parent, binding
            )
        )
    )
    result = pa.Table.from_batches(
        list(route(archive, payload, parent, binding))
    )
    assert result.select(native.column_names).to_pylist() == native.to_pylist()
    assert result.schema.metadata[b"member_binding"] == binding.canonical_json()
    assert result.schema.metadata[b"source_id"] == SOURCE.encode()
    assert (
        result.schema.metadata[b"source_receipt_sha256"]
        == parent.digest().encode()
    )
    assert result.schema.metadata[b"qualification"] == b"candidate"
    if route is historical.iter_pbs_historical_date_batches:
        assert all(row["date_value"] is None for row in result.to_pylist())
        assert result.schema.metadata[b"date_profile"] == b"not-selected"
    else:
        assert (
            result.schema.metadata[b"reference_resolution"] == b"not-performed"
        )
        if payload == XML:
            assert (
                sum(r["native_xml_id"] == "00123A" for r in result.to_pylist())
                == 2
            )
            assert any(
                r["native_text"] == "001.2300" and r["diagnostic"] == "unmapped"
                for r in result.to_pylist()
            )
    output = BytesIO()
    pq.write_table(result, output)
    assert pq.read_table(BytesIO(output.getvalue())).equals(
        result, check_metadata=True
    )
    for size in (1, 3, 4096):
        assert pa.Table.from_batches(
            list(route(archive, payload, parent, binding, rows_per_batch=size))
        ).equals(result, check_metadata=True)


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize(
    "case", ["missing", "binding", "archive", "member", "source"]
)
def test_reject_wrong_binding_before_output(route, case: str) -> None:
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


@pytest.mark.parametrize("drift_pass", [1, 2])
def test_cross_pass_identity_drift_rejected(
    monkeypatch: pytest.MonkeyPatch,
    drift_pass: int,
) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    original = historical.iter_pbs_historical_entity_batches
    calls = 0

    def drifting(*args, **kwargs):
        nonlocal calls
        calls += 1
        for index, batch in enumerate(original(*args, **kwargs)):
            if calls == drift_pass and index == 0:
                metadata = dict(batch.schema.metadata)
                metadata[b"member_binding_sha256"] = b"f" * 64
                yield batch.replace_schema_metadata(metadata)
            else:
                yield batch

    monkeypatch.setattr(
        historical, "iter_pbs_historical_entity_batches", drifting
    )
    with pytest.raises(ValueError, match="identity"):
        next(
            historical.iter_pbs_historical_reference_batches(
                archive, XML, parent, binding, rows_per_batch=1
            )
        )


def test_opt_in_date_candidate_stays_unqualified() -> None:
    payload = _production_xml()
    archive = _zip([(PATH, payload)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    result = pa.Table.from_batches(
        list(
            historical.iter_pbs_historical_date_batches(
                archive,
                payload,
                parent,
                binding,
                date_profile=pbs_dates.CANDIDATE_PROFILE,
            )
        )
    )
    assert any(r["date_value"] == date(2026, 4, 1) for r in result.to_pylist())
    assert (
        result.schema.metadata[b"source_date_era_qualification"]
        == b"not-established"
    )
    assert result.schema.metadata[b"temporal_status_inference"] == b"none"
    with pytest.raises(ValueError, match="profile"):
        next(
            historical.iter_pbs_historical_date_batches(
                archive, payload, parent, binding, date_profile="production"
            )
        )


@pytest.mark.parametrize(
    "bound", ["MAX_INDEX_ENTRIES", "MAX_INDEX_BYTES", "MAX_BATCH_BYTES"]
)
def test_reference_bounds_preserved(
    monkeypatch: pytest.MonkeyPatch, bound: str
) -> None:
    payload = _production_xml()
    archive = _zip([(PATH, payload)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    monkeypatch.setattr(pbs_references, bound, 1)
    with pytest.raises(ValueError, match="limit"):
        list(
            historical.iter_pbs_historical_reference_batches(
                archive, payload, parent, binding
            )
        )


@pytest.mark.parametrize(
    "route",
    [
        pbs_references.iter_pbs_reference_batches,
        pbs_dates.iter_pbs_date_batches,
    ],
)
def test_ordinary_guards_unchanged(route) -> None:
    with pytest.raises(ValueError, match="source"):
        next(route(XML, _receipt(XML, SOURCE)))


def test_duplicate_and_ambiguous_source_literals() -> None:
    payload = _xml()
    start = payload.index(b"<pbs:pharmaceutical-item")
    stop = payload.index(b"</pbs:pharmaceutical-item>") + len(
        b"</pbs:pharmaceutical-item>"
    )
    payload = (
        payload[:stop]
        + payload[start:stop].replace(
            b"http://snomed.info/id/123456", b"#123456"
        )
        + payload[stop:]
    )
    archive = _zip([(PATH, payload)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    result = pa.Table.from_batches(
        list(
            historical.iter_pbs_historical_reference_batches(
                archive, payload, parent, binding, rows_per_batch=1
            )
        )
    )
    rows = result.to_pylist()
    assert sum(r["diagnostic"] == "duplicate_source_literal" for r in rows) == 2
    assert sum(r["diagnostic"] == "ambiguous_source_targets" for r in rows) == 2
    assert sum(r["diagnostic"] == "unresolved" for r in rows) == 2


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("size", [0, 4097, True])
def test_batch_size_guards(route, size: int) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    with pytest.raises(ValueError, match="batch size"):
        next(route(archive, XML, parent, binding, rows_per_batch=size))
