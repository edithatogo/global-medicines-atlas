"""End-to-end qualification contracts for the stable-v1 candidate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.product_contracts import (
    ComparisonValidityOutcome,
)
from global_medicines_atlas.stable_v1_e2e_qualification import (
    QualificationReceipt,
    build_stable_v1_e2e_receipt,
    write_stable_v1_e2e_receipt,
)


@pytest.fixture(scope="module")
def receipt() -> QualificationReceipt:
    return build_stable_v1_e2e_receipt()


def test_all_comparison_validity_outcomes_are_qualified(
    receipt: QualificationReceipt,
) -> None:
    outcomes = {item.name: item.outcome for item in receipt.body.controls}

    assert outcomes == {
        "aligned": ComparisonValidityOutcome.VALID,
        "compatible": ComparisonValidityOutcome.VALID_WITH_CAVEATS,
        "mismatch": ComparisonValidityOutcome.INAPPROPRIATE_COMPARISON,
        "unknown": ComparisonValidityOutcome.INSUFFICIENT_EVIDENCE,
    }
    assert next(
        item for item in receipt.body.controls if item.name == "unknown"
    ).abstained


def test_every_control_denies_unsafe_clinical_claims(
    receipt: QualificationReceipt,
) -> None:
    for control in receipt.body.controls:
        assert control.safety_claims.model_dump() == {
            "establishes_medicine_equivalence": False,
            "establishes_substitutability": False,
            "establishes_therapeutic_interchangeability": False,
            "establishes_equal_benefit": False,
        }


def test_all_public_surfaces_cover_every_required_capability(
    receipt: QualificationReceipt,
) -> None:
    assert {
        (item.surface, item.capability) for item in receipt.body.surfaces
    } == {
        (surface, capability)
        for surface in ("api", "cli", "atlas")
        for capability in (
            "comparison_validity",
            "concept_search",
            "concept_detail",
            "jurisdictions",
            "sources",
        )
    }


def test_receipt_is_deterministic_and_canonical(tmp_path: Path) -> None:
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"

    first = write_stable_v1_e2e_receipt(first_path)
    second = write_stable_v1_e2e_receipt(second_path)

    assert first == second
    assert first_path.read_bytes() == second_path.read_bytes()
    assert (
        QualificationReceipt.model_validate_json(
            first_path.read_text(encoding="utf-8")
        )
        == first
    )
    assert first_path.read_bytes().endswith(b"\n")


def test_receipt_rejects_tampering(receipt: QualificationReceipt) -> None:
    payload = receipt.model_dump(mode="json")
    payload["body"]["external_actions_performed"] = True

    with pytest.raises(ValidationError):
        QualificationReceipt.model_validate(payload)

    digest_tampering = json.loads(receipt.model_dump_json())
    digest_tampering["body"]["fixture_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="receipt digest"):
        QualificationReceipt.model_validate(digest_tampering)


def test_receipt_records_no_external_actions(
    receipt: QualificationReceipt,
) -> None:
    assert receipt.body.unknown_evidence_abstains
    assert receipt.body.regulatory_and_funding_remain_separate
    assert receipt.body.external_actions_performed is False
