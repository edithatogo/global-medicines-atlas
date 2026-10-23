"""Profile bounded header candidates for one frozen MBS workbook archive."""

from __future__ import annotations

import argparse
import hashlib
import json
from operator import itemgetter
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import ZipFile, ZipInfo

import httpx

from global_medicines_atlas.acquisition import (
    AcquisitionPolicy,
    BoundIPAddressTransport,
)
from global_medicines_atlas.federation_reader import HOSTS
from global_medicines_atlas.mbs_archive_formats import stage_bound_member
from global_medicines_atlas.mbs_archive_inventory import (
    DATASET,
    REVISION,
    BoundArchive,
    load_archives,
)
from global_medicines_atlas.mbs_archive_members import (
    MAX_REPORT_BYTES,
    archive_policy,
)
from global_medicines_atlas.mbs_historical_csv_package import (
    FrozenMbsMember,
    load_frozen_members,
)
from global_medicines_atlas.mbs_historical_workbook_headers import (
    profile_workbook_headers,
)

if __package__:
    from scripts.profile_frozen_mbs_archives import (
        require_public_archive_revision,
        stage_pinned_archive,
    )
    from scripts.profile_frozen_mbs_sidecars import (
        classify_inventory_failure,
        require_main_actions,
    )
else:
    from profile_frozen_mbs_archives import (
        require_public_archive_revision,
        stage_pinned_archive,
    )
    from profile_frozen_mbs_sidecars import (
        classify_inventory_failure,
        require_main_actions,
    )

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_COUNT = 6
WORKBOOK_COUNT = 91
MAX_ARCHIVE_MEMBER_PATH_BYTES = 1024 * 1024


def _workbook_members(root: Path) -> tuple[FrozenMbsMember, ...]:
    members = tuple(
        member
        for member in load_frozen_members(root)
        if member.suffix == ".xlsx"
    )
    if (
        len(members) != WORKBOOK_COUNT
        or len({
            (member.source.source_path, member.path_sha256)
            for member in members
        })
        != WORKBOOK_COUNT
    ):
        raise ValueError("MBS frozen workbook denominator differs")
    return members


def _lookup(
    archive: ZipFile, members: tuple[FrozenMbsMember, ...]
) -> dict[str, tuple[ZipInfo, str]]:
    result: dict[str, tuple[ZipInfo, str]] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        native = PurePosixPath(info.filename.replace("\\", "/")).as_posix()
        if len(native.encode()) > MAX_ARCHIVE_MEMBER_PATH_BYTES:
            raise ValueError("MBS archive member path exceeds bound")
        key = hashlib.sha256(native.encode()).hexdigest()
        if key in result:
            raise ValueError("MBS archive member identity is duplicated")
        result[key] = (info, native)
    if set(result) != {member.path_sha256 for member in members}:
        raise ValueError("MBS archive member identity set differs")
    return result


def _aggregate(
    exact_commit: str,
    archive_index: int,
    source: BoundArchive,
    profiled: list[dict[str, Any]],
) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    assignments: list[dict[str, Any]] = []
    for row in profiled:
        profile_sha = row["header_profile_sha256"]
        group = groups.setdefault(
            profile_sha,
            {"header_profile_sha256": profile_sha, "profile": row["profile"]},
        )
        if group["profile"] != row["profile"]:
            raise ValueError("MBS header profile digest collision")
        assignments.append({
            "member_sha256": row["member_sha256"],
            "member_path_sha256": row["member_path_sha256"],
            "member_bytes": row["member_bytes"],
            "ordinal": row["ordinal"],
            "header_profile_sha256": profile_sha,
        })
    assignments.sort(key=itemgetter("ordinal"))
    for group in groups.values():
        group["member_count"] = sum(
            row["header_profile_sha256"] == group["header_profile_sha256"]
            for row in assignments
        )
    if len(assignments) != len(profiled):
        raise ValueError("MBS header profile assignment count differs")
    labels_emitted = any(
        candidate["labels"]
        for workbook in profiled
        for sheet in workbook["sheets"]
        for candidate in sheet["candidate_rows"]
    )
    return {
        "schema_id": "global-medicines-atlas.mbs-historical-workbook-header-profiles",
        "schema_version": 1,
        "status": "passed",
        "workflow_commit": exact_commit,
        "dataset": DATASET,
        "revision": REVISION,
        "archive_index": archive_index,
        "source": {
            "source_id": source.source_id,
            "source_path": source.source_path,
            "source_sha256": source.source_sha256,
            "source_bytes": source.source_bytes,
            "acquisition_id": source.acquisition_id,
            "b1_sha256": source.b1_sha256,
            "b2_sha256": source.b2_sha256,
        },
        "workbook_count": len(assignments),
        "profile_count": len(groups),
        "header_profiles": [groups[key] for key in sorted(groups)],
        "workbook_assignments": assignments,
        "exact_contract_header_count": sum(
            row["disposition"] == "exact_contract_match"
            for workbook in profiled
            for sheet in workbook["sheets"]
            for row in sheet["candidate_rows"]
        ),
        "unresolved_header_candidate_count": sum(
            row["disposition"] == "unresolved_candidate"
            for workbook in profiled
            for sheet in workbook["sheets"]
            for row in sheet["candidate_rows"]
        ),
        "whole_workbook_semantics_complete": False,
        "unmatched_header_cells": "unresolved",
        "non_header_cells": "native_unresolved",
        "header_labels_emitted": labels_emitted,
        "non_header_values_emitted": False,
        "new_sources": 0,
        "new_admissions": 0,
        "publications": 0,
    }


