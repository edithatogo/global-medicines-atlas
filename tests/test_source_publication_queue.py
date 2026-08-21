"""Rights-aware acquisition and publication queue contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from scripts.build_source_publication_queue import build

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "quality/qualifications/source-publication-queue.json"


def _queue() -> dict[str, Any]:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def test_queue_is_deterministic_and_separates_rights_from_acquisition() -> None:
    queue = _queue()
    assert queue == build()
    assert queue["candidate_count"] == 26
    assert queue["publication_gate"] == (
        "pending_exact_manifest_maintainer_approval"
    )
    assert queue["public_eligible_count"] == 0
    assert queue["acquisition_evidenced_count"] == 14
    assert queue["acquisition_pending_count"] == 12


def test_evidenced_sources_still_require_exact_manifest_review() -> None:
    entries = cast("list[dict[str, Any]]", _queue()["entries"])
    evidenced = [
        entry for entry in entries if entry["acquisition_state"] == "evidenced"
    ]
    assert len(evidenced) == 14
    assert all(entry["acquisition_evidence"] for entry in evidenced)
    assert all(
        entry["next_action"] == "prepare_exact_manifest_for_human_review"
        for entry in evidenced
    )


def test_rxnorm_is_derived_only_and_source_vocabulary_bytes_stay_blocked() -> None:
    entries = {
        entry["source_id"]: entry
        for entry in cast("list[dict[str, Any]]", _queue()["entries"])
    }
    assert entries["global-rxnorm"]["candidate_packaging_shape"] == (
        "derived_projection_only"
    )
    assert entries["us-rxnorm-api"]["candidate_packaging_shape"] == (
        "derived_projection_only"
    )
