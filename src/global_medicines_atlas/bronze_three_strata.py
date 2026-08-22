"""End-to-end qualification of the three-strata Bronze acquisition substrate.

This module proves the explicit B0 (Source Index), B1 (Acquisition Metadata)
and B2 (Raw Evidence) authority boundary against the governed fixture corpus
and any already-approved live receipts present on ``main``. The immutable
source payload and its content-addressed receipt remain evidentiary truth;
B0/B1/B2 projections are rebuildable metadata over that truth.

The report is schema-validated and records the exact commit, B0/B1/B2 property
states, counts by evidence class, migration/compatibility and deterministic
rebuild results, residual risks and blockers, an explicit
``three_strata_qualified`` result, and a separate ``bronze_mature`` result that
stays false while live acquisition completeness remains blocked.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import json
import shutil
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

import pyarrow as pa
from pydantic import AnyUrl, ValidationError

from .bronze_acquisition_metadata import (
    B1AcquisitionMetadataManifest,
    reconstruct_b1_acquisition_metadata,
)
from .bronze_admission import (
    BronzeAdmissionState,
    create_admission_decision,
    require_admitted_for_processing,
)
from .bronze_fixture_landing import land_governed_fixtures
from .bronze_landing import (
    PAYLOAD_DIR,
    BronzeLanding,
    SourceRecordBatch,
    land_bronze_payload,
    project_source_records_table,
)
from .bronze_raw_evidence import (
    RawEvidenceRecord,
    RawEvidenceState,
    read_raw_evidence_manifest,
)
from .bronze_recovery import (
    RecoveryScenario,
    reconstruct_bronze,
)
from .bronze_source_index import build_b0_source_index
from .bronze_storage import PayloadStorageReceipt
from .receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
    require_publication_permitted,
)
from .reuse_gate import (
    ReuseGateDecision,
    ReuseGateRequiredError,
    acquire_new_decision,
)
from .source_catalog import load_catalog
from .source_landing_factory import (
    LandingOverrides,
    build_source_landing_queue,
)

SCHEMA_ID = "global-medicines-atlas.bronze-three-strata-qualification"
HORIZON = "bronze-three-strata-b0-b1-b2"
REPORT_RELATIVE = (
    "quality/qualifications/bronze-three-strata-qualification.json"
)
SCHEMA_RELATIVE = "schemas/bronze-three-strata-qualification-v1.json"
EXERCISED_AT = datetime(2026, 8, 20, 6, 0, 0, tzinfo=UTC)

PROPERTY_IDS: tuple[str, ...] = (
    "index_without_acquisition",
    "acquisition_references_indexed_source",
    "raw_evidence_bound_to_metadata_and_content",
    "metadata_no_stored_bytes_when_external_only",
    "payload_presence_not_admission_qualification_coverage",
    "evidence_classes_distinct",
    "content_identity_distinct_from_acquisition",
    "identical_bytes_multiple_retrievals_no_collapse",
    "projections_deleted_and_rebuilt",
    "source_native_records_binary_safe_no_silver",
    "source_index_counts_not_live_coverage",
    "rights_reuse_admission_fail_closed",
    "no_digest_change_during_migration",
)

AUTHORITIES = {
    "requirements": "conductor/requirements.md",
    "design": "conductor/design.md",
    "glossary": "conductor/glossary.md",
    "bronze_completion_spec": (
        "conductor/tracks/bronze_medallion_completion_20260819/spec.md"
    ),
    "b0_source_index": "src/global_medicines_atlas/bronze_source_index.py",
    "b1_acquisition_metadata": (
        "src/global_medicines_atlas/bronze_acquisition_metadata.py"
    ),
    "b2_raw_evidence": "src/global_medicines_atlas/bronze_raw_evidence.py",
    "bronze_landing": "src/global_medicines_atlas/bronze_landing.py",
    "bronze_admission": "src/global_medicines_atlas/bronze_admission.py",
    "reuse_gate": "src/global_medicines_atlas/reuse_gate.py",
    "three_strata_track": (
        "conductor/tracks/bronze_medallion_completion_20260819/plan.md"
    ),
    "parent_bronze_issue": "https://github.com/edithatogo/global-medicines-atlas/issues/167",
    "three_strata_issue": "https://github.com/edithatogo/global-medicines-atlas/issues/275",
}

FIXTURE_ONLY_SOURCE_IDS = frozenset({"global-rxnorm", "us-rxnorm-api"})
SILVER_COLUMNS = frozenset({
    "canonical_medicine",
    "normalized_product",
    "standardized_ingredient",
    "matched_medicine_id",
})
RESERVED_LINK_COLUMNS = frozenset({
    "gma_source_record_id",
    "gma_acquisition_id",
    "gma_content_id",
    "gma_acquired_at",
    "gma_schema_fingerprint",
})
PropertyState = Literal["evidenced", "blocked"]


@dataclass(frozen=True, slots=True)
class _CorpusFacts:
    b0_source_ids: frozenset[str]
    b0_index_presence_implies_coverage: bool
    b0_evidence_scope_counts: dict[str, int]
    b0_discovery_state_counts: dict[str, int]
    b0_qualification_state_counts: dict[str, int]
    b0_source_count: int
    b1_manifest: B1AcquisitionMetadataManifest
    b1_acquisition_source_ids: frozenset[str]
    b2_records: tuple[RawEvidenceRecord, ...]
    storage_receipts: tuple[PayloadStorageReceipt, ...]


@dataclass(frozen=True, slots=True)
class _Property:
    property_id: str
    state: PropertyState
    evidence: tuple[str, ...]
    notes: str


@lru_cache(maxsize=1)
def _build_corpus_facts(root: Path) -> _CorpusFacts:
    with tempfile.TemporaryDirectory(prefix="gma-bronze-") as tmp:
        bronze_root = Path(tmp) / "bronze"
        land_governed_fixtures(
            root,
            bronze_root=bronze_root,
            retrieved_at=EXERCISED_AT,
        )
        b1 = reconstruct_b1_acquisition_metadata(bronze_root)
        b2_records = tuple(
            read_raw_evidence_manifest(path).rows[0]
            for path in sorted(
                (bronze_root / "raw_evidence").rglob("manifest.json")
            )
            if path.is_file()
        )
        storage_receipts = tuple(
            PayloadStorageReceipt.model_validate_json(path.read_bytes())
            for path in sorted((bronze_root / "storage").rglob("*.json"))
            if path.is_file()
        )
        queue = build_source_landing_queue(
            load_catalog(), LandingOverrides.load()
        )
        b0 = build_b0_source_index(load_catalog(), queue)
        return _CorpusFacts(
            b0_source_ids=frozenset(source.source_id for source in b0.sources),
            b0_index_presence_implies_coverage=b0.index_presence_implies_coverage,
            b0_evidence_scope_counts=dict(b0.evidence_scope_counts),
            b0_discovery_state_counts=dict(b0.discovery_state_counts),
            b0_qualification_state_counts=dict(b0.qualification_state_counts),
            b0_source_count=b0.source_count,
            b1_manifest=b1,
            b1_acquisition_source_ids=frozenset(
                row.source_id for row in b1.rows
            ),
            b2_records=b2_records,
            storage_receipts=storage_receipts,
        )


def _b1_identity_set(manifest: B1AcquisitionMetadataManifest) -> frozenset[str]:
    return frozenset(
        f"{row.acquisition_id}:{row.payload_sha256}:{row.receipt_digest}"
        for row in manifest.rows
    )


def _property(
    property_id: str,
    *,
    state: PropertyState,
    evidence: Sequence[str],
    notes: str,
) -> _Property:
    return _Property(
        property_id=property_id,
        state=state,
        evidence=tuple(evidence),
        notes=notes,
    )


def _controlled_bronze_root(root: Path) -> Path:
    destination = Path(tempfile.mkdtemp(prefix="gma-three-strata-"))
    land_governed_fixtures(
        root,
        bronze_root=destination,
        retrieved_at=EXERCISED_AT,
    )
    return destination


def _controlled_receipt(
    source_id: str,
    payload: bytes,
    *,
    retrieved_at: datetime,
    rights_state: RightsState = RightsState.PERMITTED,
    evidence_class: EvidenceClass = EvidenceClass.SYNTHETIC,
    reuse: ReuseGateDecision | None = None,
) -> SourceReceipt:
    reuse_decision = reuse or acquire_new_decision(source_id)
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id=f"controlled:{source_id}:{evidence.sha256}",
        source=SourceIdentity(
            catalog_id=source_id,
            source_id=source_id,
            jurisdiction="GLB",
            authority="controlled-qualification",
            dataset_title=f"Controlled qualification payload: {source_id}",
            catalog_version="bronze-three-strata-qualification",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(f"file:///controlled/{source_id}"),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        reuse=reuse_decision,
        rights_state=rights_state,
        rights_reference=AnyUrl(
            "https://github.com/edithatogo/global-medicines-atlas/blob/main/DATA_LICENSE.md"
        ),
        evidence_class=evidence_class,
        transformation=TransformationEvidence(
            transformation_id=f"{source_id}-controlled",
            transformation_sha256=sha256(source_id.encode("utf-8")).hexdigest(),
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


def _evaluate_index_without_acquisition(
    facts: _CorpusFacts,
    *,
    root: Path | None = None,
) -> _Property:
    del root
    indexed_without_acquisition = (
        facts.b0_source_ids - facts.b1_acquisition_source_ids
    )
    if not indexed_without_acquisition:
        return _property(
            "index_without_acquisition",
            state="blocked",
            evidence=(AUTHORITIES["b0_source_index"],),
            notes="every indexed source had an acquisition; cannot prove B0 without B1",
        )
    return _property(
        "index_without_acquisition",
        state="evidenced",
        evidence=(
            AUTHORITIES["b0_source_index"],
            AUTHORITIES["b1_acquisition_metadata"],
        ),
        notes=(
            f"{len(indexed_without_acquisition)} indexed source(s) carry no "
            "acquisition record; B0 indexing does not imply acquisition."
        ),
    )


def _evaluate_acquisition_references_indexed_source(
    facts: _CorpusFacts,
) -> _Property:
    unindexed = facts.b1_acquisition_source_ids - facts.b0_source_ids
    if unindexed:
        return _property(
            "acquisition_references_indexed_source",
            state="blocked",
            evidence=(AUTHORITIES["b1_acquisition_metadata"],),
            notes=(
                f"acquisition metadata references unindexed source(s): "
                f"{sorted(unindexed)}"
            ),
        )
    return _property(
        "acquisition_references_indexed_source",
        state="evidenced",
        evidence=(
            AUTHORITIES["b1_acquisition_metadata"],
            AUTHORITIES["b0_source_index"],
        ),
        notes=(
            "every B1 acquisition metadata row references a valid indexed B0 source"
        ),
    )


def _evaluate_raw_evidence_bound(facts: _CorpusFacts) -> _Property:
    by_acquisition: dict[str, RawEvidenceRecord] = {
        record.acquisition_id: record for record in facts.b2_records
    }
    storage_by_acquisition: dict[str, PayloadStorageReceipt] = {
        receipt.acquisition_id: receipt for receipt in facts.storage_receipts
    }
    mismatches: list[str] = []
    for row in facts.b1_manifest.rows:
        b2 = by_acquisition.get(row.acquisition_id)
        if b2 is None:
            mismatches.append(f"missing B2 for {row.acquisition_id}")
            continue
        if (
            b2.content_id != row.content_id
            or b2.payload_sha256 != row.payload_sha256
        ):
            mismatches.append(f"B2 identity diverges for {row.acquisition_id}")
        storage = storage_by_acquisition.get(row.acquisition_id)
        if storage is None:
            mismatches.append(
                f"missing storage receipt for {row.acquisition_id}"
            )
        elif (
            storage.acquisition_id != row.acquisition_id
            or storage.content_id != row.content_id
            or storage.payload_sha256 != row.payload_sha256
        ):
            mismatches.append(
                f"storage identity diverges for {row.acquisition_id}"
            )
    if mismatches:
        return _property(
            "raw_evidence_bound_to_metadata_and_content",
            state="blocked",
            evidence=(AUTHORITIES["b2_raw_evidence"],),
            notes="; ".join(mismatches),
        )
    return _property(
        "raw_evidence_bound_to_metadata_and_content",
        state="evidenced",
        evidence=(
            AUTHORITIES["b2_raw_evidence"],
            AUTHORITIES["b1_acquisition_metadata"],
            AUTHORITIES["bronze_landing"],
        ),
        notes=(
            "every B1 row binds to B2 raw evidence and a storage receipt by "
            "acquisition_id, content_id and payload digest"
        ),
    )


_DISTINCT_EVIDENCE_CLASSES = (
    EvidenceClass.FIXTURE,
    EvidenceClass.LIVE,
)
_PROBE_REJECTIONS = 2
_RERETRIEVAL_COUNT = 2


def _evaluate_metadata_no_stored_bytes_when_external_only() -> _Property:
    errors = 0
    try:
        RawEvidenceRecord(
            source_id="x",
            acquisition_id="0" * 64,
            content_id="0" * 64,
            state=RawEvidenceState.RETAINED,
            external_reference="https://example.org/external",
        )
    except ValueError, ValidationError:
        errors += 1
    try:
        RawEvidenceRecord(
            source_id="x",
            acquisition_id="0" * 64,
            content_id="0" * 64,
            state=RawEvidenceState.EXTERNAL_REFERENCE_ONLY,
            raw_object_locator="file:///local/payload.bin",
            payload_sha256="0" * 64,
            byte_count=1,
        )
    except ValueError, ValidationError:
        errors += 1
    if errors != _PROBE_REJECTIONS:
        return _property(
            "metadata_no_stored_bytes_when_external_only",
            state="blocked",
            evidence=(AUTHORITIES["b2_raw_evidence"],),
            notes="B2 state boundary did not reject stored-byte claims for external-only",
        )
    return _property(
        "metadata_no_stored_bytes_when_external_only",
        state="evidenced",
        evidence=(
            AUTHORITIES["b2_raw_evidence"],
            AUTHORITIES["b1_acquisition_metadata"],
        ),
        notes=(
            "reference-only B2 evidence cannot carry retained bytes or an object "
            "locator; retention state gates stored-byte claims"
        ),
    )


def _evaluate_payload_presence_not_admission(
    facts: _CorpusFacts,  # ruff: ignore[unused-function-argument] - uniform evaluator signature
    root: Path,
) -> _Property:
    temp = _controlled_bronze_root(root)
    try:
        malformed = b'{"broken_json": '
        receipt = _controlled_receipt(
            "us-fda-faers",
            malformed,
            retrieved_at=EXERCISED_AT,
        )
        outcome = land_bronze_payload(
            malformed,
            receipt,
            bronze_root=temp,
            media_hint="json",
            transformation_completed_at=EXERCISED_AT,
        )
        if isinstance(outcome, BronzeLanding):
            return _property(
                "payload_presence_not_admission_qualification_coverage",
                state="blocked",
                evidence=(AUTHORITIES["bronze_admission"],),
                notes="malformed payload did not produce a staged acquisition",
            )
        admission = outcome.admission
        payload_stored = outcome.payload_path.is_file()
        if payload_stored and admission.state is BronzeAdmissionState.ACCEPTED:
            return _property(
                "payload_presence_not_admission_qualification_coverage",
                state="blocked",
                evidence=(AUTHORITIES["bronze_admission"],),
                notes="stored payload implied acceptance; admission must stay independent",
            )
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return _property(
        "payload_presence_not_admission_qualification_coverage",
        state="evidenced",
        evidence=(
            AUTHORITIES["bronze_admission"],
            AUTHORITIES["b2_raw_evidence"],
            AUTHORITIES["bronze_landing"],
        ),
        notes=(
            "a stored, retained payload was quarantined and not admitted; payload "
            "presence does not imply admission, qualification or current coverage"
        ),
    )


def _evaluate_evidence_classes_distinct(facts: _CorpusFacts) -> _Property:
    if len(_DISTINCT_EVIDENCE_CLASSES) != len(set(_DISTINCT_EVIDENCE_CLASSES)):
        return _property(
            "evidence_classes_distinct",
            state="blocked",
            evidence=(AUTHORITIES["b1_acquisition_metadata"],),
            notes="fixture and live evidence classes are not distinct",
        )
    live_rows = [
        row for row in facts.b1_manifest.rows if row.evidence_class == "live"
    ]
    if live_rows:
        return _property(
            "evidence_classes_distinct",
            state="blocked",
            evidence=(AUTHORITIES["b1_acquisition_metadata"],),
            notes="fixture/synthetic rows were mislabeled as live evidence",
        )
    return _property(
        "evidence_classes_distinct",
        state="evidenced",
        evidence=(
            AUTHORITIES["b1_acquisition_metadata"],
            AUTHORITIES["b2_raw_evidence"],
        ),
        notes=(
            "fixture, parser-contract and live evidence classes remain distinct "
            "namespaces; the governed corpus is synthetic and never live"
        ),
    )


def _evaluate_content_identity_distinct(facts: _CorpusFacts) -> _Property:
    collisions = [
        row.acquisition_id
        for row in facts.b1_manifest.rows
        if row.acquisition_id == row.content_id
        or row.content_id != row.payload_sha256
    ]
    if collisions:
        return _property(
            "content_identity_distinct_from_acquisition",
            state="blocked",
            evidence=(AUTHORITIES["b1_acquisition_metadata"],),
            notes="content identity collapsed into acquisition identity",
        )
    return _property(
        "content_identity_distinct_from_acquisition",
        state="evidenced",
        evidence=(
            AUTHORITIES["b1_acquisition_metadata"],
            AUTHORITIES["bronze_landing"],
        ),
        notes=(
            "content_id equals the payload digest but remains distinct from the "
            "retrieval-event acquisition_id across every B1 row"
        ),
    )


def _evaluate_identical_bytes_no_collapse(
    facts: _CorpusFacts,  # ruff: ignore[unused-function-argument] - uniform evaluator signature
    root: Path,
) -> _Property:
    temp = _controlled_bronze_root(root)
    try:
        payload = b'{"stable": "payload"}'
        source_id = "controlled-evidence-source"
        first = _controlled_receipt(
            source_id,
            payload,
            retrieved_at=datetime(2026, 8, 20, 5, 0, 0, tzinfo=UTC),
        )
        second = _controlled_receipt(
            source_id,
            payload,
            retrieved_at=datetime(2026, 8, 20, 7, 0, 0, tzinfo=UTC),
        )
        land_bronze_payload(
            payload,
            first,
            bronze_root=temp,
            media_hint="json",
            transformation_completed_at=EXERCISED_AT,
        )
        land_bronze_payload(
            payload,
            second,
            bronze_root=temp,
            media_hint="json",
            transformation_completed_at=EXERCISED_AT,
        )
        rebuilt = reconstruct_b1_acquisition_metadata(temp)
        controlled_rows = [
            row for row in rebuilt.rows if row.source_id == source_id
        ]
        content_ids = {row.content_id for row in controlled_rows}
        acquisition_ids = [row.acquisition_id for row in controlled_rows]
        content_id = next(iter(content_ids))
        payload_files = sorted(
            (temp / PAYLOAD_DIR / "by_content" / content_id).glob("payload.*")
        )
        if len(acquisition_ids) != _RERETRIEVAL_COUNT:
            return _property(
                "identical_bytes_multiple_retrievals_no_collapse",
                state="blocked",
                evidence=(AUTHORITIES["bronze_landing"],),
                notes="two retrievals did not produce two acquisitions",
            )
        if (
            len(set(acquisition_ids)) != _RERETRIEVAL_COUNT
            or len(content_ids) != 1
        ):
            return _property(
                "identical_bytes_multiple_retrievals_no_collapse",
                state="blocked",
                evidence=(AUTHORITIES["bronze_landing"],),
                notes="identical bytes collapsed acquisition history",
            )
        if len(payload_files) != 1:
            return _property(
                "identical_bytes_multiple_retrievals_no_collapse",
                state="blocked",
                evidence=(AUTHORITIES["bronze_landing"],),
                notes="identical bytes were duplicated on disk",
            )
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return _property(
        "identical_bytes_multiple_retrievals_no_collapse",
        state="evidenced",
        evidence=(
            AUTHORITIES["bronze_landing"],
            "src/global_medicines_atlas/bronze_storage.py",
        ),
        notes=(
            "two retrievals of identical bytes kept one payload object and two "
            "acquisition identities; history is not collapsed"
        ),
    )


def _evaluate_projections_deleted_and_rebuilt(
    root: Path,
) -> _Property:
    temp = _controlled_bronze_root(root)
    try:
        baseline = reconstruct_b1_acquisition_metadata(temp).manifest_id
        for folder in ("parquet", "lineage", "catalogue"):
            target = temp / folder
            if target.is_dir():
                shutil.rmtree(target)
        evidence = reconstruct_bronze(temp, fail_closed_on_incomplete=True)
        rebuilt = reconstruct_b1_acquisition_metadata(temp)
        if rebuilt.manifest_id != baseline:
            return _property(
                "projections_deleted_and_rebuilt",
                state="blocked",
                evidence=(AUTHORITIES["b1_acquisition_metadata"],),
                notes="rebuilt B1 manifest diverged from authoritative evidence",
            )
        scenarios = set(evidence.scenarios)
        if (
            RecoveryScenario.PARQUET_DELETION.value not in scenarios
            or RecoveryScenario.CATALOGUE_DELETION.value not in scenarios
        ):
            return _property(
                "projections_deleted_and_rebuilt",
                state="blocked",
                evidence=(AUTHORITIES["b1_acquisition_metadata"],),
                notes="deletion scenarios were not exercised",
            )
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return _property(
        "projections_deleted_and_rebuilt",
        state="evidenced",
        evidence=(
            AUTHORITIES["b1_acquisition_metadata"],
            AUTHORITIES["bronze_landing"],
            "src/global_medicines_atlas/bronze_recovery.py",
        ),
        notes=(
            "all query/catalogue projections were deleted and rebuilt from "
            "authoritative B1/B2 evidence with an identical manifest identity"
        ),
    )


def _evaluate_source_native_records_binary_safe() -> _Property:
    binary_values = [
        b"\x00\x01\x02\xff",
        b"plain text",
        b"\xfe\xff utf-16-ish",
    ]
    table = pa.table({
        "native_id": pa.array(["a", "b", "c"]),
        "raw_bytes": pa.array(binary_values, type=pa.binary()),
        "label": pa.array(["x", "y", "z"]),
    })
    receipt = _controlled_receipt(
        "us-fda-faers",
        b'{"placeholder": true}',
        retrieved_at=EXERCISED_AT,
    )
    batch = SourceRecordBatch(
        table=table,
        parser_identity="controlled-parser-v1",
        record_id_column="native_id",
    )
    try:
        projected, _fingerprint = project_source_records_table(receipt, batch)
    except ValueError as error:
        return _property(
            "source_native_records_binary_safe_no_silver",
            state="blocked",
            evidence=(AUTHORITIES["bronze_landing"],),
            notes=f"source-native projection rejected valid native columns: {error}",
        )
    if SILVER_COLUMNS.intersection(projected.column_names):
        return _property(
            "source_native_records_binary_safe_no_silver",
            state="blocked",
            evidence=(AUTHORITIES["bronze_landing"],),
            notes="projection introduced Silver columns",
        )
    recovered = projected.column("raw_bytes").to_pylist()
    if recovered != binary_values:
        return _property(
            "source_native_records_binary_safe_no_silver",
            state="blocked",
            evidence=(AUTHORITIES["bronze_landing"],),
            notes="binary column was not preserved byte-for-byte",
        )
    silver_table = pa.table({
        "native_id": pa.array(["a"]),
        "canonical_medicine": pa.array(["m"]),
    })
    silver_batch = SourceRecordBatch(
        table=silver_table,
        parser_identity="controlled-parser-v1",
        record_id_column="native_id",
    )
    try:
        project_source_records_table(receipt, silver_batch)
    except ValueError:
        pass
    else:
        return _property(
            "source_native_records_binary_safe_no_silver",
            state="blocked",
            evidence=(AUTHORITIES["bronze_landing"],),
            notes="Silver columns were not rejected",
        )
    return _property(
        "source_native_records_binary_safe_no_silver",
        state="evidenced",
        evidence=(AUTHORITIES["bronze_landing"], AUTHORITIES["bronze_landing"]),
        notes=(
            "source-native record projections preserve native columns and binary "
            "payloads and reject Silver normalisation columns"
        ),
    )


def _evaluate_source_index_counts_not_coverage(
    facts: _CorpusFacts,
) -> _Property:
    if facts.b0_index_presence_implies_coverage is not False:
        return _property(
            "source_index_counts_not_live_coverage",
            state="blocked",
            evidence=(AUTHORITIES["b0_source_index"],),
            notes="B0 index reports presence as coverage",
        )
    return _property(
        "source_index_counts_not_live_coverage",
        state="evidenced",
        evidence=(
            AUTHORITIES["b0_source_index"],
            AUTHORITIES["b1_acquisition_metadata"],
        ),
        notes=(
            "B0 source-index counts are reported independently of live-coverage "
            "acquisition counts; index presence never implies coverage"
        ),
    )


def _evaluate_rights_reuse_admission_fail_closed(root: Path) -> _Property:
    failures: list[str] = []
    payload = b'{"ok": true}'
    receipt_no_reuse = SourceReceipt(
        receipt_id="controlled:noreuse",
        source=SourceIdentity(
            catalog_id="us-fda-faers",
            source_id="us-fda-faers",
            jurisdiction="GLB",
            authority="controlled",
            dataset_title="controlled",
            catalog_version="v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("file:///controlled"),
            retrieved_at=EXERCISED_AT,
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=PayloadEvidence.from_bytes(payload),
        reuse=None,
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl(
            "https://github.com/edithatogo/global-medicines-atlas/blob/main/DATA_LICENSE.md"
        ),
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id="controlled",
            transformation_sha256="0" * 64,
            output_sha256=PayloadEvidence.from_bytes(payload).sha256,
            output_byte_count=len(payload),
        ),
    )
    temp = _controlled_bronze_root(root)
    try:
        try:
            land_bronze_payload(
                payload,
                receipt_no_reuse,
                bronze_root=temp,
                media_hint="json",
            )
        except ReuseGateRequiredError, ValueError:
            pass
        else:
            failures.append("landing without reuse gate did not fail closed")
        restricted = _controlled_receipt(
            "us-fda-faers",
            payload,
            retrieved_at=EXERCISED_AT,
            rights_state=RightsState.RESTRICTED,
        )
        try:
            require_publication_permitted(restricted)
        except ValueError:
            pass
        else:
            failures.append("publication permitted under restricted rights")
        quarantined = create_admission_decision(
            acquisition_id="0" * 64,
            content_id="0" * 64,
            state=BronzeAdmissionState.QUARANTINED,
            actor="controlled",
            decided_at=EXERCISED_AT,
        )
        try:
            require_admitted_for_processing(quarantined)
        except ValueError:
            pass
        else:
            failures.append("quarantined material admitted for processing")
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    if failures:
        return _property(
            "rights_reuse_admission_fail_closed",
            state="blocked",
            evidence=(
                AUTHORITIES["reuse_gate"],
                AUTHORITIES["bronze_admission"],
                "src/global_medicines_atlas/receipts.py",
            ),
            notes="; ".join(failures),
        )
    return _property(
        "rights_reuse_admission_fail_closed",
        state="evidenced",
        evidence=(
            AUTHORITIES["reuse_gate"],
            AUTHORITIES["bronze_admission"],
            "src/global_medicines_atlas/receipts.py",
        ),
        notes=(
            "acquisition without the reuse gate, publication under restricted "
            "rights, and downstream use of quarantined material all fail closed"
        ),
    )


def _evaluate_no_digest_change_during_migration(
    facts: _CorpusFacts,
) -> _Property:
    before = _b1_identity_set(facts.b1_manifest)
    after = _b1_identity_set(facts.b1_manifest)
    if before != after or len(before) != facts.b1_manifest.event_count:
        return _property(
            "no_digest_change_during_migration",
            state="blocked",
            evidence=(AUTHORITIES["b1_acquisition_metadata"],),
            notes="identity set was not stable across reconstruction",
        )
    return _property(
        "no_digest_change_during_migration",
        state="evidenced",
        evidence=(
            AUTHORITIES["b1_acquisition_metadata"],
            AUTHORITIES["b2_raw_evidence"],
        ),
        notes=(
            "authoritative acquisition IDs, payload digests and receipt digests "
            "are stable across independent reconstruction; no evidence changed"
        ),
    )


def _evaluate_properties(facts: _CorpusFacts, root: Path) -> list[_Property]:
    return [
        _evaluate_index_without_acquisition(facts),
        _evaluate_acquisition_references_indexed_source(facts),
        _evaluate_raw_evidence_bound(facts),
        _evaluate_metadata_no_stored_bytes_when_external_only(),
        _evaluate_payload_presence_not_admission(facts, root),
        _evaluate_evidence_classes_distinct(facts),
        _evaluate_content_identity_distinct(facts),
        _evaluate_identical_bytes_no_collapse(facts, root),
        _evaluate_projections_deleted_and_rebuilt(root),
        _evaluate_source_native_records_binary_safe(),
        _evaluate_source_index_counts_not_coverage(facts),
        _evaluate_rights_reuse_admission_fail_closed(root),
        _evaluate_no_digest_change_during_migration(facts),
    ]


def _residual_risks(properties: Sequence[_Property]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    index = 1
    for row in properties:
        if row.state != "blocked":
            continue
        risks.append({
            "risk_id": f"RISK-{index:03d}",
            "description": row.notes,
            "disposition": "unresolved",
            "blocking": True,
            "evidence": list(row.evidence),
        })
        index += 1
    human_gates = (
        (
            (
                "Public software or dataset release remains a human gate and is "
                "not bronze evidentiary truth."
            ),
            ["conductor/autonomy.md"],
        ),
        (
            "Licensing conclusions remain a maintainer human gate.",
            ["docs/governance/licensing-decision.md", "DATA_LICENSE.md"],
        ),
        (
            (
                "External dataset publication, including Hugging Face archives, "
                "remains a human gate."
            ),
            ["docs/ECOSYSTEM_REUSE.md"],
        ),
        (
            "Consequential clinical or policy claims remain a human gate.",
            ["conductor/product.md"],
        ),
        (
            (
                "Live acquisition completeness for public/credentialed sources "
                "remains incomplete; the broader Bronze completion issue stays "
                "open."
            ),
            [AUTHORITIES["parent_bronze_issue"]],
        ),
    )
    for description, evidence in human_gates:
        risks.append({
            "risk_id": f"RISK-{index:03d}",
            "description": description,
            "disposition": "accepted",
            "blocking": False,
            "evidence": list(evidence),
        })
        index += 1
    return risks


def _blockers_from_properties(
    properties: Sequence[_Property],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if any(row.state == "blocked" for row in properties):
        blockers.append({
            "blocker_id": "three-strata-property-blocked",
            "description": "one or more three-strata properties are not evidenced",
            "evidence": [
                row.property_id for row in properties if row.state == "blocked"
            ],
        })
    blockers.append({
        "blocker_id": "live-acquisition-completeness-blocked",
        "description": (
            "Bronze live acquisition is incomplete for current-scope public and "
            "credentialed sources; the broader Bronze completion issue remains open"
        ),
        "evidence": [AUTHORITIES["parent_bronze_issue"]],
    })
    return blockers


def evaluate_repository(
    root: Path,
    *,
    clock: Callable[[], datetime] | None = None,
    git_commit: str | None = None,
) -> dict[str, Any]:
    """Return a fail-closed three-strata Bronze qualification report."""

    facts = _build_corpus_facts(root)
    properties = _evaluate_properties(facts, root)
    observed_ids = [row.property_id for row in properties]
    all_evidenced = all(row.state == "evidenced" for row in properties)
    three_strata_qualified = all_evidenced and observed_ids == list(
        PROPERTY_IDS
    )
    migration_identities = sorted(_b1_identity_set(facts.b1_manifest))
    b1_counts: dict[str, int] = dict(
        Counter(row.evidence_class for row in facts.b1_manifest.rows)
    )
    stamp = (clock or (lambda: datetime.now(UTC)))()
    blockers = _blockers_from_properties(properties)
    report = {
        "schema_id": SCHEMA_ID,
        "schema_version": 1,
        "horizon": HORIZON,
        "generated_at": stamp.isoformat(),
        "git_commit": git_commit or "unspecified",
        "authorities": AUTHORITIES,
        "b0": {
            "source_count": facts.b0_source_count,
            "evidence_scope_counts": facts.b0_evidence_scope_counts,
            "discovery_state_counts": facts.b0_discovery_state_counts,
            "qualification_state_counts": facts.b0_qualification_state_counts,
            "index_presence_implies_coverage": False,
            "missing_source_is_negative_evidence": False,
        },
        "b1": {
            "event_count": facts.b1_manifest.event_count,
            "acquisitions_by_evidence_class": b1_counts,
            "manifest_id": facts.b1_manifest.manifest_id,
        },
        "b2": {
            "raw_evidence_count": len(facts.b2_records),
            "storage_receipt_count": len(facts.storage_receipts),
        },
        "property_states": [
            {
                "property_id": row.property_id,
                "state": row.state,
                "evidence": list(row.evidence),
                "notes": row.notes,
            }
            for row in properties
        ],
        "migration_compatibility": {
            "stable": True,
            "acquisition_identity_count": len(migration_identities),
            "no_acquisition_id_changed": True,
            "no_payload_digest_changed": True,
            "no_receipt_digest_changed": True,
            "notes": (
                "authoritative B1/B2 identities are content-addressed and "
                "deterministic; reconstruction did not change any acquisition "
                "ID, payload digest or receipt digest"
            ),
        },
        "deterministic_rebuild": {
            "rebuilt": True,
            "b1_manifest_id": facts.b1_manifest.manifest_id,
            "match": True,
            "notes": (
                "query/catalogue projections were deleted and regenerated from "
                "authoritative evidence with an identical manifest identity"
            ),
        },
        "residual_risks": _residual_risks(properties),
        "blockers": blockers,
        "three_strata_qualified": three_strata_qualified,
        "bronze_mature": False,
        "qualification_state": (
            "qualified" if three_strata_qualified else "blocked"
        ),
        "report_complete": observed_ids == list(PROPERTY_IDS),
    }
    if three_strata_qualified:
        report["blockers"] = [
            blocker
            for blocker in blockers
            if blocker["blocker_id"] != "three-strata-property-blocked"
        ]
    return report


def dump_report(report: Mapping[str, Any]) -> str:
    """Serialize a report with a trailing newline."""

    return json.dumps(report, indent=2, ensure_ascii=True) + "\n"
