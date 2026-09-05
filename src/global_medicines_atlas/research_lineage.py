"""Deterministic, metadata-only lineage receipts for research exports."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field

from .models import FrozenModel


class LineageReceipt(FrozenModel):
    schema_id: Literal["global-medicines-atlas.lineage"] = (
        "global-medicines-atlas.lineage"
    )
    schema_version: Literal[1] = 1
    source_revision: str = Field(min_length=1)
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    export_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    payloads_embedded: Literal[False] = False

    def canonical_bytes(self) -> bytes:
        return (
            json.dumps(
                self.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()
