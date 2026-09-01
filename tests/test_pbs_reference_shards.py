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
