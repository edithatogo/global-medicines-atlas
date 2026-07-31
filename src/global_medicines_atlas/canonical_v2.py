"""Lossless, fail-closed canonical medicine structural migration.

Schema v2 is structural.  It must not infer structures that schema-v1 adapter
records do not contain.  Callers therefore provide an explicit projection and
the migration binds that projection to the complete source-native v1 record.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Literal, Self

import orjson
from pydantic import Field, JsonValue, model_validator

from .models import (
    AssertionKind,
    CanonicalMedicineRecord,
    FrozenModel,
    Provenance,
)

SCHEMA_ID = "global-medicines-atlas.canonical-medicine"


def _canonical_bytes(value: JsonValue) -> bytes:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS)


class SourceNativePayload(FrozenModel):
    """Complete source-native record, protected against silent alteration."""

    source_id: str = Field(min_length=1)
    native_record_id: str = Field(min_length=1)
    media_type: Literal["application/json"] = "application/json"
    payload: JsonValue
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def digest_matches_payload(self) -> Self:
        if sha256(_canonical_bytes(self.payload)).hexdigest() != self.sha256:
            raise ValueError("source-native payload digest mismatch")
        return self


class StructuralEntity(FrozenModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    native_identifiers: dict[str, str] = Field(min_length=1)
    provenance: tuple[Provenance, ...] = Field(min_length=1)
    source_native_ids: tuple[str, ...] = Field(min_length=1)


class Product(StructuralEntity):
    substance_ids: tuple[str, ...] = Field(min_length=1)
    dose_form: str | None = None
    strength: str | None = None


class Package(StructuralEntity):
    product_id: str = Field(min_length=1)
    quantity: str | None = None


class ScopedAssertion(FrozenModel):
    id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    jurisdiction: str = Field(pattern=r"^[A-Z]{2,3}$")
    scope: str = Field(min_length=1)
    population: str | None = None
    evidence_id: str = Field(min_length=1)
    assertion_kind: AssertionKind
    provenance: Provenance
    source_native_ids: tuple[str, ...] = Field(min_length=1)


class Price(FrozenModel):
    id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    jurisdiction: str = Field(pattern=r"^[A-Z]{2,3}$")
    amount: str = Field(pattern=r"^[0-9]+(\.[0-9]+)?$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    price_type: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    assertion_kind: Literal[AssertionKind.FUNDING] = AssertionKind.FUNDING
    provenance: Provenance
    source_native_ids: tuple[str, ...] = Field(min_length=1)


class CanonicalMedicineV2(FrozenModel):
    schema_id: Literal["global-medicines-atlas.canonical-medicine"] = SCHEMA_ID
    schema_version: Literal[2] = 2
    record_id: str = Field(min_length=1)
    substances: tuple[StructuralEntity, ...] = ()
    products: tuple[Product, ...] = ()
    packages: tuple[Package, ...] = ()
    indications: tuple[ScopedAssertion, ...] = ()
    prices: tuple[Price, ...] = ()
    restrictions: tuple[ScopedAssertion, ...] = ()
    source_native: tuple[SourceNativePayload, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def references_are_closed(self) -> Self:
        native_ids = [item.native_record_id for item in self.source_native]
        if len(native_ids) != len(set(native_ids)):
            raise ValueError("source-native record identifiers must be unique")
        available_native = set(native_ids)
        entities = (*self.substances, *self.products, *self.packages)
        entity_ids = [item.id for item in entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("structural identifiers must be unique")
        substances = {item.id for item in self.substances}
        products = {item.id for item in self.products}
        packages = {item.id for item in self.packages}
        if any(
            not set(item.substance_ids) <= substances for item in self.products
        ):
            raise ValueError("product references an unknown substance")
        if any(item.product_id not in products for item in self.packages):
            raise ValueError("package references an unknown product")
        if any(item.package_id not in packages for item in self.prices):
            raise ValueError("price references an unknown package")
        subjects = substances | products | packages
        if any(
            item.subject_id not in subjects
            for item in (*self.indications, *self.restrictions)
        ):
            raise ValueError(
                "assertion references an unknown structural subject"
            )
        referenced = {
            native_id
            for item in (
                *entities,
                *self.indications,
                *self.prices,
                *self.restrictions,
            )
            for native_id in item.source_native_ids
        }
        if not referenced <= available_native:
            raise ValueError(
                "projection references an unknown source-native record"
            )
        if referenced != available_native:
            raise ValueError("every source-native record must be represented")
        return self


class StructuralProjection(FrozenModel):
    """Explicit adapter-owned structure; no field is inferred by migration."""

    substances: tuple[StructuralEntity, ...] = ()
    products: tuple[Product, ...] = ()
    packages: tuple[Package, ...] = ()
    indications: tuple[ScopedAssertion, ...] = ()
    prices: tuple[Price, ...] = ()
    restrictions: tuple[ScopedAssertion, ...] = ()


def migrate_record_v1_to_v2(
    record: CanonicalMedicineRecord,
    projection: StructuralProjection,
) -> CanonicalMedicineV2:
    """Bind an explicit structural projection to a complete v1 record."""
    assertion_kinds = {
        assertion.assertion_id: assertion.kind
        for assertion in record.assertions
    }
    projected_assertions = (
        *projection.indications,
        *projection.prices,
        *projection.restrictions,
    )
    if any(
        assertion_kinds.get(item.evidence_id) is not item.assertion_kind
        for item in projected_assertions
    ):
        raise ValueError(
            "structural evidence must reference a v1 assertion of the same kind"
        )
    payload = record.model_dump(mode="json")
    native = SourceNativePayload(
        source_id="canonical-schema-v1",
        native_record_id=record.concept.concept_id,
        payload=payload,
        sha256=sha256(_canonical_bytes(payload)).hexdigest(),
    )
    return CanonicalMedicineV2(
        record_id=record.concept.concept_id,
        source_native=(native,),
        **projection.model_dump(),
    )


def rollback_record_v2_to_v1(
    record: CanonicalMedicineV2,
) -> CanonicalMedicineRecord:
    """Restore the exact v1 semantic record or reject a non-v1 envelope."""
    if len(record.source_native) != 1:
        raise ValueError(
            "v1 rollback requires exactly one source-native record"
        )
    native = record.source_native[0]
    if native.source_id != "canonical-schema-v1":
        raise ValueError("v1 rollback requires a canonical-schema-v1 payload")
    restored = CanonicalMedicineRecord.model_validate(native.payload)
    if restored.concept.concept_id != record.record_id:
        raise ValueError(
            "source-native record identity does not match schema v2"
        )
    return restored
