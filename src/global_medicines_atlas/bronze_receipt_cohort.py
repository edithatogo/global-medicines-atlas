"""Build a bounded receipt-backed Bronze cohort without changing scope."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from html import escape
from pathlib import Path
from typing import Any, cast

from .bronze_maturity import (
    CATALOG_RELATIVE,
    LANDING_OVERRIDES_RELATIVE,
    classify_catalog_source,
    evaluate_repository,
    receipt_backed_landing_evidence,
)
from .bronze_maturity import HORIZON as CURRENT_SCOPE_HORIZON

QUEUE_RELATIVE = "quality/qualifications/bronze-source-landing-queue.json"
REPORT_RELATIVE = "quality/qualifications/bronze-receipt-cohort-v1.json"
SCHEMA_RELATIVE = "schemas/bronze-receipt-cohort-v1.json"
MARKDOWN_RELATIVE = "docs/qualification/bronze-future-source-list.md"
COHORT_ID = "bronze-receipt-backed-cohort-v1"
REENTRY_TRIGGER = (
    "Re-evaluate after a source-specific successful Bronze receipt is "
    "validated under the existing rights, credential, reuse, admission, "
    "and provenance gates. This ledger does not authorize acquisition."
)


def _read_json(root: Path, relative: str) -> Any:
    """Read a repository JSON input."""

    return json.loads((root / relative).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _defer_reason_code(queue_item: Mapping[str, Any]) -> str:
    """Describe why a source is outside this direct-receipt cohort."""

    evidence_scope = queue_item.get("evidence_scope")
    if evidence_scope == "governed_fixture":
        return "fixture_is_not_a_live_source_receipt"
    if evidence_scope == "parser_contract":
        return "parser_contract_is_not_a_source_receipt"
    if queue_item.get("state") == "landed_and_evidenced":
        return "queue_landing_not_confirmed_by_receipt_validator"
    return "no_qualifying_direct_receipt"


def _load_source_maps(
    root: Path,
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    """Load unique catalog and queue rows keyed by stable source ID."""

    catalog_doc = _read_json(root, CATALOG_RELATIVE)
    queue_doc = _read_json(root, QUEUE_RELATIVE)
    catalog_rows = catalog_doc.get("sources", [])
    queue_rows = queue_doc.get("items", [])
    if not isinstance(catalog_rows, list) or not isinstance(queue_rows, list):
        raise TypeError("catalog sources and queue items must be arrays")
    catalog_rows = cast("list[Any]", catalog_rows)
    queue_rows = cast("list[Any]", queue_rows)

    catalog: dict[str, Mapping[str, Any]] = {}
    for raw_source in catalog_rows:
        if not isinstance(raw_source, Mapping):
            raise TypeError("catalog source rows must be objects")
        source = cast("Mapping[str, Any]", raw_source)
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("catalog source rows require a source_id")
        if source_id in catalog:
            raise ValueError(f"duplicate catalog source ID: {source_id}")
        catalog[source_id] = source

    queue: dict[str, Mapping[str, Any]] = {}
    for raw_item in queue_rows:
        if not isinstance(raw_item, Mapping):
            raise TypeError("queue source rows must be objects")
        item = cast("Mapping[str, Any]", raw_item)
        source_id = item.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("queue source rows require a source_id")
        if source_id in queue:
            raise ValueError(f"duplicate queue source ID: {source_id}")
        queue[source_id] = item
    if set(catalog) != set(queue):
        raise ValueError("catalog and queue source IDs must match exactly")
    return catalog, queue


def _build_members(
    root: Path,
    catalog: Mapping[str, Mapping[str, Any]],
    receipt_evidence: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Build cohort member records with content-bound receipts."""

    members: list[dict[str, Any]] = []
    for source_id in sorted(receipt_evidence):
        source = catalog[source_id]
        receipt_path = receipt_evidence[source_id]
        members.append({
            "source_id": source_id,
            "jurisdictions": source.get("jurisdictions", []),
            "title": source.get("title", ""),
            "receipt_reference": receipt_path,
            "receipt_sha256": _sha256(root / receipt_path),
        })
    return members


def _build_deferred_sources(
    catalog: Mapping[str, Mapping[str, Any]],
    queue: Mapping[str, Mapping[str, Any]],
    deferred_ids: set[str],
) -> list[dict[str, Any]]:
    """Build per-source deferrals without changing their queue states."""

    deferred: list[dict[str, Any]] = []
    for source_id in sorted(deferred_ids):
        source = catalog[source_id]
        queue_item = queue[source_id]
        deferred.append({
            "source_id": source_id,
            "jurisdictions": source.get("jurisdictions", []),
            "title": source.get("title", ""),
            "queue_state": queue_item.get("state", "unknown"),
            "evidence_scope": queue_item.get("evidence_scope", "none"),
            "defer_reason_code": _defer_reason_code(queue_item),
            "reason": queue_item.get("reason", ""),
            "next_action": queue_item.get("next_action", ""),
            "reentry_trigger": REENTRY_TRIGGER,
        })
    return deferred


