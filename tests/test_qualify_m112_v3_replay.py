"""Fail-closed tests for one-object M-112 v3 replay planning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import scripts.qualify_m112_v3_replay as qualification


def test_v3_replay_plan_is_schema_valid_and_deterministic() -> None:
    first = qualification.qualify()
    second = qualification.qualify()

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
        qualification.qualify()


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
        qualification.qualify()
