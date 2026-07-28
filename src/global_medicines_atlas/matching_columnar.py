"""Deterministic columnar and review outputs for matching qualification."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from itertools import starmap
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import Field

from .matching_features import FeatureEvidence
from .models import FrozenModel
from .review_queue import ReviewQueueEntry

MATCHING_OUTPUT_SCHEMA_VERSION = "matching-output-v1"


class MatchingOutputManifest(FrozenModel):
    schema_version: str = MATCHING_OUTPUT_SCHEMA_VERSION
    candidate_count: int = Field(ge=0)
    feature_count: int = Field(ge=0)
    files: dict[str, str]
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    clinical_equivalence_disclaimer: str

    def canonical_json(self) -> bytes:
        return (
            json.dumps(
                self.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()


DISCLAIMER = (
    "Candidate mappings are review aids and are not clinical, therapeutic, "
    "substitution, or interchangeability recommendations."
)

CANDIDATE_SCHEMA = pa.schema([
    ("candidate_id", pa.string()),
    ("source_concept_id", pa.string()),
    ("target_concept_id", pa.string()),
    ("source_jurisdiction", pa.string()),
    ("target_jurisdiction", pa.string()),
    ("mapping_level", pa.string()),
    ("confidence", pa.float64()),
    ("abstained", pa.bool_()),
    ("review_state", pa.string()),
    ("reason_codes", pa.list_(pa.string())),
    ("policy_version", pa.string()),
    ("feature_version", pa.string()),
    ("index_version", pa.string()),
    ("model_version", pa.string()),
    ("evaluated_at", pa.timestamp("us", tz="UTC")),
    ("queued_at", pa.timestamp("us", tz="UTC")),
    ("clinical_equivalence_claim", pa.bool_()),
])

FEATURE_SCHEMA = pa.schema([
    ("candidate_id", pa.string()),
    ("position", pa.int64()),
    ("feature", pa.string()),
    ("disposition", pa.string()),
    ("contribution", pa.float64()),
    ("explanation", pa.string()),
    ("source_value", pa.string()),
    ("target_value", pa.string()),
    ("provenance_ids", pa.list_(pa.string())),
])


def _canonical_bytes(value: object) -> bytes:
    def encode(item: object) -> str:
        if isinstance(item, datetime):
            return item.isoformat().replace("+00:00", "Z")
        raise TypeError(f"Unsupported canonical JSON value: {type(item)!r}")

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=encode,
    ).encode()


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_row(entry: ReviewQueueEntry) -> dict[str, object]:
    candidate = entry.candidate
    decision = entry.decision
    return {
        "candidate_id": candidate.candidate_id,
        "source_concept_id": candidate.source_concept_id,
        "target_concept_id": candidate.target_concept_id,
        "source_jurisdiction": candidate.source_jurisdiction,
        "target_jurisdiction": candidate.target_jurisdiction,
        "mapping_level": candidate.mapping_level.value,
        "confidence": decision.confidence,
        "abstained": decision.abstained,
        "review_state": decision.review_state.value,
        "reason_codes": [item.value for item in decision.reason_codes],
        "policy_version": decision.policy_version,
        "feature_version": candidate.features.feature_version,
        "index_version": candidate.index_version,
        "model_version": candidate.model_version,
        "evaluated_at": candidate.features.evaluated_at,
        "queued_at": entry.queued_at,
        "clinical_equivalence_claim": False,
    }


def _feature_rows(entry: ReviewQueueEntry) -> list[dict[str, object]]:
    candidate = entry.candidate

    def row(position: int, item: FeatureEvidence) -> dict[str, object]:
        return {
            "candidate_id": candidate.candidate_id,
            "position": position,
            "feature": item.kind.value,
            "disposition": item.disposition.value,
            "contribution": item.contribution,
            "explanation": item.explanation,
            "source_value": item.source_value,
            "target_value": item.target_value,
            "provenance_ids": list(item.provenance_ids),
        }

    return list(
        starmap(
            row,
            enumerate(
                candidate.features.ordered_evidence,
                start=1,
            ),
        )
    )


def _write_parquet(
    rows: list[dict[str, object]],
    path: Path,
    schema: pa.Schema,
) -> pa.Table:
    table = pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(  # pyright: ignore[reportUnknownMemberType]
        table,
        path,
        compression="zstd",
        use_dictionary=False,
        write_statistics=True,
        data_page_version="1.0",
    )
    return table


def write_matching_outputs(  # ruff: ignore[too-many-locals]
    entries: Iterable[ReviewQueueEntry],
    output_dir: Path,
    *,
    adjudication_events: Iterable[Mapping[str, object]] = (),
) -> MatchingOutputManifest:
    """Write stable Parquet, JSONL, DuckDB views, and a content manifest."""
    ordered = tuple(
        sorted(entries, key=lambda item: item.candidate.candidate_id)
    )
    candidate_rows = [_candidate_row(item) for item in ordered]
    feature_rows = [row for item in ordered for row in _feature_rows(item)]
    events = sorted(
        (dict(item) for item in adjudication_events),
        key=lambda item: (
            str(item.get("candidate_id", "")),
            str(item.get("occurred_at", "")),
            str(item.get("event_id", "")),
        ),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = output_dir / "matching_candidates.parquet"
    features_path = output_dir / "matching_features.parquet"
    queue_path = output_dir / "review_queue.jsonl"
    events_path = output_dir / "adjudication_events.jsonl"
    database_path = output_dir / "matching.duckdb"
    manifest_path = output_dir / "manifest.json"

    candidate_table = _write_parquet(
        candidate_rows,
        candidates_path,
        CANDIDATE_SCHEMA,
    )
    feature_table = _write_parquet(
        feature_rows,
        features_path,
        FEATURE_SCHEMA,
    )
    queue_path.write_bytes(
        b"".join(_canonical_bytes(item) + b"\n" for item in candidate_rows)
    )
    events_path.write_bytes(
        b"".join(_canonical_bytes(item) + b"\n" for item in events)
    )
    if database_path.exists():
        database_path.unlink()
    connection = duckdb.connect(str(database_path))
    try:
        connection.register("_candidate_input", candidate_table)
        connection.register("_feature_input", feature_table)
        connection.execute(
            "CREATE TABLE candidate_data AS "
            "SELECT * FROM _candidate_input ORDER BY candidate_id"
        )
        connection.execute(
            "CREATE TABLE feature_data AS "
            "SELECT * FROM _feature_input ORDER BY candidate_id, position"
        )
        connection.execute(
            "CREATE VIEW matching_candidates AS SELECT * FROM candidate_data"
        )
        connection.execute(
            "CREATE VIEW matching_features AS SELECT * FROM feature_data"
        )
        connection.execute(
            """
            CREATE VIEW matching_review_summary AS
            SELECT source_jurisdiction, target_jurisdiction, mapping_level,
                   review_state, abstained, count(*) AS candidate_count
            FROM matching_candidates
            GROUP BY ALL
            """
        )
    finally:
        connection.close()

    input_digest = hashlib.sha256(
        _canonical_bytes({
            "candidates": candidate_rows,
            "features": feature_rows,
            "events": events,
        })
    ).hexdigest()
    paths = (
        candidates_path,
        features_path,
        queue_path,
        events_path,
        database_path,
    )
    manifest = MatchingOutputManifest(
        candidate_count=len(candidate_rows),
        feature_count=len(feature_rows),
        files={path.name: _digest(path) for path in paths},
        input_digest=input_digest,
        clinical_equivalence_disclaimer=DISCLAIMER,
    )
    manifest_path.write_bytes(manifest.canonical_json())
    return manifest
