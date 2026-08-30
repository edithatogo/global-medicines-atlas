"""Technical MBS table admission, separate from rights and public release."""

from __future__ import annotations

import json
from datetime import datetime
from hashlib import sha256
from typing import Literal

from pydantic import model_validator

from .adapters._receipt import provenance_from_receipt
from .bronze_admission import (
    BronzeAdmissionRecord,
    BronzeAdmissionState,
    ValidationResult,
    create_admission_decision,
)
from .mbs_tables import MbsHtmlTable, TableContract, parse_mbs_html_tables
from .models import FrozenModel
from .receipts import EvidenceClass, SourceReceipt, require_temporal
from .source_health import (
    ProbeState,
    SourceHealthObservation,
    SourceHealthReceipt,
    build_source_health_receipt,
)


def _table_digest(tables: tuple[MbsHtmlTable, ...]) -> str:
    return sha256(
        json.dumps(
            [table.model_dump(mode="json") for table in tables],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


class MbsTableAdmission(FrozenModel):
    """Portable B1 decision with source-faithful admitted table projections."""

    source_receipt: SourceReceipt
    decision: BronzeAdmissionRecord
    tables: tuple[MbsHtmlTable, ...] = ()
    public_data_ready: Literal[False] = False

    @model_validator(mode="after")
    def bind_source_decision_and_tables(self) -> MbsTableAdmission:
        """Reject forged accepted/quarantined outcomes and cross-source joins."""
        temporal = require_temporal(self.source_receipt.temporal)
        if (
            self.source_receipt.source.source_id != "au-mbs"
            or self.source_receipt.source.jurisdiction != "AUS"
        ):
            raise ValueError("MBS admission requires the Australian MBS source")
        if (
            self.decision.acquisition_id != temporal.acquisition_id
            or self.decision.content_id != self.source_receipt.payload.sha256
        ):
            raise ValueError(
                "MBS decision must bind its source acquisition and bytes"
            )
        if self.decision.state not in {
            BronzeAdmissionState.ACCEPTED,
            BronzeAdmissionState.QUARANTINED,
        }:
            raise ValueError("MBS admission must be accepted or quarantined")
        accepted = self.decision.state is BronzeAdmissionState.ACCEPTED
        expected_reasons = () if accepted else ("mbs_table_profile_mismatch",)
        if self.decision.reason_codes != expected_reasons:
            raise ValueError(
                "MBS admission reason must match table qualification"
            )
        if accepted != bool(self.tables):
            raise ValueError(
                "only accepted MBS decisions may expose nonempty tables"
            )
        if any(
            table.provenance.source_sha256 != self.source_receipt.payload.sha256
            or table.provenance.source_id != "au-mbs"
            or table.provenance.source_uri
            != str(self.source_receipt.retrieval.uri)
            or table.provenance.retrieved_at
            != self.source_receipt.retrieval.retrieved_at
            for table in self.tables
        ):
            raise ValueError(
                "MBS tables must preserve the admitted source identity"
            )
        if (
            ValidationResult(
                check_id="mbs-table-projection",
                passed=accepted,
                message=f"projection_sha256:{_table_digest(self.tables)}",
            )
            not in self.decision.validation_results
        ):
            raise ValueError(
                "MBS decision must bind its exact table projection"
            )
        return self


def admit_mbs_html_tables(
    payload: bytes,
    receipt: SourceReceipt,
    contracts: tuple[TableContract, ...],
    *,
    decided_at: datetime,
) -> MbsTableAdmission:
    """Record accepted/quarantined technical processing without publishing.

    Payload/receipt mismatch is an input error, not a decision about unrelated
    bytes. Profile failures preserve their receipt and emit no projection.
    Rights, sensitivity, source-health currency and publication remain separate
    gates; this technical decision grants none of them.
    """
    provenance_from_receipt(
        receipt,
        payload,
        source_id="au-mbs",
        jurisdiction="AUS",
        transformation="mbs-table-admission-v1",
    )
    temporal = require_temporal(receipt.temporal)
    contract_digest = sha256(
        json.dumps(
            [contract.model_dump(mode="json") for contract in contracts],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    try:
        tables = parse_mbs_html_tables(payload, receipt, contracts)
    except ValueError:
        tables = ()
    accepted = bool(tables)
    decision = create_admission_decision(
        acquisition_id=temporal.acquisition_id,
        content_id=receipt.payload.sha256,
        state=BronzeAdmissionState.ACCEPTED
        if accepted
        else BronzeAdmissionState.QUARANTINED,
        reason_codes=() if accepted else ("mbs_table_profile_mismatch",),
        validation_results=(
            ValidationResult(
                check_id="mbs-table-schema",
                passed=accepted,
                message=f"contract_sha256:{contract_digest}; admitted_tables:{len(tables)}",
            ),
            ValidationResult(
                check_id="mbs-table-projection",
                passed=accepted,
                message=f"projection_sha256:{_table_digest(tables)}",
            ),
        ),
        actor="global-medicines-atlas:mbs-table-admission-v1",
        decided_at=decided_at,
    )
    return MbsTableAdmission(
        source_receipt=receipt, decision=decision, tables=tables
    )


def mbs_admission_health(
    outcome: MbsTableAdmission,
    *,
    previous_consecutive_failures: int = 0,
    previous_escalation_open: bool = False,
) -> SourceHealthReceipt:
    """Report usable-table health at retrieval time, not publication or currency.

    Rehearsals cannot enter the live health history. A succeeded transport with
    quarantined tables is a processing failure, not usable data availability.
    """
    receipt = outcome.source_receipt
    if receipt.evidence_class is not EvidenceClass.LIVE:
        raise ValueError(
            "live source health requires live acquisition evidence"
        )
    accepted = outcome.decision.state is BronzeAdmissionState.ACCEPTED
    observation = SourceHealthObservation(
        source_id="au-mbs",
        checked_at=receipt.retrieval.retrieved_at,
        state=ProbeState.AVAILABLE if accepted else ProbeState.UNAVAILABLE,
        detail="MBS tables admitted"
        if accepted
        else "MbsTableProfileMismatch: tables quarantined",
    )
    return build_source_health_receipt(
        observation,
        previous_consecutive_failures=previous_consecutive_failures,
        previous_escalation_open=previous_escalation_open,
    )
