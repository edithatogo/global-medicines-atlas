"""Canonical NZ medicine contract and projection tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.models import (
    AssertionKind,
    CanonicalMedicineRecord,
    EvidenceStatus,
    MedicineConcept,
    Provenance,
    StatusAssertion,
)
from global_medicines_atlas.nz import (
    project_nz_fhir_record,
    project_nz_fhir_records,
    write_canonical_index,
)
from sources.nz.nzulm_fhir import (
    FhirResourceRecord,
    load_upstream_fixture_records,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_nz_projection_emits_deterministic_provenance_bearing_records() -> None:
    records = project_nz_fhir_records(
        load_upstream_fixture_records(PROJECT_ROOT)
    )

    assert len(records) == 42
    assert list(records) == sorted(
        records, key=lambda row: row.concept.concept_id
    )
    assert all(record.concept.jurisdiction == "NZ" for record in records)
    assert all(
        record.concept.identifiers[0].system == "http://nzmt.org.nz"
        for record in records
    )
    assert all(record.provenance[0].source_sha256 for record in records)
    assert all(record.assertions == () for record in records)


def test_regulatory_and_funding_assertions_remain_distinct() -> None:
    provenance = Provenance(source_id="fixture", source_uri="local://fixture")
    concept = MedicineConcept(
        concept_id="nzmt:1",
        jurisdiction="NZ",
        level="mp",
        preferred_name="Example",
    )
    record = CanonicalMedicineRecord(
        concept=concept,
        provenance=(provenance,),
        assertions=(
            StatusAssertion(
                assertion_id="medsafe:1",
                concept_id=concept.concept_id,
                jurisdiction="NZ",
                kind=AssertionKind.REGULATORY,
                authority="Medsafe",
                status_code="approved",
                evidence_status=EvidenceStatus.CONFIRMED,
                provenance=provenance,
            ),
            StatusAssertion(
                assertion_id="pharmac:1",
                concept_id=concept.concept_id,
                jurisdiction="NZ",
                kind=AssertionKind.FUNDING,
                authority="PHARMAC",
                status_code="funded-with-restrictions",
                evidence_status=EvidenceStatus.CONFIRMED,
                provenance=provenance,
            ),
        ),
    )

    assert {item.kind for item in record.assertions} == {
        AssertionKind.REGULATORY,
        AssertionKind.FUNDING,
    }


def test_assertion_cannot_target_a_different_concept() -> None:
    provenance = Provenance(source_id="fixture", source_uri="local://fixture")
    with pytest.raises(ValidationError, match="must target"):
        CanonicalMedicineRecord(
            concept=MedicineConcept(
                concept_id="nzmt:1",
                jurisdiction="NZ",
                level="mp",
                preferred_name="Example",
            ),
            provenance=(provenance,),
            assertions=(
                StatusAssertion(
                    assertion_id="bad",
                    concept_id="nzmt:2",
                    jurisdiction="NZ",
                    kind=AssertionKind.REGULATORY,
                    authority="Medsafe",
                    status_code="approved",
                    evidence_status=EvidenceStatus.CONFIRMED,
                    provenance=provenance,
                ),
            ),
        )


def test_canonical_index_is_byte_deterministic(tmp_path: Path) -> None:
    records = project_nz_fhir_records(
        load_upstream_fixture_records(PROJECT_ROOT)
    )
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    write_canonical_index(records, first)
    write_canonical_index(reversed(records), second)

    assert first.read_bytes() == second.read_bytes()
    assert len(json.loads(first.read_text(encoding="utf-8"))) == 42


def test_malformed_optional_fhir_fields_fall_back_without_inference() -> None:
    record = FhirResourceRecord(
        resource_type="Medication",
        resource_id="fallback-id",
        resource={"resourceType": "Medication", "code": {"coding": "invalid"}},
        source_path="fixture.json",
        source_sha256="0" * 64,
    )

    projected = project_nz_fhir_record(record)

    assert projected.concept.preferred_name == "fallback-id"
    assert projected.concept.level == "unknown"
    assert projected.assertions == ()


def test_projection_rejects_non_medication_resource() -> None:
    record = FhirResourceRecord(
        resource_type="Organization",
        resource_id="org",
        resource={"resourceType": "Organization"},
        source_path="fixture.json",
        source_sha256="0" * 64,
    )

    with pytest.raises(ValueError, match="Expected Medication"):
        project_nz_fhir_record(record)
