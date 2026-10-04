"""Verify the restored public July 2025 MBS receipt without v4 promotion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from global_medicines_atlas.receipts import SourceReceipt

ROOT = Path(__file__).resolve().parents[1]
AUDIT = (
    ROOT
    / "quality/qualifications/australian-m112-2025-mbs-v4-receipt-readback-20261004.json"
)
RECEIPT = (
    ROOT
    / "quality/bronze/receipts/au-mbs/bbd662119ebebfdf08baf14c0b15c0dd5c93465910fd4f5309f37ecd37a82b8d.json"
)
MANIFEST = (
    ROOT
    / "quality/qualifications/australian-mbs-v4-candidate-2025-07/manifest.json"
)
QUALIFICATION = (
    ROOT
    / "quality/qualifications/australian-mbs-v4-candidate-2025-07/qualification.json"
)


def test_public_v4_receipt_is_restored_and_bound_to_candidate_manifest() -> (
    None
):
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    receipt = SourceReceipt.model_validate_json(RECEIPT.read_bytes())
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    qualification = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    source = manifest["source"]
    value_free_qualification = qualification["qualification"]

    assert audit["remote_readback"]["revision"] == (
        "40891976f77ee5e7688edceed25c9ac98a77547e"
    )
    assert audit["remote_readback"]["anonymous"] is True
    assert audit["local_restore"]["receipt_path"] == str(
        RECEIPT.relative_to(ROOT)
    )
    assert receipt.receipt_id == (
        "public-archive:au-mbs:db873768c5795222455033e2bad28586f19bbf2a10c7d58f06a0671d9111a556"
    )
    assert receipt.source.source_id == "au-mbs"
    assert receipt.source.catalog_version == "2025-07-version-3"
    assert receipt.payload.sha256 == source["sha256"]
    assert receipt.payload.byte_count == source["byte_count"]
    assert receipt.digest() == source["receipt_sha256"]
    assert receipt.digest() == value_free_qualification["receipt_sha256"]
    assert manifest["candidate_only"] is True
    assert qualification["candidate_only"] is True
    assert value_free_qualification["promotion_status"] == "candidate_only"
    assert value_free_qualification["blockers"] == [
        "public_v4_identity_unverified"
    ]
    assert (
        audit["public_v4_candidate"]["reported_blockers"]
        == (value_free_qualification["blockers"])
    )
    assert (
        audit["reconciliation"]["source_receipt_restored_and_verified"] is True
    )
    assert audit["reconciliation"]["m112_b1_event_complete"] is False
    assert audit["reconciliation"]["m112_v4_admission"] is False
    assert audit["reconciliation"]["m112_federation_accepted"] is False
    assert audit["boundaries"]["source_payload_bytes_read"] is False
    assert audit["boundaries"]["source_payload_values_read"] is False
    assert audit["boundaries"]["new_rights_or_licensing_conclusion"] is False


def test_public_v4_metadata_readback_hashes_match_the_pinned_receipt() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    objects = {
        item["role"]: item for item in audit["remote_readback"]["objects"]
    }
    for role, path in {
        "b1_source_receipt": RECEIPT,
        "manifest": MANIFEST,
        "value_free_qualification": QUALIFICATION,
    }.items():
        item = objects[role]
        data = path.read_bytes()
        assert item["size"] == len(data)
        assert item["raw_sha256"] == hashlib.sha256(data).hexdigest()
        git_blob = hashlib.sha1(
            f"blob {len(data)}\0".encode() + data,
            usedforsecurity=False,
        ).hexdigest()
        assert item["git_blob_oid"] == git_blob
    for reference in audit["evidence_inputs"]:
        data = (ROOT / reference["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == reference["sha256"]