def _scope_accounting(
    catalog_count: int,
    current_scope_count: int,
    member_count: int,
    deferred_count: int,
    deferred_queue_landed_count: int,
    current_scope_landed_count: int,
    current_scope_missing_count: int,
    classes: Mapping[str, str],
) -> dict[str, Any]:
    """Return counts proving the cohort partitions the declared scope."""

    fixture_only_count = sum(
        source_class == "fixture_only" for source_class in classes.values()
    )
    excluded_count = sum(
        source_class == "excluded" for source_class in classes.values()
    )
    complete = (
        member_count + deferred_count == current_scope_count
        and current_scope_landed_count + current_scope_missing_count
        == current_scope_count
        and current_scope_count + fixture_only_count + excluded_count
        == catalog_count
    )
    return {
        "catalog_source_count": catalog_count,
        "current_scope_count": current_scope_count,
        "qualified_cohort_count": member_count,
        "deferred_current_scope_count": deferred_count,
        "current_scope_evaluator_landing_count": current_scope_landed_count,
        "current_scope_evaluator_missing_count": current_scope_missing_count,
        "deferred_queue_landed_count": deferred_queue_landed_count,
        "fixture_only_count": fixture_only_count,
        "excluded_count": excluded_count,
        "partition_complete": complete,
    }


def _preserved_current_scope(root: Path) -> dict[str, Any]:
    """Evaluate the original full-scope maturity gate independently."""

    maturity = evaluate_repository(root)
    completeness = next(
        row
        for row in maturity["properties"]
        if row["property_id"] == "completeness"
    )
    return {
        "horizon_id": CURRENT_SCOPE_HORIZON,
        "qualification_state": maturity["qualification_state"],
        "completeness_state": completeness["state"],
        "bronze_mature": maturity["bronze_mature"],
        "in_scope_count": maturity["completeness_inventory"][
            "bronze_in_scope_count"
        ],
        "evaluator_landing_count": (
            maturity["completeness_inventory"]["bronze_in_scope_count"]
            - maturity["completeness_inventory"][
                "in_scope_without_landing_or_blocker"
            ]
        ),
        "in_scope_without_landing_or_blocker": maturity[
            "completeness_inventory"
        ]["in_scope_without_landing_or_blocker"],
    }


def build_bronze_receipt_cohort(root: Path) -> dict[str, Any]:
    """Build the receipt cohort and an explicit ledger for omitted sources.

    Args:
        root: Repository root containing the catalogue, queue, and receipts.

    Returns:
        A deterministic cohort report. The report never changes the existing
        current-scope maturity result or Stable v1 gate.

    Raises:
        ValueError: If catalog or queue source identities are ambiguous or
            inconsistent.
    """

    catalog, queue = _load_source_maps(root)
    classes = {
        source_id: classify_catalog_source(source)
        for source_id, source in catalog.items()
    }
    current_scope_ids = {
        source_id
        for source_id, source_class in classes.items()
        if source_class == "bronze_in_scope"
    }
    receipt_evidence = receipt_backed_landing_evidence(
        root,
        current_scope_ids,
    )
    if not receipt_evidence:
        raise ValueError("receipt cohort has no validated source receipts")
    members = _build_members(root, catalog, receipt_evidence)
    deferred_ids = current_scope_ids - set(receipt_evidence)
    deferred = _build_deferred_sources(catalog, queue, deferred_ids)
    preserved_scope = _preserved_current_scope(root)
    deferred_queue_landed_count = sum(
        item["queue_state"] == "landed_and_evidenced" for item in deferred
    )
    accounting = _scope_accounting(
        len(catalog),
        len(current_scope_ids),
        len(members),
        len(deferred),
        deferred_queue_landed_count,
        preserved_scope["evaluator_landing_count"],
        preserved_scope["in_scope_without_landing_or_blocker"],
        classes,
    )
    if not accounting["partition_complete"]:
        raise ValueError("cohort source classes do not partition the catalog")

    return {
        "schema_id": "global-medicines-atlas.bronze-receipt-cohort",
        "schema_version": 1,
        "cohort_id": COHORT_ID,
        "qualification_state": "receipt_cohort_qualified",
        "qualification_basis": (
            "Every cohort member has a source-specific direct successful "
            "receipt accepted by the current Bronze maturity receipt "
            "validator. The cohort does not claim complete global or "
            "current-scope Bronze maturity."
        ),
        "inputs": {
            "receipt_validator": {
                "path": "src/global_medicines_atlas/bronze_maturity.py",
                "sha256": _sha256(
                    Path(__file__).with_name("bronze_maturity.py")
                ),
            },
            "cohort_generator": {
                "path": "src/global_medicines_atlas/bronze_receipt_cohort.py",
                "sha256": _sha256(Path(__file__)),
            },
            "cohort_schema": {
                "path": SCHEMA_RELATIVE,
                "sha256": _sha256(root / SCHEMA_RELATIVE),
            },
            "source_catalog": {
                "path": CATALOG_RELATIVE,
                "sha256": _sha256(root / CATALOG_RELATIVE),
            },
            "source_landing_queue": {
                "path": QUEUE_RELATIVE,
                "sha256": _sha256(root / QUEUE_RELATIVE),
            },
            "landing_overrides": {
                "path": LANDING_OVERRIDES_RELATIVE,
                "sha256": _sha256(root / LANDING_OVERRIDES_RELATIVE),
            },
        },
        "qualified_cohort": {
            "state": "qualified",
            "source_count": len(members),
            "members": members,
        },
        "deferred_source_ledger": {
            "state": "tracked_not_qualified",
            "source_count": len(deferred),
            "membership_rule": (
                "All current-scope source IDs without a direct successful "
                "receipt accepted by the Bronze maturity receipt validator "
                "remain listed, including sources with other landing evidence."
            ),
            "items": deferred,
        },
        "scope_accounting": accounting,
        "preserved_current_scope": preserved_scope,
        "boundaries": {
            "current_scope_definition_changed": False,
            "current_scope_qualification_overridden": False,
            "this_report_closes_stable_v1_m5_gate": False,
            "missing_sources_treated_as_negative_evidence": False,
            "source_payloads_acquired_by_this_report": False,
            "rights_or_publication_authority_granted": False,
            "external_publication_performed": False,
        },
    }


