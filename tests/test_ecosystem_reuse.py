"""Maintainer-owned ecosystem reuse policy tests."""

from __future__ import annotations

from scripts.validate_ecosystem import validate_ecosystem


def test_ecosystem_registry_has_unique_authoritative_reuse_boundaries() -> None:
    receipt = validate_ecosystem()

    assert receipt["status"] == "pass"
    assert receipt["github_resources"] >= 7
    assert receipt["hugging_face_resources"] >= 3
    assert receipt["authorities"] == (
        receipt["github_resources"] + receipt["hugging_face_resources"]
    )
