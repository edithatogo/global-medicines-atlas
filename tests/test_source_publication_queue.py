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
        "satisfied_exact_manifest_maintainer_approval"
    )
    assert queue["public_eligible_count"] == 25
    assert queue["published_count"] == 25
    assert queue["acquisition_evidenced_count"] == 25
    assert queue["acquisition_pending_count"] == 0
    assert queue["temporarily_unavailable_count"] == 1


def test_published_sources_bind_exact_publication_receipts() -> None:
    entries = cast("list[dict[str, Any]]", _queue()["entries"])
    evidenced = [
        entry for entry in entries if entry["acquisition_state"] == "evidenced"
    ]
    assert len(evidenced) == 25
    assert all(entry["acquisition_evidence"] for entry in evidenced)
    assert all(
        entry["next_action"] == "monitor_public_revision"
        for entry in evidenced
    )
    assert all(entry["publication_state"] == "published" for entry in evidenced)


def test_open_medic_retains_failure_receipt() -> None:
    entries = {
        entry["source_id"]: entry
        for entry in cast("list[dict[str, Any]]", _queue()["entries"])
    }
    open_medic = entries["fr-open-medic"]
    assert open_medic["acquisition_state"] == "temporarily_unavailable"
    assert open_medic["next_action"] == "retry_source_acquisition"
    assert open_medic["acquisition_evidence"].endswith(
        "open-medic-acquisition-failure-20260821.json"
    )


def test_rxnorm_is_derived_only_and_source_vocabulary_bytes_stay_blocked() -> (
    None
):
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
