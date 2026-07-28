"""Policy checks for release-only provenance attestations."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TypedDict, cast

import pytest
from pydantic import AnyUrl

from global_medicines_atlas.coverage import CoverageObservation
from global_medicines_atlas.models import AssertionKind, TimeInterval
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
)
from global_medicines_atlas.release_evidence import (
    GateStatus,
    GitState,
    ReleaseState,
    qualify_release,
)

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "release-provenance.yml"
)
BLOCKED_LIVE_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "release-evidence"
    / "blocked-live-v0.4.json"
)
SHA = "a" * 64
ALL_GATES = {
    "dimension_separation": GateStatus.PASSED,
    "jurisdiction_identity": GateStatus.PASSED,
    "bitemporal_model": GateStatus.PASSED,
    "source_provenance": GateStatus.PASSED,
    "rights_review": GateStatus.PASSED,
    "canonical_schema": GateStatus.PASSED,
    "coverage_denominators": GateStatus.PASSED,
    "deterministic_migration": GateStatus.PASSED,
    "traceability": GateStatus.PASSED,
    "live_lineage_verification": GateStatus.PASSED,
}


class NegativeControl(TypedDict):
    id: str
    evidence_class: str
    rights_state: str
    denominator: int | None
    retrieved_at: str
    gate_overrides: dict[str, str]
    expected_blockers: list[str]


NEGATIVE_CONTROLS = cast(
    "list[NegativeControl]",
    json.loads(BLOCKED_LIVE_FIXTURE.read_text(encoding="utf-8"))["cases"],
)


def test_provenance_attestation_is_release_only_and_sha_pinned() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "release:" in workflow
    assert "types: [published]" in workflow
    assert "workflow_dispatch:" not in workflow
    assert "push:" not in workflow
    assert "pull_request:" not in workflow
    assert "github.event.release.draft == false" in workflow
    assert (
        "actions/attest-build-provenance@"
        "977bb373ede98d70efdf65b84cb5f73e068dcc2a" in workflow
    )


def test_provenance_job_has_minimal_required_permissions() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "contents: read" in workflow
    assert "id-token: write" in workflow
    assert "attestations: write" in workflow
    assert "contents: write" in workflow
    assert "persist-credentials: false" in workflow
    assert (
        "actions/upload-artifact@"
        "b7c566a772e6b6bfb58ed0dc250532a479d7789f" in workflow
    )
    assert "\n          path: dist/*" in workflow
    assert 'gh release upload "$RELEASE_TAG" dist/* --clobber' in workflow
    assert "subject-path: dist/*" in workflow


@pytest.mark.edge
@pytest.mark.parametrize(
    "case",
    NEGATIVE_CONTROLS,
    ids=lambda case: str(case["id"]),
)
def test_v04_negative_controls_cannot_promote(
    case: NegativeControl,
) -> None:
    retrieved_at = datetime.fromisoformat(str(case["retrieved_at"]))
    evidence_class = EvidenceClass(str(case["evidence_class"]))
    rights_state = RightsState(str(case["rights_state"]))
    receipt = SourceReceipt(
        receipt_id="receipt-live-gate",
        source=SourceIdentity(
            catalog_id="nz-medsafe",
            source_id="medsafe",
            jurisdiction="NZ",
            authority="Medsafe",
            dataset_title="Product/Application",
            catalog_version="1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl("https://example.test/medsafe"),
            retrieved_at=retrieved_at,
            acquisition_method=(
                AcquisitionMethod.API
                if evidence_class is EvidenceClass.LIVE
                else AcquisitionMethod.LOCAL_FIXTURE
            ),
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=PayloadEvidence(sha256=SHA, byte_count=1),
        effective_from=retrieved_at,
        rights_state=rights_state,
        rights_reference=(
            AnyUrl("https://example.test/rights")
            if rights_state is RightsState.PERMITTED
            else None
        ),
        evidence_class=evidence_class,
        transformation=TransformationEvidence(
            transformation_id="temporal-v2",
            transformation_sha256=SHA,
            output_sha256=SHA,
            output_byte_count=1,
        ),
    )
    interval = TimeInterval(start=retrieved_at)
    coverage = CoverageObservation(
        jurisdiction="NZ",
        source_id="medsafe",
        receipt_id=receipt.receipt_id,
        observation_id=f"coverage-{case['id']}",
        population_partition_id="all-medicines",
        dimension=AssertionKind.REGULATORY,
        medicine_concept_id="nz-medicine-1",
        assertion_type="regulatory:marketing-authorisation",
        assertion_status="approved",
        concept_population="qualification-negative-control",
        valid_time=interval,
        observed_time=interval,
        assertion_count=1,
        concept_numerator=1,
        eligible_denominator=case["denominator"],
    )
    gate_overrides = {
        gate: GateStatus(status)
        for gate, status in case["gate_overrides"].items()
    }
    evidence = qualify_release(
        git=GitState(commit=SHA[:40], dirty=False),
        receipts=[receipt],
        coverage=[coverage],
        snapshots=[],
        gate_outcomes={**ALL_GATES, **gate_overrides},
        dataset_schema_versions=["2"],
        migration_versions=["1-to-2"],
        request_approval=True,
    )

    assert evidence.release_state is ReleaseState.BLOCKED
    assert set(case["expected_blockers"]) <= set(evidence.unresolved_gates)


def test_v04_negative_control_manifest_tracks_external_gate() -> None:
    fixture = json.loads(BLOCKED_LIVE_FIXTURE.read_text(encoding="utf-8"))

    assert fixture["release"] == "v0.4"
    assert fixture["external_gate_issue"] == 54
    assert {case["id"] for case in fixture["cases"]} == {
        "fixture",
        "synthetic",
        "unknown-rights",
        "stale",
        "denominator-free",
    }
