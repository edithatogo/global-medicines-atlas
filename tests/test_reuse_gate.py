"""Pre-acquisition reuse gate contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest

from global_medicines_atlas.reuse_gate import (
    HF_CATALOGUE_REPOSITORY,
    HF_CATALOGUE_REVISION,
    SEARCH_SURFACES,
    AcquireNewNotLastResortError,
    ReuseCandidate,
    ReuseCandidateKind,
    ReuseDisposition,
    ReuseGateDecision,
    ReuseGateRequiredError,
    acquire_new_decision,
    choose_disposition,
    evaluate_reuse_gate,
    load_ecosystem_document,
    require_reuse_decision,
    search_local_clones,
)

ROOT = Path(__file__).resolve().parents[1]


def _candidate(
    surface: Literal[
        "local_clones", "github", "hugging_face", "source_registry"
    ],
    kind: ReuseCandidateKind,
    locator: str = "https://example.test/copy",
) -> ReuseCandidate:
    return ReuseCandidate(
        surface=surface,
        locator=locator,
        source_id="us-drugsfda",
        kind=kind,
    )


@pytest.mark.unit
def test_all_dispositions_are_representable() -> None:
    for disposition in ReuseDisposition:
        decision = ReuseGateDecision(
            source_id="us-drugsfda",
            disposition=disposition,
            searched_surfaces=SEARCH_SURFACES,
            candidates=(),
            rationale=f"explicit {disposition.value}",
        )
        assert decision.disposition is disposition
        assert decision.disposition.value in {
            "reuse",
            "link",
            "mirror",
            "extend",
            "fork",
            "acquire-new",
        }


@pytest.mark.unit
def test_acquire_new_is_last_resort_when_payload_exists() -> None:
    candidates = (
        _candidate("local_clones", ReuseCandidateKind.PAYLOAD, "/var/clone"),
    )
    assert choose_disposition(candidates) is ReuseDisposition.REUSE
    with pytest.raises(AcquireNewNotLastResortError):
        choose_disposition(
            candidates,
            requested=ReuseDisposition.ACQUIRE_NEW,
        )


@pytest.mark.unit
def test_gate_searches_required_surfaces_and_pins_catalogue() -> None:
    decision = evaluate_reuse_gate(
        "us-drugsfda",
        repository_root=ROOT,
        huggingface_index={
            HF_CATALOGUE_REPOSITORY: ("inventory/us-drugsfda.parquet",)
        },
    )

    assert decision.searched_surfaces == SEARCH_SURFACES
    assert decision.catalogue_revision == HF_CATALOGUE_REVISION
    assert {item.surface for item in decision.candidates} >= {
        "local_clones",
        "hugging_face",
        "source_registry",
    }
    assert decision.disposition is not ReuseDisposition.ACQUIRE_NEW
    assert HF_CATALOGUE_REVISION in " ".join(
        item.locator for item in decision.candidates
    )
    assert {
        item.revision
        for item in decision.candidates
        if item.surface == "hugging_face"
    } == {HF_CATALOGUE_REVISION}


@pytest.mark.unit
def test_missing_gate_and_incomplete_search_fail() -> None:
    with pytest.raises(ReuseGateRequiredError):
        require_reuse_decision(None, "us-drugsfda")
    allowed = acquire_new_decision("us-drugsfda")
    assert require_reuse_decision(allowed, "us-drugsfda") is allowed
    incomplete = acquire_new_decision("us-drugsfda").model_copy(
        update={"searched_surfaces": ("local_clones",)}
    )
    with pytest.raises(ReuseGateRequiredError, match="must search"):
        require_reuse_decision(incomplete, "us-drugsfda")


@pytest.mark.unit
def test_disposition_priority_order() -> None:
    assert (
        choose_disposition((
            _candidate("hugging_face", ReuseCandidateKind.PAYLOAD),
        ))
        is ReuseDisposition.LINK
    )
    assert (
        choose_disposition((_candidate("github", ReuseCandidateKind.PAYLOAD),))
        is ReuseDisposition.MIRROR
    )
    assert (
        choose_disposition((_candidate("github", ReuseCandidateKind.SCHEMA),))
        is ReuseDisposition.EXTEND
    )
    assert (
        choose_disposition((_candidate("github", ReuseCandidateKind.RELATED),))
        is ReuseDisposition.FORK
    )
    assert choose_disposition(()) is ReuseDisposition.ACQUIRE_NEW
    assert (
        choose_disposition(
            (_candidate("local_clones", ReuseCandidateKind.PAYLOAD),),
            requested=ReuseDisposition.LINK,
        )
        is ReuseDisposition.LINK
    )


@pytest.mark.unit
def test_gate_rejects_empty_id_mismatch_and_acquire_new_with_payload() -> None:
    with pytest.raises(ValueError, match="source_id is required"):
        evaluate_reuse_gate("  ", repository_root=ROOT)
    with pytest.raises(ReuseGateRequiredError, match="does not match"):
        require_reuse_decision(
            acquire_new_decision("us-drugsfda"),
            "eu-ema-json",
        )
    blocked = acquire_new_decision("us-drugsfda").model_copy(
        update={
            "candidates": (
                _candidate("local_clones", ReuseCandidateKind.PAYLOAD),
            )
        }
    )
    with pytest.raises(AcquireNewNotLastResortError):
        require_reuse_decision(blocked, "us-drugsfda")


@pytest.mark.unit
def test_ecosystem_policy_and_sibling_clone_search(tmp_path: Path) -> None:
    bad_root = tmp_path / "bad"
    (bad_root / ".context").mkdir(parents=True)
    (bad_root / ".context" / "ecosystem.toml").write_text(
        'policy = "build-first"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="reuse-before-build"):
        load_ecosystem_document(bad_root)

    root = tmp_path / "global-medicines-atlas"
    sibling = tmp_path / "nzmedicines"
    (root / ".context").mkdir(parents=True)
    sibling.mkdir()
    (root / "vendor" / "nzmedicines").mkdir(parents=True)
    (root / ".context" / "ecosystem.toml").write_text(
        'policy = "reuse-before-build"\n\n'
        "[[github]]\n"
        'id = "nzmedicines"\n'
        'repository = "edithatogo/nzmedicines"\n'
        'local_boundary = "vendor/nzmedicines"\n',
        encoding="utf-8",
    )
    hits = search_local_clones(
        "nzmedicines",
        repository_root=root,
        ecosystem=load_ecosystem_document(root),
    )
    locators = {Path(item.locator) for item in hits}
    assert sibling in locators
    assert root / "vendor" / "nzmedicines" in locators
