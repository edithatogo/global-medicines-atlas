"""Receipt-backed Bronze cohort and deferred-source ledger contracts."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from scripts.qualify_bronze_receipt_cohort import main

from global_medicines_atlas import bronze_receipt_cohort as cohort_module
from global_medicines_atlas.bronze_maturity import (
    classify_catalog_source,
    receipt_backed_landing_evidence,
)
from global_medicines_atlas.bronze_receipt_cohort import (
    build_bronze_receipt_cohort,
    dump_report,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _minimal_root(root: Path) -> None:
    schema = json.loads(
        (ROOT / "schemas/bronze-receipt-cohort-v1.json").read_text(
            encoding="utf-8"
        )
    )
    _write_json(root / "schemas/bronze-receipt-cohort-v1.json", schema)
    catalog = {
        "schema_version": 5,
        "sources": [
            {
                "source_id": "test-live-source",
                "jurisdictions": ["TST"],
                "title": "Accepted source",
                "authentication": "none",
                "access_mode": "download",
            },
            {
                "source_id": "test-deferred-source",
                "jurisdictions": ["TST"],
                "title": "Deferred source",
                "authentication": "none",
                "access_mode": "download",
            },
            {
                "source_id": "global-rxnorm",
                "jurisdictions": ["USA"],
                "title": "Fixture-only source",
                "authentication": "none",
                "access_mode": "api",
            },
            {
                "source_id": "test-credentialed-source",
                "jurisdictions": ["TST"],
                "title": "Credentialed source",
                "authentication": "account",
                "access_mode": "download",
            },
        ],
    }
    queue = {
        "items": [
            {
                "source_id": "test-live-source",
                "state": "landed_and_evidenced",
                "evidence_scope": "live_receipt",
                "reason": "Receipt is present.",
                "next_action": "Verify freshness.",
            },
            {
                "source_id": "test-deferred-source",
                "state": "manual_only_documented_acquisition",
                "evidence_scope": "none",
                "reason": "A documented export remains outstanding.",
                "next_action": "Complete the authorized export.",
            },
            {
                "source_id": "global-rxnorm",
                "state": "landed_and_evidenced",
                "evidence_scope": "governed_fixture",
                "reason": "Synthetic fixture only.",
                "next_action": "Retain fixture boundary.",
            },
            {
                "source_id": "test-credentialed-source",
                "state": "credentialed_and_excluded",
                "evidence_scope": "none",
                "reason": "Credentialed source.",
                "next_action": "Remain excluded.",
            },
        ]
    }
    _write_json(
        root / "src/global_medicines_atlas/data/medicine_source_catalog.json",
        catalog,
    )
    _write_json(
        root / "quality/qualifications/bronze-source-landing-queue.json",
        queue,
    )
    receipt_path = root / "quality/qualifications/test-live-receipt.json"
    _write_json(
        receipt_path,
        {
            "schema_id": (
                "global-medicines-atlas."
                "international-public-bronze-qualification"
            ),
            "source_id": "test-live-source",
            "accepted_admission_count": 1,
        },
    )
    _write_json(
        root / "src/global_medicines_atlas/data/source_landing_overrides.json",
        {
            "overrides": [
                {
                    "source_id": "test-live-source",
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "quality/qualifications/test-live-receipt.json"
                    ],
                },
                {
                    "source_id": "test-deferred-source",
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "https://example.invalid/receipt.json"
                    ],
                },
            ]
        },
    )


@pytest.mark.unit
def test_cohort_uses_qualified_receipts_and_keeps_other_classes_separate(
    tmp_path: Path,
) -> None:
    _minimal_root(tmp_path)

    report = build_bronze_receipt_cohort(tmp_path)

    assert [
        row["source_id"] for row in report["qualified_cohort"]["members"]
    ] == ["test-live-source"]
    assert [
        row["source_id"] for row in report["deferred_source_ledger"]["items"]
    ] == ["test-deferred-source"]
    assert report["scope_accounting"] == {
        "catalog_source_count": 4,
        "current_scope_count": 2,
        "qualified_cohort_count": 1,
        "deferred_current_scope_count": 1,
        "current_scope_evaluator_landing_count": 1,
        "current_scope_evaluator_missing_count": 1,
        "deferred_queue_landed_count": 0,
        "fixture_only_count": 1,
        "excluded_count": 1,
        "partition_complete": True,
    }
    assert report["preserved_current_scope"]["bronze_mature"] is False
    assert report["boundaries"]["this_report_closes_stable_v1_m5_gate"] is False
    assert report["deferred_source_ledger"]["items"][0]["next_action"] == (
        "Complete the authorized export."
    )


@pytest.mark.unit
def test_queue_claim_without_valid_receipt_remains_deferred(
    tmp_path: Path,
) -> None:
    _minimal_root(tmp_path)
    queue_path = (
        tmp_path / "quality/qualifications/bronze-source-landing-queue.json"
    )
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    queue["items"][1]["state"] = "landed_and_evidenced"
    queue["items"][1]["evidence_scope"] = "live_receipt"
    _write_json(queue_path, queue)

    report = build_bronze_receipt_cohort(tmp_path)

    deferred = report["deferred_source_ledger"]["items"][0]
    assert deferred["queue_state"] == "landed_and_evidenced"
    assert (
        deferred["defer_reason_code"]
        == "queue_landing_not_confirmed_by_receipt_validator"
    )
    assert report["scope_accounting"]["deferred_queue_landed_count"] == 1
    assert report["qualified_cohort"]["source_count"] == 1


@pytest.mark.unit
def test_cohort_rejects_catalog_and_queue_identity_drift(
    tmp_path: Path,
) -> None:
    _minimal_root(tmp_path)
    queue_path = (
        tmp_path / "quality/qualifications/bronze-source-landing-queue.json"
    )
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    queue["items"].pop()
    _write_json(queue_path, queue)

    with pytest.raises(ValueError, match="source IDs must match"):
        build_bronze_receipt_cohort(tmp_path)


@pytest.mark.unit
def test_cohort_rejects_malformed_and_duplicate_catalog_queue_rows(
    tmp_path: Path,
) -> None:
    cases = (
        ("catalog_sources_not_array", TypeError),
        ("catalog_row_not_object", TypeError),
        ("catalog_missing_id", ValueError),
        ("catalog_duplicate_id", ValueError),
        ("queue_items_not_array", TypeError),
        ("queue_row_not_object", TypeError),
        ("queue_missing_id", ValueError),
        ("queue_duplicate_id", ValueError),
    )
    for index, (case, error_type) in enumerate(cases):
        root = tmp_path / str(index)
        _minimal_root(root)
        is_catalog = case.startswith("catalog_")
        relative = (
            "src/global_medicines_atlas/data/medicine_source_catalog.json"
            if is_catalog
            else "quality/qualifications/bronze-source-landing-queue.json"
        )
        document = json.loads((root / relative).read_text(encoding="utf-8"))
        key = "sources" if is_catalog else "items"
        if case.endswith("not_array"):
            document[key] = {}
        elif case.endswith("row_not_object"):
            document[key].append(None)
        elif case.endswith("missing_id"):
            document[key][0].pop("source_id")
        elif case.endswith("duplicate_id"):
            document[key].append(copy.deepcopy(document[key][0]))
        _write_json(root / relative, document)

        with pytest.raises(error_type):
            build_bronze_receipt_cohort(root)


@pytest.mark.unit
def test_cohort_fails_closed_if_source_partition_is_inconsistent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _minimal_root(tmp_path)

    def inconsistent_accounting(*args: object) -> dict[str, bool]:
        del args
        return {"partition_complete": False}

    monkeypatch.setattr(
        cohort_module,
        "_scope_accounting",
        inconsistent_accounting,
    )

    with pytest.raises(ValueError, match="do not partition"):
        build_bronze_receipt_cohort(tmp_path)


@pytest.mark.unit
def test_empty_receipt_set_cannot_be_reported_as_qualified(
    tmp_path: Path,
) -> None:
    _minimal_root(tmp_path)
    (tmp_path / "quality/qualifications/test-live-receipt.json").unlink()

    with pytest.raises(ValueError, match="no validated source receipts"):
        build_bronze_receipt_cohort(tmp_path)


@pytest.mark.unit
def test_markdown_source_metadata_is_escaped() -> None:
    report: dict[str, Any] = {
        "cohort_id": "test",
        "scope_accounting": {
            "qualified_cohort_count": 1,
            "deferred_current_scope_count": 0,
            "current_scope_evaluator_landing_count": 1,
            "deferred_queue_landed_count": 0,
            "current_scope_evaluator_missing_count": 0,
        },
        "preserved_current_scope": {
            "qualification_state": "qualified",
            "completeness_state": "complete",
            "bronze_mature": True,
        },
        "qualified_cohort": {
            "members": [
                {
                    "source_id": "source-1",
                    "jurisdictions": ["<script>|`[link]`"],
                    "title": "Title",
                    "receipt_reference": "receipt.json",
                }
            ]
        },
        "deferred_source_ledger": {"items": []},
    }

    rendered = cohort_module.render_markdown(report)
    assert "&lt;script&gt;&#124;&#96;&#91;link&#93;&#96;" in rendered
    assert "<script>" not in rendered


@pytest.mark.unit
def test_report_and_future_list_regenerate_and_validate(
    tmp_path: Path,
) -> None:
    _minimal_root(tmp_path)
    schema_path = ROOT / "schemas/bronze-receipt-cohort-v1.json"
    _write_json(
        tmp_path / "schemas/bronze-receipt-cohort-v1.json",
        json.loads(schema_path.read_text(encoding="utf-8")),
    )

    assert main(["--root", str(tmp_path)]) == 0

    report = json.loads(
        (
            tmp_path / "quality/qualifications/bronze-receipt-cohort-v1.json"
        ).read_text(encoding="utf-8")
    )
    schema = json.loads(
        (tmp_path / "schemas/bronze-receipt-cohort-v1.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(  # pyright: ignore[reportUnknownMemberType]
        report
    )
    markdown = (
        tmp_path / "docs/qualification/bronze-future-source-list.md"
    ).read_text(encoding="utf-8")
    assert "test-deferred-source" in markdown
    assert "test-live-source" in markdown
    assert "Stable v1 M5 gate closed: `false`" in markdown
    assert markdown == render_markdown(report)
    assert dump_report(report).endswith("\n")


@pytest.mark.unit
def test_committed_cohort_is_current_and_does_not_hide_full_scope_gaps() -> (
    None
):
    report = build_bronze_receipt_cohort(ROOT)
    catalog = json.loads(
        (
            ROOT
            / "src/global_medicines_atlas/data/medicine_source_catalog.json"
        ).read_text(encoding="utf-8")
    )
    current_scope = {
        row["source_id"]
        for row in catalog["sources"]
        if classify_catalog_source(row) == "bronze_in_scope"
    }
    expected_cohort = set(receipt_backed_landing_evidence(ROOT, current_scope))
    actual_cohort = {
        row["source_id"] for row in report["qualified_cohort"]["members"]
    }
    assert actual_cohort == expected_cohort
    assert report["scope_accounting"]["partition_complete"] is True
    assert (
        report["scope_accounting"]["current_scope_evaluator_landing_count"]
        == 42
    )
    assert (
        report["scope_accounting"]["current_scope_evaluator_missing_count"]
        == 115
    )
    assert report["scope_accounting"]["deferred_queue_landed_count"] == 15
    assert report["preserved_current_scope"]["qualification_state"] == "blocked"
    assert report["preserved_current_scope"]["bronze_mature"] is False
    assert report["boundaries"]["this_report_closes_stable_v1_m5_gate"] is False
    committed_report = json.loads(
        (
            ROOT / "quality/qualifications/bronze-receipt-cohort-v1.json"
        ).read_text(encoding="utf-8")
    )
    assert committed_report == report
    assert (ROOT / "docs/qualification/bronze-future-source-list.md").read_text(
        encoding="utf-8"
    ) == render_markdown(report)
