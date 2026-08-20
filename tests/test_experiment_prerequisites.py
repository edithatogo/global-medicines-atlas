"""Prerequisite gates for object versioning and high-update formats."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.experiment_prerequisites import (
    ExperimentPrerequisiteReceipt,
)

ROOT = Path(__file__).resolve().parents[1]
OBJECT_VERSIONING = (
    ROOT / "quality/qualifications/object-versioning-prerequisite.json"
)
DELTA_HUDI = ROOT / "quality/qualifications/delta-hudi-prerequisite.json"


@pytest.mark.unit
@pytest.mark.parametrize("path", [OBJECT_VERSIONING, DELTA_HUDI])
def test_committed_prerequisite_receipts_fail_closed(path: Path) -> None:
    receipt = ExperimentPrerequisiteReceipt.model_validate_json(
        path.read_bytes()
    )

    assert receipt.eligible is False
    assert receipt.outcome == "not_run_prerequisite_unmet"
    assert receipt.credentials_created is False
    assert receipt.production_deployment_claimed is False
    assert any(not check.satisfied for check in receipt.checks)


@pytest.mark.unit
def test_satisfied_check_requires_evidence() -> None:
    payload = json.loads(OBJECT_VERSIONING.read_text(encoding="utf-8"))
    payload["checks"][0]["satisfied"] = True

    with pytest.raises(ValidationError, match="requires evidence"):
        ExperimentPrerequisiteReceipt.model_validate(payload)


@pytest.mark.unit
def test_receipt_rejects_false_eligibility_or_outcome() -> None:
    payload = json.loads(DELTA_HUDI.read_text(encoding="utf-8"))
    payload["eligible"] = True
    with pytest.raises(ValidationError, match="complete check state"):
        ExperimentPrerequisiteReceipt.model_validate(payload)

    payload = json.loads(DELTA_HUDI.read_text(encoding="utf-8"))
    payload["outcome"] = "eligible"
    with pytest.raises(ValidationError, match="prerequisite eligibility"):
        ExperimentPrerequisiteReceipt.model_validate(payload)
