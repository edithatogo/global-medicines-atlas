from pathlib import Path

import pytest
from pydantic import ValidationError
from scripts.run_product_qualification import run

from global_medicines_atlas.product_release import ThreatCase, VerificationState


def test_threat_without_receipt_remains_unverified():
    case = ThreatCase(
        threat_id="THREAT-001",
        description="Oversized request",
        control="Contract bounds",
        verification=VerificationState.NOT_VERIFIED,
        reason="no durable control-test receipt was supplied",
    )
    assert case.verification is VerificationState.NOT_VERIFIED
    assert case.receipt_id is None


def test_threat_identifiers_are_governed():
    with pytest.raises(ValidationError):
        ThreatCase(
            threat_id="SQLI",
            description="Injection",
            control="Parameterized SQL",
            verification=VerificationState.NOT_VERIFIED,
            reason="not executed",
        )


def test_runner_executes_every_governed_abuse_control(tmp_path: Path):
    run(tmp_path / "evidence.json", tmp_path / "receipts")
    assert {
        item.stem for item in (tmp_path / "receipts").glob("THREAT-*.json")
    } == {
        "THREAT-001",
        "THREAT-002",
        "THREAT-003",
        "THREAT-004",
        "THREAT-005",
    }
