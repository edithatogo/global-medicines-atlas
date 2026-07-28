"""Shared contracts for lawful, fixture-only jurisdiction adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Literal

import orjson
from pydantic import AnyUrl, TypeAdapter

from ..models import (
    AssertionKind,
    CanonicalMedicineRecord,
    EvidenceStatus,
    FrozenModel,
    Identifier,
    MedicineConcept,
    Provenance,
    StatusAssertion,
)
from ..receipts import (
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

SourceContract = tuple[str, AssertionKind, str]


class FixtureSource(FrozenModel):
    source_id: str
    title: str
    evidence_limit: str


class FixtureAssertion(FrozenModel):
    source_id: str
    status_code: str
    restrictions: tuple[str, ...] = ()


class FixtureMedicine(FrozenModel):
    id: str
    level: str
    name: str
    identifier_system: str
    identifier: str
    assertions: tuple[FixtureAssertion, ...]


class FixtureDocument(FrozenModel):
    fixture_version: str
    sources: tuple[FixtureSource, ...]
    medicines: tuple[FixtureMedicine, ...]


DOCUMENT_ADAPTER = TypeAdapter(FixtureDocument)


@dataclass(frozen=True, slots=True)
class SourceAccessLimit:
    """Explicit boundary between a fixture contract and a live source."""

    source_id: str
    access: Literal["synthetic-fixture", "licensed-declaration-only"]
    rights_state: RightsState
    payload_included: bool
    evidence_limit: str


@dataclass(frozen=True, slots=True)
class FixtureProjection:
    """Canonical fixture output with receipts and access declarations."""

    records: tuple[CanonicalMedicineRecord, ...]
    receipts: tuple[SourceReceipt, ...]
    access_limits: tuple[SourceAccessLimit, ...]


def load_fixture_document(payload: bytes) -> FixtureDocument:
    """Parse a synthetic JSON fixture without performing network access."""
    return DOCUMENT_ADAPTER.validate_json(payload)


def _project_record(
    item: FixtureMedicine,
    *,
    jurisdiction: str,
    source_contracts: dict[str, SourceContract],
    payload_evidence: PayloadEvidence,
    retrieved_at: datetime,
    fixture_version: str,
    transformation_id: str,
) -> CanonicalMedicineRecord:
    local_id = item.id
    concept_id = f"{jurisdiction.casefold()}:{local_id}"
    provenance_by_source: dict[str, Provenance] = {}
    assertions: list[StatusAssertion] = []
    for index, raw_assertion in enumerate(item.assertions):
        source_id = raw_assertion.source_id
        if source_id not in source_contracts:
            raise ValueError(f"Undeclared fixture source: {source_id}")
        authority, kind, _source_uri = source_contracts[source_id]
        provenance = provenance_by_source.setdefault(
            source_id,
            Provenance(
                source_id=source_id,
                source_uri=f"fixture://{source_id}",
                retrieved_at=retrieved_at,
                source_sha256=payload_evidence.sha256,
                source_version=fixture_version,
                transformation=transformation_id,
            ),
        )
        assertions.append(
            StatusAssertion(
                assertion_id=f"{source_id}:{local_id}:{index}",
                concept_id=concept_id,
                jurisdiction=jurisdiction,
                kind=kind,
                authority=authority,
                status_code=raw_assertion.status_code,
                # Fixture projection validates adapter shape only. Promotion to
                # confirmed evidence requires a separate live-source ingestor
                # with a qualifying receipt.
                evidence_status=EvidenceStatus.UNKNOWN,
                restrictions=raw_assertion.restrictions,
                provenance=provenance,
            )
        )
    if not assertions:
        raise ValueError("Every fixture medicine requires an assertion")
    return CanonicalMedicineRecord(
        concept=MedicineConcept(
            concept_id=concept_id,
            jurisdiction=jurisdiction,
            level=item.level,
            preferred_name=item.name,
            identifiers=(
                Identifier(
                    system=item.identifier_system,
                    value=item.identifier,
                ),
            ),
        ),
        assertions=tuple(assertions),
        provenance=tuple(
            provenance_by_source[key] for key in sorted(provenance_by_source)
        ),
    )


def _make_receipt(
    *,
    source_id: str,
    authority: str,
    jurisdiction: str,
    fixture_version: str,
    title: str,
    retrieved_at: datetime,
    payload_evidence: PayloadEvidence,
    transformation_id: str,
    output: bytes,
) -> SourceReceipt:
    return SourceReceipt(
        receipt_id=f"{source_id}:{payload_evidence.sha256}",
        source=SourceIdentity(
            catalog_id=source_id,
            source_id=source_id,
            jurisdiction=jurisdiction,
            authority=authority,
            dataset_title=title,
            catalog_version=fixture_version,
        ),
        retrieval=RetrievalEvidence(
            uri=AnyUrl(f"https://fixtures.invalid/{source_id}.json"),
            retrieved_at=retrieved_at,
            acquisition_method=AcquisitionMethod.LOCAL_FIXTURE,
            status=AcquisitionStatus.SUCCEEDED,
        ),
        payload=payload_evidence,
        rights_state=RightsState.PERMITTED,
        rights_reference=AnyUrl("https://fixtures.invalid/rights/synthetic"),
        evidence_class=EvidenceClass.SYNTHETIC,
        transformation=TransformationEvidence(
            transformation_id=transformation_id,
            transformation_sha256=sha256(
                transformation_id.encode()
            ).hexdigest(),
            output_sha256=sha256(output).hexdigest(),
            output_byte_count=len(output),
        ),
    )


def project_fixture(
    *,
    payload: bytes,
    retrieved_at: datetime,
    jurisdiction: str,
    transformation_id: str,
    source_contracts: dict[str, SourceContract],
) -> FixtureProjection:
    """Project a strict synthetic fixture into canonical assertions."""
    document = load_fixture_document(payload)
    declared_sources = {source.source_id: source for source in document.sources}
    if set(declared_sources) != set(source_contracts):
        raise ValueError("Fixture sources do not match adapter contract")

    payload_evidence = PayloadEvidence.from_bytes(payload)
    fixture_version = document.fixture_version
    records = [
        _project_record(
            item,
            jurisdiction=jurisdiction,
            source_contracts=source_contracts,
            payload_evidence=payload_evidence,
            retrieved_at=retrieved_at,
            fixture_version=fixture_version,
            transformation_id=transformation_id,
        )
        for item in document.medicines
    ]

    output = orjson.dumps(
        [
            record.model_dump(mode="json")
            for record in sorted(
                records,
                key=lambda record: record.concept.concept_id,
            )
        ],
        option=orjson.OPT_SORT_KEYS,
    )
    receipts: list[SourceReceipt] = []
    limits: list[SourceAccessLimit] = []
    for source_id, (authority, _kind, source_uri) in source_contracts.items():
        declaration = declared_sources[source_id]
        evidence_limit = declaration.evidence_limit
        receipts.append(
            _make_receipt(
                source_id=source_id,
                authority=authority,
                jurisdiction=jurisdiction,
                fixture_version=fixture_version,
                title=declaration.title,
                retrieved_at=retrieved_at,
                payload_evidence=payload_evidence,
                transformation_id=transformation_id,
                output=output,
            )
        )
        limits.append(
            SourceAccessLimit(
                source_id=source_id,
                access="synthetic-fixture",
                rights_state=RightsState.PERMITTED,
                payload_included=True,
                evidence_limit=(
                    f"{evidence_limit} Live source not accessed; "
                    f"landing page is {source_uri}."
                ),
            )
        )
    return FixtureProjection(
        records=tuple(
            sorted(records, key=lambda record: record.concept.concept_id)
        ),
        receipts=tuple(receipts),
        access_limits=tuple(limits),
    )
