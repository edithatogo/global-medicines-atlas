"""Build the auditable future-source ledger for bounded Bronze qualification."""

from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from global_medicines_atlas.bronze_maturity import (
    CATALOG_RELATIVE,
    HORIZON,
    SCOPE_DECISION_RELATIVE,
    classify_catalog_source,
    evaluate_repository,
)

ROOT = Path(__file__).resolve().parents[1]
QUEUE = "quality/qualifications/bronze-source-landing-queue.json"
REPORT = "quality/qualifications/bronze-bounded-scope-future-sources-v1.json"
MARKDOWN = "docs/qualification/bronze-bounded-scope-future-sources.md"
SCHEMA = "schemas/bronze-bounded-scope-future-sources-v1.json"


def build_report(root: Path) -> dict[str, Any]:
    """Bind the deferred IDs and source-specific actions to the decision."""
    catalog = json.loads((root / CATALOG_RELATIVE).read_text(encoding="utf-8"))
    queue = json.loads((root / QUEUE).read_text(encoding="utf-8"))
    decision_path = root / SCOPE_DECISION_RELATIVE
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    rows = {item["source_id"]: item for item in queue["items"]}
    scope = {
        row["source_id"]
        for row in catalog["sources"]
        if classify_catalog_source(row) == "bronze_in_scope"
    }
    active = set(decision["active_source_ids"])
    if not active <= scope:
        raise ValueError("bounded active source IDs do not match catalog")
    deferred_ids = sorted(scope - active)
    maturity = evaluate_repository(root)
    inventory = maturity["completeness_inventory"]
    if (
        maturity["horizon"] != HORIZON
        or inventory["bronze_in_scope_count"] != len(active)
        or inventory["full_bronze_source_universe_count"] != len(scope)
        or inventory["deferred_source_count"] != len(deferred_ids)
    ):
        raise ValueError(
            "maturity result does not reconcile with scope decision"
        )
    catalog_by_id = {row["source_id"]: row for row in catalog["sources"]}
    items: list[dict[str, Any]] = []
    for source_id in deferred_ids:
        source = catalog_by_id[source_id]
        queue_item = rows[source_id]
        items.append({
            "source_id": source_id,
            "jurisdictions": source.get("jurisdictions", []),
            "title": source.get("title", ""),
            "queue_state": queue_item.get("state", "unknown"),
            "reason": queue_item.get("reason", ""),
            "next_action": queue_item.get("next_action", ""),
            "reentry_trigger": decision["reentry_trigger"],
        })
    return {
        "schema_id": "global-medicines-atlas.bronze-bounded-scope-future-sources",
        "schema_version": 1,
        "ledger_id": "bronze-bounded-scope-future-sources-v1",
        "qualification_horizon": HORIZON,
        "qualification_state": maturity["qualification_state"],
        "scope_decision": {
            "path": SCOPE_DECISION_RELATIVE,
            "sha256": sha256(decision_path.read_bytes()).hexdigest(),
        },
        "source_accounting": {
            "catalog_source_count": len(catalog["sources"]),
            "full_public_source_count": len(scope),
            "active_source_count": len(active),
            "deferred_source_count": len(deferred_ids),
            "full_scope_missing_evidence_count": inventory[
                "full_scope_missing_count"
            ],
            "partition_complete": len(active) + len(deferred_ids) == len(scope),
        },
        "deferred_sources": items,
        "boundaries": {
            "missing_coverage_is_not_negative_evidence": True,
            "rights_or_acquisition_authority_granted": False,
            "publication_authority_granted": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    accounting = report["source_accounting"]
    items = report["deferred_sources"]
    lines = [
        "# Bronze bounded-scope future sources",
        "",
        "This versioned ledger records sources deferred from the approved `bronze-bounded-public-scope-v1` horizon. The full public catalogue universe remains visible; missing evidence is not negative evidence. This ledger grants no source acquisition, rights, retention, or publication authority.",
        "",
        f"- Full public source universe: `{accounting['full_public_source_count']}`",
        f"- Active qualification horizon: `{accounting['active_source_count']}`",
        f"- Deferred sources: `{accounting['deferred_source_count']}`",
        f"- Missing evidence across the full universe: `{accounting['full_scope_missing_evidence_count']}`",
        f"- Current bounded-horizon qualification: `{report['qualification_state']}`",
        f"- Machine-readable ledger: [`{REPORT}`](../../{REPORT})",
        f"- Scope decision: [`{SCOPE_DECISION_RELATIVE}`](../../{SCOPE_DECISION_RELATIVE})",
        "",
        "| Source ID | Jurisdictions | Source | Queue state | Reason | Next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in items:
        fields = [
            item["source_id"],
            ", ".join(item["jurisdictions"]),
            item["title"],
            item["queue_state"],
            item["reason"],
            item["next_action"],
        ]
        lines.append(
            "| "
            + " | ".join(
                str(value).replace("|", "&#124;").replace("\n", " ")
                for value in fields
            )
            + " |"
        )
    lines.extend((
        "",
        "A source re-enters qualification only after its source-specific existing rights, acquisition, reuse, admission, temporal-identity, provenance, and validation gates pass.",
        "",
    ))
    return "\n".join(lines)


def main() -> int:
    report = build_report(ROOT)
    schema = json.loads((ROOT / SCHEMA).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(report)  # pyright: ignore[reportUnknownMemberType]
    (ROOT / REPORT).write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / MARKDOWN).write_text(render_markdown(report), encoding="utf-8")
    print(
        f"wrote {REPORT} ({report['source_accounting']['deferred_source_count']} deferred sources)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
