from __future__ import annotations

import json
from hashlib import sha256

import pytest
from scripts.prepare_m112_historical_source_receipts import (
    OUTPUT_ROOT,
    QUALIFICATION,
    build_receipts,
    render_outputs,
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
