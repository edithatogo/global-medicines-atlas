"""Profile source-native value shapes for one frozen MBS archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import operator
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
from global_medicines_atlas.mbs_historical_workbook_native import (
    iter_workbook_records,
)
from global_medicines_atlas.mbs_historical_workbook_value_shapes import (
    EXPECTED_FIELDS,
    profile_workbook_records,
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
HEADER_REPORT = (
    ROOT
    / "quality/qualifications/mbs-historical-workbook-header-cohort-20261024-40040624592.json"
)
HEADER_SHA256 = (
    "5a5858e0a458c46452188a4f52ea396bf1f98c9ce3710d747dd1a58588c196f1"
)
COHORT_REPORT = (
    ROOT
    / "quality/qualifications/mbs-historical-workbook-cohort-20261023-39724026209-39891918206.json"
)
COHORT_SHA256 = (
    "3bbcc74fee209cee521ce6ee85ef87f3ed13df2d202cb1f96effb02274b48546"
)
FIELD_STATE_REPORT = (
    ROOT
    / "quality/qualifications/mbs-workbook-field-state-reconciliation-20261025.json"
)
FIELD_STATE_SHA256 = (
    "9cf68711d80142d248bea04eb6ef62c1a768e116891e10c1208a07249bd1481d"
)
MAX_MEMBER_PATH_BYTES = 1024 * 1024


def _read_bound(path: Path, expected_sha256: str) -> dict:
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError(f"bound input digest differs: {path.name}")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError(f"bound input report malformed: {path.name}")
    return value


def _inputs() -> tuple[  # ruff: ignore[too-many-branches] -- bind all qualified MBS reports and identities
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    header = _read_bound(HEADER_REPORT, HEADER_SHA256)
    cohort = _read_bound(COHORT_REPORT, COHORT_SHA256)
    field_state = _read_bound(FIELD_STATE_REPORT, FIELD_STATE_SHA256)
    if (
        header.get("workbook_count") != WORKBOOK_COUNT
        or header.get("status") != "passed"
    ):
        raise ValueError("bound MBS header cohort differs")
    if (
        cohort.get("status") != "passed"
        or len(cohort.get("candidate_outputs_by_group", {})) != WORKBOOK_COUNT
    ):
        raise ValueError("bound MBS workbook candidate cohort differs")
    field_inputs = field_state.get("inputs", {})
    if (
        field_state.get("status")
        != "field_states_reconciled_with_semantic_limits"
        or field_inputs.get("header_cohort", {}).get("sha256") != HEADER_SHA256
        or field_inputs.get("package_cohort", {}).get("sha256") != COHORT_SHA256
        or field_state.get("historical_workbook_cohort", {}).get(
            "unique_candidate_identities"
        )
        != WORKBOOK_COUNT
    ):
        raise ValueError(
            "bound MBS field-state reconciliation identity differs"
        )
    assignments = header.get("workbook_assignments")
    if not isinstance(assignments, list) or len(assignments) != WORKBOOK_COUNT:
        raise ValueError("bound MBS workbook header assignments differ")
    profiles = header.get("header_profiles")
    if not isinstance(profiles, list):
        raise TypeError("bound MBS header profile groups are malformed")
    profile_by_digest = {
        row["header_profile_sha256"]: row["profile"]
        for row in profiles
        if isinstance(row, dict)
        and isinstance(row.get("header_profile_sha256"), str)
    }
    if len(profile_by_digest) != len(profiles):
        raise ValueError("bound MBS header profile identities differ")
    by_member: dict[str, dict] = {}
    for row in assignments:
        if (
            not isinstance(row, dict)
            or row.get("header_profile_sha256") not in profile_by_digest
        ):
            raise ValueError("bound MBS workbook assignment profile differs")
        key = row.get("member_path_sha256")
        if not isinstance(key, str) or key in by_member:
            raise ValueError("bound MBS workbook path identity differs")
        by_member[key] = {
            **row,
            "profile": profile_by_digest[row["header_profile_sha256"]],
        }
    outputs: dict[str, dict] = {}
    for group, candidate in cohort["candidate_outputs_by_group"].items():
        if not isinstance(candidate, dict):
            raise TypeError("bound MBS candidate output malformed")
        key = candidate.get("member_path_sha256")
        if not isinstance(key, str) or key in outputs:
            raise ValueError("bound MBS candidate member identity differs")
        outputs[key] = {**candidate, "candidate_group": int(group)}
    if set(outputs) != set(by_member):
        raise ValueError("MBS header and candidate member identities differ")
    return header, cohort, field_state, by_member, outputs


def _lookup(
    archive: ZipFile, members: tuple[FrozenMbsMember, ...]
) -> dict[str, tuple[ZipInfo, str]]:
    result: dict[str, tuple[ZipInfo, str]] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        native = PurePosixPath(info.filename.replace("\\", "/")).as_posix()
        if len(native.encode()) > MAX_MEMBER_PATH_BYTES:
            raise ValueError("MBS archive member path exceeds bound")
        key = hashlib.sha256(native.encode()).hexdigest()
        if key in result:
            raise ValueError("MBS archive member path identity duplicated")
        result[key] = (info, native)
    if set(result) != {member.path_sha256 for member in members}:
        raise ValueError("MBS frozen archive member inventory differs")
    return result


def _source_record(source: BoundArchive) -> dict:
    return {
        "source_id": source.source_id,
        "source_path": source.source_path,
        "source_sha256": source.source_sha256,
        "source_bytes": source.source_bytes,
        "acquisition_id": source.acquisition_id,
        "b1_sha256": source.b1_sha256,
        "b2_sha256": source.b2_sha256,
    }


def qualify(  # ruff: ignore[too-many-branches, too-many-locals, too-many-statements] -- bounded one-archive source readback and aggregate receipt
    exact_commit: str,
    archive_index: int,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    """Download a frozen archive transiently and emit shape counts only."""
    require_main_actions(exact_commit)
    _, _, _, assignments, outputs = _inputs()
    archives = load_archives(ROOT)
    if (
        len(archives) != ARCHIVE_COUNT
        or type(archive_index) is not int
        or not 0 <= archive_index < ARCHIVE_COUNT
    ):
        raise ValueError("MBS frozen archive cohort differs")
    source = archives[archive_index]
    if source.dataset != DATASET or source.revision != REVISION:
        raise ValueError("MBS source archive revision differs")
    frozen_members = tuple(
        member
        for member in load_frozen_members(ROOT)
        if member.source == source
    )
    workbook_members = tuple(
        member for member in frozen_members if member.suffix == ".xlsx"
    )
    policy = AcquisitionPolicy(
        allowed_hosts=HOSTS,
        timeout_seconds=120,
        max_bytes=archive_policy(source).max_archive_bytes,
        max_attempts=1,
        max_redirects=3,
    )
    workbook_reports: list[dict] = []
    totals = {
        field: {
            "cell_count": 0,
            "value_shapes": {},
            "native_cell_types": {},
            "native_states": {},
            "formula_cells": 0,
            "formula_cells_with_cache": 0,
            "source_error_cells": 0,
            "native_missing_value_cells": 0,
            "missing_physical_cell_positions": 0,
        }
        for field in EXPECTED_FIELDS
    }
    counters = dict.fromkeys(
        (
            "source_cell_records",
            "header_cells",
            "pre_header_cells",
            "other_sheet_cells",
            "out_of_contract_data_cells",
            "data_rows",
        ),
        0,
    )
    if workbook_members:  # ruff: ignore[too-many-nested-blocks] -- source archive lifetime encloses streamed member validation
        with (
            TemporaryDirectory(prefix="mbs-workbook-value-shape-") as temp,
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
                lookup = _lookup(archive, frozen_members)
                for member in workbook_members:
                    binding = assignments.get(member.path_sha256)
                    candidate = outputs.get(member.path_sha256)
                    if binding is None or candidate is None:
                        raise ValueError(
                            "MBS workbook candidate binding is absent"
                        )
                    if (
                        binding["member_sha256"],
                        binding["member_bytes"],
                        binding["source_sha256"],
                    ) != (
                        member.sha256,
                        member.byte_count,
                        source.source_sha256,
                    ):
                        raise ValueError(
                            "MBS workbook header/source identity differs"
                        )
                    info, native = lookup[member.path_sha256]
                    if info.file_size != member.byte_count:
                        raise ValueError(
                            "MBS workbook member byte count differs"
                        )
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
                        profile = profile_workbook_records(
                            iter_workbook_records(path, member, native),
                            binding["profile"],
                        )
                        for field in EXPECTED_FIELDS:
                            for name, value in profile["fields"][field].items():
                                if isinstance(value, int):
                                    totals[field][name] += value
                                elif isinstance(value, dict):
                                    counter = totals[field][name]
                                    if not isinstance(counter, dict):
                                        raise TypeError(
                                            "MBS field counter shape differs"
                                        )
                                    for key, count in value.items():
                                        counter[key] = (
                                            counter.get(key, 0) + count
                                        )
                        for name in counters:
                            counters[name] += profile[name]
                        workbook_reports.append({
                            "candidate_group": candidate["candidate_group"],
                            "candidate_output_id": candidate["output_id"],
                            "candidate_parquet_sha256": candidate[
                                "parquet_sha256"
                            ],
                            "candidate_parquet_bytes": candidate[
                                "parquet_bytes"
                            ],
                            "member_sha256": member.sha256,
                            "member_path_sha256": member.path_sha256,
                            "member_bytes": member.byte_count,
                            "header_profile_sha256": binding[
                                "header_profile_sha256"
                            ],
                            "source_sha256": source.source_sha256,
                            "profile": profile,
                        })
                    finally:
                        if path.exists():
                            path.chmod(0o600)
                            path.unlink()
            require_public_archive_revision(client)
    return {
        "schema_id": "global-medicines-atlas.mbs-historical-workbook-value-shapes",
        "schema_version": 1,
        "status": "passed",
        "workflow_commit": exact_commit,
        "dataset": DATASET,
        "revision": REVISION,
        "archive_index": archive_index,
        "source": _source_record(source),
        "input_report_digests": {
            "header_cohort_sha256": HEADER_SHA256,
            "candidate_cohort_sha256": COHORT_SHA256,
            "field_state_sha256": FIELD_STATE_SHA256,
        },
        "expected_workbook_count": len(workbook_members),
        "workbook_count": len(workbook_reports),
        "workbook_bindings": sorted(
            workbook_reports, key=operator.itemgetter("candidate_group")
        ),
        **counters,
        "fields": totals,
        "source_values_emitted": False,
        "source_column_meanings_qualified": False,
        "currency_interpreted": False,
        "date_interpreted": False,
        "new_sources": 0,
        "new_admissions": 0,
        "consumer_canaries": 0,
        "publications": 0,
    }


def _write(output: Path, report: dict) -> None:
    payload = (
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    if len(payload) > MAX_REPORT_BYTES:
        raise ValueError("MBS value-shape report exceeds byte bound")
    if output.exists() or output.is_symlink():
        raise FileExistsError(
            "existing MBS value-shape report must be preserved"
        )
    output.write_bytes(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--archive-index", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = qualify(args.exact_commit, args.archive_index)
    except Exception as error:
        report = {
            "schema_version": 1,
            "status": "failed",
            "archive_index": args.archive_index,
            "failure_category": classify_inventory_failure(error),
            "source_values_emitted": False,
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
