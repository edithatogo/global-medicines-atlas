"""Source-explicit Australian document and organization Gold candidates.

The organization node preserves only the authority label declared by a source
receipt. It is not a canonical legal-entity resolution or an endorsement.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

import pyarrow as pa
from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from .models import FrozenModel
from .receipts import (
    EvidenceClass,
    RightsState,
    SensitivityClassification,
    SourceReceipt,
)

AustralianSourceId = Literal["au-mbs", "au-pbs"]
ProvenanceNodeKind = Literal["source_document", "source_declared_organization"]
IdentityStatus = Literal[
    "exact_source_payload", "source_declared_label_not_canonical"
]
EXPECTED_NODE_COUNT = 2


class AustralianGoldProvenanceEvidence(FrozenModel):
    """Exact receipt and payload identity supporting provenance candidates."""

    source_id: AustralianSourceId
    receipt_id: str = Field(min_length=1)
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalog_version: str = Field(min_length=1)


class AustralianGoldProvenanceNode(FrozenModel):
    """A source document or explicitly non-canonical authority label."""

    node_id: str = Field(pattern=r"^australian-gold-node:[0-9a-f]{64}$")
    kind: ProvenanceNodeKind
    label: str = Field(min_length=1)
    identity_status: IdentityStatus
    evidence: AustralianGoldProvenanceEvidence

    @model_validator(mode="after")
    def identity_is_bound(self) -> AustralianGoldProvenanceNode:
        expected_status: IdentityStatus = (
            "exact_source_payload"
            if self.kind == "source_document"
            else "source_declared_label_not_canonical"
        )
        if self.identity_status != expected_status:
            raise ValueError("Australian provenance node status differs")
        if self.node_id != _node_id(
            self.kind, self.label, self.identity_status, self.evidence
        ):
            raise ValueError("Australian provenance node identity differs")
        return self


class AustralianGoldProvenanceEdge(FrozenModel):
    """A receipt-explicit document-to-declared-authority relationship."""

    edge_id: str = Field(pattern=r"^australian-gold-edge:[0-9a-f]{64}$")
    kind: Literal["source_declares_authority"] = "source_declares_authority"
    source_node_id: str = Field(pattern=r"^australian-gold-node:[0-9a-f]{64}$")
    target_node_id: str = Field(pattern=r"^australian-gold-node:[0-9a-f]{64}$")
    semantic_dimension: Literal["source_provenance"] = "source_provenance"
    mapping_method: Literal["source-explicit"] = "source-explicit"
    confidence: None = None
    confidence_calibration: Literal["not_applicable_source_declaration"] = (
        "not_applicable_source_declaration"
    )
    review_state: Literal["not_reviewed"] = "not_reviewed"
    evidence: AustralianGoldProvenanceEvidence
    supporting_source_ids: tuple[AustralianSourceId, ...]
    supporting_revisions: tuple[str, ...] = Field(min_length=1, max_length=1)
    supporting_native_paths: tuple[Literal["source.authority"], ...] = (
        "source.authority",
    )
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
    comparison_validity: Literal["source_provenance_only"] = (
        "source_provenance_only"
    )
    inferred: Literal[False] = False

    @model_validator(mode="after")
    def evidence_and_identity_are_bound(self) -> AustralianGoldProvenanceEdge:
        if self.source_node_id == self.target_node_id:
            raise ValueError("Australian provenance self-edge is invalid")
        if self.supporting_source_ids != (self.evidence.source_id,):
            raise ValueError("Australian provenance source support differs")
        if self.supporting_revisions != (self.evidence.catalog_version,):
            raise ValueError("Australian provenance revision support differs")
        if self.contradiction_edge_ids or self.supersedes_edge_ids:
            raise ValueError("Australian provenance history is not asserted")
        if self.edge_id != _edge_id(self.model_dump(exclude={"edge_id"})):
            raise ValueError("Australian provenance edge identity differs")
        return self


class AustralianGoldProvenanceCandidate(FrozenModel):
    """Closed two-node candidate preserving one receipt authority declaration."""

    model_config = ConfigDict(revalidate_instances="always")
    schema_id: Literal[
        "global-medicines-atlas.australian-gold-provenance-candidate"
    ] = "global-medicines-atlas.australian-gold-provenance-candidate"
    schema_version: Literal[1] = 1
    qualification: Literal["synthetic_source_identity_candidate_only"] = (
        "synthetic_source_identity_candidate_only"
    )
    asserted_dimensions: tuple[()] = ()
    admission_performed: Literal[False] = False
    inference_performed: Literal[False] = False
    publication_performed: Literal[False] = False
    nodes: tuple[AustralianGoldProvenanceNode, ...]
    edges: tuple[AustralianGoldProvenanceEdge, ...]
    graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def graph_is_closed_and_bound(self) -> AustralianGoldProvenanceCandidate:
        if (
            tuple(sorted(self.nodes, key=lambda node: node.node_id))
            != self.nodes
        ):
            raise ValueError(
                "Australian provenance nodes are not deterministic"
            )
        if len(self.nodes) != EXPECTED_NODE_COUNT or len(self.edges) != 1:
            raise ValueError("Australian provenance graph denominator differs")
        by_id = {node.node_id: node for node in self.nodes}
        if len(by_id) != len(self.nodes):
            raise ValueError("Australian provenance node identity is ambiguous")
        source = by_id.get(self.edges[0].source_node_id)
        target = by_id.get(self.edges[0].target_node_id)
        if source is None or target is None:
            raise ValueError("Australian provenance edge support differs")
        if (
            source.kind != "source_document"
            or target.kind != "source_declared_organization"
            or source.evidence != target.evidence
            or self.edges[0].evidence != source.evidence
        ):
            raise ValueError("Australian provenance edge support differs")
        if self.graph_sha256 != _digest(
            self.model_dump(exclude={"graph_sha256"})
        ):
            raise ValueError("Australian provenance graph digest differs")
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


def _node_id(
    kind: str,
    label: str,
    identity_status: str,
    evidence: AustralianGoldProvenanceEvidence,
) -> str:
    return "australian-gold-node:" + _digest({
        "kind": kind,
        "label": label,
        "identity_status": identity_status,
        "evidence": evidence.model_dump(),
    })


def _edge_id(content: object) -> str:
    return "australian-gold-edge:" + _digest(content)


def build_australian_gold_provenance_candidate(
    receipt: SourceReceipt | object,
) -> AustralianGoldProvenanceCandidate:
    """Project a synthetic receipt's exact source authority declaration."""
    receipt = SourceReceipt.model_validate(receipt)
    if receipt.evidence_class is not EvidenceClass.SYNTHETIC:
        raise ValueError(
            "Australian provenance candidate requires synthetic evidence"
        )
    if receipt.source.source_id not in {"au-mbs", "au-pbs"}:
        raise ValueError(
            "Australian provenance requires an Australian benefits source"
        )
    source_id: AustralianSourceId = receipt.source.source_id  # pyright: ignore[reportAssignmentType]
    evidence = AustralianGoldProvenanceEvidence(
        source_id=source_id,
        receipt_id=receipt.receipt_id,
        receipt_sha256=receipt.digest(),
        source_sha256=receipt.payload.sha256,
        catalog_version=receipt.source.catalog_version,
    )
    document = AustralianGoldProvenanceNode(
        node_id=_node_id(
            "source_document",
            receipt.source.dataset_title,
            "exact_source_payload",
            evidence,
        ),
        kind="source_document",
        label=receipt.source.dataset_title,
        identity_status="exact_source_payload",
        evidence=evidence,
    )
    authority = AustralianGoldProvenanceNode(
        node_id=_node_id(
            "source_declared_organization",
            receipt.source.authority,
            "source_declared_label_not_canonical",
            evidence,
        ),
        kind="source_declared_organization",
        label=receipt.source.authority,
        identity_status="source_declared_label_not_canonical",
        evidence=evidence,
    )
    edge_data = {
        "kind": "source_declares_authority",
        "source_node_id": document.node_id,
        "target_node_id": authority.node_id,
        "semantic_dimension": "source_provenance",
        "mapping_method": "source-explicit",
        "confidence": None,
        "confidence_calibration": "not_applicable_source_declaration",
        "review_state": "not_reviewed",
        "evidence": evidence.model_dump(),
        "supporting_source_ids": (source_id,),
        "supporting_revisions": (evidence.catalog_version,),
        "supporting_native_paths": ("source.authority",),
        "valid_time_status": "unselected",
        "source_effective_from": receipt.effective_from,
        "source_effective_to": receipt.effective_to,
        "retrieved_at": receipt.retrieval.retrieved_at,
        "rights_state": receipt.rights_state,
        "sensitivity": (
            receipt.sensitivity or SensitivityClassification()
        ).model_dump(),
        "contradiction_edge_ids": (),
        "supersedes_edge_ids": (),
        "negative_control_outcome": "not_applicable",
        "comparison_validity": "source_provenance_only",
        "inferred": False,
    }
    edge = AustralianGoldProvenanceEdge.model_validate({
        "edge_id": _edge_id(edge_data),
        **edge_data,
    })
    nodes = tuple(sorted((document, authority), key=lambda node: node.node_id))
    edges = (edge,)
    provisional = AustralianGoldProvenanceCandidate.model_construct(
        nodes=nodes, edges=edges, graph_sha256="0" * 64
    )
    return AustralianGoldProvenanceCandidate(
        nodes=nodes,
        edges=edges,
        graph_sha256=_digest(provisional.model_dump(exclude={"graph_sha256"})),
    )


