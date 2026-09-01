"""Synthetic qualification accounts for all historical native evidence."""

import json

import pyarrow as pa
import pytest
from test_au_pbs_v3 import _zip  # ruff: ignore[import-private-name]
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name]
)
from test_pbs_historical_silver import PATH, SOURCE
from test_pbs_silver import XML

from global_medicines_atlas import pbs_historical_qualification as qualifier
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)
from global_medicines_atlas.pbs_xml_slots import PbsXmlSlot


def test_all_projections_have_exact_denominators_and_parquet_parity() -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    report = qualifier.qualify_pbs_historical_projections(
        archive, XML, parent, binding
    )
    assert report["qualification"] == "structural_storage_candidate_only"
    assert report["source_id"] == SOURCE
    assert report["member_binding_sha256"] == binding.digest()
    assert report["parent_receipt_sha256"] == parent.digest()
    assert report["archive_sha256"] == binding.archive_payload.sha256
    assert report["member_sha256"] == binding.member_payload.sha256
    assert report["date_profile"] == "not-selected"
    assert not report["domain_semantics_qualified"]
    assert not report["publication_performed"]
    assert len(report["projections"]) == 5
    for name, projection in report["projections"].items():
        assert projection["native_fields"] == report["native_fields"]
        assert projection["native_digest"] == report["native_digest"]
        assert projection["rows"] == (
            report["native_fields"]
            if name in {"native", "domain"}
            else report["elements"]
        )
        assert projection["parquet_roundtrip_verified"]
    assert "001.2300" not in json.dumps(report)
    assert " Before " not in json.dumps(report)
    assert (
        qualifier.qualify_pbs_historical_projections(
            archive, XML, parent, binding, rows_per_batch=1
        )
        == report
    )


@pytest.mark.parametrize(
    "projection", ["native", "domain", "entities", "references", "dates"]
)
def test_one_projection_shard_preserves_full_denominator(
    projection: str,
) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    report = qualifier.qualify_pbs_historical_projections(
        archive, XML, parent, binding, projection=projection
    )
    assert report["projection_shard"] == projection
    assert tuple(report["projections"]) == (projection,)
    result = report["projections"][projection]
    assert result["native_fields"] == report["native_fields"]
    assert result["native_digest"] == report["native_digest"]
    assert result["parquet_roundtrip_verified"] is True


def test_unknown_projection_shard_fails_closed() -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    with pytest.raises(ValueError, match="projection shard"):
        qualifier.qualify_pbs_historical_projections(
            archive, XML, parent, binding, projection="unknown"
        )


def test_reference_windows_are_gap_free_and_preserve_ordered_counts() -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    reports = [
        qualifier.qualify_pbs_historical_projections(
            archive,
            XML,
            parent,
            binding,
            projection="references",
            reference_shard=(index, 2),
        )
        for index in range(2)
    ]
    assert [report["reference_window"] for report in reports] == [
        {
            "index": 0,
            "count": 2,
            "start_row": 0,
            "stop_row": 5,
            "total_rows": 10,
        },
        {
            "index": 1,
            "count": 2,
            "start_row": 5,
            "stop_row": 10,
            "total_rows": 10,
        },
    ]
    projections = [report["projections"]["references"] for report in reports]
    assert sum(item["rows"] for item in projections) == 10
    assert (
        sum(item["native_fields"] for item in projections)
        == reports[0]["native_fields"]
    )
    assert all(
        item["native_digest_scope"] == "ordered-window" for item in projections
    )


@pytest.mark.parametrize("shard", [(-1, 2), (2, 2), (0, 0), (0, 65)])
def test_invalid_reference_window_fails_closed(shard: tuple[int, int]) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    with pytest.raises(ValueError, match="reference shard"):
        qualifier.qualify_pbs_historical_projections(
            archive,
            XML,
            parent,
            binding,
            projection="references",
            reference_shard=shard,
        )


def test_progress_is_aggregate_and_does_not_change_qualification() -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    events = []
    report = qualifier.qualify_pbs_historical_projections(
        archive,
        XML,
        parent,
        binding,
        rows_per_batch=1,
        progress=lambda *event: events.append(event),
    )
    assert events[0] == ("binding-validation", 0, 0)
    assert events[1] == ("denominator", 0, 0)
    for name, projection in report["projections"].items():
        phase = [event for event in events if event[0] == name]
        assert phase[0] == (name, 0, 0)
        assert phase[-1][1:] == (projection["rows"], projection["rows"])
    assert report == qualifier.qualify_pbs_historical_projections(
        archive, XML, parent, binding
    )


