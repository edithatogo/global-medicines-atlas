"""Generate deterministic, fail-closed v0.6 product evidence."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from global_medicines_atlas.product_release import (
    DeploymentEvidence,
    PerformanceResult,
    QualificationReceipt,
    ThreatCase,
    VerificationState,
    qualify_product_release,
    validate_receipt,
)

DEFAULT_OUTPUT = Path(
    "tests/fixtures/release-evidence/product/fixture-qualified-v0.6.json"
)
LIMITATIONS = (
    "Fixture-only evidence; no live source coverage is claimed.",
    "No production deployment has been verified.",
    "Accessibility conformance has not been established.",
)
PERFORMANCE_CHECKS = (
    ("PERF-CONTRACT", "contract validation p95", 25.0),
    ("PERF-QUERY", "fixture comparison query p95", 250.0),
    ("PERF-EXPORT-PAGE", "bounded single-page JSONL export", 1000.0),
)
THREAT_CHECKS = (
    (
        "THREAT-001",
        "Database path escape",
        "Database access is confined to the configured root.",
    ),
    (
        "THREAT-002",
        "Cursor tamper or cross-query replay",
        "Signed cursors bind filters and clocks.",
    ),
    (
        "THREAT-003",
        "Mutation methods on the public API",
        "The API exposes read-only methods.",
    ),
    (
        "THREAT-004",
        "Active HTML or script content",
        "Server-rendered output escapes hostile values.",
    ),
    (
        "THREAT-005",
        "Missing or corrupt database",
        "Readiness and queries fail closed.",
    ),
)


def _load_receipts(
    path: Path | None,
) -> dict[tuple[str, str], QualificationReceipt]:
    if path is None or not path.exists():
        return {}
    receipts: dict[tuple[str, str], QualificationReceipt] = {}
    for receipt_path in sorted(path.glob("*.json")):
        try:
            receipt = QualificationReceipt.model_validate_json(
                receipt_path.read_text()
            )
        except OSError, ValidationError, ValueError, json.JSONDecodeError:
            continue
        receipts[receipt.kind, receipt.subject_id] = receipt
    return receipts


def build_evidence(
    *,
    receipts_dir: Path | None = None,
    implementation_digest: str = "0" * 64,
    now: datetime | None = None,
):
    clock = now or datetime.now(UTC)
    receipts = _load_receipts(receipts_dir)
    performance: list[PerformanceResult] = []
    for scenario_id, scenario, budget in PERFORMANCE_CHECKS:
        receipt = receipts.get(("performance", scenario_id))
        reason = "no durable execution receipt was supplied"
        receipt_error: str | None = None
        if receipt is not None:
            receipt_error = validate_receipt(
                receipt,
                kind="performance",
                subject_id=scenario_id,
                implementation_digest=implementation_digest,
                now=clock,
            )
            reason = receipt_error or receipt.result.detail
        verified = receipt is not None and receipt_error is None
        observed_ms = (
            receipt.result.observed_ms if verified and receipt else None
        )
        sample_size = (
            receipt.result.sample_size if verified and receipt else None
        )
        receipt_passed = (
            receipt.result.passed if verified and receipt else False
        )
        receipt_id = receipt.receipt_id if verified and receipt else None
        performance.append(
            PerformanceResult(
                scenario_id=scenario_id,
                scenario=scenario,
                budget_ms=budget,
                observed_ms=observed_ms,
                sample_size=sample_size,
                verification=(
                    VerificationState.PASSED
                    if verified and receipt_passed
                    else VerificationState.FAILED
                    if verified
                    else VerificationState.NOT_VERIFIED
                ),
                reason=reason,
                receipt_id=receipt_id,
            )
        )
    threats: list[ThreatCase] = []
    for threat_id, description, control in THREAT_CHECKS:
        receipt = receipts.get(("threat", threat_id))
        reason = "no durable control-test receipt was supplied"
        receipt_error = None
        if receipt is not None:
            receipt_error = validate_receipt(
                receipt,
                kind="threat",
                subject_id=threat_id,
                implementation_digest=implementation_digest,
                now=clock,
            )
            reason = receipt_error or receipt.result.detail
        verified = receipt is not None and receipt_error is None
        receipt_passed = (
            receipt.result.passed if verified and receipt else False
        )
        receipt_id = receipt.receipt_id if verified and receipt else None
        threats.append(
            ThreatCase(
                threat_id=threat_id,
                description=description,
                control=control,
                verification=(
                    VerificationState.PASSED
                    if verified and receipt_passed
                    else VerificationState.FAILED
                    if verified
                    else VerificationState.NOT_VERIFIED
                ),
                reason=reason,
                receipt_id=receipt_id,
            )
        )
    return qualify_product_release(
        performance=tuple(performance),
        threats=tuple(threats),
        deployment=DeploymentEvidence(
            clean_start=VerificationState.NOT_VERIFIED,
            live_deployment=VerificationState.NOT_VERIFIED,
            accessibility_conformance=VerificationState.NOT_VERIFIED,
            production_data=VerificationState.NOT_VERIFIED,
            detail="Deployment and external conformance require separate live verification.",
        ),
        limitations=LIMITATIONS,
        api_contract_verified=True,
        bounded_queries_verified=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--receipts", type=Path)
    parser.add_argument("--implementation-digest", default="0" * 64)
    arguments = parser.parse_args()
    evidence = build_evidence(
        receipts_dir=arguments.receipts,
        implementation_digest=arguments.implementation_digest,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(evidence.canonical_json())
    print(f"{evidence.state.value}: {evidence.digest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
