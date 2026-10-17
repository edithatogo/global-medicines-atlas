from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256

import pytest
from scripts.prepare_m112_historical_source_receipts import (
    OBJECT_RIGHTS_METADATA,
    OUTPUT_ROOT,
    QUALIFICATION,
    RECEIPT_JOIN_AUDIT,
    RIGHTS_DECISION,
    ROOT,
    build_receipts,
    render_outputs,
    validate_approved_manifest_scope,
)

from global_medicines_atlas.receipts import EvidenceClass, SourceReceipt


@pytest.mark.unit
def test_m112_historical_source_receipts_bind_approved_14_without_live_claims() -> (
    None
):
    receipts, qualification = build_receipts()

    assert len(receipts) == 14
    assert qualification["scope"]["approved_m112_denominator"] == 1759
    assert qualification["counts"] == {
        "historical_canonical_source_receipts": 14,
        "live_source_receipts": 0,
        "independent_storage_receipts": 0,
        "admission_histories": 0,
    }
    assert qualification["scope"]["source_payload_bytes_read"] is False
    assert qualification["scope"]["source_payload_values_read"] is False
    assert qualification["scope"]["new_acquisition_performed"] is False
    assert qualification["scope"]["rights_scope_changed"] is False
    assert qualification["scope"]["m112_federation_accepted"] is False
    assert all(
        receipt.evidence_class is EvidenceClass.HISTORICAL
        and not receipt.satisfies_live_gate
        and receipt.rights_state.value == "permitted"
        and receipt.sensitivity is not None
        and receipt.sensitivity.publication.value == "review_required"
        and receipt.temporal is not None
        and receipt.temporal.source_published_at is None
        and receipt.temporal.source_effective_at is None
        and receipt.temporal.source_version is None
        and receipt.payload.sha256 == receipt.transformation.output_sha256
        and receipt.payload.byte_count
        == receipt.transformation.output_byte_count
        for receipt in receipts.values()
    )


@pytest.mark.unit
def test_m112_historical_source_receipts_are_canonical_and_reproducible() -> (
    None
):
    outputs = render_outputs()
    receipts, qualification = build_receipts()
    assert QUALIFICATION in outputs
    assert len([path for path in outputs if path != QUALIFICATION]) == 14
    assert json.loads(outputs[QUALIFICATION]) == qualification
    for acquisition_id, receipt in receipts.items():
        path = OUTPUT_ROOT / receipt.source.source_id / f"{acquisition_id}.json"
        encoded = outputs[path]
        assert encoded == receipt.canonical_json() + b"\n"
        rebuilt = SourceReceipt.model_validate_json(encoded)
        assert rebuilt == receipt
        assert sha256(encoded.rstrip(b"\n")).hexdigest() == receipt.digest()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("target", "key", "replacement"),
    [
        ("decision_scope", "dataset", "unapproved/dataset"),
        ("decision_scope", "revision", "0" * 40),
        ("decision_scope", "manifest_sha256", "0" * 64),
        ("rights_record", "path", "raw/outside-approved-scope.csv"),
        ("rights_record", "sha256", "0" * 64),
        ("rights_record", "byte_count", 1),
        ("manifest_record", "sha256_matches_manifest", False),
        ("manifest_record", "byte_count", 1),
    ],
)
def test_exact_rights_scope_rejects_manifest_identity_drift(
    target: str,
    key: str,
    replacement: object,
) -> None:
    rights_decision_path = ROOT / RIGHTS_DECISION
    object_rights_path = ROOT / OBJECT_RIGHTS_METADATA
    receipt_join_path = ROOT / RECEIPT_JOIN_AUDIT
    rights_bytes = rights_decision_path.read_bytes()
    object_rights_bytes = object_rights_path.read_bytes()
    receipt_join_bytes = receipt_join_path.read_bytes()
    decision = json.loads(rights_bytes)
    rights_metadata = json.loads(object_rights_bytes)
    join_audit = json.loads(receipt_join_bytes)

    if target == "decision_scope":
        decision = deepcopy(decision)
        decision["scope"][key] = replacement
    elif target == "rights_record":
        rights_metadata = deepcopy(rights_metadata)
        rights_metadata["records"][0][key] = replacement
    else:
        join_audit = deepcopy(join_audit)
        dataset = next(
            item
            for item in join_audit["datasets"]
            if item["dataset"] == decision["scope"]["dataset"]
        )
        dataset["joined_objects"][0][key] = replacement

    with pytest.raises(ValueError, match=r".+"):
        validate_approved_manifest_scope(
            decision,
            rights_bytes,
            rights_metadata,
            join_audit,
            receipt_join_bytes,
        )
