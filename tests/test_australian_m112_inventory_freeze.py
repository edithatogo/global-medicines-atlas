"""Verify M-112 denominator membership is pinned to the approved path set."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from scripts.freeze_australian_m112_inventory import (
    OUTPUT,
    build_report,
)


def test_inventory_freeze_matches_approved_and_current_path_membership() -> (
    None
):
    report = build_report()
    scope = report["scope"]
    members = report["members"]

    assert scope["membership_key"] == ["dataset", "path"]
    assert scope["approved_member_count"] == 1759
    assert scope["raw_source_payload_paths"] == 1736
    assert scope["existing_projection_paths"] == 23
    assert scope["producer_dataset_count"] == 5
    assert scope["same_membership_as_current_reconciliation"] is True
    assert scope["members_with_revision_advanced_since_approval"] == 18
    assert len({(row["dataset"], row["path"]) for row in members}) == 1759
    assert report["boundaries"]["source_payload_bytes_read"] is False
    assert (
        report["boundaries"]["source_admission_or_v4_admission_performed"]
        is False
    )


def test_inventory_freeze_binds_approval_and_membership_digest() -> None:
    report = build_report()
    approval = report["approval"]
    members = report["members"]
    canonical = "\n".join(
        json.dumps(
            [row["dataset"], row["path"]],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for row in members
    )

    assert (
        approval["kind"]
        == "australian_m112_exact_denominator_maintainer_approval"
    )
    assert approval["approved_inventory_sha256"] == (
        "ccc0667b1ce8ba19d4bed0a6590e2bc55ab954d7bd6cc51f56e51231cc780460"
    )
    assert (
        hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        == report["scope"]["path_membership_sha256"]
    )


def test_frozen_inventory_artifact_is_reproducible() -> None:
    report = build_report()
    observed: Any = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert observed == report
