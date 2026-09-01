"""Transient same-run inputs for bounded historical PBS reference workers."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path
from tempfile import TemporaryFile
from typing import Any, cast

import pyarrow as pa

from .pbs_historical_qualification import (
    _account_nested_batch,  # pyright: ignore[reportPrivateUsage]
    _projection,  # pyright: ignore[reportPrivateUsage]
)
from .pbs_member_identity import PbsXmlMemberBinding
from .pbs_references import (
    ReferenceIndex,
    _annotated_batches,  # pyright: ignore[reportPrivateUsage]
    _index,  # pyright: ignore[reportPrivateUsage]
    _schema,  # pyright: ignore[reportPrivateUsage]
)

MAX_REFERENCE_SHARDS = 32


def _encoded(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _digest(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
    }


def _index_payload(index: ReferenceIndex) -> bytes:
    rows: list[dict[str, Any]] = []
    for (kind, value), (counts, targets) in sorted(
        index.items(), key=lambda item: (item[0][0], item[0][1])
    ):
        rows.append({
            "kind": kind,
            "value": value,
            "resources": sorted(
                (
                    {"value": resource, "count": count}
                    for resource, count in counts.items()
                ),
                key=lambda item: (
                    item["value"] is not None,
                    item["value"] or "",
                ),
            ),
            "targets": targets,
        })
    return _encoded(rows)


def _lineage(binding: PbsXmlMemberBinding) -> dict[str, str]:
    return {
        "source_id": binding.source.source_id,
        "source_sha256": binding.member_payload.sha256,
        "schema_era": binding.source.catalog_version,
        "receipt_sha256": binding.parent_receipt_sha256,
        "member_binding_sha256": binding.digest(),
        "archive_sha256": binding.archive_payload.sha256,
        "member_path": binding.member_path,
    }


def _counter() -> dict[str, int]:
    return dict.fromkeys(
        (
            "rows",
            "native_fields",
            "unmapped_rows",
            "duplicate_literal_rows",
            "ambiguous_reference_rows",
            "unresolved_reference_rows",
            "date_unselected_rows",
        ),
        0,
    )


def prepare_reference_entity_material(  # ruff: ignore[too-many-branches,too-many-locals]
    batches: Iterator[pa.RecordBatch],
    binding: PbsXmlMemberBinding,
    denominator: dict[str, Any],
    output: Path,
    *,
    shard_count: int | None = None,
) -> dict[str, Any]:
    """Materialize the verified entity stream once for downstream DAG nodes."""
    total = denominator.get("elements")
    if (
        type(total) is not int
        or total < 1
        or (
            shard_count is not None
            and (
                type(shard_count) is not int
                or not 1 <= shard_count <= min(MAX_REFERENCE_SHARDS, total)
            )
        )
    ):
        raise ValueError("invalid PBS reference entity material preparation")
    output.parent.mkdir(parents=True, exist_ok=True)
    counts = _counter()
    digest = hashlib.sha256()
    schema: pa.Schema | None = None
    writer: pa.RecordBatchStreamWriter | None = None
    partition_paths = (
        [
            output.parent / f"reference-{index:02d}.arrow"
            for index in range(shard_count)
        ]
        if shard_count is not None
        else []
    )
    partition_writers: list[pa.RecordBatchStreamWriter | None] = [
        None for _ in partition_paths
    ]
    partition_counts = [_counter() for _ in partition_paths]
    partition_digests = [hashlib.sha256() for _ in partition_paths]
    observed = 0
    try:
        for batch in batches:
            if schema is None:
                schema = batch.schema
                writer = pa.ipc.new_stream(str(output), schema)
                partition_writers = [
                    pa.ipc.new_stream(str(path), schema)
                    for path in partition_paths
                ]
            elif not batch.schema.equals(schema, check_metadata=True):
                raise ValueError("PBS reference entity material schema changed")
            if writer is None:
                raise RuntimeError(
                    "PBS reference entity material was not initialized"
                )
            writer.write_batch(batch)  # pyright: ignore[reportUnknownMemberType]
            _account_nested_batch(batch, _lineage(binding), counts, digest)
            batch_start, batch_stop = observed, observed + batch.num_rows
            for index, partition_writer in enumerate(partition_writers):
                start = total * index // len(partition_writers)
                stop = total * (index + 1) // len(partition_writers)
                selected_start = max(start, batch_start)
                selected_stop = min(stop, batch_stop)
                if selected_start < selected_stop:
                    if partition_writer is None:
                        raise RuntimeError(
                            "PBS reference entity partition was not initialized"
                        )
                    selected = batch.slice(
                        selected_start - batch_start,
                        selected_stop - selected_start,
                    )
                    partition_writer.write_batch(selected)  # pyright: ignore[reportUnknownMemberType]
                    _account_nested_batch(
                        selected,
                        _lineage(binding),
                        partition_counts[index],
                        partition_digests[index],
                    )
            observed = batch_stop
    finally:
        if writer is not None:
            writer.close()
        for partition_writer in partition_writers:
            if partition_writer is not None:
                partition_writer.close()
    expected_denominator = {
        key: denominator[key]
        for key in ("native_fields", "elements", "native_digest")
    }
    if (
        schema is None
        or counts["rows"] != total
        or counts["native_fields"] != expected_denominator["native_fields"]
        or digest.hexdigest() != expected_denominator["native_digest"]
    ):
        raise ValueError("PBS reference entity material denominator changed")
    contract: dict[str, Any] = {
        "schema_version": 1,
        "purpose": "transient-reference-entity-material",
        "binding": binding.model_dump(mode="json"),
        "binding_sha256": binding.digest(),
        "denominator": expected_denominator,
        "entity_material": {"path": output.name, **_digest(output)},
        "partitions": [
            {
                "index": index,
                "count": len(partition_paths),
                "start_row": total * index // len(partition_paths),
                "stop_row": total * (index + 1) // len(partition_paths),
                "path": path.name,
                **_digest(path),
                "expected_projection": {
                    "rows": partition_counts[index]["rows"],
                    "native_fields": partition_counts[index]["native_fields"],
                    "native_digest": partition_digests[index].hexdigest(),
                },
            }
            for index, path in enumerate(partition_paths)
        ],
        "publication_performed": False,
        "evidence_truth": False,
    }
    return {
        **contract,
        "contract_sha256": hashlib.sha256(_encoded(contract)).hexdigest(),
    }


def load_reference_entity_material(
    directory: Path, receipt: dict[str, Any]
) -> tuple[pa.RecordBatchReader, PbsXmlMemberBinding, dict[str, Any]]:
    """Validate one material receipt and open its content-bound Arrow stream."""
    contract = {
        key: value for key, value in receipt.items() if key != "contract_sha256"
    }
    if (
        receipt.get("purpose") != "transient-reference-entity-material"
        or receipt.get("schema_version") != 1
        or receipt.get("publication_performed") is not False
        or receipt.get("evidence_truth") is not False
        or receipt.get("contract_sha256")
        != hashlib.sha256(_encoded(contract)).hexdigest()
    ):
        raise ValueError("PBS reference entity material receipt changed")
    material = receipt.get("entity_material")
    denominator = receipt.get("denominator")
    if not isinstance(material, dict) or not isinstance(denominator, dict):
        raise TypeError("PBS reference entity material receipt is invalid")
    material = cast("dict[str, Any]", material)
    denominator = cast("dict[str, Any]", denominator)
    binding = PbsXmlMemberBinding.model_validate(receipt.get("binding"))
    if binding.digest() != receipt.get("binding_sha256"):
        raise ValueError("PBS reference entity material binding changed")
    path = directory / str(material.get("path"))
    if path.parent != directory or _digest(path) != {
        key: material.get(key) for key in ("sha256", "byte_count")
    }:
        raise ValueError("PBS reference entity material digest changed")
    if (
        set(denominator) != {"native_fields", "elements", "native_digest"}
        or any(
            type(denominator.get(key)) is not int
            for key in ("native_fields", "elements")
        )
        or not isinstance(denominator.get("native_digest"), str)
    ):
        raise ValueError("PBS reference entity material denominator changed")
    return (
        pa.ipc.open_stream(pa.memory_map(str(path), "r")),
        binding,
        denominator,
    )


def load_reference_entity_partition(
    directory: Path, receipt: dict[str, Any], shard_index: int
) -> tuple[
    pa.RecordBatchReader,
    PbsXmlMemberBinding,
    dict[str, Any],
    dict[str, Any],
]:
    """Validate and open one independently bound prepared entity partition."""
    contract = {
        key: value for key, value in receipt.items() if key != "contract_sha256"
    }
    if (
        receipt.get("contract_sha256")
        != hashlib.sha256(_encoded(contract)).hexdigest()
    ):
        raise ValueError("PBS reference entity material receipt changed")
    partitions = receipt.get("partitions")
    denominator = receipt.get("denominator")
    if not isinstance(partitions, list) or not isinstance(denominator, dict):
        raise TypeError("PBS reference entity partition receipt is invalid")
    partitions = cast("list[object]", partitions)
    if not 0 <= shard_index < len(partitions):
        raise ValueError("PBS reference entity partition index changed")
    partition = partitions[shard_index]
    if not isinstance(partition, dict):
        raise TypeError("PBS reference entity partition receipt is invalid")
    partition = cast("dict[str, Any]", partition)
    if partition.get("index") != shard_index:
        raise ValueError("PBS reference entity partition index changed")
    binding = PbsXmlMemberBinding.model_validate(receipt.get("binding"))
    if binding.digest() != receipt.get("binding_sha256"):
        raise ValueError("PBS reference entity material binding changed")
    path = directory / str(partition.get("path"))
    if path.parent != directory or _digest(path) != {
        key: partition.get(key) for key in ("sha256", "byte_count")
    }:
        raise ValueError("PBS reference entity partition digest changed")
    return (
        pa.ipc.open_stream(pa.memory_map(str(path), "r")),
        binding,
        cast("dict[str, Any]", denominator),
        partition,
    )


def prepare_reference_index(
    batches: Iterator[pa.RecordBatch],
    binding: PbsXmlMemberBinding,
    denominator: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    """Build only the global reference index as one retryable DAG node."""
    total = denominator.get("elements")
    if type(total) is not int or total < 1:
        raise ValueError("invalid PBS reference index preparation")
    output.parent.mkdir(parents=True, exist_ok=True)
    counts = _counter()
    digest = hashlib.sha256()
    schema: pa.Schema | None = None
    with TemporaryFile() as spool:
        writer: pa.RecordBatchStreamWriter | None = None
        try:
            for batch in batches:
                if schema is None:
                    schema = batch.schema
                    writer = pa.ipc.new_stream(spool, schema)
                elif not batch.schema.equals(schema, check_metadata=True):
                    raise ValueError(
                        "PBS reference index entity schema changed"
                    )
                if writer is None:
                    raise RuntimeError(
                        "PBS reference index spool was not initialized"
                    )
                writer.write_batch(batch)  # pyright: ignore[reportUnknownMemberType]
                _account_nested_batch(batch, _lineage(binding), counts, digest)
        finally:
            if writer is not None:
                writer.close()
        if (
            schema is None
            or counts["rows"] != total
            or counts["native_fields"] != denominator.get("native_fields")
            or digest.hexdigest() != denominator.get("native_digest")
        ):
            raise ValueError("PBS reference index denominator changed")
        spool.seek(0)
        index, identity, indexed_rows = _index(iter(pa.ipc.open_stream(spool)))
        if (
            identity is None
            or not identity.equals(schema, check_metadata=True)
            or indexed_rows != total
        ):
            raise ValueError("PBS reference index denominator changed")
    output.write_bytes(_index_payload(index))
    return {
        "schema_version": 1,
        "purpose": "transient-reference-global-index",
        "binding_sha256": binding.digest(),
        "binding": binding.model_dump(mode="json"),
        "denominator": {
            key: denominator[key]
            for key in ("native_fields", "elements", "native_digest")
        },
        "index": {"path": output.name, **_digest(output)},
        "publication_performed": False,
        "evidence_truth": False,
    }


def prepare_reference_partition(  # ruff: ignore[too-many-locals]
    batches: Iterator[pa.RecordBatch],
    binding: PbsXmlMemberBinding,
    denominator: dict[str, Any],
    output: Path,
    *,
    shard_index: int,
    shard_count: int,
) -> dict[str, Any]:
    """Build one independently retryable, content-bound entity partition."""
    total = denominator.get("elements")
    if (
        type(total) is not int  # ruff: ignore[too-many-boolean-expressions]
        or total < 1
        or type(shard_count) is not int
        or not 1 <= shard_count <= MAX_REFERENCE_SHARDS
        or shard_count > total
        or type(shard_index) is not int
        or not 0 <= shard_index < shard_count
    ):
        raise ValueError("invalid PBS reference partition preparation")
    output.parent.mkdir(parents=True, exist_ok=True)
    start = total * shard_index // shard_count
    stop = total * (shard_index + 1) // shard_count
    complete_counts, selected_counts = _counter(), _counter()
    complete_digest, selected_digest = hashlib.sha256(), hashlib.sha256()
    lineage = _lineage(binding)
    observed = 0
    schema: pa.Schema | None = None
    writer: pa.RecordBatchStreamWriter | None = None
    try:
        for batch in batches:
            if schema is None:
                schema = batch.schema
                writer = pa.ipc.new_stream(str(output), schema)
            elif not batch.schema.equals(schema, check_metadata=True):
                raise ValueError(
                    "PBS reference partition entity schema changed"
                )
            _account_nested_batch(
                batch, lineage, complete_counts, complete_digest
            )
            batch_start, batch_stop = observed, observed + batch.num_rows
            selected_start, selected_stop = (
                max(start, batch_start),
                min(stop, batch_stop),
            )
            if selected_start < selected_stop:
                if writer is None:
                    raise RuntimeError(
                        "PBS reference partition was not initialized"
                    )
                selected = batch.slice(
                    selected_start - batch_start, selected_stop - selected_start
                )
                _account_nested_batch(
                    selected, lineage, selected_counts, selected_digest
                )
                writer.write_batch(selected)  # pyright: ignore[reportUnknownMemberType]
            observed = batch_stop
    finally:
        if writer is not None:
            writer.close()
    if (
        schema is None
        or observed != total
        or complete_counts["native_fields"] != denominator.get("native_fields")
        or complete_digest.hexdigest() != denominator.get("native_digest")
    ):
        raise ValueError("PBS reference partition denominator changed")
    projection = _projection(
        iter(pa.ipc.open_stream(pa.memory_map(str(output), "r"))),
        binding,
        denominator,
        nested=True,
        phase="reference-preparation",
        row_window=(start, stop),
    )
    expected = {
        "rows": selected_counts["rows"],
        "native_fields": selected_counts["native_fields"],
        "native_digest": selected_digest.hexdigest(),
    }
    if any(projection[key] != expected[key] for key in expected):
        raise ValueError("PBS reference partition changed after preparation")
    return {
        "schema_version": 1,
        "purpose": "transient-reference-entity-partition",
        "binding_sha256": binding.digest(),
        "denominator": {
            key: denominator[key]
            for key in ("native_fields", "elements", "native_digest")
        },
        "partition": {
            "index": shard_index,
            "count": shard_count,
            "start_row": start,
            "stop_row": stop,
            "path": output.name,
            **_digest(output),
            "expected_projection": expected,
        },
        "publication_performed": False,
        "evidence_truth": False,
    }


def assemble_reference_manifest(
    directory: Path,
    binding: PbsXmlMemberBinding,
    denominator: dict[str, Any],
    index_receipt: dict[str, Any],
    partition_receipts: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Verify independently prepared nodes and assemble the worker contract."""
    expected_denominator = {
        key: denominator[key]
        for key in ("native_fields", "elements", "native_digest")
    }
    binding_sha256 = binding.digest()
    if (
        index_receipt.get("purpose") != "transient-reference-global-index"
        or index_receipt.get("binding_sha256") != binding_sha256
        or index_receipt.get("denominator") != expected_denominator
    ):
        raise ValueError("PBS reference index receipt binding changed")
    index = index_receipt.get("index")
    if not isinstance(index, dict):
        raise TypeError("PBS reference index receipt is invalid")
    index = cast("dict[str, Any]", index)
    index_path = directory / str(index.get("path"))
    if index_path.parent != directory or _digest(index_path) != {
        key: index.get(key) for key in ("sha256", "byte_count")
    }:
        raise ValueError("PBS reference index receipt digest changed")

    partitions: list[dict[str, Any]] = []
    for receipt in partition_receipts:
        if (
            receipt.get("purpose") != "transient-reference-entity-partition"
            or receipt.get("binding_sha256") != binding_sha256
            or receipt.get("denominator") != expected_denominator
        ):
            raise ValueError("PBS reference partition receipt binding changed")
        partition = receipt.get("partition")
        if not isinstance(partition, dict):
            raise TypeError("PBS reference partition receipt is invalid")
        partition = cast("dict[str, Any]", partition)
        path = directory / str(partition.get("path"))
        if path.parent != directory or _digest(path) != {
            key: partition.get(key) for key in ("sha256", "byte_count")
        }:
            raise ValueError("PBS reference partition receipt digest changed")
        partitions.append(partition)
    partitions.sort(key=lambda item: item.get("index", -1))
    total = expected_denominator["elements"]
    count = len(partitions)
    if not 1 <= count <= MAX_REFERENCE_SHARDS:
        raise ValueError("PBS reference partition coverage changed")
    expected_native_fields = 0
    for position, partition in enumerate(partitions):
        expected = partition.get("expected_projection")
        if not isinstance(expected, dict):
            raise TypeError("PBS reference partition receipt is invalid")
        expected = cast("dict[str, Any]", expected)
        if (
            partition.get("index")  # ruff: ignore[too-many-boolean-expressions]
            != position
            or partition.get("count") != count
            or partition.get("start_row") != total * position // count
            or partition.get("stop_row") != total * (position + 1) // count
            or expected.get("rows")
            != partition["stop_row"] - partition["start_row"]
            or type(expected.get("native_fields")) is not int
        ):
            raise ValueError("PBS reference partition coverage changed")
        expected_native_fields += expected["native_fields"]
    if expected_native_fields != expected_denominator["native_fields"]:
        raise ValueError("PBS reference partition denominator changed")
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "purpose": "transient-same-run-reference-qualification-input",
        "binding": binding.model_dump(mode="json"),
        "denominator": expected_denominator,
        "index": index,
        "partitions": partitions,
        "publication_performed": False,
        "evidence_truth": False,
    }
    (directory / "reference-manifest.json").write_bytes(_encoded(manifest))
    return manifest


