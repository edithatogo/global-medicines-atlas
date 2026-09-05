"""Deterministic, metadata-only RO-Crate research package envelopes.

The crate is a rebuildable Platinum projection: source payloads remain in
their governed Bronze locations and are represented here only by public
identifiers, distributions, and content digests.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Literal, cast

from pydantic import Field, model_validator

from .models import FrozenModel

_HASH = r"^[0-9a-f]{64}$"
_CROISSANT_PAYLOAD_KEYS = frozenset({
    "recordSet",
    "records",
    "data",
    "examples",
})


def _distribution_field(
    distribution: CrateDistribution | Mapping[str, object], field: str
) -> str:
    value = (
        distribution.get(field)
        if isinstance(distribution, Mapping)
        else getattr(distribution, field)
    )
    return str(value)


class CrateDistribution(FrozenModel):
    """A distribution reference; bytes are deliberately never embedded."""

    identifier: str = Field(min_length=1)
    name: str = Field(min_length=1)
    content_url: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    sha256: str = Field(pattern=_HASH)


class ResearchCrate(FrozenModel):
    """Small RO-Crate 1.1 JSON-LD envelope for an Atlas revision."""

    schema_id: Literal["global-medicines-atlas.ro-crate"]
    schema_version: Literal[1]
    ro_crate_version: Literal["1.1"]
    identifier: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    dataset_url: str = Field(min_length=1)
    distributions: tuple[CrateDistribution, ...] = Field(min_length=1)
    source_receipts_authoritative: Literal[True] = True
    payloads_embedded: Literal[False] = False

    @model_validator(mode="after")
    def unique_identifiers(self) -> ResearchCrate:
        ids = tuple(item.identifier for item in self.distributions)
        if len(ids) != len(set(ids)):
            raise ValueError("crate distribution identifiers must be unique")
        return self

    def jsonld(self) -> dict[str, object]:
        """Return a deterministic RO-Crate JSON-LD document."""

        graph: list[dict[str, object]] = [
            {
                "@id": "./",
                "@type": "Dataset",
                "name": self.name,
                "version": self.version,
                "url": self.dataset_url,
                "distribution": [
                    _distribution_field(item, "identifier")
                    for item in self.distributions
                ],
            }
        ]
        graph.extend(
            {
                "@id": _distribution_field(item, "identifier"),
                "@type": "https://schema.org/DataDownload",
                "name": _distribution_field(item, "name"),
                "contentUrl": _distribution_field(item, "content_url"),
                "encodingFormat": _distribution_field(item, "media_type"),
                "sha256": _distribution_field(item, "sha256"),
            }
            for item in self.distributions
        )
        return {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": graph,
        }

    def canonical_jsonld_bytes(self) -> bytes:
        return (
            json.dumps(
                self.jsonld(), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            + b"\n"
        )

    def jsonld_sha256(self) -> str:
        return hashlib.sha256(self.canonical_jsonld_bytes()).hexdigest()

    def croissant(self) -> dict[str, object]:
        """Return a deterministic metadata-only Croissant descriptor."""
        descriptor: dict[str, object] = {
            "@context": "https://mlcommons.org/croissant/1.0",
            "@type": "Dataset",
            "name": self.name,
            "version": self.version,
            "url": self.dataset_url,
            "cr:metadataOnly": True,
            "distribution": [
                {
                    "@id": item.identifier,
                    "name": item.name,
                    "contentUrl": item.content_url,
                    "encodingFormat": item.media_type,
                    "sha256": item.sha256,
                }
                for item in self.distributions
            ],
        }
        validate_metadata_only_croissant(descriptor)
        return descriptor

    def canonical_croissant_bytes(self) -> bytes:
        return (
            json.dumps(
                self.croissant(), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            + b"\n"
        )

    def croissant_sha256(self) -> str:
        return hashlib.sha256(self.canonical_croissant_bytes()).hexdigest()


def validate_metadata_only_croissant(descriptor: Mapping[str, object]) -> None:
    """Fail closed when a Croissant descriptor contains inline payload data.

    Croissant metadata may be published independently of the governed bytes.
    This check is intentionally structural and recursive: a payload-bearing
    nested object must not be able to bypass the top-level metadata-only flag.
    """

    if descriptor.get("cr:metadataOnly") is not True:
        raise ValueError(
            "Croissant descriptor must declare metadata-only output"
        )

    def walk(value: object) -> None:
        if isinstance(value, Mapping):
            mapping = cast("Mapping[str, object]", value)
            if _CROISSANT_PAYLOAD_KEYS.intersection(mapping):
                raise ValueError(
                    "Croissant descriptor must not embed payload data"
                )
            for child in mapping.values():
                walk(child)
        elif isinstance(value, (list, tuple)):
            for child in cast("tuple[object, ...] | list[object]", value):
                walk(child)

    walk(descriptor)


def build_research_crate(
    *,
    identifier: str,
    name: str,
    version: str,
    dataset_url: str,
    distributions: tuple[CrateDistribution, ...],
) -> ResearchCrate:
    """Build a metadata-only crate with stable ordering."""

    return ResearchCrate(
        schema_id="global-medicines-atlas.ro-crate",
        schema_version=1,
        ro_crate_version="1.1",
        identifier=identifier,
        name=name,
        version=version,
        dataset_url=dataset_url,
        distributions=tuple(
            sorted(
                distributions,
                key=lambda item: _distribution_field(item, "identifier"),
            )
        ),
    )
