"""Deterministic, metadata-only RO-Crate research package envelopes.

The crate is a rebuildable Platinum projection: source payloads remain in
their governed Bronze locations and are represented here only by public
identifiers, distributions, and content digests.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field, model_validator

from .models import FrozenModel

_HASH = r"^[0-9a-f]{64}$"


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
                "distribution": [item.identifier for item in self.distributions],
            }
        ]
        graph.extend(
            {
                "@id": item.identifier,
                "@type": "https://schema.org/DataDownload",
                "name": item.name,
                "contentUrl": item.content_url,
                "encodingFormat": item.media_type,
                "sha256": item.sha256,
            }
            for item in self.distributions
        )
        return {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": graph,
        }

    def canonical_jsonld_bytes(self) -> bytes:
        return (
            json.dumps(self.jsonld(), sort_keys=True, separators=(",", ":"))
            .encode("utf-8")
            + b"\n"
        )

    def jsonld_sha256(self) -> str:
        return hashlib.sha256(self.canonical_jsonld_bytes()).hexdigest()

    def croissant(self) -> dict[str, object]:
        """Return a deterministic, metadata-only Croissant descriptor.

        The descriptor references distributions by URL and digest only.  It
        intentionally has no ``recordSet`` or inline data so generating this
        Platinum projection can never embed governed source payloads.
        """

        return {
            "@context": {
                "@vocab": "https://schema.org/",
                "cr": "http://mlcommons.org/croissant/",
            },
            "@type": "Dataset",
            "name": self.name,
            "version": self.version,
            "identifier": self.identifier,
            "url": self.dataset_url,
            "cr:metadataOnly": True,
            "distribution": [
                {
                    "@type": "DataDownload",
                    "name": item.name,
                    "contentUrl": item.content_url,
                    "encodingFormat": item.media_type,
                    "sha256": item.sha256,
                }
                for item in self.distributions
            ],
        }

    def canonical_croissant_bytes(self) -> bytes:
        """Serialize the Croissant descriptor with stable key ordering."""

        return (
            json.dumps(self.croissant(), sort_keys=True, separators=(",", ":"))
            .encode("utf-8")
            + b"\n"
        )

    def croissant_sha256(self) -> str:
        """Return the content digest of the canonical Croissant descriptor."""

        return hashlib.sha256(self.canonical_croissant_bytes()).hexdigest()


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
        distributions=tuple(sorted(distributions, key=lambda item: item.identifier)),
    )
