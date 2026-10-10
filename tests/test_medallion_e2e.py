"""Synthetic proof that Bronze, Silver, Gold and Platinum compose."""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Never, Protocol, cast

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient
from test_pbs_silver import XML as PBS_XML
from test_support.federation import admission_record
from typer.testing import CliRunner

from global_medicines_atlas import atlas as atlas_module
from global_medicines_atlas import platinum_configuration
from global_medicines_atlas.api import create_app
from global_medicines_atlas.atlas import AtlasQueryService, create_atlas_app
from global_medicines_atlas.bronze_admission import BronzeAdmissionState
from global_medicines_atlas.bronze_landing import (
    BronzeLanding,
    land_bronze_payload,
)
from global_medicines_atlas.bronze_storage import (
    LocalFilesystemPayloadStore,
    PayloadStore,
    StoredObjectEvidence,
    StoredPayload,
)
from global_medicines_atlas.cli import app as cli_app
from global_medicines_atlas.federation_distribution import (
    DistributionBinding,
    ProducedObject,
    load_synthetic_producer_inventory,
    reconcile_distribution,
)
from global_medicines_atlas.federation_reader import FederatedReader
from global_medicines_atlas.frontier_attestation import (
    build_verification_cost_receipt,
    canonical_verification_cost_bytes,
    verify_verification_cost_receipt,
)
from global_medicines_atlas.frontier_merkle import (
    MerkleLeaf,
    build_merkle_manifest,
    canonical_merkle_manifest_bytes,
    verify_merkle_manifest,
)
from global_medicines_atlas.gold_edge_review import (
    build_gold_edge_review_queue,
    regenerate_gold_edge_review_queue,
)
from global_medicines_atlas.historical_change import (
    HistoricalChange,
    HistoricalChangeService,
    compare_historical_snapshots,
)
from global_medicines_atlas.historical_comparison import (
    NativeField,
    NativeRow,
    NativeSnapshot,
)
from global_medicines_atlas.matching_models import (
    AdjudicationEvent,
    ReviewState,
)
from global_medicines_atlas.mbs_gold_graph import (
    MbsGoldEdge,
    build_mbs_gold_graph_candidate,
    project_mbs_gold_graph_arrow,
)
from global_medicines_atlas.mbs_silver import iter_mbs_silver_batches
from global_medicines_atlas.pbs_gold_graph import (
    PbsGoldEdge,
    build_pbs_gold_graph_candidate,
    project_pbs_gold_graph_arrow,
)
from global_medicines_atlas.pbs_silver import iter_pbs_silver_batches
from global_medicines_atlas.platinum_benefits import BenefitsService
from global_medicines_atlas.platinum_identity_service import (
    ResolverDatasetIdentityService,
)
from global_medicines_atlas.platinum_query import (
    PlatinumQueryService,
    QueryResult,
    QuerySpec,
    QueryUnavailable,
)
from global_medicines_atlas.platinum_resolver import (
    ProductResource,
    StorageNeutralResolver,
)
from global_medicines_atlas.platinum_structure import SourceStructureService
from global_medicines_atlas.platinum_types import (
    PlatinumSemanticDimension,
)
from global_medicines_atlas.platinum_v2_api import create_v2_app
from global_medicines_atlas.platinum_v2_contracts import (
    V2ComparisonQuery,
    V2EvidenceQuery,
)
from global_medicines_atlas.query_service import ReadOnlyQueryService
from global_medicines_atlas.receipts import (
    AcquisitionMethod,
    AcquisitionStatus,
    EvidenceClass,
    PayloadEvidence,
    RetrievalEvidence,
    RightsState,
    SourceIdentity,
    SourceReceipt,
    TransformationEvidence,
    require_temporal,
    temporal_identity_from_source,
)
from global_medicines_atlas.research_export_package import (
    build_research_export_package,
    verify_research_export_package,
)
from global_medicines_atlas.research_exports import (
    ExportSource,
    build_query_snapshot_manifest,
    canonical_result_bytes,
    manifest_sha256,
)
from global_medicines_atlas.research_lineage import (
    ResearchLineageArtifact,
    build_research_lineage_receipt,
)
from global_medicines_atlas.research_package import (
    CrateDistribution,
    build_research_crate,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision
from global_medicines_atlas.review_queue import (
    append_adjudication,
    load_adjudications,
)

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 6, tzinfo=UTC)
SOURCE_ID = "au-mbs"
GOLD_REVIEW_QUEUED_AT = datetime(2026, 10, 6, tzinfo=UTC)
type SyntheticOutput = tuple[
    Literal["bronze", "silver", "gold", "platinum"],
    str,
    bytes,
    Literal["B0", "B1", "B2"] | None,
]


def _exercise_benefits_cli(
    resolver: StorageNeutralResolver,
    resource_id: str,
    columns: tuple[str, ...],
    api_page: dict[str, Any],
    test_context: tuple[pytest.MonkeyPatch, Path],
) -> None:
    monkeypatch, tmp_path = test_context
    cursor_key = "".join(("fixture-only-", "cursor-signing-", "key-32-bytes"))
    monkeypatch.setattr(
        platinum_configuration,
        "load_benefits_resolver",
        lambda **_kwargs: resolver,
    )
    monkeypatch.setenv("GMA_CURSOR_SECRET", cursor_key)
    trust_file = tmp_path / "synthetic-trust.json"
    trust_file.write_text("{}", encoding="utf-8")
    metadata_root = tmp_path / "synthetic-metadata"
    metadata_root.mkdir(exist_ok=True)
    schema_file = tmp_path / "federation.schema.json"
    schema_file.write_bytes(
        (ROOT / "contracts/medallion/v4/federation.schema.json").read_bytes()
    )
    arguments = [
        "benefits",
        resource_id,
        "--trust-file",
        str(trust_file),
        "--metadata-root",
        str(metadata_root),
        "--schema-file",
        str(schema_file),
        *(item for column in columns for item in ("--column", column)),
        "--limit",
        "1",
    ]
    result = CliRunner().invoke(cli_app, arguments)
    assert result.exit_code == 0, result.output
    cli_page = json.loads(result.stdout)
    for key in (
        "rows",
        "identity",
        "page_sha256",
        "window_sha256",
        "coverage_state",
        "comparison_validity",
    ):
        assert cli_page[key] == api_page[key]


def _exercise_source_structure_cli(
    resolver: StorageNeutralResolver,
    resource_id: str,
    columns: tuple[str, ...],
    expected: QueryResult,
    test_context: tuple[pytest.MonkeyPatch, Path],
) -> None:
    """Read the verified synthetic structure through the installed CLI."""
    monkeypatch, tmp_path = test_context
    monkeypatch.setattr(
        platinum_configuration,
        "load_benefits_resolver",
        lambda **_kwargs: resolver,
    )
    trust_file = tmp_path / "synthetic-structure-trust.json"
    trust_file.write_text("{}", encoding="utf-8")
    metadata_root = tmp_path / "synthetic-structure-metadata"
    metadata_root.mkdir(exist_ok=True)
    schema_file = tmp_path / "federation.schema.json"
    schema_file.write_bytes(
        (ROOT / "contracts/medallion/v4/federation.schema.json").read_bytes()
    )
    arguments = [
        "source-structure",
        resource_id,
        "--trust-file",
        str(trust_file),
        "--metadata-root",
        str(metadata_root),
        "--schema-file",
        str(schema_file),
        *(item for column in columns for item in ("--column", column)),
        "--limit",
        "1",
        "--offline",
    ]
    result = CliRunner().invoke(cli_app, arguments)
    assert result.exit_code == 0, result.output
    cli_page = json.loads(result.stdout)
    assert cli_page["status"] == "available"
    assert cli_page["rows"] == list(expected.rows)
    assert cli_page["identity"]["resource_id"] == resource_id
    assert cli_page["identity"]["revision"] == expected.evidence.revision
    assert cli_page["identity"]["path"] == expected.evidence.path
    assert (
        cli_page["identity"]["object_sha256"] == expected.evidence.object_sha256
    )
    assert cli_page["identity"]["semantic_dimension"] == "source_structure"
    assert cli_page["query_sha256"] == expected.query_receipt.query_sha256
    receipt = json.loads(cli_page["query_receipt_json"])
    assert cli_page["query_receipt_sha256"] == receipt["receipt_sha256"]
    assert receipt["query_sha256"] == expected.query_receipt.query_sha256
    assert receipt["result_sha256"] == expected.result_sha256
    assert receipt["cache_receipt_sha256"]


