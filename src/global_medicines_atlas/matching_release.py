"""Fail-closed v0.5 matching qualification evidence."""

from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256

from pydantic import Field, model_validator

from .matching_columnar import DISCLAIMER, MatchingOutputManifest
from .matching_evaluation import MatchingMetrics
from .models import FrozenModel


class KernelDisposition(StrEnum):
    PYTHON_REFERENCE = "python_reference"
    NOT_PROMOTED = "not_promoted"
    PROMOTED = "promoted"


class MatchingReleaseState(StrEnum):
    BLOCKED = "blocked"
    FIXTURE_QUALIFIED = "fixture_qualified"
    REVIEWED = "reviewed"


class EngineDisposition(FrozenModel):
    python: KernelDisposition = KernelDisposition.PYTHON_REFERENCE
    mojo: KernelDisposition = KernelDisposition.NOT_PROMOTED
    rust_tantivy: KernelDisposition = KernelDisposition.NOT_PROMOTED
    rationale: str = Field(min_length=1)


class MatchingReleaseEvidence(FrozenModel):
    version: str = "v0.5"
    state: MatchingReleaseState
    metrics: MatchingMetrics
    output_manifest: MatchingOutputManifest
    output_manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    corpus_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    calibration_version: str = Field(min_length=1)
    index_version: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    engine_disposition: EngineDisposition
    open_review_count: int = Field(ge=0)
    unresolved_conflict_count: int = Field(ge=0)
    limitations: tuple[str, ...] = Field(min_length=1)
    clinical_equivalence_disclaimer: str = DISCLAIMER
    gates: dict[str, bool]
    unresolved_gates: tuple[str, ...]

    @model_validator(mode="after")
    def fail_closed(self) -> MatchingReleaseEvidence:
        if self.clinical_equivalence_disclaimer != DISCLAIMER:
            raise ValueError("The clinical-equivalence disclaimer is required")
        if self.output_manifest.clinical_equivalence_disclaimer != DISCLAIMER:
            raise ValueError("The output manifest disclaimer is required")
        expected_digest = sha256(
            self.output_manifest.canonical_json()
        ).hexdigest()
        if self.output_manifest_digest != expected_digest:
            raise ValueError("Output manifest digest does not match manifest")

        missing = sorted(REQUIRED_GATES - self.gates.keys())
        if missing:
            raise ValueError(f"Missing qualification gates: {missing}")
        promoted = any(
            disposition is KernelDisposition.PROMOTED
            for disposition in (
                self.engine_disposition.mojo,
                self.engine_disposition.rust_tantivy,
            )
        )
        if promoted:
            promotion_missing = sorted(PROMOTION_GATES - self.gates.keys())
            if promotion_missing:
                raise ValueError(
                    f"Missing engine-promotion gates: {promotion_missing}"
                )

        expected_unresolved = _unresolved_gates(
            gates=self.gates,
            open_review_count=self.open_review_count,
            unresolved_conflict_count=self.unresolved_conflict_count,
            promoted=promoted,
        )
        if self.unresolved_gates != expected_unresolved:
            raise ValueError(
                "Unresolved gates do not match qualification evidence"
            )
        expected_state = _release_state(self.gates, expected_unresolved)
        if self.state is not expected_state:
            raise ValueError(
                f"Evidence state must be {expected_state.value} for its gates"
            )
        return self

    def canonical_json(self) -> bytes:
        return (
            json.dumps(
                self.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()


REQUIRED_GATES: frozenset[str] = frozenset({
    "corpus_reviewed",
    "holdout_sealed",
    "metrics_passed",
    "calibration_passed",
    "artifacts_reproducible",
    "human_adjudication_complete",
})
PROMOTION_GATES: frozenset[str] = frozenset({
    "engine_parity_passed",
    "representative_benchmark_passed",
    "scalene_profile_justifies_promotion",
})


def _unresolved_gates(
    *,
    gates: dict[str, bool],
    open_review_count: int,
    unresolved_conflict_count: int,
    promoted: bool,
) -> tuple[str, ...]:
    required: frozenset[str] = (
        REQUIRED_GATES | PROMOTION_GATES if promoted else REQUIRED_GATES
    )
    unresolved: set[str] = {item for item in required if not gates.get(item)}
    if open_review_count:
        unresolved.add("open_reviews")
    if unresolved_conflict_count:
        unresolved.add("unresolved_conflicts")
    return tuple(sorted(unresolved))


def _release_state(
    gates: dict[str, bool], unresolved: tuple[str, ...]
) -> MatchingReleaseState:
    if not unresolved:
        return MatchingReleaseState.REVIEWED
    fixture_ready = all(
        gates.get(item, False)
        for item in (
            "metrics_passed",
            "calibration_passed",
            "artifacts_reproducible",
        )
    )
    return (
        MatchingReleaseState.FIXTURE_QUALIFIED
        if fixture_ready
        else MatchingReleaseState.BLOCKED
    )


def qualify_matching_release(
    *,
    metrics: MatchingMetrics,
    output_manifest: MatchingOutputManifest,
    output_manifest_digest: str,
    corpus_digest: str,
    holdout_digest: str,
    calibration_version: str,
    index_version: str,
    model_version: str,
    engine_disposition: EngineDisposition,
    open_review_count: int,
    unresolved_conflict_count: int,
    limitations: tuple[str, ...],
    gates: dict[str, bool],
) -> MatchingReleaseEvidence:
    expected_manifest_digest = sha256(
        output_manifest.canonical_json()
    ).hexdigest()
    if output_manifest_digest != expected_manifest_digest:
        raise ValueError("Output manifest digest does not match manifest")
    promoted = any(
        disposition is KernelDisposition.PROMOTED
        for disposition in (
            engine_disposition.mojo,
            engine_disposition.rust_tantivy,
        )
    )
    unresolved = _unresolved_gates(
        gates=gates,
        open_review_count=open_review_count,
        unresolved_conflict_count=unresolved_conflict_count,
        promoted=promoted,
    )
    return MatchingReleaseEvidence(
        state=_release_state(gates, unresolved),
        metrics=metrics,
        output_manifest=output_manifest,
        output_manifest_digest=output_manifest_digest,
        corpus_digest=corpus_digest,
        holdout_digest=holdout_digest,
        calibration_version=calibration_version,
        index_version=index_version,
        model_version=model_version,
        engine_disposition=engine_disposition,
        open_review_count=open_review_count,
        unresolved_conflict_count=unresolved_conflict_count,
        limitations=limitations,
        gates=dict(sorted(gates.items())),
        unresolved_gates=unresolved,
    )
