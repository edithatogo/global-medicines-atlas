"""Resolve only bounded, source-local PBS URI candidates on GitHub Actions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.pbs_hosted_qualification import (
    DATASET,
    RECEIPT,
    REVISION,
    _RetryBudget,  # ruff: ignore[import-private-name] -- reuse exact verified-input route  # pyright: ignore[reportPrivateUsage]
    _verified_inputs,  # ruff: ignore[import-private-name] -- reuse exact verified-input route  # pyright: ignore[reportPrivateUsage]
    failure_report,
)
from global_medicines_atlas.pbs_native_uri_screen import screen_pbs_native_uris

REVIEW_PACKET = (
    Path(__file__).parents[1]
    / "quality/qualifications/pbs-native-reference-review-packet-20261025-40103169910.json"
)
EXPECTED_REVIEW_CASES = 46


def load_review_cases(
    member_sha256: str,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Load only the pinned value-free case addresses for a matching member."""
    packet_bytes = REVIEW_PACKET.read_bytes()
    packet = cast("dict[str, Any]", json.loads(packet_bytes))
    report = cast("dict[str, Any]", packet.get("report", {}))
    source = cast("dict[str, Any]", report.get("source", {}))
    if (
        report.get("schema_id")
        != "global-medicines-atlas.pbs-reference-review-packet"
        or report.get("schema_version") != 1
        or source.get("member_sha256") != member_sha256
        or source.get("revision") != REVISION
        or source.get("dataset") != DATASET
    ):
        raise ValueError("pinned PBS reference review packet binding differs")
    calibration = cast("dict[str, Any]", report.get("calibration", {}))
    if (
        calibration.get("source_cases_reviewed") != 0
        or calibration.get("semantic_relationships_qualified") is not False
    ):
        raise ValueError("pinned PBS reference calibration state differs")
    cases_value = report.get("cases")
    if not isinstance(cases_value, list):
        raise TypeError("pinned PBS reference review cases must be a list")
    cases = cast("list[object]", cases_value)
    if len(cases) != EXPECTED_REVIEW_CASES:
        raise ValueError("pinned PBS reference review case count differs")
    selected: list[dict[str, str]] = []
    for case_value in cases:
        if not isinstance(case_value, dict):
            raise TypeError(
                "pinned PBS reference review case must be an object"
            )
        case = cast("dict[str, Any]", case_value)
        if (
            case.get("uri_resolution") != "not_performed"
            or case.get("adjudication") != "unreviewed"
            or case.get("semantic_relationship_qualified") is not False
        ):
            raise ValueError("pinned PBS reference review case differs")
        if not isinstance(case.get("case_id"), str) or not isinstance(
            case.get("reference_occurrence"), str
        ):
            raise TypeError("pinned PBS reference case identity must be text")
        selected.append({
            "case_id": case["case_id"],
            "reference_occurrence": case["reference_occurrence"],
        })
    return selected, {
        "packet_file": REVIEW_PACKET.name,
        "packet_file_sha256": hashlib.sha256(packet_bytes).hexdigest(),
        "packet_screen_run_id": source["screen_run_id"],
        "packet_screen_receipt_sha256": source["screen_receipt_sha256"],
        "packet_case_count": len(selected),
        "packet_cases_reviewed": 0,
    }


if __package__:
    from scripts.qualify_historical_pbs_public import (
        write_qualification_receipt,
    )
else:
    from qualify_historical_pbs_public import write_qualification_receipt


def run(exact_commit: str, output: Path) -> dict[str, Any]:
    """Verify the pinned B1/B2/member inputs, then retain URI aggregates only."""
    latest: dict[str, Any] = {}

    def checkpoint(report: dict[str, Any]) -> None:
        nonlocal latest
        latest = write_qualification_receipt(output, report)

    retry = _RetryBudget(progress=checkpoint)
    inputs: Any | None = None
    try:
        inputs = _verified_inputs(exact_commit, transport=None, retry=retry)
        review_cases, review_packet = load_review_cases(
            inputs.binding.member_payload.sha256
        )
        qualification = screen_pbs_native_uris(
            inputs.xml,
            review_cases=review_cases,
            progress=lambda _phase, batches, rows: retry.checkpoint(
                "projection-qualification",
                "native-reference-match",
                batches,
                rows,
            ),
        )
        report = {
            "schema_id": "global-medicines-atlas.pbs-native-uri-screen",
            "schema_version": 1,
            "status": "passed",
            **inputs.context,
            "operation": "pbs-native-uri-screen",
            "dataset": DATASET,
            "revision": REVISION,
            "archive_sha256": inputs.binding.archive_payload.sha256,
            "archive_size_bytes": inputs.binding.archive_payload.byte_count,
            "member_path": inputs.binding.member_path,
            "member_sha256": inputs.binding.member_payload.sha256,
            "member_size_bytes": inputs.binding.member_payload.byte_count,
            "source_receipt_sha256": inputs.parent.digest(),
            "source_receipt_file_sha256": RECEIPT.sha256,
            "qualification": qualification,
            "review_packet_binding": review_packet,
            "uri_resolution_performed": True,
            "semantic_relationships_qualified": False,
            "source_values_emitted": False,
            "external_targets_fetched": 0,
            "admissions_created": 0,
            "publication_performed": False,
            "canaries_performed": 0,
            "new_sources_added": 0,
        }
    except Exception as error:
        report = failure_report(error)
        report.update({
            "schema_id": "global-medicines-atlas.pbs-native-uri-screen",
            "schema_version": 1,
            "operation": "pbs-native-uri-screen",
            "uri_resolution_performed": False,
            "semantic_relationships_qualified": False,
            "source_values_emitted": False,
            "external_targets_fetched": 0,
            "admissions_created": 0,
            "publication_performed": False,
            "canaries_performed": 0,
            "new_sources_added": 0,
        })
        if inputs is not None:
            report.update({
                **inputs.context,
                "dataset": DATASET,
                "revision": REVISION,
                "archive_sha256": inputs.binding.archive_payload.sha256,
                "archive_size_bytes": inputs.binding.archive_payload.byte_count,
                "member_path": inputs.binding.member_path,
                "member_sha256": inputs.binding.member_payload.sha256,
                "member_size_bytes": inputs.binding.member_payload.byte_count,
                "source_receipt_sha256": inputs.parent.digest(),
                "source_receipt_file_sha256": RECEIPT.sha256,
            })
        if "progress" in latest:
            report["progress"] = latest["progress"]
    return write_qualification_receipt(output, report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("existing receipt must be preserved")
    report = run(args.exact_commit, args.output)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
