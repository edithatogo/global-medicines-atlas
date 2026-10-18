"""Contract checks for the current path-by-path M-112 reconciliation."""

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
import scripts.refresh_m112_august_release_crosswalk as crosswalk
from scripts.refresh_m112_august_release_crosswalk import (
    ALIAS_PATH,
    ALIAS_READBACK,
    AUTHORIZATION,
    BASELINE,
    DATASET,
    LIFECYCLE,
    OUTPUT,
    PBS_IDENTITIES,
    PBS_INDEX,
    PBS_READBACK,
    PBS_RIGHTS_LEDGER,
    RAW_PATH,
    ROOT_READBACK,
    SOURCE_DIGEST,
    SOURCE_RECEIPT,
    build_report,
)

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


def test_august_raw_crosswalk_reconciles_exact_denominator_and_gates() -> None:  # ruff: ignore[too-many-statements] -- explicit assertions are the gate contract
    report = _load(ROOT / OUTPUT)
    assert report == build_report()

    baseline = _load(ROOT / BASELINE)
    old_rows = {
        (row["dataset"], row["path"]): row for row in baseline["objects"]
    }
    rows = {
        row["path"]: row
        for row in report["objects"]
        if row["dataset"] == DATASET
    }
    assert report["scope"]["approved_denominator"] == 1759
    assert report["scope"]["reconciled_paths"] == 1759
    assert report["scope"]["denominator_changed"] is False
    assert report["scope"]["preserved_deferrals"] == 1759
    assert len(report["objects"]) == 1759
    assert len(rows) == sum(
        row["dataset"] == DATASET for row in report["objects"]
    )
    pbs_path = "raw/2026-04-01/2026-04-01-XML-V3.zip"
    pbs_row = next(
        row
        for row in report["objects"]
        if row["dataset"] == "edithatogo/australian-pbs-source-archive"
        and row["path"] == pbs_path
    )
    assert pbs_row["rights"]["receipt_claim_status"] == (
        "receipt_permitted_claim_source_ledger_unknown"
    )
    assert pbs_row["rights"]["decision_evidence"] is None
    assert pbs_row["rights"]["state"].startswith("unresolved:")
    assert pbs_row["b1_b2_lineage"]["complete"] is True
    assert pbs_row["identity"]["anonymous_digest_readback"] is True
    assert pbs_row["v4_admission"] is False
    assert pbs_row["consumer_canary"] is False
    assert pbs_row["disposition"] == "deferred_not_admitted"

    assert (
        rows[RAW_PATH]["rights"]["state"]
        == "authorized_exact_source_release_permitted"
    )
    assert (
        rows[ALIAS_PATH]["rights"]["state"]
        == "authorized_exact_source_release_permitted"
    )
    assert rows[RAW_PATH]["rights"]["evidence"]["path"] == SOURCE_RECEIPT
    assert (
        rows[RAW_PATH]["rights"]["decision_evidence"]["path"] == AUTHORIZATION
    )
    assert (
        rows[ALIAS_PATH]["rights"]["decision_evidence"]["path"] == AUTHORIZATION
    )

    assert rows[RAW_PATH]["identity"]["anonymous_digest_readback"] is True
    assert rows[RAW_PATH]["b1_b2_lineage"]["complete"] is True
    assert rows[ALIAS_PATH]["identity"]["anonymous_digest_readback"] is True
    assert rows[ALIAS_PATH]["identity"]["sha256"] == (
        "c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565"
    )
    assert rows[ALIAS_PATH]["identity"]["digest_evidence"]["path"] == (
        ALIAS_READBACK
    )
    assert rows[ALIAS_PATH]["b1_b2_lineage"]["complete"] is True
    assert (
        rows[ALIAS_PATH]["b1_b2_lineage"]["evidence"]["canonical_object"][
            "archive_path"
        ]
        == RAW_PATH
    )
    assert (
        rows[ALIAS_PATH]["b1_b2_lineage"]["evidence"][
            "alias_anonymous_readback"
        ]["path"]
        == ALIAS_READBACK
    )

    for path, row in rows.items():
        original = old_rows[DATASET, path]
        if path not in {RAW_PATH, ALIAS_PATH}:
            assert row == original
        else:
            assert (
                row["disposition"]
                == original["disposition"]
                == "deferred_not_admitted"
            )
            assert row["v4_admission"] is False
            assert row["consumer_canary"] is False
    pbs_original = next(
        row
        for row in old_rows.values()
        if row["dataset"] == "edithatogo/australian-pbs-source-archive"
        and row["path"] == pbs_path
    )
    assert pbs_row["disposition"] == pbs_original["disposition"]
    assert pbs_row["v4_admission"] == pbs_original["v4_admission"]
    assert pbs_row["consumer_canary"] == pbs_original["consumer_canary"]

    assert (
        report["aggregate_gates"][
            "paths_with_exact_scope_rights_decision_and_public_readback"
        ]
        == 14
    )
    assert (
        report["aggregate_gates"]["paths_with_exact_source_release_rights"] == 2
    )
    assert (
        report["aggregate_gates"]["paths_with_anonymous_digest_readback"] == 29
    )
    assert report["aggregate_gates"]["paths_with_complete_b1_b2_lineage"] == 3
    assert (
        report["aggregate_gates"]["paths_with_conflicting_rights_evidence"] == 1
    )
    assert report["aggregate_gates"]["paths_admitted_to_v4"] == 0
    assert report["aggregate_gates"]["paths_with_consumer_canary"] == 0
    assert report["boundaries"]["rights_decision_created_or_expanded"] is False
    assert report["boundaries"]["source_payload_bytes_read"] is True
    assert report["boundaries"]["source_payload_bytes_retained"] is False
    assert report["boundaries"]["source_values_inspected"] is False
    assert report["boundaries"]["v4_admission_performed"] is False


