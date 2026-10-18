"""Add six qualified PBS utilisation lineages to the frozen M-112 gate report."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.bronze_admission import (
    BronzeAdmissionRecord,
    BronzeAdmissionState,
)
from global_medicines_atlas.bronze_raw_evidence import RawEvidenceManifest
from global_medicines_atlas.receipts import AcquisitionEvent, RightsState

ROOT = Path(__file__).resolve().parents[1]
QUAL = Path("quality/qualifications")
BASE = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261019-pbs-projected-b1-b2-lineage.json"
)
LINEAGE = QUAL / "australian-pbs-utilisation-landed-lineage-20261019.json"
RECEIPT_READBACK = (
    QUAL / "australian-pbs-utilisation-receipt-sidecar-readback-20261019.json"
)
OUTPUT = (
    QUAL
    / "australian-m112-per-object-gate-reconciliation-20261019-pbs-utilisation-lineage.json"
)
DATASET = "edithatogo/australian-pbs-utilisation-archive"
REVISION = "9f1d53cd50eea251b326da42a96f3ac72ebce97a"
EXPECTED_ADDITIONS = 6
EXPECTED_DENOMINATOR = 1759
EXPECTED_PRIOR_COMPLETE_RAW = 1725
EXPECTED_COMPLETE_PROJECTIONS = 10
EXPECTED_PRIOR_COMPLETE_TOTAL = 1735
EXPECTED_COMPLETE_RAW = 1731
EXPECTED_COMPLETE_TOTAL = 1741
EXPECTED_INCOMPLETE_RAW = 5
EXPECTED_INCOMPLETE_PROJECTIONS = 13
EXPECTED_SIDECAR_METADATA_BYTES = 4226


def _read(path: Path) -> dict[str, Any]:
    value: object = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return cast("dict[str, Any]", value)


def _digest(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def require_landed_admission(admission: BronzeAdmissionRecord) -> None:
    if admission.state is not BronzeAdmissionState.LANDED:
        raise ValueError(
            "PBS utilisation B1/B2 lineage admission is not landed"
        )


def _receipt_sidecar_metadata_bytes() -> int:
    receipt_readback = _read(RECEIPT_READBACK)
    if not all((
        receipt_readback["dataset"] == DATASET,
        receipt_readback["revision"] == REVISION,
        receipt_readback["metadata_sidecar_bytes_read"]
        == EXPECTED_SIDECAR_METADATA_BYTES,
        receipt_readback["source_payload_bytes_read"] is False,
        receipt_readback["source_payload_values_read"] is False,
    )):
        raise ValueError("PBS utilisation receipt sidecar readback changed")
    return cast("int", receipt_readback["metadata_sidecar_bytes_read"])


def build_report() -> dict[str, Any]:
    """Verify generated B1/B2 artifacts and preserve independent M-112 gates."""
    base = _read(BASE)
    lineage = _read(LINEAGE)
    totals = base["updated_gate_totals"]
    if not all((
        base["scope"]["approved_denominator"] == EXPECTED_DENOMINATOR,
        base["scope"]["denominator_changed"] is False,
        totals["complete_raw_b1_b2_lineage"] == EXPECTED_PRIOR_COMPLETE_RAW,
        totals["complete_projection_lineage"] == EXPECTED_COMPLETE_PROJECTIONS,
        totals["complete_b1_b2_lineage_objects"]
        == EXPECTED_PRIOR_COMPLETE_TOTAL,
        totals["v4_admissions"] == 0,
        totals["consumer_canaries"] == 0,
        lineage["scope"]["dataset"] == DATASET,
        lineage["scope"]["revision"] == REVISION,
        lineage["scope"]["lineages_completed"] == EXPECTED_ADDITIONS,
        lineage["scope"]["rights_concluded"] is False,
        lineage["boundaries"]["source_payload_bytes_read"] is False,
        lineage["boundaries"]["rights_or_licensing_conclusion_added"] is False,
        len(lineage["objects"]) == EXPECTED_ADDITIONS,
        _receipt_sidecar_metadata_bytes() == EXPECTED_SIDECAR_METADATA_BYTES,
    )):
        raise ValueError(
            "PBS utilisation lineage scope or M-112 baseline changed"
        )

    objects = {
        (row["dataset"], row["revision"], row["path"]): row
        for row in base["objects"]
    }
    rows = {
        (row["dataset"], row["revision"], row["path"]): row
        for row in lineage["objects"]
    }
    if len(rows) != EXPECTED_ADDITIONS:
        raise ValueError("PBS utilisation lineage keys are not unique")
    for key, item in rows.items():
        target = objects.get(key)
        if target is None or key[0] != DATASET or key[1] != REVISION:
            raise ValueError(
                "PBS utilisation lineage is outside frozen inventory"
            )
        if not all((
            target["candidate_class"] == "raw_source_payload",
            target["approved_denominator_member"] is True,
            target["disposition"] == "deferred_not_admitted",
            target["b1_b2_lineage"]["complete"] is False,
            target["v4_admission"] is False,
            target["consumer_canary"] is False,
            target["identity"]["sha256"] == item["content_sha256"],
            target["identity"]["byte_count"] == item["byte_count"],
            target["rights"]["state"]
            == "source-specific rights review absent; per-object sidecar has no rights_state",
            item["rights_state"] == "unknown",
            item["reviewer_status"] == "unreviewed",
            item["v4_admission"] is False,
            item["consumer_canary"] is False,
        )):
            raise ValueError("PBS utilisation identity or deferral changed")

        event_path = Path(item["acquisition_event_path"])
        b2_path = Path(item["b2_manifest_path"])
        admission_path = Path(item["landed_admission_path"])
        if not all((
            _digest(event_path)
            == lineage["output_bindings"][event_path.as_posix()],
            _digest(b2_path)
            == item["b2_manifest_sha256"]
            == lineage["output_bindings"][b2_path.as_posix()],
            _digest(admission_path)
            == item["landed_admission_sha256"]
            == lineage["output_bindings"][admission_path.as_posix()],
        )):
            raise ValueError(
                "PBS utilisation generated artifact digest differs"
            )
        event = AcquisitionEvent.model_validate_json(
            (ROOT / event_path).read_bytes()
        )
        b2 = RawEvidenceManifest.model_validate_json(
            (ROOT / b2_path).read_bytes()
        )
        admission = BronzeAdmissionRecord.model_validate_json(
            (ROOT / admission_path).read_bytes()
        )
        require_landed_admission(admission)
        if not all((
            event.acquisition_id == item["acquisition_id"],
            event.content_id == item["content_sha256"],
            event.rights_state is RightsState.UNKNOWN,
            b2.row_count == 1,
            b2.rows[0].acquisition_id == event.acquisition_id,
            b2.rows[0].external_reference == item["pinned_b2_reference"],
            b2.rows[0].payload_sha256 is None,
            admission.acquisition_id == event.acquisition_id,
            admission.content_id == event.content_id,
            admission.reviewer_status == "unreviewed",
        )):
            raise ValueError("PBS utilisation B1/B2 records are not joined")

        target["b1_b2_lineage"] = {
            "complete": True,
            "state": "historical B1 receipt metadata joined to local B1 acquisition, pinned external-reference B2, and unreviewed landed admission; rights unresolved",
            "evidence": {
                "path": LINEAGE.as_posix(),
                "sha256": _digest(LINEAGE),
                "object_path": item["path"],
            },
        }

    result = copy.deepcopy(base)
    result["purpose"] = (
        "Preserve the approved 1,759-object inventory while binding the six "
        "PBS utilisation source objects to their exact receipt sidecars, B1 "
        "acquisition records, B2 references, and unreviewed landed decisions."
    )
    result["observed_at"] = lineage["recorded_at"]
    result["boundaries"].update({
        "projection_bytes_streamed_this_run": 0,
        "source_payload_bytes_persisted_this_run": False,
        "source_payload_bytes_read_this_run": False,
        "source_payload_bytes_streamed_this_run": 0,
        "source_payload_values_inspected_this_run": False,
        "receipt_sidecar_metadata_bytes_read_this_run": (
            _receipt_sidecar_metadata_bytes()
        ),
    })
    result_objects = {
        (row["dataset"], row["revision"], row["path"]): row
        for row in result["objects"]
    }
    for key in rows:
        result_objects[key]["b1_b2_lineage"] = objects[key]["b1_b2_lineage"]

    updated = result["updated_gate_totals"]
    updated["complete_raw_b1_b2_lineage"] += EXPECTED_ADDITIONS
    updated["complete_raw_b1_b2_lineage_paths"] += EXPECTED_ADDITIONS
    updated["complete_b1_b2_lineage_objects"] += EXPECTED_ADDITIONS
    updated["preserved_deferrals"] = EXPECTED_DENOMINATOR
    result["lineage_counts_after_expansion"]["complete_raw_lineages"] += (
        EXPECTED_ADDITIONS
    )
    result["lineage_counts_after_expansion"]["incomplete_raw_lineages"] -= (
        EXPECTED_ADDITIONS
    )
    result["lineage_counts_after_expansion"]["complete_lineage_objects"] += (
        EXPECTED_ADDITIONS
    )
    result["pbs_utilisation_lineage_increment"] = {
        "qualification_path": LINEAGE.as_posix(),
        "qualification_sha256": _digest(LINEAGE),
        "dataset": DATASET,
        "revision": REVISION,
        "new_complete_raw_lineages": EXPECTED_ADDITIONS,
        "complete_raw_lineages_after_expansion": updated[
            "complete_raw_b1_b2_lineage"
        ],
        "rights_concluded": False,
        "source_payload_bytes_read": False,
        "v4_admissions": 0,
        "consumer_canaries": 0,
    }
    result["evidence_inputs"].append({
        "path": LINEAGE.as_posix(),
        "sha256": _digest(LINEAGE),
    })
    if not all((
        updated["complete_raw_b1_b2_lineage"] == EXPECTED_COMPLETE_RAW,
        updated["complete_projection_lineage"] == EXPECTED_COMPLETE_PROJECTIONS,
        updated["complete_b1_b2_lineage_objects"] == EXPECTED_COMPLETE_TOTAL,
        result["lineage_counts_after_expansion"]["incomplete_raw_lineages"]
        == EXPECTED_INCOMPLETE_RAW,
        result["lineage_counts_after_expansion"][
            "incomplete_projection_lineages"
        ]
        == EXPECTED_INCOMPLETE_PROJECTIONS,
        updated["v4_admissions"] == 0,
        updated["consumer_canaries"] == 0,
    )):
        raise ValueError("cumulative M-112 lineage totals changed unexpectedly")
    return result


def main() -> None:
    result = build_report()
    destination = ROOT / OUTPUT
    body = json.dumps(result, ensure_ascii=False, indent=2).encode() + b"\n"
    if destination.exists() and destination.read_bytes() != body:
        raise ValueError(f"append-only reconciliation differs: {OUTPUT}")
    if not destination.exists():
        destination.write_bytes(body)
    print(
        json.dumps(
            {
                "output": OUTPUT.as_posix(),
                "complete_raw": result["updated_gate_totals"][
                    "complete_raw_b1_b2_lineage"
                ],
                "complete_total": result["updated_gate_totals"][
                    "complete_b1_b2_lineage_objects"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