def _exercise_gold_edge_surfaces(
    edges: pa.Table,
    *,
    edge_file: Path,
) -> None:
    """Compare the synthetic Gold edge API and CLI readbacks."""
    client = TestClient(
        create_app(
            cast("ReadOnlyQueryService", object()),
            gold_edges=edges,
        )
    )
    response = client.get("/api/v1/edges", params={"limit": "10"})
    assert response.status_code == 200, response.text
    api_page = response.json()

    cli_result = CliRunner().invoke(
        cli_app,
        ["edges", "--edge-file", str(edge_file), "--limit", "10"],
    )
    assert cli_result.exit_code == 0, cli_result.output
    cli_page = json.loads(cli_result.stdout)
    assert cli_page == api_page
    assert api_page["qualification"] == "synthetic_silver_candidate_only"
    assert api_page["total"] == edges.num_rows
    assert all(
        item["evidence"]["source_id"] == "au-mbs" for item in api_page["items"]
    )


def _exercise_gold_review_queue(
    edges: pa.Table,
    *,
    expected_edges: Iterable[MbsGoldEdge | PbsGoldEdge],
    adjudication_path: Path,
) -> None:
    """Rebuild review cases from portable Gold projection without promotion."""
    edge_file = adjudication_path.with_suffix(".parquet")
    pq.write_table(edges, edge_file)
    projected_edges = []
    for row in edges.to_pylist():
        edge = {
            key: value
            for key, value in row.items()
            if key not in {"evidence_json", "controls_json"}
        }
        edge["evidence"] = json.loads(row["evidence_json"])
        edge.update(json.loads(row["controls_json"]))
        projected_edges.append(edge)
    expected_review_cases = build_gold_edge_review_queue(
        expected_edges,
        queued_at=GOLD_REVIEW_QUEUED_AT,
    )
    review_cases = build_gold_edge_review_queue(
        projected_edges,
        queued_at=GOLD_REVIEW_QUEUED_AT,
    )
    assert len(review_cases) == edges.num_rows
    assert {case.edge_id for case in review_cases} == set(
        edges.column("edge_id").to_pylist()
    )
    assert {case.edge_id: case.edge_sha256 for case in review_cases} == {
        case.edge_id: case.edge_sha256 for case in expected_review_cases
    }
    assert all(
        case.review_state.value == "pending_review" for case in review_cases
    )
    assert all(case.promotion_performed is False for case in review_cases)
    cli_payload = _invoke_gold_review_cli(edge_file)
    assert cli_payload["cases"] == [
        case.model_dump(mode="json") for case in review_cases
    ]
    assert cli_payload["promotion_performed"] is False
    case = review_cases[0]
    first = _gold_adjudication(
        candidate_id=case.review_case_id,
        state=ReviewState.NEEDS_INFORMATION,
        occurred_at=GOLD_REVIEW_QUEUED_AT + timedelta(seconds=1),
        rationale="Synthetic E2E fixture requests more evidence.",
    )
    append_adjudication(adjudication_path, first)
    events = load_adjudications(adjudication_path)
    assert events == (first,)
    assert (
        regenerate_gold_edge_review_queue(review_cases, events) == review_cases
    )
    assert _invoke_gold_review_cli(edge_file, adjudication_path)["cases"] == [
        case.model_dump(mode="json") for case in review_cases
    ]

    terminal = _gold_adjudication(
        candidate_id=case.review_case_id,
        state=ReviewState.ACCEPTED,
        occurred_at=GOLD_REVIEW_QUEUED_AT + timedelta(seconds=2),
        rationale="Synthetic E2E fixture supplies a terminal review event.",
        supersedes_event_id=first.event_id,
    )
    append_adjudication(adjudication_path, terminal)
    events = load_adjudications(adjudication_path)
    assert events == (first, terminal)
    remaining_cases = regenerate_gold_edge_review_queue(review_cases, events)
    assert {item.review_case_id for item in remaining_cases} == {
        item.review_case_id
        for item in review_cases
        if item.review_case_id != case.review_case_id
    }
    assert all(item.promotion_performed is False for item in remaining_cases)
    assert _invoke_gold_review_cli(
        edge_file,
        adjudication_path,
    )["cases"] == [item.model_dump(mode="json") for item in remaining_cases]
    assert case.promotion_performed is False


def _invoke_gold_review_cli(
    edge_file: Path,
    adjudication_file: Path | None = None,
) -> dict[str, Any]:
    args = [
        "gold-review-queue",
        "--edge-file",
        str(edge_file),
        "--queued-at",
        GOLD_REVIEW_QUEUED_AT.isoformat(),
    ]
    if adjudication_file is not None:
        args.extend(("--adjudications-file", str(adjudication_file)))
    result = CliRunner().invoke(cli_app, args)
    assert result.exit_code == 0, result.stderr
    return json.loads(result.stdout)


def _gold_adjudication(
    *,
    candidate_id: str,
    state: ReviewState,
    occurred_at: datetime,
    rationale: str,
    supersedes_event_id: str | None = None,
) -> AdjudicationEvent:
    reviewer_id = "synthetic-e2e-reviewer"
    event_id = AdjudicationEvent.content_id(
        candidate_id=candidate_id,
        state=state,
        occurred_at=occurred_at,
        reviewer_id=reviewer_id,
        rationale=rationale,
        supersedes_event_id=supersedes_event_id,
    )
    return AdjudicationEvent(
        event_id=event_id,
        candidate_id=candidate_id,
        state=state,
        occurred_at=occurred_at,
        reviewer_id=reviewer_id,
        rationale=rationale,
        supersedes_event_id=supersedes_event_id,
    )