def _read_index(payload: bytes) -> ReferenceIndex:
    raw: object = json.loads(payload)
    if not isinstance(raw, list):
        raise TypeError("PBS reference shard index is invalid")
    index: ReferenceIndex = {}
    for value in cast("list[object]", raw):
        if not isinstance(value, dict):
            raise TypeError("PBS reference shard index is invalid")
        row = cast("dict[str, Any]", value)
        kind, literal, resources, targets = (
            row.get("kind"),
            row.get("value"),
            row.get("resources"),
            row.get("targets"),
        )
        if (
            not isinstance(kind, str)
            or not isinstance(literal, str)
            or not isinstance(resources, list)
            or type(targets) is not int
            or targets < 0
        ):
            raise ValueError("PBS reference shard index is invalid")
        counts: Counter[str | None] = Counter()
        for raw_resource in cast("list[object]", resources):
            resource = raw_resource
            if not isinstance(resource, dict):
                raise TypeError("PBS reference shard index is invalid")
            resource = cast("dict[str, Any]", resource)
            target, count = resource.get("value"), resource.get("count")
            if (target is not None and not isinstance(target, str)) or (
                type(count) is not int or count < 1
            ):
                raise ValueError("PBS reference shard index is invalid")
            counts[target] = count
        index[kind, literal] = counts, targets
    return index


