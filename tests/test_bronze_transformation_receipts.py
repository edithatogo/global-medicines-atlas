"""Acquisition, admission, and transformation evidence stay distinct."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from tests.test_source_receipts import source_receipt

import global_medicines_atlas.bronze_transformation as transformation_module
from global_medicines_atlas.bronze_admission import admit_bronze_landing
from global_medicines_atlas.bronze_landing import land_bronze_payload
from global_medicines_atlas.bronze_transformation import (
    TransformationRunReceipt,
    receipt_for_parquet,
    write_transformation_run_receipt,
)
from global_medicines_atlas.receipts import (
    PayloadEvidence,
    TransformationEvidence,
    temporal_identity_from_source,
)
from global_medicines_atlas.reuse_gate import acquire_new_decision

ROOT = Path(__file__).resolve().parents[1]
TRANSFORMATION_SCHEMA = ROOT / "schemas/bronze-transformation-run-v1.json"
PAYLOAD = b'{"medicine":"actual parquet identity"}'
NOW = datetime(2026, 8, 20, 8, 0, tzinfo=UTC)


def _receipt_with_legacy_raw_output():
    receipt = source_receipt()
    evidence = PayloadEvidence.from_bytes(PAYLOAD)
    retrieval = receipt.retrieval.model_copy(update={"retrieved_at": NOW})
    return receipt.model_copy(
        update={
            "retrieval": retrieval,
            "payload": evidence,
            "reuse": acquire_new_decision(receipt.source.source_id),
            "temporal": temporal_identity_from_source(
                retrieved_at=NOW,
                source_id=receipt.source.source_id,
                payload_sha256=evidence.sha256,
                original_uri=str(retrieval.uri),
            ),
            "transformation": TransformationEvidence(
                transformation_id="legacy-source-transform",
                transformation_sha256="a" * 64,
                output_sha256=evidence.sha256,
                output_byte_count=len(PAYLOAD),
            ),
        }
    )


@pytest.mark.unit
def test_actual_parquet_bytes_define_every_parquet_identity(
    tmp_path: Path,
) -> None:
    receipt = _receipt_with_legacy_raw_output()
    landing = land_bronze_payload(
        PAYLOAD,
        receipt,
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    actual_digest = sha256(landing.parquet_path.read_bytes()).hexdigest()
    run = landing.transformation_run

    assert actual_digest != receipt.payload.sha256
    assert receipt.transformation.output_sha256 == receipt.payload.sha256
    assert run.input_content_id == receipt.payload.sha256
    assert run.output.sha256 == actual_digest
    assert run.output.byte_count == landing.parquet_path.stat().st_size
    assert landing.table.parquet_digest == actual_digest
    lineage = json.loads(landing.lineage_path.read_bytes())
    parquet = next(
        item
        for item in lineage["outputs"]
        if item["namespace"] == "gma.acquisition_manifest"
    )
    assert parquet["facets"]["version"]["datasetVersion"] == actual_digest
    assert parquet["name"].endswith(actual_digest)
    assert (
        lineage["run"]["facets"]["gma_transformation"]["transformationRunId"]
        == run.run_id
    )


@pytest.mark.unit
def test_three_receipt_types_are_separate_and_append_only(
    tmp_path: Path,
) -> None:
    landing = land_bronze_payload(
        PAYLOAD,
        _receipt_with_legacy_raw_output(),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
    )
    acquisition_path = next(
        (tmp_path / "bronze" / "acquisitions").rglob("*.json")
    )
    acquisition = json.loads(acquisition_path.read_bytes())
    transformation = TransformationRunReceipt.model_validate_json(
        landing.transformation_receipt_path.read_bytes()
    )
    schema = json.loads(TRANSFORMATION_SCHEMA.read_bytes())
    Draft202012Validator(schema).validate(
        json.loads(landing.transformation_receipt_path.read_bytes())
    )

    assert "transformation" not in acquisition
    assert acquisition["retrieval"]["uri"]
    assert acquisition["rights_state"] == "permitted"
    assert transformation.input_content_id == acquisition["content_id"]
    assert transformation.output.sha256 == landing.table.parquet_digest

    first = admit_bronze_landing(landing, decided_at=NOW)
    second = admit_bronze_landing(
        landing,
        actor="maintainer:review",
        decided_at=NOW + timedelta(minutes=1),
        supersedes_decision_id=first.decision_id,
    )
    assert first.path != second.path
    assert first.path is not None
    assert first.path.is_file()
    assert second.path is not None
    assert second.path.is_file()
    assert second.supersedes_decision_id == first.decision_id
    admissions = tuple((tmp_path / "bronze" / "admissions").rglob("*.json"))
    assert len(admissions) == 4


@pytest.mark.edge
def test_transformation_and_admission_identities_reject_tampering(
    tmp_path: Path,
) -> None:
    landing = land_bronze_payload(
        PAYLOAD,
        _receipt_with_legacy_raw_output(),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
        transformation_completed_at=NOW,
    )
    run_payload = landing.transformation_run.model_dump(mode="json")
    run_payload["run_id"] = "f" * 64
    with pytest.raises(ValidationError, match="run_id does not bind"):
        TransformationRunReceipt.model_validate(run_payload)

    decision = admit_bronze_landing(landing, decided_at=NOW)
    decision_payload = decision.model_dump(mode="json")
    decision_payload["decision_id"] = "f" * 64
    with pytest.raises(ValidationError, match="decision_id does not bind"):
        type(decision).model_validate(decision_payload)
    decision_payload["supersedes_decision_id"] = "f" * 64
    with pytest.raises(ValidationError, match="cannot supersede itself"):
        type(decision).model_validate(decision_payload)


@pytest.mark.edge
def test_append_only_run_and_admission_history_detect_corruption(
    tmp_path: Path,
) -> None:
    landing = land_bronze_payload(
        PAYLOAD,
        _receipt_with_legacy_raw_output(),
        bronze_root=tmp_path / "bronze",
        media_hint="json",
        transformation_completed_at=NOW,
    )
    run_path = landing.transformation_receipt_path
    run_path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="cannot be rewritten"):
        write_transformation_run_receipt(
            landing.transformation_run,
            bronze_root=tmp_path / "bronze",
            source_id=landing.receipt.source.source_id,
        )

    first = admit_bronze_landing(landing, decided_at=NOW)
    assert first.path is not None
    first.path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="cannot be rewritten"):
        admit_bronze_landing(landing, decided_at=NOW)
    with pytest.raises(ValueError, match="does not exist"):
        admit_bronze_landing(
            landing,
            decided_at=NOW + timedelta(minutes=1),
            supersedes_decision_id="e" * 64,
        )


@pytest.mark.unit
def test_transformation_environment_fallback_and_ci_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parquet = tmp_path / "output.parquet"
    parquet.write_bytes(b"parquet")
    monkeypatch.setattr(transformation_module, "ROOT", tmp_path)
    monkeypatch.setenv("GITHUB_SHA", "A" * 40)
    run = receipt_for_parquet(
        parquet,
        acquisition_id="a" * 64,
        input_content_id="b" * 64,
        completed_at=NOW,
    )
    assert run.code_commit == "a" * 40
    assert run.environment_identity == "python-runtime"


@pytest.mark.edge
def test_transformation_requires_git_without_ci_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parquet = tmp_path / "output.parquet"
    parquet.write_bytes(b"parquet")
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.setattr(transformation_module.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="git is required"):
        receipt_for_parquet(
            parquet,
            acquisition_id="a" * 64,
            input_content_id="b" * 64,
            completed_at=NOW,
        )
