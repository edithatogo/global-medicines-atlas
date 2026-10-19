"""Fail-closed tests for one-object M-112 v3 replay planning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import scripts.qualify_m112_v3_replay as qualification

CSV_TARGET = "raw/mbs/utilisation/group/mbs-group-2016-july.csv"
DEMOGRAPHICS_TARGET = (
    "raw/mbs/utilisation/demographics/mbs-demographics-2016-qtr-3-july.csv"
)


def test_v3_replay_rejects_another_object_after_its_v4_admission() -> None:
    with pytest.raises(ValueError, match="already has a v4 contract"):
        qualification.qualify(target_path=CSV_TARGET)


def test_v3_replay_rejects_paths_outside_approved_raw_mbs_scope() -> None:
    with pytest.raises(ValueError, match="approved raw B2 path"):
        qualification.qualify(target_path="raw/pbs/unknown.pdf")


def test_v3_replay_rejects_replaying_the_admitted_workbook_again() -> None:
    with pytest.raises(ValueError, match="already has a v4 contract"):
        qualification.qualify()


def test_v3_replay_detects_an_existing_exact_v4_contract(
    tmp_path: Path,
) -> None:
    candidate = {
        "dataset": qualification.TARGET_DATASET,
        "revision": qualification.TARGET_REVISION,
        "path": CSV_TARGET,
    }
    contract_path = (
        tmp_path
        / "quality/qualifications/australian-m112-v4-csv-raw-b2-contract.json"
    )
    contract_path.parent.mkdir(parents=True)
    contract_path.write_text(
        json.dumps({"location": candidate}), encoding="utf-8"
    )

    assert (
        qualification._already_admitted(  # pyright: ignore[reportPrivateUsage]
            tmp_path, candidate
        )
        is True
    )


def test_v3_replay_plan_is_schema_valid_and_deterministic() -> None:
    first = qualification.qualify(allow_existing=True)
    second = qualification.qualify(allow_existing=True)

    assert first == second
    assert len(first["snapshots"]) == 1
    snapshot = first["snapshots"][0]
    assert snapshot["partition_value"].endswith(qualification.TARGET_PATH)
    assert snapshot["source_url"].startswith("https://data.gov.au/")
    assert snapshot["replay_eligible"] is True
    assert snapshot["rights_state"] == qualification.RIGHTS_STATE
    assert first["replay_plan"]["eligible_snapshot_count"] == 1
    step = first["replay_plan"]["steps"][0]
    assert step["candidate_only"] is True
    assert step["hosted_replay_status"] == "pending"
    assert step["source_payload_values"] == "not_read"
    assert step["v4_admission_performed"] is False
    assert step["m112_consumer_canary_performed"] is False


def test_v3_replay_supports_exact_qualified_demographics_source() -> None:
    plan = qualification.qualify(
        target_path=DEMOGRAPHICS_TARGET, allow_existing=True
    )

    assert plan["snapshots"][0]["source_id"] == "au-data-gov-mbs-demographics"
    assert plan["contracts"][0]["source_id"] == "au-data-gov-mbs-demographics"
    assert plan["contracts"][0]["contract_id"] == (
        "au-data-gov-mbs-demographics:historical-backfill-replay:v1"
    )
    assert plan["snapshots"][0]["replay_eligible"] is True


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("rights", "exact-scope rights"),
        ("lineage", "complete B1/B2 lineage"),
        ("restore", "anonymous restore receipt"),
    ],
)
def test_v3_replay_rejects_unqualified_candidates(
    monkeypatch: pytest.MonkeyPatch, mutation: str, message: str
) -> None:
    original = qualification._read_json  # pyright: ignore[reportPrivateUsage]

    def read_json(root: Path, relative: str) -> dict[str, Any]:
        document = original(root, relative)
        if relative != qualification.ROLE_REPORT:
            return document
        candidate = next(
            item
            for item in document["objects"]
            if item["path"] == qualification.TARGET_PATH
        )
        if mutation == "rights":
            candidate["rights_state"] = "unknown"
        elif mutation == "lineage":
            candidate["contract_role_states"]["lineage.inputs"] = "partial"
        else:
            candidate["verification_candidate_receipt"][
                "contract_role_state"
            ] = "missing"
        return document

    monkeypatch.setattr(qualification, "_read_json", read_json)
    with pytest.raises(ValueError, match=message):
        qualification.qualify(allow_existing=True)


def test_v3_replay_rejects_changed_external_reference_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = qualification._read_json  # pyright: ignore[reportPrivateUsage]

    def read_json(root: Path, relative: str) -> dict[str, Any]:
        document = original(root, relative)
        if relative.endswith("/manifest.json"):
            document["rows"][0]["external_reference"] = (
                "https://example.org/changed"
            )
        return document

    monkeypatch.setattr(qualification, "_read_json", read_json)
    with pytest.raises(ValueError, match="B2 manifest differs"):
        qualification.qualify(allow_existing=True)
