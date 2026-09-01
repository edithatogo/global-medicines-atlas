"""Frontier experiments cannot begin from speculative prerequisites."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.frontier_experiment_matrix import (
    FrontierExperimentMatrix,
    verify_imported_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "quality/qualifications/frontier-experiment-matrix.json"


def document():
    return json.loads(MATRIX.read_text())


def test_checked_in_matrix_is_complete_bounded_and_inert() -> None:
    matrix = FrontierExperimentMatrix.model_validate(document())
    verify_imported_evidence(matrix, ROOT)
    assert {item.size.value for item in matrix.workloads} == {
        "tiny",
        "medium",
        "large",
    }
    assert not any(item.experiment_started for item in matrix.experiments)
    assert not any(
        item.production_dependency_adopted for item in matrix.experiments
    )
    assert not any(
        item.technology_promotion_claimed for item in matrix.experiments
    )


@pytest.mark.parametrize("field", ["revision", "path", "sha256"])
def test_partial_public_identity_fails(field: str) -> None:
    raw = document()
    raw["experiments"][0]["public_object"] = {
        "dataset": "edithatogo/australian-pbs-source-archive",
        field: "a" * (40 if field == "revision" else 64)
        if field != "path"
        else "x",
        "anonymously_verified": False,
    }
    with pytest.raises(ValidationError, match="identity must be complete"):
        FrontierExperimentMatrix.model_validate(raw)


def test_unmet_or_unverified_prerequisites_block_start() -> None:
    raw = document()
    row = raw["experiments"][0]
    row["experiment_started"] = True
    with pytest.raises(ValidationError, match="without complete prerequisites"):
        FrontierExperimentMatrix.model_validate(raw)

    row["prerequisite_evidence"] = {
        "exact_public_object": True,
        "anonymous_digest": True,
        "request_instrumentation": True,
    }
    row["public_object"] = {
        "dataset": "edithatogo/australian-pbs-source-archive",
        "revision": "a" * 40,
        "path": "bronze/example.parquet",
        "sha256": "b" * 64,
        "anonymously_verified": False,
    }
    with pytest.raises(ValidationError, match="without complete prerequisites"):
        FrontierExperimentMatrix.model_validate(raw)


def test_missing_prerequisite_key_blocks_start() -> None:
    raw = document()
    row = raw["experiments"][0]
    row["prerequisite_evidence"].pop("anonymous_digest")
    with pytest.raises(ValidationError, match="prerequisite denominator"):
        FrontierExperimentMatrix.model_validate(raw)


def test_reused_result_requires_imported_decision() -> None:
    raw = document()
    reused = next(
        item for item in raw["experiments"] if item["disposition"] == "reused"
    )
    reused["reused_evidence"] = []
    with pytest.raises(ValidationError, match="requires imported evidence"):
        FrontierExperimentMatrix.model_validate(raw)


def test_matrix_rejects_unimported_or_changed_evidence(tmp_path: Path) -> None:
    raw = document()
    raw["experiments"][0]["reused_evidence"] = [
        "quality/qualifications/other.json"
    ]
    with pytest.raises(ValidationError, match="unimported"):
        FrontierExperimentMatrix.model_validate(raw)

    matrix = FrontierExperimentMatrix.model_validate(document())
    for item in matrix.imported_evidence:
        target = tmp_path / item.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / item.path).read_bytes())
    first = tmp_path / matrix.imported_evidence[0].path
    first.write_bytes(first.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_imported_evidence(matrix, tmp_path)


def test_profiles_require_ordered_unique_bounds() -> None:
    raw = document()
    raw["workloads"][1] = copy.deepcopy(raw["workloads"][0])
    with pytest.raises(ValidationError, match="required once"):
        FrontierExperimentMatrix.model_validate(raw)


@pytest.mark.parametrize(
    "dimension",
    [
        "maximum_rows",
        "maximum_source_bytes",
        "maximum_requests",
        "maximum_memory_bytes",
    ],
)
def test_profiles_require_every_bound_to_strictly_increase(
    dimension: str,
) -> None:
    raw = document()
    raw["workloads"][1][dimension] = raw["workloads"][0][dimension]
    with pytest.raises(ValidationError, match="bounds must increase"):
        FrontierExperimentMatrix.model_validate(raw)


def test_matrix_requires_exact_experiment_family_denominator() -> None:
    raw = document()
    raw["experiments"][0]["experiment_id"] = "invented_experiment"
    with pytest.raises(ValidationError, match="unknown frontier experiment"):
        FrontierExperimentMatrix.model_validate(raw)


@pytest.mark.parametrize(
    "field", ["baseline", "threshold", "rights_sensitivity_review"]
)
def test_every_experiment_requires_decision_inputs(field: str) -> None:
    raw = document()
    raw["experiments"][0].pop(field)
    with pytest.raises(ValidationError):
        FrontierExperimentMatrix.model_validate(raw)
