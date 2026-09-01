"""Transient partition contract for hosted PBS reference qualification."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from test_au_pbs_v3 import _zip  # ruff: ignore[import-private-name]
from test_australian_source_contracts import (
    _receipt,  # ruff: ignore[import-private-name]
)
from test_pbs_historical_silver import PATH, SOURCE
from test_pbs_silver import XML

from global_medicines_atlas import pbs_reference_shards as shards
from global_medicines_atlas import pbs_references
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
    load_reference_entity_partition,
    prepare_reference_entity_material,
    prepare_reference_index,
    prepare_reference_partition,
    prepare_reference_partition_group,
    prepare_reference_shards,
    qualify_reference_shard,
    validate_reference_partition_group,
)
from global_medicines_atlas.pbs_references import (
    _index,  # ruff: ignore[import-private-name]  # pyright: ignore[reportPrivateUsage]
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


def _resign(receipt: dict[str, object]) -> None:
    contract = {
        key: value for key, value in receipt.items() if key != "contract_sha256"
    }
    receipt["contract_sha256"] = shards.hashlib.sha256(
        shards._encoded(contract)  # pyright: ignore[reportPrivateUsage]
    ).hexdigest()


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


def test_global_index_preparation_streams_once_with_deterministic_parity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binding, denominator, batches = inputs()
    baseline, _, rows = _index(batches())
    expected = shards._index_payload(baseline)  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setattr(
        shards,
        "TemporaryFile",
        lambda: pytest.fail("global index preparation must not create a spool"),
    )
    output = tmp_path / "reference-index.json"
    receipt = prepare_reference_index(
        iter(batches()), binding, denominator, output
    )
    checkpoint = receipt["preparation"]
    assert output.read_bytes() == expected
    assert checkpoint["row_count"] == rows == denominator["elements"]
    assert checkpoint["batch_count"] > 1
    assert checkpoint["entry_count"] >= 0
    assert 0 <= checkpoint["encoded_bytes"] <= pbs_references.MAX_INDEX_BYTES
    assert len(checkpoint["schema_sha256"]) == 64


def test_global_index_budget_failure_leaves_no_partial_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binding, denominator, batches = inputs()
    output = tmp_path / "reference-index.json"
    monkeypatch.setattr(pbs_references, "MAX_INDEX_ENTRIES", 0)

    def candidate(_batch: pa.RecordBatch) -> Iterator[dict[str, Any]]:
        yield {
            "contract_kind": "item_xml_id",
            "reference_value": "bounded-candidate",
            "reference_value_state": "value",
            "reference_resource": None,
            "reference_resource_state": "not_applicable",
        }

    monkeypatch.setattr(
        pbs_references,
        "_columnar_contracts",
        candidate,
    )
    with pytest.raises(ValueError, match="entry/byte limit"):
        prepare_reference_index(batches(), binding, denominator, output)
    assert not output.exists()


def test_global_index_rejects_denominator_tamper_before_artifact(
    tmp_path: Path,
) -> None:
    binding, denominator, batches = inputs()
    output = tmp_path / "reference-index.json"
    changed = {**denominator, "native_digest": "0" * 64}
    with pytest.raises(ValueError, match="denominator changed"):
        prepare_reference_index(batches(), binding, changed, output)
    assert not output.exists()


def test_global_index_rejects_entity_schema_drift(tmp_path: Path) -> None:
    binding, denominator, batches = inputs()
    values = list(batches())
    changed = values[1].append_column(
        "unexpected", pa.array([1] * values[1].num_rows)
    )
    with pytest.raises(ValueError, match="entity schema changed"):
        prepare_reference_index(
            iter([values[0], changed]),
            binding,
            denominator,
            tmp_path / "reference-index.json",
        )


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


def test_partition_group_scans_once_and_emits_only_assigned_contiguous_window(
    tmp_path: Path,
) -> None:
    binding, denominator, batches = inputs()
    scans = 0

    def counted():
        nonlocal scans
        scans += 1
        yield from batches()

    receipt = prepare_reference_partition_group(
        counted(),
        binding,
        denominator,
        tmp_path,
        group_index=1,
        group_count=2,
        shard_count=4,
    )
    loaded_binding, loaded_denominator, partitions = (
        validate_reference_partition_group(tmp_path, receipt)
    )
    assert scans == 1
    assert loaded_binding == binding
    assert loaded_denominator == denominator
    assert receipt["group"] == {
        "index": 1,
        "count": 2,
        "start_partition": 2,
        "stop_partition": 4,
    }
    assert [partition["index"] for partition in partitions] == [2, 3]
    assert sorted(path.name for path in tmp_path.glob("*.arrow")) == [
        "reference-02.arrow",
        "reference-03.arrow",
    ]
    assert (
        sum(
            partition["expected_projection"]["rows"] for partition in partitions
        )
        == partitions[-1]["stop_row"] - partitions[0]["start_row"]
    )


@pytest.mark.parametrize("mutation", ["drop", "reorder", "receipt", "bytes"])
def test_partition_group_rejects_drop_reorder_and_tamper(
    tmp_path: Path, mutation: str
) -> None:
    binding, denominator, batches = inputs()
    receipt = prepare_reference_partition_group(
        batches(),
        binding,
        denominator,
        tmp_path,
        group_index=0,
        group_count=2,
        shard_count=4,
    )
    if mutation == "drop":
        receipt["partitions"].pop()
        _resign(receipt)
    elif mutation == "reorder":
        receipt["partitions"].reverse()
        _resign(receipt)
    elif mutation == "receipt":
        receipt["group"]["stop_partition"] = 3
    else:
        with (tmp_path / "reference-00.arrow").open("ab") as stream:
            stream.write(b"tampered")
    with pytest.raises((TypeError, ValueError), match=r"group|digest"):
        validate_reference_partition_group(tmp_path, receipt)


@pytest.mark.parametrize(
    ("group_index", "group_count", "shard_count"),
    [(-1, 2, 4), (2, 2, 4), (0, 3, 4), (True, 2, 4), (0, True, 4)],
)
def test_partition_group_rejects_invalid_or_uneven_coverage(
    tmp_path: Path,
    group_index: int,
    group_count: int,
    shard_count: int,
) -> None:
    binding, denominator, batches = inputs()
    with pytest.raises(ValueError, match="group preparation"):
        prepare_reference_partition_group(
            batches(),
            binding,
            denominator,
            tmp_path,
            group_index=group_index,
            group_count=group_count,
            shard_count=shard_count,
        )


def test_partition_group_rejects_existing_output(tmp_path: Path) -> None:
    binding, denominator, batches = inputs()
    (tmp_path / "reference-00.arrow").write_bytes(b"occupied")
    with pytest.raises(ValueError, match="output already exists"):
        prepare_reference_partition_group(
            batches(),
            binding,
            denominator,
            tmp_path,
            group_index=0,
            group_count=2,
            shard_count=4,
        )


def test_partition_group_rejects_schema_and_writer_initialization_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binding, denominator, batches = inputs()
    values = list(batches())
    changed = values[1].append_column(
        "unexpected", pa.array([1] * values[1].num_rows)
    )
    with pytest.raises(ValueError, match="entity schema changed"):
        prepare_reference_partition_group(
            iter([values[0], changed]),
            binding,
            denominator,
            tmp_path / "schema",
            group_index=0,
            group_count=2,
            shard_count=4,
        )

    monkeypatch.setattr(pa.ipc, "new_stream", lambda *_: None)
    with pytest.raises(RuntimeError, match="was not initialized"):
        prepare_reference_partition_group(
            batches(),
            binding,
            denominator,
            tmp_path / "writer",
            group_index=0,
            group_count=2,
            shard_count=4,
        )


def test_partition_group_rejects_denominator_and_written_projection_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binding, denominator, batches = inputs()
    with pytest.raises(ValueError, match="denominator changed"):
        prepare_reference_partition_group(
            batches(),
            binding,
            {**denominator, "native_digest": "0" * 64},
            tmp_path / "denominator",
            group_index=0,
            group_count=2,
            shard_count=4,
        )

    original = shards._projection  # pyright: ignore[reportPrivateUsage]

    def changed(*args: Any, **kwargs: Any) -> dict[str, Any]:
        report = original(*args, **kwargs)
        report["native_digest"] = "9" * 64
        return report

    monkeypatch.setattr(shards, "_projection", changed)
    with pytest.raises(ValueError, match="changed after preparation"):
        prepare_reference_partition_group(
            batches(),
            binding,
            denominator,
            tmp_path / "projection",
            group_index=0,
            group_count=2,
            shard_count=4,
        )


@pytest.mark.parametrize("mutation", ["container", "binding", "partition"])
def test_partition_group_validation_rejects_structural_receipt_drift(
    tmp_path: Path, mutation: str
) -> None:
    binding, denominator, batches = inputs()
    receipt = prepare_reference_partition_group(
        batches(),
        binding,
        denominator,
        tmp_path,
        group_index=0,
        group_count=2,
        shard_count=4,
    )
    if mutation == "container":
        receipt["group"] = []
    elif mutation == "binding":
        receipt["binding_sha256"] = "0" * 64
    else:
        receipt["partitions"][0] = []
    _resign(receipt)
    with pytest.raises((TypeError, ValueError), match=r"receipt|binding"):
        validate_reference_partition_group(tmp_path, receipt)


def test_partition_group_validation_rejects_projection_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binding, denominator, batches = inputs()
    receipt = prepare_reference_partition_group(
        batches(),
        binding,
        denominator,
        tmp_path,
        group_index=0,
        group_count=2,
        shard_count=4,
    )
    original = shards._projection  # pyright: ignore[reportPrivateUsage]

    def changed(*args: Any, **kwargs: Any) -> dict[str, Any]:
        report = original(*args, **kwargs)
        report["native_digest"] = "8" * 64
        return report

    monkeypatch.setattr(shards, "_projection", changed)
    with pytest.raises(ValueError, match="projection changed"):
        validate_reference_partition_group(tmp_path, receipt)


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


def test_entity_material_writes_independently_bound_partitions_once(
    tmp_path: Path,
) -> None:
    binding, denominator, batches = inputs()
    directory = tmp_path / "fanout"
    receipt = prepare_reference_entity_material(
        batches(),
        binding,
        denominator,
        directory / "entities.arrow",
        shard_count=3,
    )
    loaded_rows = 0
    loaded_fields = 0
    for index in range(3):
        reader, loaded_binding, loaded_denominator, partition = (
            load_reference_entity_partition(directory, receipt, index)
        )
        assert loaded_binding == binding
        assert loaded_denominator == denominator
        assert list(reader)
        loaded_rows += partition["expected_projection"]["rows"]
        loaded_fields += partition["expected_projection"]["native_fields"]
    assert loaded_rows == denominator["elements"]
    assert loaded_fields == denominator["native_fields"]


@pytest.mark.parametrize("shard_count", [0, 33, True])
def test_entity_material_rejects_invalid_partition_count(
    tmp_path: Path, shard_count: int
) -> None:
    binding, denominator, batches = inputs()
    with pytest.raises(ValueError, match="entity material preparation"):
        prepare_reference_entity_material(
            batches(),
            binding,
            denominator,
            tmp_path / "entities.arrow",
            shard_count=shard_count,
        )


def test_preparation_nodes_reject_invalid_or_changed_denominators(
    tmp_path: Path,
) -> None:
    binding, denominator, batches = inputs()
    invalid = dict(denominator, elements=0)
    with pytest.raises(ValueError, match="index preparation"):
        prepare_reference_index(
            batches(), binding, invalid, tmp_path / "invalid-index.json"
        )
    with pytest.raises(ValueError, match="partition preparation"):
        prepare_reference_partition(
            batches(),
            binding,
            denominator,
            tmp_path / "invalid-partition.arrow",
            shard_index=2,
            shard_count=2,
        )
    changed = dict(denominator, native_fields=denominator["native_fields"] + 1)
    with pytest.raises(ValueError, match="material denominator changed"):
        prepare_reference_entity_material(
            batches(), binding, changed, tmp_path / "changed-material.arrow"
        )
    with pytest.raises(ValueError, match="index denominator changed"):
        prepare_reference_index(
            batches(), binding, changed, tmp_path / "changed-index.json"
        )


@pytest.mark.parametrize("mutation", ["contract", "index", "digest"])
def test_entity_partition_loader_rejects_tampering(
    tmp_path: Path, mutation: str
) -> None:
    binding, denominator, batches = inputs()
    receipt = prepare_reference_entity_material(
        batches(),
        binding,
        denominator,
        tmp_path / "entities.arrow",
        shard_count=2,
    )
    if mutation == "contract":
        receipt["contract_sha256"] = "0" * 64
    elif mutation == "index":
        receipt["partitions"][0]["index"] = 1
    else:
        (tmp_path / "reference-00.arrow").write_bytes(b"changed")
    with pytest.raises((TypeError, ValueError), match="entity"):
        load_reference_entity_partition(tmp_path, receipt, 0)


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
    ("mutation", "expected"),
    [
        ("material-type", "receipt is invalid"),
        ("denominator-type", "receipt is invalid"),
        ("binding", "binding changed"),
        ("denominator-keys", "denominator changed"),
        ("denominator-fields", "denominator changed"),
        ("denominator-digest", "denominator changed"),
    ],
)
def test_entity_material_loader_rejects_resigned_invalid_contracts(
    tmp_path: Path, mutation: str, expected: str
) -> None:
    binding, denominator, batches = inputs()
    receipt = prepare_reference_entity_material(
        batches(), binding, denominator, tmp_path / "entities.arrow"
    )
    if mutation == "material-type":
        receipt["entity_material"] = []
    elif mutation == "denominator-type":
        receipt["denominator"] = []
    elif mutation == "binding":
        receipt["binding_sha256"] = "0" * 64
    elif mutation == "denominator-keys":
        receipt["denominator"]["extra"] = 1
    elif mutation == "denominator-fields":
        receipt["denominator"]["elements"] = True
    else:
        receipt["denominator"]["native_digest"] = 1
    _resign(receipt)
    with pytest.raises((TypeError, ValueError), match=expected):
        load_reference_entity_material(tmp_path, receipt)


@pytest.mark.parametrize(
    ("mutation", "index", "expected"),
    [
        ("partitions-type", 0, "receipt is invalid"),
        ("denominator-type", 0, "receipt is invalid"),
        ("range", 3, "index changed"),
        ("record-type", 0, "receipt is invalid"),
        ("record-index", 0, "index changed"),
        ("binding", 0, "binding changed"),
    ],
)
def test_entity_partition_loader_rejects_resigned_invalid_contracts(
    tmp_path: Path, mutation: str, index: int, expected: str
) -> None:
    binding, denominator, batches = inputs()
    receipt = prepare_reference_entity_material(
        batches(),
        binding,
        denominator,
        tmp_path / "entities.arrow",
        shard_count=2,
    )
    if mutation == "partitions-type":
        receipt["partitions"] = {}
    elif mutation == "denominator-type":
        receipt["denominator"] = []
    elif mutation == "record-type":
        receipt["partitions"][0] = []
    elif mutation == "record-index":
        receipt["partitions"][0]["index"] = 1
    elif mutation == "binding":
        receipt["binding_sha256"] = "0" * 64
    _resign(receipt)
    with pytest.raises((TypeError, ValueError), match=expected):
        load_reference_entity_partition(tmp_path, receipt, index)


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


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("index-binding", "index receipt binding"),
        ("index-type", "index receipt is invalid"),
        ("partition-binding", "partition receipt binding"),
        ("partition-type", "partition receipt is invalid"),
        ("empty", "coverage changed"),
        ("projection-type", "partition receipt is invalid"),
        ("coverage", "coverage changed"),
        ("native-fields", "denominator changed"),
    ],
)
def test_manifest_rejects_each_invalid_node_contract(
    tmp_path: Path, mutation: str, expected: str
) -> None:
    binding, denominator, batches = inputs()
    index_receipt = prepare_reference_index(
        batches(), binding, denominator, tmp_path / "reference-index.json"
    )
    partitions = [
        prepare_reference_partition(
            batches(),
            binding,
            denominator,
            tmp_path / f"reference-{index:02d}.arrow",
            shard_index=index,
            shard_count=2,
        )
        for index in range(2)
    ]
    if mutation == "index-binding":
        index_receipt["purpose"] = "other"
    elif mutation == "index-type":
        index_receipt["index"] = []
    elif mutation == "partition-binding":
        partitions[0]["purpose"] = "other"
    elif mutation == "partition-type":
        partitions[0]["partition"] = []
    elif mutation == "empty":
        partitions.clear()
    elif mutation == "projection-type":
        partitions[0]["partition"]["expected_projection"] = []
    elif mutation == "coverage":
        partitions[0]["partition"]["count"] = 3
    else:
        partitions[0]["partition"]["expected_projection"]["native_fields"] += 1
    with pytest.raises((TypeError, ValueError), match=expected):
        assemble_reference_manifest(
            tmp_path, binding, denominator, index_receipt, partitions
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
