from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyUrl

from global_medicines_atlas.adapters.european_union import (
    project_ema_medicine_csv,
    project_union_register_xml,
)
from global_medicines_atlas.adapters.united_kingdom import (
    DMD_DECLARATION,
    project_mhra_products_csv,
    project_nice_appraisals_xml,
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

FIXTURES = Path(__file__).parent / "fixtures" / "native"
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
) -> SourceReceipt:
    evidence = PayloadEvidence.from_bytes(payload)
    return SourceReceipt(
        receipt_id=f"synthetic:{source_id}",
        source=SourceIdentity(
            catalog_id=source_id,
            source_id=source_id,
            jurisdiction=jurisdiction,
            authority="Synthetic test authority",
            dataset_title=f"Synthetic native fixture for {source_id}",
            catalog_version="synthetic-native-v1",
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(f"https://fixtures.invalid/{source_id}"),
            retrieved_at=datetime(2026, 7, 29, tzinfo=UTC),
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=evidence,
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id=f"{source_id}-synthetic-native-v1",
            transformation_sha256=SHA,
            output_sha256=evidence.sha256,
            output_byte_count=evidence.byte_count,
        ),
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    (
        "path",
        "projector",
        "source_id",
        "jurisdiction",
        "kind",
        "concept_id",
        "level",
    ),
    [
        (
            FIXTURES / "eu" / "ema_medicines.csv",
            project_ema_medicine_csv,
            "eu-ema",
            "EU",
            AssertionKind.REGULATORY,
            "eu-ema:EMEA/H/C/000001",
            "centrally-authorised-product",
        ),
        (
            FIXTURES / "eu" / "union_register.xml",
            project_union_register_xml,
            "eu-union-register",
            "EU",
            AssertionKind.REGULATORY,
            "eu-union-register:EU/1/26/000001",
            "centrally-authorised-product",
        ),
        (
            FIXTURES / "gb" / "mhra_products.csv",
            project_mhra_products_csv,
            "uk-mhra",
            "GBR",
            AssertionKind.REGULATORY,
            "uk-mhra:PL 00001/0001",
            "nationally-authorised-product",
        ),
        (
            FIXTURES / "gb" / "nice_appraisals.xml",
            project_nice_appraisals_xml,
            "uk-nice",
            "GBR",
            AssertionKind.FUNDING,
            "uk-nice:TA999",
            "appraisal",
        ),
    ],
)
def test_native_fixture_projection_is_receipt_bound_and_separated(
    path: Path,
    projector: Projector,
    source_id: str,
    jurisdiction: str,
    kind: AssertionKind,
    concept_id: str,
    level: str,
) -> None:
    payload = path.read_bytes()
    receipt = _receipt(
        payload,
        source_id=source_id,
        jurisdiction=jurisdiction,
    )

    records = projector(payload, receipt)

    assert len(records) == 1
    record = records[0]
    assert record.concept.concept_id == concept_id
    assert record.concept.level == level
    assert {item.kind for item in record.assertions} == {kind}
    assert record.assertions[0].evidence_status is EvidenceStatus.UNKNOWN
    assert record.provenance[0].source_sha256 == receipt.payload.sha256


@pytest.mark.edge
@pytest.mark.parametrize(
    ("path", "projector", "source_id", "jurisdiction"),
    [
        (
            FIXTURES / "eu" / "ema_medicines.csv",
            project_ema_medicine_csv,
            "eu-ema",
            "EU",
        ),
        (
            FIXTURES / "eu" / "union_register.xml",
            project_union_register_xml,
            "eu-union-register",
            "EU",
        ),
        (
            FIXTURES / "gb" / "mhra_products.csv",
            project_mhra_products_csv,
            "uk-mhra",
            "GBR",
        ),
        (
            FIXTURES / "gb" / "nice_appraisals.xml",
            project_nice_appraisals_xml,
            "uk-nice",
            "GBR",
        ),
    ],
)
def test_native_adapter_rejects_payload_tampering(
    path: Path,
    projector: Projector,
    source_id: str,
    jurisdiction: str,
) -> None:
    payload = path.read_bytes()
    receipt = _receipt(
        payload,
        source_id=source_id,
        jurisdiction=jurisdiction,
    )

    with pytest.raises(ValueError, match="does not match"):
        projector(payload + b"\n", receipt)


@pytest.mark.edge
@pytest.mark.parametrize(
    ("projector", "source_id", "jurisdiction", "root"),
    [
        (
            project_union_register_xml,
            "eu-union-register",
            "EU",
            "community-register",
        ),
        (
            project_nice_appraisals_xml,
            "uk-nice",
            "GBR",
            "nice-guidance",
        ),
    ],
)
def test_xml_adapter_rejects_dtd(
    projector: Projector,
    source_id: str,
    jurisdiction: str,
    root: str,
) -> None:
    payload = (
        f'<!DOCTYPE {root} [<!ENTITY xxe "unsafe">]><{root}>&xxe;</{root}>'
    ).encode()
    receipt = _receipt(
        payload,
        source_id=source_id,
        jurisdiction=jurisdiction,
    )

    with pytest.raises(ValueError, match="must not contain"):
        projector(payload, receipt)


@pytest.mark.edge
@pytest.mark.parametrize(
    ("projector", "source_id", "jurisdiction"),
    [
        (project_ema_medicine_csv, "eu-ema", "EU"),
        (project_union_register_xml, "eu-union-register", "EU"),
        (project_mhra_products_csv, "uk-mhra", "GBR"),
        (project_nice_appraisals_xml, "uk-nice", "GBR"),
    ],
)
def test_native_adapter_enforces_bounded_payload(
    projector: Projector,
    source_id: str,
    jurisdiction: str,
) -> None:
    payload = b"x" * 1_000_001

    with pytest.raises(ValueError, match="exceeds the 1 MB"):
        projector(
            payload,
            _receipt(
                payload,
                source_id=source_id,
                jurisdiction=jurisdiction,
            ),
        )


def test_native_adapter_rejects_wrong_source_receipt() -> None:
    payload = (FIXTURES / "eu" / "ema_medicines.csv").read_bytes()
    receipt = _receipt(
        payload,
        source_id="eu-union-register",
        jurisdiction="EU",
    )

    with pytest.raises(ValueError, match="Expected source_id"):
        project_ema_medicine_csv(payload, receipt)


def test_nice_restrictions_and_dmd_boundary_are_explicit() -> None:
    payload = (FIXTURES / "gb" / "nice_appraisals.xml").read_bytes()
    records = project_nice_appraisals_xml(
        payload,
        _receipt(payload, source_id="uk-nice", jurisdiction="GBR"),
    )

    assert records[0].assertions[0].restrictions == (
        "Specialist initiation only",
    )
    assert DMD_DECLARATION.access == "licensed-declaration-only"
    assert DMD_DECLARATION.rights_state is RightsState.RESTRICTED
    assert DMD_DECLARATION.payload_included is False
