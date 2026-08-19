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
    require_reuse_decision,
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


@pytest.mark.unit
def test_missing_gate_and_incomplete_search_fail() -> None:
    with pytest.raises(ReuseGateRequiredError):
        require_reuse_decision(None, "us-drugsfda")
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
