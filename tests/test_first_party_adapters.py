"""Fixture-driven contracts for NZ and Australian first-party adapters."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyUrl

from global_medicines_atlas.adapters.au_artg import project_artg_csv
from global_medicines_atlas.adapters.au_pbs import project_pbs_xml
from global_medicines_atlas.adapters.nz_medsafe import (
    project_medsafe_registry_csv,
)
from global_medicines_atlas.adapters.nz_pharmac import (
    project_pharmac_schedule_xml,
)
from global_medicines_atlas.models import (
    AssertionKind,
    CanonicalMedicineRecord,
    EvidenceStatus,
)
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

FIXTURES = Path(__file__).parent / "fixtures" / "adapters"
SHA = "a" * 64
Projector = Callable[
    [bytes, SourceReceipt],
    tuple[CanonicalMedicineRecord, ...],
]


def _receipt(
    payload: bytes,
    *,
    source_id: str,
    jurisdiction: str,
    authority: str,
    live: bool = False,
) -> SourceReceipt:
    payload_evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id=f"fixture:{source_id}",
        source=SourceIdentity(
            catalog_id=source_id,
            source_id=source_id,
            jurisdiction=jurisdiction,
            authority=authority,
            dataset_title=f"Synthetic fixture for {source_id}",
            catalog_version="fixture-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(f"https://fixtures.invalid/{source_id}"),
            retrieved_at=datetime(2026, 7, 29, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=payload_evidence,
        rights_state=RightsState.PERMITTED if live else RightsState.UNKNOWN,
        rights_reference=(
            AnyUrl(f"https://rights.example/{source_id}") if live else None
        ),
        evidence_class=EvidenceClass.LIVE if live else EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id=f"{source_id}-fixture",
            transformation_sha256=SHA,
            output_sha256=payload_evidence.sha256,
            output_byte_count=payload_evidence.byte_count,
        ),
    )


@pytest.mark.parametrize(
    (
        "fixture_name",
        "projector",
        "source_id",
        "jurisdiction",
        "authority",
        "expected_kind",
        "expected_concept_id",
        "expected_status",
    ),
    [
        (
            "nz_pharmac_schedule.xml",
            project_pharmac_schedule_xml,
            "nz-pharmac",
            "NZL",
            "Pharmac",
            AssertionKind.FUNDING,
            "nz-pharmac:1234567",
            "funded",
        ),
        (
            "nz_medsafe_registry.csv",
            project_medsafe_registry_csv,
            "nz-medsafe",
            "NZL",
            "Medsafe",
            AssertionKind.REGULATORY,
            "nz-medsafe:TT50-0001",
            "consent-given",
        ),
        (
            "au_artg.csv",
            project_artg_csv,
            "au-artg",
            "AUS",
            "Therapeutic Goods Administration",
            AssertionKind.REGULATORY,
            "au-artg:123456",
            "active",
        ),
        (
            "au_pbs.xml",
            project_pbs_xml,
            "au-pbs",
            "AUS",
            "Department of Health, Disability and Ageing",
            AssertionKind.FUNDING,
            "au-pbs:1234A",
            "listed",
        ),
    ],
)
def test_adapter_projects_one_evidence_dimension(
    fixture_name: str,
    projector: Projector,
    source_id: str,
    jurisdiction: str,
    authority: str,
    expected_kind: AssertionKind,
    expected_concept_id: str,
    expected_status: str,
) -> None:
    payload = (FIXTURES / fixture_name).read_bytes()
    receipt = _receipt(
        payload,
        source_id=source_id,
        jurisdiction=jurisdiction,
        authority=authority,
    )

    records = projector(payload, receipt)

    assert len(records) == 1
    record = records[0]
    assert record.concept.concept_id == expected_concept_id
    assert record.concept.jurisdiction == jurisdiction
    assert len(record.assertions) == 1
    assertion = record.assertions[0]
    assert assertion.kind is expected_kind
    assert assertion.status_code == expected_status
    assert assertion.evidence_status is EvidenceStatus.UNKNOWN
    assert assertion.provenance.source_sha256 == receipt.payload.sha256
    assert assertion.provenance.source_version == "fixture-v1"


@pytest.mark.parametrize(
    ("fixture_name", "projector", "source_id", "jurisdiction", "authority"),
    [
        (
            "nz_pharmac_schedule.xml",
            project_pharmac_schedule_xml,
            "nz-pharmac",
            "NZL",
            "Pharmac",
        ),
        (
            "nz_medsafe_registry.csv",
            project_medsafe_registry_csv,
            "nz-medsafe",
            "NZL",
            "Medsafe",
        ),
        (
            "au_artg.csv",
            project_artg_csv,
            "au-artg",
            "AUS",
            "Therapeutic Goods Administration",
        ),
        (
            "au_pbs.xml",
            project_pbs_xml,
            "au-pbs",
            "AUS",
            "Department of Health, Disability and Ageing",
        ),
    ],
)
def test_adapter_confirms_only_qualifying_live_receipts(
    fixture_name: str,
    projector: Projector,
    source_id: str,
    jurisdiction: str,
    authority: str,
) -> None:
    payload = (FIXTURES / fixture_name).read_bytes()
    receipt = _receipt(
        payload,
        source_id=source_id,
        jurisdiction=jurisdiction,
        authority=authority,
        live=True,
    )

    records = projector(payload, receipt)

    assert receipt.satisfies_live_gate
    assert records[0].assertions[0].evidence_status is EvidenceStatus.CONFIRMED


@pytest.mark.parametrize(
    ("fixture_name", "projector", "source_id", "jurisdiction", "authority"),
    [
        (
            "nz_pharmac_schedule.xml",
            project_pharmac_schedule_xml,
            "nz-pharmac",
            "NZL",
            "Pharmac",
        ),
        (
            "nz_medsafe_registry.csv",
            project_medsafe_registry_csv,
            "nz-medsafe",
            "NZL",
            "Medsafe",
        ),
        (
            "au_artg.csv",
            project_artg_csv,
            "au-artg",
            "AUS",
            "Therapeutic Goods Administration",
        ),
        (
            "au_pbs.xml",
            project_pbs_xml,
            "au-pbs",
            "AUS",
            "Department of Health, Disability and Ageing",
        ),
    ],
)
def test_adapter_rejects_payload_not_bound_to_receipt(
    fixture_name: str,
    projector: Projector,
    source_id: str,
    jurisdiction: str,
    authority: str,
) -> None:
    payload = (FIXTURES / fixture_name).read_bytes()
    receipt = _receipt(
        payload,
        source_id=source_id,
        jurisdiction=jurisdiction,
        authority=authority,
    )

    with pytest.raises(ValueError, match="does not match"):
        projector(payload + b"\n", receipt)


def test_regulatory_and_funding_sources_remain_separate() -> None:
    cases = (
        (
            "nz_medsafe_registry.csv",
            project_medsafe_registry_csv,
            _receipt(
                (FIXTURES / "nz_medsafe_registry.csv").read_bytes(),
                source_id="nz-medsafe",
                jurisdiction="NZL",
                authority="Medsafe",
            ),
            AssertionKind.REGULATORY,
        ),
        (
            "nz_pharmac_schedule.xml",
            project_pharmac_schedule_xml,
            _receipt(
                (FIXTURES / "nz_pharmac_schedule.xml").read_bytes(),
                source_id="nz-pharmac",
                jurisdiction="NZL",
                authority="Pharmac",
            ),
            AssertionKind.FUNDING,
        ),
        (
            "au_artg.csv",
            project_artg_csv,
            _receipt(
                (FIXTURES / "au_artg.csv").read_bytes(),
                source_id="au-artg",
                jurisdiction="AUS",
                authority="Therapeutic Goods Administration",
            ),
            AssertionKind.REGULATORY,
        ),
        (
            "au_pbs.xml",
            project_pbs_xml,
            _receipt(
                (FIXTURES / "au_pbs.xml").read_bytes(),
                source_id="au-pbs",
                jurisdiction="AUS",
                authority="Department of Health, Disability and Ageing",
            ),
            AssertionKind.FUNDING,
        ),
    )

    for fixture_name, projector, receipt, expected_kind in cases:
        records = projector((FIXTURES / fixture_name).read_bytes(), receipt)
        kinds = {
            assertion.kind
            for record in records
            for assertion in record.assertions
        }
        assert kinds == {expected_kind}
