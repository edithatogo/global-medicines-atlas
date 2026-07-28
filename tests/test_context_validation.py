"""Repository context and traceability tests."""

from __future__ import annotations

from scripts.validate_context import validate_context


def test_context_manifest_resolves_repository_truth() -> None:
    receipt = validate_context()

    assert receipt["status"] == "pass"
    assert receipt["tracks"] >= 2
    assert receipt["requirements"] >= 30
    assert receipt["harness_profiles"] >= 14
    assert receipt["human_gates"] >= 6
    assert receipt["releases"] == 10
