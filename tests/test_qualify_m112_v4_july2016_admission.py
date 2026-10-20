"""Tests for the exact July 2016 raw B2 M-112 v4 qualification."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.qualify_m112_v4_july2016_admission import (
    CSV_ADMISSION_REPORT,
    DEMOGRAPHICS_Q3_OUTPUT,
    DEMOGRAPHICS_Q3_PATH,
    HISTORICAL_1993_2015_OUTPUT,
    TARGET_BYTES,
    TARGET_EVIDENCE_COMMITS,
    TARGET_IDENTITIES,
    TARGET_PATH,
    TARGET_SHA256,
    build_contract,
    expected_cache_bytes,
    validate_contract,
)

from global_medicines_atlas.federation_consumer import bind_consumer_contract

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = "raw/mbs/utilisation/group/mbs-group-2016-july.csv"
HISTORICAL_PATH = (
    "raw/mbs/utilisation/group/mbs-demographics-historical-1993-2015.zip"
)
DEMOGRAPHICS_Q3_SHA256 = (
    "bc6ad85e41bd2394f4dc0b3550c0657eb7389f444c9300d72105a41530e08e1c"
)
CANARY_RECEIPT = ROOT / (
    "quality/qualifications/"
    "australian-m112-v4-july2016-consumer-canary-20261020-39300224557.json"
)
HISTORICAL_CANARY_RECEIPT = ROOT / (
    "quality/qualifications/"
    "australian-m112-v4-historical-1993-2015-consumer-canary-20261020-39330593204.json"
)


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


def test_csv_contract_pins_its_exact_raw_b2_identity() -> None:
    identity = TARGET_IDENTITIES[CSV_PATH]
    contract = build_contract(
        target_path=CSV_PATH,
    )
    parsed = json.loads(validate_contract(contract))

    assert parsed["source"]["bronze_stratum"] == "B2"
    assert parsed["source"]["representation"] == "raw"
    assert parsed["location"]["dataset"] == identity["dataset"]
    assert parsed["location"]["revision"] == identity["revision"]
    assert parsed["location"]["path"] == CSV_PATH
    assert parsed["location"]["bytes"] == identity["bytes"]
    assert parsed["location"]["sha256"] == identity["sha256"]
    assert parsed["consumers"] == []
    assert parsed["lineage"]["v3_replay"]["url"].startswith(
        "https://raw.githubusercontent.com/edithatogo/global-medicines-atlas/"
        "5b4d66268deccfb28ef33805d474c06aaa940a98/"
    )


def test_historical_demographics_contract_uses_all_exact_candidate_roles() -> (
    None
):
    assert HISTORICAL_1993_2015_OUTPUT.name == (
        "australian-m112-v4-historical-1993-2015-raw-b2-contract.json"
    )
    identity = TARGET_IDENTITIES[HISTORICAL_PATH]
    contract = build_contract(
        target_path=HISTORICAL_PATH,
        evidence_commit="3df35dbd1475557122faa3025b915e37cf202a55",
    )
    parsed = json.loads(validate_contract(contract))

    assert parsed["source"]["source_id"] == identity["source_id"]
    assert parsed["source"]["acquisition_id"] == identity["acquisition_id"]
    assert parsed["source"]["effective_date"] == "2015-12-31"
    assert parsed["source"]["schema_era"].startswith(
        "unqualified-native-schema;"
    )
    assert parsed["location"]["dataset"] == identity["dataset"]
    assert parsed["location"]["revision"] == identity["revision"]
    assert parsed["location"]["path"] == HISTORICAL_PATH
    assert parsed["location"]["bytes"] == identity["bytes"]
    assert parsed["location"]["sha256"] == identity["sha256"]
    assert parsed["lineage"]["v3_replay"]["url"].startswith(
        "https://raw.githubusercontent.com/edithatogo/global-medicines-atlas/"
        "3df35dbd1475557122faa3025b915e37cf202a55/"
    )
    assert parsed["consumers"] == []
    assert parsed["cache"]["state"] == "removed"


def test_merged_historical_role_evidence_binds_the_default_contract() -> None:
    parsed = json.loads(
        validate_contract(build_contract(target_path=HISTORICAL_PATH))
    )

    assert parsed["lineage"]["v3_replay"]["url"].startswith(
        "https://raw.githubusercontent.com/edithatogo/global-medicines-atlas/"
        "060114c0a9d1d6f8122f0829f24257861ae30e75/"
    )


def test_q3_demographics_identity_is_explicitly_allowlisted() -> None:
    identity = TARGET_IDENTITIES[DEMOGRAPHICS_Q3_PATH]

    assert DEMOGRAPHICS_Q3_OUTPUT.name == (
        "australian-m112-v4-demographics-q3-july-raw-b2-contract.json"
    )
    assert identity == {
        "dataset": "edithatogo/australian-mbs-utilisation-archive",
        "revision": "dee9a5b0580dfe394474dc26b372559462e157e7",
        "sha256": DEMOGRAPHICS_Q3_SHA256,
        "bytes": 7_680_041,
        "source_id": "au-data-gov-mbs-demographics",
        "acquisition_id": (
            "75807b1ebadafa0a0566463b0cf4f28cab2bf728d7bee92f61d51fc349d8d9fb"
        ),
    }
    assert TARGET_EVIDENCE_COMMITS[DEMOGRAPHICS_Q3_PATH] is None


def test_csv_admission_receipt_binds_the_exact_candidate_contract() -> None:
    report = json.loads((ROOT / CSV_ADMISSION_REPORT).read_text())

    assert report["status"] == "admitted_pending_consumer_canary"
    assert report["admissions"] == 1
    assert report["consumer_canaries"] == 0
    assert report["admission"]["path"] == CSV_PATH
    assert report["contract_sha256"] == (
        "d1924c8c21a52baff437dcf0ec55e7abffe599bf091bdaea082bc020c203aab7"
    )


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


def test_hosted_canary_receipt_qualifies_only_the_pinned_admitted_object() -> (
    None
):
    report = json.loads(CANARY_RECEIPT.read_text(encoding="utf-8"))
    canary = report["consumer_canary"]

    assert report["status"] == "admitted_with_consumer_canary"
    assert report["approved_denominator"] == 1759
    assert report["admissions"] == 1
    assert report["consumer_canaries"] == 1
    assert report["contract_sha256"] == (
        "b95056d6ab657f5b280870dc2ac7dcb1578019224e843d423a99e2880f451d7e"
    )
    assert canary["status"] == "passed"
    assert canary["object"] == {
        "bytes": TARGET_BYTES,
        "dataset": "edithatogo/australian-mbs-utilisation-archive",
        "path": TARGET_PATH,
        "revision": "dee9a5b0580dfe394474dc26b372559462e157e7",
        "sha256": TARGET_SHA256,
    }
    assert canary["verification"]["origin"] == "remote"
    assert canary["verification"]["remote_digest_match"] is True
    assert canary["verification"]["consumer_stream_digest_match"] is True
    assert canary["verification"]["reader_cache_bytes_after_read"] == 0
    assert canary["verification"]["reader_cache_bytes_after_close"] == 0
    assert canary["verification"]["expired_cache_not_retained"] is True
    assert canary["verification"]["source_values_or_rows_interpreted"] is False
    assert canary["hosted_workflow"]["run_id"] == 39_300_224_557
    assert canary["hosted_workflow"]["commit"] == (
        "500344931252ce65768b55fb2f3e07191470344c"
    )


def test_hosted_canary_offers_the_exact_historical_admitted_object() -> None:
    workflow = (
        ROOT
        / ".github/workflows/australian-m112-v4-july2016-consumer-canary.yml"
    ).read_text(encoding="utf-8")

    assert f"          - {HISTORICAL_PATH}" in workflow
    assert f"          - {DEMOGRAPHICS_Q3_PATH}" in workflow


def test_historical_hosted_canary_receipt_qualifies_exact_admitted_object() -> (
    None
):
    report = json.loads(HISTORICAL_CANARY_RECEIPT.read_text(encoding="utf-8"))
    canary = report["consumer_canary"]

    assert report["status"] == "admitted_with_consumer_canary"
    assert report["admissions"] == 1
    assert report["consumer_canaries"] == 1
    assert report["contract_sha256"] == (
        "992eb2ce2d93891f51423284df2d718bc7d44af6511cc09c11c33a578588210b"
    )
    assert canary["status"] == "passed"
    assert canary["object"] == {
        "bytes": 205885063,
        "dataset": "edithatogo/australian-mbs-utilisation-archive",
        "path": HISTORICAL_PATH,
        "revision": "dee9a5b0580dfe394474dc26b372559462e157e7",
        "sha256": "e00bd214e7f9e2428000a8e67c8d46a78fb4b12f381373d813849287cbc9cc33",
    }
    assert canary["hosted_workflow"]["run_id"] == 39330593204
    assert canary["hosted_workflow"]["commit"] == (
        "3149a5533ecb1b721d9deda66311d4abc94ee3d1"
    )
    assert canary["verification"]["origin"] == "remote"
    assert canary["verification"]["remote_digest_match"] is True
    assert canary["verification"]["consumer_stream_digest_match"] is True
    assert canary["verification"]["reader_cache_bytes_after_read"] == 0
    assert canary["verification"]["reader_cache_bytes_after_close"] == 0
    assert canary["verification"]["source_values_or_rows_interpreted"] is False
