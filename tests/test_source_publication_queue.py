"""Rights-aware acquisition and publication queue contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from scripts.build_source_publication_queue import build

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "quality/qualifications/source-publication-queue.json"
DECISIONS = (
    ROOT / "src/global_medicines_atlas/data/source_rights_source_decisions.json"
)


def _queue() -> dict[str, Any]:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def test_queue_is_deterministic_and_separates_rights_from_acquisition() -> None:
    queue = _queue()
    assert queue == build()
    assert queue["candidate_count"] == 26
    assert queue["publication_gate"] == (
        "satisfied_exact_manifest_maintainer_approval"
    )
    assert queue["public_eligible_count"] == 24
    assert queue["published_count"] == 24
    assert queue["acquisition_evidenced_count"] == 24
    assert queue["acquisition_pending_count"] == 2
    assert queue["temporarily_unavailable_count"] == 0


def test_published_sources_bind_exact_publication_receipts() -> None:
    entries = cast("list[dict[str, Any]]", _queue()["entries"])
    evidenced = [
        entry for entry in entries if entry["acquisition_state"] == "evidenced"
    ]
    assert len(evidenced) == 24
    assert all(entry["acquisition_evidence"] for entry in evidenced)
    assert all(
        entry["next_action"] == "monitor_public_revision" for entry in evidenced
    )
    assert all(entry["publication_state"] == "published" for entry in evidenced)


def test_approved_manifests_match_publication_receipts() -> None:
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    receipts = {
        receipt["dataset"]: receipt
        for receipt in (
            json.loads(
                (
                    ROOT
                    / "quality/qualifications/fda-public-huggingface-20260821.json"
                ).read_text(encoding="utf-8")
            ),
            json.loads(
                (
                    ROOT
                    / "quality/qualifications/international-public-huggingface-20260821.json"
                ).read_text(encoding="utf-8")
            ),
        )
    }
    manifests = decisions["approved_publication_manifests"]
    assert {item["repository"] for item in manifests} == set(receipts)
    for manifest in manifests:
        receipt = receipts[manifest["repository"]]
        assert receipt["immutable_revision"] == manifest["revision"]
        assert receipt["manifest_sha256"] == manifest["manifest_sha256"]
        assert set(receipt["source_ids"]) == set(manifest["source_ids"])
        assert receipt["repository_private"] is False


def test_open_medic_supersedes_failure_with_publication_receipt() -> None:
    entries = {
        entry["source_id"]: entry
        for entry in cast("list[dict[str, Any]]", _queue()["entries"])
    }
    open_medic = entries["fr-open-medic"]
    assert open_medic["acquisition_state"] == "evidenced"
    assert open_medic["publication_state"] == "published"
    assert open_medic["next_action"] == "monitor_public_revision"
    assert open_medic["acquisition_evidence"].endswith(
        "international-public-huggingface-20260821.json"
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
