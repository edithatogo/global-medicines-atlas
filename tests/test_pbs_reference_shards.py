"""Transient partition contract for hosted PBS reference qualification."""

import json
from pathlib import Path

import pyarrow as pa
import pytest
from test_au_pbs_v3 import _zip  # ruff: ignore[import-private-name]
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name]
)
from test_pbs_historical_silver import PATH, SOURCE
from test_pbs_silver import XML

from global_medicines_atlas import pbs_reference_shards as shards
from global_medicines_atlas.pbs_historical_projections import (
    iter_pbs_historical_entity_batches,
)
from global_medicines_atlas.pbs_historical_qualification import (
    _denominator,  # ruff: ignore[import-private-name]  # pyright: ignore[reportPrivateUsage]
)
from global_medicines_atlas.pbs_member_identity import (
    build_pbs_xml_member_binding,
)
from global_medicines_atlas.pbs_reference_shards import (
    _read_index,  # ruff: ignore[import-private-name]  # pyright: ignore[reportPrivateUsage]
    assemble_reference_manifest,
    load_reference_entity_material,
    prepare_reference_entity_material,
    prepare_reference_index,
    prepare_reference_partition,
    prepare_reference_shards,
    qualify_reference_shard,
)
from global_medicines_atlas.pbs_references import (
    _reference_batches,  # ruff: ignore[import-private-name]  # pyright: ignore[reportPrivateUsage]
)


def inputs():
    archive = _zip([(PATH, XML)])
    parent = _receipt(archive, SOURCE)
    binding = build_pbs_xml_member_binding(archive, parent)
    denominator = _denominator(XML)

    def batches():
        return iter_pbs_historical_entity_batches(
            archive, XML, parent, binding, rows_per_batch=2
        )

    return binding, denominator, batches


def test_prepared_reference_shards_reassemble_full_ordered_projection(
    tmp_path: Path,
) -> None:
    binding, denominator, batches = inputs()
    manifest = prepare_reference_shards(
        batches(), binding, denominator, tmp_path / "prepared", shard_count=3
    )
    reports = [
        qualify_reference_shard(
            tmp_path / "prepared", shard_index=index, rows_per_batch=2
        )
        for index in range(3)
    ]
    assert manifest["evidence_truth"] is False
    assert manifest["publication_performed"] is False
    assert (
        sum(report["projections"]["references"]["rows"] for report in reports)
        == denominator["elements"]
    )
    assert (
        sum(
            report["projections"]["references"]["native_fields"]
            for report in reports
        )
        == denominator["native_fields"]
    )
    prepared = pa.concat_tables([
        pa.Table.from_batches(
            list(
                _reference_batches(
                    batches(),
                    batches(),
                    2,
                    start_row=window["start_row"],
                    stop_row=window["stop_row"],
                    expected_total_rows=denominator["elements"],
                )
            )
        )
        for window in (report["reference_window"] for report in reports)
    ])
    full = pa.Table.from_batches(
        list(
            _reference_batches(
                batches(),
                batches(),
                2,
                expected_total_rows=denominator["elements"],
            )
        )
    )
    assert prepared.equals(full, check_metadata=True)


def test_disaggregated_preparation_reassembles_existing_worker_contract(
    tmp_path: Path,
) -> None:
    binding, denominator, batches = inputs()
    directory = tmp_path / "dag"
    index_receipt = prepare_reference_index(
        batches(), binding, denominator, directory / "reference-index.json"
    )
    partition_receipts = [
        prepare_reference_partition(
            batches(),
            binding,
            denominator,
            directory / f"reference-{index:02d}.arrow",
            shard_index=index,
            shard_count=3,
        )
        for index in range(3)
    ]
    manifest = assemble_reference_manifest(
        directory,
        binding,
        denominator,
        index_receipt,
        partition_receipts,
    )
    reports = [
        qualify_reference_shard(directory, shard_index=index, rows_per_batch=2)
        for index in range(3)
    ]
    assert manifest["evidence_truth"] is False
    assert manifest["publication_performed"] is False
    assert (
        sum(report["projections"]["references"]["rows"] for report in reports)
        == denominator["elements"]
    )
    assert (
        sum(
            report["projections"]["references"]["native_fields"]
            for report in reports
        )
        == denominator["native_fields"]
    )