def prepare_reference_shards(  # ruff: ignore[too-many-branches,too-many-locals,too-many-statements]
    batches: Iterator[pa.RecordBatch],
    binding: PbsXmlMemberBinding,
    denominator: dict[str, Any],
    output: Path,
    *,
    shard_count: int,
) -> dict[str, Any]:
    """Write digest-bound transient Arrow partitions and one global index."""
    total = denominator.get("elements")
    if (
        type(shard_count) is not int
        or not 1 <= shard_count <= MAX_REFERENCE_SHARDS
        or type(total) is not int
        or shard_count > total
    ):
        raise ValueError("invalid PBS reference shard preparation")
    output.mkdir(parents=True, exist_ok=False)
    paths = [
        output / f"reference-{index:02d}.arrow" for index in range(shard_count)
    ]
    writers: list[pa.RecordBatchStreamWriter | None] = [None] * shard_count
    lineage = {
        "source_id": binding.source.source_id,
        "source_sha256": binding.member_payload.sha256,
        "schema_era": binding.source.catalog_version,
        "receipt_sha256": binding.parent_receipt_sha256,
        "member_binding_sha256": binding.digest(),
        "archive_sha256": binding.archive_payload.sha256,
        "member_path": binding.member_path,
    }
    counter_keys = (
        "rows",
        "native_fields",
        "unmapped_rows",
        "duplicate_literal_rows",
        "ambiguous_reference_rows",
        "unresolved_reference_rows",
        "date_unselected_rows",
    )
    expected_counts: list[dict[str, int]] = [
        dict.fromkeys(counter_keys, 0) for _ in range(shard_count)
    ]
    expected_digests = [hashlib.sha256() for _ in range(shard_count)]
    complete_counts: dict[str, int] = dict.fromkeys(counter_keys, 0)
    complete_digest = hashlib.sha256()
    observed = 0
    schema: pa.Schema | None = None
    with TemporaryFile() as spool:  # ruff: ignore[too-many-nested-blocks]
        spool_writer: pa.RecordBatchStreamWriter | None = None
        try:
            for batch in batches:
                if schema is None:
                    schema = batch.schema
                    spool_writer = pa.ipc.new_stream(spool, schema)
                    writers = [
                        pa.ipc.new_stream(str(path), schema) for path in paths
                    ]
                elif not batch.schema.equals(schema, check_metadata=True):
                    raise ValueError(
                        "PBS reference shard entity schema changed"
                    )
                if spool_writer is None:
                    raise RuntimeError(
                        "PBS reference spool was not initialized"
                    )
                spool_writer.write_batch(batch)  # pyright: ignore[reportUnknownMemberType]
                _account_nested_batch(
                    batch, lineage, complete_counts, complete_digest
                )
                batch_start, batch_stop = observed, observed + batch.num_rows
                for index, writer in enumerate(writers):
                    start = total * index // shard_count
                    stop = total * (index + 1) // shard_count
                    selected_start, selected_stop = (
                        max(start, batch_start),
                        min(stop, batch_stop),
                    )
                    if selected_start < selected_stop:
                        if writer is None:
                            raise RuntimeError(
                                "PBS reference partition was not initialized"
                            )
                        selected = batch.slice(
                            selected_start - batch_start,
                            selected_stop - selected_start,
                        )
                        _account_nested_batch(
                            selected,
                            lineage,
                            expected_counts[index],
                            expected_digests[index],
                        )
                        writer.write_batch(  # pyright: ignore[reportUnknownMemberType]
                            selected
                        )
                observed = batch_stop
        finally:
            if spool_writer is not None:
                spool_writer.close()
            for writer in writers:
                if writer is not None:
                    writer.close()
        if schema is None or observed != total:
            raise ValueError("PBS reference shard entity denominator changed")
        if (
            complete_counts["rows"] != total
            or complete_counts["native_fields"] != denominator["native_fields"]
            or complete_digest.hexdigest() != denominator["native_digest"]
        ):
            raise ValueError(
                "PBS reference shard complete stream digest changed"
            )
        spool.seek(0)
        index, identity, indexed_rows = _index(iter(pa.ipc.open_stream(spool)))
        if (
            identity is None
            or not identity.equals(schema, check_metadata=True)
            or indexed_rows != total
        ):
            raise ValueError("PBS reference shard index denominator changed")
    index_path = output / "reference-index.json"
    index_path.write_bytes(_index_payload(index))
    partitions: list[dict[str, Any]] = []
    for index, path in enumerate(paths):
        start = total * index // shard_count
        stop = total * (index + 1) // shard_count
        expected_projection = _projection(
            iter(pa.ipc.open_stream(pa.memory_map(str(path), "r"))),
            binding,
            denominator,
            nested=True,
            phase="reference-preparation",
            row_window=(start, stop),
        )
        independently_expected = {
            "rows": expected_counts[index]["rows"],
            "native_fields": expected_counts[index]["native_fields"],
            "native_digest": expected_digests[index].hexdigest(),
        }
        if any(
            expected_projection[key] != independently_expected[key]
            for key in independently_expected
        ):
            raise ValueError(
                "PBS reference partition changed after preparation"
            )
        partitions.append({
            "index": index,
            "count": shard_count,
            "start_row": start,
            "stop_row": stop,
            "path": path.name,
            **_digest(path),
            "expected_projection": independently_expected,
        })
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "purpose": "transient-same-run-reference-qualification-input",
        "binding": binding.model_dump(mode="json"),
        "denominator": {
            key: denominator[key]
            for key in ("native_fields", "elements", "native_digest")
        },
        "index": {"path": index_path.name, **_digest(index_path)},
        "partitions": partitions,
        "publication_performed": False,
        "evidence_truth": False,
    }
    manifest_path = output / "reference-manifest.json"
    manifest_path.write_bytes(_encoded(manifest))
    return manifest


