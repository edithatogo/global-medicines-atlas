"""Exact frozen BSD/RVG identity and original five-role lineage bindings.

This metadata contract does not qualify native layout, interpretation, rights
for derivatives, v4 admission, consumer delivery or public release.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATASET = "edithatogo/australian-mbs-source-archive"
REVISION = "42d73b6facac016f14a335d36d83f1a3b630add8"
PREFIX = "quality/qualifications/"
INPUTS = {
    "lineage": (
        "australian-m112-per-object-gate-reconciliation-20261019-july-mbs-source-lineage-reviewed.json",
        "cf62413bd6edecedd1cb7178393526921f3a35125789e0dbfdbdb1a2853fb243",
    ),
    "metadata": (
        "australian-m112-raw-b2-metadata-reconciliation-20261018.json",
        "026fa22ceae824ba5570b515057402b2e303b488bed63b1b6b6437f8fce05853",
    ),
    "frozen": (
        "australian-m112-frozen-object-inventory-20261018.json",
        "eaa1d84325c7672100398acf8116f0312369ca336d42ed21eee110452d3fefa4",
    ),
    "identity": (
        "australian-mbs-six-raw-object-rights-attestation-20261020.json",
        "79f3cd76786fbb13ef5607085ee97a69a21bb361b52025f886256093dd5e4f3d",
    ),
}
EXPECTED_OBJECTS = 3
EXPECTED_METADATA_ROLES = 5


@dataclass(frozen=True)
class MetadataPin:
    """One retained metadata file, separate from source payload identity."""

    role: str
    path: str
    sha256: str
    byte_count: int


@dataclass(frozen=True)
class BoundSidecar:
    """Frozen raw candidate; no typed or interpreted output is implied."""

    dataset: str
    revision: str
    source_path: str
    sha256: str
    byte_count: int
    format: str
    acquisition_id: str
    metadata: tuple[MetadataPin, ...]


def _bound(root: Path, key: str) -> dict[str, Any]:
    name, digest = INPUTS[key]
    data = (root / PREFIX / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("MBS sidecar retained metadata digest differs")
    return json.loads(data)


def load_sidecars(root: Path) -> tuple[BoundSidecar, ...]:
    """Require frozen path membership, exact bytes and all original B1/B2 roles."""
    reports = {key: _bound(root, key) for key in INPUTS}
    frozen = {
        (row["dataset"], row["path"]) for row in reports["frozen"]["members"]
    }
    lineage = {
        row["path"]: row
        for row in reports["lineage"]["objects"]
        if row["dataset"] == DATASET
    }
    readbacks = {
        row["path"]: row
        for row in reports["metadata"]["readbacks"]
        if row["dataset"] == DATASET and row["revision"] == REVISION
    }
    candidates = [
        row
        for row in reports["identity"]["authorized_objects"]
        if row["path"].startswith(("raw/mbs/bsd/", "raw/mbs/rvg/"))
    ]
    if len(candidates) != EXPECTED_OBJECTS:
        raise ValueError("MBS sidecar exact candidate count differs")
    outputs: list[BoundSidecar] = []
    for candidate in candidates:
        path = candidate["path"]
        row = lineage[path]
        identity, joined = row["identity"], row["b1_b2_lineage"]
        if (
            (DATASET, path) not in frozen
            or not joined["complete"]
            or identity["sha256"] != candidate["sha256"]
            or identity["byte_count"] != candidate["byte_count"]
        ):
            raise ValueError("MBS sidecar frozen identity or lineage differs")
        acquisition = joined["acquisition_id"]
        paths = {
            "acquisition": f"bronze/acquisitions/au-mbs/{acquisition}.json",
            "source_receipt": f"bronze/receipts/au-mbs/{acquisition}.json",
            "b2_reference": f"bronze/raw-evidence/au-mbs/{acquisition}/manifest.json",
            "path_receipt": "bronze/"
            + path.removeprefix("raw/")
            + ".receipt.json",
        }
        admissions = [
            name
            for name in readbacks
            if name.startswith(f"bronze/admissions/au-mbs/{acquisition}/")
        ]
        if len(admissions) != 1:
            raise ValueError("MBS sidecar landed admission count differs")
        paths["landed_admission"] = admissions[0]
        pins: list[MetadataPin] = []
        for role, name in paths.items():
            metadata = readbacks[name]
            if (
                not joined["receipt_roles"][role]
                or metadata["pinned_digest_match"] is not True
                or metadata["expected_identity_match"] is not True
                or metadata["status_read_passed"] is not True
            ):
                raise ValueError("MBS sidecar original metadata role differs")
            pins.append(
                MetadataPin(
                    role,
                    name,
                    metadata["observed_sha256"],
                    metadata["observed_bytes"],
                )
            )
        if len(pins) != EXPECTED_METADATA_ROLES:
            raise ValueError("MBS sidecar metadata role count differs")
        outputs.append(
            BoundSidecar(
                DATASET,
                REVISION,
                path,
                candidate["sha256"],
                candidate["byte_count"],
                {".csv": "csv", ".xml": "xml", ".txt": "text"}[
                    Path(path).suffix.lower()
                ],
                acquisition,
                tuple(pins),
            )
        )
    return tuple(outputs)
