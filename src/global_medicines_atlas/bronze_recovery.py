# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false

"""Reconstruct rebuildable Bronze layers from payloads and receipts.

The immutable source payload and its content-addressed receipt are
evidentiary truth. Hugging Face and other publication surfaces are not.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Literal

import orjson
from pydantic import Field

from .bronze_admission import (
    DownstreamAdmissionError,
    latest_admission_for_receipt,
    require_admitted_for_processing,
)
from .bronze_landing import (
    ACQUISITION_DIR,
    LINEAGE_DIR,
    PARQUET_DIR,
    PAYLOAD_DIR,
    RECEIPT_DIR,
    BronzeAcquisition,
    BronzeLanding,
    land_bronze_payload,
    write_rebuildable_layers,
)
from .iceberg_ready import IcebergReadyTableSpec, iceberg_rest_create_body
from .models import FrozenModel
from .receipts import (
    SHA256_PATTERN,
    AcquisitionEvent,
    SourceReceipt,
    require_temporal,
)

CATALOGUE_DIR = "catalogue"
RECOVERY_DIR = "recovery"
JOURNAL_NAME = "journal.jsonl"
RECOVERY_SCHEMA_ID = "global-medicines-atlas.bronze-recovery-evidence"
CURRENT_PARSER_GENERATION = 1
_DERIVATIVE_SUFFIXES = (".duckdb", ".lance", ".lancedb")
_PARTIAL_LAYER_FLOOR = 2
_DUPLICATE_COUNT = 2


class BronzeRecoveryError(ValueError):
    """Reconstruction cannot proceed without inventing evidentiary truth."""


class RecoveryScenario(StrEnum):
    """Machine-verifiable disaster and reproducibility rehearsals."""

    CLEAN_ROOM_REBUILD = "clean-room-rebuild"
    REBUILDABLE_DATABASE_LOSS = "rebuildable-database-loss"
    CATALOGUE_DELETION = "catalogue-deletion"
    PARQUET_DELETION = "parquet-deletion"
    INTERRUPTED_ACQUISITION = "interrupted-acquisition"
    PARTIAL_STORAGE_LOSS = "partial-storage-loss"
    DUPLICATE_RETRIEVAL = "duplicate-retrieval"
    CODE_ROLLBACK_NEWER_PAYLOADS = "code-rollback-newer-payloads"


class RecoveredLandingEvidence(FrozenModel):
    """Compact identity of one reconstructed acquisition."""

    acquisition_id: str = Field(pattern=SHA256_PATTERN)
    content_id: str = Field(pattern=SHA256_PATTERN)
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    receipt_digest: str = Field(pattern=SHA256_PATTERN)
    parquet_sha256: str = Field(pattern=SHA256_PATTERN)
    catalogue_identifier: str = Field(min_length=3)


class BronzeRecoveryEvidence(FrozenModel):
    """Compact, independently verifiable reconstruction receipt."""

    schema_id: Literal["global-medicines-atlas.bronze-recovery-evidence"] = (
        RECOVERY_SCHEMA_ID
    )
    schema_version: Literal[1] = 1
    hugging_face_is_source_of_truth: Literal[False] = False
    evidentiary_inputs: tuple[Literal["payload"], Literal["receipt"]] = (
        "payload",
        "receipt",
    )
    rebuildable_derivatives_absent: bool
    scenarios: tuple[str, ...]
    landings: tuple[RecoveredLandingEvidence, ...]
    incomplete_count: int = Field(ge=0)
    evidence_digest: str = Field(pattern=SHA256_PATTERN)

    def canonical_json(self) -> bytes:
        """Stable JSON including the evidence digest."""

        payload = self.model_dump(mode="json", exclude_none=False)
        return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS) + b"\n"


def _receipt_field_names() -> frozenset[str]:
    return frozenset(SourceReceipt.model_fields)


def _as_object_map(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise BronzeRecoveryError(f"{label} must be a JSON object")
    mapped: dict[str, object] = {}
    for key, item in value.items():
        mapped[str(key)] = item
    return mapped


def load_receipt_for_reconstruction(
    raw: bytes,
    *,
    parser_generation: int = CURRENT_PARSER_GENERATION,
) -> tuple[SourceReceipt, bool]:
    """Parse a receipt; older parsers ignore newer unknown fields."""

    document = _as_object_map(json.loads(raw), "receipt")
    known = _receipt_field_names()
    extra = [key for key in document if key not in known]
    compatible = {key: value for key, value in document.items() if key in known}
    if extra and parser_generation > CURRENT_PARSER_GENERATION:
        raise BronzeRecoveryError("receipt fields exceed this parser")
    receipt = SourceReceipt.model_validate(compatible)
    return receipt, bool(extra)


def _payload_path_for(bronze_root: Path, content_id: str) -> Path | None:
    folder = bronze_root / PAYLOAD_DIR / "by_content" / content_id
    matches = sorted(folder.glob("payload.*"))
    if not matches:
        return None
    return matches[0]


def _receipt_paths(bronze_root: Path) -> list[Path]:
    receipts = bronze_root / RECEIPT_DIR
    if not receipts.exists():
        return []
    return sorted(path for path in receipts.rglob("*.json") if path.is_file())


def _payload_paths(bronze_root: Path) -> list[Path]:
    payloads = bronze_root / PAYLOAD_DIR / "by_content"
    if not payloads.exists():
        return []
    return sorted(
        path for path in payloads.glob("*/payload.*") if path.is_file()
    )


def _derivatives_present(bronze_root: Path) -> bool:
    return any(
        path.suffix.lower() in _DERIVATIVE_SUFFIXES
        for path in bronze_root.rglob("*")
    )


def _read_journal(bronze_root: Path) -> list[dict[str, object]]:
    journal = bronze_root / RECOVERY_DIR / JOURNAL_NAME
    if not journal.is_file():
        return []
    records: list[dict[str, object]] = []
    for line in journal.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            records.append(_as_object_map(parsed, "journal record"))
    return records


def _append_journal(bronze_root: Path, record: Mapping[str, object]) -> None:
    folder = bronze_root / RECOVERY_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / JOURNAL_NAME
    with path.open("ab") as handle:
        handle.write(orjson.dumps(dict(record)) + b"\n")


def _catalogue_path(bronze_root: Path, identifier: str) -> Path:
    namespace, _, name = identifier.partition(".")
    return bronze_root / CATALOGUE_DIR / namespace / name / "create-table.json"


def _write_catalogue(bronze_root: Path, spec: IcebergReadyTableSpec) -> Path:
    path = _catalogue_path(bronze_root, spec.identifier)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = iceberg_rest_create_body(spec)
    path.write_bytes(orjson.dumps(body, option=orjson.OPT_SORT_KEYS) + b"\n")
    return path


def resume_interrupted_acquisition(
    bronze_root: Path,
    *,
    payload: bytes,
    receipt: SourceReceipt,
    media_hint: str | None = None,
) -> BronzeAcquisition | BronzeLanding:
    """Finish an acquisition after payload staging without rewriting bytes."""

    temporal = require_temporal(receipt.temporal)
    content_id = temporal.content_id or receipt.payload.sha256
    staged = _payload_path_for(bronze_root, content_id)
    if staged is not None and staged.read_bytes() != payload:
        raise BronzeRecoveryError("staged payload does not match receipt")
    landing = land_bronze_payload(
        payload,
        receipt,
        bronze_root=bronze_root,
        media_hint=media_hint,
    )
    _append_journal(
        bronze_root,
        {
            "scenario": RecoveryScenario.INTERRUPTED_ACQUISITION.value,
            "content_id": content_id,
            "acquisition_id": temporal.acquisition_id,
        },
    )
    return landing


def _ensure_acquisition_event(
    bronze_root: Path,
    receipt: SourceReceipt,
    *,
    content_id: str,
) -> None:
    temporal = require_temporal(receipt.temporal)
    source_id = receipt.source.source_id
    event_path = (
        bronze_root
        / ACQUISITION_DIR
        / source_id
        / f"{temporal.acquisition_id}.json"
    )
    if event_path.exists():
        return
    event = AcquisitionEvent(
        acquisition_id=temporal.acquisition_id,
        content_id=content_id,
        source_id=source_id,
        source_version=temporal.source_version,
        retrieved_at=temporal.retrieved_at,
        source_published_at=temporal.source_published_at,
        source_effective_at=temporal.source_effective_at,
        valid_from=temporal.valid_from,
        valid_to=temporal.valid_to,
        payload_sha256=receipt.payload.sha256,
        source=receipt.source,
        retrieval=receipt.retrieval,
        reuse=receipt.reuse,
        rights_state=receipt.rights_state,
        rights_reference=receipt.rights_reference,
        rights_policy=receipt.rights_policy,
        evidence_class=receipt.evidence_class,
    )
    event_path.parent.mkdir(parents=True, exist_ok=True)
    event_path.write_bytes(event.canonical_json() + b"\n")


def _rebuild_one(
    bronze_root: Path,
    receipt_path: Path,
    *,
    parser_generation: int,
) -> tuple[RecoveredLandingEvidence | None, str, bool]:
    raw = receipt_path.read_bytes()
    receipt, had_extra = load_receipt_for_reconstruction(
        raw,
        parser_generation=parser_generation,
    )
    if receipt_path.read_bytes() != raw:
        raise BronzeRecoveryError("receipt bytes must remain immutable")
    temporal = require_temporal(receipt.temporal)
    content_id = temporal.content_id or receipt.payload.sha256
    payload_path = _payload_path_for(bronze_root, content_id)
    if payload_path is None:
        return None, content_id, had_extra
    payload = payload_path.read_bytes()
    if not receipt.payload.matches(payload):
        raise BronzeRecoveryError("payload digest does not match receipt")
    source_id = receipt.source.source_id
    parquet_path = (
        bronze_root
        / PARQUET_DIR
        / source_id
        / temporal.acquisition_id
        / "acquisition_manifest.parquet"
    )
    lineage_path = (
        bronze_root
        / LINEAGE_DIR
        / source_id
        / temporal.acquisition_id
        / "acquisition_manifest.openlineage.json"
    )
    try:
        admission = latest_admission_for_receipt(
            receipt_path=receipt_path,
            receipt=receipt,
        )
    except DownstreamAdmissionError as error:
        admission_dir = (
            bronze_root / "admissions" / source_id / temporal.acquisition_id
        )
        if any(admission_dir.glob("*.json")):
            raise BronzeRecoveryError(str(error)) from error
        outcome = land_bronze_payload(
            payload,
            receipt,
            bronze_root=bronze_root,
            media_hint=payload_path.suffix.lstrip("."),
            admission_decided_at=temporal.retrieved_at,
            transformation_completed_at=temporal.retrieved_at,
        )
        if not isinstance(outcome, BronzeLanding):
            return None, content_id, had_extra
        parquet_path = outcome.parquet_path
        spec = outcome.table
    else:
        try:
            require_admitted_for_processing(admission)
        except DownstreamAdmissionError:
            return None, content_id, had_extra
        spec = write_rebuildable_layers(
            receipt,
            payload,
            payload_path=payload_path,
            parquet_path=parquet_path,
            lineage_path=lineage_path,
            bronze_root=bronze_root,
            admission=admission,
        )
    _write_catalogue(bronze_root, spec)
    _ensure_acquisition_event(bronze_root, receipt, content_id=content_id)
    landing = RecoveredLandingEvidence(
        acquisition_id=temporal.acquisition_id,
        content_id=content_id,
        payload_sha256=receipt.payload.sha256,
        receipt_digest=receipt.digest(),
        parquet_sha256=sha256(parquet_path.read_bytes()).hexdigest(),
        catalogue_identifier=spec.identifier,
    )
    return landing, content_id, had_extra


def _orphan_payloads(
    payload_files: list[Path],
    referenced: set[str],
) -> list[str]:
    return [
        path.parent.name
        for path in payload_files
        if path.parent.name not in referenced
    ]


def _evidence_digest(
    *,
    derivatives_absent: bool,
    scenarios: list[str],
    landings: list[RecoveredLandingEvidence],
    incomplete_count: int,
) -> str:
    unsigned = {
        "schema_id": RECOVERY_SCHEMA_ID,
        "schema_version": 1,
        "hugging_face_is_source_of_truth": False,
        "evidentiary_inputs": ["payload", "receipt"],
        "rebuildable_derivatives_absent": derivatives_absent,
        "scenarios": scenarios,
        "landings": [item.model_dump(mode="json") for item in landings],
        "incomplete_count": incomplete_count,
    }
    return sha256(
        orjson.dumps(unsigned, option=orjson.OPT_SORT_KEYS)
    ).hexdigest()


def reconstruct_bronze(
    bronze_root: Path,
    *,
    fail_closed_on_incomplete: bool = False,
    parser_generation: int = CURRENT_PARSER_GENERATION,
) -> BronzeRecoveryEvidence:
    """Rebuild Parquet, lineage, and catalogue from local evidentiary truth."""

    receipt_files = _receipt_paths(bronze_root)
    payload_files = _payload_paths(bronze_root)
    snapshot = (
        list((bronze_root / PARQUET_DIR).rglob("*.parquet")),
        list((bronze_root / LINEAGE_DIR).rglob("*.json")),
        list((bronze_root / CATALOGUE_DIR).rglob("*.json")),
    )
    referenced: set[str] = set()
    content_counts: dict[str, int] = {}
    incomplete: list[str] = []
    landings: list[RecoveredLandingEvidence] = []
    newer_fields = False
    for receipt_path in receipt_files:
        rebuilt, content_id, had_extra = _rebuild_one(
            bronze_root,
            receipt_path,
            parser_generation=parser_generation,
        )
        newer_fields = newer_fields or had_extra
        referenced.add(content_id)
        content_counts[content_id] = content_counts.get(content_id, 0) + 1
        if rebuilt is None:
            incomplete.append(content_id)
            continue
        landings.append(rebuilt)
    incomplete.extend(_orphan_payloads(payload_files, referenced))
    if incomplete and fail_closed_on_incomplete:
        raise BronzeRecoveryError(
            "incomplete acquisition cannot be reconstructed"
        )
    scenarios = _collect_scenarios(
        parquet_before=snapshot[0],
        lineage_before=snapshot[1],
        catalogue_before=snapshot[2],
        receipt_files=receipt_files,
        payload_files=payload_files,
        derivatives=_derivatives_present(bronze_root),
        content_counts=content_counts,
        newer_fields=newer_fields,
        journal=_read_journal(bronze_root),
        incomplete=incomplete,
    )
    ordered = sorted(scenarios)
    derivatives_absent = not _derivatives_present(bronze_root)
    digest = _evidence_digest(
        derivatives_absent=derivatives_absent,
        scenarios=ordered,
        landings=landings,
        incomplete_count=len(incomplete),
    )
    return BronzeRecoveryEvidence(
        rebuildable_derivatives_absent=derivatives_absent,
        scenarios=tuple(ordered),
        landings=tuple(landings),
        incomplete_count=len(incomplete),
        evidence_digest=digest,
    )


def _collect_scenarios(
    *,
    parquet_before: list[Path],
    lineage_before: list[Path],
    catalogue_before: list[Path],
    receipt_files: list[Path],
    payload_files: list[Path],
    derivatives: bool,
    content_counts: dict[str, int],
    newer_fields: bool,
    journal: list[dict[str, object]],
    incomplete: list[str],
) -> set[str]:
    scenarios: set[str] = set()
    missing_parquet = not parquet_before
    missing_lineage = not lineage_before
    missing_catalogue = not catalogue_before
    if receipt_files and payload_files and missing_parquet:
        scenarios.add(RecoveryScenario.CLEAN_ROOM_REBUILD.value)
        scenarios.add(RecoveryScenario.PARQUET_DELETION.value)
    if missing_catalogue:
        scenarios.add(RecoveryScenario.CATALOGUE_DELETION.value)
    if not derivatives:
        scenarios.add(RecoveryScenario.REBUILDABLE_DATABASE_LOSS.value)
    missing_layers = sum((missing_parquet, missing_lineage, missing_catalogue))
    if missing_layers >= _PARTIAL_LAYER_FLOOR:
        scenarios.add(RecoveryScenario.PARTIAL_STORAGE_LOSS.value)
    if any(count >= _DUPLICATE_COUNT for count in content_counts.values()):
        scenarios.add(RecoveryScenario.DUPLICATE_RETRIEVAL.value)
    if newer_fields:
        scenarios.add(RecoveryScenario.CODE_ROLLBACK_NEWER_PAYLOADS.value)
    if incomplete or any(
        record.get("scenario") == RecoveryScenario.INTERRUPTED_ACQUISITION.value
        for record in journal
    ):
        scenarios.add(RecoveryScenario.INTERRUPTED_ACQUISITION.value)
    return scenarios


def write_recovery_evidence(
    evidence: BronzeRecoveryEvidence,
    destination: Path,
) -> Path:
    """Persist compact reconstruction evidence for independent verification."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(evidence.canonical_json())
    return destination
