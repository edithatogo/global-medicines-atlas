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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--exact-commit", required=True)
    args = parser.parse_args(argv)
    try:
        reports = _read_reports(args.receipts)
        report = aggregate_shards(reports, expected_commit=args.exact_commit)
    except KeyError, TypeError, ValueError, json.JSONDecodeError:
        report = {
            "schema_version": 1,
            "status": "incomplete",
            "reason": "projection-shards-incomplete-or-inconsistent",
            "publication_performed": False,
        }
    _write(args.output, report)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
