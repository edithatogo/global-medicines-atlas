"""Fail-closed v0.8 Mojo kernel qualification contract."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .models import FrozenModel


class MojoQualification(FrozenModel):
    """Evidence-backed disposition of the experimental Mojo path."""

    schema_version: Literal["1.0.0"]
    release: Literal["v0.8"]
    authoritative_engine: Literal["python-3.14"]
    mojo_disposition: Literal["experimental_not_promoted"]
    toolchain_version: str = Field(min_length=1)
    hosted_smoke_run: str = Field(
        pattern=r"^https://github\.com/.+/actions/runs/\d+$"
    )
    hosted_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    real_kernel_present: bool
    arrow_fixture_parity: Literal["not_run_no_real_kernel", "passed"]
    fallback_rehearsal: Literal[
        "not_applicable_no_runtime_path",
        "passed",
    ]
    representative_benchmark: Literal["not_run_no_real_kernel", "passed"]
    scalene_justifies_promotion: bool
    promotion: Literal["denied", "approved"]
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def promotion_requires_every_gate(self) -> MojoQualification:
        gates_pass = (
            self.real_kernel_present
            and self.arrow_fixture_parity == "passed"
            and self.fallback_rehearsal == "passed"
            and self.representative_benchmark == "passed"
            and self.scalene_justifies_promotion
        )
        if self.promotion == "approved" and not gates_pass:
            raise ValueError("Mojo promotion requires every ADR 0003 gate")
        return self
