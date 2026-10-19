"""Tests for the exact July 2016 raw B2 M-112 v4 qualification."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.qualify_m112_v4_july2016_admission import (
    TARGET_BYTES,
    TARGET_PATH,
    TARGET_SHA256,
    build_contract,
    expected_cache_bytes,
    validate_contract,
)

from global_medicines_atlas.federation_consumer import bind_consumer_contract

ROOT = Path(__file__).resolve().parents[1]


def test_contract_pins_one_raw_b2_object_and_leaves_canary_pending() -> None:
    contract = build_contract()
    encoded = validate_contract(contract)
    parsed = json.loads(encoded)

    assert parsed["source"]["bronze_stratum"] == "B2"
    assert parsed["source"]["representation"] == "raw"
    assert parsed["source"]["schema_era"].startswith(
        "unqualified-native-schema"
    )
    assert parsed["location"]["path"] == TARGET_PATH
    assert parsed["location"]["bytes"] == TARGET_BYTES
    assert parsed["location"]["sha256"] == TARGET_SHA256
    assert parsed["consumers"] == []


def test_actual_consumer_binding_uses_the_exact_contract_identity() -> None:
    encoded = validate_contract(build_contract())

    binding = bind_consumer_contract(
        encoded,
        consumer_repository="edithatogo/global-medicines-atlas",
        consumer_commit="a" * 40,
    )

    assert binding.path == TARGET_PATH
    assert binding.object_sha256 == TARGET_SHA256
    assert binding.byte_count == TARGET_BYTES
    assert binding.contract_sha256


def test_contract_rejects_consumer_or_object_identity_drift() -> None:
    contract = build_contract()
    contract["location"]["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="identity mismatch"):
        validate_contract(contract)


def test_contract_is_schema_and_semantically_valid() -> None:
    contract = build_contract()

    raw = validate_contract(contract, root=ROOT)

    assert raw.endswith(b"\n")
    assert b"source-native workbook layout remains unqualified" not in raw


@pytest.mark.parametrize(
    ("expiry_delta", "expected"),
    [(timedelta(seconds=-1), 0), (timedelta(seconds=1), TARGET_BYTES)],
)
def test_reader_cache_expectation_follows_the_admitted_expiry(
    expiry_delta: timedelta, expected: int
) -> None:
    observed_at = datetime(2026, 10, 20, tzinfo=UTC)

    assert (
        expected_cache_bytes(observed_at + expiry_delta, observed_at)
        == expected
    )
