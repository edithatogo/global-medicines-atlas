"""Transient same-run inputs for bounded historical PBS reference workers."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable, Iterator
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
    progress: Callable[[str, str, int, int], None] | None = None,
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
    if progress is not None:
        progress("entity-partition-preparation", "references", 0, 0)
    with TemporaryFile() as spool:  # ruff: ignore[too-many-nested-blocks]
        spool_writer: pa.RecordBatchStreamWriter | None = None
        try:
            batch_count = 0
            for batch in batches:
                batch_count += 1
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
                if progress is not None:
                    progress(
                        "entity-partition-preparation",
                        "references",
                        batch_count,
                        observed,
                    )
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
        if progress is not None:
            progress(
                "global-index-preparation",
                "references",
                batch_count,
                observed,
            )
        index, identity, indexed_rows = _index(iter(pa.ipc.open_stream(spool)))
        if (
            identity is None
            or not identity.equals(schema, check_metadata=True)
            or indexed_rows != total
        ):
            raise ValueError("PBS reference shard index denominator changed")
    index_path = output / "reference-index.json"
    index_path.write_bytes(_index_payload(index))
    if progress is not None:
        progress("manifest-verification", "references", batch_count, observed)
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
