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

from global_medicines_atlas import bronze_maturity as bronze_maturity_mod
from global_medicines_atlas.bronze_maturity import (
    CATALOG_RELATIVE,
    PROPERTY_IDS,
    SCHEMA_RELATIVE,
    classify_catalog_source,
    dump_report,
    evaluate_completeness,
    evaluate_repository,
    landing_source_ids,
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


def _validate(report: dict[str, Any]) -> None:
    _validator().validate(  # pyright: ignore[reportUnknownMemberType]
        report
    )


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
    _validate(report)
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
        _validate(invalid)


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
    _validate(_load(path))
    assert _load(path)["bronze_mature"] is False


def _row(
    property_id: str,
    *,
    state: str = "evidenced",
    evidence: tuple[str, ...] = ("DATA_LICENSE.md",),
    blocker_ids: tuple[str, ...] = (),
    notes: str = "ok",
) -> dict[str, Any]:
    return {
        "property_id": property_id,
        "mandatory": True,
        "state": state,
        "requirement_ids": ["M-092"],
        "evidence": list(evidence),
        "blocker_ids": list(blocker_ids),
        "notes": notes,
    }


def _full_properties(**overrides: Any) -> list[dict[str, Any]]:
    rows = [_row(property_id) for property_id in PROPERTY_IDS]
    for key, value in overrides.items():
        rows[0][key] = value
    return rows


@pytest.mark.unit
def test_landing_source_ids_skips_undecodable_and_pyc_files(
    tmp_path: Path,
) -> None:
    adapters = tmp_path / "src/global_medicines_atlas/adapters"
    fixtures = tmp_path / "tests/fixtures/nested"
    adapters.mkdir(parents=True)
    fixtures.mkdir(parents=True)
    (adapters / "ok.py").write_text('"au-artg"\n', encoding="utf-8")
    (adapters / "skip.pyc").write_bytes(b"\x00compiled")
    (fixtures / "binary.bin").write_bytes(b"\xff\xfe")
    found = landing_source_ids(tmp_path, {"au-artg", "missing"})
    assert found == {"au-artg"}


@pytest.mark.unit
def test_completeness_is_evidenced_when_every_in_scope_source_landed(
    tmp_path: Path,
) -> None:
    catalog = tmp_path / CATALOG_RELATIVE
    catalog.parent.mkdir(parents=True)
    catalog.write_text(
        json.dumps({
            "sources": [
                {
                    "source_id": "au-artg",
                    "authentication": "none",
                    "access_mode": "web_search",
                    "implemented_ingestion": True,
                },
                {
                    "source_id": "global-rxnorm",
                    "authentication": "none",
                    "access_mode": "api",
                },
                {
                    "source_id": "au-pbs-embargo",
                    "authentication": "manual_approval",
                    "access_mode": "licensed_feed",
                },
            ]
        }),
        encoding="utf-8",
    )
    spec = tmp_path / (
        "conductor/tracks/bronze_medallion_completion_20260819/spec.md"
    )
    spec.parent.mkdir(parents=True)
    spec.write_text("bronze\n", encoding="utf-8")
    contracts = (
        tmp_path / "src/global_medicines_atlas/adapters/fixture_contracts.py"
    )
    contracts.parent.mkdir(parents=True, exist_ok=True)
    contracts.write_text('SOURCE = "au-artg"\n', encoding="utf-8")
    property_row, inventory = evaluate_completeness(tmp_path)
    assert property_row["state"] == "evidenced"
    assert inventory["in_scope_without_landing_or_blocker"] == 0


@pytest.mark.unit
def test_adversarial_review_covers_fail_closed_branches(
    tmp_path: Path,
) -> None:
    forbidden_path = "docs/publication/data-layer-archive-receipt.md"
    (tmp_path / forbidden_path).parent.mkdir(parents=True)
    (tmp_path / forbidden_path).write_text("archive\n", encoding="utf-8")
    needle_path = "notes/later-layer.md"
    (tmp_path / needle_path).parent.mkdir(parents=True)
    (tmp_path / needle_path).write_text(
        "silver implementation complete\n",
        encoding="utf-8",
    )
    (tmp_path / "DATA_LICENSE.md").write_text("CC-BY-4.0\n", encoding="utf-8")

    forbidden = run_adversarial_review(
        tmp_path,
        _full_properties(evidence=[forbidden_path]),
        bronze_mature=False,
    )
    assert any(
        item["finding_id"] == "ADV-FORBIDDEN-EVIDENCE"
        and item["severity"] == "error"
        for item in forbidden["findings"]
    )

    missing = run_adversarial_review(
        tmp_path,
        _full_properties(evidence=["absent-evidence.md"]),
        bronze_mature=False,
    )
    assert any(
        item["finding_id"].startswith("ADV-MISSING-")
        for item in missing["findings"]
    )

    needle = run_adversarial_review(
        tmp_path,
        _full_properties(evidence=[needle_path]),
        bronze_mature=False,
    )
    assert any(
        item["finding_id"].startswith("ADV-NEEDLE-")
        for item in needle["findings"]
    )

    qualified = run_adversarial_review(
        tmp_path,
        _full_properties(),
        bronze_mature=True,
    )
    assert any(
        item["finding_id"] == "ADV-FALSE-MATURITY"
        and "Every mandatory property is evidenced" in item["detail"]
        for item in qualified["findings"]
    )

    mismatch = run_adversarial_review(
        tmp_path,
        [_row("completeness")],
        bronze_mature=False,
    )
    assert any(
        item["finding_id"] == "ADV-PROPERTY-SET" and item["severity"] == "error"
        for item in mismatch["findings"]
    )


@pytest.mark.unit
def test_duplicate_blocker_ids_are_emitted_once() -> None:
    blockers = bronze_maturity_mod._blockers_from_properties((
        _row("completeness", state="blocked", blocker_ids=("shared",)),
        _row("quarantine", state="blocked", blocker_ids=("shared",)),
    ))
    assert [item["blocker_id"] for item in blockers] == ["shared"]


@pytest.mark.unit
def test_evaluate_repository_fail_closes_inconsistent_maturity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "DATA_LICENSE.md").write_text("CC-BY-4.0\n", encoding="utf-8")
    inventory = {
        "catalog_source_count": 1,
        "bronze_in_scope_count": 1,
        "fixture_only_count": 0,
        "excluded_count": 0,
        "in_scope_without_landing_or_blocker": 0,
        "missing_coverage_is_not_negative_evidence": True,
    }

    def fake_completeness(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        del root
        return _row("completeness"), inventory

    def fake_properties(rows: list[dict[str, Any]]):
        def inner(root: Path) -> list[dict[str, Any]]:
            del root
            return rows

        return inner

    inconsistent = _full_properties(blocker_ids=["stale"])
    monkeypatch.setattr(
        bronze_maturity_mod,
        "evaluate_properties",
        fake_properties(inconsistent),
    )
    monkeypatch.setattr(
        bronze_maturity_mod,
        "evaluate_completeness",
        fake_completeness,
    )
    blocked = evaluate_repository(tmp_path, git_commit=None)
    assert blocked["bronze_mature"] is False
    assert blocked["git_commit"] == "unspecified"
    assert blocked["blockers"]

    clean = _full_properties()
    monkeypatch.setattr(
        bronze_maturity_mod,
        "evaluate_properties",
        fake_properties(clean),
    )
    qualified = evaluate_repository(tmp_path, git_commit="abc")
    assert qualified["bronze_mature"] is True
    assert qualified["blockers"] == []

    poisoned = _full_properties(
        evidence=["docs/publication/data-layer-archive-receipt.md"],
    )
    (tmp_path / "docs/publication").mkdir(parents=True)
    (tmp_path / "docs/publication/data-layer-archive-receipt.md").write_text(
        "hf\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        bronze_maturity_mod,
        "evaluate_properties",
        fake_properties(poisoned),
    )
    review_failed = evaluate_repository(tmp_path, git_commit="abc")
    assert review_failed["bronze_mature"] is False
    assert review_failed["adversarial_review"]["passed"] is False
