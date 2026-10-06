"""Synthetic proof that Bronze, Silver, Gold and Platinum compose."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest

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
    QuerySpec,
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

    def handle(request: httpx.Request) -> httpx.Response:
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
        admitted_contracts=frozenset({binding.contract_sha256}),
        admitted_semantic_manifests=frozenset({
            hashlib.sha256(semantic).hexdigest()
        }),
        transport_factory=lambda: httpx.MockTransport(handle),
        clock=lambda: NOW,
    ) as resolver:
        result = PlatinumQueryService(resolver).query(
            resource.resource_id,
            engine="polars",
            spec=QuerySpec(columns=("kind", "inferred"), limit=1),
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
    assert nodes.num_rows == 2
