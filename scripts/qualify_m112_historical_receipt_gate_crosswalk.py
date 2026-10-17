"""Bind historical M-112 SourceReceipt projections to exact gate rows.

This metadata-only crosswalk records the receipt projections merged in PR
#1102. Historical projections do not close live receipt, storage, B1/B2,
admission, canary, or federation acceptance gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from operator import itemgetter
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
GATE_REPORT = Path(
    "quality/qualifications/"
    "australian-m112-per-object-gate-reconciliation-20261005.json"
)
HISTORICAL_REPORT = Path(
    "quality/qualifications/"
    "australian-m112-historical-source-receipts-20261017.json"
)
ACQUISITION_IMPORT = Path(
    "quality/qualifications/"
    "australian-mbs-utilisation-acquisition-import-20261004.json"
)
OUTPUT_PATH = Path(
    "quality/qualifications/"
    "australian-m112-historical-receipt-gate-crosswalk-20261017.json"
)
EXPECTED_DENOMINATOR = 1759
EXPECTED_HISTORICAL_RECEIPTS = 14
EXPECTED_DATASET = "edithatogo/australian-mbs-utilisation-archive"


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    content = (ROOT / path).read_bytes()
    value = json.loads(content)
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return cast("dict[str, Any]", value), content


def crosswalk_receipt(
    *,
    output: dict[str, Any],
    receipt_path: str,
    receipt_bytes: bytes,
    receipt: dict[str, Any],
    acquisition: dict[str, Any],
    gate_row: dict[str, Any],
) -> dict[str, Any]:
    """Validate one historical receipt against its exact B2 and gate identity."""

    b2 = acquisition.get("b2_raw_reference")
    temporal = receipt.get("temporal")
    payload = receipt.get("payload")
    source = receipt.get("source")
    if not all(
        isinstance(value, dict) for value in (b2, temporal, payload, source)
    ):
        raise ValueError(
            "historical receipt lacks source, temporal, payload, or B2 metadata"
        )
    b2 = cast("dict[str, Any]", b2)
    temporal = cast("dict[str, Any]", temporal)
    payload = cast("dict[str, Any]", payload)
    source = cast("dict[str, Any]", source)

    acquisition_id = output.get("acquisition_id")
    identity = gate_row.get("identity")
    if not isinstance(identity, dict):
        raise TypeError("per-object gate row has no identity")
    identity = cast("dict[str, Any]", identity)
    source_id = output.get("source_id")
    if any((
        gate_row.get("dataset") != EXPECTED_DATASET,
        b2.get("dataset") != EXPECTED_DATASET,
        gate_row.get("path") != b2.get("path"),
        gate_row.get("revision") != b2.get("revision"),
        identity.get("sha256") != b2.get("sha256"),
        identity.get("byte_count") != b2.get("byte_count"),
        payload.get("sha256") != b2.get("sha256"),
        payload.get("byte_count") != b2.get("byte_count"),
        temporal.get("content_id") != b2.get("sha256"),
        temporal.get("acquisition_id") != acquisition_id,
        acquisition.get("acquisition_id") != acquisition_id,
        source.get("source_id") != source_id,
        acquisition.get("path") != gate_row.get("path"),
        receipt.get("evidence_class") != "historical",
        gate_row.get("approved_denominator_member") is not True,
        gate_row.get("b1_b2_lineage", {}).get("complete") is not False,
        gate_row.get("v4_admission") is not False,
        gate_row.get("consumer_canary") is not False,
    )):
        raise ValueError(
            "historical receipt identity does not match the per-object gate row"
        )

    return {
        "dataset": EXPECTED_DATASET,
        "revision": b2["revision"],
        "path": b2["path"],
        "source_id": source_id,
        "acquisition_id": acquisition_id,
        "receipt": {
            "path": receipt_path,
            "sha256": _sha256(receipt_bytes),
            "evidence_class": "historical",
            "satisfies_live_gate": False,
        },
        "object_identity": {
            "sha256": b2["sha256"],
            "byte_count": b2["byte_count"],
        },
        "gate_row": {
            "approved_denominator_member": True,
            "b1_b2_lineage_complete": False,
            "v4_admission": False,
            "consumer_canary": False,
        },
        "independent_storage_receipt_present": False,
        "admission_history_present": False,
    }


@dataclass(frozen=True)
class QualificationInputs:
    """Validated source reports and identities for the receipt crosswalk."""

    gate_report: dict[str, Any]
    historical_report: dict[str, Any]
    acquisition_import: dict[str, Any]
    gate_sha256: str
    historical_sha256: str
    acquisition_import_sha256: str


def _load_inputs() -> QualificationInputs:
    gate_report, gate_bytes = read_json(GATE_REPORT)
    historical_report, historical_bytes = read_json(HISTORICAL_REPORT)
    acquisition_import, acquisition_bytes = read_json(ACQUISITION_IMPORT)
    gate_rows = {
        (row["dataset"], row["path"]): row for row in gate_report["objects"]
    }
    acquisitions = {
        row["acquisition_id"]: row for row in acquisition_import["records"]
    }
    if len(gate_rows) != EXPECTED_DENOMINATOR:
        raise ValueError(
            "approved M-112 gate denominator changed or is incomplete"
        )
    if len(acquisitions) != len(acquisition_import["records"]):
        raise ValueError(
            "acquisition import contains duplicate acquisition IDs"
        )

    expected_gate_hash = _sha256(gate_bytes)
    if (
        historical_report["inputs"]["per_object_gate_reconciliation_sha256"]
        != expected_gate_hash
    ):
        raise ValueError(
            "historical receipt report is not bound to the current gate report"
        )

    return QualificationInputs(
        gate_report=gate_report,
        historical_report=historical_report,
        acquisition_import=acquisition_import,
        gate_sha256=expected_gate_hash,
        historical_sha256=_sha256(historical_bytes),
        acquisition_import_sha256=_sha256(acquisition_bytes),
    )


def _build_rows(inputs: QualificationInputs) -> list[dict[str, Any]]:
    gate_rows = {
        (row["dataset"], row["path"]): row
        for row in inputs.gate_report["objects"]
    }
    acquisitions = {
        row["acquisition_id"]: row
        for row in inputs.acquisition_import["records"]
    }
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for output in inputs.historical_report["outputs"]:
        receipt_path = output["path"]
        receipt_bytes = (ROOT / receipt_path).read_bytes()
        if _sha256(receipt_bytes.rstrip(b"\n")) != output["sha256"]:
            raise ValueError(
                f"historical receipt digest mismatch: {receipt_path}"
            )
        receipt = json.loads(receipt_bytes)
        acquisition_id = output["acquisition_id"]
        acquisition = acquisitions.get(acquisition_id)
        if acquisition is None:
            raise ValueError(
                f"historical receipt has no acquisition record: {acquisition_id}"
            )
        b2 = acquisition.get("b2_raw_reference")
        if not isinstance(b2, dict):
            raise TypeError(
                f"historical receipt has no immutable B2 reference: {acquisition_id}"
            )
        b2 = cast("dict[str, Any]", b2)
        dataset = b2.get("dataset")
        path = b2.get("path")
        if not isinstance(dataset, str) or not isinstance(path, str):
            raise TypeError(
                f"historical receipt has invalid B2 identity: {acquisition_id}"
            )
        key = (dataset, path)
        gate_row = gate_rows.get(key)
        if gate_row is None:
            raise ValueError(
                f"historical receipt is outside the approved denominator: {key}"
            )
        if key in seen:
            raise ValueError(
                f"duplicate historical receipt for M-112 object: {key}"
            )
        seen.add(key)
        rows.append(
            crosswalk_receipt(
                output=output,
                receipt_path=receipt_path,
                receipt_bytes=receipt_bytes.rstrip(b"\n"),
                receipt=receipt,
                acquisition=acquisition,
                gate_row=gate_row,
            )
        )

    rows.sort(key=itemgetter("dataset", "path"))
    if len(rows) != EXPECTED_HISTORICAL_RECEIPTS:
        raise ValueError("historical receipt projection cohort changed")
    return rows


def build_qualification() -> dict[str, Any]:
    inputs = _load_inputs()
    rows = _build_rows(inputs)
    return {
        "schema_id": "global-medicines-atlas.australian-m112-historical-receipt-gate-crosswalk",
        "schema_version": 1,
        "observed_at": "2026-10-17",
        "requirement": "M-112",
        "status": "14_historical_receipts_crosswalked_all_live_gates_open",
        "inputs": [
            {"path": GATE_REPORT.as_posix(), "sha256": inputs.gate_sha256},
            {
                "path": HISTORICAL_REPORT.as_posix(),
                "sha256": inputs.historical_sha256,
            },
            {
                "path": ACQUISITION_IMPORT.as_posix(),
                "sha256": inputs.acquisition_import_sha256,
            },
        ],
        "scope": {
            "approved_denominator": EXPECTED_DENOMINATOR,
            "reconciled_paths": EXPECTED_DENOMINATOR,
            "denominator_changed": False,
            "historical_receipt_projection_paths": len(rows),
            "unmatched_historical_receipt_projections": 0,
        },
        "counts": {
            "historical_source_receipt_projections": len(rows),
            "live_source_receipts": 0,
            "independent_storage_receipts": 0,
            "complete_b1_b2_lineage": 0,
            "v4_admissions": 0,
            "consumer_canaries": 0,
            "preserved_deferred_paths": EXPECTED_DENOMINATOR,
        },
        "boundaries": {
            "source_payload_bytes_read": False,
            "source_payload_values_read": False,
            "new_acquisition_performed": False,
            "rights_scope_changed": False,
            "external_publication_performed": False,
            "v4_admission_performed": False,
            "consumer_canaries_performed": False,
            "m112_federation_accepted": False,
        },
        "objects": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed report is stale",
    )
    args = parser.parse_args()
    rendered = (
        json.dumps(build_qualification(), indent=2, sort_keys=True) + "\n"
    )
    output_path = ROOT / OUTPUT_PATH
    if args.check:
        if (
            not output_path.exists()
            or output_path.read_text(encoding="utf-8") != rendered
        ):
            raise SystemExit(f"qualification is stale: {OUTPUT_PATH}")
    else:
        output_path.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