def dump_report(report: Mapping[str, Any]) -> str:
    """Serialize the cohort report as stable, indented JSON."""

    return json.dumps(report, indent=2, ensure_ascii=True) + "\n"


def _markdown_cell(value: Any) -> str:
    """Escape one value for a Markdown table cell."""

    text = str(value).replace("\n", " ").replace("\r", " ")
    escaped = escape(text, quote=True)
    return (
        escaped
        .replace("|", "&#124;")
        .replace("`", "&#96;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
    )


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render the cohort result and complete future-source list."""

    accounting = report["scope_accounting"]
    preserved = report["preserved_current_scope"]
    lines = [
        "# Bronze receipt cohort and future source list",
        "",
        (
            "This report qualifies only the listed source-specific successful "
            "receipts. It does not redefine current Bronze scope, establish "
            "global coverage, or clear Stable v1 M5."
        ),
        "",
        f"- Cohort: `{report['cohort_id']}`",
        f"- Receipt-qualified sources: `{accounting['qualified_cohort_count']}`",
        (
            f"- Deferred current-scope sources: "
            f"`{accounting['deferred_current_scope_count']}`"
        ),
        (
            f"- Full-scope evaluator landing evidence: "
            f"`{accounting['current_scope_evaluator_landing_count']}`"
        ),
        (
            f"- Deferred but queue-marked landed: "
            f"`{accounting['deferred_queue_landed_count']}`"
        ),
        (
            f"- Full-scope evaluator missing landing evidence: "
            f"`{accounting['current_scope_evaluator_missing_count']}`"
        ),
        f"- Current-scope Bronze status: `{preserved['qualification_state']}`",
        f"- Current-scope completeness: `{preserved['completeness_state']}`",
        (
            "- Current-scope Bronze mature: "
            f"`{str(preserved['bronze_mature']).lower()}`"
        ),
        "- Stable v1 M5 gate closed: `false`",
        "",
        (
            "The JSON qualification is "
            f"[`{REPORT_RELATIVE}`](../../{REPORT_RELATIVE}). Queue reasons "
            "and next actions remain source-specific. The re-entry condition "
            "requires a successful receipt validated under existing rights, "
            "credential, reuse, admission, and provenance gates; this list "
            "grants no acquisition authority."
        ),
        "",
        "## Receipt-qualified cohort",
        "",
        "| Source ID | Jurisdiction(s) | Source | Receipt |",
        "| --- | --- | --- | --- |",
    ]
    cohort = report["qualified_cohort"]
    for member in cohort["members"]:
        jurisdictions = ", ".join(member["jurisdictions"])
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    member["source_id"],
                    jurisdictions,
                    member["title"],
                    member["receipt_reference"],
                )
            )
            + " |"
        )
    lines.extend([
        "",
        "## Deferred current-scope sources",
        "",
        (
            "These sources remain in the original Bronze denominator. Their "
            "absence from the receipt cohort is not negative source evidence."
        ),
        "",
        "| Source ID | Jurisdiction(s) | Source | Queue state | Reason | Next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    ledger = report["deferred_source_ledger"]
    for item in ledger["items"]:
        jurisdictions = ", ".join(item["jurisdictions"])
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    item["source_id"],
                    jurisdictions,
                    item["title"],
                    item["queue_state"],
                    item["reason"],
                    item["next_action"],
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"
