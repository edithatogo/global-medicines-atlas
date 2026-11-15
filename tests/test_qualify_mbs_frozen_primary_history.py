"""Existing MBS primary history must match exact public evidence."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import scripts.qualify_mbs_frozen_primary_history as qualification


def _inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return tuple(
        json.loads((qualification.ROOT / path).read_bytes())
        for path in (
            qualification.RECEIPT,
            qualification.NATIVE,
            qualification.BINDING,
        )
    )  # type: ignore[return-value]


def test_existing_receipt_matches_seven_exact_frozen_objects() -> None:
    result = qualification.reconcile(*_inputs())
    combined = qualification.build()
    memory = combined.pop("primary_memory")
    assert result == combined
    assert memory["exact_objects_passed"] == 3
    assert memory["independent_recovery_established"] is False
    assert result["summary"] == {
        "frozen_exact_matches": 7,
        "outside_objects_not_covered": 4,
        "independent_recovery_established": False,
    }
    assert all(
        not result["boundaries"][key]
        for key in (
            "new_payload_reads",
            "source_values_or_rows_retained",
            "participant_or_cohort_data_accessed",
            "dataset_added_or_published",
            "v4_admission_or_consumer_canary",
        )
    )


@pytest.mark.parametrize(
    ("field", "value"), [("actor", "user"), ("body_sha256", "0" * 64)]
)
def test_rejects_wrong_receipt_provenance(field: str, value: str) -> None:
    receipt, native, binding = _inputs()
    native["comment"][field] = value
    with pytest.raises(ValueError, match="Actions identity differs"):
        qualification.reconcile(receipt, native, binding)


def test_rejects_mismatched_historical_revision() -> None:
    receipt, native, binding = _inputs()
    receipt["revision"] = "0" * 40
    with pytest.raises(ValueError, match="archive receipt identity differs"):
        qualification.reconcile(receipt, native, binding)


def test_rejects_missing_or_replaced_primary_inventory_member() -> None:
    receipt, native, binding = _inputs()
    receipt["observed"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="primary inventory differs"):
        qualification.reconcile(receipt, native, binding)


def test_rejects_claiming_outside_revision_as_frozen() -> None:
    receipt, native, binding = _inputs()
    binding["objects"][0]["revision"] = "0" * 40
    with pytest.raises(ValueError, match="exact-match denominator differs"):
        qualification.reconcile(receipt, native, binding)


def test_build_rejects_modified_original_receipt(tmp_path: Path) -> None:
    receipt, native, binding = _inputs()
    for path, value in zip(
        (qualification.RECEIPT, qualification.NATIVE, qualification.BINDING),
        (receipt, native, binding),
        strict=True,
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(copy.deepcopy(value)), encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        qualification.build(tmp_path)


def test_primary_memory_rejects_unclosed_buffer() -> None:
    values = [
        json.loads((qualification.ROOT / path).read_bytes())
        for path in (
            qualification.MEMORY,
            qualification.ARTIFACT,
            qualification.REPLAYS,
        )
    ]
    values[0]["objects"][0]["memory_buffer_closed"] = False
    with pytest.raises(ValueError, match="privacy boundary differs"):
        qualification.reconcile_memory(*values)


def test_primary_memory_rejects_duplicate_object() -> None:
    values = [
        json.loads((qualification.ROOT / path).read_bytes())
        for path in (
            qualification.MEMORY,
            qualification.ARTIFACT,
            qualification.REPLAYS,
        )
    ]
    values[0]["objects"][1] = values[0]["objects"][0]
    with pytest.raises(ValueError, match="object path differs"):
        qualification.reconcile_memory(*values)


def test_report_cli_writes_and_checks_frozen_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(qualification, "ROOT", tmp_path)
    monkeypatch.setattr(qualification, "build", lambda: {"objects": []})
    target = tmp_path / qualification.OUTPUT
    target.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "argv", ["qualification"])
    assert qualification.main() == 0
    assert json.loads(target.read_text()) == {"objects": []}
    monkeypatch.setattr(sys, "argv", ["qualification", "--check"])
    assert qualification.main() == 0
    target.write_text("{}")
    with pytest.raises(ValueError, match="report is stale"):
        qualification.main()
