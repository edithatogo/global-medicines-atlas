"""Evidence-bound PBS graph candidates over synthetic Silver entities.

The graph represents XML containment only.  Native structural classifications
remain independent candidate dimensions and never become funding, formulary,
regulatory, medicine-identity, or terminology-equivalence assertions.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal

import pyarrow as pa
from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from .models import FrozenModel
from .pbs_entities import iter_pbs_entity_batches
from .receipts import (
    EvidenceClass,
    RightsState,
    SensitivityClassification,
    SourceReceipt,
)

NodeDimension = Literal[
    "source_document",
    "schedule_structure",
    "pbs_item_structure",
    "presentation_structure",
    "restriction_structure",
    "terminology_reference_structure",
    "classification_reference_structure",
    "unmapped_source_structure",
]


class PbsGoldFieldEvidence(FrozenModel):
    """One complete source-faithful Silver field occurrence."""

    source_field_id: str = Field(min_length=1)
    source_ordinal: int = Field(strict=True, ge=0)
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_id: Literal["au-pbs"] = "au-pbs"
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_era: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    schema_path: str = Field(min_length=1)
    value: str | None
    state: Literal["null", "value"]
    mapping_target: Literal[
        "schedules",
        "items",
        "presentations",
        "restrictions",
        "amt_references",
        "classifications",
        "unmapped",
    ]
    mapping_status: Literal["source_structure", "unmapped"]
    item_occurrence_id: str | None

    @model_validator(mode="after")
    def state_and_identity_are_bound(self) -> PbsGoldFieldEvidence:
        if (self.state == "value") != (self.value is not None):
            raise ValueError("PBS Gold field state differs from value")
        if self.source_field_id != f"{self.source_sha256}:{self.path}":
            raise ValueError("PBS Gold field identity differs from lineage")
        expected_status = (
            "unmapped"
            if self.mapping_target == "unmapped"
            else "source_structure"
        )
        if self.mapping_status != expected_status:
            raise ValueError("PBS Gold field structural mapping differs")
        return self


class PbsGoldEvidence(FrozenModel):
    """Exact B1/B2, schema-era, entity, row, and field denominator evidence."""

    source_id: Literal["au-pbs"] = "au-pbs"
    entity_id: str = Field(min_length=1)
    parent_entity_id: str | None
    source_record_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_era: str = Field(min_length=1)
    first_source_ordinal: int = Field(strict=True, ge=0)
    last_source_ordinal: int = Field(strict=True, ge=0)
    field_count: int = Field(strict=True, ge=1)
    fields_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def ordinal_denominator_is_possible(self) -> PbsGoldEvidence:
        if (
            self.last_source_ordinal - self.first_source_ordinal + 1
            != self.field_count
        ):
            raise ValueError("PBS Gold field ordinal denominator differs")
        if self.entity_id != f"{self.source_sha256}:{self.source_record_id}":
            raise ValueError("PBS Gold entity identity differs from B2")
        expected_parent = _source_parent_entity_id(
            self.source_sha256, self.source_record_id
        )
        if self.parent_entity_id != expected_parent:
            raise ValueError("PBS Gold parent identity differs from B2")
        return self


class PbsGoldNode(FrozenModel):
    """One source-entity candidate retaining all of its Silver fields."""

    node_id: str = Field(pattern=r"^pbs-gold-node:[0-9a-f]{64}$")
    kind: Literal["pbs_native_entity"] = "pbs_native_entity"
    semantic_dimension: NodeDimension
    evidence: PbsGoldEvidence
    fields: tuple[PbsGoldFieldEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def fields_and_identity_are_bound(self) -> PbsGoldNode:
        ordinals = tuple(field.source_ordinal for field in self.fields)
        expected = tuple(
            range(
                self.evidence.first_source_ordinal,
                self.evidence.last_source_ordinal + 1,
            )
        )
        if len(self.fields) != self.evidence.field_count:
            raise ValueError("PBS Gold node field denominator differs")
        if ordinals != expected:
            raise ValueError(
                "PBS Gold node fields are not ordered and contiguous"
            )
        if (
            _digest([field.model_dump() for field in self.fields])
            != self.evidence.fields_sha256
        ):
            raise ValueError("PBS Gold node fields differ from evidence")
        for field in self.fields:
            if (
                field.source_id != self.evidence.source_id
                or field.source_sha256 != self.evidence.source_sha256
                or field.receipt_sha256 != self.evidence.receipt_sha256
                or field.schema_era != self.evidence.schema_era
                or field.record_id != self.evidence.source_record_id
            ):
                raise ValueError("PBS Gold node field lineage differs")
        targets = {field.mapping_target for field in self.fields}
        if len(targets) != 1:
            raise ValueError("PBS Gold node structural dimension is ambiguous")
        expected_dimension = _dimension(
            self.evidence.parent_entity_id, next(iter(targets))
        )
        if self.semantic_dimension != expected_dimension:
            raise ValueError("PBS Gold node structural dimension differs")
        if self.node_id != _node_id(
            self.semantic_dimension, self.evidence, self.fields
        ):
            raise ValueError("PBS Gold node identity differs from evidence")
        return self


class PbsGoldEdge(FrozenModel):
    """One explicit source-tree containment edge, never an inferred link."""

    edge_id: str = Field(pattern=r"^pbs-gold-edge:[0-9a-f]{64}$")
    kind: Literal["source_contains_entity"] = "source_contains_entity"
    source_node_id: str = Field(pattern=r"^pbs-gold-node:[0-9a-f]{64}$")
    target_node_id: str = Field(pattern=r"^pbs-gold-node:[0-9a-f]{64}$")
    semantic_dimension: Literal["source_structure"] = "source_structure"
    mapping_method: Literal["source-explicit"] = "source-explicit"
    confidence: None = None
    confidence_calibration: Literal["not_applicable_source_structure"] = (
        "not_applicable_source_structure"
    )
    review_state: Literal["not_reviewed"] = "not_reviewed"
    evidence: PbsGoldEvidence
    supporting_source_ids: tuple[Literal["au-pbs"], ...] = ("au-pbs",)
    supporting_revisions: tuple[str, ...] = Field(min_length=1, max_length=1)
    supporting_native_rows: tuple[str, ...] = Field(min_length=1, max_length=1)
    supporting_native_paths: tuple[str, ...] = Field(min_length=1)
    valid_time_status: Literal["unselected"] = "unselected"
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
    comparison_validity: Literal["source_structure_only"] = (
        "source_structure_only"
    )
    inferred: Literal[False] = False

    @model_validator(mode="after")
    def content_is_bound(self) -> PbsGoldEdge:
        if self.source_node_id == self.target_node_id:
            raise ValueError("PBS Gold self-edge is invalid")
        if self.supporting_revisions != (self.evidence.schema_era,):
            raise ValueError("PBS Gold edge revision differs from evidence")
        if self.supporting_native_rows != (self.evidence.entity_id,):
            raise ValueError("PBS Gold edge native row differs from evidence")
        if self.contradiction_edge_ids or self.supersedes_edge_ids:
            raise ValueError("PBS Gold candidate cannot assert graph history")
        if self.edge_id != _edge_id(
            self.source_node_id, self.target_node_id, self.evidence
        ):
            raise ValueError("PBS Gold edge identity differs from evidence")
        return self


class PbsGoldGraphCandidate(FrozenModel):
    """Closed candidate graph of all source-native PBS XML entities."""

    model_config = ConfigDict(revalidate_instances="always")
    schema_id: Literal["global-medicines-atlas.pbs-gold-graph-candidate"] = (
        "global-medicines-atlas.pbs-gold-graph-candidate"
    )
    schema_version: Literal[1] = 1
    qualification: Literal["synthetic_silver_candidate_only"] = (
        "synthetic_silver_candidate_only"
    )
    asserted_dimensions: tuple[()] = ()
    admission_performed: Literal[False] = False
    inference_performed: Literal[False] = False
    terminology_resolution_performed: Literal[False] = False
    publication_performed: Literal[False] = False
    source_entity_count: int = Field(strict=True, ge=1)
    source_root_count: int = Field(strict=True, ge=1)
    nodes: tuple[PbsGoldNode, ...]
    edges: tuple[PbsGoldEdge, ...]
    graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def graph_is_closed_and_bound(self) -> PbsGoldGraphCandidate:
        if (
            tuple(sorted(self.nodes, key=lambda item: item.node_id))
            != self.nodes
        ):
            raise ValueError("PBS Gold nodes are not deterministic")
        if (
            tuple(sorted(self.edges, key=lambda item: item.edge_id))
            != self.edges
        ):
            raise ValueError("PBS Gold edges are not deterministic")
        by_id = {node.node_id: node for node in self.nodes}
        by_entity = {node.evidence.entity_id: node for node in self.nodes}
        if len(by_id) != len(self.nodes) or len(by_entity) != len(self.nodes):
            raise ValueError("PBS Gold node identity is ambiguous")
        if len({edge.edge_id for edge in self.edges}) != len(self.edges):
            raise ValueError("PBS Gold edge identity is ambiguous")
        roots = [
            node
            for node in self.nodes
            if node.evidence.parent_entity_id is None
        ]
        if (
            len(self.nodes) != self.source_entity_count
            or len(roots) != self.source_root_count
            or len(self.edges)
            != self.source_entity_count - self.source_root_count
        ):
            raise ValueError("PBS Gold graph denominator differs from Silver")
        for edge in self.edges:
            source = by_id.get(edge.source_node_id)
            target = by_id.get(edge.target_node_id)
            if source is None or target is None:
                raise ValueError("PBS Gold edge endpoint is absent")
            if (
                target.evidence.parent_entity_id != source.evidence.entity_id
                or edge.evidence != target.evidence
                or edge.supporting_native_paths
                != tuple(field.path for field in target.fields)
            ):
                raise ValueError("PBS Gold edge is not source-parent supported")
        if self.graph_sha256 != _digest(
            self.model_dump(exclude={"graph_sha256"})
        ):
            raise ValueError("PBS Gold graph digest differs")
        return self


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


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _source_parent_entity_id(
    source_sha256: str, source_record_id: str
) -> str | None:
    """Derive the exact XML parent identity from a native record path."""
    element_path, ordinal_separator, _ordinal = source_record_id.rpartition("/")
    parent_path, element_separator, _element = element_path.rpartition("/")
    if not ordinal_separator or not element_separator or not parent_path:
        return None
    return f"{source_sha256}:{parent_path}"


def _node_id(
    dimension: str,
    evidence: PbsGoldEvidence,
    fields: tuple[PbsGoldFieldEvidence, ...],
) -> str:
    return "pbs-gold-node:" + _digest({
        "dimension": dimension,
        "evidence": evidence.model_dump(),
        "fields": [field.model_dump() for field in fields],
    })


def _edge_id(source: str, target: str, evidence: PbsGoldEvidence) -> str:
    return "pbs-gold-edge:" + _digest({
        "kind": "source_contains_entity",
        "source": source,
        "target": target,
        "evidence": evidence.model_dump(),
    })


def _dimension(parent_entity_id: str | None, target: str) -> NodeDimension:
    if parent_entity_id is None:
        return "source_document"
    by_target: dict[str, NodeDimension] = {
        "schedules": "schedule_structure",
        "items": "pbs_item_structure",
        "presentations": "presentation_structure",
        "restrictions": "restriction_structure",
        "prices": "price_structure",
        "amt_references": "terminology_reference_structure",
        "classifications": "classification_reference_structure",
        "unmapped": "unmapped_source_structure",
    }
    # Closed mapping_target validation makes this lookup total.
    return by_target[target]


def _rows(batches: Iterable[pa.RecordBatch]) -> list[dict[str, Any]]:
    return [row for batch in batches for row in batch.to_pylist()]


def build_pbs_gold_graph_candidate(
    payload: bytes, receipt: SourceReceipt
) -> PbsGoldGraphCandidate:
    """Build a source-containment-only graph from synthetic PBS Silver."""
    receipt = SourceReceipt.model_validate(receipt.model_dump())
    if receipt.evidence_class is not EvidenceClass.SYNTHETIC:
        raise ValueError("PBS Gold candidate requires synthetic evidence")
    rows = _rows(iter_pbs_entity_batches(payload, receipt))
    if not rows:
        raise ValueError("PBS Gold candidate requires source entities")
    nodes: list[PbsGoldNode] = []
    for row in rows:
        fields = tuple(
            PbsGoldFieldEvidence.model_validate(field)
            for field in row["native_fields"]
        )
        evidence = PbsGoldEvidence(
            entity_id=row["entity_id"],
            parent_entity_id=row["parent_entity_id"],
            source_record_id=fields[0].record_id,
            source_sha256=fields[0].source_sha256,
            receipt_sha256=fields[0].receipt_sha256,
            schema_era=fields[0].schema_era,
            first_source_ordinal=fields[0].source_ordinal,
            last_source_ordinal=fields[-1].source_ordinal,
            field_count=len(fields),
            fields_sha256=_digest([field.model_dump() for field in fields]),
        )
        dimension = _dimension(row["parent_entity_id"], row["mapping_target"])
        nodes.append(
            PbsGoldNode(
                node_id=_node_id(dimension, evidence, fields),
                semantic_dimension=dimension,
                evidence=evidence,
                fields=fields,
            )
        )
    by_entity = {node.evidence.entity_id: node for node in nodes}
    edges: list[PbsGoldEdge] = []
    for node in nodes:
        parent_id = node.evidence.parent_entity_id
        if parent_id is None:
            continue
        parent = by_entity.get(parent_id)
        if parent is None:
            raise ValueError("PBS Gold Silver parent entity is absent")
        edges.append(
            PbsGoldEdge(
                edge_id=_edge_id(parent.node_id, node.node_id, node.evidence),
                source_node_id=parent.node_id,
                target_node_id=node.node_id,
                evidence=node.evidence,
                supporting_revisions=(node.evidence.schema_era,),
                supporting_native_rows=(node.evidence.entity_id,),
                supporting_native_paths=tuple(
                    field.path for field in node.fields
                ),
                source_effective_from=receipt.effective_from,
                source_effective_to=receipt.effective_to,
                retrieved_at=receipt.retrieval.retrieved_at,
                rights_state=receipt.rights_state,
                sensitivity=receipt.sensitivity or SensitivityClassification(),
            )
        )
    node_tuple = tuple(sorted(nodes, key=lambda item: item.node_id))
    edge_tuple = tuple(sorted(edges, key=lambda item: item.edge_id))
    root_count = sum(node.evidence.parent_entity_id is None for node in nodes)
    provisional = PbsGoldGraphCandidate.model_construct(
        source_entity_count=len(nodes),
        source_root_count=root_count,
        nodes=node_tuple,
        edges=edge_tuple,
        graph_sha256="0" * 64,
    )
    return PbsGoldGraphCandidate(
        source_entity_count=len(nodes),
        source_root_count=root_count,
        nodes=node_tuple,
        edges=edge_tuple,
        graph_sha256=_digest(provisional.model_dump(exclude={"graph_sha256"})),
    )


PBS_GOLD_NODE_SCHEMA = pa.schema(
    [
        pa.field("node_id", pa.string(), nullable=False),
        pa.field("kind", pa.string(), nullable=False),
        pa.field("semantic_dimension", pa.string(), nullable=False),
        pa.field("evidence_json", pa.string(), nullable=False),
        pa.field("fields_json", pa.string(), nullable=False),
    ],
    metadata={
        "schema_name": "global-medicines-atlas.pbs-gold.nodes",
        "schema_version": "1.0",
        "qualification": "synthetic_silver_candidate_only",
        "asserted_dimensions": "none",
    },
)
PBS_GOLD_EDGE_SCHEMA = pa.schema(
    [
        pa.field("edge_id", pa.string(), nullable=False),
        pa.field("kind", pa.string(), nullable=False),
        pa.field("source_node_id", pa.string(), nullable=False),
        pa.field("target_node_id", pa.string(), nullable=False),
        pa.field("semantic_dimension", pa.string(), nullable=False),
        pa.field("mapping_method", pa.string(), nullable=False),
        pa.field("confidence", pa.float64()),
        pa.field("review_state", pa.string(), nullable=False),
        pa.field("evidence_json", pa.string(), nullable=False),
        pa.field("controls_json", pa.string(), nullable=False),
    ],
    metadata={
        "schema_name": "global-medicines-atlas.pbs-gold.edges",
        "schema_version": "1.0",
        "qualification": "synthetic_silver_candidate_only",
        "asserted_dimensions": "source_structure_only",
    },
)


def project_pbs_gold_graph_arrow(
    graph: PbsGoldGraphCandidate,
) -> tuple[pa.Table, pa.Table]:
    """Return deterministic Arrow projections of a validated PBS candidate."""
    graph = PbsGoldGraphCandidate.model_validate(graph.model_dump())
    nodes = pa.Table.from_pylist(
        [
            {
                "node_id": node.node_id,
                "kind": node.kind,
                "semantic_dimension": node.semantic_dimension,
                "evidence_json": _canonical(
                    node.evidence.model_dump()
                ).decode(),
                "fields_json": _canonical([
                    field.model_dump() for field in node.fields
                ]).decode(),
            }
            for node in graph.nodes
        ],
        schema=PBS_GOLD_NODE_SCHEMA,
    )
    edges = pa.Table.from_pylist(
        [
            {
                "edge_id": edge.edge_id,
                "kind": edge.kind,
                "source_node_id": edge.source_node_id,
                "target_node_id": edge.target_node_id,
                "semantic_dimension": edge.semantic_dimension,
                "mapping_method": edge.mapping_method,
                "confidence": edge.confidence,
                "review_state": edge.review_state,
                "evidence_json": _canonical(
                    edge.evidence.model_dump()
                ).decode(),
                "controls_json": _canonical(
                    edge.model_dump(
                        exclude={
                            "edge_id",
                            "kind",
                            "source_node_id",
                            "target_node_id",
                            "semantic_dimension",
                            "mapping_method",
                            "confidence",
                            "review_state",
                            "evidence",
                        }
                    )
                ).decode(),
            }
            for edge in graph.edges
        ],
        schema=PBS_GOLD_EDGE_SCHEMA,
    )
    return nodes, edges