def qualify_reference_shard(  # ruff: ignore[too-many-locals]
    directory: Path, *, shard_index: int, rows_per_batch: int = 4096
) -> dict[str, Any]:
    """Verify and qualify exactly one prepared reference partition."""
    manifest: object = json.loads(
        (directory / "reference-manifest.json").read_bytes()
    )
    if not isinstance(manifest, dict):
        raise TypeError("PBS reference shard manifest is invalid")
    manifest = cast("dict[str, Any]", manifest)
    partitions_raw = manifest.get("partitions")
    if not isinstance(partitions_raw, list):
        raise TypeError("PBS reference shard manifest is invalid")
    partitions = cast("list[object]", partitions_raw)
    if not 0 <= shard_index < len(partitions):
        raise TypeError("PBS reference shard manifest is invalid")
    partition = partitions[shard_index]
    if not isinstance(partition, dict):
        raise TypeError("PBS reference shard manifest is invalid")
    partition = cast("dict[str, Any]", partition)
    if partition.get("index") != shard_index:
        raise ValueError("PBS reference shard manifest is invalid")
    index_record = manifest.get("index")
    denominator = manifest.get("denominator")
    if not isinstance(index_record, dict) or not isinstance(denominator, dict):
        raise TypeError("PBS reference shard manifest is invalid")
    index_record = cast("dict[str, Any]", index_record)
    denominator = cast("dict[str, Any]", denominator)
    index_path = directory / str(index_record.get("path"))
    partition_path = directory / str(partition.get("path"))
    for path, record in (
        (index_path, index_record),
        (partition_path, partition),
    ):
        if _digest(path) != {
            key: record.get(key) for key in ("sha256", "byte_count")
        }:
            raise ValueError("PBS reference shard input digest changed")
    index = _read_index(index_path.read_bytes())
    binding = PbsXmlMemberBinding.model_validate(manifest.get("binding"))
    source_batches = pa.ipc.open_stream(pa.memory_map(str(partition_path), "r"))
    schema = _schema(source_batches.schema)
    annotated = (
        output
        for batch in source_batches
        for output in _annotated_batches(batch, index, schema, rows_per_batch)
    )
    window = (partition["start_row"], partition["stop_row"])
    projection = _projection(
        annotated,
        binding,
        denominator,
        nested=True,
        phase="references",
        row_window=window,
    )
    expected_projection = partition.get("expected_projection")
    if not isinstance(expected_projection, dict):
        raise TypeError("PBS reference shard projection digest is invalid")
    expected_projection = cast("dict[str, Any]", expected_projection)
    if any(
        projection.get(key) != expected_projection.get(key)
        for key in ("rows", "native_fields", "native_digest")
    ):
        raise ValueError("PBS reference shard projection digest changed")
    manifest_sha256 = hashlib.sha256(
        (directory / "reference-manifest.json").read_bytes()
    ).hexdigest()
    return {
        "schema_version": 1,
        "qualification": "structural_storage_candidate_only",
        "projection_shard": "references",
        "reference_window": {
            key: partition[key]
            for key in ("index", "count", "start_row", "stop_row")
        }
        | {"total_rows": denominator["elements"]},
        "preparation_manifest_sha256": manifest_sha256,
        "expected_reference_projection": {
            key: expected_projection[key]
            for key in ("rows", "native_fields", "native_digest")
        },
        "source_id": binding.source.source_id,
        "parent_receipt_sha256": binding.parent_receipt_sha256,
        "archive_sha256": binding.archive_payload.sha256,
        "member_sha256": binding.member_payload.sha256,
        "member_binding_sha256": binding.digest(),
        **denominator,
        "projections": {"references": projection},
        "date_profile": "not-selected",
        "domain_semantics_qualified": False,
        "publication_performed": False,
    }
