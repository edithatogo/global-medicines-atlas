# pyright: reportUnknownMemberType=false

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest
from pydantic import AnyUrl, ValidationError

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
    REQUIREMENT_IDS,
    GateStatus,
    GitState,
    InputEvidenceDigests,
    ReleaseEvidence,
    ReleaseState,
    qualify_release,
)
from global_medicines_atlas.snapshots import (
    SnapshotArtifact,
    SnapshotManifest,
    TransformationLineage,
)

NOW = datetime(2026, 7, 29, tzinfo=UTC)
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


def receipt(evidence_class: EvidenceClass) -> SourceReceipt:
    return SourceReceipt(
        receipt_id=f"receipt-{evidence_class}",
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
            retrieved_at=NOW,
            acquisition_method=(
                AcquisitionMethod.LOCAL_FIXTURE
                if evidence_class is EvidenceClass.FIXTURE
                else AcquisitionMethod.API
            ),
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=PayloadEvidence(sha256=SHA, byte_count=1),
        effective_from=NOW,
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl("https://example.test/rights"),
        evidence_class=evidence_class,
        transformation=TransformationEvidence(
            transformation_id="temporal-v2",
            transformation_sha256=SHA,
            output_sha256=SHA,
            output_byte_count=1,
        ),
    )


def coverage(denominator: int | None = 1) -> CoverageObservation:
    interval = TimeInterval(start=NOW)
    return CoverageObservation(
        jurisdiction="NZ",
        source_id="medsafe",
        receipt_id="receipt-live",
        observation_id="coverage-1",
        population_partition_id="all-medicines",
        dimension=AssertionKind.REGULATORY,
        medicine_concept_id="nz-medicine-1",
        assertion_type="regulatory:marketing-authorisation",
        assertion_status="approved",
        concept_population="fixture",
        valid_time=interval,
        observed_time=interval,
        assertion_count=1,
        concept_numerator=1,
        eligible_denominator=denominator,
    )


def snapshot() -> SnapshotManifest:
    return SnapshotManifest(
        dataset_schema_id="temporal-assertion",
        dataset_schema_version="2",
        source_catalog_sha256=SHA,
        transformation=TransformationLineage(
            command=("python", "build.py"),
            package_commit=SHA[:40],
        ),
        artifacts=(
            SnapshotArtifact(
                role="input", path="input.json", sha256=SHA, size_bytes=1
            ),
            SnapshotArtifact(
                role="output", path="output.parquet", sha256=SHA, size_bytes=1
            ),
        ),
    )


def qualify(
    evidence_class: EvidenceClass,
    *,
    denominator: int | None = 1,
    request_approval: bool = False,
    gates: dict[str, GateStatus] | None = None,
    snapshots: tuple[SnapshotManifest, ...] = (),
    dirty: bool = False,
) -> ReleaseEvidence:
    return qualify_release(
        git=GitState(commit=SHA[:40], dirty=dirty),
        receipts=[receipt(evidence_class)],
        coverage=[coverage(denominator)],
        snapshots=snapshots,
        gate_outcomes=gates or ALL_GATES,
        dataset_schema_versions=["2", "2"],
        migration_versions=["1-to-2"],
        request_approval=request_approval,
    )


@pytest.mark.unit
def test_fixture_evidence_is_deterministic_and_requirement_complete() -> None:
    evidence = qualify(EvidenceClass.FIXTURE, snapshots=(snapshot(),))

    assert evidence.release_state is ReleaseState.FIXTURE_QUALIFIED
    assert tuple(item.requirement_id for item in evidence.requirement_map) == (
        REQUIREMENT_IDS
    )
    assert evidence.receipt_counts == {EvidenceClass.FIXTURE: 1}
    assert evidence.dataset_schema_versions == ("2",)
    assert evidence.canonical_json() == evidence.canonical_json()


@pytest.mark.edge
def test_fixture_receipt_cannot_claim_live_or_approved() -> None:
    fixture = qualify(EvidenceClass.FIXTURE, request_approval=True)

    assert fixture.release_state is ReleaseState.BLOCKED
    assert "live_evidence_only" in fixture.unresolved_gates
    with pytest.raises(ValidationError, match="non-live receipts"):
        ReleaseEvidence.model_validate({
            **fixture.model_dump(),
            "release_state": ReleaseState.APPROVED,
        })