def test_entity_material_is_reusable_by_index_and_partition_nodes(
    tmp_path: Path,
) -> None:
    binding, denominator, batches = inputs()
    directory = tmp_path / "material"
    receipt = prepare_reference_entity_material(
        batches(), binding, denominator, directory / "entities.arrow"
    )
    index_batches, loaded_binding, loaded_denominator = (
        load_reference_entity_material(directory, receipt)
    )
    index_receipt = prepare_reference_index(
        iter(index_batches),
        loaded_binding,
        loaded_denominator,
        directory / "reference-index.json",
    )
    partition_receipts = []
    for index in range(2):
        partition_batches, loaded_binding, loaded_denominator = (
            load_reference_entity_material(directory, receipt)
        )
        partition_receipts.append(
            prepare_reference_partition(
                iter(partition_batches),
                loaded_binding,
                loaded_denominator,
                directory / f"reference-{index:02d}.arrow",
                shard_index=index,
                shard_count=2,
            )
        )
    manifest = assemble_reference_manifest(
        directory,
        binding,
        denominator,
        index_receipt,
        partition_receipts,
    )
    assert receipt["evidence_truth"] is False
    assert receipt["publication_performed"] is False
    assert manifest["denominator"] == denominator


@pytest.mark.parametrize(
    "mutation", ["digest", "path", "binding", "denominator", "purpose"]
)
def test_entity_material_loader_rejects_tampering(
    tmp_path: Path, mutation: str
) -> None:
    binding, denominator, batches = inputs()
    directory = tmp_path / mutation
    receipt = prepare_reference_entity_material(
        batches(), binding, denominator, directory / "entities.arrow"
    )
    if mutation == "digest":
        (directory / "entities.arrow").write_bytes(b"changed")
    elif mutation == "path":
        receipt["entity_material"]["path"] = "../entities.arrow"
    elif mutation == "binding":
        receipt["binding_sha256"] = "9" * 64
    elif mutation == "denominator":
        receipt["denominator"]["elements"] += 1
    else:
        receipt["purpose"] = "other"
    with pytest.raises((TypeError, ValueError), match=r"entity material"):
        load_reference_entity_material(directory, receipt)


@pytest.mark.parametrize(
    "mutation", ["index-digest", "partition-digest", "missing", "binding"]
)
def test_disaggregated_manifest_fails_closed_on_incomplete_or_mixed_nodes(
    tmp_path: Path, mutation: str
) -> None:
    binding, denominator, batches = inputs()
    directory = tmp_path / mutation
    index_receipt = prepare_reference_index(
        batches(), binding, denominator, directory / "reference-index.json"
    )
    partition_receipts = [
        prepare_reference_partition(
            batches(),
            binding,
            denominator,
            directory / f"reference-{index:02d}.arrow",
            shard_index=index,
            shard_count=2,
        )
        for index in range(2)
    ]
    if mutation == "index-digest":
        (directory / "reference-index.json").write_bytes(b"changed")
    elif mutation == "partition-digest":
        (directory / "reference-00.arrow").write_bytes(b"changed")
    elif mutation == "missing":
        partition_receipts.pop()
    else:
        partition_receipts[0]["binding_sha256"] = "9" * 64
    with pytest.raises(
        (TypeError, ValueError), match=r"binding|digest|coverage"
    ):
        assemble_reference_manifest(
            directory,
            binding,
            denominator,
            index_receipt,
            partition_receipts,
        )


def test_prepared_reference_shard_rejects_tampered_partition(
    tmp_path: Path,
) -> None:
    binding, denominator, batches = inputs()
    directory = tmp_path / "prepared"
    prepare_reference_shards(
        batches(), binding, denominator, directory, shard_count=2
    )
    with (directory / "reference-00.arrow").open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="digest"):
        qualify_reference_shard(directory, shard_index=0)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [None],
        [{"kind": 1, "value": "x", "resources": [], "targets": 0}],
        [{"kind": "k", "value": 1, "resources": [], "targets": 0}],
        [{"kind": "k", "value": "x", "resources": {}, "targets": 0}],
        [{"kind": "k", "value": "x", "resources": [], "targets": -1}],
        [{"kind": "k", "value": "x", "resources": [None], "targets": 1}],
        [
            {
                "kind": "k",
                "value": "x",
                "resources": [{"value": 1, "count": 1}],
                "targets": 1,
            }
        ],
        [
            {
                "kind": "k",
                "value": "x",
                "resources": [{"value": "r", "count": 0}],
                "targets": 1,
            }
        ],
    ],
)
def test_reference_index_rejects_invalid_typed_payloads(
    payload: object,
) -> None:
    with pytest.raises((TypeError, ValueError), match="index is invalid"):
        _read_index(json.dumps(payload).encode())


