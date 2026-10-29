"""Exact frozen workbook candidates, independent of CSV period/measure meaning."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .bronze_raw_evidence import RawEvidenceManifest
from .mbs_demographic_csv_cohort import (
    FROZEN,
    FROZEN_SHA256,
    STRUCTURE,
    STRUCTURE_SHA256,
)
from .mbs_demographic_silver import DemographicSource
from .receipts import AcquisitionEvent

STREAMING = "quality/qualifications/australian-mbs-workbook-streaming-receipt-20261017.json"
STREAMING_SHA256 = (
    "eb3d63082a2e2af9df18f8073b335cac84f406533342f3abf989327b6fe65dd0"
)
CANDIDATE_COUNT = 3
SOURCE_PATHS = tuple(
    f"raw/mbs/utilisation/demographics/mbs-demographics-2016-qtr{quarter}-{month}hr.xlsx"
    for quarter, month in ((1, "march"), (2, "june"), (3, "july"))
)


@dataclass(frozen=True)
class DemographicWorkbookCandidate:
    """Existing structural identity; row counts and physical shape need readback."""

    source: DemographicSource
    byte_count: int
    structural_receipt_path: str
    structural_receipt_sha256: str


def _bound(root: Path, path: str, digest: str) -> dict[str, Any]:
    payload = (root / path).read_bytes()
    if sha256(payload).hexdigest() != digest:
        raise ValueError("retained workbook metadata digest differs")
    return json.loads(payload)


def _documents(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for receipt in report["per_object_receipts"]:
        document = receipt["document"]
        path = document["raw_reference"]["path"]
        if path in result:
            raise ValueError("workbook structural receipt duplicates a path")
        result[path] = document
    return result


def load_workbook_candidates(
    root: Path,
) -> tuple[DemographicWorkbookCandidate, ...]:
    """Join exactly three frozen objects to latest structural evidence and B1/B2.

    The old Q1/Q2 expanded-size failures are superseded only by their exact
    successful streaming receipt. No row count, header, field meaning, date or
    equivalence is inferred from a CSV, filename or neighbouring workbook.
    """
    old = _documents(_bound(root, STRUCTURE, STRUCTURE_SHA256))
    streaming = _documents(_bound(root, STREAMING, STREAMING_SHA256))
    frozen = _bound(root, FROZEN, FROZEN_SHA256)
    members = {(row["dataset"], row["path"]) for row in frozen["members"]}
    candidates: list[DemographicWorkbookCandidate] = []
    for path in SOURCE_PATHS:
        original = old[path]
        document = streaming.get(path, original)
        reference = document["raw_reference"]
        if any(
            reference[key] != original["raw_reference"][key]
            for key in ("dataset", "revision", "path", "sha256", "byte_count")
        ):
            raise ValueError(
                "workbook streaming identity differs from original"
            )
        if (
            type(reference["byte_count"]) is not int
            or reference["byte_count"] <= 0
        ):
            raise ValueError("workbook byte count is invalid")
        if (
            (reference["dataset"], path) not in members
            or document["result"]["status"] != "structure_verified"
            or document["result"].get("anonymous_digest_verified") is not True
            or document["acquisition_id"] != original["acquisition_id"]
        ):
            raise ValueError("workbook frozen or structural evidence differs")
        family = "au-data-gov-mbs-demographics"
        acquisition = document["acquisition_id"]
        source = DemographicSource(
            acquisition=AcquisitionEvent.model_validate_json(
                (
                    root
                    / f"quality/bronze/imported-acquisitions/{family}/{acquisition}.json"
                ).read_bytes()
            ),
            raw_manifest=RawEvidenceManifest.model_validate_json(
                (
                    root
                    / f"quality/bronze/raw-evidence/{family}/{acquisition}/manifest.json"
                ).read_bytes()
            ),
            dataset=reference["dataset"],
            source_revision=reference["revision"],
            source_path=path,
            source_format="workbook",
        )
        retrieval = source.acquisition.retrieval
        if (
            source.source_sha256 != reference["sha256"]
            or retrieval is None
            or retrieval.http is None
            or retrieval.http.observed_byte_length != reference["byte_count"]
        ):
            raise ValueError("workbook B1/B2 digest or byte count differs")
        candidates.append(
            DemographicWorkbookCandidate(
                source,
                reference["byte_count"],
                STREAMING if path in streaming else STRUCTURE,
                STREAMING_SHA256 if path in streaming else STRUCTURE_SHA256,
            )
        )
    return tuple(candidates)
