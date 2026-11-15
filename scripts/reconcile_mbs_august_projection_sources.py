"""Reconstruct missing source metadata from existing August MBS receipts.

The B1 events describe the original acquisitions; the B2 references were
created later and point to an already verified, byte-identical archive object.
No payload is fetched, read or written, and no admission is made.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import scripts.qualify_m112_existing_reimbursement_batch as bounded
import scripts.qualify_mbs_august_projection_field_lineage as lineage

from global_medicines_atlas.bronze_raw_evidence import (
    RawEvidenceKind,
    RawEvidenceManifest,
    build_raw_evidence_reference_from_acquisition,
)
from global_medicines_atlas.receipts import (
    AcquisitionEvent,
    SensitivityClassification,
    SourceReceipt,
    require_temporal,
)

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = "quality/qualifications/australian-mbs-august-source-reconstruction-20261115"
REPORT = f"{DIRECTORY}/reconstruction.json"
RECORDED_ON = "2026-11-15"
OUTPUTS_PER_PRODUCER = 2
ACQUISITIONS = {
    "99fa": "783bd12fab14dc8f93cb34b1d87e9c3f7c95543d261b008f4e0da018a3d11e57",
    "d781": "caa6da91b9a87a5094fc803b378321430bdd9c609b36298c8205747bc7651e81",
}


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _event(receipt: SourceReceipt, acquisition_id: str) -> AcquisitionEvent:
    temporal = require_temporal(receipt.temporal)
    _require(
        temporal.acquisition_id == acquisition_id
        and temporal.content_id == receipt.payload.sha256 == lineage.SOURCE_SHA
        and receipt.payload.byte_count == lineage.SOURCE_BYTES
        and temporal.source_version == "2026-08-01"
        and receipt.source.source_id == "au-mbs"
        and receipt.retrieval.status.value == "succeeded"
        and receipt.sensitivity is not None
        and receipt.sensitivity.data_sensitivity.value == "non_sensitive"
        and receipt.sensitivity.personal_data.value == "none",
        "original source receipt identity or classification differs",
    )
    return AcquisitionEvent(
        acquisition_id=temporal.acquisition_id,
        content_id=receipt.payload.sha256,
        source_id=receipt.source.source_id,
        source_version=temporal.source_version,
        retrieved_at=receipt.retrieval.retrieved_at,
        source_published_at=temporal.source_published_at,
        source_effective_at=temporal.source_effective_at,
        valid_from=temporal.valid_from,
        valid_to=temporal.valid_to,
        payload_sha256=receipt.payload.sha256,
        source=receipt.source,
        retrieval=receipt.retrieval,
        reuse=receipt.reuse,
        rights_state=receipt.rights_state,
        rights_reference=receipt.rights_reference,
        rights_policy=receipt.rights_policy,
        evidence_class=receipt.evidence_class,
        sensitivity=receipt.sensitivity or SensitivityClassification(),
    )


def build(root: Path = ROOT) -> dict[str, bytes]:  # ruff: ignore[too-many-locals] -- bind distinct source identities
    """Produce exact, retrospective metadata without mutating the originals."""
    _vocabulary, crosswalk = lineage.build(root)
    digest = bounded.read_bound_metadata(
        root, *lineage.INPUTS["digest_receipt"]
    )
    matching = [
        row for row in digest["objects"] if row["path"] == lineage.SOURCE
    ]
    _require(
        len(matching) == 1
        and matching[0]
        == {
            "dataset": lineage.DATASET,
            "revision": lineage.FROZEN_REVISION,
            "path": lineage.SOURCE,
            "sha256": lineage.SOURCE_SHA,
            "byte_count": lineage.SOURCE_BYTES,
        }
        and digest["boundaries"]["payload_bytes_persisted_or_emitted"] is False,
        "existing source archive digest evidence differs",
    )
    archive_uri = (
        f"https://huggingface.co/datasets/{lineage.DATASET}/resolve/"
        f"{lineage.FROZEN_REVISION}/{lineage.SOURCE}"
    )
    outputs: dict[str, bytes] = {}
    records: list[dict[str, Any]] = []
    for name, acquisition_id in ACQUISITIONS.items():
        receipt_path, receipt_sha = lineage.INPUTS[f"receipt_{name}"]
        receipt_bytes = (root / receipt_path).read_bytes()
        _require(
            _sha(receipt_bytes) == receipt_sha, "source receipt digest differs"
        )
        receipt = SourceReceipt.model_validate_json(receipt_bytes)
        event = _event(receipt, acquisition_id)
        b2 = RawEvidenceManifest.from_rows((
            build_raw_evidence_reference_from_acquisition(
                event,
                external_reference=archive_uri,
                kind=RawEvidenceKind.PAYLOAD,
                media_type="application/xml",
            ),
        ))
        linked = [
            row
            for row in crosswalk["objects"]
            if row["source_receipt"]["sha256"] == receipt_sha
        ]
        _require(
            len(linked) == OUTPUTS_PER_PRODUCER,
            "source receipt projection set differs",
        )
        event_path = f"{DIRECTORY}/{name}-acquisition.json"
        manifest_path = f"{DIRECTORY}/{name}-b2-reference.json"
        outputs[event_path] = event.canonical_json()
        outputs[manifest_path] = b2.canonical_json()
        records.append({
            "producer": name,
            "acquisition_id": acquisition_id,
            "original_retrieved_at": receipt.retrieval.retrieved_at.isoformat(),
            "original_receipt": {"path": receipt_path, "sha256": receipt_sha},
            "reconstructed_event": {
                "path": event_path,
                "sha256": _sha(outputs[event_path]),
            },
            "later_b2_reference": {
                "path": manifest_path,
                "sha256": _sha(outputs[manifest_path]),
            },
            "existing_archive_verified_at": digest["verified_at"],
            "archive_identity": matching[0],
            "projection_paths": sorted(row["path"] for row in linked),
        })
    outputs[REPORT] = _json({
        "schema_id": "global-medicines-atlas.mbs-august-reconstructed-source-metadata",
        "schema_version": 1,
        "recorded_on": RECORDED_ON,
        "source_digest_evidence": {
            "path": lineage.INPUTS["digest_receipt"][0],
            "sha256": lineage.INPUTS["digest_receipt"][1],
        },
        "records": records,
        "boundaries": {
            "events_and_b2_references_are_original_historical_files": False,
            "b2_reference_existed_at_original_retrieval": "not_established",
            "source_payload_read_or_written": False,
            "participant_or_cohort_data_accessed": False,
            "bronze_processing_or_v4_admission": False,
            "dataset_acquired_or_published": False,
        },
    })
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for relative, data in build().items():
        path = ROOT / relative
        if args.check:
            _require(
                path.is_file() and path.read_bytes() == data,
                f"stale: {relative}",
            )
        else:
            _require(
                not path.exists() or path.read_bytes() == data,
                f"immutable conflict: {relative}",
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print("Reconstructed two source metadata pairs; no payload or admission")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
