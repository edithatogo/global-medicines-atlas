"""Guard the exact-copy P7 date-profile reconciliation and its limits."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = (
    ROOT
    / "quality/qualifications/mbs-p7-date-profile-reconciliation-20261025.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_p7_date_profile_reconciliation_is_digest_bound_and_conversion_stays_disabled() -> (
    None
):
    report: dict[str, Any] = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    asserted_report_sha256 = report["report_sha256"]
    payload = json.dumps(
        {key: value for key, value in report.items() if key != "report_sha256"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert asserted_report_sha256 == hashlib.sha256(payload).hexdigest()
    assert report["status"] == (
        "internal_exact_copy_dmy_inference_reconciled_conversion_disabled"
    )
    assert report["source"]["sha256"] == (
        "2f1cbc2d2dcbb93be86f42c8dbbe9f5f9e8fb550cad38b6ee54d0e9bdd2e27b8"
    )

    reconciliation = report["reconciliation"]
    assert reconciliation["inferred_profile"] == "mbs-dmy"
    assert reconciliation["inference_scope"] == (
        "internal_file_consistency_for_this_exact_donor_archived_copy_only"
    )
    assert reconciliation["evidence_counts"] == {
        "populated_date_fields": 4,
        "profiled_cells": 1280,
        "ambiguous_calendar_order_cells_before_inference": 1194,
        "unique_dmy_calendar_date_cells": 4,
        "unique_mdy_calendar_date_cells": 0,
        "unique_calendar_date_cells": 86,
    }

    limits = report["operational_limits"]
    assert limits["operational_date_conversion_enabled"] is False
    assert limits["source_owner_confirmation"] is False
    assert limits["official_provenance_confirmed"] is False
    assert limits["domain_date_meaning_qualified"] is False
    assert limits["temporal_comparison_enabled"] is False
    assert limits["cross_era_equivalence_promoted"] is False

    evidence = [
        *reconciliation["prior_unselected_reports"],
        *report["supporting_evidence"],
    ]
    for item in evidence:
        evidence_path = ROOT / item["path"]
        assert _sha256(evidence_path) == item["sha256"]
