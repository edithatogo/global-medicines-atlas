"""Pinned discovery snapshot contracts for the reuse gate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from global_medicines_atlas.reuse_gate import (
    AcquireNewNotLastResortError,
    DiscoverySurface,
    DiscoverySurfaceState,
    ReuseCandidate,
    ReuseCandidateKind,
    ReuseDiscoverySnapshot,
    ReuseDisposition,
    ReuseGateDecision,
    ReuseGateRequiredError,
    build_discovery_snapshot,
    read_discovery_snapshot,
    require_reuse_decision,
    write_discovery_snapshot,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 8, 22, 0, 0, tzinfo=UTC)


def _snapshot(**changes: object) -> ReuseDiscoverySnapshot:
    surfaces = tuple(
        DiscoverySurface(
            name=name,
            state=DiscoverySurfaceState.SUCCESS,
            query="source-x",
            candidates=(),
        )
        for name in (
            "local_clones",
            "github",
            "hugging_face",
            "source_registry",
        )
    )
    payload = {
        "source_id": "source-x",
        "generated_at": NOW,
        "freshness_seconds": 3600,
        "tool_version": "test/1",
        "surfaces": surfaces,
        **changes,
    }
    supplied = payload["surfaces"]
    if len(supplied) == 1:
        by_name = {surface.name: surface for surface in surfaces}
        by_name[supplied[0].name] = supplied[0]
        payload["surfaces"] = tuple(by_name.values())
    return ReuseDiscoverySnapshot.model_validate(payload)


def _decision(
    snapshot: ReuseDiscoverySnapshot, **changes: object
) -> ReuseGateDecision:
    values: dict[str, object] = {
        "source_id": "source-x",
        "disposition": ReuseDisposition.ACQUIRE_NEW,
        "searched_surfaces": (
            "local_clones",
            "github",
            "hugging_face",
            "source_registry",
        ),
        "candidates": (),
        "rationale": "fixture snapshot",
        "discovery_snapshot": snapshot,
    }
    values.update(changes)
    return ReuseGateDecision(
        **values,
    )


def test_snapshot_id_is_deterministic_and_pinned() -> None:
    first = _snapshot()
    second = _snapshot()
    assert first.snapshot_id == second.snapshot_id
    assert first.snapshot_id.startswith("sha256:")
    assert first.snapshot_id == first.recompute_snapshot_id()


def test_snapshot_records_candidate_query_revision_and_digest() -> None:
    candidate = ReuseCandidate(
        surface="github",
        locator="https://github.com/owner/repo",
        source_id="source-x",
        kind=ReuseCandidateKind.PAYLOAD,
        query="source-x",
        revision="abc123",
        digest="a" * 64,
    )
    snapshot = _snapshot(
        surfaces=(
            DiscoverySurface(
                name="github",
                state=DiscoverySurfaceState.SUCCESS,
                query="source-x",
                candidates=(candidate,),
            ),
        )
    )
    github = next(
        surface for surface in snapshot.surfaces if surface.name == "github"
    )
    assert github.candidates[0].revision == "abc123"


def test_stale_snapshot_fails_closed_for_acquire_new() -> None:
    stale = _snapshot(generated_at=NOW - timedelta(hours=2))
    with pytest.raises(ReuseGateRequiredError, match="stale"):
        require_reuse_decision(_decision(stale), "source-x", now=NOW)


def test_unavailable_or_skipped_surface_fails_closed() -> None:
    unavailable = _snapshot(
        surfaces=(
            DiscoverySurface(
                name="github",
                state=DiscoverySurfaceState.UNAVAILABLE,
                query="source-x",
                candidates=(),
                detail="offline",
            ),
        )
    )
    with pytest.raises(ReuseGateRequiredError, match="unavailable"):
        require_reuse_decision(_decision(unavailable), "source-x", now=NOW)

    skipped = _decision(None)  # type: ignore[arg-type]
    with pytest.raises(ReuseGateRequiredError, match="snapshot"):
        require_reuse_decision(skipped, "source-x", now=NOW)


def test_payload_candidate_blocks_acquire_new_even_with_snapshot() -> None:
    snapshot = _snapshot()
    candidate = ReuseCandidate(
        surface="local_clones",
        locator="fixture://source-x.bin",
        source_id="source-x",
        kind=ReuseCandidateKind.PAYLOAD,
    )
    decision = _decision(snapshot, candidates=(candidate,))
    with pytest.raises(AcquireNewNotLastResortError):
        require_reuse_decision(decision, "source-x", now=NOW)


def test_fixture_snapshot_rebuild_is_offline_and_deterministic(
    tmp_path: Path,
) -> None:
    snapshot = build_discovery_snapshot(
        "source-x",
        repository_root=tmp_path,
        generated_at=NOW,
        github_index={},
        huggingface_index={},
    )
    assert snapshot.snapshot_id == snapshot.recompute_snapshot_id()
    assert {surface.name for surface in snapshot.surfaces} == {
        "local_clones",
        "github",
        "hugging_face",
        "source_registry",
    }


def test_snapshot_validation_and_round_trip(tmp_path: Path) -> None:
    snapshot = _snapshot()
    path = tmp_path / "nested" / "snapshot.json"
    write_discovery_snapshot(snapshot, path)
    assert read_discovery_snapshot(path) == snapshot
    with pytest.raises(ValueError, match="source_id is required"):
        build_discovery_snapshot(" ", repository_root=tmp_path)
    with pytest.raises(ValueError, match="unique"):
        ReuseDiscoverySnapshot(
            source_id="source-x",
            generated_at=NOW,
            freshness_seconds=3600,
            tool_version="test/1",
            surfaces=(*snapshot.surfaces[:3], snapshot.surfaces[0]),
        )
    with pytest.raises(ValueError, match="expiry"):
        ReuseDiscoverySnapshot(**{
            **snapshot.model_dump(mode="json"),
            "expires_at": "2026-08-22T00:00:01Z",
            "snapshot_id": "",
        })
    with pytest.raises(ValueError, match="snapshot_id"):
        ReuseDiscoverySnapshot(**{
            **snapshot.model_dump(mode="json"),
            "snapshot_id": "sha256:" + "0" * 64,
        })
    mismatched = ReuseDiscoverySnapshot.model_validate({
        **snapshot.model_dump(mode="json"),
        "source_id": "other",
        "snapshot_id": "",
    })
    with pytest.raises(ReuseGateRequiredError, match="snapshot source_id"):
        require_reuse_decision(_decision(mismatched), "source-x", now=NOW)
