"""Maintainer-owned ecosystem reuse policy tests."""

from __future__ import annotations

from pathlib import Path

from scripts.validate_ecosystem import validate_ecosystem

ROOT = Path(__file__).resolve().parents[1]


def test_ecosystem_registry_has_unique_authoritative_reuse_boundaries() -> None:
    receipt = validate_ecosystem()

    assert receipt["status"] == "pass"
    assert receipt["github_resources"] >= 7
    assert receipt["hugging_face_resources"] >= 3
    assert receipt["authorities"] == (
        receipt["github_resources"] + receipt["hugging_face_resources"]
    )


def test_australian_donors_and_legacy_hf_composite_have_transition_dispositions() -> (
    None
):
    registry = (ROOT / ".context/ecosystem.toml").read_text(encoding="utf-8")

    assert 'repository = "edithatogo/aus_mbs_pbs_graph"' in registry
    assert 'repository = "edithatogo/aus-health-data-scraper"' in registry
    assert (
        registry.count('disposition = "migrate-all-and-archive-after-parity"')
        == 2
    )
    assert (
        'repository = "edithatogo/global-medicines-atlas-international-open"'
        in registry
    )
    assert (
        'disposition = "publicize-after-hosted-exact-manifest-verification"'
        in registry
    )