@pytest.mark.parametrize("count", [0, 11, 33, True])
def test_preparation_rejects_invalid_shard_count(
    tmp_path: Path, count: int
) -> None:
    binding, denominator, batches = inputs()
    with pytest.raises(ValueError, match="preparation"):
        prepare_reference_shards(
            batches(),
            binding,
            denominator,
            tmp_path / str(count),
            shard_count=count,
        )


@pytest.mark.parametrize("mutation", ["reorder", "drop", "duplicate"])
def test_preparation_rejects_entity_stream_order_or_coverage_drift(
    tmp_path: Path, mutation: str
) -> None:
    binding, denominator, batches = inputs()
    table = pa.Table.from_batches(list(batches())).combine_chunks()
    midpoint = table.num_rows // 2
    first = table.slice(0, midpoint).to_batches()[0]
    second = table.slice(midpoint).to_batches()[0]
    changed = {
        "reorder": [second, first],
        "drop": [first],
        "duplicate": [first, first],
    }[mutation]
    with pytest.raises(ValueError, match=r"denominator|stream digest"):
        prepare_reference_shards(
            iter(changed),
            binding,
            denominator,
            tmp_path / mutation,
            shard_count=2,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "not-object",
        "no-partitions",
        "bad-partition",
        "bad-index",
        "no-pins",
        "no-expected",
        "bad-expected",
    ],
)
def test_reference_worker_rejects_malformed_manifest_contracts(
    tmp_path: Path, mutation: str
) -> None:
    binding, denominator, batches = inputs()
    directory = tmp_path / mutation
    prepare_reference_shards(
        batches(), binding, denominator, directory, shard_count=2
    )
    path = directory / "reference-manifest.json"
    manifest = json.loads(path.read_text())
    if mutation == "not-object":
        changed: object = []
    else:
        changed = manifest
        if mutation == "no-partitions":
            manifest["partitions"] = None
        elif mutation == "bad-partition":
            manifest["partitions"][0] = None
        elif mutation == "bad-index":
            manifest["partitions"][0]["index"] = 1
        elif mutation == "no-pins":
            manifest["index"] = None
        elif mutation == "no-expected":
            manifest["partitions"][0]["expected_projection"] = None
        else:
            manifest["partitions"][0]["expected_projection"][
                "native_digest"
            ] = "9" * 64
    path.write_text(json.dumps(changed))
    with pytest.raises((TypeError, ValueError), match=r"manifest|digest"):
        qualify_reference_shard(directory, shard_index=0)


def test_reference_index_roundtrips_counted_resource() -> None:
    index = _read_index(
        json.dumps([
            {
                "kind": "amt",
                "value": "A",
                "resources": [{"value": "R", "count": 2}],
                "targets": 1,
            }
        ]).encode()
    )
    assert index["amt", "A"][0]["R"] == 2


def test_reference_worker_rejects_out_of_range_shard(tmp_path: Path) -> None:
    binding, denominator, batches = inputs()
    directory = tmp_path / "range"
    prepare_reference_shards(
        batches(), binding, denominator, directory, shard_count=2
    )
    with pytest.raises(TypeError, match="manifest"):
        qualify_reference_shard(directory, shard_index=2)


def test_preparation_rejects_schema_and_written_projection_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binding, denominator, batches = inputs()
    values = list(batches())
    altered = values[0].append_column(
        "unexpected", pa.array([1] * values[0].num_rows)
    )
    with pytest.raises(ValueError, match="schema"):
        prepare_reference_shards(
            iter([values[0], altered]),
            binding,
            {**denominator, "elements": values[0].num_rows * 2},
            tmp_path / "schema",
            shard_count=2,
        )

    original = shards._projection

    def changed(*args, **kwargs):
        report = original(*args, **kwargs)
        report["native_digest"] = "9" * 64
        return report

    monkeypatch.setattr(shards, "_projection", changed)
    with pytest.raises(ValueError, match="changed after preparation"):
        prepare_reference_shards(
            iter(values),
            binding,
            denominator,
            tmp_path / "projection",
            shard_count=2,
        )
