"""Aggregate bounded PBS projection receipts without reading source bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.pbs_qualification_aggregate import aggregate_shards


def _write(output: Path, report: dict[str, Any]) -> None:
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    envelope = {
        "report": report,
        "report_sha256": hashlib.sha256(payload).hexdigest(),
    }
    output.write_text(
        json.dumps(envelope, sort_keys=True) + "\n", encoding="utf-8"
    )


def _read_reports(path: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for receipt in sorted(path.glob("**/pbs-*-receipt.json")):
        envelope: object = json.loads(receipt.read_text(encoding="utf-8"))
        if not isinstance(envelope, dict):
            raise TypeError("invalid shard receipt")
        checked = cast("dict[str, object]", envelope)
        raw_report = checked.get("report")
        if not isinstance(raw_report, dict):
            raise TypeError("invalid shard receipt")
        report = cast("dict[str, Any]", raw_report)
        canonical = json.dumps(
            report, sort_keys=True, separators=(",", ":")
        ).encode()
        if (
            checked.get("report_sha256")
            != hashlib.sha256(canonical).hexdigest()
        ):
            raise ValueError("shard receipt digest changed")
        reports.append(report)
    return reports


def _shard_id(report: dict[str, Any]) -> str | None:
    projection = report.get("projection_shard")
    qualification = report.get("qualification")
    if projection is None and isinstance(qualification, dict):
        qualification = cast("dict[str, Any]", qualification)
        projection = qualification.get("projection_shard")
    if projection in {"native", "domain", "entities", "dates"}:
        return cast("str", projection)
    shard = report.get("reference_shard")
    if projection == "references" and type(shard) is int and shard >= 0:
        return f"references:{shard}"
    if isinstance(qualification, dict):
        qualification = cast("dict[str, Any]", qualification)
        window = qualification.get("reference_window")
        if projection == "references" and isinstance(window, dict):
            window = cast("dict[str, Any]", window)
            index = window.get("index")
            if type(index) is int and index >= 0:
                return f"references:{index}"
    return None


def _coverage(
    reports: list[dict[str, Any]], reference_shards: int
) -> tuple[list[str], list[str]]:
    expected = [
        "native",
        "domain",
        "entities",
        "dates",
        *(f"references:{index}" for index in range(reference_shards)),
    ]
    observed: dict[str, list[dict[str, Any]]] = {}
    for report in reports:
        identity = _shard_id(report)
        if identity is not None:
            observed.setdefault(identity, []).append(report)
    missing = [identity for identity in expected if identity not in observed]
    failed = [
        identity
        for identity in expected
        if len(observed.get(identity, ())) != 1
        or observed[identity][0].get("status") != "passed"
    ]
    return missing, failed


def _aggregate_complete(
    reports: list[dict[str, Any]], exact_commit: str, reference_shards: int
) -> dict[str, Any]:
    missing, failed = _coverage(reports, reference_shards)
    if missing or failed:
        raise ValueError("shard coverage is incomplete")
    return aggregate_shards(reports, expected_commit=exact_commit)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--reference-shards", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        reports = _read_reports(args.receipts)
        report = _aggregate_complete(
            reports, args.exact_commit, args.reference_shards
        )
    except KeyError, TypeError, ValueError, json.JSONDecodeError:
        reports = locals().get("reports", [])
        missing, failed = _coverage(reports, args.reference_shards)
        report = {
            "schema_version": 1,
            "status": "incomplete",
            "reason": "projection-shards-incomplete-or-inconsistent",
            "missing_shard_ids": missing,
            "failed_shard_ids": failed,
            "publication_performed": False,
        }
    _write(args.output, report)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