@pytest.mark.unit
def test_clean_live_evidence_can_qualify_but_not_self_approve() -> None:
    live = qualify(EvidenceClass.LIVE)

    assert live.release_state is ReleaseState.LIVE_QUALIFIED
    assert not live.unresolved_gates

    requested = qualify(EvidenceClass.LIVE, request_approval=True)
    assert requested.release_state is ReleaseState.BLOCKED
    assert requested.unresolved_gates == ("external_approval_receipt",)


@pytest.mark.edge
def test_live_evidence_requires_verified_lineage() -> None:
    live = qualify(EvidenceClass.LIVE)
    payload = live.model_dump()
    payload["gate_outcomes"]["live_lineage_verification"] = GateStatus.FAILED

    with pytest.raises(ValidationError, match="verified live lineage"):
        ReleaseEvidence.model_validate(payload)


@pytest.mark.edge
def test_live_evidence_rejects_fixture_snapshot_scope() -> None:
    live = qualify(EvidenceClass.LIVE)
    payload = live.model_dump()
    payload["snapshot_scopes"] = ("fixture-only qualification evidence",)

    with pytest.raises(ValidationError, match="fixture snapshots"):
        ReleaseEvidence.model_validate(payload)


@pytest.mark.unit
def test_forged_approval_gate_cannot_approve_live_evidence() -> None:
    gates = {**ALL_GATES, "maintainer_release_approval": GateStatus.PASSED}

    evidence = qualify(
        EvidenceClass.LIVE,
        request_approval=True,
        gates=gates,
    )

    assert evidence.release_state is ReleaseState.BLOCKED
    assert evidence.unresolved_gates == ("external_approval_receipt",)


@pytest.mark.edge
def test_unknown_denominator_and_failed_gate_block_qualification() -> None:
    gates = {**ALL_GATES, "coverage_denominators": GateStatus.FAILED}

    evidence = qualify(EvidenceClass.LIVE, denominator=None, gates=gates)

    assert evidence.release_state is ReleaseState.BLOCKED
    assert evidence.coverage_unknown_denominators == 1
    assert evidence.unresolved_gates == (
        "coverage_denominators",
        "known_coverage_denominators",
    )


@pytest.mark.edge
def test_dirty_repository_blocks_live_but_is_reported_for_fixture() -> None:
    live = qualify(EvidenceClass.LIVE, dirty=True)
    fixture = qualify(
        EvidenceClass.FIXTURE,
        snapshots=(snapshot(),),
        dirty=True,
    )

    assert live.release_state is ReleaseState.BLOCKED
    assert "clean_repository" in live.unresolved_gates
    assert fixture.release_state is ReleaseState.FIXTURE_QUALIFIED
    assert fixture.git.dirty is True


@pytest.mark.edge
@pytest.mark.parametrize(
    ("schema_versions", "migration_versions", "missing_gate"),
    [
        ([], ["1-to-2"], "dataset_schema_versions"),
        (["2"], [], "migration_versions"),
    ],
)
def test_live_qualification_requires_nonempty_versions(
    schema_versions: list[str],
    migration_versions: list[str],
    missing_gate: str,
) -> None:
    evidence = qualify_release(
        git=GitState(commit=SHA[:40], dirty=False),
        receipts=[receipt(EvidenceClass.LIVE)],
        coverage=[coverage()],
        snapshots=[],
        gate_outcomes=ALL_GATES,
        dataset_schema_versions=schema_versions,
        migration_versions=migration_versions,
    )

    assert evidence.release_state is ReleaseState.BLOCKED
    assert missing_gate in evidence.unresolved_gates


