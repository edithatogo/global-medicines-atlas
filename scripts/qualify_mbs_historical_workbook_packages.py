"""Qualify all frozen historical workbook members in bounded protected-runner groups."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict
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
from global_medicines_atlas.mbs_archive_inventory import DATASET, REVISION
from global_medicines_atlas.mbs_archive_members import (
    MAX_REPORT_BYTES,
    archive_policy,
)
from global_medicines_atlas.mbs_historical_csv_package import (
    FrozenMbsMember,
    load_frozen_members,
)
from global_medicines_atlas.mbs_historical_workbook_package import (
    qualify_workbook_member_package,
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
EXPECTED_WORKBOOK_MEMBERS = 91
MEMBERS_PER_GROUP = 1
GROUP_COUNT = EXPECTED_WORKBOOK_MEMBERS // MEMBERS_PER_GROUP
Progress = Callable[[str, int], None]


def _workbook_members(root: Path) -> tuple[FrozenMbsMember, ...]:
    members = tuple(
        member
        for member in load_frozen_members(root)
        if member.suffix == ".xlsx"
    )
    if (
        len(members) != EXPECTED_WORKBOOK_MEMBERS
        or len({(m.source.source_path, m.path_sha256) for m in members})
        != EXPECTED_WORKBOOK_MEMBERS
    ):
        raise ValueError("MBS frozen workbook member denominator differs")
    if any(
        member.source.dataset != DATASET or member.source.revision != REVISION
        for member in members
    ) or len({m.source.source_path for m in members}) != len({
        m.source for m in members
    }):
        raise ValueError("MBS frozen workbook archive binding differs")
    return members


def select_group(root: Path, group: int) -> tuple[FrozenMbsMember, ...]:
    """Partition all exact frozen workbook identities; no caller supplies source URLs."""
    if type(group) is not int or not 0 <= group < GROUP_COUNT:
        raise ValueError("MBS workbook group is outside the frozen cohort")
    members = _workbook_members(root)
    start = group * MEMBERS_PER_GROUP
    return members[start : start + MEMBERS_PER_GROUP]


def _progress(callback: Progress | None, phase: str, completed: int) -> None:
    if callback is not None:
        callback(phase, completed)


def _lookup(
    archive: ZipFile, members: tuple[FrozenMbsMember, ...]
) -> dict[str, tuple[ZipInfo, str]]:
    lookup: dict[str, tuple[ZipInfo, str]] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        native = PurePosixPath(info.filename.replace("\\", "/")).as_posix()
        key = hashlib.sha256(native.encode()).hexdigest()
        if key in lookup:
            raise ValueError(
                "MBS workbook archive member identity is duplicated"
            )
        lookup[key] = (info, native)
    if set(lookup) != {member.path_sha256 for member in members}:
        raise ValueError("MBS workbook archive member identity set differs")
    return lookup


def _qualify_member(
    root: Path,
    archive: ZipFile,
    member: FrozenMbsMember,
    pair: tuple[ZipInfo, str],
) -> dict[str, Any]:
    info, native = pair
    if info.file_size != member.byte_count:
        raise ValueError("MBS workbook archive member size differs")
    path = root / f"member-{member.ordinal}.xlsx"
    try:
        with archive.open(info) as stream:
            stage_bound_member(
                stream,
                path,
                {"sha256": member.sha256, "bytes": member.byte_count},
            )
        return qualify_workbook_member_package(path, member, native)
    finally:
        if path.exists():
            path.chmod(0o600)
            path.unlink()


def qualify(
    exact_commit: str,
    group: int,
    *,
    transport: httpx.BaseTransport | None = None,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """Verify parent bytes and every selected member before complete package checks.

    Parent SHA/size and retained member inventories bind the already verified
    archive. Rehash only selected member streams; no extraction uses native paths.
    Parquet and native values stay private; only manifests/counts leave the runner.
    """
    require_main_actions(exact_commit)
    selected = select_group(ROOT, group)
    source = selected[0].source
    all_members = tuple(
        m for m in _workbook_members(ROOT) if m.source == source
    )
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=120,
        max_bytes=archive_policy(source).max_archive_bytes,
        max_attempts=1,
        max_redirects=3,
    )
    reports: list[dict[str, Any]] = []
    with (
        TemporaryDirectory(
            prefix="mbs-historical-workbook-group-"
        ) as temporary,
        httpx.Client(
            transport=transport or BoundIPAddressTransport(policy=policy),
            trust_env=False,
            follow_redirects=True,
            max_redirects=3,
            timeout=120,
            headers={"Accept-Encoding": "identity"},
        ) as client,
    ):
        root = Path(temporary)
        archive_path = root / "source.zip"
        require_public_archive_revision(client)
        _progress(progress, "source-stage", 0)
        stage_pinned_archive(client, source, archive_path)
        with ZipFile(archive_path) as archive:
            lookup = _lookup(archive, all_members)
            for member in selected:
                _progress(progress, "member-native-check", len(reports))
                reports.append(
                    _qualify_member(
                        root, archive, member, lookup[member.path_sha256]
                    )
                )
                _progress(progress, "member-complete", len(reports))
        _progress(progress, "public-readback", len(reports))
        require_public_archive_revision(client)
    if len(reports) != len(selected):
        raise ValueError("MBS workbook completed member denominator differs")
    return {
        "schema_id": "global-medicines-atlas.frozen-historical-mbs-workbook-native-group",
        "schema_version": 1,
        "status": "passed",
        "workflow_commit": exact_commit,
        "dataset": DATASET,
        "revision": REVISION,
        "group": group,
        "group_count": GROUP_COUNT,
        "cohort_members": EXPECTED_WORKBOOK_MEMBERS,
        "selected_member_bindings": [asdict(member) for member in selected],
        "members": reports,
        "native_member_names_or_values_emitted": False,
        "source_column_semantics_qualified": False,
        "new_sources": 0,
        "new_admissions": 0,
        "new_federated_canaries": 0,
        "publications": 0,
        "rights_conclusion_changed": False,
    }


def _encoded(report: dict[str, Any]) -> bytes:
    data = (
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode()
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError(
            "MBS workbook complete group receipt byte bound exceeded"
        )
    return data


def _write(output: Path, report: dict[str, Any]) -> None:
    payload = _encoded(report)
    with TemporaryDirectory(
        prefix=".mbs-workbook-receipt-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "receipt.json"
        staged.write_bytes(payload)
        staged.replace(output)


def _execute(
    exact_commit: str, group: int, output: Path, state: dict[str, Any]
) -> dict[str, Any]:
    require_main_actions(exact_commit)

    def progress(phase: str, completed: int) -> None:
        if (
            phase
            not in {
                "not-started",
                "source-stage",
                "member-native-check",
                "member-complete",
                "public-readback",
            }
            or type(completed) is not int
            or not 0 <= completed <= MEMBERS_PER_GROUP
        ):
            raise ValueError("MBS workbook progress state differs")
        state.update({"phase": phase, "completed_members": completed})
        _write(
            output,
            {
                "schema_version": 1,
                "status": "incomplete",
                "workflow_commit": exact_commit,
                "group": group,
                "phase": phase,
                "completed_members": completed,
                "native_member_names_or_values_emitted": False,
                "new_sources": 0,
                "new_admissions": 0,
                "publications": 0,
            },
        )

    progress("not-started", 0)
    report = qualify(exact_commit, group, progress=progress)
    _write(output, report)
    return report


def main(argv: list[str] | None = None) -> int:
    """Retain bounded progress on termination and coded failures without values."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument(
        "--group", required=True, type=int, choices=range(GROUP_COUNT)
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        parser.error("existing historical workbook receipt must be preserved")
    state: dict[str, Any] = {"phase": "not-started", "completed_members": 0}
    try:
        report = _execute(args.exact_commit, args.group, args.output, state)
    except Exception as error:
        report = {
            "schema_version": 1,
            "status": "failed",
            **state,
            "reason": "historical-workbook-native-group-did-not-complete",
            "group": args.group,
            "failure_category": classify_inventory_failure(error),
            "native_member_names_or_values_emitted": False,
            "new_sources": 0,
            "new_admissions": 0,
            "publications": 0,
        }
        _write(args.output, report)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
