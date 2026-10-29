"""Receipt-bound qualification candidates within the frozen MBS CSV inventory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .bronze_raw_evidence import RawEvidenceManifest
from .mbs_demographic_silver import CSV_HEADERS, DemographicSource
from .receipts import AcquisitionEvent

STRUCTURE = "quality/qualifications/australian-mbs-utilisation-payload-validation-receipt-20261004.json"
STRUCTURE_SHA256 = (
    "f622434530f3d184a5aea6684e67dc7f874424c2ada634b2f154490a39c6f457"
)
HEADERS = "quality/qualifications/australian-mbs-utilisation-header-inventory-20261006.json"
HEADERS_SHA256 = (
    "7760909d98d4d9723c0f02de72269c9e88296a80e641e3af5eec5766737b5fbf"
)
FROZEN = "quality/qualifications/australian-m112-frozen-object-inventory-20261018.json"
FROZEN_SHA256 = (
    "eaa1d84325c7672100398acf8116f0312369ca336d42ed21eee110452d3fefa4"
)
CANDIDATE_COUNT = 3


@dataclass(frozen=True)
class DemographicCsvCandidate:
    """An exact prior structural observation, with independent meaning gates."""

    source: DemographicSource
    byte_count: int
    expected_rows: int
    prior_structural_receipt_sha256: str
    prior_header_receipt_sha256: str


def _bound(root: Path, path: str, digest: str) -> dict[str, Any]:
    payload = (root / path).read_bytes()
    if sha256(payload).hexdigest() != digest:
        raise ValueError("retained metadata digest differs")
    return json.loads(payload)


def load_csv_candidates(root: Path) -> tuple[DemographicCsvCandidate, ...]:  # ruff: ignore[too-many-locals] -- exact receipt joins retain each independent identity
    """Join three exact CSVs to frozen membership and existing B1/B2 records.

    Only retained metadata is read. Prior structural evidence neither qualifies
    source meaning nor changes rights, admission, publication or consumer gates.
    """
    structure = _bound(root, STRUCTURE, STRUCTURE_SHA256)
    headers = _bound(root, HEADERS, HEADERS_SHA256)
    frozen = _bound(root, FROZEN, FROZEN_SHA256)
    membership = {(row["dataset"], row["path"]) for row in frozen["members"]}
    header_rows = {row["path"]: row for row in headers["records"]}
    expected_header = sha256(
        json.dumps(CSV_HEADERS, separators=(",", ":")).encode()
    ).hexdigest()
    candidates: list[DemographicCsvCandidate] = []
    seen: set[str] = set()
    for receipt in structure["per_object_receipts"]:
        document = receipt["document"]
        reference = document["raw_reference"]
        path = reference["path"]
        if not path.startswith(
            "raw/mbs/utilisation/demographics/"
        ) or not path.endswith(".csv"):
            continue
        if path in seen or (reference["dataset"], path) not in membership:
            raise ValueError(
                "demographic CSV membership is duplicated or unfrozen"
            )
        seen.add(path)
        header = header_rows.get(path)
        checks = document["result"].get("checks", {})
        if (
            document["result"]["status"] != "structure_verified"  # ruff: ignore[too-many-boolean-expressions] -- all exact identity fields must agree
            or document["result"].get("anonymous_digest_verified") is not True
            or checks.get("column_count") != len(CSV_HEADERS)
            or type(checks.get("row_count")) is not int
            or checks["row_count"] <= 0
            or type(reference["byte_count"]) is not int
            or reference["byte_count"] <= 0
            or header is None
            or header["header_sha256"] != expected_header
            or header["source_sha256"] != reference["sha256"]
            or header["source_revision"] != reference["revision"]
            or header["acquisition_id"] != document["acquisition_id"]
            or header["byte_count"] != reference["byte_count"]
            or header["anonymous_digest_verified"] is not True
        ):
            raise ValueError(
                "demographic CSV structural/header evidence differs"
            )
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
            source_format="csv",
        )
        if source.source_sha256 != reference["sha256"]:
            raise ValueError("demographic CSV B1/B2 digest differs")
        candidates.append(
            DemographicCsvCandidate(
                source,
                reference["byte_count"],
                checks["row_count"],
                STRUCTURE_SHA256,
                HEADERS_SHA256,
            )
        )
    if len(candidates) != CANDIDATE_COUNT:
        raise ValueError("demographic CSV candidate denominator differs")
    return tuple(
        sorted(candidates, key=lambda candidate: candidate.source.source_path)
    )
