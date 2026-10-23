"""All frozen MBS workbook profiles reconcile by exact archive/member identity."""

from __future__ import annotations

import hashlib
import json
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest
from scripts.reconcile_mbs_historical_workbook_header_profiles import (
    reconcile_reports,
)

from global_medicines_atlas.mbs_archive_inventory import (
    DATASET,
    REVISION,
    BoundArchive,
)
from global_medicines_atlas.mbs_historical_csv_package import FrozenMbsMember

ROOT = Path(__file__).resolve().parents[1]


def test_standalone_entrypoint_imports_from_scripts_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = (
        ROOT / "scripts/reconcile_mbs_historical_workbook_header_profiles.py"
    )
    paths = [
        entry
        for entry in sys.path
        if Path(entry or ".").resolve() != ROOT.resolve()
    ]
    monkeypatch.setattr(sys, "path", paths)
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = runpy.run_path(
        str(script), run_name="standalone_mbs_header_reconciler"
    )
    assert callable(module["main"])


def _source(index: int) -> BoundArchive:
    return BoundArchive(
        dataset=DATASET,
        revision=REVISION,
        source_path=f"raw/mbs/archive-{index}.zip",
        source_sha256=f"{index:064x}",
        source_bytes=100 + index,
        source_id=f"source-{index}",
        acquisition_id=f"acquisition-{index}",
        b1_sha256=f"{index + 10:064x}",
        b2_sha256=f"{index + 20:064x}",
        prior_status="structure_verified",
        prior_member_count=1,
        prior_expanded_bytes=100,
        prior_inventory_sha256=f"{index + 30:064x}",
    )


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _report(index: int, source: BoundArchive, *, workbook: bool) -> dict:
    profile = {
        "sheets": (
            [
                {
                    "ordinal": 0,
                    "name": "Sheet1",
                    "dimension": "A1:B2",
                    "candidate_rows": [
                        {
                            "row_index": 1,
                            "labels": [{"column": "A", "text": "Year"}],
                            "disposition": "exact_contract_match",
                            "column_bindings": [
                                {
                                    "column": "A",
                                    "native_header": "Year",
                                    "field": "calendar_year_label",
                                    "status": "interpreted",
                                }
                            ],
                        },
                        {
                            "row_index": 2,
                            "labels": [{"column": "A", "text": "Legacy"}],
                            "disposition": "unresolved_candidate",
                        },
                    ],
                }
            ]
            if workbook
            else []
        )
    }
    profile_sha = hashlib.sha256(_canonical(profile)).hexdigest()
    source_record = {
        "source_id": source.source_id,
        "source_path": source.source_path,
        "source_sha256": source.source_sha256,
        "source_bytes": source.source_bytes,
        "acquisition_id": source.acquisition_id,
        "b1_sha256": source.b1_sha256,
        "b2_sha256": source.b2_sha256,
    }
    assignments = (
        [
            {
                "member_sha256": "a" * 64,
                "member_path_sha256": "b" * 64,
                "member_bytes": 10,
                "ordinal": 0,
                "header_profile_sha256": profile_sha,
            }
        ]
        if workbook
        else []
    )
    return {
        "schema_id": "global-medicines-atlas.mbs-historical-workbook-header-profiles",
        "schema_version": 1,
        "status": "passed",
        "workflow_commit": "c" * 40,
        "dataset": DATASET,
        "revision": REVISION,
        "archive_index": index,
        "source": source_record,
        "workbook_count": len(assignments),
        "profile_count": 1 if workbook else 0,
        "header_profiles": (
            [
                {
                    "header_profile_sha256": profile_sha,
                    "profile": profile,
                    "member_count": 1,
                }
            ]
            if workbook
            else []
        ),
        "workbook_assignments": assignments,
        "exact_contract_header_count": 1 if workbook else 0,
        "unresolved_header_candidate_count": 1 if workbook else 0,
        "whole_workbook_semantics_complete": False,
        "unmatched_header_cells": "unresolved",
        "non_header_cells": "native_unresolved",
        "header_labels_emitted": workbook,
        "new_sources": 0,
        "new_admissions": 0,
        "publications": 0,
    }


def _inputs():
    sources = tuple(_source(index) for index in range(6))
    members = (
        FrozenMbsMember(
            source=sources[0],
            ordinal=0,
            sha256="a" * 64,
            byte_count=10,
            path_sha256="b" * 64,
            suffix=".xlsx",
            inventory_sha256="d" * 64,
        ),
    )
    reports = [
        _report(index, source, workbook=index == 0)
        for index, source in enumerate(sources)
    ]
    return sources, members, reports


def test_reconciles_all_archives_and_preserves_unresolved_cells():
    sources, members, reports = _inputs()

    result = reconcile_reports(
        "c" * 40,
        reports,
        sources,
        members,
        expected_workbook_count=1,
    )

    assert result["archive_count"] == 6
    assert result["workbook_count"] == 1
    assert result["profile_count"] == 1
    assert result["exact_contract_header_count"] == 1
    assert result["unresolved_header_candidate_count"] == 1
    assert result["interpreted_header_column_binding_count"] == 1
    assert result["unresolved_header_label_count"] == 1
    assert (
        result["field_state_policy"]["non_header_cells"] == "native_unresolved"
    )
    assert result["whole_workbook_semantics_complete"] is False
    assert result["new_sources"] == result["new_admissions"] == 0
    assert result["consumer_canaries"] == result["publications"] == 0


def test_rejects_missing_archive_receipt():
    sources, members, reports = _inputs()
    with pytest.raises(ValueError, match="archive denominator"):
        reconcile_reports(
            "c" * 40,
            reports[:-1],
            sources,
            members,
            expected_workbook_count=1,
        )


def test_rejects_duplicate_member_assignment():
    sources, members, reports = _inputs()
    assignment = reports[0]["workbook_assignments"][0]
    reports[0]["workbook_assignments"].append(dict(assignment))
    reports[0]["workbook_count"] = 2
    reports[0]["header_profiles"][0]["member_count"] = 2
    reports[0]["exact_contract_header_count"] = 2
    reports[0]["unresolved_header_candidate_count"] = 2
    with pytest.raises(ValueError, match="member identity is duplicated"):
        reconcile_reports(
            "c" * 40,
            reports,
            sources,
            members,
            expected_workbook_count=1,
        )


def test_rejects_profile_member_count_without_assignments():
    sources, members, reports = _inputs()
    reports[0]["header_profiles"][0]["member_count"] = 2
    reports[0]["exact_contract_header_count"] = 2
    reports[0]["unresolved_header_candidate_count"] = 2

    with pytest.raises(ValueError, match="profile assignment count differs"):
        reconcile_reports(
            "c" * 40,
            reports,
            sources,
            members,
            expected_workbook_count=1,
        )


def test_rejects_unresolved_header_labels_reported_as_interpreted():
    sources, members, reports = _inputs()
    reports[0]["unresolved_header_candidate_count"] = 0
    with pytest.raises(ValueError, match="unresolved header count"):
        reconcile_reports(
            "c" * 40,
            reports,
            sources,
            members,
            expected_workbook_count=1,
        )
