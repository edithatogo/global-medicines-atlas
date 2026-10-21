"""Cross-check current manifest membership against the frozen M-112 ledger."""

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
ADDENDUM = (
    ROOT
    / "quality/qualifications/australian-m112-root-manifest-path-readback-20261021.json"
)
BASE = (
    ROOT
    / "quality/qualifications/australian-m112-per-object-gate-reconciliation-20261005.json"
)


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_two_august_mbs_paths_are_reconciled_without_promoting_other_gates() -> (
    None
):
    addendum = _read(ADDENDUM)
    base = _read(BASE)
    m108 = _read(
        ROOT
        / "quality/qualifications/australian-m108-derived-products-20261017.json"
    )
    latest = m108["latest_mbs_archive_append_readback"]
    assert addendum["scope"]["approved_denominator"] == 1759
    assert addendum["scope"]["denominator_changed"] is False
    assert addendum["scope"]["m112_accepted"] is False
    assert addendum["root_manifest"]["dataset_revision"] == latest["revision"]
    assert (
        addendum["root_manifest"]["manifest_sha256"]
        == latest["root_manifest_sha256"]
    )
    assert (
        addendum["root_manifest"]["file_count"]
        == latest["root_manifest_object_count"]
    )
    assert addendum["root_manifest"]["manifest_byte_count"] == 59818
    assert (
        addendum["current_head_reconciliation"][
            "root_object_count_matches_latest_append_receipt"
        ]
        is True
    )
    paths = {row["path"]: row for row in addendum["objects"]}
    assert len(paths) == 2
    base_rows = {
        row["path"]: row for row in base["objects"] if row["path"] in paths
    }
    assert set(paths) == set(base_rows)
    for path, row in paths.items():
        old = base_rows[path]
        assert row["manifest_row"] == {
            "path": path,
            "bytes": old["identity"]["byte_count"],
            "sha256": old["identity"]["sha256"]
            or "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565",
            "kind": "raw_payload",
            "source_id": "au-mbs",
            "category": "monthly_schedule_xml",
        }
        assert row["preserved_git_blob_oid"] == old["identity"]["git_blob_oid"]
        assert (
            row["prior_anonymous_digest_readback"]
            is old["identity"]["anonymous_digest_readback"]
        )
        assert row["current_root_manifest_membership"] is True
        assert row["rights_decision"] == old["rights"]["decision_evidence"]
        assert row["b1_b2_lineage_complete"] is old["b1_b2_lineage"]["complete"]
        assert row["v4_admission"] is old["v4_admission"]
        assert row["consumer_canary"] is old["consumer_canary"]
        assert row["disposition"] == old["disposition"]


def test_addendum_binds_exact_historical_source_digests() -> None:
    addendum = _read(ADDENDUM)
    inputs = cast("list[dict[str, str]]", addendum["inputs"])
    assert inputs
    bindings = _read(
        ROOT
        / "quality/qualifications/australian-m112-root-manifest-historical-input-bindings-20261022.json"
    )
    assert (
        bindings["historical_readback"]["sha256"]
        == hashlib.sha256(ADDENDUM.read_bytes()).hexdigest()
    )
    assert bindings["historical_evidence_rewritten"] is False
    assert bindings["snapshot_is_executable_workflow"] is False
    retained = {row["path"]: row for row in bindings["retained_inputs"]}
    assert set(retained) == {
        ".github/workflows/australian-mbs-root-manifest-append.yml"
    }
    for item in inputs:
        replacement = retained.get(item["path"])
        path = ROOT / (
            replacement["retained_path"] if replacement else item["path"]
        )
        if replacement:
            assert replacement["sha256"] == item["sha256"]
            assert path.suffix == ".txt"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
