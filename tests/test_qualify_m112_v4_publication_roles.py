"""Tests for unbound M-112 publication and anonymous-restore receipt evidence."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from scripts.qualify_m112_v4_publication_roles import (
    DIGEST_REPORT,
    ROLE_REPORT,
    qualify,
)


def test_exact_mbs_candidates_receive_unbound_publication_and_restore_evidence() -> (
    None
):
    report = qualify()
    candidates = [
        item
        for item in report["objects"]
        if item["dataset"] == "edithatogo/australian-mbs-utilisation-archive"
    ]

    assert len(candidates) == 14
    assert report["cohort"]["publication_candidate_receipts"] == 14
    assert report["cohort"]["verification_candidate_receipts"] == 14
    for candidate in candidates:
        assert candidate["contract_role_states"]["publication"] == (
            "candidate_receipt_available_unbound"
        )
        assert candidate["contract_role_states"]["verification"] == (
            "candidate_receipt_available_unbound"
        )
        assert (
            candidate["publication_candidate_receipt"]["manifest"][
                "exact_object_match"
            ]
            is True
        )
        verification = candidate["verification_candidate_receipt"]
        assert verification["anonymous"] is True
        assert verification["token_free"] is True
        assert verification["clean_room"] is True
        assert verification["temporary_source_bytes_removed"] is True


def test_refresh_preserves_the_denominator_and_zero_admissions_and_canaries() -> (
    None
):
    report = qualify()

    assert report["cohort"]["approved_denominator"] == 1759
    assert report["cohort"]["approved_denominator_changed"] is False
    assert report["cohort"]["v4_admissions"] == 0
    assert report["cohort"]["consumer_canaries"] == 0
    assert report["boundaries"]["v4_admission_performed"] is False
    assert report["boundaries"]["consumer_canary_performed"] is False


def test_missing_exact_manifest_match_fails_closed(tmp_path: Path) -> None:
    (tmp_path / ROLE_REPORT).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / DIGEST_REPORT).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / ROLE_REPORT, tmp_path / ROLE_REPORT)
    digest_path = tmp_path / DIGEST_REPORT
    shutil.copy(ROOT / DIGEST_REPORT, digest_path)
    digest_report = json.loads(digest_path.read_text(encoding="utf-8"))
    mbs = next(
        item
        for item in digest_report["verified_objects"]
        if item["dataset"] == "edithatogo/australian-mbs-utilisation-archive"
    )
    mbs["sha256"] = "0" * 64
    digest_path.write_text(json.dumps(digest_report), encoding="utf-8")

    with pytest.raises(ValueError, match="unique hosted manifest match"):
        qualify(tmp_path)


ROOT = Path(__file__).resolve().parents[1]