def _encoded(report: dict[str, Any]) -> bytes:
    payload = (
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    if len(payload) > MAX_REPORT_BYTES:
        raise ValueError("MBS header profile report byte bound exceeded")
    return payload


def _write(output: Path, report: dict[str, Any]) -> None:
    payload = _encoded(report)
    with TemporaryDirectory(
        prefix=".mbs-header-report-", dir=output.parent
    ) as temp:
        staged = Path(temp) / "receipt.json"
        staged.write_bytes(payload)
        staged.replace(output)


def qualify(
    exact_commit: str,
    archive_index: int,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Verify and profile only frozen XLSX members from one pinned archive."""
    require_main_actions(exact_commit)
    archives = load_archives(ROOT)
    if type(archive_index) is not int or not 0 <= archive_index < len(archives):
        raise ValueError("MBS archive index is outside the frozen cohort")
    source = archives[archive_index]
    if source.dataset != DATASET or source.revision != REVISION:
        raise ValueError("MBS source archive binding differs")
    members = tuple(
        member for member in _workbook_members(ROOT) if member.source == source
    )
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=120,
        max_bytes=archive_policy(source).max_archive_bytes,
        max_attempts=1,
        max_redirects=3,
    )
    profiled: list[dict[str, Any]] = []
    with (
        TemporaryDirectory(prefix="mbs-historical-header-profile-") as temp,
        httpx.Client(
            transport=transport or BoundIPAddressTransport(policy=policy),
            trust_env=False,
            follow_redirects=True,
            max_redirects=3,
            timeout=120,
            headers={"Accept-Encoding": "identity"},
        ) as client,
    ):
        root = Path(temp)
        archive_path = root / "source.zip"
        require_public_archive_revision(client)
        stage_pinned_archive(client, source, archive_path)
        with ZipFile(archive_path) as archive:
            lookup = _lookup(
                archive,
                tuple(
                    member
                    for member in load_frozen_members(ROOT)
                    if member.source == source
                ),
            )
            for member in members:
                info, native = lookup[member.path_sha256]
                if info.file_size != member.byte_count:
                    raise ValueError("MBS workbook member size differs")
                path = root / f"member-{member.ordinal}.xlsx"
                try:
                    with archive.open(info) as stream:
                        stage_bound_member(
                            stream,
                            path,
                            {
                                "sha256": member.sha256,
                                "bytes": member.byte_count,
                            },
                        )
                    report = profile_workbook_headers(path, member, native)
                    canonical_text = report["canonical_profile"]
                    if not isinstance(canonical_text, str):
                        raise TypeError(
                            "MBS canonical header profile is not text"
                        )
                    canonical_profile = json.loads(canonical_text)
                    profile = canonical_profile
                    profiled.append({
                        **report,
                        "ordinal": member.ordinal,
                        "profile": profile,
                    })
                finally:
                    if path.exists():
                        path.chmod(0o600)
                        path.unlink()
        require_public_archive_revision(client)
    if len(profiled) != len(members):
        raise ValueError("MBS header profile member denominator differs")
    return _aggregate(exact_commit, archive_index, source, profiled)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--archive-index", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        parser.error("existing MBS header profile report must be preserved")
    try:
        report = qualify(args.exact_commit, args.archive_index)
    except Exception as error:
        report = {
            "schema_version": 1,
            "status": "failed",
            "archive_index": args.archive_index,
            "failure_category": classify_inventory_failure(error),
            "header_labels_emitted": False,
            "new_sources": 0,
            "new_admissions": 0,
            "publications": 0,
        }
        _write(args.output, report)
        return 1
    _write(args.output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
