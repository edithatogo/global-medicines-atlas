"""Bounded historical PBS storage/structure accounting without promotion."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator
from io import BytesIO
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .pbs_historical_annotations import (
    iter_pbs_historical_date_batches,
    iter_pbs_historical_reference_batches,
)
from .pbs_historical_projections import (
    iter_pbs_historical_domain_batches,
    iter_pbs_historical_entity_batches,
)
from .pbs_historical_silver import iter_pbs_historical_silver_batches
from .pbs_member_identity import (
    PbsXmlMemberBinding,
    validate_pbs_xml_member_binding,
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
    counts = dict.fromkeys(
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
        for row in batch.to_pylist():
            if any(row.get(key) != value for key, value in expected.items()):
                raise ValueError("historical projection row lineage changed")
            if nested:
                fields = row["native_fields"]
                if not fields:
                    raise ValueError("historical entity lineage is empty")
                record_id = fields[0]["record_id"]
                parent_path = "/".join(record_id.split("/")[:-2])
                expected_parent = (
                    f"{binding.member_payload.sha256}:{parent_path}"
                    if parent_path
                    else None
                )
                if (
                    row["entity_id"]
                    != f"{binding.member_payload.sha256}:{record_id}"
                    or row["parent_entity_id"] != expected_parent
                    or any(field["record_id"] != record_id for field in fields)
                    or row["item_occurrence_id"]
                    != fields[0]["item_occurrence_id"]
                ):
                    raise ValueError(
                        "historical entity occurrence lineage changed"
                    )
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
            for field in row["native_fields"] if nested else (row,):
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


def qualify_pbs_historical_projections(
    archive_payload: bytes,
    member_payload: bytes,
    parent: SourceReceipt,
    binding: PbsXmlMemberBinding,
    *,
    rows_per_batch: int = 1024,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, Any]:
    """Account for every XML slot in five candidate projections and Parquet.

    Revalidate the exact historical parent/archive/member binding before work.
    An independent bounded XML-slot walk supplies ordered value/path/state
    digests and field/element denominators. Each projection must preserve them,
    full top-level/nested lineage and metadata-aware per-batch Parquet equality.
    Report only fixed counters and evidence IDs, never native text or payloads.
    All transforms use existing finite parsing/index/entity/output bounds;
    in-memory per-batch Parquet buffers add memory, not a total resident cap.
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
        ("entities", iter_pbs_historical_entity_batches, True),
        ("references", iter_pbs_historical_reference_batches, True),
        ("dates", iter_pbs_historical_date_batches, True),
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
