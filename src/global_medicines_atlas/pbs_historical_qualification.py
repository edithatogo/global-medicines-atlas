"""Bounded historical PBS storage/structure accounting without promotion."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Generator, Iterator
from io import BytesIO
from itertools import pairwise
from tempfile import TemporaryFile
from typing import Any, cast

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .pbs_dates import _date_batches  # pyright: ignore[reportPrivateUsage]
from .pbs_historical_projections import (
    iter_pbs_historical_domain_batches,
    iter_pbs_historical_entity_batches,
)
from .pbs_historical_silver import iter_pbs_historical_silver_batches
from .pbs_member_identity import (
    PbsXmlMemberBinding,
    validate_pbs_xml_member_binding,
)
from .pbs_references import (
    _reference_batches,  # pyright: ignore[reportPrivateUsage]
)
from .pbs_xml_slots import iter_pbs_xml_slots
from .receipts import SourceReceipt

_NATIVE_KEYS = (
    "source_ordinal",
    "record_id",
    "path",
    "schema_path",
    "value",
    "state",
)
QUALIFICATION_ROWS_PER_BATCH = 4096


def _encoded(values: list[Any]) -> bytes:
    return (
        json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()
        + b"\n"
    )


def _checkpoint(
    progress: Callable[[str, int, int], None] | None,
    phase: str,
    batches: int,
    rows: int,
) -> None:
    if progress is not None:
        progress(phase, batches, rows)


def _denominator(
    payload: bytes, progress: Callable[[str, int, int], None] | None = None
) -> dict[str, Any]:
    digest = hashlib.sha256()
    fields = elements = 0
    for ordinal, slot in enumerate(iter_pbs_xml_slots(payload)):
        digest.update(
            _encoded([
                ordinal,
                slot.record_id,
                slot.path,
                slot.schema_path,
                slot.value,
                "null" if slot.value is None else "value",
            ])
        )
        fields += 1
        elements += slot.path == slot.record_id + "/text"
        if progress is not None and fields % 65536 == 0:
            progress("denominator", 0, fields)
    if progress is not None:
        progress("denominator", 0, fields)
    return {
        "native_fields": fields,
        "elements": elements,
        "native_digest": digest.hexdigest(),
    }


def _projection(
    batches: Iterator[pa.RecordBatch],
    binding: PbsXmlMemberBinding,
    denominator: dict[str, Any],
    *,
    nested: bool,
    progress: Callable[[str, int, int], None] | None = None,
    phase: str = "unavailable",
) -> dict[str, Any]:
    expected = {
        "source_id": binding.source.source_id,
        "source_sha256": binding.member_payload.sha256,
        "schema_era": binding.source.catalog_version,
        "receipt_sha256": binding.parent_receipt_sha256,
        "member_binding_sha256": binding.digest(),
        "archive_sha256": binding.archive_payload.sha256,
        "member_path": binding.member_path,
    }
    metadata_expected = {
        b"source_id": binding.source.source_id.encode(),
        b"source_receipt_sha256": binding.parent_receipt_sha256.encode(),
        b"member_binding_sha256": binding.digest().encode(),
        b"member_binding": binding.canonical_json(),
        b"qualification": b"candidate",
        b"conversion": b"none",
    }
    counts: dict[str, int] = dict.fromkeys(
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
    digest = hashlib.sha256()
    for batch_number, batch in enumerate(batches, 1):
        metadata = batch.schema.metadata or {}
        if any(
            metadata.get(key) != value
            for key, value in metadata_expected.items()
        ):
            raise ValueError("historical projection metadata changed")
        table = pa.Table.from_batches([batch])
        output = BytesIO()
        pq.write_table(table, output)  # pyright: ignore[reportUnknownMemberType]
        restored = pq.read_table(BytesIO(output.getvalue()))  # pyright: ignore[reportUnknownMemberType]
        if not table.equals(restored, check_metadata=True):
            raise ValueError("historical Parquet roundtrip changed projection")
        if nested:
            _account_nested_batch(batch, expected, counts, digest)
            _checkpoint(progress, phase, batch_number, counts["rows"])
            continue
        for row in batch.to_pylist():
            if any(row.get(key) != value for key, value in expected.items()):
                raise ValueError("historical projection row lineage changed")
            counts["rows"] += 1
            counts["unmapped_rows"] += row.get("mapping_target") == "unmapped"
            counts["duplicate_literal_rows"] += (
                row.get("diagnostic") == "duplicate_source_literal"
            )
            counts["ambiguous_reference_rows"] += (
                row.get("diagnostic") == "ambiguous_source_targets"
            )
            counts["unresolved_reference_rows"] += (
                row.get("diagnostic") == "unresolved"
            )
            counts["date_unselected_rows"] += (
                row.get("date_conversion_status") == "profile_not_selected"
            )
            for field in (row,):
                if (
                    any(
                        field.get(key) != value
                        for key, value in expected.items()
                    )
                    or field["source_field_id"]
                    != f"{binding.member_payload.sha256}:{field['path']}"
                ):
                    raise ValueError("historical native field lineage changed")
                digest.update(_encoded([field[key] for key in _NATIVE_KEYS]))
                counts["native_fields"] += 1
        _checkpoint(progress, phase, batch_number, counts["rows"])
    if (
        counts["native_fields"] != denominator["native_fields"]
        or counts["rows"]
        != denominator["elements" if nested else "native_fields"]
    ):
        raise ValueError("historical projection denominator changed")
    if digest.hexdigest() != denominator["native_digest"]:
        raise ValueError("historical projection native digest changed")
    return {
        **counts,
        "native_digest": digest.hexdigest(),
        "parquet_roundtrip_verified": True,
    }


def _account_nested_batch(
    batch: pa.RecordBatch,
    expected: dict[str, str],
    counts: dict[str, int],
    digest: Any,
) -> None:
    """Account for an entity batch without materialising nested row dicts."""
    columns: dict[str, list[Any]] = {
        name: cast(
            "list[Any]",
            batch.column(batch.schema.get_field_index(name)).to_pylist(),
        )
        for name in (
            *expected,
            "entity_id",
            "parent_entity_id",
            "item_occurrence_id",
            "mapping_target",
            "diagnostic",
            "date_conversion_status",
        )
        if name in batch.schema.names
    }
    if any(
        any(value != expected[name] for value in columns[name])
        for name in expected
    ):
        raise ValueError("historical projection row lineage changed")

    nested = cast(
        "pa.ListArray[Any]",
        batch.column(batch.schema.get_field_index("native_fields")),
    )
    lengths = cast("list[int]", pc.list_value_length(nested).to_pylist())
    if any(length == 0 for length in lengths):
        raise ValueError("historical entity lineage is empty")
    offsets = cast("list[int]", nested.offsets.to_pylist())
    flattened = cast("pa.StructArray", pc.list_flatten(nested))
    fields: dict[str, list[Any]] = {
        name: cast(
            "list[Any]",
            flattened.field(name).to_pylist(),  # pyright: ignore[reportUnknownMemberType]
        )
        for name in (
            *expected,
            "source_field_id",
            "item_occurrence_id",
            *_NATIVE_KEYS,
        )
    }
    if any(
        any(value != expected[name] for value in fields[name])
        for name in expected
    ) or any(
        source_field_id != f"{expected['source_sha256']}:{path}"
        for source_field_id, path in zip(
            fields["source_field_id"], fields["path"], strict=True
        )
    ):
        raise ValueError("historical native field lineage changed")

    for row_number, (start, stop) in enumerate(pairwise(offsets)):
        record_id = fields["record_id"][start]
        parent_path = "/".join(record_id.split("/")[:-2])
        expected_parent = (
            f"{expected['source_sha256']}:{parent_path}"
            if parent_path
            else None
        )
        if (
            columns["entity_id"][row_number]
            != f"{expected['source_sha256']}:{record_id}"
            or columns["parent_entity_id"][row_number] != expected_parent
            or any(
                value != record_id for value in fields["record_id"][start:stop]
            )
            or columns["item_occurrence_id"][row_number]
            != fields["item_occurrence_id"][start]
        ):
            raise ValueError("historical entity occurrence lineage changed")

    counts["rows"] += batch.num_rows
    counts["unmapped_rows"] += columns.get("mapping_target", []).count(
        "unmapped"
    )
    counts["duplicate_literal_rows"] += columns.get("diagnostic", []).count(
        "duplicate_source_literal"
    )
    counts["ambiguous_reference_rows"] += columns.get("diagnostic", []).count(
        "ambiguous_source_targets"
    )
    counts["unresolved_reference_rows"] += columns.get("diagnostic", []).count(
        "unresolved"
    )
    counts["date_unselected_rows"] += columns.get(
        "date_conversion_status", []
    ).count("profile_not_selected")
    for values in zip(*(fields[name] for name in _NATIVE_KEYS), strict=True):
        digest.update(_encoded(list(values)))
    counts["native_fields"] += len(fields["record_id"])


def qualify_pbs_historical_projections(
    archive_payload: bytes,
    member_payload: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    *,
    rows_per_batch: int = QUALIFICATION_ROWS_PER_BATCH,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, Any]:
    """Account for every XML slot in five candidate projections and Parquet.

    Revalidate the exact historical parent/archive/member binding before work.
    An independent bounded XML-slot walk supplies ordered value/path/state
    digests and field/element denominators. Each projection must preserve them,
    full top-level/nested lineage and metadata-aware per-batch Parquet equality.
    Report only fixed counters and evidence IDs, never native text or payloads.
    All transforms use existing finite parsing/index/entity/output bounds;
    The default uses the existing maximum validated row bound to reduce repeated
    Parquet setup; encoded-byte limits can still emit smaller batches. In-memory
    per-batch Parquet buffers add memory, not a total resident cap. Entity output
    is replayed from an automatically deleted Arrow spool so reference and date
    qualification do not rebuild the source-derived entity projection.
    No date profile, semantic/source-era qualification, acquisition, filesystem
    output, network call, admission or publication occurs. Errors yield no report.
    An optional callback receives phase codes and processed batch/row counters,
    never source text. Its partial checkpoints are not qualification reports.
    """
    if progress is not None:
        progress("binding-validation", 0, 0)
    binding = validate_pbs_xml_member_binding(
        binding, archive_payload, member_payload, parent
    )
    if progress is not None:
        progress("denominator", 0, 0)
    denominator = _denominator(member_payload, progress)
    routes = (
        ("native", iter_pbs_historical_silver_batches, False),
        ("domain", iter_pbs_historical_domain_batches, False),
    )
    projections = {}
    for name, route, nested in routes:
        if progress is not None:
            progress(name, 0, 0)
        projections[name] = _projection(
            route(
                archive_payload,
                member_payload,
                parent,
                binding,
                rows_per_batch=rows_per_batch,
            ),
            binding,
            denominator,
            nested=nested,
            progress=progress,
            phase=name,
        )
    with TemporaryFile() as spool:
        entity_schema: pa.Schema | None = None

        def entity_batches() -> Generator[pa.RecordBatch]:
            nonlocal entity_schema
            writer = None
            try:
                for batch in iter_pbs_historical_entity_batches(
                    archive_payload,
                    member_payload,
                    parent,
                    binding,
                    rows_per_batch=rows_per_batch,
                ):
                    if writer is None:
                        entity_schema = batch.schema
                        writer = pa.ipc.new_stream(spool, batch.schema)
                    writer.write_batch(  # pyright: ignore[reportUnknownMemberType]
                        batch
                    )
                    yield batch
            finally:
                if writer is not None:
                    writer.close()

        if progress is not None:
            progress("entities", 0, 0)
        entity_stream = entity_batches()
        try:
            projections["entities"] = _projection(
                entity_stream,
                binding,
                denominator,
                nested=True,
                progress=progress,
                phase="entities",
            )
        finally:
            entity_stream.close()
        if entity_schema is None:
            raise ValueError("historical entity projection is empty")

        def replay_entities() -> Iterator[pa.RecordBatch]:
            spool.seek(0)
            yield from pa.ipc.open_stream(spool)

        replay_routes = (
            (
                "references",
                _reference_batches(
                    replay_entities(), replay_entities(), rows_per_batch
                ),
            ),
            ("dates", _date_batches(replay_entities(), None, rows_per_batch)),
        )
        for name, batches in replay_routes:
            if progress is not None:
                progress(name, 0, 0)
            projections[name] = _projection(
                batches,
                binding,
                denominator,
                nested=True,
                progress=progress,
                phase=name,
            )
    return {
        "schema_version": 1,
        "qualification": "structural_storage_candidate_only",
        "source_id": binding.source.source_id,
        "parent_receipt_sha256": binding.parent_receipt_sha256,
        "archive_sha256": binding.archive_payload.sha256,
        "member_sha256": binding.member_payload.sha256,
        "member_binding_sha256": binding.digest(),
        **denominator,
        "projections": projections,
        "date_profile": "not-selected",
        "domain_semantics_qualified": False,
        "publication_performed": False,
    }