def test_august_crosswalk_inputs_are_digest_bound() -> None:
    report = _load(ROOT / OUTPUT)
    expected_paths = {
        BASELINE,
        LIFECYCLE,
        ROOT_READBACK,
        SOURCE_DIGEST,
        ALIAS_READBACK,
        SOURCE_RECEIPT,
        AUTHORIZATION,
        "quality/qualifications/mbs-current-release-contract.json",
        PBS_INDEX,
        PBS_IDENTITIES,
        PBS_RIGHTS_LEDGER,
        PBS_READBACK,
    }
    assert {row["path"] for row in report["inputs"]} == expected_paths
    for binding in report["inputs"]:
        digest = hashlib.sha256(
            (ROOT / binding["path"]).read_bytes()
        ).hexdigest()
        assert digest == binding["sha256"]


def test_alias_readback_rejects_a_different_immutable_revision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    readback = _load(ROOT / ALIAS_READBACK)
    readback["revision"] = "0" * 40
    invalid_readback = tmp_path / "invalid-readback.json"
    invalid_readback.write_text(json.dumps(readback), encoding="utf-8")
    monkeypatch.setattr(crosswalk, "ALIAS_READBACK", str(invalid_readback))
    with pytest.raises(ValueError, match="does not bind the alias"):
        crosswalk.build_report()


@pytest.mark.parametrize(
    ("field", "value"),
    [("revision", "0" * 40), ("byte_count", 1)],
)
def test_alias_readback_rejects_reconciliation_row_identity_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str | int,
) -> None:
    baseline = _load(ROOT / crosswalk.BASELINE)
    alias = next(
        row
        for row in baseline["objects"]
        if row["dataset"] == DATASET and row["path"] == ALIAS_PATH
    )
    if field == "revision":
        alias[field] = value
    else:
        alias["identity"][field] = value
    invalid_baseline = tmp_path / "invalid-baseline.json"
    invalid_baseline.write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(crosswalk, "BASELINE", str(invalid_baseline))

    with pytest.raises(ValueError, match="does not bind the alias"):
        crosswalk.build_report()


def test_alias_lineage_rejects_a_different_git_object_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _load(ROOT / BASELINE)
    alias = next(
        row
        for row in baseline["objects"]
        if row["dataset"] == DATASET and row["path"] == ALIAS_PATH
    )
    alias["identity"]["git_blob_oid"] = "0" * 40
    invalid_baseline = tmp_path / "invalid-baseline.json"
    invalid_baseline.write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(crosswalk, "BASELINE", str(invalid_baseline))

    with pytest.raises(
        ValueError,
        match="does not resolve to the canonical raw B1/B2 object",
    ):
        crosswalk.build_report()
