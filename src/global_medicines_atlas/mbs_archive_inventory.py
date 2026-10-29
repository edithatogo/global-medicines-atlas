"""Frozen historical MBS archive identities, original lineage and prior holds."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from .bronze_raw_evidence import (
    RawEvidenceKind,
    RawEvidenceManifest,
    RawEvidenceState,
)
from .mbs_demographic_csv_cohort import (
    FROZEN,
    FROZEN_SHA256,
    STRUCTURE,
    STRUCTURE_SHA256,
)
from .receipts import AcquisitionEvent, AcquisitionStatus

DATASET = "edithatogo/australian-mbs-utilisation-archive"
REVISION = "dee9a5b0580dfe394474dc26b372559462e157e7"
EXPECTED_ARCHIVES = 6


@dataclass(frozen=True)
class BoundArchive:
    """A raw archive candidate; member typing and era semantics stay unqualified."""

    dataset: str
    revision: str
    source_path: str
    source_sha256: str
    source_bytes: int
    source_id: str
    acquisition_id: str
    b1_sha256: str
    b2_sha256: str
    prior_status: str
    prior_member_count: int | None
    prior_expanded_bytes: int | None
    prior_inventory_sha256: str | None


def _bound(root: Path, path: str, digest: str) -> dict[str, Any]:
    payload = (root / path).read_bytes()
    if hashlib.sha256(payload).hexdigest() != digest:
        raise ValueError("MBS archive retained metadata digest differs")
    return json.loads(payload)


def _candidate(
    root: Path, document: dict[str, Any], frozen: set[tuple[str, str]]
) -> BoundArchive:
    reference = document["raw_reference"]
    family = (
        "au-data-gov-mbs-group"
        if "/group/" in reference["path"]
        else "au-data-gov-mbs-demographics"
    )
    b1 = (
        root
        / f"quality/bronze/imported-acquisitions/{family}/{document['acquisition_id']}.json"
    ).read_bytes()
    b2 = (
        root
        / f"quality/bronze/raw-evidence/{family}/{document['acquisition_id']}/manifest.json"
    ).read_bytes()
    event = AcquisitionEvent.model_validate_json(b1)
    manifest = RawEvidenceManifest.model_validate_json(b2)
    if manifest.row_count != 1:
        raise ValueError("MBS archive requires one exact B2 reference")
    raw = manifest.rows[0]
    if (
        (DATASET, reference["path"]) not in frozen
        or reference["dataset"] != DATASET
        or reference["revision"] != REVISION
    ):
        raise ValueError("MBS archive frozen identity differs")
    if (
        event.source_id != family
        or event.acquisition_id != document["acquisition_id"]
        or event.payload_sha256 != reference["sha256"]
    ):
        raise ValueError("MBS archive original B1 binding differs")
    if (
        event.retrieval is None
        or event.retrieval.status is not AcquisitionStatus.SUCCEEDED
        or event.retrieval.http is None
    ):
        raise ValueError("MBS archive succeeded retrieval evidence required")
    if event.retrieval.http.observed_byte_length != reference["byte_count"]:
        raise ValueError("MBS archive original B1 byte count differs")
    if (
        raw.source_id != event.source_id
        or raw.acquisition_id != event.acquisition_id
        or raw.content_id != event.content_id
        or raw.kind is not RawEvidenceKind.PAYLOAD
        or raw.state is not RawEvidenceState.EXTERNAL_REFERENCE_ONLY
    ):
        raise ValueError("MBS archive original B2 binding differs")
    if (
        unquote(urlsplit(raw.external_reference or "").path)
        != f"/datasets/{DATASET}/resolve/{REVISION}/{reference['path']}"
    ):
        raise ValueError("MBS archive original B2 locator differs")
    checks = document["result"].get("checks", {})
    return BoundArchive(
        DATASET,
        REVISION,
        reference["path"],
        reference["sha256"],
        reference["byte_count"],
        family,
        event.acquisition_id,
        hashlib.sha256(b1).hexdigest(),
        hashlib.sha256(b2).hexdigest(),
        document["result"]["status"],
        checks.get("member_count"),
        checks.get("expanded_bytes"),
        checks.get("member_inventory_sha256"),
    )


def load_archives(root: Path) -> tuple[BoundArchive, ...]:
    """Retain all six members and prior outcomes; never promote a resource hold."""
    structure = _bound(root, STRUCTURE, STRUCTURE_SHA256)
    frozen = _bound(root, FROZEN, FROZEN_SHA256)
    membership = {(row["dataset"], row["path"]) for row in frozen["members"]}
    sources = tuple(
        _candidate(root, row["document"], membership)
        for row in structure["per_object_receipts"]
        if row["document"]["raw_reference"]["path"].endswith(".zip")
    )
    if (
        len(sources) != EXPECTED_ARCHIVES
        or len({source.source_path for source in sources}) != EXPECTED_ARCHIVES
    ):
        raise ValueError("MBS archive frozen cohort count differs")
    return sources
