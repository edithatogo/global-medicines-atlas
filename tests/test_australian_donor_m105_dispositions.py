"""Keep the M-105 disposition denominator exact without inferring parity."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = (
    ROOT / "quality/qualifications/australian-donor-m105-dispositions.json"
)
INVENTORY = (
    ROOT / "quality/qualifications/australian-health-donor-inventory.json"
)
DELTA = ROOT / "quality/qualifications/australian-donor-delta.json"
FINAL_DISPOSITIONS = {
    "adopt",
    "adapt",
    "replace-with-equivalent",
    "retain-legacy",
    "supersede",
    "exclude-with-reason",
}


def test_m105_dispositions_cover_exact_pinned_and_later_donors() -> None:
    receipt = json.loads(RECEIPT.read_text())
    inventory = json.loads(INVENTORY.read_text())
    delta = json.loads(DELTA.read_text())
    expected_baseline = {
        (
            repo["repository"],
            repo["commit"],
            item["path"],
            item["git_object_sha1"],
            item["sha256"],
        )
        for repo in inventory["denominator"]["repositories"]
        for item in repo["files"]
    }
    observed_baseline = [
        (
            item["repository"],
            item["commit"],
            item["path"],
            item["git_object_sha1"],
            item["sha256"],
        )
        for item in receipt["baseline"]
    ]
    assert len(observed_baseline) == len(expected_baseline)
    assert set(observed_baseline) == expected_baseline
    expected_delta = {
        (
            review["observation"]["repository"],
            review["observation"]["head"],
            item["path"],
            item["blob"],
        )
        for review in delta["reviews"]
        for item in review["observation"]["files"]
    }
    observed_delta = [
        (
            item["repository"],
            item["commit"],
            item["path"],
            item["git_object_sha1"],
        )
        for item in receipt["post_baseline_delta"]
    ]
    assert len(observed_delta) == len(expected_delta)
    assert set(observed_delta) == expected_delta
    assert all(
        item["disposition"] in FINAL_DISPOSITIONS
        for item in [*receipt["baseline"], *receipt["post_baseline_delta"]]
    )


def test_m105_dispositions_do_not_promote_unproven_behavior() -> None:
    receipt = json.loads(RECEIPT.read_text())
    assert receipt["qualification_state"] == "partial"
    assert (
        sum(
            item["acceptance_state"] == "pending_behavioral_parity"
            for item in receipt["baseline"]
        )
        == 11
    )
    assert (
        sum(
            item["acceptance_state"] == "pending_behavioral_parity"
            for item in receipt["post_baseline_delta"]
        )
        == 5
    )
