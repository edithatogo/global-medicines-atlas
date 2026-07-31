"""Aggregate stable-v1 reproduction, migration, and recovery rehearsal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from global_medicines_atlas import stable_v1_rehearsal
from global_medicines_atlas.stable_v1_rehearsal import (
    StableV1RehearsalError,
    run_stable_v1_rehearsal,
    verify_receipt_content,
)

ROOT = Path(__file__).resolve().parents[1]
AGGREGATE_SCHEMA = (
    ROOT / "schemas" / "stable_v1_aggregate_rehearsal.schema.json"
)


def test_stable_v1_rehearsal_is_deterministic_and_honest(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"

    first = run_stable_v1_rehearsal(first_path)
    second = run_stable_v1_rehearsal(second_path)

    assert first == second
    assert first.schema_version == 2
    assert first.passed
    assert first.clean_room.boundary == "independent_local_fixture_process"
    assert first.clean_room.artifact_only_release_reproduction is False
    assert first.canonical.regulatory_funding_separation_verified
    assert first.canonical.rollback_exact
    assert first.recovery.production_disaster_recovery_qualified is False
    assert first.external_publication_verified is False
    assert set(first.fixture_sha256) == {
        "canonical_v1_fixture",
        "structural_projection_fixture",
    }
    assert {
        "schemas/canonical-medicine-v2.json",
        "schemas/stable-v1-rehearsal-v1.json",
        "schemas/stable_v1_aggregate_rehearsal.schema.json",
        "scripts/rehearse_stable_v1.py",
        "src/global_medicines_atlas/stable_v1_rehearsal.py",
        "uv.lock",
    }.issubset(first.input_sha256)
    assert first.qualification_input_tree_sha256
    assert verify_receipt_content(first)
    assert first_path.read_bytes() == second_path.read_bytes()
    assert json.loads(first_path.read_text(encoding="utf-8"))["passed"]
    Draft202012Validator(
        json.loads(AGGREGATE_SCHEMA.read_text(encoding="utf-8"))
    ).validate(first.model_dump(mode="json"))


def test_rehearsal_receipt_detects_tampering(tmp_path: Path) -> None:
    receipt = run_stable_v1_rehearsal(tmp_path / "receipt.json")
    tampered = receipt.model_copy(
        update={
            "canonical": receipt.canonical.model_copy(
                update={"rollback_exact": False}
            )
        }
    )

    assert not verify_receipt_content(tampered)


@pytest.mark.parametrize(
    "relative_path",
    [
        "uv.lock",
        "schemas/stable_v1_aggregate_rehearsal.schema.json",
        "src/global_medicines_atlas/stable_v1_rehearsal.py",
    ],
)
def test_rehearsal_receipt_revalidates_current_bound_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
) -> None:
    receipt = run_stable_v1_rehearsal(tmp_path / "receipt.json")
    current = dict(receipt.input_sha256)
    current[relative_path] = "f" * 64
    monkeypatch.setattr(
        stable_v1_rehearsal, "_input_identities", lambda: current
    )

    assert not verify_receipt_content(receipt)


def test_rehearsal_receipt_rejects_resigned_tree_identity_mismatch(
    tmp_path: Path,
) -> None:
    receipt = run_stable_v1_rehearsal(tmp_path / "receipt.json")
    tampered = receipt.model_copy(
        update={"qualification_input_tree_sha256": "f" * 64}
    )
    tampered = tampered.model_copy(
        update={
            "content_sha256": stable_v1_rehearsal._receipt_digest(
                tampered.model_dump(mode="json")
            )
        }
    )

    assert not verify_receipt_content(tampered)


def test_rehearsal_receipt_revalidates_fixture_identities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = run_stable_v1_rehearsal(tmp_path / "receipt.json")
    monkeypatch.setattr(
        stable_v1_rehearsal,
        "_fixture_identities",
        lambda: {
            "canonical_v1_fixture": "e" * 64,
            "structural_projection_fixture": "d" * 64,
        },
    )

    assert not verify_receipt_content(receipt)


def test_rehearsal_fails_closed_on_child_identity_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "global_medicines_atlas.stable_v1_rehearsal._run_clean_process",
        lambda: {
            "canonical_v1_sha256": "0" * 64,
            "canonical_v2_sha256": "1" * 64,
        },
    )

    with pytest.raises(
        StableV1RehearsalError, match="clean-process reproduction"
    ):
        run_stable_v1_rehearsal(tmp_path / "receipt.json")

    assert not (tmp_path / "receipt.json").exists()


@pytest.mark.parametrize(
    ("returncode", "stdout", "message"),
    [
        (1, "", "clean-process reproduction failed"),
        (0, "{", "returned invalid JSON"),
        (0, "[]", "invalid identity set"),
        (0, '{"wrong":"identity"}', "invalid identity set"),
        (
            0,
            '{"canonical_v1_sha256":1,"canonical_v2_sha256":"x"}',
            "invalid identities",
        ),
    ],
)
def test_clean_process_receipt_parser_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
    stdout: str,
    message: str,
) -> None:
    completed = stable_v1_rehearsal.subprocess.CompletedProcess(
        args=["python"], returncode=returncode, stdout=stdout, stderr=""
    )

    def fake_run(*_args: object, **_kwargs: object) -> object:
        return completed

    monkeypatch.setattr(
        stable_v1_rehearsal.subprocess,
        "run",
        fake_run,
    )

    with pytest.raises(StableV1RehearsalError, match=message):
        stable_v1_rehearsal._run_clean_process()