@pytest.mark.edge
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("receipt_id", "receipt-other"),
        ("source_id", "other-source"),
        ("jurisdiction", "AU"),
        ("dimension", AssertionKind.FUNDING),
    ],
)
def test_coverage_identity_mismatch_blocks_live_qualification(
    field: str,
    value: str,
) -> None:
    observation = coverage().model_copy(update={field: value})
    evidence = qualify_release(
        git=GitState(commit=SHA[:40], dirty=False),
        receipts=[receipt(EvidenceClass.LIVE)],
        coverage=[observation],
        snapshots=[],
        gate_outcomes=ALL_GATES,
        dataset_schema_versions=["2"],
        migration_versions=["1-to-2"],
    )

    assert evidence.release_state is ReleaseState.BLOCKED
    assert "coverage_receipt_reconciliation" in evidence.unresolved_gates


@pytest.mark.unit
def test_input_and_individual_digests_bind_qualification_inputs() -> None:
    baseline = qualify(EvidenceClass.LIVE)
    changed = qualify_release(
        git=GitState(commit=SHA[:40], dirty=False),
        receipts=[
            receipt(EvidenceClass.LIVE).model_copy(
                update={"receipt_id": "receipt-tampered"}
            )
        ],
        coverage=[coverage()],
        snapshots=[],
        gate_outcomes=ALL_GATES,
        dataset_schema_versions=["2"],
        migration_versions=["1-to-2"],
    )

    assert baseline.input_evidence.receipts_sha256 != (
        changed.input_evidence.receipts_sha256
    )
    assert baseline.receipt_digests != changed.receipt_digests
    assert len(baseline.receipt_digests[0]) == 64


@pytest.mark.unit
def test_explicit_raw_input_digests_are_preserved() -> None:
    raw = InputEvidenceDigests(
        receipts_sha256="1" * 64,
        coverage_sha256="2" * 64,
        snapshots_sha256="3" * 64,
        gates_sha256="4" * 64,
    )
    evidence = qualify_release(
        git=GitState(commit=SHA[:40], dirty=False),
        receipts=[receipt(EvidenceClass.LIVE)],
        coverage=[coverage()],
        snapshots=[],
        gate_outcomes=ALL_GATES,
        dataset_schema_versions=["2"],
        migration_versions=["1-to-2"],
        input_evidence=raw,
    )

    assert evidence.input_evidence == raw


@pytest.mark.edge
def test_release_evidence_model_rejects_approved_state() -> None:
    live = qualify(EvidenceClass.LIVE)

    with pytest.raises(ValidationError, match="cannot produce approved"):
        ReleaseEvidence.model_validate({
            **live.model_dump(),
            "release_state": ReleaseState.APPROVED,
        })


@pytest.mark.edge
def test_release_evidence_rejects_duplicate_requirement_ids() -> None:
    evidence = qualify(EvidenceClass.FIXTURE)
    requirements = list(evidence.requirement_map)
    requirements.append(requirements[0])
    with pytest.raises(ValidationError, match="duplicate identifiers"):
        ReleaseEvidence.model_validate({
            **evidence.model_dump(),
            "requirement_map": requirements,
        })


@pytest.mark.edge
def test_release_evidence_rejects_unknown_requirement_ids() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    requirements = list(evidence.requirement_map)
    requirements[0] = requirements[0].model_copy(update={"requirement_id": "M-999"})
    with pytest.raises(ValidationError, match="unknown identifiers"):
        ReleaseEvidence.model_validate({
            **evidence.model_dump(),
            "requirement_map": requirements,
        })


@pytest.mark.edge
def test_release_evidence_rejects_incomplete_requirement_map() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    with pytest.raises(ValidationError, match="missing required identifiers"):
        ReleaseEvidence.model_validate({
            **evidence.model_dump(),
            "requirement_map": list(evidence.requirement_map)[1:],
        })


@pytest.mark.edge
def test_release_evidence_rejects_requirement_gate_drift() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    requirements = list(evidence.requirement_map)
    requirements[0] = requirements[0].model_copy(update={"gates": ("traceability",)})
    with pytest.raises(ValidationError, match="gates do not match"):
        ReleaseEvidence.model_validate({
            **evidence.model_dump(),
            "requirement_map": requirements,
        })


@pytest.mark.edge
def test_release_evidence_rejects_stale_requirement_satisfaction() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    requirements = list(evidence.requirement_map)
    requirements[0] = requirements[0].model_copy(update={"satisfied": False})
    with pytest.raises(ValidationError, match="satisfaction does not match"):
        ReleaseEvidence.model_validate({
            **evidence.model_dump(),
            "requirement_map": requirements,
        })


