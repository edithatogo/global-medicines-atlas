"""Bronze maturity qualification fails closed against repository evidence."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from global_medicines_atlas.bronze_maturity import (
    PROPERTY_IDS,
    SCHEMA_RELATIVE,
    classify_catalog_source,
    dump_report,
    evaluate_repository,
    reject_forbidden_evidence,
    run_adversarial_review,
)

ROOT = Path(__file__).resolve().parents[1]
FIXED_CLOCK = datetime(2026, 8, 20, 6, 48, tzinfo=UTC)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator():
    schema = _load(ROOT / SCHEMA_RELATIVE)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.mark.unit
def test_licensed_and_credentialed_sources_are_excluded_not_incomplete() -> (
    None
):
    assert (
        classify_catalog_source({
            "source_id": "au-artg",
            "authentication": "none",
            "access_mode": "web_search",
        })
        == "bronze_in_scope"
    )
    assert (
        classify_catalog_source({
            "source_id": "au-pbs-embargo",
            "authentication": "manual_approval",
            "access_mode": "licensed_feed",
        })
        == "excluded"
    )
    assert (
        classify_catalog_source({
            "source_id": "nz-nzulm-bulk",
            "authentication": "account",
            "access_mode": "download",
        })
        == "excluded"
    )
    assert (
        classify_catalog_source({
            "source_id": "global-rxnorm",
            "authentication": "none",
            "access_mode": "api",
        })
        == "fixture_only"
    )


@pytest.mark.unit
def test_publication_and_stable_v1_success_are_forbidden_bronze_evidence() -> (
    None
):
    rejected = reject_forbidden_evidence((
        "src/global_medicines_atlas/bronze_landing.py",
        "quality/qualifications/stable-v1-contract.json",
        "docs/publication/data-layer-archive-receipt.md",
    ))
    assert "quality/qualifications/stable-v1-contract.json" in rejected
    assert "docs/publication/data-layer-archive-receipt.md" in rejected
    assert "src/global_medicines_atlas/bronze_landing.py" not in rejected


@pytest.mark.unit
def test_live_report_validates_and_does_not_declare_false_maturity() -> None:
    report = evaluate_repository(
        ROOT,
        clock=lambda: FIXED_CLOCK,
        git_commit="test",
    )
    _validator().validate(report)
    assert [row["property_id"] for row in report["properties"]] == list(
        PROPERTY_IDS
    )
    assert report["report_complete"] is True
    assert (
        report["completeness_inventory"][
            "missing_coverage_is_not_negative_evidence"
        ]
        is True
    )
    inventory = report["completeness_inventory"]
    assert inventory["catalog_source_count"] == (
        inventory["bronze_in_scope_count"]
        + inventory["fixture_only_count"]
        + inventory["excluded_count"]
    )
    assert report["adversarial_review"]["actor"] == (
        "criteria-versus-code-tests-docs"
    )
    assert report["adversarial_review"]["kind"] == (
        "independent-repository-evidence-review"
    )
    assert "second maintainer" not in report["adversarial_review"]["method"]
    assert "not a person" in report["adversarial_review"]["method"]
    assert report["adversarial_review"]["passed"] is True
    blocked = [
        row["property_id"]
        for row in report["properties"]
        if row["state"] != "evidenced"
    ]
    if blocked:
        assert report["bronze_mature"] is False
        assert report["qualification_state"] == "blocked"
        assert report["blockers"]
    else:
        assert report["bronze_mature"] is True
        assert report["qualification_state"] == "qualified"
        assert report["blockers"] == []


@pytest.mark.unit
def test_schema_rejects_mature_declaration_with_blockers() -> None:
    report = evaluate_repository(
        ROOT,
        clock=lambda: FIXED_CLOCK,
        git_commit="test",
    )
    invalid = copy.deepcopy(report)
    invalid["bronze_mature"] = True
    invalid["qualification_state"] = "qualified"
    with pytest.raises(ValidationError):
        _validator().validate(invalid)


@pytest.mark.unit
def test_adversarial_review_rejects_false_maturity_claim() -> None:
    report = evaluate_repository(
        ROOT,
        clock=lambda: FIXED_CLOCK,
        git_commit="test",
    )
    review = run_adversarial_review(
        ROOT,
        report["properties"],
        bronze_mature=True,
    )
    errors = [
        item["finding_id"]
        for item in review["findings"]
        if item["severity"] == "error"
    ]
    if any(row["state"] != "evidenced" for row in report["properties"]):
        assert "ADV-FALSE-MATURITY" in errors
        assert review["passed"] is False
    else:
        assert review["passed"] is True


@pytest.mark.unit
def test_excluded_sources_are_not_counted_as_missing_landing() -> None:
    report = evaluate_repository(
        ROOT,
        clock=lambda: FIXED_CLOCK,
        git_commit="test",
    )
    catalog = _load(
        ROOT / "src/global_medicines_atlas/data/medicine_source_catalog.json"
    )
    excluded = [
        source["source_id"]
        for source in catalog["sources"]
        if classify_catalog_source(source) == "excluded"
    ]
    assert excluded
    notes = next(
        row["notes"]
        for row in report["properties"]
        if row["property_id"] == "completeness"
    )
    for source_id in excluded[:5]:
        assert source_id not in notes


@pytest.mark.unit
def test_dump_report_round_trips() -> None:
    report = evaluate_repository(
        ROOT,
        clock=lambda: FIXED_CLOCK,
        git_commit="deadbeef",
    )
    payload = dump_report(report)
    assert payload.endswith("\n")
    assert json.loads(payload)["git_commit"] == "deadbeef"


@pytest.mark.unit
def test_committed_report_matches_schema_when_present() -> None:
    path = ROOT / "quality/qualifications/bronze-maturity.json"
    if not path.is_file():
        pytest.skip("report not generated yet")
    _validator().validate(_load(path))
    assert _load(path)["bronze_mature"] is False
