"""Mojo v0.8 non-promotion qualification."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from global_medicines_atlas.mojo_qualification import MojoQualification

RECEIPT = Path("quality/qualifications/mojo-v08.json")


def test_committed_mojo_receipt_denies_unsupported_promotion() -> None:
    qualification = MojoQualification.model_validate_json(
        RECEIPT.read_text(encoding="utf-8")
    )
    assert qualification.authoritative_engine == "python-3.14"
    assert qualification.mojo_disposition == "experimental_not_promoted"
    assert qualification.promotion == "denied"
    assert not qualification.real_kernel_present


def test_mojo_promotion_requires_every_adr_gate() -> None:
    document = MojoQualification.model_validate_json(
        RECEIPT.read_text(encoding="utf-8")
    ).model_dump(mode="json")
    unsupported = deepcopy(document)
    unsupported["promotion"] = "approved"
    with pytest.raises(ValidationError, match="every ADR 0003 gate"):
        MojoQualification.model_validate(unsupported)


def test_fully_qualified_future_kernel_can_be_promoted() -> None:
    document = MojoQualification.model_validate_json(
        RECEIPT.read_text(encoding="utf-8")
    ).model_dump(mode="json")
    document.update({
        "real_kernel_present": True,
        "arrow_fixture_parity": "passed",
        "fallback_rehearsal": "passed",
        "representative_benchmark": "passed",
        "scalene_justifies_promotion": True,
        "promotion": "approved",
    })
    assert MojoQualification.model_validate(document).promotion == "approved"
