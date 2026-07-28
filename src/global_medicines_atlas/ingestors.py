"""Deterministic contracts shared by governed source ingestors."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from typing import Any

import orjson
from pydantic import Field, model_validator

from .models import CanonicalMedicineRecord, FrozenModel
from .receipts import SourceReceipt


def _canonical_digest(value: object) -> str:
    return sha256(orjson.dumps(value, option=orjson.OPT_SORT_KEYS)).hexdigest()


class PayloadMember(FrozenModel):
    """One named payload whose bytes are qualified by a source receipt."""

    name: str = Field(min_length=1)
    payload: bytes
    receipt: SourceReceipt

    @model_validator(mode="after")
    def payload_matches_receipt(self) -> PayloadMember:
        if not self.receipt.payload.matches(self.payload):
            raise ValueError("payload bytes do not match the source receipt")
        return self


class PayloadSet(FrozenModel):
    """A deterministic, source-consistent set of acquired payloads."""

    source_id: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=2, max_length=3)
    members: tuple[PayloadMember, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def members_are_consistent(self) -> PayloadSet:
        names = [member.name for member in self.members]
        if len(names) != len(set(names)):
            raise ValueError("payload member names must be unique")
        for member in self.members:
            source = member.receipt.source
            if source.source_id != self.source_id:
                raise ValueError("all receipts must match the payload source")
            if source.jurisdiction != self.jurisdiction:
                raise ValueError(
                    "all receipts must match the payload jurisdiction"
                )
        return self

    @property
    def lineage_digest(self) -> str:
        """Identify the set independently of caller-provided member order."""

        lineage = [
            {
                "name": member.name,
                "payload_sha256": member.receipt.payload.sha256,
                "payload_bytes": member.receipt.payload.byte_count,
                "receipt_digest": member.receipt.digest(),
            }
            for member in sorted(self.members, key=lambda item: item.name)
        ]
        return _canonical_digest({
            "jurisdiction": self.jurisdiction,
            "members": lineage,
            "source_id": self.source_id,
        })

    @property
    def receipt_ids(self) -> tuple[str, ...]:
        return tuple(
            member.receipt.receipt_id
            for member in sorted(self.members, key=lambda item: item.name)
        )


class ProjectionSchema(FrozenModel):
    """Versioned logical input schema used by a projection."""

    schema_id: str = Field(min_length=1)
    fields: Mapping[str, str] = Field(min_length=1)

    @property
    def fingerprint(self) -> str:
        return _canonical_digest({
            "fields": dict(sorted(self.fields.items())),
            "schema_id": self.schema_id,
        })


class ProjectionOutcome(FrozenModel):
    """Canonical records plus reproducible lineage for one projection."""

    source_id: str = Field(min_length=1)
    jurisdiction: str = Field(min_length=2, max_length=3)
    projection_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    payload_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_ids: tuple[str, ...] = Field(min_length=1)
    schema_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    records: tuple[CanonicalMedicineRecord, ...]
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def records_match_outcome(self) -> ProjectionOutcome:
        if len(self.receipt_ids) != len(set(self.receipt_ids)):
            raise ValueError("projection receipt identifiers must be unique")
        concept_ids = [record.concept.concept_id for record in self.records]
        if len(concept_ids) != len(set(concept_ids)):
            raise ValueError("projection concept identifiers must be unique")
        if any(
            record.concept.jurisdiction != self.jurisdiction
            for record in self.records
        ):
            raise ValueError(
                "all projected records must match the jurisdiction"
            )
        return self

    @property
    def projection_digest(self) -> str:
        """Identify records and lineage without relying on object ordering."""

        records = sorted(
            (
                record.model_dump(mode="json", exclude_none=False)
                for record in self.records
            ),
            key=lambda record: record["concept"]["concept_id"],
        )
        return _canonical_digest({
            "jurisdiction": self.jurisdiction,
            "payload_set_digest": self.payload_set_digest,
            "population_id": self.population_id,
            "projection_id": self.projection_id,
            "records": records,
            "schema_fingerprint": self.schema_fingerprint,
            "source_id": self.source_id,
        })


Projector = Callable[
    [PayloadSet, ProjectionSchema],
    Sequence[CanonicalMedicineRecord],
]


def project_payload_set(
    payloads: PayloadSet,
    schema: ProjectionSchema,
    *,
    projection_id: str,
    population_id: str,
    projector: Projector,
    warnings: Sequence[str] = (),
) -> ProjectionOutcome:
    """Run a pure projector and bind its output to payload and schema lineage."""

    records = tuple(projector(payloads, schema))
    return ProjectionOutcome(
        source_id=payloads.source_id,
        jurisdiction=payloads.jurisdiction,
        projection_id=projection_id,
        population_id=population_id,
        payload_set_digest=payloads.lineage_digest,
        receipt_ids=payloads.receipt_ids,
        schema_fingerprint=schema.fingerprint,
        records=records,
        warnings=tuple(warnings),
    )


def canonical_record_payload(
    record: CanonicalMedicineRecord,
) -> dict[str, Any]:
    """Return a JSON-compatible representation used by parity comparisons."""

    return record.model_dump(mode="json", exclude_none=False)