def _exercise_historical_surfaces(
    previous_payload: bytes,
    previous: SourceReceipt,
    current_payload: bytes,
    current: SourceReceipt,
    *,
    history_file: Path,
    bronze_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compare API and CLI history pages derived from synthetic Bronze XML."""
    previous_landed = land_bronze_payload(
        previous_payload,
        previous,
        bronze_root=bronze_root / "previous",
        media_hint="xml",
        admission_decided_at=previous.retrieval.retrieved_at,
        transformation_completed_at=previous.retrieval.retrieved_at,
    )
    current_landed = land_bronze_payload(
        current_payload,
        current,
        bronze_root=bronze_root / "current",
        media_hint="xml",
        admission_decided_at=current.retrieval.retrieved_at,
        transformation_completed_at=current.retrieval.retrieved_at,
    )

    def snapshot(
        payload_path: Path,
        receipt: SourceReceipt,
    ) -> NativeSnapshot:
        temporal = require_temporal(receipt.temporal)
        parsed = [
            row
            for batch in iter_mbs_silver_batches(
                payload_path.read_bytes(), receipt, table="descriptions"
            )
            for row in batch.to_pylist()
        ]
        native_rows = []
        for row in parsed:
            description = row["Description"]
            state = (
                "missing"
                if description["native_state"] == "missing_field"
                else "null"
                if description["native_state"] == "null"
                else "value"
            )
            native_rows.append(
                NativeRow(
                    native_id=row["source_record_id"],
                    occurrence_id=str(row["source_ordinal"]),
                    fields=(
                        NativeField(
                            name="Description",
                            state=state,
                            value=(
                                description["native_value"]
                                if state == "value"
                                else None
                            ),
                        ),
                    ),
                )
            )
        return NativeSnapshot(
            source_id=receipt.source.source_id,
            table="descriptions",
            dimension="service_benefit",
            schema_era="synthetic-e2e-v1",
            identity_profile="mbs-description-record",
            scope_id="synthetic-bronze-payload",
            source_revision=temporal.acquisition_id,
            source_path="bronze/raw.xml",
            b1_sha256=receipt.digest(),
            b2_sha256=receipt.payload.sha256,
            observed_at=receipt.retrieval.retrieved_at,
            cohort="synthetic",
            declared_rows=len(native_rows),
            complete=True,
            rows=tuple(native_rows),
        )

    change = compare_historical_snapshots(
        snapshot(previous_landed.payload_path, previous),
        snapshot(current_landed.payload_path, current),
    )
    service = HistoricalChangeService((change,))
    history_file.write_text(
        json.dumps({
            "version": "1.0",
            "changes": [change.model_dump(mode="json")],
        }),
        encoding="utf-8",
    )
    api_response = TestClient(
        create_app(
            cast("ReadOnlyQueryService", object()),
            historical_changes=service,
        )
    ).get("/api/v1/history", params={"offset": "0", "limit": "10"})
    assert api_response.status_code == 200, api_response.text
    api_page = api_response.json()

    cli_result = CliRunner().invoke(
        cli_app,
        ["history", "--history-file", str(history_file), "--limit", "10"],
    )
    assert cli_result.exit_code == 0, cli_result.output
    assert json.loads(cli_result.stdout) == api_page
    item = api_page["items"][0]
    assert item["comparison_state"] == "compared"
    assert item["availability"] == "both_present"
    assert item["absence_interpretation"] == "unknown"
    assert {change["kind"] for change in item["changes"]} == {
        "field_changed",
        "removed_observation",
    }
    removed = next(
        change
        for change in item["changes"]
        if change["kind"] == "removed_observation"
    )
    assert removed["interpretation"] == "observed_change"
    assert removed["native_id"] == "au-mbs:00567:00::1"

    _exercise_atlas_history(
        service,
        change,
        previous.digest(),
        current.digest(),
        monkeypatch=monkeypatch,
    )


def _exercise_atlas_history(
    service: HistoricalChangeService,
    change: HistoricalChange,
    previous_digest: str,
    current_digest: str,
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    atlas_client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()), historical_changes=service
        )
    )
    assert (
        'href="/history">Review historical changes'
        in atlas_client.get("/").text
    )
    atlas_response = atlas_client.get(
        "/history", params={"offset": "0", "limit": "10"}
    )
    assert atlas_response.status_code == 200
    assert atlas_response.headers["cache-control"] == "no-store"
    assert "Historical changes" in atlas_response.text
    assert "absence interpretation: unknown" in atlas_response.text
    assert "au-mbs:00567:00::1" in atlas_response.text
    assert previous_digest in atlas_response.text
    assert current_digest in atlas_response.text
    assert "bronze/raw.xml" in atlas_response.text
    assert "prior synthetic service" in atlas_response.text
    assert "fixture service" in atlas_response.text
    incompatible = compare_historical_snapshots(
        change.left,
        change.right.model_copy(update={"source_id": "later-source"}),
    )
    identity_response = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            historical_changes=HistoricalChangeService((incompatible,)),
        )
    ).get("/history")
    assert identity_response.status_code == 200
    assert SOURCE_ID in identity_response.text
    assert "later-source" in identity_response.text
    unattributed = HistoricalChangeService((
        compare_historical_snapshots(None, change.right),
    ))
    unavailable = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()), historical_changes=unattributed
        )
    ).get("/history")
    assert unavailable.status_code == 503
    assert "lack attributable source metadata" in unavailable.text

    class InvalidHistoryService:
        def page(self, *, offset: int = 0, limit: int = 100) -> object:
            del offset, limit
            raise ValueError("synthetic invalid history page")

    invalid_client = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            historical_changes=cast(
                "HistoricalChangeService", InvalidHistoryService()
            ),
        )
    )
    invalid = invalid_client.get("/history")
    assert invalid.status_code == 422
    assert "historical change page is invalid" in invalid.text

    monkeypatch.setattr(atlas_module, "_MAX_HISTORY_PAGE_BYTES", 1)
    oversized = atlas_client.get("/history")
    assert oversized.status_code == 503
    assert "response byte limit" in oversized.text


def _payload() -> bytes:
    return (
        b"<MBS_XML><Data><ItemNum>00123</ItemNum>"
        b"<SubItemNum>00</SubItemNum><Description>fixture service</Description>"
        b"</Data></MBS_XML>"
    )


def _receipt(
    payload: bytes,
    *,
    source_id: str = SOURCE_ID,
    retrieved_at: datetime = NOW,
) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    receipt = SourceReceipt(
        receipt_id="synthetic:medallion-e2e",
        source=SourceIdentity(
            catalog_id=source_id,
            source_id=source_id,
            jurisdiction="AUS",
            authority="Repository-owned synthetic fixture",
            dataset_title=f"Synthetic {source_id} E2E fixture",
            catalog_version="synthetic-e2e-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=f"https://fixtures.invalid/{source_id}.xml",
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id="synthetic-identity",
            transformation_sha256="a" * 64,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )
    return receipt.model_copy(
        update={
            "reuse": acquire_new_decision(source_id),
            "temporal": temporal_identity_from_source(
                retrieved_at=retrieved_at,
                source_id=source_id,
                payload_sha256=evidence.sha256,
                source_version="synthetic-e2e-v1",
            ),
        }
    )


class _SyntheticRemoteLocatorPayloadStore(PayloadStore):
    """Use temp bytes with a portable, explicitly fake B2 locator."""

    def __init__(self, root: Path) -> None:
        self._local = LocalFilesystemPayloadStore(root)
        self.policy = self._local.policy

    def store(
        self,
        payload: bytes,
        *,
        acquisition_id: str,
        content_id: str,
        suffix: str,
    ) -> StoredPayload:
        stored = self._local.store(
            payload,
            acquisition_id=acquisition_id,
            content_id=content_id,
            suffix=suffix,
        )
        primary = stored.receipt.primary.model_copy(
            update={
                "uri": (
                    "https://fixtures.invalid/bronze/"
                    f"{content_id}/payload{suffix}"
                )
            }
        )
        return StoredPayload(
            materialized_path=stored.materialized_path,
            receipt=stored.receipt.model_copy(update={"primary": primary}),
        )

    def read_object(self, reference: StoredObjectEvidence) -> bytes:
        return (self._local.root / reference.key).read_bytes()


def _assert_landed_b1_projection(
    landing: BronzeLanding,
    *,
    payload: bytes,
) -> bytes:
    """Bind a portable B1 projection to local B2 without embedding B2 bytes."""
    parquet = landing.parquet_path.read_bytes()
    table = pq.read_table(io.BytesIO(parquet))
    assert table.num_rows == 1
    assert (
        table.column("source_id").to_pylist()[0]
        == landing.receipt.source.source_id
    )
    assert (
        table.column("acquisition_id").to_pylist()[0]
        == require_temporal(landing.receipt.temporal).acquisition_id
    )
    assert (
        table.column("payload_sha256").to_pylist()[0]
        == hashlib.sha256(payload).hexdigest()
    )
    assert (
        table.column("receipt_digest").to_pylist()[0]
        == landing.receipt.digest()
    )
    assert table.column("evidence_class").to_pylist()[0] == "synthetic"
    assert table.column("rights_state").to_pylist()[0] == "unknown"
    locator = table.column("raw_evidence_locator").to_pylist()[0]
    assert locator == (
        "https://fixtures.invalid/bronze/"
        f"{hashlib.sha256(payload).hexdigest()}/payload.xml"
    )
    workstation_path = str(landing.payload_path).encode()
    decoded_values = [
        value
        for row in table.to_pylist()
        for value in row.values()
        if value is not None
    ]
    metadata_values = [
        value
        for metadata in (
            table.schema.metadata,
            pq.read_metadata(io.BytesIO(parquet)).metadata,
        )
        if metadata
        for pair in metadata.items()
        for value in pair
    ]
    for value in (*decoded_values, *metadata_values):
        encoded = value if isinstance(value, bytes) else str(value).encode()
        assert workstation_path not in encoded
        assert payload not in encoded
    return parquet


def _assert_projection_rejects_embedded_b2(
    landing: BronzeLanding,
    *,
    payload: bytes,
    tmp_path: Path,
) -> None:
    """Prove decoded Parquet and metadata leak checks reject B2 sentinels."""
    table = pq.read_table(landing.parquet_path)
    path_sentinel = str(landing.payload_path)
    for name, value in (("path", path_sentinel), ("payload", payload)):
        leaked_table = table.append_column(f"leaked_{name}", pa.array([value]))
        leaked_path = tmp_path / f"leaked-{name}.parquet"
        pq.write_table(leaked_table, leaked_path)
        with pytest.raises(AssertionError):
            _assert_landed_b1_projection(
                replace(landing, acquisition_manifest_path=leaked_path),
                payload=payload,
            )

    for name, sentinel in (
        ("path", path_sentinel.encode()),
        ("payload", payload),
    ):
        metadata = dict(table.schema.metadata or {})
        metadata[f"leaked_{name}".encode()] = sentinel
        leaked_table = table.replace_schema_metadata(metadata)
        leaked_path = tmp_path / f"leaked-metadata-{name}.parquet"
        pq.write_table(leaked_table, leaked_path)
        with pytest.raises(AssertionError):
            _assert_landed_b1_projection(
                replace(landing, acquisition_manifest_path=leaked_path),
                payload=payload,
            )


def _platinum_contract(payload: bytes, receipt: SourceReceipt) -> bytes:
    document = json.loads(
        (ROOT / "contracts/medallion/v4/fixtures/valid.json").read_bytes()
    )
    digest = hashlib.sha256(payload).hexdigest()
    document["source"].update(
        source_id=receipt.source.source_id,
        acquisition_id=require_temporal(receipt.temporal).acquisition_id,
        layer="platinum",
        bronze_stratum=None,
        representation="projection",
        schema_era="synthetic-e2e-v1",
        comparison_cohort="synthetic",
        effective_date=None,
        retrieved_at=NOW.isoformat().replace("+00:00", "Z"),
    )
    document["location"].update(
        path=f"platinum/synthetic-{receipt.source.source_id}-edges.parquet",
        bytes=len(payload),
        sha256=digest,
    )
    document["verification"].update(
        path=document["location"]["path"],
        bytes=len(payload),
        sha256=digest,
        verified_at=NOW.isoformat().replace("+00:00", "Z"),
    )
    document["rights"].update(
        subject_sha256=digest,
        path=document["location"]["path"],
        basis="Synthetic test fixture only; no real publication authority",
    )
    document["lineage"]["inputs"] = [
        {
            "url": "https://fixtures.invalid/receipts/source.json",
            "sha256": receipt.digest(),
        }
    ]
    document["lineage"]["promotion_receipt"] = document["verification"][
        "receipt"
    ]
    document["cache"]["offline_behavior"] = "verified_exact_digest_only"
    document["cache"]["expires_at"] = (
        (NOW + timedelta(days=1)).isoformat().replace("+00:00", "Z")
    )
    document["cache"]["max_bytes"] = max(
        document["cache"]["max_bytes"], len(payload)
    )
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def _distribution_contract(
    payload: bytes,
    receipt: SourceReceipt,
    *,
    layer: Literal["bronze", "silver", "gold", "platinum"],
    path: str,
    bronze_stratum: Literal["B0", "B1", "B2"] | None = None,
) -> bytes:
    """Build a non-publishable v4 identity for one actual E2E output."""
    document = json.loads(
        (ROOT / "contracts/medallion/v4/fixtures/valid.json").read_bytes()
    )
    digest = hashlib.sha256(payload).hexdigest()
    temporal = require_temporal(receipt.temporal)
    document["authority"]["producer_repository"] = (
        "edithatogo/global-medicines-atlas"
    )
    document["publication"]["run"] = (
        "https://github.com/edithatogo/global-medicines-atlas/actions/runs/1"
    )
    document["source"].update(
        source_id=receipt.source.source_id,
        acquisition_id=temporal.acquisition_id,
        layer=layer,
        bronze_stratum=bronze_stratum,
        representation="projection",
        schema_era="synthetic-e2e-v1",
        comparison_cohort="synthetic",
        effective_date=None,
        retrieved_at=NOW.isoformat().replace("+00:00", "Z"),
    )
    for group in ("location", "verification", "rights"):
        document[group].update(
            dataset="example/australian-benefits-synthetic",
            path=path,
        )
    for group in ("location", "verification"):
        document[group].update(bytes=len(payload), sha256=digest)
    document["verification"]["verified_at"] = NOW.isoformat().replace(
        "+00:00", "Z"
    )
    document["rights"]["subject_sha256"] = digest
    document["lineage"]["inputs"] = [
        {
            "url": "https://fixtures.invalid/receipts/source.json",
            "sha256": receipt.digest(),
        }
    ]
    if layer != "bronze":
        document["lineage"]["promotion_receipt"] = document["verification"][
            "receipt"
        ]
    document["cache"]["offline_behavior"] = "verified_exact_digest_only"
    document["cache"]["expires_at"] = (
        (NOW + timedelta(days=1)).isoformat().replace("+00:00", "Z")
    )
    document["cache"]["max_bytes"] = max(
        document["cache"]["max_bytes"], len(payload)
    )
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def _reconcile_synthetic_outputs(
    receipt: SourceReceipt,
    outputs: tuple[SyntheticOutput, ...],
) -> tuple[DistributionBinding, ...]:
    """Bind actual E2E output bytes to a complete synthetic denominator."""
    producer = "edithatogo/global-medicines-atlas"
    dataset = "example/australian-benefits-synthetic"
    inventory_objects: list[dict[str, object]] = []
    contracts = []
    for layer, path, payload, bronze_stratum in outputs:
        digest = hashlib.sha256(payload).hexdigest()
        inventory_objects.append({
            "source_id": receipt.source.source_id,
            "acquisition_id": require_temporal(receipt.temporal).acquisition_id,
            "layer": layer,
            "bronze_stratum": bronze_stratum,
            "path": path,
            "sha256": digest,
            "byte_count": len(payload),
        })
        contracts.append(
            _distribution_contract(
                payload,
                receipt,
                layer=layer,
                path=path,
                bronze_stratum=bronze_stratum,
            )
        )
    inventory = load_synthetic_producer_inventory(
        json.dumps(
            {
                "schema_id": (
                    "global-medicines-atlas.synthetic-producer-inventory"
                ),
                "schema_version": 1,
                "producer_repository": producer,
                "dataset": dataset,
                "evidence_kind": "synthetic",
                "publishable": False,
                "objects": inventory_objects,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
    assert inventory.publishable is False
    return reconcile_distribution(
        inventory.objects,
        contracts,
        schema=(
            ROOT / "contracts/medallion/v4/federation.schema.json"
        ).read_bytes(),
        destinations=dict.fromkeys(
            ("bronze", "silver", "gold", "platinum"), dataset
        ),
    )


def _exercise_federated_reader(
    receipt: SourceReceipt,
    outputs: tuple[SyntheticOutput, ...],
    bindings: tuple[DistributionBinding, ...],
) -> None:
    """Read each reconciled synthetic product remotely and from exact cache."""
    contracts = tuple(
        _distribution_contract(
            payload,
            receipt,
            layer=layer,
            path=path,
            bronze_stratum=bronze_stratum,
        )
        for layer, path, payload, bronze_stratum in outputs
    )
    payloads_by_contract = {
        hashlib.sha256(contract).hexdigest(): output[2]
        for contract, output in zip(contracts, outputs, strict=True)
    }
    bindings_by_contract = {
        binding.contract_sha256: binding for binding in bindings
    }
    assert set(payloads_by_contract) == set(bindings_by_contract)

    dataset = "example/australian-benefits-synthetic"
    remote_paths = {
        (
            f"/datasets/{dataset}/resolve/{binding.revision}/"
            f"{binding.object.path}"
        ): payloads_by_contract[digest]
        for digest, binding in bindings_by_contract.items()
    }
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        if request.url.path.startswith("/api/datasets/"):
            return httpx.Response(
                200,
                json={"sha": "a" * 40, "private": False, "gated": False},
            )
        payload = remote_paths.get(request.url.path)
        if payload is None:
            return httpx.Response(404)
        return httpx.Response(200, content=payload)

    schema = (
        ROOT / "contracts/medallion/v4/federation.schema.json"
    ).read_bytes()
    with FederatedReader(
        schema=schema,
        admission_records=tuple(admission_record(raw) for raw in contracts),
        transport_factory=lambda: httpx.MockTransport(handle),
        clock=lambda: NOW,
    ) as reader:
        for contract in contracts:
            digest = hashlib.sha256(contract).hexdigest()
            expected = payloads_by_contract[digest]
            with reader.open(contract) as result:
                assert result.origin == "remote"
                assert result.sha256 == hashlib.sha256(expected).hexdigest()
                assert result.byte_count == len(expected)
                assert result.stream.read() == expected

            request_count = len(requests)
            with reader.open(contract, offline=True) as cached:
                assert cached.origin == "verified_cache"
                assert cached.sha256 == hashlib.sha256(expected).hexdigest()
                assert cached.byte_count == len(expected)
                assert cached.stream.read() == expected
            assert len(requests) == request_count

            reader.evict()
            with (
                pytest.raises(ValueError, match="offline"),
                reader.open(contract, offline=True),
            ):
                pytest.fail("eviction must not synthesize an object")
            assert len(requests) == request_count

            with reader.open(contract) as refetched:
                assert refetched.origin == "remote"
                assert refetched.sha256 == hashlib.sha256(expected).hexdigest()
                assert refetched.byte_count == len(expected)
                assert refetched.stream.read() == expected

    _exercise_pbs_v2_identity(contracts, outputs, bindings, schema)


class _IdentityOnlyV2Service:
    """V2 query dependency that must remain unused by identity lookups."""

    def v2_comparisons(self, query: V2ComparisonQuery) -> Never:
        del query
        raise AssertionError("identity lookup must not run a comparison")

    def v2_evidence(self, query: V2EvidenceQuery) -> Never:
        del query
        raise AssertionError("identity lookup must not query evidence")


class _IdentityHttpResponse(Protocol):
    status_code: int

    def json(self) -> dict[str, Any]: ...


class _IdentityHttpClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: list[tuple[str, str]] | None = None,
    ) -> _IdentityHttpResponse: ...


def _exercise_pbs_v2_identity(
    contracts: tuple[bytes, ...],
    outputs: tuple[SyntheticOutput, ...],
    bindings: tuple[DistributionBinding, ...],
    schema: bytes,
) -> None:
    """Expose the exact synthetic PBS Gold edge through V2 identity only."""
    pbs_edges = next(
        (
            (contract, output[2])
            for contract, output in zip(contracts, outputs, strict=True)
            if output[1] == "gold/pbs-edges.parquet"
        ),
        None,
    )
    if pbs_edges is None:
        return

    contract, payload = pbs_edges
    bindings_by_contract = {
        binding.contract_sha256: binding for binding in bindings
    }
    binding = bindings_by_contract[hashlib.sha256(contract).hexdigest()]
    resource_id = "au.pbs.synthetic.structure"
    semantic_manifest = json.dumps(
        {
            "contract_sha256": binding.contract_sha256,
            "entity_granularity": "evidence_edge",
            "resource_id": resource_id,
            "semantic_dimension": "source_structure",
            "version": "1.0",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    resource = ProductResource(
        resource_id=resource_id,
        semantic_dimension="source_structure",
        entity_granularity="evidence_edge",
        binding=binding,
        contract=contract,
        semantic_manifest=semantic_manifest,
    )
    api_requests: list[httpx.Request] = []

    def handle_api_request(request: httpx.Request) -> httpx.Response:
        api_requests.append(request)
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        if request.url.path.startswith("/api/datasets/"):
            return httpx.Response(
                200,
                json={
                    "sha": binding.revision,
                    "private": False,
                    "gated": False,
                },
            )
        if request.url.path.endswith(f"/{binding.object.path}"):
            return httpx.Response(200, content=payload)
        return httpx.Response(404)

    with StorageNeutralResolver(
        schema=schema,
        resources=[resource],
        admission_records=(admission_record(contract),),
        admitted_semantic_manifests=frozenset({
            hashlib.sha256(semantic_manifest).hexdigest()
        }),
        transport_factory=lambda: httpx.MockTransport(handle_api_request),
        clock=lambda: NOW,
    ) as resolver:
        identity_service = ResolverDatasetIdentityService(
            resolver,
            jurisdictions={resource_id: "AU"},
        )
        client = cast(
            "_IdentityHttpClient",
            TestClient(
                create_v2_app(
                    _IdentityOnlyV2Service(),
                    dataset_identities=identity_service,
                )
            ),
        )
        response = client.get(f"/api/v2/datasets/{resource_id}")
        assert api_requests == []
        _exercise_pbs_source_structure_atlas(
            resolver, resource_id, binding, payload, api_requests
        )

    assert response.status_code == 200
    identity = response.json()
    assert identity["semantic_dimension"] == "source_structure"
    assert identity["entity_granularity"] == "evidence_edge"
    assert identity["revision"] == binding.revision
    assert identity["path"] == binding.object.path
    assert identity["object_sha256"] == hashlib.sha256(payload).hexdigest()
    assert identity["coverage_state"] == "not_declared"
    assert identity["comparison_validity"] == "not_evaluated"
    assert identity["rows_queried"] is False


def _exercise_pbs_source_structure_atlas(
    resolver: StorageNeutralResolver,
    resource_id: str,
    binding: DistributionBinding,
    payload: bytes,
    requests: list[httpx.Request],
) -> None:
    """Read PBS structure through Atlas, verified cache and eviction."""
    atlas = TestClient(
        create_atlas_app(
            cast("AtlasQueryService", object()),
            federated_source_structure=SourceStructureService(
                resolver, jurisdictions={resource_id: "AU"}
            ),
        )
    )
    params = {
        "resource_id": resource_id,
        "columns": "kind,semantic_dimension,controls_json",
        "limit": "10",
    }
    response = atlas.get("/federated/source-structure", params=params)
    assert response.status_code == 200, response.text
    for detail in (
        resource_id,
        binding.revision,
        binding.object.path,
        hashlib.sha256(payload).hexdigest(),
        "source_structure",
        "evidence_edge",
        "source_structure_only",
        "not declared",
        "not evaluated",
        "Missing coverage is not negative evidence",
    ):
        assert detail in response.text
    assert [item.url.path for item in requests] == [
        f"/api/datasets/{binding.dataset}/revision/{binding.revision}",
        (
            f"/datasets/{binding.dataset}/resolve/{binding.revision}/"
            f"{binding.object.path}"
        ),
    ]
    request_count = len(requests)
    cached = atlas.get(
        "/federated/source-structure", params={**params, "offline": "true"}
    )
    assert cached.status_code == 200
    assert "source_structure_only" in cached.text
    assert len(requests) == request_count
    resolver.evict()
    unavailable = atlas.get(
        "/federated/source-structure", params={**params, "offline": "true"}
    )
    assert unavailable.status_code == 200
    assert "Pinned evidence unavailable" in unavailable.text
    assert "source_structure_only" not in unavailable.text
    assert len(requests) == request_count


def _binding(raw: bytes) -> DistributionBinding:
    document = json.loads(raw)
    source = document["source"]
    location = document["location"]
    produced = ProducedObject(
        producer_repository=document["authority"]["producer_repository"],
        source_id=source["source_id"],
        acquisition_id=source["acquisition_id"],
        layer=source["layer"],
        bronze_stratum=source["bronze_stratum"],
        path=location["path"],
        sha256=location["sha256"],
        byte_count=location["bytes"],
        evidence_kind=document["evidence_kind"],
    )
    return reconcile_distribution(
        [produced],
        [raw],
        schema=(
            ROOT / "contracts/medallion/v4/federation.schema.json"
        ).read_bytes(),
        destinations={"platinum": location["dataset"]},
    )[0]


def _exercise_query_cache(
    resolver: StorageNeutralResolver,
    resource_id: str,
    requests: list[httpx.Request],
    *,
    columns: tuple[str, ...] = ("kind", "inferred"),
) -> QueryResult:
    service = PlatinumQueryService(resolver)
    spec = QuerySpec(columns=columns, limit=1)
    result = service.query(resource_id, engine="polars", spec=spec)
    assert len(requests) == 2

    cached = service.query(
        resource_id, engine="polars", spec=spec, offline=True
    )
    assert len(requests) == 2
    assert cached.rows == result.rows
    assert cached.result_sha256 == result.result_sha256
    assert cached.cache_receipt.last_origin == "verified_cache"

    resolver.evict()
    unavailable = service.query_state(
        resource_id, engine="polars", spec=spec, offline=True
    )
    assert isinstance(unavailable, QueryUnavailable)
    assert unavailable.reason == "offline_cache_unavailable"

    refetched = service.query(resource_id, engine="polars", spec=spec)
    assert len(requests) == 4
    assert refetched.rows == result.rows
    assert refetched.result_sha256 == result.result_sha256
    return result


def _parquet_payload(table: pa.RecordBatch | pa.Table) -> bytes:
    output = io.BytesIO()
    parquet_table = (
        table if isinstance(table, pa.Table) else pa.Table.from_batches([table])
    )
    pq.write_table(parquet_table, output)
    return output.getvalue()


@dataclass(frozen=True)
class _SyntheticBatchAttestation:
    manifest_payload: bytes
    manifest_sha256: str
    manifest_url: str
    cost_receipt_payload: bytes
    cost_receipt_sha256: str
    cost_receipt_url: str


def _prepare_synthetic_batch_attestation(
    *,
    source_payload: bytes,
    source_sha256: str,
    query_receipt_payload: bytes,
    query_receipt_sha256: str,
    result_payload: bytes,
    result_sha256: str,
    resource_id: str,
    revision: str,
    tmp_path: Path,
) -> _SyntheticBatchAttestation:
    assert hashlib.sha256(source_payload).hexdigest() == source_sha256
    assert (
        hashlib.sha256(query_receipt_payload).hexdigest()
        == query_receipt_sha256
    )
    assert hashlib.sha256(result_payload).hexdigest() == result_sha256
    batch_manifest = build_merkle_manifest((
        MerkleLeaf(path="bronze/raw.xml", sha256=source_sha256),
        MerkleLeaf(
            path="platinum/query-receipt.json",
            sha256=query_receipt_sha256,
        ),
        MerkleLeaf(path="platinum/query-result.json", sha256=result_sha256),
    ))
    assert verify_merkle_manifest(batch_manifest)
    manifest_payload = canonical_merkle_manifest_bytes(batch_manifest)
    manifest_sha256_value = hashlib.sha256(manifest_payload).hexdigest()
    cost_receipt = build_verification_cost_receipt(batch_manifest)
    assert cost_receipt.object_sha256_checks == len(batch_manifest.leaves)
    assert verify_verification_cost_receipt(batch_manifest, cost_receipt)
    cost_receipt_payload = canonical_verification_cost_bytes(cost_receipt)
    cost_receipt_sha256 = hashlib.sha256(cost_receipt_payload).hexdigest()
    batch_manifest_url = (
        "https://fixtures.invalid/synthetic/exports/"
        f"{resource_id}/resolve/"
        f"{revision}/merkle-manifest.json"
    )
    cost_receipt_url = (
        "https://fixtures.invalid/synthetic/exports/"
        f"{resource_id}/resolve/"
        f"{revision}/verification-cost.json"
    )
    (tmp_path / "merkle-manifest.json").write_bytes(manifest_payload)
    (tmp_path / "verification-cost.json").write_bytes(cost_receipt_payload)
    return _SyntheticBatchAttestation(
        manifest_payload=manifest_payload,
        manifest_sha256=manifest_sha256_value,
        manifest_url=batch_manifest_url,
        cost_receipt_payload=cost_receipt_payload,
        cost_receipt_sha256=cost_receipt_sha256,
        cost_receipt_url=cost_receipt_url,
    )


def _verify_saved_research_export(
    result: QueryResult,
    source_receipt: SourceReceipt,
    source_payload: bytes,
    resource_id: str,
    tmp_path: Path,
) -> bytes:
    revision = "a" * 40
    source = ExportSource(
        dataset_id=f"synthetic/{source_receipt.source.source_id}",
        revision=revision,
        path="bronze/raw.xml",
        sha256=source_receipt.payload.sha256,
        schema_id="gma.synthetic.mbs.xml",
        schema_version="1",
    )
    manifest = build_query_snapshot_manifest(
        query={
            "engine": result.engine,
            "query_receipt_sha256": result.query_receipt.receipt_sha256,
            "request": json.loads(result.query_receipt.canonical_query),
            "resource_id": resource_id,
        },
        result_rows=result.rows,
        sources=[source],
        generated_at=NOW,
        generator_commit="synthetic-e2e-v1",
    )
    result_payload = canonical_result_bytes(result.rows)
    assert hashlib.sha256(result_payload).hexdigest() == manifest.result_sha256
    (tmp_path / "query-result.json").write_bytes(result_payload)

    receipt_payload = result.query_receipt.canonical_bytes
    assert (
        hashlib.sha256(receipt_payload).hexdigest()
        == result.query_receipt.receipt_sha256
    )
    (tmp_path / "query-receipt.json").write_bytes(receipt_payload)
    attestation = _prepare_synthetic_batch_attestation(
        source_payload=source_payload,
        source_sha256=source.sha256,
        query_receipt_payload=receipt_payload,
        query_receipt_sha256=result.query_receipt.receipt_sha256,
        result_payload=result_payload,
        result_sha256=manifest.result_sha256,
        resource_id=resource_id,
        revision=revision,
        tmp_path=tmp_path,
    )
    assert resource_id in attestation.manifest_url
    assert resource_id in attestation.cost_receipt_url
    export_url = (
        "https://fixtures.invalid/synthetic/exports/"
        f"{resource_id}/resolve/"
        f"{revision}/query-result.json"
    )
    assert resource_id in export_url
    crate = build_research_crate(
        identifier=manifest_sha256(manifest),
        name="Synthetic medicine evidence query",
        version="synthetic-e2e-v1",
        dataset_url=f"https://fixtures.invalid/synthetic/exports/{resource_id}",
        distributions=(
            CrateDistribution(
                identifier="query-result.json",
                name="Synthetic query result",
                content_url=export_url,
                media_type="application/json",
                sha256=manifest.result_sha256,
            ),
            CrateDistribution(
                identifier="merkle-manifest.json",
                name="Synthetic batch Merkle manifest",
                content_url=attestation.manifest_url,
                media_type="application/json",
                sha256=attestation.manifest_sha256,
            ),
            CrateDistribution(
                identifier="verification-cost.json",
                name="Synthetic verification-cost receipt",
                content_url=attestation.cost_receipt_url,
                media_type="application/json",
                sha256=attestation.cost_receipt_sha256,
            ),
        ),
    )
    lineage = build_research_lineage_receipt(
        export_id=manifest_sha256(manifest),
        revision=revision,
        artifacts=(
            ResearchLineageArtifact(
                identifier=f"synthetic-{source_receipt.source.source_id}-source",
                role="input",
                public_url=(
                    f"https://fixtures.invalid/{source.dataset_id}/resolve/"
                    f"{revision}/bronze/raw.xml"
                ),
                sha256=source.sha256,
            ),
            ResearchLineageArtifact(
                identifier="query-receipt.json",
                role="input",
                public_url=(
                    "https://fixtures.invalid/synthetic/receipts/resolve/"
                    f"{resource_id}/{revision}/query-receipt.json"
                ),
                sha256=result.query_receipt.receipt_sha256,
            ),
            ResearchLineageArtifact(
                identifier="query-result.json",
                role="output",
                public_url=export_url,
                sha256=manifest.result_sha256,
            ),
            ResearchLineageArtifact(
                identifier="merkle-manifest.json",
                role="output",
                public_url=attestation.manifest_url,
                sha256=attestation.manifest_sha256,
            ),
            ResearchLineageArtifact(
                identifier="verification-cost.json",
                role="output",
                public_url=attestation.cost_receipt_url,
                sha256=attestation.cost_receipt_sha256,
            ),
        ),
    )
    package = build_research_export_package(
        manifest=manifest,
        crate=crate,
        lineage=lineage,
    )
    archive_bytes = package.archive_bytes()
    (tmp_path / "research-export.zip").write_bytes(archive_bytes)
    saved_archive = (tmp_path / "research-export.zip").read_bytes()

    assert b"source_record_has_benefit" not in saved_archive
    assert source_payload not in saved_archive
    assert receipt_payload not in saved_archive
    assert result_payload not in saved_archive
    assert attestation.manifest_payload not in saved_archive
    assert attestation.cost_receipt_payload not in saved_archive
    lineage_document = json.loads(dict(package.documents)["lineage.json"])
    output_identifiers = {
        artifact["identifier"]
        for artifact in lineage_document["artifacts"]
        if artifact["role"] == "output"
    }
    assert output_identifiers == {
        "query-result.json",
        "merkle-manifest.json",
        "verification-cost.json",
    }
    assert (
        verify_research_export_package(saved_archive).archive_bytes()
        == saved_archive
    )
    return saved_archive


def _silver_gold_products(
    payload: bytes, receipt: SourceReceipt
) -> tuple[pa.RecordBatch, pa.Table, bytes]:
    silver = next(iter_mbs_silver_batches(payload, receipt, table="services"))
    assert silver.num_rows == 1
    assert silver.column("source_sha256")[0].as_py() == receipt.payload.sha256

    candidate = build_mbs_gold_graph_candidate(payload, receipt)
    assert candidate.qualification == "synthetic_silver_candidate_only"
    assert candidate.admission_performed is False
    nodes, edges = project_mbs_gold_graph_arrow(candidate)
    assert nodes.num_rows == 2
    gold = _parquet_payload(edges)
    assert pq.read_table(io.BytesIO(gold)).num_rows == 1
    return silver, nodes, gold


def _query_synthetic_platinum(
    gold: bytes,
    receipt: SourceReceipt,
    *,
    resource_id: str = "au.mbs.synthetic.edges",
    semantic_dimension: PlatinumSemanticDimension = "service_benefit",
    columns: tuple[str, ...] = ("kind", "inferred"),
    monkeypatch: pytest.MonkeyPatch | None = None,
    tmp_path: Path | None = None,
) -> QueryResult:
    contract = _platinum_contract(gold, receipt)
    binding = _binding(contract)
    semantic = json.dumps(
        {
            "contract_sha256": binding.contract_sha256,
            "entity_granularity": "evidence_edge",
            "resource_id": resource_id,
            "semantic_dimension": semantic_dimension,
            "version": "1.0",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    resource = ProductResource(
        resource_id=resource_id,
        semantic_dimension=semantic_dimension,
        entity_granularity="evidence_edge",
        binding=binding,
        contract=contract,
        semantic_manifest=semantic,
    )
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        if "/api/datasets/" in request.url.path:
            return httpx.Response(
                200, json={"sha": "a" * 40, "private": False, "gated": False}
            )
        return httpx.Response(200, content=gold)

    with StorageNeutralResolver(
        schema=(
            ROOT / "contracts/medallion/v4/federation.schema.json"
        ).read_bytes(),
        resources=[resource],
        admission_records=(admission_record(contract),),
        admitted_semantic_manifests=frozenset({
            hashlib.sha256(semantic).hexdigest()
        }),
        transport_factory=lambda: httpx.MockTransport(handle),
        clock=lambda: NOW,
    ) as resolver:
        if semantic_dimension == "service_benefit":
            client = cast(
                "_IdentityHttpClient",
                TestClient(
                    create_app(
                        cast("ReadOnlyQueryService", object()),
                        benefits=BenefitsService(
                            resolver,
                            cursor_key=b"synthetic-e2e-cursor-key-32-bytes",
                        ),
                    )
                ),
            )
            response = client.get(
                f"/api/v1/benefits/{resource_id}",
                params=[("columns", column) for column in columns]
                + [("limit", "1")],
            )
            assert response.status_code == 200
            page = response.json()
            assert page["status"] == "available"
            assert page["rows"] == [
                {
                    column: value
                    for column, value in {
                        "kind": "source_record_has_benefit",
                        "inferred": False,
                    }.items()
                    if column in columns
                }
            ]
            assert page["identity"]["source_id"] == receipt.source.source_id
            assert page["identity"]["revision"] == binding.revision
            assert page["identity"]["path"] == binding.object.path
            assert (
                page["identity"]["object_sha256"]
                == hashlib.sha256(gold).hexdigest()
            )
            assert page["identity"]["semantic_dimension"] == "service_benefit"
            assert page["identity"]["entity_granularity"] == "evidence_edge"
            assert page["coverage_state"] == "not_declared"
            assert page["comparison_validity"] == "not_evaluated"
            assert page["page_sha256"]
            assert page["window_sha256"]
            assert len(requests) == 2
            assert requests[0].url.path == (
                f"/api/datasets/{binding.dataset}/revision/{binding.revision}"
            )
            assert requests[1].url.path == (
                f"/datasets/{binding.dataset}/resolve/{binding.revision}/"
                f"{binding.object.path}"
            )

            atlas = TestClient(
                create_atlas_app(
                    cast("AtlasQueryService", object()),
                    federated_benefits=BenefitsService(
                        resolver,
                        cursor_key=b"synthetic-e2e-atlas-cursor-key-32-bytes",
                    ),
                )
            )
            atlas_response = atlas.get(
                "/federated/benefits",
                params={
                    "resource_id": resource_id,
                    "columns": "kind,inferred",
                    "limit": "1",
                },
            )
            assert atlas_response.status_code == 200
            for detail in (
                resource_id,
                binding.revision,
                binding.object.path,
                hashlib.sha256(gold).hexdigest(),
                "service_benefit",
                "evidence_edge",
                "source_record_has_benefit",
                "not declared",
                "not evaluated",
                "Acquisition",
                "Schema era",
                "Contract SHA-256",
                "Semantic manifest SHA-256",
                "Retrieved at",
                "Cache expires at",
                "Query SHA-256",
                "Page SHA-256",
                "Window SHA-256",
                "Query receipt SHA-256",
            ):
                assert detail in atlas_response.text
            requests.clear()

            if monkeypatch is not None and tmp_path is not None:
                _exercise_benefits_cli(
                    resolver,
                    resource_id,
                    columns,
                    page,
                    (monkeypatch, tmp_path),
                )
                requests.clear()

        result = _exercise_query_cache(
            resolver, resource.resource_id, requests, columns=columns
        )
        if (
            semantic_dimension == "source_structure"
            and monkeypatch is not None
            and tmp_path is not None
        ):
            _exercise_source_structure_cli(
                resolver,
                resource_id,
                columns,
                result,
                (monkeypatch, tmp_path),
            )
            assert len(requests) == 4
        return result


@pytest.mark.e2e
def test_synthetic_evidence_flows_from_bronze_to_platinum_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify exact synthetic lineage through each layer without publication."""
    raw = _payload()
    previous_raw = (
        b"<MBS_XML><Data><ItemNum>00123</ItemNum>"
        b"<SubItemNum>00</SubItemNum>"
        b"<Description>prior synthetic service</Description></Data>"
        b"<Data><ItemNum>00567</ItemNum><SubItemNum>00</SubItemNum>"
        b"<Description>removed synthetic service</Description></Data>"
        b"</MBS_XML>"
    )
    previous_receipt = _receipt(
        previous_raw,
        retrieved_at=NOW - timedelta(days=1),
    )
    receipt = _receipt(raw)
    _exercise_historical_surfaces(
        previous_raw,
        previous_receipt,
        raw,
        receipt,
        history_file=tmp_path / "synthetic-history.json",
        bronze_root=tmp_path / "historical-bronze",
        monkeypatch=monkeypatch,
    )
    landed = land_bronze_payload(
        raw,
        receipt,
        bronze_root=tmp_path / "bronze",
        media_hint="xml",
        admission_decided_at=NOW,
        transformation_completed_at=NOW,
        payload_store=_SyntheticRemoteLocatorPayloadStore(
            tmp_path / "synthetic-object-store"
        ),
    )
    assert landed.payload_path.read_bytes() == raw
    assert landed.receipt.evidence_class is EvidenceClass.SYNTHETIC
    assert isinstance(landed, BronzeLanding)
    assert landed.receipt.payload.sha256 == hashlib.sha256(raw).hexdigest()
    assert landed.admission.state is BronzeAdmissionState.ACCEPTED
    assert landed.receipt.rights_state is RightsState.UNKNOWN
    assert landed.receipt.satisfies_live_gate is False
    b1_manifest = _assert_landed_b1_projection(landed, payload=raw)
    _assert_projection_rejects_embedded_b2(
        landed,
        payload=raw,
        tmp_path=tmp_path,
    )

    silver, nodes, gold = _silver_gold_products(
        landed.payload_path.read_bytes(), landed.receipt
    )
    edge_file = tmp_path / "mbs-gold-edges.parquet"
    gold_edges = pq.read_table(io.BytesIO(gold))
    pq.write_table(gold_edges, edge_file)
    _exercise_gold_edge_surfaces(gold_edges, edge_file=edge_file)
    _exercise_gold_review_queue(
        gold_edges,
        expected_edges=build_mbs_gold_graph_candidate(
            landed.payload_path.read_bytes(), landed.receipt
        ).edges,
        adjudication_path=tmp_path / "mbs-gold-adjudications.jsonl",
    )
    result = _query_synthetic_platinum(
        gold, landed.receipt, monkeypatch=monkeypatch, tmp_path=tmp_path
    )

    assert result.status == "available"
    assert result.rows == (
        {"inferred": False, "kind": "source_record_has_benefit"},
    )
    assert result.evidence.object_sha256 == hashlib.sha256(gold).hexdigest()
    assert result.evidence.source_id == SOURCE_ID
    assert (
        result.evidence.acquisition_id
        == require_temporal(landed.receipt.temporal).acquisition_id
    )
    assert result.query_receipt.result_sha256 == result.result_sha256
    export_package = _verify_saved_research_export(
        result=result,
        source_receipt=landed.receipt,
        source_payload=landed.payload_path.read_bytes(),
        resource_id="au.mbs.synthetic.edges",
        tmp_path=tmp_path,
    )
    outputs: tuple[SyntheticOutput, ...] = (
        (
            "bronze",
            "bronze/acquisition-manifest.parquet",
            b1_manifest,
            "B1",
        ),
        (
            "silver",
            "silver/mbs-services.parquet",
            _parquet_payload(silver),
            None,
        ),
        (
            "gold",
            "gold/mbs-nodes.parquet",
            _parquet_payload(nodes),
            None,
        ),
        ("gold", "gold/mbs-edges.parquet", gold, None),
        (
            "platinum",
            "platinum/research-export.zip",
            export_package,
            None,
        ),
    )
    bindings = _reconcile_synthetic_outputs(landed.receipt, outputs)
    _exercise_federated_reader(landed.receipt, outputs, bindings)
    assert len(bindings) == 5
    assert {item.object.layer for item in bindings} == {
        "bronze",
        "silver",
        "gold",
        "platinum",
    }
    assert all(item.object.evidence_kind == "synthetic" for item in bindings)
    assert all(item.revision == "a" * 40 for item in bindings)


@pytest.mark.e2e
def test_synthetic_pbs_structure_flows_from_bronze_to_platinum(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preserve PBS containment as source structure across all product layers."""
    raw = PBS_XML
    receipt = _receipt(raw, source_id="au-pbs")
    landed = land_bronze_payload(
        raw,
        receipt,
        bronze_root=tmp_path / "bronze",
        media_hint="xml",
        admission_decided_at=NOW,
        transformation_completed_at=NOW,
        payload_store=_SyntheticRemoteLocatorPayloadStore(
            tmp_path / "synthetic-object-store"
        ),
    )
    assert landed.receipt.evidence_class is EvidenceClass.SYNTHETIC
    assert isinstance(landed, BronzeLanding)
    assert landed.receipt.rights_state is RightsState.UNKNOWN
    assert landed.receipt.satisfies_live_gate is False
    b1_manifest = _assert_landed_b1_projection(landed, payload=raw)
    assert landed.payload_path.read_bytes() == raw
    assert landed.receipt.payload.sha256 == hashlib.sha256(raw).hexdigest()

    silver = pa.Table.from_batches(
        list(
            iter_pbs_silver_batches(
                landed.payload_path.read_bytes(), landed.receipt
            )
        )
    )
    candidate = build_pbs_gold_graph_candidate(
        landed.payload_path.read_bytes(), landed.receipt
    )
    assert candidate.asserted_dimensions == ()
    assert candidate.admission_performed is False
    assert candidate.inference_performed is False
    nodes, edges = project_pbs_gold_graph_arrow(candidate)
    assert all(
        edge.semantic_dimension == "source_structure"
        and edge.comparison_validity == "source_structure_only"
        and not edge.inferred
        for edge in candidate.edges
    )
    silver_payload = _parquet_payload(silver)
    node_payload = _parquet_payload(nodes)
    gold_payload = _parquet_payload(edges)
    _exercise_gold_review_queue(
        pq.read_table(io.BytesIO(gold_payload)),
        expected_edges=candidate.edges,
        adjudication_path=tmp_path / "pbs-gold-adjudications.jsonl",
    )
    result = _query_synthetic_platinum(
        gold_payload,
        landed.receipt,
        resource_id="au.pbs.synthetic.structure",
        semantic_dimension="source_structure",
        columns=(
            "kind",
            "semantic_dimension",
            "controls_json",
        ),
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
    )
    assert result.status == "available"
    assert result.rows
    assert all(
        row["semantic_dimension"] == "source_structure" for row in result.rows
    )
    assert all(
        '"comparison_validity":"source_structure_only"'
        in str(row["controls_json"])
        and '"inferred":false' in str(row["controls_json"])
        for row in result.rows
    )
    assert result.evidence.semantic_dimension == "source_structure"
    assert result.evidence.source_id == "au-pbs"
    export_package = _verify_saved_research_export(
        result=result,
        source_receipt=landed.receipt,
        source_payload=landed.payload_path.read_bytes(),
        resource_id="au.pbs.synthetic.structure",
        tmp_path=tmp_path,
    )
    outputs: tuple[SyntheticOutput, ...] = (
        (
            "bronze",
            "bronze/acquisition-manifest.parquet",
            b1_manifest,
            "B1",
        ),
        (
            "silver",
            "silver/pbs-native-fields.parquet",
            silver_payload,
            None,
        ),
        ("gold", "gold/pbs-nodes.parquet", node_payload, None),
        ("gold", "gold/pbs-edges.parquet", gold_payload, None),
        (
            "platinum",
            "platinum/pbs-research-export.zip",
            export_package,
            None,
        ),
    )
    bindings = _reconcile_synthetic_outputs(landed.receipt, outputs)
    _exercise_federated_reader(landed.receipt, outputs, bindings)
    assert len(bindings) == 5
    assert {item.object.layer for item in bindings} == {
        "bronze",
        "silver",
        "gold",
        "platinum",
    }
    assert all(item.object.evidence_kind == "synthetic" for item in bindings)
    assert all(item.revision == "a" * 40 for item in bindings)
