"""Bounded in-memory Arrow tables for MBS schema-change candidates.

The projection retains source and selection denominators and marks literal
absence as unknown. It does not acquire, qualify, persist, or publish source
data, and it never labels an observed-only key as an addition or cessation.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pyarrow as pa

from .mbs_schema_change_events import (
    MbsSchemaChangeReport,
)

MAX_BATCH_ROWS = 1024
MAX_CANONICAL_BYTES = 128 * 1024 * 1024
_METADATA: dict[bytes | str, bytes | str] = {
    b"schema_id": b"global-medicines-atlas.mbs-schema-change-arrow",
    b"schema_version": b"1",
    b"qualification": b"observed_change_candidate",
    b"absence_interpretation": b"unknown",
}
_FIELD = pa.struct([
    pa.field("name", pa.string(), nullable=False),
    pa.field("state", pa.string(), nullable=False),
    pa.field("value", pa.string()),
])
_COHORT = pa.struct([
    *[
        pa.field(name, pa.string(), nullable=False)
        for name in (
            "source_id",
            "table",
            "dimension",
            "schema_era",
            "identity_profile",
            "source_revision",
            "source_path",
            "b1_sha256",
            "b2_sha256",
            "scope_id",
            "cohort",
            "evidence_class",
            "observed_at",
        )
    ],
    pa.field("source_record_count", pa.int64(), nullable=False),
    pa.field("omitted_record_count", pa.int64(), nullable=False),
    pa.field("selected_key_count", pa.int64(), nullable=False),
    pa.field("selected_row_count", pa.int64(), nullable=False),
    pa.field("unmatched_selected_key_count", pa.int64(), nullable=False),
    pa.field("scan_complete", pa.bool_(), nullable=False),
])
ENVELOPE_SCHEMA = pa.schema(
    [
        pa.field("report_sha256", pa.string(), nullable=False),
        pa.field("qualification", pa.string(), nullable=False),
        pa.field("absence_interpretation", pa.string(), nullable=False),
        pa.field("mapping_sha256", pa.string(), nullable=False),
        pa.field("event_count", pa.int64(), nullable=False),
        pa.field("historical", _COHORT, nullable=False),
        pa.field("current", _COHORT, nullable=False),
    ],
    metadata=_METADATA,
)
EVENT_SCHEMA = pa.schema(
    [
        pa.field("report_sha256", pa.string(), nullable=False),
        pa.field("ordinal", pa.int64(), nullable=False),
        pa.field("event_id", pa.string(), nullable=False),
        pa.field("native_id", pa.string(), nullable=False),
        pa.field("silver_target_field", pa.string()),
        pa.field("kind", pa.string(), nullable=False),
        pa.field("historical_occurrence", pa.string()),
        pa.field("current_occurrence", pa.string()),
        pa.field("historical", _FIELD),
        pa.field("current", _FIELD),
    ],
    metadata=_METADATA,
)


def _cohort(
    report: MbsSchemaChangeReport, *, historical: bool
) -> dict[str, object]:
    cohort = report.historical if historical else report.current
    snapshot = cohort.snapshot
    selected_rows = len(snapshot.rows)
    return {
        "source_id": snapshot.source_id,
        "table": snapshot.table,
        "dimension": snapshot.dimension,
        "schema_era": snapshot.schema_era,
        "identity_profile": snapshot.identity_profile,
        "source_revision": snapshot.source_revision,
        "source_path": snapshot.source_path,
        "b1_sha256": snapshot.b1_sha256,
        "b2_sha256": snapshot.b2_sha256,
        "scope_id": snapshot.scope_id,
        "cohort": snapshot.cohort,
        "evidence_class": cohort.evidence_class,
        "observed_at": snapshot.observed_at.isoformat(),
        "source_record_count": cohort.source_record_count,
        "omitted_record_count": cohort.omitted_record_count,
        "selected_key_count": len(cohort.selected_native_keys),
        "selected_row_count": selected_rows,
        "unmatched_selected_key_count": (
            len(cohort.selected_native_keys) - selected_rows
        ),
        "scan_complete": snapshot.complete,
    }


def _event_batches(
    report: MbsSchemaChangeReport, rows_per_batch: int
) -> Iterator[pa.RecordBatch]:
    for start in range(0, len(report.events), rows_per_batch):
        rows = [
            {
                **event.model_dump(mode="json"),
                "report_sha256": report.report_sha256,
                "ordinal": start + offset,
            }
            for offset, event in enumerate(
                report.events[start : start + rows_per_batch]
            )
        ]
        yield pa.RecordBatch.from_pylist(rows, schema=EVENT_SCHEMA)


def project_mbs_schema_change_report(
    value: MbsSchemaChangeReport,
    *,
    rows_per_batch: int = MAX_BATCH_ROWS,
) -> tuple[pa.Table, Iterator[pa.RecordBatch]]:
    """Validate and project one report plus bounded, ordered event batches.

    The envelope distinguishes full parsed source records, omitted records,
    selected native keys, and observed selected rows. Missing selected keys
    remain unmatched observations with unknown absence meaning. The report
    digest binds the complete supplied cohorts, mapping, and event payload.
    """
    if (
        type(rows_per_batch) is not int
        or not 1 <= rows_per_batch <= MAX_BATCH_ROWS
    ):
        raise ValueError("rows_per_batch must be an integer from 1 to 1024")
    report = MbsSchemaChangeReport.model_validate(
        value.model_dump(warnings=False)
    )
    canonical = json.dumps(
        report.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(canonical) > MAX_CANONICAL_BYTES:
        raise ValueError("MBS schema change canonical byte limit exceeded")
    envelope = pa.Table.from_pylist(
        [
            {
                "report_sha256": report.report_sha256,
                "qualification": report.qualification,
                "absence_interpretation": report.absence_interpretation,
                "mapping_sha256": report.mapping.mapping_sha256,
                "event_count": len(report.events),
                "historical": _cohort(report, historical=True),
                "current": _cohort(report, historical=False),
            }
        ],
        schema=ENVELOPE_SCHEMA,
    )
    return envelope, _event_batches(report, rows_per_batch)


__all__ = [
    "ENVELOPE_SCHEMA",
    "EVENT_SCHEMA",
    "MAX_BATCH_ROWS",
    "MAX_CANONICAL_BYTES",
    "project_mbs_schema_change_report",
]
