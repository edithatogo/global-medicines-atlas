"""Bind a completed exact-main PBS URI screen to retained value-free context."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

from global_medicines_atlas.pbs_uri_context_enrichment import (
    enrich_uri_review_packet,
)
from global_medicines_atlas.pbs_uri_review_packet_reconciler import (
    PACKET_FILENAME,
    ReconciliationError,
    reconcile_uri_review_packet,
    write_new_envelope,
)

CONTEXT_SCREEN_FILENAME = (
    "pbs-native-reference-screen-20261025-40103169910.json"
)
REVIEW_CASE_COUNT = 46
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")


def _read(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ReconciliationError("evidence envelope is invalid")
    return cast("dict[str, Any]", value), hashlib.sha256(raw).hexdigest()


def qualify_context(  # ruff: ignore[too-many-locals] -- bind the three immutable inputs and two outputs together
    *,
    root: Path,
    uri_receipt_path: Path,
    expected_uri_receipt_sha256: str,
    expected_uri_run_id: str,
    expected_uri_run_attempt: str,
    expected_commit: str,
    integration_run_id: str,
    integration_commit: str,
    context_packet_output: Path,
    qualification_receipt_output: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reconcile and enrich 46 cases without emitting values or semantics."""
    if not _SHA256.fullmatch(expected_uri_receipt_sha256):
        raise ReconciliationError("URI receipt digest is invalid")
    if (
        not expected_uri_run_id.isdecimal()
        or not expected_uri_run_attempt.isdecimal()
    ):
        raise ReconciliationError("URI run identity is invalid")
    if not _COMMIT.fullmatch(expected_commit):
        raise ReconciliationError("exact source commit is invalid")
    if not _COMMIT.fullmatch(integration_commit):
        raise ReconciliationError("integration workflow commit is invalid")
    if not integration_run_id.isdecimal():
        raise ReconciliationError("context qualification run ID is invalid")

    qualifications = root / "quality/qualifications"
    packet_path = qualifications / PACKET_FILENAME
    context_screen_path = qualifications / CONTEXT_SCREEN_FILENAME
    packet, packet_sha = _read(packet_path)
    context_screen, context_screen_sha = _read(context_screen_path)
    uri_receipt, uri_receipt_sha = _read(uri_receipt_path)
    if uri_receipt_sha != expected_uri_receipt_sha256:
        raise ReconciliationError("URI receipt file digest differs")
    uri_report = cast("dict[str, Any]", uri_receipt.get("report", {}))
    if uri_report.get("run_attempt") != expected_uri_run_attempt:
        raise ReconciliationError("URI run attempt differs")

    reconciliation = reconcile_uri_review_packet(
        packet_path,
        uri_receipt_path,
        expected_run_id=expected_uri_run_id,
        expected_commit=expected_commit,
        expected_uri_receipt_sha256=expected_uri_receipt_sha256,
    )
    context_packet = enrich_uri_review_packet(
        packet,
        context_screen,
        reconciliation,
        packet_file_sha256=packet_sha,
        screen_file_sha256=context_screen_sha,
    )
    context_report = cast("dict[str, Any]", context_packet["report"])
    packet_contract = {
        "uri_run_id": expected_uri_run_id,
        "uri_workflow_commit": expected_commit,
        "uri_receipt_sha256": expected_uri_receipt_sha256,
        "source_values_emitted": False,
        "semantic_relationships_qualified": False,
        "edges_emitted": False,
        "case_count": REVIEW_CASE_COUNT,
        "context_examples_bound": REVIEW_CASE_COUNT,
    }
    if any(
        context_report.get(key) != value
        for key, value in packet_contract.items()
    ):
        raise ReconciliationError("enriched packet binding differs")
    cases = cast("list[dict[str, Any]]", context_report["cases"])
    if any(
        case.get("adjudication") != "unreviewed"
        or case.get("semantic_review_state") != "pending"
        or case.get("semantic_relationship_qualified") is not False
        for case in cases
    ):
        raise ReconciliationError("enriched case review state differs")

    packet_bytes = (
        json.dumps(context_packet, sort_keys=True, indent=2, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    context_packet_output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with context_packet_output.open("xb") as stream:
            stream.write(packet_bytes)
    except FileExistsError as exc:
        raise ReconciliationError(
            "existing context packet must be preserved"
        ) from exc
    packet_file_sha = hashlib.sha256(packet_bytes).hexdigest()

    receipt_report = {
        "schema_id": "global-medicines-atlas.pbs-uri-context-qualification",
        "schema_version": 1,
        "status": "passed",
        "integration_run_id": integration_run_id,
        "integration_workflow_commit": integration_commit,
        "source_packet_file": PACKET_FILENAME,
        "source_packet_sha256": packet_sha,
        "context_screen_file": CONTEXT_SCREEN_FILENAME,
        "context_screen_run_id": context_screen["report"]["run_id"],
        "context_screen_workflow_commit": context_screen["report"][
            "workflow_commit"
        ],
        "context_screen_receipt_sha256": context_screen_sha,
        "uri_run_id": expected_uri_run_id,
        "uri_run_attempt": expected_uri_run_attempt,
        "uri_workflow_commit": expected_commit,
        "uri_receipt_file_sha256": uri_receipt_sha,
        "uri_reconciliation_report_sha256": reconciliation["report_sha256"],
        "context_packet_file": context_packet_output.name,
        "context_packet_file_sha256": packet_file_sha,
        "context_packet_report_sha256": context_packet["report_sha256"],
        "case_count": REVIEW_CASE_COUNT,
        "cases_reviewed": 0,
        "semantic_relationships_qualified": False,
        "edges_emitted": False,
        "precision_claimed": False,
        "recall_claimed": False,
        "source_values_emitted": False,
        "external_targets_fetched": 0,
        "new_sources_added": 0,
        "admissions_created": 0,
        "canaries_performed": 0,
        "publication_performed": False,
    }
    canonical = json.dumps(
        receipt_report,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    qualification_receipt = {
        "report": receipt_report,
        "report_sha256": hashlib.sha256(canonical).hexdigest(),
    }
    write_new_envelope(qualification_receipt, qualification_receipt_output)
    return context_packet, qualification_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--uri-receipt", type=Path, required=True)
    parser.add_argument("--expected-uri-receipt-sha256", required=True)
    parser.add_argument("--expected-uri-run-id", required=True)
    parser.add_argument("--expected-uri-run-attempt", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--integration-run-id", required=True)
    parser.add_argument("--integration-commit", required=True)
    parser.add_argument("--context-packet-output", type=Path, required=True)
    parser.add_argument(
        "--qualification-receipt-output", type=Path, required=True
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    uri_receipt = (
        args.uri_receipt
        if args.uri_receipt.is_absolute()
        else root / args.uri_receipt
    )
    try:
        qualify_context(
            root=root,
            uri_receipt_path=uri_receipt.resolve(),
            expected_uri_receipt_sha256=args.expected_uri_receipt_sha256,
            expected_uri_run_id=args.expected_uri_run_id,
            expected_uri_run_attempt=args.expected_uri_run_attempt,
            expected_commit=args.expected_commit,
            integration_run_id=args.integration_run_id,
            integration_commit=args.integration_commit,
            context_packet_output=(
                args.context_packet_output
                if args.context_packet_output.is_absolute()
                else root / args.context_packet_output
            ),
            qualification_receipt_output=(
                args.qualification_receipt_output
                if args.qualification_receipt_output.is_absolute()
                else root / args.qualification_receipt_output
            ),
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        ReconciliationError,
    ) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
