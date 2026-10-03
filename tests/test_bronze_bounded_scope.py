"""Verify the approved bounded Bronze horizon and future-source ledger."""

from __future__ import annotations

import json
from hashlib import sha256

from jsonschema import Draft202012Validator
from scripts.build_bronze_bounded_scope_ledger import (
    MARKDOWN,
    REPORT,
    ROOT,
    SCHEMA,
    build_report,
    render_markdown,
)

from global_medicines_atlas.bronze_maturity import (
    CATALOG_RELATIVE,
    SCOPE_DECISION_RELATIVE,
    classify_catalog_source,
)


def test_scope_decision_is_catalog_bound_and_schema_valid() -> None:
    decision = json.loads((ROOT / SCOPE_DECISION_RELATIVE).read_text())
    schema = json.loads(
        (ROOT / "schemas/bronze-bounded-scope-decision-v1.json").read_text()
    )
    Draft202012Validator(schema).validate(decision)
    catalog = json.loads((ROOT / CATALOG_RELATIVE).read_text())["sources"]
    full_scope = {
        row["source_id"]
        for row in catalog
        if classify_catalog_source(row) == "bronze_in_scope"
    }
    assert decision["full_scope_source_count"] == len(full_scope) == 157
    assert (
        decision["full_scope_source_ids_sha256"]
        == sha256(("\n".join(sorted(full_scope)) + "\n").encode()).hexdigest()
    )
    assert len(decision["active_source_ids"]) == 42
    assert (
        decision["active_scope_source_ids_sha256"]
        == sha256(
            ("\n".join(sorted(decision["active_source_ids"])) + "\n").encode()
        ).hexdigest()
    )
    assert set(decision["active_source_ids"]) <= full_scope


def test_bounded_future_ledger_is_complete_and_reproducible() -> None:
    report = build_report(ROOT)
    schema = json.loads((ROOT / SCHEMA).read_text())
    Draft202012Validator(schema).validate(report)
    accounting = report["source_accounting"]
    assert accounting == {
        "catalog_source_count": 174,
        "full_public_source_count": 157,
        "active_source_count": 42,
        "deferred_source_count": 115,
        "full_scope_missing_evidence_count": 115,
        "partition_complete": True,
    }
    assert len(report["deferred_sources"]) == 115
    assert (
        len({item["source_id"] for item in report["deferred_sources"]}) == 115
    )
    assert all(
        item["reason"] and item["next_action"]
        for item in report["deferred_sources"]
    )
    assert report == json.loads((ROOT / REPORT).read_text())
    assert render_markdown(report) == (ROOT / MARKDOWN).read_text()
