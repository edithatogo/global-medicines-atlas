"""Metadata-only triage never turns filenames into privacy decisions."""

from __future__ import annotations

import copy
from typing import Any

import pytest
import scripts.qualify_pbs_member_privacy_triage as qualification


@pytest.fixture(scope="module")
def evidence() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root = qualification.ROOT
    return (
        qualification.bounded.read_bound_metadata(
            root, *qualification.context.INPUTS["privacy"]
        ),
        qualification.bounded.read_bound_metadata(
            root, *qualification.context.INPUTS["api"]
        ),
        qualification.bounded.read_bound_metadata(root, *qualification.CONTEXT),
    )


def test_all_members_and_objects_remain_unassessed() -> None:
    result = qualification.build()
    inventory = result["unassessed_inventory"]
    assert inventory["objects"] == 1722
    assert inventory["distinct_digest_and_size_pairs"] == 1721
    assert inventory["paths_in_duplicate_group"] == 2
    assert inventory["privacy_clearances"] == 0
    archive = result["september_2025_archive"]
    assert len(archive["members"]) == 33
    assert archive["members_with_review_labels"] == 8
    assert all(
        row["privacy"] == qualification.context.UNKNOWN
        for row in archive["members"]
    )
    assert all(
        row["member_digest_available"] is False for row in archive["members"]
    )
    assert any(not row["filename_review_labels"] for row in archive["members"])
    assert not any(result["boundaries"].values())


@pytest.mark.parametrize(
    "mutation",
    ["object_clearance", "wrong_archive", "member_removed", "read_gate"],
)
def test_wrong_identity_or_unsafe_privacy_change_fails_closed(
    evidence: tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
    mutation: str,
) -> None:
    privacy, api, previous = copy.deepcopy(evidence)
    if mutation == "object_clearance":
        row = next(
            r
            for r in privacy["objects"]
            if r["sha256"] == qualification.context.SCHEDULE_CSV_SHA
        )
        row["privacy"] = "cleared"
    elif mutation == "wrong_archive":
        api["pbs_schedule_api"]["sha256"] = "0" * 64
    elif mutation == "member_removed":
        api["pbs_schedule_api"]["members"].pop()
    else:
        previous["boundaries"]["unassessed_payload_reads_authorized"] = True
    with pytest.raises(
        ValueError, match="PBS member or privacy inventory differs"
    ):
        qualification.reconcile(privacy, api, previous)
