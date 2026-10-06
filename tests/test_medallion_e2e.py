"""Synthetic proof that Bronze, Silver, Gold and Platinum compose."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest
from test_support.federation import admission_record

from global_medicines_atlas.bronze_admission import BronzeAdmissionState
from global_medicines_atlas.bronze_landing import land_bronze_payload
from global_medicines_atlas.federation_distribution import (
    DistributionBinding,
    ProducedObject,
    reconcile_distribution,
)
from global_medicines_atlas.mbs_gold_graph import (
    build_mbs_gold_graph_candidate,
    project_mbs_gold_graph_arrow,
)
from global_medicines_atlas.mbs_silver import iter_mbs_silver_batches
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

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 6, tzinfo=UTC)
SOURCE_ID = "au-mbs"


def _payload() -> bytes:
    return (
        b"<MBS_XML><Data><ItemNum>00123</ItemNum>"
        b"<SubItemNum>00</SubItemNum><Description>fixture service</Description>"
        b"</Data></MBS_XML>"
    )


def _receipt(payload: bytes) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    receipt = SourceReceipt(
        receipt_id="synthetic:medallion-e2e",
        source=SourceIdentity(
            catalog_id=SOURCE_ID,
            source_id=SOURCE_ID,
            jurisdiction="AUS",
            authority="Repository-owned synthetic fixture",
            dataset_title="Synthetic MBS E2E fixture",
            catalog_version="synthetic-e2e-v1",
        ),
        retrieval=RetrievalEvidence(
            uri="https://fixtures.invalid/mbs.xml",
            retrieved_at=NOW,
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
            "reuse": acquire_new_decision(SOURCE_ID),
            "temporal": temporal_identity_from_source(
                retrieved_at=NOW,
                source_id=SOURCE_ID,
                payload_sha256=evidence.sha256,
                source_version="synthetic-e2e-v1",
            ),
        }
    )


def _platinum_contract(payload: bytes, receipt: SourceReceipt) -> bytes:
    document = json.loads(
        (ROOT / "contracts/medallion/v4/fixtures/valid.json").read_bytes()
    )
    digest = hashlib.sha256(payload).hexdigest()
    document["source"].update(
        source_id=SOURCE_ID,
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
        path="platinum/synthetic-mbs-edges.parquet",
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
) -> QueryResult:
    service = PlatinumQueryService(resolver)
    spec = QuerySpec(columns=("kind", "inferred"), limit=1)
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


def _verify_saved_research_export(
    result: QueryResult,
    source_receipt: SourceReceipt,
    resource_id: str,
    tmp_path: Path,
) -> None:
    revision = "a" * 40
    source = ExportSource(
        dataset_id="synthetic/mbs",
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
    export_url = (
        "https://fixtures.invalid/synthetic/exports/resolve/"
        f"{revision}/query-result.json"
    )
    crate = build_research_crate(
        identifier=manifest_sha256(manifest),
        name="Synthetic medicine evidence query",
        version="synthetic-e2e-v1",
        dataset_url="https://fixtures.invalid/synthetic/exports",
        distributions=(
            CrateDistribution(
                identifier="query-result.json",
                name="Synthetic query result",
                content_url=export_url,
                media_type="application/json",
                sha256=manifest.result_sha256,
            ),
        ),
    )
    lineage = build_research_lineage_receipt(
        export_id=manifest_sha256(manifest),
        revision=revision,
        artifacts=(
            ResearchLineageArtifact(
                identifier="synthetic-mbs-source",
                role="input",
                public_url=(
                    "https://fixtures.invalid/synthetic/mbs/resolve/"
                    f"{revision}/bronze/raw.xml"
                ),
                sha256=source.sha256,
            ),
            ResearchLineageArtifact(
                identifier="query-receipt.json",
                role="input",
                public_url=(
                    "https://fixtures.invalid/synthetic/receipts/resolve/"
                    f"{revision}/query-receipt.json"
                ),
                sha256=result.query_receipt.receipt_sha256,
            ),
            ResearchLineageArtifact(
                identifier="query-result.json",
                role="output",
                public_url=export_url,
                sha256=manifest.result_sha256,
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
    assert result_payload not in saved_archive
    assert (
        verify_research_export_package(saved_archive).archive_bytes()
        == saved_archive
    )


@pytest.mark.e2e
def test_synthetic_evidence_flows_from_bronze_to_platinum_query(
    tmp_path: Path,
) -> None:
    """Verify exact synthetic lineage through each layer without publication."""
    raw = _payload()
    receipt = _receipt(raw)
    landed = land_bronze_payload(
        raw,
        receipt,
        bronze_root=tmp_path / "bronze",
        media_hint="xml",
        admission_decided_at=NOW,
        transformation_completed_at=NOW,
    )
    assert landed.payload_path.read_bytes() == raw
    assert landed.receipt.evidence_class is EvidenceClass.SYNTHETIC
    assert landed.receipt.payload.sha256 == hashlib.sha256(raw).hexdigest()
    assert landed.admission.state is BronzeAdmissionState.ACCEPTED
    assert landed.receipt.rights_state is RightsState.UNKNOWN
    assert landed.receipt.satisfies_live_gate is False

    silver = next(
        iter_mbs_silver_batches(
            landed.payload_path.read_bytes(), landed.receipt, table="services"
        )
    )
    assert silver.num_rows == 1
    assert (
        silver.column("source_sha256")[0].as_py()
        == landed.receipt.payload.sha256
    )

    candidate = build_mbs_gold_graph_candidate(
        landed.payload_path.read_bytes(), landed.receipt
    )
    assert candidate.qualification == "synthetic_silver_candidate_only"
    assert candidate.admission_performed is False
    nodes, edges = project_mbs_gold_graph_arrow(candidate)
    edge_sink = io.BytesIO()
    pq.write_table(edges, edge_sink)
    gold = edge_sink.getvalue()
    assert pq.read_table(io.BytesIO(gold)).num_rows == 1

    contract = _platinum_contract(gold, landed.receipt)
    binding = _binding(contract)
    semantic = json.dumps(
        {
            "contract_sha256": binding.contract_sha256,
            "entity_granularity": "evidence_edge",
            "resource_id": "au.mbs.synthetic.edges",
            "semantic_dimension": "service_benefit",
            "version": "1.0",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    resource = ProductResource(
        resource_id="au.mbs.synthetic.edges",
        semantic_dimension="service_benefit",
        entity_granularity="evidence_edge",
        binding=binding,
        contract=contract,
        semantic_manifest=semantic,
    )

    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
        result = _exercise_query_cache(resolver, resource.resource_id, requests)

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
    assert nodes.num_rows == 2

    _verify_saved_research_export(
        result=result,
        source_receipt=landed.receipt,
        resource_id=resource.resource_id,
        tmp_path=tmp_path,
    )
