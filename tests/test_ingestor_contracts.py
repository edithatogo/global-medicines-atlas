from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

import pytest
from pydantic import ValidationError

from global_medicines_atlas.ingestors import (
    PayloadMember,
    PayloadSet,
    ProjectionSchema,
    project_payload_set,
)
from global_medicines_atlas.models import (
    CanonicalMedicineRecord,
    MedicineConcept,
    Provenance,
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

NOW = datetime(2026, 7, 29, tzinfo=UTC)


def receipt(name: str, payload: bytes) -> SourceReceipt:
    digest = sha256(payload).hexdigest()
    return SourceReceipt(
        receipt_id=f"receipt-{name}",
        source=SourceIdentity(
            catalog_id="test-source",
            source_id="test-source",
            jurisdiction="NZL",
            authority="Test Authority",
            dataset_title="Test data",
            catalog_version="1",
        ),
        retrieval=RetrievalEvidence(
            uri=f"https://example.test/{name}",
            retrieved_at=NOW,
            acquisition_method=AcquisitionMethod.DOWNLOAD,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=PayloadEvidence.from_bytes(payload),
        rights_state=RightsState.UNKNOWN,
        evidence_class=EvidenceClass.FIXTURE,
        transformation=TransformationEvidence(
            transformation_id="raw-v1",
            transformation_sha256="a" * 64,
            output_sha256=digest,
            output_byte_count=len(payload),
        ),
    )


def member(name: str, payload: bytes) -> PayloadMember:
    return PayloadMember(
        name=name,
        payload=payload,
        receipt=receipt(name, payload),
    )


def record(concept_id: str = "nz:test") -> CanonicalMedicineRecord:
    provenance = Provenance(
        source_id="test-source",
        source_uri="https://example.test/",
    )
    return CanonicalMedicineRecord(
        concept=MedicineConcept(
            concept_id=concept_id,
            jurisdiction="NZL",
            level="product",
            preferred_name="Test medicine",
        ),
        provenance=(provenance,),
    )


@pytest.mark.unit
def test_payload_set_lineage_is_order_independent() -> None:
    first = member("first.csv", b"first")
    second = member("second.csv", b"second")

    left = PayloadSet(
        source_id="test-source",
        jurisdiction="NZL",
        members=(first, second),
    )
    right = PayloadSet(
        source_id="test-source",
        jurisdiction="NZL",
        members=(second, first),
    )

    assert left.lineage_digest == right.lineage_digest
    assert left.receipt_ids == ("receipt-first.csv", "receipt-second.csv")


@pytest.mark.edge
def test_payload_member_rejects_bytes_not_qualified_by_receipt() -> None:
    with pytest.raises(ValidationError, match="do not match"):
        PayloadMember(
            name="changed.csv",
            payload=b"changed",
            receipt=receipt("changed.csv", b"original"),
        )


@pytest.mark.edge
def test_payload_set_rejects_duplicate_names_and_mixed_sources() -> None:
    duplicate = member("same.csv", b"same")
    with pytest.raises(ValidationError, match="names must be unique"):
        PayloadSet(
            source_id="test-source",
            jurisdiction="NZL",
            members=(duplicate, duplicate),
        )

    other = duplicate.model_copy(
        update={
            "receipt": duplicate.receipt.model_copy(
                update={
                    "source": duplicate.receipt.source.model_copy(
                        update={"source_id": "other-source"}
                    )
                }
            )
        }
    )
    with pytest.raises(ValidationError, match="match the payload source"):
        PayloadSet(
            source_id="test-source",
            jurisdiction="NZL",
            members=(other,),
        )


@pytest.mark.unit
def test_schema_fingerprint_is_stable_across_mapping_order() -> None:
    left = ProjectionSchema(
        schema_id="products-v1",
        fields={"id": "string", "status": "string"},
    )
    right = ProjectionSchema(
        schema_id="products-v1",
        fields={"status": "string", "id": "string"},
    )

    assert left.fingerprint == right.fingerprint


@pytest.mark.integration
def test_projection_outcome_binds_records_to_lineage_and_schema() -> None:
    payloads = PayloadSet(
        source_id="test-source",
        jurisdiction="NZL",
        members=(member("products.csv", b"id,name\n1,test\n"),),
    )
    schema = ProjectionSchema(
        schema_id="products-v1",
        fields={"id": "string", "name": "string"},
    )
    outcome = project_payload_set(
        payloads,
        schema,
        projection_id="canonical-products-v1",
        population_id="all-current-products",
        projector=lambda _payloads, _schema: (record(),),
    )

    assert outcome.payload_set_digest == payloads.lineage_digest
    assert outcome.receipt_ids == payloads.receipt_ids
    assert outcome.schema_fingerprint == schema.fingerprint
    assert len(outcome.projection_digest) == 64


@pytest.mark.edge
def test_projection_rejects_duplicate_concepts_and_wrong_jurisdiction() -> None:
    payloads = PayloadSet(
        source_id="test-source",
        jurisdiction="NZL",
        members=(member("products.csv", b"fixture"),),
    )
    schema = ProjectionSchema(
        schema_id="products-v1",
        fields={"id": "string"},
    )

    with pytest.raises(ValidationError, match="must be unique"):
        project_payload_set(
            payloads,
            schema,
            projection_id="projection-v1",
            population_id="population",
            projector=lambda _payloads, _schema: (record(), record()),
        )

    wrong = record().model_copy(
        update={
            "concept": record().concept.model_copy(
                update={"jurisdiction": "AUS"}
            )
        }
    )
    with pytest.raises(ValidationError, match="match the jurisdiction"):
        project_payload_set(
            payloads,
            schema,
            projection_id="projection-v1",
            population_id="population",
            projector=lambda _payloads, _schema: (wrong,),
        )
