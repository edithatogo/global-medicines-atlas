"""Contract checks for the current path-by-path M-112 reconciliation."""

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = (
    ROOT
    / "quality/qualifications/australian-m112-per-object-gate-reconciliation-20261005.json"
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_reconciliation_covers_approved_denominator_and_preserves_deferrals() -> (
    None
):
    report = _load(REPORT_PATH)
    inventory = _load(
        ROOT
        / "quality/qualifications/australian-m112-current-tree-object-inventory-20261004.json"
    )
    expected = {
        (row["dataset"], row["path"]) for row in inventory["observations"]
    }
    objects = report["objects"]
    observed = {(row["dataset"], row["path"]) for row in objects}

    assert report["scope"]["approved_denominator"] == 1759
    assert report["scope"]["reconciled_paths"] == 1759
    assert report["scope"]["denominator_changed"] is False
    assert report["scope"]["preserved_deferrals"] == 1759
    assert observed == expected
    assert len(observed) == len(objects)
    assert all(row["approved_denominator_member"] for row in objects)
    assert all(row["disposition"] == "deferred_not_admitted" for row in objects)


def test_gate_results_do_not_promote_metadata_or_rights_to_admission() -> None:
    report = _load(REPORT_PATH)
    objects = report["objects"]

    assert all(row["identity"]["git_blob_and_size_match"] for row in objects)
    assert (
        sum(row["identity"]["anonymous_digest_readback"] for row in objects)
        == 28
    )
    rights_qualified = [
        row
        for row in objects
        if row["rights"]["state"].startswith("approved_exact_scope")
    ]
    assert len(rights_qualified) == 14
    assert all(not row["b1_b2_lineage"]["complete"] for row in objects)
    assert all(not row["v4_admission"] for row in objects)
    assert all(not row["consumer_canary"] for row in objects)
    assert report["aggregate_gates"]["paths_with_complete_b1_b2_lineage"] == 0
    assert report["aggregate_gates"]["paths_admitted_to_v4"] == 0


def test_report_input_digests_match_current_evidence() -> None:
    report = _load(REPORT_PATH)
    references: dict[str, str] = {}

    def collect_references(value: Any) -> None:
        if isinstance(value, dict):
            node = cast("dict[str, Any]", value)
            path = node.get("path")
            sha256 = node.get("sha256")
            if isinstance(path, str) and isinstance(sha256, str):
                references[path] = sha256
            else:
                for nested in node.values():
                    collect_references(nested)
        elif isinstance(value, list):
            for nested in cast("list[Any]", value):
                collect_references(nested)

    collect_references(report)
    assert {source["path"] for source in report["inputs"]} <= references.keys()
    for source, expected_sha256 in references.items():
        path = ROOT / source
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256
