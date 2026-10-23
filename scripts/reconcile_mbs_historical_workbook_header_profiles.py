"""Reconcile exact-main header profiles for the frozen MBS workbook cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
import operator
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

if __package__:
    from scripts.profile_frozen_mbs_sidecars import require_main_actions
    from scripts.profile_mbs_historical_workbook_headers import (
        ARCHIVE_COUNT,
        WORKBOOK_COUNT,
    )
else:
    from profile_frozen_mbs_sidecars import require_main_actions
    from profile_mbs_historical_workbook_headers import (
        ARCHIVE_COUNT,
        WORKBOOK_COUNT,
    )

from global_medicines_atlas.mbs_archive_inventory import (
    DATASET,
    REVISION,
    BoundArchive,
    load_archives,
)
from global_medicines_atlas.mbs_historical_csv_package import (
    FrozenMbsMember,
    load_frozen_members,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT_STEM = "historical-workbook-header-profiles"


@dataclass
class _ProfileTotals:
    groups: dict[str, dict[str, Any]] = field(default_factory=dict)
    exact_headers: int = 0
    unresolved_headers: int = 0
    interpreted_bindings: int = 0
    unresolved_labels: int = 0
    header_labels_emitted: bool = False


@dataclass
class _CohortTotals:
    profile_groups: dict[str, dict[str, Any]] = field(default_factory=dict)
    assignments: list[dict[str, Any]] = field(default_factory=list)
    seen_members: set[tuple[int, str, str, int, int]] = field(
        default_factory=set
    )
    archive_summaries: list[dict[str, Any]] = field(default_factory=list)
    exact_headers: int = 0
    unresolved_headers: int = 0
    interpreted_bindings: int = 0
    unresolved_labels: int = 0
    header_labels_emitted: bool = False


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_record(source: BoundArchive) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "source_path": source.source_path,
        "source_sha256": source.source_sha256,
        "source_bytes": source.source_bytes,
        "acquisition_id": source.acquisition_id,
        "b1_sha256": source.b1_sha256,
        "b2_sha256": source.b2_sha256,
    }


def _expected_members_by_archive(
    sources: tuple[BoundArchive, ...],
    members: tuple[FrozenMbsMember, ...],
    expected_workbook_count: int,
) -> dict[int, set[tuple[str, str, int, int]]]:
    if len(sources) != ARCHIVE_COUNT:
        raise ValueError("MBS header-profile archive denominator differs")
    if any(
        source.dataset != DATASET or source.revision != REVISION
        for source in sources
    ):
        raise ValueError("MBS header-profile source context differs")
    if (
        sum(member.suffix == ".xlsx" for member in members)
        != expected_workbook_count
    ):
        raise ValueError("MBS frozen workbook denominator differs")

    source_indices = {source: index for index, source in enumerate(sources)}
    if len(source_indices) != ARCHIVE_COUNT:
        raise ValueError("MBS header-profile source identity is duplicated")
    expected: dict[int, set[tuple[str, str, int, int]]] = {
        index: set() for index in range(ARCHIVE_COUNT)
    }
    for member in members:
        if member.suffix != ".xlsx":
            continue
        try:
            archive_index = source_indices[member.source]
        except KeyError as exc:
            raise ValueError("MBS workbook source binding differs") from exc
        identity = (
            member.sha256,
            member.path_sha256,
            member.byte_count,
            member.ordinal,
        )
        if identity in expected[archive_index]:
            raise ValueError("MBS frozen workbook identity is duplicated")
        expected[archive_index].add(identity)
    if (
        sum(len(identities) for identities in expected.values())
        != expected_workbook_count
    ):
        raise ValueError("MBS frozen workbook identities are not unique")
    return expected


def _profile_groups(report: dict[str, Any]) -> _ProfileTotals:
    totals = _ProfileTotals()
    for group in report.get("header_profiles", []):
        profile = group.get("profile")
        profile_sha = group.get("header_profile_sha256")
        if not isinstance(profile, dict) or not isinstance(profile_sha, str):
            raise TypeError("MBS header-profile group is malformed")
        typed_profile = cast("dict[str, Any]", profile)
        typed_group = cast("dict[str, Any]", group)
        if _sha256(_canonical(typed_profile)) != profile_sha:
            raise ValueError("MBS header-profile digest differs")
        if profile_sha in totals.groups:
            raise ValueError("MBS header-profile group is duplicated")
        count = group.get("member_count")
        if type(count) is not int or count <= 0:
            raise ValueError("MBS header-profile member count differs")
        totals.groups[profile_sha] = typed_group

        candidate_counts = _count_profile_candidates(typed_profile, count)
        totals.exact_headers += candidate_counts[0]
        totals.unresolved_headers += candidate_counts[1]
        totals.interpreted_bindings += candidate_counts[2]
        totals.unresolved_labels += candidate_counts[3]

    totals.header_labels_emitted = any(
        candidate.get("labels")
        for group in totals.groups.values()
        for sheet in group["profile"].get("sheets", [])
        for candidate in sheet.get("candidate_rows", [])
    )
    if report.get("profile_count") != len(totals.groups):
        raise ValueError("MBS header-profile summary differs")
    if report.get("header_labels_emitted") != totals.header_labels_emitted:
        raise ValueError("MBS header-profile label summary differs")
    if report.get("exact_contract_header_count") != totals.exact_headers:
        raise ValueError("MBS exact header count differs")
    if (
        report.get("unresolved_header_candidate_count")
        != totals.unresolved_headers
    ):
        raise ValueError("MBS unresolved header count differs")
    return totals


def _count_profile_candidates(
    profile: dict[str, Any], members: int
) -> tuple[int, int, int, int]:
    exact_count = 0
    unresolved_count = 0
    interpreted_bindings = 0
    unresolved_labels = 0
    for sheet in profile.get("sheets", []):
        for candidate in sheet.get("candidate_rows", []):
            labels = candidate.get("labels", [])
            if candidate.get("disposition") == "exact_contract_match":
                exact_count += members
                bindings = candidate.get("column_bindings", [])
                if any(
                    binding.get("status") != "interpreted"
                    for binding in bindings
                ):
                    raise ValueError(
                        "MBS supported header binding state differs"
                    )
                interpreted_bindings += members * len(bindings)
            elif candidate.get("disposition") == "unresolved_candidate":
                unresolved_count += members
                unresolved_labels += members * len(labels)
            else:
                raise ValueError("MBS header candidate disposition differs")
    return (
        exact_count,
        unresolved_count,
        interpreted_bindings,
        unresolved_labels,
    )


def _assignments_for_archive(
    report: dict[str, Any],
    index: int,
    source: BoundArchive,
    groups: dict[str, dict[str, Any]],
    expected: set[tuple[str, str, int, int]],
    seen_members: set[tuple[int, str, str, int, int]],
) -> list[dict[str, Any]]:
    local_assignments = report.get("workbook_assignments", [])
    if report.get("workbook_count") != len(local_assignments):
        raise ValueError("MBS header-profile workbook count differs")
    assignments: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    archive_member_ids: set[tuple[str, str, int, int]] = set()
    for assignment in local_assignments:
        profile_sha = assignment.get("header_profile_sha256")
        if profile_sha not in groups:
            raise ValueError("MBS workbook profile assignment is unbound")
        identity = (
            index,
            assignment.get("member_sha256"),
            assignment.get("member_path_sha256"),
            assignment.get("member_bytes"),
            assignment.get("ordinal"),
        )
        if (
            not isinstance(identity[1], str)
            or not isinstance(identity[2], str)
            or type(identity[3]) is not int
            or type(identity[4]) is not int
        ):
            raise TypeError("MBS workbook member identity is malformed")
        if identity in seen_members:
            raise ValueError("MBS workbook member identity is duplicated")
        seen_members.add(identity)
        archive_member_ids.add((
            identity[1],
            identity[2],
            identity[3],
            identity[4],
        ))
        counts[profile_sha] = counts.get(profile_sha, 0) + 1
        assignments.append({
            "archive_index": index,
            "source_path": source.source_path,
            "source_sha256": source.source_sha256,
            "member_sha256": identity[1],
            "member_path_sha256": identity[2],
            "member_bytes": identity[3],
            "ordinal": identity[4],
            "header_profile_sha256": profile_sha,
        })
    if any(
        counts.get(key, 0) != group["member_count"]
        for key, group in groups.items()
    ):
        raise ValueError("MBS workbook profile assignment count differs")
    if archive_member_ids != expected:
        raise ValueError("MBS workbook member denominator differs")
    return assignments


def _validate_archive_report(
    report: dict[str, Any], exact_commit: str, source: BoundArchive
) -> None:
    expected = {
        "status": "passed",
        "workflow_commit": exact_commit,
        "dataset": DATASET,
        "revision": REVISION,
        "source": _source_record(source),
        "whole_workbook_semantics_complete": False,
        "unmatched_header_cells": "unresolved",
        "non_header_cells": "native_unresolved",
        "new_sources": 0,
        "new_admissions": 0,
        "publications": 0,
    }
    if any(report.get(key) != value for key, value in expected.items()):
        raise ValueError("MBS header-profile archive receipt differs")


def reconcile_reports(
    exact_commit: str,
    reports: list[dict[str, Any]],
    sources: tuple[BoundArchive, ...],
    members: tuple[FrozenMbsMember, ...],
    *,
    expected_workbook_count: int = WORKBOOK_COUNT,
) -> dict[str, Any]:
    """Prove full archive and member coverage before grouping profiles."""
    if len(reports) != ARCHIVE_COUNT:
        raise ValueError("MBS header-profile archive denominator differs")
    expected_members = _expected_members_by_archive(
        sources, members, expected_workbook_count
    )

    reports_by_index: dict[int, dict[str, Any]] = {}
    for report in reports:
        index = report.get("archive_index")
        if type(index) is not int or not 0 <= index < ARCHIVE_COUNT:
            raise ValueError("MBS header-profile archive index differs")
        if index in reports_by_index:
            raise ValueError("MBS header-profile archive index is duplicated")
        reports_by_index[index] = report
    if set(reports_by_index) != set(range(ARCHIVE_COUNT)):
        raise ValueError("MBS header-profile archive coverage differs")

    expected_sources = dict(enumerate(sources))
    cohort = _CohortTotals()

    for index in range(ARCHIVE_COUNT):
        report = reports_by_index[index]
        source = expected_sources[index]
        _validate_archive_report(report, exact_commit, source)
        profiles = _profile_groups(report)
        cohort.exact_headers += profiles.exact_headers
        cohort.unresolved_headers += profiles.unresolved_headers
        cohort.interpreted_bindings += profiles.interpreted_bindings
        cohort.unresolved_labels += profiles.unresolved_labels
        cohort.header_labels_emitted = (
            cohort.header_labels_emitted or profiles.header_labels_emitted
        )
        for profile_sha, group in profiles.groups.items():
            profile = group["profile"]
            global_group = cohort.profile_groups.setdefault(
                profile_sha,
                {
                    "header_profile_sha256": profile_sha,
                    "profile": profile,
                    "member_count": 0,
                },
            )
            if global_group["profile"] != profile:
                raise ValueError("MBS header-profile digest collision")
            global_group["member_count"] += group["member_count"]

        archive_assignments = _assignments_for_archive(
            report,
            index,
            source,
            profiles.groups,
            expected_members[index],
            cohort.seen_members,
        )
        cohort.assignments.extend(archive_assignments)
        cohort.archive_summaries.append({
            "archive_index": index,
            "source": _source_record(source),
            "workbook_count": len(archive_assignments),
            "profile_count": len(profiles.groups),
            "header_labels_emitted": report["header_labels_emitted"],
        })

    if (
        len(cohort.seen_members) != expected_workbook_count
        or len(cohort.assignments) != expected_workbook_count
    ):
        raise ValueError("MBS complete workbook cohort differs")
    if (
        sum(group["member_count"] for group in cohort.profile_groups.values())
        != expected_workbook_count
    ):
        raise ValueError("MBS global workbook profile denominator differs")
    cohort.assignments.sort(
        key=operator.itemgetter(
            "archive_index", "ordinal", "member_path_sha256"
        )
    )
    return {
        "schema_id": "global-medicines-atlas.mbs-historical-workbook-header-cohort",
        "schema_version": 1,
        "status": "passed",
        "workflow_commit": exact_commit,
        "dataset": DATASET,
        "revision": REVISION,
        "archive_count": ARCHIVE_COUNT,
        "archives": cohort.archive_summaries,
        "workbook_count": len(cohort.assignments),
        "profile_count": len(cohort.profile_groups),
        "header_profiles": [
            cohort.profile_groups[key] for key in sorted(cohort.profile_groups)
        ],
        "workbook_assignments": cohort.assignments,
        "exact_contract_header_count": cohort.exact_headers,
        "unresolved_header_candidate_count": cohort.unresolved_headers,
        "interpreted_header_column_binding_count": cohort.interpreted_bindings,
        "unresolved_header_label_count": cohort.unresolved_labels,
        "header_labels_emitted": cohort.header_labels_emitted,
        "field_state_policy": {
            "exact_contract_header_bindings": "interpreted",
            "other_header_candidates": "unresolved",
            "non_header_cells": "native_unresolved",
        },
        "whole_workbook_semantics_complete": False,
        "new_sources": 0,
        "new_admissions": 0,
        "consumer_canaries": 0,
        "publications": 0,
    }


def _read_inputs(input_dir: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for index in range(ARCHIVE_COUNT):
        path = input_dir / f"{REPORT_STEM}-{index}.json"
        if path.is_symlink() or not path.is_file():
            raise ValueError("MBS archive profile receipt is missing")
        raw = path.read_bytes()
        if len(raw) > 32 * 1024 * 1024:
            raise ValueError("MBS archive profile receipt exceeds bound")
        report = json.loads(raw)
        if not isinstance(report, dict):
            raise TypeError("MBS archive profile receipt is malformed")
        reports.append(cast("dict[str, Any]", report))
    return reports


def _write(output: Path, report: dict[str, Any]) -> None:
    if output.exists() or output.is_symlink():
        raise ValueError("existing MBS header cohort receipt must be preserved")
    payload = (
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    with TemporaryDirectory(
        prefix=".mbs-header-cohort-", dir=output.parent
    ) as temp:
        staged = Path(temp) / "receipt.json"
        staged.write_bytes(payload)
        staged.replace(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        require_main_actions(args.exact_commit)
        sources = load_archives(ROOT)
        members = load_frozen_members(ROOT)
        report = reconcile_reports(
            args.exact_commit, _read_inputs(args.input_dir), sources, members
        )
    except Exception:
        report = {
            "schema_id": "global-medicines-atlas.mbs-historical-workbook-header-cohort",
            "schema_version": 1,
            "status": "failed",
            "failure_category": "header_profile_reconciliation_failed",
            "workflow_commit": args.exact_commit,
            "new_sources": 0,
            "new_admissions": 0,
            "consumer_canaries": 0,
            "publications": 0,
        }
        _write(args.output, report)
        return 1
    _write(args.output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
