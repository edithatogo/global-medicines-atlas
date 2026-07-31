"""Runtime canonical medicine schema-v2 migration and rollback contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from global_medicines_atlas.canonical_v2 import (
    Package,
    Price,
    Product,
    ScopedAssertion,
    StructuralEntity,
    StructuralProjection,
    migrate_record_v1_to_v2,
    rollback_record_v2_to_v1,
)
from global_medicines_atlas.models import (
    AssertionKind,
    CanonicalMedicineRecord,
    EvidenceStatus,
    Identifier,
    MedicineConcept,
    Provenance,
    StatusAssertion,
)


def _v1() -> CanonicalMedicineRecord:
    regulatory_provenance = Provenance(
        source_id="nz-medsafe",
        source_uri="https://example.invalid/source",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_sha256="a" * 64,
        source_path="row/1",
        transformation="representative-test-v1",
    )
    funding_provenance = regulatory_provenance.model_copy(
        update={"source_id": "nz-pharmac"}
    )
    return CanonicalMedicineRecord(
        concept=MedicineConcept(
            concept_id="nz:test-1",
            jurisdiction="NZL",
            level="product",
            preferred_name="Example medicine",
            identifiers=(Identifier(system="urn:test", value="1"),),
        ),
        assertions=(
            StatusAssertion(
                assertion_id="assertion:1",
                concept_id="nz:test-1",
                jurisdiction="NZL",
                kind=AssertionKind.REGULATORY,
                authority="Medsafe",
                status_code="approved",
                evidence_status=EvidenceStatus.CONFIRMED,
                provenance=regulatory_provenance,
            ),
            StatusAssertion(
                assertion_id="assertion:2",
                concept_id="nz:test-1",
                jurisdiction="NZL",
                kind=AssertionKind.FUNDING,
                authority="Pharmac",
                status_code="funded",
                evidence_status=EvidenceStatus.CONFIRMED,
                restrictions=("special-authority",),
                provenance=funding_provenance,
            ),
        ),
        provenance=(regulatory_provenance, funding_provenance),
    )


def _projection(record: CanonicalMedicineRecord) -> StructuralProjection:
    provenance = record.provenance[0]
    funding_provenance = record.provenance[1]
    native = (record.concept.concept_id,)
    substance = StructuralEntity(
        id="substance:1",
        label="Example ingredient",
        native_identifiers={"urn:test-substance": "S1"},
        provenance=(provenance,),
        source_native_ids=native,
    )
    product = Product(
        id="product:1",
        label="Example medicine",
        native_identifiers={"urn:test": "1"},
        provenance=(provenance,),
        source_native_ids=native,
        substance_ids=(substance.id,),
        dose_form="tablet",
        strength="10 mg",
    )
    package = Package(
        id="package:1",
        label="Example medicine 30 tablets",
        native_identifiers={"urn:test-package": "P1"},
        provenance=(provenance,),
        source_native_ids=native,
        product_id=product.id,
        quantity="30 tablets",
    )
    indication = ScopedAssertion(
        id="indication:1",
        subject_id=product.id,
        jurisdiction="NZL",
        scope="representative indication",
        evidence_id="assertion:1",
        assertion_kind=AssertionKind.REGULATORY,
        provenance=provenance,
        source_native_ids=native,
    )
    restriction = ScopedAssertion(
        id="restriction:1",
        subject_id=package.id,
        jurisdiction="NZL",
        scope="special-authority",
        evidence_id="assertion:2",
        assertion_kind=AssertionKind.FUNDING,
        provenance=funding_provenance,
        source_native_ids=native,
    )
    price = Price(
        id="price:1",
        package_id=package.id,
        jurisdiction="NZL",
        amount="12.34",
        currency="NZD",
        price_type="schedule",
        evidence_id="assertion:2",
        provenance=funding_provenance,
        source_native_ids=native,
    )
    return StructuralProjection(
        substances=(substance,),
        products=(product,),
        packages=(package,),
        indications=(indication,),
        prices=(price,),
        restrictions=(restriction,),
    )


def test_migration_round_trip_preserves_complete_v1_record() -> None:
    original = _v1()
    migrated = migrate_record_v1_to_v2(original, _projection(original))
    assert migrated.schema_version == 2
    assert rollback_record_v2_to_v1(migrated) == original
    assert migrated.indications[0].assertion_kind is AssertionKind.REGULATORY
    assert migrated.restrictions[0].assertion_kind is AssertionKind.FUNDING
    assert migrated.prices[0].assertion_kind is AssertionKind.FUNDING


@given(st.text(min_size=1).filter(lambda value: bool(value.strip())))
def test_round_trip_preserves_arbitrary_source_native_labels(
    label: str,
) -> None:
    original = _v1().model_copy(
        update={
            "concept": _v1().concept.model_copy(
                update={"preferred_name": label}
            )
        }
    )
    assert (
        rollback_record_v2_to_v1(
            migrate_record_v1_to_v2(original, _projection(original))
        )
        == original
    )


def test_migration_rejects_dangling_structural_reference() -> None:
    original = _v1()
    projection = _projection(original)
    broken = projection.model_copy(
        update={
            "packages": (
                projection.packages[0].model_copy(
                    update={"product_id": "missing"}
                ),
            )
        }
    )
    with pytest.raises(ValidationError, match="unknown product"):
        migrate_record_v1_to_v2(original, broken)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("products", "unknown substance"),
        ("prices", "unknown package"),
        ("indications", "unknown structural subject"),
    ],
)
def test_migration_rejects_other_dangling_references(
    field: str,
    message: str,
) -> None:
    original = _v1()
    projection = _projection(original)
    if field == "products":
        values: object = (
            projection.products[0].model_copy(
                update={"substance_ids": ("missing",)}
            ),
        )
    elif field == "prices":
        values = (
            projection.prices[0].model_copy(update={"package_id": "missing"}),
        )
    else:
        values = (
            projection.indications[0].model_copy(
                update={"subject_id": "missing"}
            ),
        )
    broken = projection.model_copy(update={field: values})
    with pytest.raises(ValidationError, match=message):
        migrate_record_v1_to_v2(original, broken)


def test_migration_rejects_unknown_source_native_reference() -> None:
    original = _v1()
    projection = _projection(original)
    broken = projection.model_copy(
        update={
            "substances": (
                projection.substances[0].model_copy(
                    update={"source_native_ids": ("unknown",)}
                ),
            )
        }
    )
    with pytest.raises(ValidationError, match="unknown source-native"):
        migrate_record_v1_to_v2(original, broken)


def test_migration_rejects_regulatory_funding_kind_substitution() -> None:
    original = _v1()
    projection = _projection(original)
    substituted = projection.model_copy(
        update={
            "restrictions": (
                projection.restrictions[0].model_copy(
                    update={"assertion_kind": AssertionKind.REGULATORY}
                ),
            )
        }
    )
    with pytest.raises(ValueError, match="assertion of the same kind"):
        migrate_record_v1_to_v2(original, substituted)


def test_migration_rejects_unrepresented_native_record() -> None:
    original = _v1()
    with pytest.raises(ValidationError, match="must be represented"):
        migrate_record_v1_to_v2(original, StructuralProjection())


def test_rollback_rejects_identity_substitution() -> None:
    original = _v1()
    migrated = migrate_record_v1_to_v2(original, _projection(original))
    substituted = migrated.model_copy(update={"record_id": "nz:other"})
    with pytest.raises(ValueError, match="identity does not match"):
        rollback_record_v2_to_v1(substituted)


def test_source_native_payload_digest_is_fail_closed() -> None:
    original = _v1()
    payload = migrate_record_v1_to_v2(
        original, _projection(original)
    ).model_dump()
    payload["source_native"][0]["payload"]["concept"]["preferred_name"] = (
        "altered"
    )
    with pytest.raises(ValidationError, match="digest mismatch"):
        type(
            migrate_record_v1_to_v2(original, _projection(original))
        ).model_validate(payload)
