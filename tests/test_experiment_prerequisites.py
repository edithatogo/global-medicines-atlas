"""Prerequisite gates for object versioning and high-update formats."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

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
HUDI_SCRIPT = ROOT / "scripts/run_hudi_experiment.py"


def _load_hudi_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "run_hudi_experiment", HUDI_SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


@pytest.mark.unit
def test_hudi_failure_receipt_is_preserved_and_returns_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _load_hudi_script()

    def fail(_directory: Path) -> tuple[list[dict[str, object]], str]:
        raise RuntimeError("Python runtime unsupported by the preview")

    output = tmp_path / "hudi.json"
    monkeypatch.setattr(script, "_run_hudi", fail)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_hudi_experiment.py", "--output", str(output)],
    )

    assert script.main() == 1
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["outcome"] == "failed"
    assert receipt["correctness_verified"] is False
    assert receipt["error"]["message"] == (
        "Python runtime unsupported by the preview"
    )
