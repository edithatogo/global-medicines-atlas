"""Contract-typed candidate projection for the admitted MBS Gold graph.

The graph stores typed representations as serialized text. This adapter
restores only field-contract-bound Decimal/date/string types from those
already-converted values and keeps native text beside them. It does not parse
source values or establish federation v4 admission or product trust.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import cast

import pyarrow as pa

from .australian_source_contracts import (
    MbsFieldContract,
    ValueType,
    mbs_field_contracts,
)
from .mbs_gold_graph import (
    MbsGoldEdge,
    MbsGoldFieldEvidence,
    MbsGoldGraphCandidate,
    MbsGoldNode,
)
from .receipts import (
    SensitivityClassification,
    SourceReceipt,
    TemporalIdentity,
)

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CONTRACTS = {field.native_name: field for field in mbs_field_contracts()}
_DECIMAL_TYPES = frozenset({"aud_decimal", "decimal", "percentage"})
_TEXT_TYPES = frozenset({"identifier", "source_code", "source_text"})
_MBS_XML_V3 = "2025-07-version-3"


def _validate_receipt_binding(
    graph: MbsGoldGraphCandidate, source_receipt: SourceReceipt
) -> TemporalIdentity:
    if graph.qualification != "admitted_real_silver_candidate_only":
        raise ValueError("scalar candidate requires admitted real Silver graph")
    if source_receipt.temporal is None:
        raise ValueError("source receipt lacks acquisition identity")
    receipt_binding = (
        source_receipt.digest(),
        source_receipt.payload.sha256,
        source_receipt.source.source_id,
        source_receipt.source.catalog_version,
        source_receipt.rights_state,
    )
    for evidence in (node.evidence for node in graph.nodes):
        graph_binding = (
            evidence.receipt_sha256,
            evidence.source_sha256,
            evidence.source_id,
            evidence.catalog_version,
            evidence.rights_state,
        )
        if receipt_binding != graph_binding:
            raise ValueError("source receipt differs from Gold graph evidence")
    return source_receipt.temporal


def _validate_field_contract(
    graph: MbsGoldGraphCandidate,
) -> dict[str, tuple[str, ...]]:
    fields: dict[str, tuple[str, ...]] = {}
    for kind in ("mbs_service_record", "mbs_benefit_record"):
        nodes = [node for node in graph.nodes if node.kind == kind]
        if not nodes:
            raise ValueError("Gold graph is missing a required node class")
        names = tuple(field.native_name for field in nodes[0].fields)
        if any(
            tuple(field.native_name for field in n.fields) != names
            for n in nodes
        ):
            raise ValueError("Gold graph field denominator differs by record")
        if any(not _IDENTIFIER.fullmatch(name) for name in names):
            raise ValueError("Gold field name cannot form a scalar column")
        target = "services" if kind == "mbs_service_record" else "benefits"
        if any(
            name not in _CONTRACTS or _CONTRACTS[name].target_table != target
            for name in names
        ):
            raise ValueError("Gold field differs from its MBS table contract")
        fields[kind] = names
    return fields


def _arrow_type(value_type: ValueType) -> pa.DataType:
    if value_type == "source_date":
        return pa.date32()
    if value_type in _DECIMAL_TYPES:
        return pa.decimal128(38, 9)
    return pa.string()


def _field_columns(
    fields: dict[str, tuple[str, ...]],
) -> list[pa.Field[pa.DataType]]:
    columns: list[pa.Field[pa.DataType]] = [
        pa.field(name, pa.int64() if name == "source_ordinal" else pa.string())
        for name in (
            "source_id",
            "source_record_id",
            "source_ordinal",
            "source_sha256",
            "source_receipt_sha256",
            "acquisition_id",
            "schema_era",
            "source_effective_at",
            "retrieved_at",
            "valid_time_status",
            "source_snapshot_effective_date",
            "source_effective_from",
            "source_effective_to",
            "rights_state",
            "sensitivity_json",
            "source_receipt_sensitivity_json",
        )
    ]
    for kind, prefix in (
        ("mbs_service_record", "service"),
        ("mbs_benefit_record", "benefit"),
    ):
        for name in fields[kind]:
            contract = _CONTRACTS[name]
            base = f"{prefix}__{name}__"
            columns.extend([
                pa.field(base + "typed_value_text", pa.string()),
                pa.field(
                    base + "typed_value",
                    _arrow_type(contract.value_type),
                    metadata={
                        b"native_type": contract.value_type.encode(),
                        b"currency": (
                            b"AUD"
                            if contract.value_type == "aud_decimal"
                            else b"not_applicable"
                        ),
                        b"unit": (
                            b"source_magnitude_percent"
                            if contract.value_type == "percentage"
                            else b"not_applicable"
                        ),
                        b"conversion_version": b"mbs-scalar-v2",
                    },
                ),
                pa.field(base + "native_state", pa.string()),
                pa.field(base + "native_value", pa.string()),
                pa.field(base + "conversion_status", pa.string()),
            ])
    return columns


def _typed_value(
    field: MbsGoldFieldEvidence, contract: MbsFieldContract, schema_era: str
) -> str | Decimal | date | None:
    native_value = field.typed_value
    status = field.conversion_status
    if status in {
        "missing_field",
        "null",
        "blank",
        "invalid",
        "unsupported_format",
        "unrepresentable",
    }:
        if native_value is not None:
            raise ValueError("non-converted MBS field carries a typed value")
        return None
    if status == "preserved":
        if contract.value_type not in _TEXT_TYPES:
            raise ValueError("preserved MBS value conflicts with field type")
        return native_value
    if status != "converted" or not isinstance(native_value, str):
        raise ValueError("converted MBS value lacks serialized scalar")
    if contract.value_type in _DECIMAL_TYPES:
        try:
            parsed = Decimal(native_value)
            pa.scalar(parsed, type=pa.decimal128(38, 9))
        except (InvalidOperation, pa.ArrowInvalid, pa.ArrowTypeError) as error:
            raise ValueError(
                "MBS decimal is not exact decimal128(38,9)"
            ) from error
        return parsed
    if contract.value_type == "source_date":
        if schema_era != _MBS_XML_V3:
            raise ValueError("MBS date conversion lacks a qualified source era")
        try:
            return date.fromisoformat(native_value)
        except ValueError as error:
            raise ValueError(
                "MBS Silver date is not canonical ISO text"
            ) from error
    if contract.value_type in _TEXT_TYPES:
        raise ValueError("text MBS field cannot have converted status")
    raise ValueError("unsupported MBS field type")


def _record_values(
    service: MbsGoldNode,
    benefit: MbsGoldNode,
    edge: MbsGoldEdge,
    temporal: TemporalIdentity,
    receipt_sensitivity: SensitivityClassification,
) -> dict[str, object]:
    if service.evidence != benefit.evidence:
        raise ValueError("Gold relationship crosses source records")
    evidence = service.evidence
    row: dict[str, object] = {
        "source_id": evidence.source_id,
        "source_record_id": evidence.source_record_id,
        "source_ordinal": evidence.source_ordinal,
        "source_sha256": evidence.source_sha256,
        "source_receipt_sha256": evidence.receipt_sha256,
        "acquisition_id": temporal.acquisition_id,
        "schema_era": evidence.catalog_version,
        "source_effective_at": temporal.source_effective_at.isoformat()
        if temporal.source_effective_at
        else None,
        "retrieved_at": temporal.retrieved_at.isoformat(),
        "valid_time_status": edge.valid_time_status,
        "source_snapshot_effective_date": (
            edge.source_snapshot_effective_date.isoformat()
            if edge.source_snapshot_effective_date
            else None
        ),
        "source_effective_from": (
            edge.source_effective_from.isoformat()
            if edge.source_effective_from
            else None
        ),
        "source_effective_to": (
            edge.source_effective_to.isoformat()
            if edge.source_effective_to
            else None
        ),
        "rights_state": evidence.rights_state.value,
        # Graph and B1 sensitivity are distinct evidence-bearing assertions.
        "sensitivity_json": evidence.sensitivity.model_dump_json(),
        "source_receipt_sensitivity_json": receipt_sensitivity.model_dump_json(),
    }
    for node, prefix in ((service, "service"), (benefit, "benefit")):
        for field in node.fields:
            row[f"{prefix}__{field.native_name}__typed_value_text"] = (
                field.typed_value
            )
            row[f"{prefix}__{field.native_name}__typed_value"] = _typed_value(
                field,
                _CONTRACTS[field.native_name],
                node.evidence.catalog_version,
            )
            row[f"{prefix}__{field.native_name}__native_state"] = (
                field.native_state
            )
            row[f"{prefix}__{field.native_name}__native_value"] = (
                field.native_value
            )
            row[f"{prefix}__{field.native_name}__conversion_status"] = str(
                field.conversion_status
            )
    return row


def project_mbs_gold_scalar_candidate(
    graph: MbsGoldGraphCandidate,
    source_receipt: SourceReceipt,
) -> pa.Table:
    """Flatten exact service/benefit field states at source-record grain.

    The receipt is independently supplied and revalidated against the graph;
    its canonical digest and acquisition ID are carried into table metadata.
    """
    graph = MbsGoldGraphCandidate.model_validate(graph.model_dump())
    source_receipt = SourceReceipt.model_validate(source_receipt.model_dump())
    temporal = _validate_receipt_binding(graph, source_receipt)

    edges_by_record: dict[tuple[str, int], tuple[str, str, MbsGoldEdge]] = {}
    node_by_id = {node.node_id: node for node in graph.nodes}
    for edge in graph.edges:
        service = node_by_id[edge.source_node_id]
        benefit = node_by_id[edge.target_node_id]
        record_address = (
            edge.evidence.source_record_id,
            edge.evidence.source_ordinal,
        )
        edges_by_record[record_address] = (
            service.node_id,
            benefit.node_id,
            edge,
        )

    fields = _validate_field_contract(graph)
    columns = _field_columns(fields)
    rows: list[dict[str, object]] = []
    for _record_address, (service_id, benefit_id, edge) in sorted(
        edges_by_record.items(),
        key=lambda item: item[0][1],
    ):
        service, benefit = node_by_id[service_id], node_by_id[benefit_id]
        rows.append(
            _record_values(
                service,
                benefit,
                edge,
                temporal,
                source_receipt.sensitivity or SensitivityClassification(),
            )
        )

    schema = pa.schema(
        columns,
        metadata={
            b"schema_name": b"global-medicines-atlas.mbs-gold-scalar-candidate",
            b"schema_version": b"1",
            b"qualification": b"candidate_only",
            b"consumer_admission": b"not_performed",
            b"value_representation": b"contract_bound_arrow_scalars_v1",
            b"source_receipt_sha256": source_receipt.digest().encode(),
            b"acquisition_id": temporal.acquisition_id.encode(),
            b"graph_sha256": graph.graph_sha256.encode(),
            b"input_admission_sha256": cast(
                "str", graph.input_admission_sha256
            ).encode(),
            b"input_semantic_manifest_sha256": cast(
                "str", graph.input_semantic_manifest_sha256
            ).encode(),
        },
    )
    return pa.Table.from_pylist(rows, schema=schema)