def test_entity_projection_is_built_once_and_replayed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    original = qualifier.iter_pbs_historical_entity_batches
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        yield from original(*args, **kwargs)

    monkeypatch.setattr(
        qualifier, "iter_pbs_historical_entity_batches", counted
    )
    report = qualifier.qualify_pbs_historical_projections(
        archive, XML, parent, binding, rows_per_batch=1
    )
    assert calls == 1
    assert tuple(report["projections"]) == (
        "native",
        "domain",
        "entities",
        "references",
        "dates",
    )


def test_denominator_reports_only_bounded_intervals(monkeypatch):
    slot = PbsXmlSlot("/item/1", "/item/1/text", "/item/text", "secret")
    monkeypatch.setattr(
        qualifier, "iter_pbs_xml_slots", lambda _payload: iter([slot] * 65537)
    )
    events = []
    report = qualifier._denominator(
        b"synthetic", lambda *event: events.append(event)
    )
    assert events == [("denominator", 0, 65536), ("denominator", 0, 65537)]
    assert report["native_fields"] == 65537
    assert "secret" not in json.dumps(events)


@pytest.mark.parametrize("case", ["archive", "member", "binding"])
def test_wrong_identity_cannot_get_report(case: str) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    member = XML
    if case == "archive":
        archive += b"wrong"
    elif case == "member":
        member += b"wrong"
    else:
        binding = binding.model_copy(update={"parent_receipt_sha256": "f" * 64})
    with pytest.raises(ValueError, match="match"):
        qualifier.qualify_pbs_historical_projections(
            archive, member, parent, binding
        )


@pytest.mark.parametrize("case", ["drop", "value", "lineage", "metadata"])
def test_corrupted_projection_rejected(
    monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    original = qualifier.iter_pbs_historical_domain_batches

    def corrupt(*args, **kwargs):
        for batch in original(*args, **kwargs):
            rows = batch.to_pylist()
            if case == "drop":
                rows = rows[:-1]
            elif case == "value":
                rows[0]["value"] = "changed"
            elif case == "lineage":
                rows[0]["archive_sha256"] = "f" * 64
            altered = pa.RecordBatch.from_pylist(rows, schema=batch.schema)
            if case == "metadata":
                yield altered.replace_schema_metadata({})
            else:
                yield altered

    monkeypatch.setattr(
        qualifier, "iter_pbs_historical_domain_batches", corrupt
    )
    with pytest.raises(
        ValueError, match=r"lineage|denominator|digest|metadata"
    ):
        qualifier.qualify_pbs_historical_projections(
            archive, XML, parent, binding
        )


def test_parquet_metadata_loss_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    original = qualifier.pq.read_table

    def changed(*args, **kwargs):
        return original(*args, **kwargs).replace_schema_metadata({})

    monkeypatch.setattr(qualifier.pq, "read_table", changed)
    with pytest.raises(ValueError, match="Parquet"):
        qualifier.qualify_pbs_historical_projections(
            archive, XML, parent, binding
        )


@pytest.mark.parametrize("case", ["entity", "parent", "nested", "empty"])
def test_entity_lineage_corruption_rejected(
    monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    original = qualifier.iter_pbs_historical_entity_batches

    def corrupt(*args, **kwargs):
        for batch in original(*args, **kwargs):
            rows = batch.to_pylist()
            if case == "entity":
                rows[0]["entity_id"] = "wrong"
            elif case == "parent":
                rows[0]["parent_entity_id"] = "wrong"
            elif case == "nested":
                rows[0]["native_fields"][0]["archive_sha256"] = "f" * 64
            else:
                rows[0]["native_fields"] = []
            yield pa.RecordBatch.from_pylist(rows, schema=batch.schema)

    monkeypatch.setattr(
        qualifier, "iter_pbs_historical_entity_batches", corrupt
    )
    with pytest.raises(ValueError, match=r"lineage|denominator"):
        qualifier.qualify_pbs_historical_projections(
            archive, XML, parent, binding
        )
