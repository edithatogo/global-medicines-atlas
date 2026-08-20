"""Contracts for optional datahouse experiments."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from global_medicines_atlas.datahouse_experiments import (
    EXPERIMENT_IDS,
    ExperimentOutcome,
    ExperimentReceipt,
    batch_manifest,
    classify_prerequisite,
    decision_matrix,
    ducklake_comparison,
    experiment_matrix,
    iceberg_rest_attempt,
    iceberg_v3_capabilities,
    verify_batch_manifest,
)


def test_matrix_covers_every_experiment_and_explicit_outcome(tmp_path) -> None:
    fixture = tmp_path / "fixture.parquet"
    fixture.write_bytes(b"governed synthetic parquet fixture")

    matrix = experiment_matrix(fixture)

    assert tuple(item.experiment_id for item in matrix) == EXPERIMENT_IDS
    assert {item.outcome for item in matrix} == {ExperimentOutcome.NOT_RUN}
    assert all(item.specification.uri.startswith("https://") for item in matrix)
    assert all(item.specification.revision for item in matrix)
    assert all(
        item.fixture_sha256 == hashlib.sha256(fixture.read_bytes()).hexdigest()
        for item in matrix
    )
    assert all(item.limitations and item.rollback_procedure for item in matrix)


def test_receipt_schema_accepts_serialized_matrix(tmp_path) -> None:
    fixture = tmp_path / "fixture.parquet"
    fixture.write_bytes(b"fixture")
    schema = json.loads(
        Path("schemas/datahouse-experiment-receipt-v1.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema)

    for receipt in experiment_matrix(fixture):
        validator.validate(receipt.to_dict())


def test_receipt_rejects_unpinned_specification() -> None:
    with pytest.raises(ValueError, match="revision"):
        ExperimentReceipt.from_dict({
            "schema_version": "1.0",
            "experiment_id": "iceberg_rest",
            "outcome": "not_run",
            "specification": {
                "uri": "https://example.test/spec",
                "revision": "",
            },
            "runtime": {"python": "3.14", "dependencies": []},
            "fixture_sha256": "0" * 64,
            "feature_flags": [],
            "limitations": ["not executed"],
            "rollback_procedure": "remove rebuildable metadata",
        })


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"experiment_id": "unknown"}, "unknown experiment"),
        (
            {"specification": {"uri": "http://example.test", "revision": "v1"}},
            "HTTPS",
        ),
        ({"limitations": []}, "limitation"),
        ({"rollback_procedure": ""}, "rollback"),
    ],
)
def test_receipt_rejects_incomplete_authority(override, message) -> None:
    value = {
        "schema_version": "1.0",
        "experiment_id": "iceberg_rest",
        "outcome": "not_run",
        "specification": {"uri": "https://example.test", "revision": "v1"},
        "runtime": {"python": "3.14", "dependencies": []},
        "fixture_sha256": "0" * 64,
        "feature_flags": [],
        "limitations": ["not run"],
        "rollback_procedure": "delete derivatives",
    }
    value.update(override)
    with pytest.raises(ValueError, match=message):
        ExperimentReceipt.from_dict(value)


def test_receipt_rejects_non_object_runtime() -> None:
    with pytest.raises(TypeError, match="must be objects"):
        ExperimentReceipt.from_dict({"specification": [], "runtime": []})


def test_batch_manifest_is_order_independent_and_detects_tampering() -> None:
    objects = {
        "sha256:alpha": hashlib.sha256(b"alpha").hexdigest(),
        "sha256:beta": hashlib.sha256(b"beta").hexdigest(),
        "sha256:gamma": hashlib.sha256(b"gamma").hexdigest(),
    }

    first = batch_manifest(objects)
    second = batch_manifest(dict(reversed(tuple(objects.items()))))

    assert first == second
    assert verify_batch_manifest(first, objects)
    corrupted = dict(objects)
    corrupted["sha256:beta"] = hashlib.sha256(b"corrupted").hexdigest()
    assert not verify_batch_manifest(first, corrupted)


def test_batch_manifest_rejects_duplicate_or_invalid_authority() -> None:
    digest = hashlib.sha256(b"alpha").hexdigest()
    with pytest.raises(ValueError, match="content ID"):
        batch_manifest([("sha256:alpha", digest), ("sha256:alpha", digest)])
    with pytest.raises(ValueError, match="SHA-256"):
        batch_manifest({"sha256:alpha": "not-a-digest"})
    with pytest.raises(ValueError, match="content ID"):
        batch_manifest([("", digest)])
    assert batch_manifest([])["leaf_count"] == 0
    assert verify_batch_manifest({}, {"sha256:alpha": "invalid"}) is False


def test_iceberg_v3_capabilities_fall_back_without_identity_drift() -> None:
    identity = "gma.bronze.synthetic@sha256:abc"
    result = iceberg_v3_capabilities(
        advertised={"variant", "row_lineage"},
        requested={"variant", "deletion_vectors"},
        table_identity=identity,
    )

    assert result["supported"] == ["variant"]
    assert result["fallback"] == ["deletion_vectors"]
    assert result["table_identity"] == identity
    assert result["fallback_format_version"] == 2
    with pytest.raises(ValueError, match="identity"):
        iceberg_v3_capabilities(
            advertised=set(), requested=set(), table_identity=""
        )


def test_ducklake_uses_disposable_catalogue_and_preserves_baseline(
    tmp_path,
) -> None:
    result = ducklake_comparison(
        tmp_path,
        rows=[(1, "synthetic"), (2, "redistributable")],
    )

    assert result["outcome"] == "supported"
    assert result["row_count"] == 2
    assert result["baseline_sha256"] == result["recovered_sha256"]
    assert result["catalogue_authoritative"] is False


@pytest.mark.parametrize("experiment_id", ["object_versioning", "delta_hudi"])
def test_unmet_entry_conditions_are_explicit(experiment_id) -> None:
    result = classify_prerequisite(
        experiment_id,
        evidence={},
    )

    assert result.outcome is ExperimentOutcome.NOT_RUN_PREREQUISITE_UNMET
    assert result.limitations
    if experiment_id == "delta_hudi":
        complete = classify_prerequisite(
            experiment_id,
            evidence={
                "update_rate": 1,
                "delete_rate": 1,
                "concurrency": 1,
                "transaction_requirements": "atomic updates",
            },
        )
        assert complete.outcome is ExperimentOutcome.NOT_RUN


def test_unknown_prerequisite_gate_is_rejected() -> None:
    with pytest.raises(ValueError, match="no prerequisite gate"):
        classify_prerequisite("iceberg_rest", {})


def test_iceberg_rest_unavailable_is_a_reproducible_failure_receipt(
    tmp_path,
) -> None:
    fixture = tmp_path / "fixture.parquet"
    fixture.write_bytes(b"fixture")

    receipt = iceberg_rest_attempt(fixture, endpoint=None)

    assert receipt.outcome is ExperimentOutcome.FAILED
    assert receipt.feature_flags == ("endpoint_unconfigured",)
    assert "No disposable Iceberg REST endpoint" in receipt.limitations[0]
    with pytest.raises(NotImplementedError, match="endpoint"):
        iceberg_rest_attempt(fixture, endpoint="http://127.0.0.1:8181")


def test_cross_experiment_disposition_separates_evidence_from_inference(
    tmp_path,
) -> None:
    fixture = tmp_path / "fixture.parquet"
    fixture.write_bytes(b"fixture")
    receipts = list(experiment_matrix(fixture))
    receipts[2] = ExperimentReceipt(
        experiment_id="ducklake",
        outcome=ExperimentOutcome.SUPPORTED,
        specification=receipts[2].specification,
        fixture_sha256=receipts[2].fixture_sha256,
        limitations=("Single embedded implementation only.",),
        rollback_procedure="Delete disposable derivatives.",
    )

    matrix = decision_matrix(receipts)

    assert matrix["ducklake"]["disposition"] == "continue-experiment"
    assert matrix["object_versioning"]["disposition"] == "not-run"
    assert matrix["ducklake"]["deployment_authorized"] is False
    with pytest.raises(ValueError, match="missing experiment"):
        decision_matrix(receipts[:-1])
