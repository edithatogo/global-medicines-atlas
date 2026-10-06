"""Synthetic proof that Bronze, Silver, Gold and Platinum compose."""

from __future__ import annotations

import hashlib
import io
import json
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

from global_medicines_atlas.api import create_app
from global_medicines_atlas.bronze_admission import BronzeAdmissionState
from global_medicines_atlas.bronze_landing import land_bronze_payload
from global_medicines_atlas.federation_distribution import (
    DistributionBinding,
    ProducedObject,
    load_synthetic_producer_inventory,
    reconcile_distribution,
)
from global_medicines_atlas.federation_reader import FederatedReader
from global_medicines_atlas.mbs_gold_graph import (
    build_mbs_gold_graph_candidate,
    project_mbs_gold_graph_arrow,
)
from global_medicines_atlas.mbs_silver import iter_mbs_silver_batches
from global_medicines_atlas.pbs_gold_graph import (
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

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 6, tzinfo=UTC)
SOURCE_ID = "au-mbs"
type SyntheticOutput = tuple[
    Literal["bronze", "silver", "gold", "platinum"],
    str,
    bytes,
    Literal["B0", "B1", "B2"] | None,
]


def _payload() -> bytes:
    return (
        b"<MBS_XML><Data><ItemNum>00123</ItemNum>"
        b"<SubItemNum>00</SubItemNum><Description>fixture service</Description>"
        b"</Data></MBS_XML>"
    )


def _receipt(payload: bytes, *, source_id: str = SOURCE_ID) -> SourceReceipt:
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
            "reuse": acquire_new_decision(source_id),
            "temporal": temporal_identity_from_source(
                retrieved_at=NOW,
                source_id=source_id,
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
    assert api_requests == []


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


def _verify_saved_research_export(
    result: QueryResult,
    source_receipt: SourceReceipt,
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
            requests.clear()

        return _exercise_query_cache(
            resolver, resource.resource_id, requests, columns=columns
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

    silver, nodes, gold = _silver_gold_products(
        landed.payload_path.read_bytes(), landed.receipt
    )
    result = _query_synthetic_platinum(gold, landed.receipt)

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
        resource_id="au.mbs.synthetic.edges",
        tmp_path=tmp_path,
    )
    outputs: tuple[SyntheticOutput, ...] = (
        (
            "bronze",
            "bronze/receipts/source.json",
            landed.receipt.canonical_json(),
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
    )
    assert landed.receipt.evidence_class is EvidenceClass.SYNTHETIC
    assert landed.receipt.rights_state is RightsState.UNKNOWN
    assert landed.receipt.satisfies_live_gate is False
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
        resource_id="au.pbs.synthetic.structure",
        tmp_path=tmp_path,
    )
    outputs: tuple[SyntheticOutput, ...] = (
        (
            "bronze",
            "bronze/receipts/pbs-source.json",
            landed.receipt.canonical_json(),
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
