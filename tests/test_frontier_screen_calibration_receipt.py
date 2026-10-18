"""Committed Frontier screening/calibration receipt is reproducible."""

import json
from pathlib import Path

import jsonschema
from scripts.qualify_frontier_screening_calibration import (
    SCHEMA,
    build_receipt,
    canonical_bytes,
)

ROOT = Path(__file__).parents[1]
RECEIPT = (
    ROOT / "quality/qualifications/frontier-screen-calibration-20261018.json"
)


def test_frontier_screen_calibration_receipt_is_schema_valid_and_reproducible() -> (
    None
):
    expected = canonical_bytes(build_receipt())
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_bytes())

    jsonschema.validate(receipt, schema)
    assert RECEIPT.read_bytes() == expected
    assert receipt["screening"]["finding_counts"] == {
        "email_like_value": 1,
        "known_value_digest": 1,
        "sensitive_field_name": 1,
    }
    assert receipt["candidate_calibration"]["confidence_emitted"] is False
    assert receipt["calibration_mechanics_control"]["case_overlap_count"] == 0
