"""Fail-closed entry-condition receipts for gated datahouse experiments."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .models import FrozenModel


class PrerequisiteCheck(FrozenModel):
    name: str = Field(min_length=1)
    satisfied: bool
    evidence: tuple[str, ...] = ()

    @model_validator(mode="after")
    def satisfied_check_has_evidence(self) -> PrerequisiteCheck:
        if self.satisfied and not self.evidence:
            raise ValueError("satisfied prerequisite requires evidence")
        return self


class ExperimentPrerequisiteReceipt(FrozenModel):
    schema_id: Literal["global-medicines-atlas.experiment-prerequisite-receipt"]
    schema_version: Literal[1]
    experiment_id: Literal["object_versioning", "delta_hudi"]
    checks: tuple[PrerequisiteCheck, ...] = Field(min_length=1)
    eligible: bool
    outcome: Literal["eligible", "not_run_prerequisite_unmet"]
    credentials_created: Literal[False] = False
    production_deployment_claimed: Literal[False] = False

    @model_validator(mode="after")
    def outcome_matches_checks(self) -> ExperimentPrerequisiteReceipt:
        all_satisfied = all(check.satisfied for check in self.checks)
        if self.eligible != all_satisfied:
            raise ValueError("eligibility must equal the complete check state")
        expected = "eligible" if all_satisfied else "not_run_prerequisite_unmet"
        if self.outcome != expected:
            raise ValueError("outcome must match prerequisite eligibility")
        return self