@pytest.mark.edge
def test_release_evidence_rejects_missing_gate_outcome() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    outcomes = dict(evidence.gate_outcomes)
    outcomes.pop("traceability")
    with pytest.raises(ValidationError, match="missing required gates"):
        ReleaseEvidence.model_validate({**evidence.model_dump(), "gate_outcomes": outcomes})


@pytest.mark.edge
def test_release_evidence_rejects_omitted_failed_gate() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    outcomes = {**evidence.gate_outcomes, "traceability": GateStatus.FAILED}
    with pytest.raises(ValidationError, match="omit non-passed"):
        ReleaseEvidence.model_validate({
            **evidence.model_dump(),
            "gate_outcomes": outcomes,
            "unresolved_gates": tuple(
                gate for gate in evidence.unresolved_gates if gate != "traceability"
            ),
        })


@pytest.mark.edge
def test_release_evidence_rejects_duplicate_unresolved_gate() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    unresolved = ("traceability", "traceability")
    with pytest.raises(ValidationError, match="must be unique"):
        ReleaseEvidence.model_validate({
            **evidence.model_dump(),
            "gate_outcomes": {
                **evidence.gate_outcomes,
                "traceability": GateStatus.FAILED,
            },
            "unresolved_gates": unresolved,
        })


@pytest.mark.edge
def test_release_evidence_rejects_unsorted_unresolved_gates() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    with pytest.raises(ValidationError, match="must be sorted"):
        ReleaseEvidence.model_validate({
            **evidence.model_dump(),
            "gate_outcomes": {
                **evidence.gate_outcomes,
                "traceability": GateStatus.FAILED,
                "rights_review": GateStatus.FAILED,
            },
            "unresolved_gates": ("traceability", "rights_review"),
        })


@pytest.mark.edge
def test_release_evidence_rejects_noncanonical_requirement_order() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    with pytest.raises(ValidationError, match="canonical order"):
        ReleaseEvidence.model_validate({
            **evidence.model_dump(),
            "requirement_map": tuple(reversed(evidence.requirement_map)),
        })


@pytest.mark.edge
def test_release_evidence_rejects_unsorted_schema_versions() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    with pytest.raises(ValidationError, match="schema versions must be unique and sorted"):
        ReleaseEvidence.model_validate({
            **evidence.model_dump(),
            "dataset_schema_versions": ("2", "1"),
        })


@pytest.mark.edge
def test_release_evidence_rejects_negative_counts() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    counts = dict(evidence.receipt_counts)
    counts[EvidenceClass.LIVE] = -1
    with pytest.raises(ValidationError, match="counts must be nonnegative"):
        ReleaseEvidence.model_validate({
            **evidence.model_dump(),
            "receipt_counts": counts,
        })


@pytest.mark.edge
def test_release_evidence_rejects_malformed_receipt_digest() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    with pytest.raises(ValidationError, match="receipt digests"):
        ReleaseEvidence.model_validate({
            **evidence.model_dump(),
            "receipt_digests": ("not-a-digest",),
        })


@pytest.mark.edge
def test_release_evidence_rejects_unsorted_receipt_digests() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    digests = ("f" * 64, "0" * 64)
    with pytest.raises(ValidationError, match="receipt digests must be sorted"):
        ReleaseEvidence.model_validate({**evidence.model_dump(), "receipt_digests": digests})


@pytest.mark.edge
def test_release_evidence_rejects_duplicate_receipt_digests() -> None:
    evidence = qualify(EvidenceClass.LIVE)
    digest = "0" * 64
    with pytest.raises(ValidationError, match="receipt digests must be unique"):
        ReleaseEvidence.model_validate({
            **evidence.model_dump(),
            "receipt_digests": (digest, digest),
        })


@pytest.mark.unit
def test_checked_in_json_schema_accepts_model_and_rejects_approval() -> None:
    schema = json.loads(
        Path("schemas/release-evidence-v1.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    payload = qualify(EvidenceClass.LIVE).model_dump(mode="json")

    validator.validate(payload)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({**payload, "release_state": "approved"})
