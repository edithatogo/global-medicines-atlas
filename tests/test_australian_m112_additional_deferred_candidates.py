"""Contract tests for the additional M-112 source deferrals."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = (
    ROOT
    / "quality/qualifications/"
    / ("australian-m112-additional-deferred-source-candidates-20261004.json")
)


def _read(path: str) -> dict[str, object]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_additional_deferrals_preserve_scope_and_open_gates() -> None:
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    previous = _read(
        "quality/qualifications/australian-m112-deferred-source-candidates-20261004.json"
    )

    assert register["scope"]["approved_candidate_denominator"] == 1_759
    assert register["scope"]["previously_deferred_candidate_paths"] == 1_719
    assert register["scope"]["newly_deferred_candidate_paths"] == 40
    assert register["scope"]["combined_deferred_candidate_paths"] == 1_759
    assert (
        register["scope"]["remaining_candidate_paths_for_active_reconciliation"]
        == 0
    )
    assert register["scope"]["denominator_changed"] is False
    assert previous["scope"]["denominator_changed"] is False

    groups = {
        row["group_id"]: row for row in register["additional_deferred_sources"]
    }
    assert set(groups) == {
        "au-mbs-august-2026-raw-object-paths",
        "au-mbs-existing-projections",
        "au-pbs-historical-archive",
        "au-mbs-utilisation-rights-ledger",
        "au-pbs-utilisation-rights-ledger",
        "au-mbs-six-exact-receipt-and-authorization-gaps",
    }
    assert sum(row["candidate_paths"] for row in groups.values()) == 40
    assert register["active_reconciliation_remainder"]["candidate_paths"] == 0
    assert register["active_reconciliation_remainder"]["candidate_class"] == (
        "raw_source_payload"
    )
    assert register["boundaries"]["new_rights_or_licensing_conclusion"] is False
    assert register["boundaries"]["approved_denominator_changed"] is False
    assert register["boundaries"]["v4_admission_performed"] is False
    assert register["boundaries"]["m112_federation_accepted"] is False


def test_additional_deferrals_match_the_exact_current_candidate_inventory() -> (
    None
):
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    metadata = _read(
        "quality/qualifications/australian-m112-current-tree-object-inventory-20261004.json"
    )
    report = _read(
        "quality/qualifications/australian-m112-current-tree-object-identity-reconciliation-20261004.json"
    )
    previous = _read(
        "quality/qualifications/australian-m112-deferred-source-candidates-20261004.json"
    )
    rows = metadata["observations"]
    revisions = {
        row["dataset"]: row["revision"]
        for row in report["current_tree_metadata_readback"]["datasets"]
    }
    groups = {
        row["group_id"]: row for row in register["additional_deferred_sources"]
    }
    deferred_paths: set[str] = set()

    for group in groups.values():
        selected = [
            row
            for row in rows
            if row["dataset"] == group["dataset"]
            and (
                group["path_selection"].get("kind")
                == "all_candidates_in_dataset"
                or (
                    group["path_selection"].get("kind")
                    == "candidate_class_and_dataset"
                    and row["candidate_class"]
                    == group["path_selection"]["candidate_class"]
                )
                or (
                    group["path_selection"].get("kind") == "exact_paths"
                    and row["path"] in group["path_selection"]["paths"]
                )
            )
        ]
        assert len(selected) == group["candidate_paths"]
        assert (
            sum(
                row["candidate_class"] == "raw_source_payload"
                for row in selected
            )
            == (group["raw_paths"])
        )
        assert (
            sum(
                row["candidate_class"] == "existing_data_projection"
                for row in selected
            )
            == group["projection_paths"]
        )
        assert group["current_revision"] == revisions[group["dataset"]]
        assert all(
            row["revision"] == group["current_revision"] for row in selected
        )
        if group["group_id"] == "au-mbs-august-2026-raw-object-paths":
            alias = group["path_alias_identity"]
            assert {row["path"] for row in selected} == set(alias["paths"])
            assert {row["observed_git_blob_oid"] for row in selected} == {
                alias["same_current_git_blob_oid"]
            }
            assert {row["observed_bytes"] for row in selected} == {
                alias["same_byte_count"]
            }
            assert {row["observed_lfs_sha256"] for row in selected} == {None}
            assert (
                alias["same_source_sha256"]
                == report["digest_coverage"]["alias"][
                    "sha256_from_verified_path"
                ]
            )
        assert deferred_paths.isdisjoint(row["path"] for row in selected)
        deferred_paths.update(row["path"] for row in selected)

    previous_source = previous["deferred_sources"][0]
    previous_rows = [
        row
        for row in rows
        if row["dataset"] == previous_source["dataset"]
        and row["revision"] == previous_source["current_revision"]
    ]
    assert len(previous_rows) == previous_source["candidate_paths"] == 1_719
    assert deferred_paths.isdisjoint(row["path"] for row in previous_rows)

    active = register["active_reconciliation_remainder"]
    active_rows = [
        row
        for row in rows
        if row["dataset"] == active["dataset"]
        and row["candidate_class"] == active["candidate_class"]
        and row["path"]
        not in {
            "raw/mbs/releases/Downloads-20260801/MBS-XML-20260801.XML",
            "raw/mbs/releases/2026-08-01/c5c04792cbdc7017589b4453aa4506f26b6cfcbfeaee3b0d6c866a8050b06565.xml",
        }
    ]
    assert len(active_rows) == 6
    assert active["candidate_paths"] == 0
    newly_deferred = {
        row["path"]
        for group in groups.values()
        for row in rows
        if row["dataset"] == group["dataset"]
        and group["path_selection"].get("kind") == "exact_paths"
        and row["path"] in group["path_selection"]["paths"]
    }
    assert {row["path"] for row in active_rows} <= newly_deferred


def test_deferred_groups_match_rights_and_evidence_crosswalks() -> None:
    register = json.loads(REGISTER.read_text(encoding="utf-8"))
    crosswalk = _read(
        "quality/qualifications/australian-m112-source-rights-lineage-crosswalk-20260930.json"
    )
    groups = {
        row["group_id"]: row for row in register["additional_deferred_sources"]
    }
    mbs_source = next(
        row
        for row in crosswalk["candidate_rights_and_lineage"]
        if row["dataset"] == "edithatogo/australian-mbs-source-archive"
    )
    pbs_source = next(
        row
        for row in crosswalk["candidate_rights_and_lineage"]
        if row["dataset"] == "edithatogo/australian-pbs-source-archive"
    )
    for key, dataset in [
        ("au-mbs-august-2026-raw-object-paths", mbs_source),
        ("au-pbs-historical-archive", pbs_source),
    ]:
        if key == "au-mbs-august-2026-raw-object-paths":
            # The register corrects the historical crosswalk wording while
            # retaining its first two exact authorization and receipt facts.
            assert (
                groups[key]["source_evidence"][:2]
                == (dataset["source_specific_evidence"][:2])
            )
            assert (
                "Both records retain their source-native accepted state"
                in (groups[key]["source_evidence"][2])
            )
            assert (
                "without treating either unreviewed record as accepted"
                not in (groups[key]["reentry_trigger"])
            )
        else:
            assert (
                groups[key]["source_evidence"]
                == dataset["source_specific_evidence"]
            )
    assert (
        "23 existing data projections"
        in groups["au-mbs-existing-projections"]["reason"]
    )
    assert groups["au-mbs-utilisation-rights-ledger"]["source_ids"] == sorted(
        next(
            row["sources"]
            for row in crosswalk["candidate_rights_and_lineage"]
            if row["dataset"]
            == groups["au-mbs-utilisation-rights-ledger"]["dataset"]
        )
    )

    for evidence in register["evidence_inputs"]:
        path = ROOT / evidence["path"]
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest() == evidence["sha256"]
        )
