"""Evidence-bearing Gold graph candidates for synthetic and admitted MBS Silver.

Only source-record co-occurrence produces an edge.  The projection does not
perform terminology linking, entity resolution, admission, or publication.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any, Literal, cast

import pyarrow as pa
from pydantic import (
    AwareDatetime,
    ConfigDict,
    Field,
    model_serializer,
    model_validator,
)

from .mbs_silver import iter_mbs_silver_batches
from .mbs_typed_values import ConversionStatus
from .models import FrozenModel
from .receipts import (
    EvidenceClass,
    RightsState,
    SensitivityClassification,
    SourceReceipt,
)

SYNTHETIC_GRAPH_SCHEMA_VERSION = 2
ADMITTED_GRAPH_SCHEMA_VERSION = 3


class MbsGoldFieldEvidence(FrozenModel):
    """One literal Silver field state carried into a graph node."""

    native_name: str = Field(min_length=1)
    native_state: Literal["missing_field", "null", "value"]
    native_value: str | None
    conversion_status: ConversionStatus | Literal["unrepresentable"]
    typed_value: str | None

    @model_validator(mode="after")
    def native_state_matches_value(self) -> MbsGoldFieldEvidence:
        if (self.native_state == "value") != (self.native_value is not None):
            raise ValueError("Gold field native state differs from value")
        return self


class MbsGoldEvidence(FrozenModel):
    """Exact B1/B2 and row address supporting a node or edge."""

    source_id: Literal["au-mbs"] = "au-mbs"
    source_record_id: str = Field(min_length=1)
    source_ordinal: int = Field(strict=True, ge=0)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalog_version: str = Field(min_length=1)
    rights_state: RightsState
    sensitivity: SensitivityClassification = Field(
        default_factory=SensitivityClassification
    )


class MbsGoldNode(FrozenModel):
    """Source-record-scoped service or benefit evidence entity."""

    node_id: str = Field(pattern=r"^mbs-gold-node:[0-9a-f]{64}$")
    kind: Literal["mbs_service_record", "mbs_benefit_record"]
    evidence: MbsGoldEvidence
    fields: tuple[MbsGoldFieldEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def sorted_unique_and_bound(self) -> MbsGoldNode:
        names = tuple(field.native_name for field in self.fields)
        if names != tuple(sorted(set(names))):
            raise ValueError("Gold node fields must be sorted and unique")
        if self.node_id != _node_id(self.kind, self.evidence, self.fields):
            raise ValueError("Gold node identity differs from evidence")
        return self


class MbsGoldEdge(FrozenModel):
    """An explicit same-source-record service-to-benefit relationship."""

    edge_id: str = Field(pattern=r"^mbs-gold-edge:[0-9a-f]{64}$")
    kind: Literal["source_record_has_benefit"] = "source_record_has_benefit"
    source_node_id: str = Field(pattern=r"^mbs-gold-node:[0-9a-f]{64}$")
    target_node_id: str = Field(pattern=r"^mbs-gold-node:[0-9a-f]{64}$")
    evidence: MbsGoldEvidence
    supporting_revisions: tuple[str, ...] = Field(min_length=1, max_length=1)
    assertion_basis: Literal["same_source_record"] = "same_source_record"
    semantic_dimension: Literal["service_benefit"] = "service_benefit"
    mapping_method: Literal["source-explicit"] = "source-explicit"
    confidence: None = None
    confidence_calibration: Literal["not_applicable_source_record"] = (
        "not_applicable_source_record"
    )
    review_state: Literal["not_reviewed"] = "not_reviewed"
    valid_time_status: Literal[
        "unselected", "source_snapshot_effective_date"
    ] = "unselected"
    source_snapshot_effective_date: date | None = None
    source_effective_from: AwareDatetime | None = None
    source_effective_to: AwareDatetime | None = None
    retrieved_at: AwareDatetime
    rights_state: RightsState
    sensitivity: SensitivityClassification = Field(
        default_factory=SensitivityClassification
    )
    contradiction_edge_ids: tuple[str, ...] = ()
    supersedes_edge_ids: tuple[str, ...] = ()
    negative_control_outcome: Literal["not_applicable"] = "not_applicable"
    comparison_validity: Literal["same_source_record_only"] = (
        "same_source_record_only"
    )
    inferred: Literal[False] = False

    @model_serializer(mode="wrap")
    def serialize_snapshot_date(self, handler: Any) -> Any:
        value = handler(self)
        if self.source_snapshot_effective_date is None:
            value.pop("source_snapshot_effective_date", None)
        return value

    @model_validator(mode="after")
    def content_bound(self) -> MbsGoldEdge:
        if self.valid_time_status == "source_snapshot_effective_date":
            if (
                self.source_snapshot_effective_date is None
                or self.source_effective_from is not None
                or self.source_effective_to is not None
            ):
                raise ValueError(
                    "snapshot date must preserve day-level precision"
                )
        elif self.source_snapshot_effective_date is not None:
            raise ValueError("unselected validity cannot carry a snapshot date")
        if self.source_node_id == self.target_node_id:
            raise ValueError("Gold graph self-edge is invalid")
        if self.edge_id != _edge_id(
            self.source_node_id, self.target_node_id, self.evidence
        ):
            raise ValueError("Gold edge identity differs from evidence")
        if self.contradiction_edge_ids or self.supersedes_edge_ids:
            raise ValueError("Gold candidate cannot assert graph history")
        if self.supporting_revisions != (self.evidence.catalog_version,):
            raise ValueError("Gold edge revision differs from B1 evidence")
        return self


class MbsGoldGraphCandidate(FrozenModel):
    """Deterministic candidate graph retaining all selected Silver evidence."""

    model_config = ConfigDict(revalidate_instances="always")
    schema_id: Literal["global-medicines-atlas.mbs-gold-graph-candidate"] = (
        "global-medicines-atlas.mbs-gold-graph-candidate"
    )
    schema_version: Literal[2, 3] = SYNTHETIC_GRAPH_SCHEMA_VERSION
    qualification: Literal[
        "synthetic_silver_candidate_only", "admitted_real_silver_candidate_only"
    ] = "synthetic_silver_candidate_only"
    admission_performed: Literal[False] = False
    input_admission_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    input_semantic_manifest_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    terminology_linking_performed: Literal[False] = False
    publication_performed: Literal[False] = False
    source_record_count: int = Field(strict=True, ge=1)
    nodes: tuple[MbsGoldNode, ...]
    edges: tuple[MbsGoldEdge, ...]
    graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_serializer(mode="wrap")
    def serialize_real_admission(self, handler: Any) -> Any:
        value = handler(self)
        if self.qualification == "synthetic_silver_candidate_only":
            value.pop("input_admission_sha256", None)
            value.pop("input_semantic_manifest_sha256", None)
        return value

    @model_validator(mode="after")
    def input_admission_is_bound(self) -> MbsGoldGraphCandidate:
        if self.qualification == "synthetic_silver_candidate_only":
            if self.schema_version != SYNTHETIC_GRAPH_SCHEMA_VERSION:
                raise ValueError("synthetic Gold graph must retain schema v2")
            if (
                self.input_admission_sha256
                or self.input_semantic_manifest_sha256
            ):
                raise ValueError(
                    "synthetic Gold graph cannot claim real Silver admission"
                )
        else:
            if self.schema_version != ADMITTED_GRAPH_SCHEMA_VERSION:
                raise ValueError(
                    "admitted real Silver Gold graph requires schema v3"
                )
            if (
                not self.input_admission_sha256
                or not self.input_semantic_manifest_sha256
            ):
                raise ValueError(
                    "real Silver Gold graph requires both admission digests"
                )
        return self

    @model_validator(mode="after")
    def graph_is_closed_and_bound(self) -> MbsGoldGraphCandidate:
        if (
            tuple(sorted(self.nodes, key=lambda item: item.node_id))
            != self.nodes
        ):
            raise ValueError("Gold nodes are not deterministic")
        if (
            tuple(sorted(self.edges, key=lambda item: item.edge_id))
            != self.edges
        ):
            raise ValueError("Gold edges are not deterministic")
        by_id = {node.node_id: node for node in self.nodes}
        if len(by_id) != len(self.nodes):
            raise ValueError("Gold node identity is ambiguous")
        if len({edge.edge_id for edge in self.edges}) != len(self.edges):
            raise ValueError("Gold edge identity is ambiguous")
        if (
            len(self.nodes) != self.source_record_count * 2
            or len(self.edges) != self.source_record_count
        ):
            raise ValueError("Gold graph denominator differs from Silver")
        service_evidence = {
            _evidence_address(node.evidence)
            for node in self.nodes
            if node.kind == "mbs_service_record"
        }
        benefit_evidence = {
            _evidence_address(node.evidence)
            for node in self.nodes
            if node.kind == "mbs_benefit_record"
        }
        edge_evidence = {
            _evidence_address(edge.evidence) for edge in self.edges
        }
        if not (
            len(service_evidence)
            == len(benefit_evidence)
            == len(edge_evidence)
            == self.source_record_count
            and service_evidence == benefit_evidence == edge_evidence
        ):
            raise ValueError("Gold graph evidence denominator is ambiguous")
        for edge in self.edges:
            source = by_id.get(edge.source_node_id)
            target = by_id.get(edge.target_node_id)
            if source is None or target is None:
                raise ValueError("Gold edge endpoint is absent")
            if (
                source.kind != "mbs_service_record"
                or target.kind != "mbs_benefit_record"
                or source.evidence != target.evidence
                or edge.evidence != source.evidence
            ):
                raise ValueError(
                    "Gold edge is not supported by the same record"
                )
        node_policies = {
            (node.evidence.rights_state, node.evidence.sensitivity)
            for node in self.nodes
        }
        edge_policies = {
            (edge.rights_state, edge.sensitivity) for edge in self.edges
        }
        if len(node_policies) != 1 or node_policies != edge_policies:
            raise ValueError("Gold graph rights/sensitivity metadata differs")
        if self.graph_sha256 != _digest(
            self.model_dump(exclude={"graph_sha256"})
        ):
            raise ValueError("Gold graph digest differs")
        return self


class MbsGoldAdmittedSilverInput(FrozenModel):
    """Verified source/receipt metadata for an admitted real Silver cohort."""

    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalog_version: str = Field(min_length=1)
    source_record_count: int = Field(strict=True, ge=1)
    source_effective_date: date
    retrieved_at: AwareDatetime
    rights_state: RightsState
    admission_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda item: (
            item.isoformat() if isinstance(item, datetime) else str(item)
        ),
    ).encode()


def _evidence_address(
    evidence: MbsGoldEvidence,
) -> tuple[str, int, str, str, str]:
    return (
        evidence.source_record_id,
        evidence.source_ordinal,
        evidence.source_sha256,
        evidence.receipt_sha256,
        evidence.catalog_version,
    )


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _node_id(
    kind: str,
    evidence: MbsGoldEvidence,
    fields: tuple[MbsGoldFieldEvidence, ...],
) -> str:
    return "mbs-gold-node:" + _digest({
        "kind": kind,
        "evidence": evidence.model_dump(),
        "fields": [field.model_dump() for field in fields],
    })


def _edge_id(source: str, target: str, evidence: MbsGoldEvidence) -> str:
    return "mbs-gold-edge:" + _digest({
        "kind": "source_record_has_benefit",
        "source": source,
        "target": target,
        "evidence": evidence.model_dump(),
    })


def _typed_text(value: object) -> str | None:
    return None if value is None else str(value)


def _fields(row: dict[str, Any]) -> tuple[MbsGoldFieldEvidence, ...]:
    evidence: list[MbsGoldFieldEvidence] = []
    for name, value in row.items():
        if not isinstance(value, dict) or "native_state" not in value:
            continue
        evidence.append(
            MbsGoldFieldEvidence.model_validate({
                "native_name": name,
                "native_state": value["native_state"],
                "native_value": value["native_value"],
                "conversion_status": value["conversion_status"],
                "typed_value": _typed_text(
                    cast("object", value["typed_value"])
                ),
            })
        )
    return tuple(sorted(evidence, key=lambda item: item.native_name))


def _rows(batches: Iterable[pa.RecordBatch]) -> list[dict[str, Any]]:
    return [row for batch in batches for row in batch.to_pylist()]


def _source_effective_bounds(
    receipt: SourceReceipt,
) -> tuple[datetime | None, datetime | None]:
    temporal = receipt.temporal
    if temporal is None:  # pragma: no cover - SourceReceipt invariant
        raise ValueError("MBS Gold candidate requires temporal evidence")
    return (
        receipt.effective_from
        or temporal.valid_from
        or temporal.source_effective_at,
        receipt.effective_to or temporal.valid_to,
    )


def _validate_admitted_silver_table(
    table: pa.Table,
    *,
    name: Literal["services", "benefits"],
    source: MbsGoldAdmittedSilverInput,
) -> None:
    metadata = table.schema.metadata or {}
    expected = {
        b"schema_name": f"global-medicines-atlas.mbs-silver.{name}".encode(),
        b"source_id": b"au-mbs",
        b"subject_kind": b"service",
        b"dimension": b"service_benefit",
        b"mapping_status": b"source_native",
        b"qualification": b"candidate",
        b"conversion_version": b"mbs-scalar-v2",
        b"source_receipt_sha256": source.receipt_sha256.encode(),
        b"rights_state": source.rights_state.value.encode(),
        b"evidence_class": b"live",
        b"schema_era": source.catalog_version.encode(),
    }
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError(
            "MBS Silver table metadata differs from admitted source"
        )
    if table.num_rows != source.source_record_count:
        raise ValueError("MBS Silver table row count differs from admission")
    for column in (
        "source_record_id",
        "source_ordinal",
        "source_sha256",
        "receipt_sha256",
    ):
        if column not in table.column_names:
            raise ValueError("MBS Silver table lacks source row identity")
    for column, expected in (
        ("source_sha256", source.source_sha256),
        ("receipt_sha256", source.receipt_sha256),
    ):
        if set(table[column].to_pylist()) != {expected}:
            raise ValueError(
                "MBS Silver row identity differs from admitted digests"
            )


def _admitted_record_pair(
    service_row: dict[str, Any],
    benefit_row: dict[str, Any],
    identity: tuple[str, int, str, str],
    source: MbsGoldAdmittedSilverInput,
    sensitivity: SensitivityClassification,
) -> tuple[tuple[MbsGoldNode, MbsGoldNode], MbsGoldEdge]:
    source_record_id, source_ordinal, source_sha256, receipt_sha256 = identity
    evidence = MbsGoldEvidence(
        source_record_id=source_record_id,
        source_ordinal=source_ordinal,
        source_sha256=source_sha256,
        receipt_sha256=receipt_sha256,
        catalog_version=source.catalog_version,
        rights_state=source.rights_state,
        sensitivity=sensitivity,
    )
    service_fields = _fields(service_row)
    benefit_fields = _fields(benefit_row)
    service_node = MbsGoldNode(
        node_id=_node_id("mbs_service_record", evidence, service_fields),
        kind="mbs_service_record",
        evidence=evidence,
        fields=service_fields,
    )
    benefit_node = MbsGoldNode(
        node_id=_node_id("mbs_benefit_record", evidence, benefit_fields),
        kind="mbs_benefit_record",
        evidence=evidence,
        fields=benefit_fields,
    )
    edge = MbsGoldEdge(
        edge_id=_edge_id(service_node.node_id, benefit_node.node_id, evidence),
        source_node_id=service_node.node_id,
        target_node_id=benefit_node.node_id,
        evidence=evidence,
        supporting_revisions=(source.catalog_version,),
        valid_time_status="source_snapshot_effective_date",
        source_snapshot_effective_date=source.source_effective_date,
        retrieved_at=source.retrieved_at,
        rights_state=source.rights_state,
        sensitivity=sensitivity,
    )
    return (service_node, benefit_node), edge


def _real_silver_candidate(
    nodes: list[MbsGoldNode],
    edges: list[MbsGoldEdge],
    source: MbsGoldAdmittedSilverInput,
) -> MbsGoldGraphCandidate:
    node_tuple = tuple(sorted(nodes, key=lambda item: item.node_id))
    edge_tuple = tuple(sorted(edges, key=lambda item: item.edge_id))
    provisional = MbsGoldGraphCandidate.model_construct(
        schema_version=ADMITTED_GRAPH_SCHEMA_VERSION,
        qualification="admitted_real_silver_candidate_only",
        input_admission_sha256=source.admission_sha256,
        input_semantic_manifest_sha256=source.semantic_manifest_sha256,
        source_record_count=len(edges),
        nodes=node_tuple,
        edges=edge_tuple,
        graph_sha256="0" * 64,
    )
    return MbsGoldGraphCandidate(
        schema_version=ADMITTED_GRAPH_SCHEMA_VERSION,
        qualification="admitted_real_silver_candidate_only",
        input_admission_sha256=source.admission_sha256,
        input_semantic_manifest_sha256=source.semantic_manifest_sha256,
        source_record_count=len(edges),
        nodes=node_tuple,
        edges=edge_tuple,
        graph_sha256=_digest(provisional.model_dump(exclude={"graph_sha256"})),
    )


def build_mbs_gold_graph_from_admitted_silver(
    services: pa.Table,
    benefits: pa.Table,
    source: MbsGoldAdmittedSilverInput,
) -> MbsGoldGraphCandidate:
    """Project source-record relationships from verified, admitted real MBS Silver."""
    source = MbsGoldAdmittedSilverInput.model_validate(source.model_dump())
    if source.rights_state is not RightsState.PERMITTED:
        raise ValueError(
            "real MBS Gold graph requires permitted admitted Silver"
        )
    _validate_admitted_silver_table(services, name="services", source=source)
    _validate_admitted_silver_table(benefits, name="benefits", source=source)
    service_rows = services.to_pylist()
    benefit_rows = benefits.to_pylist()
    if not service_rows or len(service_rows) != len(benefit_rows):
        raise ValueError("admitted MBS service and benefit denominators differ")
    keys = (
        "source_record_id",
        "source_ordinal",
        "source_sha256",
        "receipt_sha256",
    )
    services_by_identity = {
        tuple(row[key] for key in keys): row for row in service_rows
    }
    benefits_by_identity = {
        tuple(row[key] for key in keys): row for row in benefit_rows
    }
    if (
        len(services_by_identity) != len(service_rows)
        or len(benefits_by_identity) != len(benefit_rows)
        or services_by_identity.keys() != benefits_by_identity.keys()
    ):
        raise ValueError(
            "admitted MBS Silver row identities do not pair exactly"
        )
    nodes: list[MbsGoldNode] = []
    edges: list[MbsGoldEdge] = []
    sensitivity = SensitivityClassification()
    for identity in sorted(services_by_identity):
        pair, edge = _admitted_record_pair(
            services_by_identity[identity],
            benefits_by_identity[identity],
            identity,
            source,
            sensitivity,
        )
        nodes.extend(pair)
        edges.append(edge)
    return _real_silver_candidate(nodes, edges, source)


def build_mbs_gold_graph_candidate(
    payload: bytes, receipt: SourceReceipt
) -> MbsGoldGraphCandidate:
    """Build only explicit service/benefit record edges from synthetic Silver."""
    receipt = SourceReceipt.model_validate(receipt.model_dump())
    if receipt.evidence_class is not EvidenceClass.SYNTHETIC:
        raise ValueError("MBS Gold candidate requires synthetic evidence")
    service_rows = _rows(
        iter_mbs_silver_batches(payload, receipt, table="services")
    )
    benefit_rows = _rows(
        iter_mbs_silver_batches(payload, receipt, table="benefits")
    )
    if len(service_rows) != len(benefit_rows) or not service_rows:
        raise ValueError(
            "MBS Gold Silver denominators differ"
        )  # pragma: no cover - paired producer invariant
    nodes: list[MbsGoldNode] = []
    edges: list[MbsGoldEdge] = []
    for service_row, benefit_row in zip(
        service_rows, benefit_rows, strict=True
    ):
        keys = (
            "source_record_id",
            "source_ordinal",
            "source_sha256",
            "receipt_sha256",
        )
        if any(service_row[key] != benefit_row[key] for key in keys):
            raise ValueError(
                "MBS Gold Silver row evidence differs"
            )  # pragma: no cover - same receipt/table producer invariant
        evidence = MbsGoldEvidence(
            **{key: service_row[key] for key in keys},
            catalog_version=receipt.source.catalog_version,
            rights_state=receipt.rights_state,
            sensitivity=receipt.sensitivity or SensitivityClassification(),
        )
        service_fields = _fields(service_row)
        benefit_fields = _fields(benefit_row)
        service = MbsGoldNode(
            node_id=_node_id("mbs_service_record", evidence, service_fields),
            kind="mbs_service_record",
            evidence=evidence,
            fields=service_fields,
        )
        benefit = MbsGoldNode(
            node_id=_node_id("mbs_benefit_record", evidence, benefit_fields),
            kind="mbs_benefit_record",
            evidence=evidence,
            fields=benefit_fields,
        )
        edge = MbsGoldEdge(
            edge_id=_edge_id(service.node_id, benefit.node_id, evidence),
            source_node_id=service.node_id,
            target_node_id=benefit.node_id,
            evidence=evidence,
            supporting_revisions=(receipt.source.catalog_version,),
            source_effective_from=_source_effective_bounds(receipt)[0],
            source_effective_to=_source_effective_bounds(receipt)[1],
            retrieved_at=receipt.retrieval.retrieved_at,
            rights_state=receipt.rights_state,
            sensitivity=receipt.sensitivity or SensitivityClassification(),
        )
        nodes.extend((service, benefit))
        edges.append(edge)
    node_tuple = tuple(sorted(nodes, key=lambda item: item.node_id))
    edge_tuple = tuple(sorted(edges, key=lambda item: item.edge_id))
    provisional = MbsGoldGraphCandidate.model_construct(
        source_record_count=len(service_rows),
        nodes=node_tuple,
        edges=edge_tuple,
        graph_sha256="0" * 64,
    )
    return MbsGoldGraphCandidate(
        source_record_count=len(service_rows),
        nodes=node_tuple,
        edges=edge_tuple,
        graph_sha256=_digest(provisional.model_dump(exclude={"graph_sha256"})),
    )


MBS_GOLD_NODE_SCHEMA = pa.schema(
    [
        pa.field("node_id", pa.string(), nullable=False),
        pa.field("kind", pa.string(), nullable=False),
        pa.field("evidence_json", pa.string(), nullable=False),
        pa.field("fields_json", pa.string(), nullable=False),
    ],
    metadata={
        "schema_name": "global-medicines-atlas.mbs-gold.nodes",
        "schema_version": "2.0",
        "qualification": "synthetic_silver_candidate_only",
    },
)
MBS_GOLD_EDGE_SCHEMA = pa.schema(
    [
        pa.field("edge_id", pa.string(), nullable=False),
        pa.field("kind", pa.string(), nullable=False),
        pa.field("source_node_id", pa.string(), nullable=False),
        pa.field("target_node_id", pa.string(), nullable=False),
        pa.field("evidence_json", pa.string(), nullable=False),
        pa.field("assertion_basis", pa.string(), nullable=False),
        pa.field("inferred", pa.bool_(), nullable=False),
        pa.field("controls_json", pa.string(), nullable=False),
    ],
    metadata={
        "schema_name": "global-medicines-atlas.mbs-gold.edges",
        "schema_version": "2.0",
        "qualification": "synthetic_silver_candidate_only",
    },
)


def project_mbs_gold_graph_arrow(
    graph: MbsGoldGraphCandidate,
) -> tuple[pa.Table, pa.Table]:
    """Return deterministic Arrow projections of a validated candidate graph."""
    graph = MbsGoldGraphCandidate.model_validate(graph.model_dump())
    admitted_bindings: dict[bytes, bytes] = {}
    if graph.qualification == "admitted_real_silver_candidate_only":
        admission_sha256 = cast("str", graph.input_admission_sha256)
        semantic_manifest_sha256 = cast(
            "str", graph.input_semantic_manifest_sha256
        )
        admitted_bindings = {
            b"input_admission_sha256": admission_sha256.encode(),
            b"input_semantic_manifest_sha256": (
                semantic_manifest_sha256.encode()
            ),
            b"graph_sha256": graph.graph_sha256.encode(),
        }
    projection_metadata = {
        **(MBS_GOLD_NODE_SCHEMA.metadata or {}),
        b"qualification": graph.qualification.encode(),
        b"schema_version": f"{graph.schema_version}.0".encode(),
        **admitted_bindings,
    }
    edge_projection_metadata = {
        **(MBS_GOLD_EDGE_SCHEMA.metadata or {}),
        b"qualification": graph.qualification.encode(),
        b"schema_version": f"{graph.schema_version}.0".encode(),
        **admitted_bindings,
    }
    node_schema = cast(
        "pa.Schema",
        cast("Any", MBS_GOLD_NODE_SCHEMA).with_metadata(projection_metadata),
    )
    edge_schema = cast(
        "pa.Schema",
        cast("Any", MBS_GOLD_EDGE_SCHEMA).with_metadata(
            edge_projection_metadata
        ),
    )
    nodes = pa.Table.from_pylist(
        [
            {
                "node_id": node.node_id,
                "kind": node.kind,
                "evidence_json": _canonical(
                    node.evidence.model_dump()
                ).decode(),
                "fields_json": _canonical([
                    field.model_dump() for field in node.fields
                ]).decode(),
            }
            for node in graph.nodes
        ],
        schema=node_schema,
    )
    edges = pa.Table.from_pylist(
        [
            {
                "edge_id": edge.edge_id,
                "kind": edge.kind,
                "source_node_id": edge.source_node_id,
                "target_node_id": edge.target_node_id,
                "evidence_json": _canonical(
                    edge.evidence.model_dump()
                ).decode(),
                "assertion_basis": edge.assertion_basis,
                "inferred": edge.inferred,
                "controls_json": _canonical(
                    edge.model_dump(
                        exclude={
                            "edge_id",
                            "kind",
                            "source_node_id",
                            "target_node_id",
                            "evidence",
                            "assertion_basis",
                            "inferred",
                        }
                    )
                ).decode(),
            }
            for edge in graph.edges
        ],
        schema=edge_schema,
    )
    return nodes, edges
