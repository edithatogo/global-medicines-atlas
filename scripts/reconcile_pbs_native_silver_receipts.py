"""Bind aggregate PBS native package and source-local screen without values.

Every retained field remains a source observation with unresolved domain meaning.
Exact lexical reference matches remain candidates, not reviewed relationships.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from global_medicines_atlas.mbs_historical_csv_package import (
    canonical_package_json,
)
from global_medicines_atlas.pbs_hosted_qualification import DATASET, REVISION

MAX_RECEIPT_BYTES = 1_000_000
MAX_PARQUET_BYTES = 4 * 1024**3
SHA256_HEX_LENGTH = 64
PACKAGE_SCHEMA_VERSION = 2
SERIALIZATION_BUILDS = 2


def _digest(value: str) -> bool:
    return len(value) == SHA256_HEX_LENGTH and all(
        char in "0123456789abcdef" for char in value
    )


def _envelope(path: Path) -> tuple[dict[str, Any], str]:
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > MAX_RECEIPT_BYTES
    ):
        raise ValueError("PBS aggregate receipt file is invalid")
    raw = path.read_bytes()
    envelope = json.loads(raw)
    report = envelope["report"]
    encoded = json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(encoded).hexdigest() != envelope["report_sha256"]:
        raise ValueError("PBS aggregate receipt envelope digest differs")
    return report, hashlib.sha256(raw).hexdigest()


def reconcile(package_path: Path, screen_path: Path) -> dict[str, Any]:
    """Require the exact native field denominator across independent receipts."""
    package_report, package_receipt_sha = _envelope(package_path)
    screen_report, screen_receipt_sha = _envelope(screen_path)
    if (
        package_report["status"] != "passed"  # ruff: ignore[too-many-boolean-expressions] -- both receipt identities are mandatory
        or screen_report["status"] != "passed"
        or package_report["dataset"] != DATASET
        or screen_report["dataset"] != DATASET
        or package_report["revision"] != REVISION
        or screen_report["revision"] != REVISION
        or screen_report["operation"] != "pbs-native-reference-screen"
    ):
        raise ValueError("PBS native receipt status or source differs")
    package_run = package_report["qualification"]
    screen = screen_report["qualification"]
    manifest = package_run["package"]
    identity = {
        key: value for key, value in manifest.items() if key != "output_id"
    }
    output_id = hashlib.sha256(canonical_package_json(identity)).hexdigest()
    boundaries = manifest["boundaries"]
    coverage = manifest["coverage"]
    parquet = manifest["parquet"]
    member = manifest["member_binding"]
    if (
        manifest["schema_id"]  # ruff: ignore[too-many-boolean-expressions] -- every exact package boundary is mandatory
        != "global-medicines-atlas.pbs-native-value-package"
        or manifest["schema_version"] != PACKAGE_SCHEMA_VERSION
        or manifest["candidate_only"] is not True
        or manifest["output_id"] != output_id
        or any(boundaries.values())
        or package_run["serialization_builds"] != SERIALIZATION_BUILDS
        or package_run["independent_pipeline_builds"] is not False
        or package_run["parquet_bytes_identical"] is not True
        or package_run["complete_source_reparse_and_restore"] is not True
        or package_run["temporary_derivatives_removed"] is not True
        or package_run["new_admissions"] != 0
        or package_run["publications"] != 0
        or package_report["publication_performed"] is not False
        or screen_report["publication_performed"] is not False
        or screen_report["rights_conclusion_changed"] is not False
    ):
        raise ValueError("PBS native package qualification differs")
    if (
        manifest["member_binding_sha256"]  # ruff: ignore[too-many-boolean-expressions] -- compare every fixed B1/B2 binding
        != screen["member_binding_sha256"]
        or manifest["parent_receipt_sha256"] != screen["parent_receipt_sha256"]
        or member["member_payload"]["sha256"] != screen["member_sha256"]
        or member["archive_payload"]["sha256"] != screen["archive_sha256"]
        or coverage["native_fields"] != screen["native_fields"]
        or package_report["source_receipt_file_sha256"]
        != screen_report["source_receipt_file_sha256"]
        or not _digest(coverage["native_core_sha256"])
        or not _digest(parquet["sha256"])
        or type(parquet["bytes"]) is not int
        or not 0 < parquet["bytes"] <= MAX_PARQUET_BYTES
        or package_run["restored_file_digest"] != parquet
    ):
        raise ValueError("PBS native package and screen identity differs")
    counts = screen["reference_status_counts"]
    if (
        sum(counts.values())  # ruff: ignore[too-many-boolean-expressions] -- complete lexical denominator with no promotion
        != screen["reference_fields"]
        or sum(coverage["mapping_targets"].values()) != coverage["entities"]
        or sum(coverage["conversion_statuses"].values()) != coverage["entities"]
        or screen["native_values_emitted"] is not False
        or screen["semantic_relationships_qualified"] is not False
        or screen["domain_semantics_qualified"] is not False
        or screen["external_targets_fetched"] != 0
        or screen["new_sources"] != 0
        or screen["new_admissions"] != 0
        or screen["publications"] != 0
    ):
        raise ValueError("PBS native field or reference denominator differs")
    return {
        "schema_id": "global-medicines-atlas.pbs-native-silver-reconciliation",
        "schema_version": 1,
        "status": "passed",
        "package_run_id": package_report["run_id"],
        "package_workflow_commit": package_report["workflow_commit"],
        "package_receipt_sha256": package_receipt_sha,
        "screen_run_id": screen_report["run_id"],
        "screen_workflow_commit": screen_report["workflow_commit"],
        "screen_receipt_sha256": screen_receipt_sha,
        "dataset": DATASET,
        "revision": REVISION,
        "candidate_output": {
            "output_id": output_id,
            "parquet_sha256": parquet["sha256"],
            "parquet_bytes": parquet["bytes"],
            "archive_sha256": screen["archive_sha256"],
            "member_sha256": screen["member_sha256"],
            "native_core_sha256": coverage["native_core_sha256"],
            "candidate_only": True,
            "rights_qualified": False,
            "admitted": False,
            "published": False,
        },
        "field_state_coverage": {
            "source_fields": coverage["native_fields"],
            "native_unresolved_fields": coverage["native_fields"],
            "interpreted_fields": 0,
            "unavailable_patient_rates": True,
        },
        "source_local_reference_screen": {
            "definition_fields": screen["definition_fields"],
            "reference_fields": screen["reference_fields"],
            "ambiguous_definition_literals": screen[
                "ambiguous_definition_literals"
            ],
            "reference_status_counts": counts,
            "comparison": screen["comparison"],
            "semantic_relationships_qualified": False,
        },
        "domain_semantics_qualified": False,
        "new_sources": 0,
        "new_admissions": 0,
        "publications": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-receipt", type=Path, required=True)
    parser.add_argument("--screen-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("existing PBS reconciliation must be preserved")
    report = reconcile(args.package_receipt, args.screen_receipt)
    args.output.write_bytes(canonical_package_json(report) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
