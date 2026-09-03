"""Contracts for optional, non-blocking datahouse experiments."""

from __future__ import annotations

import importlib.util
import json
import tomllib
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from global_medicines_atlas.datahouse_experiment_matrix import (
    ALL_EXPERIMENTS,
    ExperimentMatrix,
    ExperimentOutcome,
    matrix_digest,
    verify_matrix_inputs,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "quality/qualifications/datahouse-experiment-matrix.json"
SCHEMA = ROOT / "schemas/datahouse-experiment-matrix-v1.json"


def _payload() -> dict[str, object]:
    return json.loads(MATRIX.read_text(encoding="utf-8"))


@pytest.mark.unit
def test_committed_matrix_covers_every_experiment_once() -> None:
    matrix = ExperimentMatrix.model_validate_json(MATRIX.read_bytes())

    assert {item.experiment_id for item in matrix.experiments} == set(
        ALL_EXPERIMENTS
    )
    assert len(matrix.experiments) == len(ALL_EXPERIMENTS)
    assert matrix.bronze_completion_blocking is False
    assert matrix.payload_receipts_remain_authoritative is True
    assert matrix_digest(matrix) == matrix_digest(
        ExperimentMatrix.model_validate(matrix.model_dump(mode="json"))
    )


@pytest.mark.unit
def test_matrix_rejects_missing_and_duplicate_experiments() -> None:
    payload = _payload()
    experiments = payload["experiments"]
    assert isinstance(experiments, list)
    payload["experiments"] = experiments[:-1]
    with pytest.raises(ValidationError, match="exactly once"):
        ExperimentMatrix.model_validate(payload)

    payload = _payload()
    experiments = payload["experiments"]
    assert isinstance(experiments, list)
    experiments[-1] = experiments[0]
    with pytest.raises(ValidationError, match="exactly once"):
        ExperimentMatrix.model_validate(payload)


@pytest.mark.unit
def test_not_run_outcome_requires_unmet_prerequisites() -> None:
    payload = _payload()
    experiments = payload["experiments"]
    assert isinstance(experiments, list)
    item = cast("dict[str, object]", experiments[0])
    assert isinstance(item, dict)
    item["outcome"] = ExperimentOutcome.NOT_RUN_PREREQUISITE_UNMET
    item["prerequisites_met"] = True

    with pytest.raises(ValidationError, match="unmet prerequisite"):
        ExperimentMatrix.model_validate(payload)


@pytest.mark.unit
def test_executed_outcome_requires_measured_evidence() -> None:
    payload = _payload()
    experiments = payload["experiments"]
    assert isinstance(experiments, list)
    item = cast("dict[str, object]", experiments[0])
    assert isinstance(item, dict)
    item["outcome"] = ExperimentOutcome.SUPPORTED
    item["prerequisites_met"] = True
    item["evidence"] = []

    with pytest.raises(ValidationError, match="evidence"):
        ExperimentMatrix.model_validate(payload)


@pytest.mark.unit
def test_specification_references_are_version_or_revision_pinned() -> None:
    matrix = ExperimentMatrix.model_validate_json(MATRIX.read_bytes())

    assert all(
        reference.version or reference.revision
        for item in matrix.experiments
        for reference in item.specifications
    )

    payload = _payload()
    experiments = payload["experiments"]
    assert isinstance(experiments, list)
    item = cast("dict[str, object]", experiments[0])
    specifications = item["specifications"]
    assert isinstance(specifications, list)
    reference = cast("dict[str, object]", specifications[0])
    reference.pop("version", None)
    reference.pop("revision", None)
    with pytest.raises(ValidationError, match="version or revision"):
        ExperimentMatrix.model_validate(payload)


@pytest.mark.unit
def test_executed_outcome_rejects_unmet_prerequisites() -> None:
    payload = _payload()
    experiments = payload["experiments"]
    assert isinstance(experiments, list)
    item = cast("dict[str, object]", experiments[0])
    item["outcome"] = ExperimentOutcome.FAILED
    item["prerequisites_met"] = False
    item["evidence"] = ["quality/qualifications/failure.json"]

    with pytest.raises(ValidationError, match="satisfied prerequisites"):
        ExperimentMatrix.model_validate(payload)


@pytest.mark.unit
def test_matrix_rows_record_measurement_and_disposition_contract() -> None:
    matrix = ExperimentMatrix.model_validate_json(MATRIX.read_bytes())

    assert all(item.unmet_requirement for item in matrix.experiments)
    assert all(item.hypothesis and item.baseline for item in matrix.experiments)
    assert all(
        item.thresholds and item.rights_review for item in matrix.experiments
    )
    assert {item.disposition for item in matrix.experiments} <= {
        "promote-candidate",
        "retain-preview",
        "defer",
        "reject",
    }


@pytest.mark.unit
def test_unrun_experiment_cannot_be_marked_promotion_candidate() -> None:
    payload = _payload()
    experiments = payload["experiments"]
    assert isinstance(experiments, list)
    item = cast("dict[str, object]", experiments[3])
    item["disposition"] = "promote-candidate"

    with pytest.raises(ValidationError, match="successful outcome"):
        ExperimentMatrix.model_validate(payload)


@pytest.mark.unit
@pytest.mark.parametrize(
    "outcome", [ExperimentOutcome.UNSUPPORTED, ExperimentOutcome.FAILED]
)
def test_unsuccessful_experiment_cannot_be_promotion_candidate(
    outcome: ExperimentOutcome,
) -> None:
    payload = _payload()
    experiments = cast("list[dict[str, object]]", payload["experiments"])
    item = experiments[0]
    item["outcome"] = outcome
    item["disposition"] = "promote-candidate"

    with pytest.raises(ValidationError, match="successful outcome"):
        ExperimentMatrix.model_validate(payload)


@pytest.mark.unit
def test_v1_rows_without_enrichment_fields_remain_compatible() -> None:
    payload = _payload()
    experiments = cast("list[dict[str, object]]", payload["experiments"])
    for item in experiments:
        for field in (
            "unmet_requirement",
            "hypothesis",
            "baseline",
            "thresholds",
            "rights_review",
            "disposition",
        ):
            item.pop(field)

    matrix = ExperimentMatrix.model_validate(payload)
    assert all(item.disposition is None for item in matrix.experiments)


@pytest.mark.unit
def test_matrix_input_digests_are_verified(tmp_path: Path) -> None:
    matrix = ExperimentMatrix.model_validate_json(MATRIX.read_bytes())
    verify_matrix_inputs(matrix, ROOT)

    fixture = tmp_path / matrix.fixture_path
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(b"changed")
    lock = tmp_path / matrix.dependency_lock_path
    lock.write_bytes((ROOT / matrix.dependency_lock_path).read_bytes())

    with pytest.raises(ValueError, match="digest mismatch"):
        verify_matrix_inputs(matrix, tmp_path)


@pytest.mark.unit
def test_matrix_input_verification_rejects_missing_files(
    tmp_path: Path,
) -> None:
    matrix = ExperimentMatrix.model_validate_json(MATRIX.read_bytes())

    with pytest.raises(FileNotFoundError):
        verify_matrix_inputs(matrix, tmp_path)


@pytest.mark.unit
def test_experiment_dependencies_remain_outside_core() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    runtime = "\n".join(project["project"]["dependencies"]).lower()

    assert "pyiceberg" not in runtime
    assert "ducklake" not in runtime
    assert "lakefs" not in runtime
    assert "deltalake" not in runtime
    assert "hudi" not in runtime
    assert (
        importlib.util.find_spec("global_medicines_atlas.bronze_recovery")
        is not None
    )


@pytest.mark.unit
def test_committed_json_schema_matches_model() -> None:
    committed = json.loads(SCHEMA.read_text(encoding="utf-8"))
    generated = ExperimentMatrix.model_json_schema()

    assert committed == generated
