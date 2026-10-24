"""Targeted integrity tests for the retained PBS context enrichment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from global_medicines_atlas.pbs_uri_context_enrichment import (
    ContextEnrichmentError,
    enrich_uri_review_packet,
)

_ROOT = Path(__file__).parents[1]
_QUALIFICATIONS = _ROOT / "quality/qualifications"


def _load(name: str) -> tuple[dict[str, Any], str]:
    raw = (_QUALIFICATIONS / name).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _enriched(
    packet: dict[str, Any],
    packet_sha: str,
    screen: dict[str, Any],
    screen_sha: str,
    reconciliation: dict[str, Any],
) -> dict[str, Any]:
    return enrich_uri_review_packet(
        packet,
        screen,
        reconciliation,
        packet_file_sha256=packet_sha,
        screen_file_sha256=screen_sha,
    )


def test_exact_retained_context_is_bound_without_values_or_semantic_promotion():
    packet, packet_sha = _load(
        "pbs-native-reference-review-packet-20261025-40103169910.json"
    )
    screen, screen_sha = _load(
        "pbs-native-reference-screen-20261025-40103169910.json"
    )
    reconciliation, _ = _load(
        "pbs-native-reference-uri-review-reconciliation-20261025-40120162365.json"
    )

    report = _enriched(packet, packet_sha, screen, screen_sha, reconciliation)[
        "report"
    ]

    assert report["context_examples_bound"] == 46
    assert report["source_values_emitted"] is False
    assert report["semantic_relationships_qualified"] is False
    assert report["precision_claimed"] is False
    assert report["recall_claimed"] is False
    assert (
        sum(
            case["source_context"]["nearest_subject_element"] is not None
            for case in report["cases"]
        )
        == 8
    )
    assert (
        sum(
            case["source_context"]["nearest_identifier_element"] is not None
            for case in report["cases"]
        )
        == 38
    )
    assert (
        sum(
            case["source_context"]["same_member_literal_candidate_target_count"]
            for case in report["cases"]
        )
        == 35
    )


def test_context_enrichment_rejects_wrong_screen_receipt_digest():
    packet, packet_sha = _load(
        "pbs-native-reference-review-packet-20261025-40103169910.json"
    )
    screen, _screen_sha = _load(
        "pbs-native-reference-screen-20261025-40103169910.json"
    )
    reconciliation, _ = _load(
        "pbs-native-reference-uri-review-reconciliation-20261025-40120162365.json"
    )

    with pytest.raises(ContextEnrichmentError, match="receipt digests differ"):
        _enriched(packet, packet_sha, screen, "0" * 64, reconciliation)
