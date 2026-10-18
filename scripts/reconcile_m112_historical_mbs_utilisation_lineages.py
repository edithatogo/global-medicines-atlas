"""Extend the frozen M-112 overlay with audited MBS utilisation B1/B2 links."""

from __future__ import annotations

import copy
import hashlib
import json
from operator import itemgetter
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionRecord,
    BronzeAdmissionState,
)
from global_medicines_atlas.bronze_raw_evidence import RawEvidenceManifest
from global_medicines_atlas.receipts import AcquisitionEvent, SourceReceipt

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
BASE_OVERLAY = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261018-retained-joins.json"
)
LINEAGE_QUALIFICATION = (
    QUAL / "australian-mbs-utilisation-landed-lineage-20261019.json"
)
OUTPUT = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261019-mbs-util-lineages.json"
)
EXPECTED_DENOMINATOR = 1759
EXPECTED_RAW_PATHS = 1736
EXPECTED_PROJECTIONS = 23
EXPECTED_PRIOR_COMPLETE = 6
EXPECTED_NEW_COMPLETE = 14
EXPECTED_COMPLETE = 20


def _read(path: Path) -> dict[str, Any]:
    value: object = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return cast("dict[str, Any]", value)


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def build_report() -> dict[str, Any]:  # ruff: ignore[too-many-locals,too-many-statements] -- keep the overlay's 14 exact path validations together
    """Verify all 14 newly recorded events, then update only their lineage rows."""
    prior = _read(BASE_OVERLAY)
    qualification = _read(LINEAGE_QUALIFICATION)
    rows = copy.deepcopy(prior["objects"])
    path_key = itemgetter("dataset", "revision", "path")
    by_key = {path_key(row): row for row in rows}
    if (
        len(rows) != EXPECTED_DENOMINATOR
        or len(by_key) != EXPECTED_DENOMINATOR
        or prior["scope"]["approved_raw_paths"] != EXPECTED_RAW_PATHS
        or prior["scope"]["approved_projection_paths"] != EXPECTED_PROJECTIONS
        or prior["updated_gate_totals"]["complete_raw_b1_b2_lineage"]
        != EXPECTED_PRIOR_COMPLETE
    ):
        raise ValueError(
            "the frozen M-112 baseline or prior lineage count changed"
        )
    scope = qualification["scope"]
    if any((
        scope["dataset"] != "edithatogo/australian-mbs-utilisation-archive",
        scope["revision"] != "dee9a5b0580dfe394474dc26b372559462e157e7",
        scope["lineages_completed"] != EXPECTED_NEW_COMPLETE,
    )):
        raise ValueError("MBS utilisation lineage qualification scope changed")
    boundaries = qualification["boundaries"]
    if any(
        boundaries[key] is not False
        for key in (
            "new_sources_added",
            "frozen_denominator_changed",
            "rights_or_licensing_conclusion_added",
            "v4_admission_performed",
        )
    ):
        raise ValueError("MBS utilisation lineage qualification scope changed")

    changed_keys: set[tuple[str, str, str]] = set()
    outputs: list[dict[str, Any]] = []
    for item in qualification["objects"]:
        key = (item["dataset"], item["revision"], item["path"])
        row = by_key.get(key)
        if row is None or key in changed_keys:
            raise ValueError("MBS utilisation path is absent or duplicated")
        if (
            row["candidate_class"] != "raw_source_payload"
            or row["identity"]["sha256"] != item["content_sha256"]
            or row["identity"]["byte_count"] != item["byte_count"]
            or row["b1_b2_lineage"]["complete"] is not False
        ):
            raise ValueError(
                f"MBS utilisation inventory identity differs: {item['path']}"
            )

        receipt_path = Path(item["source_receipt_path"])
        event_path = Path(item["acquisition_event_path"])
        b2_path = Path(item["b2_manifest_path"])
        admission_path = Path(item["landed_admission_path"])
        receipt = SourceReceipt.model_validate_json(
            (ROOT / receipt_path).read_bytes()
        )
        event = AcquisitionEvent.model_validate_json(
            (ROOT / event_path).read_bytes()
        )
        b2 = RawEvidenceManifest.model_validate_json(
            (ROOT / b2_path).read_bytes()
        )
        decision = BronzeAdmissionRecord.model_validate_json(
            (ROOT / admission_path).read_bytes()
        )
        b2_row = b2.rows[0]
        temporal = receipt.temporal
        if temporal is None:
            raise ValueError(
                "historical source receipt lacks temporal identity"
            )
        if any((
            temporal.acquisition_id != item["acquisition_id"],
            temporal.content_id != item["content_sha256"],
            receipt.payload.byte_count != item["byte_count"],
            event.acquisition_id != item["acquisition_id"],
            event.content_id != item["content_sha256"],
            b2.row_count != 1,
            b2_row.acquisition_id != item["acquisition_id"],
            b2_row.content_id != item["content_sha256"],
            b2_row.external_reference is None,
            b2_row.state.value != "external_reference_only",
            decision.acquisition_id != item["acquisition_id"],
            decision.content_id != item["content_sha256"],
            decision.state is not BronzeAdmissionState.LANDED,
            decision.reviewer_status != "unreviewed",
            item["v4_admission"] is not False,
            item["consumer_canary"] is not False,
        )):
            raise ValueError(
                f"MBS utilisation B1/B2 roles differ: {item['path']}"
            )

        row["b1_b2_lineage"] = {
            "complete": True,
            "state": (
                "The exact frozen path and revision join to a historical source "
                "receipt, acquisition event, external-reference-only B2 manifest, "
                "and a current landed admission decision marked unreviewed. The "
                "landed event binds the prior anonymous digest and byte-count "
                "readback for this immutable archive object. It does not claim "
                "locally retained payload bytes, processing acceptance, changed "
                "rights, v4 admission, or consumer validation."
            ),
            "evidence": {
                "qualification_path": LINEAGE_QUALIFICATION.as_posix(),
                "qualification_sha256": _sha(LINEAGE_QUALIFICATION),
                "source_receipt_path": receipt_path.as_posix(),
                "acquisition_event_path": event_path.as_posix(),
                "b2_manifest_path": b2_path.as_posix(),
                "b2_manifest_sha256": item["b2_manifest_sha256"],
                "landed_admission_path": admission_path.as_posix(),
                "landed_admission_sha256": item["landed_admission_sha256"],
                "anonymous_digest_evidence": item["anonymous_digest_evidence"],
            },
            "acquisition_id": item["acquisition_id"],
            "source_revision": item["revision"],
            "content_sha256": item["content_sha256"],
            "byte_count": item["byte_count"],
            "admission_state": "landed",
            "reviewer_status": "unreviewed",
        }
        changed_keys.add(key)
        outputs.append({
            "dataset": item["dataset"],
            "revision": item["revision"],
            "path": item["path"],
            "acquisition_id": item["acquisition_id"],
            "content_sha256": item["content_sha256"],
            "byte_count": item["byte_count"],
            "landed_admission_path": admission_path.as_posix(),
            "reviewer_status": "unreviewed",
        })

    if len(changed_keys) != EXPECTED_NEW_COMPLETE:
        raise ValueError(
            "expected 14 distinct MBS utilisation lineage additions"
        )
    complete = sum(
        row["b1_b2_lineage"]["complete"]
        for row in rows
        if row["candidate_class"] == "raw_source_payload"
    )
    if complete != EXPECTED_COMPLETE:
        raise ValueError("inventory-wide complete B1/B2 lineage count changed")

    report = copy.deepcopy(prior)
    report["observed_at"] = "2026-10-19"
    report["purpose"] = (
        "Preserve the frozen object inventory while adding current landed, "
        "unreviewed B1/B2 lineage events for 14 already-inventory MBS objects."
    )
    report["objects"] = rows
    report["current_b1_b2_lineage_expansion"] = {
        "prior_complete_lineages": EXPECTED_PRIOR_COMPLETE,
        "new_complete_lineages": EXPECTED_NEW_COMPLETE,
        "complete_lineages_after_expansion": complete,
        "objects": sorted(outputs, key=itemgetter("path")),
        "input_bindings": {
            BASE_OVERLAY.as_posix(): _sha(BASE_OVERLAY),
            LINEAGE_QUALIFICATION.as_posix(): _sha(LINEAGE_QUALIFICATION),
        },
        "boundaries": qualification["boundaries"],
    }
    report["updated_gate_totals"]["complete_raw_b1_b2_lineage"] = complete
    report["updated_gate_totals"]["complete_raw_b1_b2_lineage_paths"] = complete
    if (
        report["updated_gate_totals"]["approved_denominator"]
        != EXPECTED_DENOMINATOR
        or report["updated_gate_totals"]["v4_admissions"] != 0
        or report["updated_gate_totals"]["consumer_canaries"] != 0
        or report["updated_gate_totals"]["preserved_deferrals"]
        != EXPECTED_DENOMINATOR
    ):
        raise ValueError("a separate M-112 gate or denominator changed")
    return report


def main() -> None:
    body = json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n"
    (ROOT / OUTPUT).write_text(body, encoding="utf-8")
    print(OUTPUT.as_posix())


if __name__ == "__main__":
    main()
