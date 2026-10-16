"""Cross-check current manifest membership against the frozen M-112 ledger."""

import hashlib
import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
ADDENDUM = (
    ROOT
    / "quality/qualifications/australian-m112-root-manifest-path-readback-20261017.json"
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
    assert addendum["scope"]["approved_denominator"] == 1759
    assert addendum["scope"]["denominator_changed"] is False
    assert addendum["scope"]["m112_accepted"] is False
    assert addendum["root_manifest"]["dataset_revision"] == (
        "3d2d528439bddf6f42e8e700c88917f0960a9f38"
    )
    assert addendum["root_manifest"]["manifest_sha256"] == (
        "7afe928933fece384f8459dd268fcd2c4f26c8325dc52577f7a1582e8d63a0ac"
    )
    assert addendum["root_manifest"]["file_count"] == 28
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


def test_addendum_binds_local_source_digests() -> None:
    addendum = _read(ADDENDUM)
    inputs = cast("list[dict[str, str]]", addendum["inputs"])
    assert inputs
    for item in inputs:
        path = ROOT / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