AUSTRALIAN_GOLD_PROVENANCE_NODE_SCHEMA = pa.schema(
    [
        pa.field("node_id", pa.string(), nullable=False),
        pa.field("kind", pa.string(), nullable=False),
        pa.field("label", pa.string(), nullable=False),
        pa.field("identity_status", pa.string(), nullable=False),
        pa.field("evidence_json", pa.string(), nullable=False),
    ],
    metadata={
        "schema_name": "global-medicines-atlas.australian-gold.provenance-nodes",
        "schema_version": "1.0",
        "qualification": "synthetic_source_identity_candidate_only",
    },
)
AUSTRALIAN_GOLD_PROVENANCE_EDGE_SCHEMA = pa.schema(
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
        "schema_name": "global-medicines-atlas.australian-gold.provenance-edges",
        "schema_version": "1.0",
        "qualification": "synthetic_source_identity_candidate_only",
    },
)


def project_australian_gold_provenance_arrow(
    graph: AustralianGoldProvenanceCandidate,
) -> tuple[pa.Table, pa.Table]:
    """Return deterministic Arrow projections after full graph revalidation."""
    graph = AustralianGoldProvenanceCandidate.model_validate(graph.model_dump())
    nodes = pa.Table.from_pylist(
        [
            {
                "node_id": node.node_id,
                "kind": node.kind,
                "label": node.label,
                "identity_status": node.identity_status,
                "evidence_json": _canonical(
                    node.evidence.model_dump()
                ).decode(),
            }
            for node in graph.nodes
        ],
        schema=AUSTRALIAN_GOLD_PROVENANCE_NODE_SCHEMA,
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
        schema=AUSTRALIAN_GOLD_PROVENANCE_EDGE_SCHEMA,
    )
    return nodes, edges
