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
from scripts.qualify_bronze_maturity import main as qualify_bronze_main

from global_medicines_atlas import bronze_maturity as bronze_maturity_mod
from global_medicines_atlas.bronze_maturity import (
    CATALOG_RELATIVE,
    FDA_SHORTAGES_HISTORICAL_SNAPSHOT_COUNT,
    PROPERTY_IDS,
    SCHEMA_RELATIVE,
    classify_catalog_source,
    dump_report,
    evaluate_completeness,
    evaluate_repository,
    landing_source_ids,
    receipt_backed_landing_evidence,
    receipt_backed_landing_source_ids,
    reject_forbidden_evidence,
    run_adversarial_review,
)
from global_medicines_atlas.cms_partd_qualification import (
    RAW_RELATIVE,
    RECORDS_RELATIVE,
    RIGHTS_RELATIVE,
)

ROOT = Path(__file__).resolve().parents[1]
FIXED_CLOCK = datetime(2026, 8, 20, 6, 48, tzinfo=UTC)


def test_cms_source_record_qualification_counts_as_bronze_landing() -> None:
    evidence = receipt_backed_landing_evidence(
        ROOT, {"us-cms-partd-formulary", "us-cms-partd-spending"}
    )
    assert evidence == {
        "us-cms-partd-formulary": (
            "quality/qualifications/cms-partd-source-record-qualification-20260927.json"
        ),
        "us-cms-partd-spending": (
            "quality/qualifications/cms-partd-source-record-qualification-20260927.json"
        ),
    }


def test_fda_shortages_scoped_internal_receipt_counts_as_bronze_landing() -> (
    None
):
    evidence = receipt_backed_landing_evidence(ROOT, {"us-fda-drug-shortages"})
    assert evidence == {
        "us-fda-drug-shortages": (
            "quality/qualifications/fda-shortages-live-corpus-20260821.json"
        )
    }


def test_fda_shortages_success_predicate_accepts_qualified_receipt() -> None:
    receipt = json.loads(
        (
            ROOT
            / "quality/qualifications/fda-shortages-live-corpus-20260821.json"
        ).read_text(encoding="utf-8")
    )
    assert bronze_maturity_mod._is_successful_fda_shortages_receipt(
        receipt, "us-fda-drug-shortages"
    )
    assert FDA_SHORTAGES_HISTORICAL_SNAPSHOT_COUNT == 129


def test_nice_internal_acquisition_receipt_counts_as_bronze_landing() -> None:
    evidence = receipt_backed_landing_evidence(
        ROOT, {"gb-nice-medicines-utilisation"}
    )
    assert evidence == {
        "gb-nice-medicines-utilisation": (
            "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
        )
    }
    receipt = json.loads(
        (
            ROOT
            / "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
        ).read_text(encoding="utf-8")
    )
    assert receipt["source_records_projected"] is False
    assert receipt["external_publication_authorized"] is False


@pytest.mark.unit
def test_sweden_private_aggregate_receipt_counts_as_bronze_landing() -> None:
    evidence = receipt_backed_landing_evidence(
        ROOT, {bronze_maturity_mod.SWEDEN_SOURCE_ID}
    )
    assert evidence == {
        bronze_maturity_mod.SWEDEN_SOURCE_ID: bronze_maturity_mod.SWEDEN_QUALIFICATION_RELATIVE
    }
    receipt = json.loads(
        (ROOT / bronze_maturity_mod.SWEDEN_QUALIFICATION_RELATIVE).read_text(
            encoding="utf-8"
        )
    )
    assert receipt["rights_boundary"]["coarse_rights_state"] == "unknown"
    assert receipt["rights_boundary"]["publication_authorized"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda receipt: receipt.update(workflow_commit="0" * 40),
        lambda receipt: receipt["payload_sha256"].pop(),
        lambda receipt: receipt["retention"].update(archive_sha256="0" * 64),
        lambda receipt: receipt["rights_boundary"].update(
            external_publication_authorized=True
        ),
    ],
)
@pytest.mark.unit
def test_sweden_landing_rejects_receipt_or_boundary_drift(
    tmp_path: Path, mutate
) -> None:
    receipt = json.loads(
        (ROOT / bronze_maturity_mod.SWEDEN_QUALIFICATION_RELATIVE).read_text(
            encoding="utf-8"
        )
    )
    mutate(receipt)
    relative = bronze_maturity_mod.SWEDEN_QUALIFICATION_RELATIVE
    receipt_path = tmp_path / relative
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    overrides = tmp_path / bronze_maturity_mod.LANDING_OVERRIDES_RELATIVE
    overrides.parent.mkdir(parents=True)
    overrides.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": bronze_maturity_mod.SWEDEN_SOURCE_ID,
                    "state": "landed_and_evidenced",
                    "evidence_references": [relative],
                }
            ]
        }),
        encoding="utf-8",
    )
    assert (
        receipt_backed_landing_evidence(
            tmp_path, {bronze_maturity_mod.SWEDEN_SOURCE_ID}
        )
        == {}
    )


@pytest.mark.parametrize(
    "authorization_field",
    [
        "acquisition_authorized",
        "internal_retention_authorized",
        "public_release_authorized",
        "external_publication_authorized",
    ],
)
def test_nice_internal_landing_requires_source_specific_rights(
    tmp_path: Path, authorization_field: str
) -> None:
    receipt = json.loads(
        (
            ROOT
            / "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
        ).read_text(encoding="utf-8")
    )
    authorization = json.loads(
        (
            ROOT
            / "quality/qualifications/nice-utilisation-acquisition-authorization.json"
        ).read_text(encoding="utf-8")
    )
    authorization[authorization_field] = not authorization[authorization_field]
    authorization_path = (
        tmp_path
        / "quality/qualifications/nice-utilisation-acquisition-authorization.json"
    )
    authorization_path.parent.mkdir(parents=True)
    authorization_path.write_text(json.dumps(authorization), encoding="utf-8")
    receipt_path = (
        tmp_path
        / "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
    )
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    overrides_path = (
        tmp_path
        / "src/global_medicines_atlas/data/source_landing_overrides.json"
    )
    overrides_path.parent.mkdir(parents=True)
    overrides_path.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": "gb-nice-medicines-utilisation",
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )

    assert (
        receipt_backed_landing_evidence(
            tmp_path, {"gb-nice-medicines-utilisation"}
        )
        == {}
    )


@pytest.mark.parametrize(
    "failure",
    [
        "missing_authorization",
        "invalid_authorization",
        "archive",
        "hashes",
        "truncated_payloads",
    ],
)
def test_nice_internal_landing_rejects_incomplete_receipt_metadata(
    tmp_path: Path, failure: str
) -> None:
    receipt = json.loads(
        (
            ROOT
            / "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
        ).read_text(encoding="utf-8")
    )
    authorization = json.loads(
        (
            ROOT
            / "quality/qualifications/nice-utilisation-acquisition-authorization.json"
        ).read_text(encoding="utf-8")
    )
    if failure == "archive":
        receipt["private_archive"] = None
    elif failure == "hashes":
        receipt["payload_sha256"] = {}
    elif failure == "truncated_payloads":
        receipt["payload_count"] = 1
        receipt["accepted_admission_count"] = 1
        receipt["acquisition_manifest_count"] = 1
        receipt["payload_sha256"] = receipt["payload_sha256"][:1]
        receipt["private_archive"]["restored_payload_count"] = 1
    receipt_path = (
        tmp_path
        / "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
    )
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    authorization_path = (
        tmp_path
        / "quality/qualifications/nice-utilisation-acquisition-authorization.json"
    )
    if failure != "missing_authorization":
        authorization_path.write_text(
            "[]"
            if failure == "invalid_authorization"
            else json.dumps(authorization),
            encoding="utf-8",
        )
    overrides_path = (
        tmp_path
        / "src/global_medicines_atlas/data/source_landing_overrides.json"
    )
    overrides_path.parent.mkdir(parents=True)
    overrides_path.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": "gb-nice-medicines-utilisation",
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "quality/qualifications/nice-utilisation-acquisition-success-20260821.json"
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )

    assert (
        receipt_backed_landing_evidence(
            tmp_path, {"gb-nice-medicines-utilisation"}
        )
        == {}
    )


@pytest.mark.parametrize(
    ("source_id", "field", "value"),
    [
        ("us-fda-orange-book", "prompt_complete", True),
        ("us-fda-drug-shortages", "prompt_complete", False),
        ("us-fda-drug-shortages", "schema_version", True),
        ("us-fda-drug-shortages", "current_source_record_rows", 0),
        ("us-fda-drug-shortages", "archive_checksums_verified", 0),
    ],
)
def test_fda_shortages_success_predicate_rejects_unqualified_receipt(
    source_id: str, field: str, value: object
) -> None:
    receipt = json.loads(
        (
            ROOT
            / "quality/qualifications/fda-shortages-live-corpus-20260821.json"
        ).read_text(encoding="utf-8")
    )
    receipt[field] = value
    assert not bronze_maturity_mod._is_successful_fda_shortages_receipt(
        receipt, source_id
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("internal_retention_authorized", False),
        ("current_source_record_projection_count", 0),
        ("current_recovered_source_record_projection_count", 0),
        ("current_source_record_parquet_pairs_byte_identical", 0),
        ("unique_historical_list_snapshots_archived", 128),
        ("external_publication_performed", True),
        ("historical_detail_snapshot_coverage_complete", True),
    ],
)
def test_fda_shortages_receipt_fails_closed_on_scope_or_evidence_drift(
    tmp_path: Path, field: str, value: object
) -> None:
    qualification = json.loads(
        (
            ROOT
            / "quality/qualifications/fda-shortages-live-corpus-20260821.json"
        ).read_text(encoding="utf-8")
    )
    qualification[field] = value
    receipt = (
        tmp_path
        / "quality/qualifications/fda-shortages-live-corpus-20260821.json"
    )
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps(qualification), encoding="utf-8")
    overrides = tmp_path / bronze_maturity_mod.LANDING_OVERRIDES_RELATIVE
    overrides.parent.mkdir(parents=True)
    overrides.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": "us-fda-drug-shortages",
                    "state": "landed_and_evidenced",
                    "evidence_references": [str(receipt.relative_to(tmp_path))],
                }
            ]
        }),
        encoding="utf-8",
    )
    assert (
        receipt_backed_landing_evidence(tmp_path, {"us-fda-drug-shortages"})
        == {}
    )


def test_cms_maturity_landing_rejects_rights_drift(tmp_path: Path) -> None:
    for relative in (RAW_RELATIVE, RECORDS_RELATIVE, RIGHTS_RELATIVE):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    overrides = tmp_path / bronze_maturity_mod.LANDING_OVERRIDES_RELATIVE
    overrides.parent.mkdir(parents=True, exist_ok=True)
    overrides.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": "us-cms-partd-spending",
                    "state": "landed_and_evidenced",
                    "evidence_references": [RECORDS_RELATIVE],
                }
            ]
        }),
        encoding="utf-8",
    )
    rights = json.loads(
        (tmp_path / RIGHTS_RELATIVE).read_text(encoding="utf-8")
    )
    rights["external_publication_authorized"] = False
    (tmp_path / RIGHTS_RELATIVE).write_text(
        json.dumps(rights), encoding="utf-8"
    )
    assert (
        receipt_backed_landing_evidence(tmp_path, {"us-cms-partd-spending"})
        == {}
    )


@pytest.mark.unit
@pytest.mark.parametrize("path_kind", ["relative", "absolute"])
def test_qualification_cli_accepts_custom_output_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path_kind: str
) -> None:
    monkeypatch.chdir(tmp_path)
    target = Path("reports/bronze.json")
    if path_kind == "absolute":
        target = tmp_path / target
    assert qualify_bronze_main(["--output", str(target)]) == 0
    report = json.loads(target.read_text(encoding="utf-8"))
    assert report["report_complete"] is True
    assert report["qualification_state"] in {"blocked", "qualified"}


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
def test_receipt_backed_landing_requires_exact_nonpublication_receipt(
    tmp_path: Path,
) -> None:
    overrides = tmp_path / (
        "src/global_medicines_atlas/data/source_landing_overrides.json"
    )
    overrides.parent.mkdir(parents=True)
    receipts = tmp_path / "quality/qualifications"
    receipts.mkdir(parents=True)
    (receipts / "bronze.json").write_text(
        json.dumps({
            "schema_id": "global-medicines-atlas.example-live-qualification",
            "accepted_admission_count": 1,
            "source_ids": ["au-artg"],
        }),
        encoding="utf-8",
    )
    (receipts / "publication.json").write_text(
        json.dumps({"source_ids": ["au-pbs"]}), encoding="utf-8"
    )
    (receipts / "invalid.json").write_text("{", encoding="utf-8")
    publication_directory = tmp_path / "docs/publication"
    publication_directory.mkdir(parents=True)
    (publication_directory / "admission.json").write_text(
        json.dumps({
            "schema_id": "global-medicines-atlas.example-live-qualification",
            "accepted_admission_count": 1,
            "source_ids": ["publication-path"],
        }),
        encoding="utf-8",
    )
    overrides.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": "au-artg",
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "quality/qualifications/bronze.json"
                    ],
                },
                {
                    "source_id": "au-pbs",
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "quality/qualifications/publication.json"
                    ],
                },
                {
                    "source_id": "missing-evidence",
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        None,
                        "quality/qualifications/missing.json",
                        "quality/qualifications/invalid.json",
                    ],
                },
                {
                    "source_id": "publication-path",
                    "state": "landed_and_evidenced",
                    "evidence_references": ["docs/publication/admission.json"],
                },
            ]
        }),
        encoding="utf-8",
    )
    assert receipt_backed_landing_source_ids(
        tmp_path, {"au-artg", "au-pbs", "missing-evidence", "publication-path"}
    ) == {"au-artg"}
    assert receipt_backed_landing_evidence(tmp_path, {"au-artg"}) == {
        "au-artg": "quality/qualifications/bronze.json"
    }


@pytest.mark.unit
def test_us_live_records_receipt_counts_only_recovered_source_products(
    tmp_path: Path,
) -> None:
    source_id = "us-openfda-faers"
    overrides = tmp_path / bronze_maturity_mod.LANDING_OVERRIDES_RELATIVE
    overrides.parent.mkdir(parents=True)
    overrides.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": source_id,
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "quality/qualifications/us-live-bronze-records.json"
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )
    receipt = tmp_path / "quality/qualifications/us-live-bronze-records.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(
        json.dumps({
            "schema_id": "global-medicines-atlas.us-live-bronze-records-qualification",
            "schema_version": 1,
            "evidence_class": "live_bounded_internal",
            "source_count": 1,
            "acquisition_succeeded_count": 1,
            "acquisition_failed_count": 0,
            "accepted_admission_count": 1,
            "quarantined_admission_count": 0,
            "recovered_acquisition_count": 1,
            "source_record_projection_count": 1,
            "recovered_source_record_projection_count": 1,
            "source_record_parquet_pairs_byte_identical": 1,
            "record_products": [{"source_id": source_id, "row_count": 4}],
            "coverage_complete": False,
            "external_publication_performed": False,
            "public_release_authorized": False,
        }),
        encoding="utf-8",
    )
    assert receipt_backed_landing_evidence(tmp_path, {source_id}) == {
        source_id: "quality/qualifications/us-live-bronze-records.json"
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "value", "products"),
    [
        ("recovered_acquisition_count", 0, None),
        ("recovered_source_record_projection_count", 0, None),
        ("source_record_parquet_pairs_byte_identical", 0, None),
        ("external_publication_performed", True, None),
        ("coverage_complete", True, None),
        ("source_count", 0, None),
        ("acquisition_failed_count", 1, None),
        ("accepted_admission_count", 2, None),
        ("quarantined_admission_count", 1, None),
        ("source_record_projection_count", 0, None),
        (
            "acquisition_succeeded_count",
            1,
            [{"source_id": "other", "row_count": 4}],
        ),
        (
            "acquisition_succeeded_count",
            1,
            [{"source_id": "us-openfda-faers", "row_count": True}],
        ),
        (
            "acquisition_succeeded_count",
            1,
            [{"source_id": "us-openfda-faers", "row_count": 0}],
        ),
        (
            "acquisition_succeeded_count",
            1,
            [
                {"source_id": "us-openfda-faers", "row_count": 4},
                {"source_id": "us-openfda-faers", "row_count": 3},
            ],
        ),
        ("acquisition_succeeded_count", 1, [None]),
        ("acquisition_succeeded_count", 1, []),
    ],
)
def test_us_live_records_receipt_fails_closed_on_inconsistent_summary(
    tmp_path: Path,
    field: str,
    value: object,
    products: list[object] | None,
) -> None:
    source_id = "us-openfda-faers"
    overrides = tmp_path / bronze_maturity_mod.LANDING_OVERRIDES_RELATIVE
    overrides.parent.mkdir(parents=True)
    overrides.write_text(
        json.dumps({
            "overrides": [
                {
                    "source_id": source_id,
                    "state": "landed_and_evidenced",
                    "evidence_references": [
                        "quality/qualifications/us-live-bronze-records.json"
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )
    receipt_data: dict[str, object] = {
        "schema_id": "global-medicines-atlas.us-live-bronze-records-qualification",
        "schema_version": 1,
        "evidence_class": "live_bounded_internal",
        "source_count": 1,
        "acquisition_succeeded_count": 1,
        "acquisition_failed_count": 0,
        "accepted_admission_count": 1,
        "quarantined_admission_count": 0,
        "recovered_acquisition_count": 1,
        "source_record_projection_count": 1,
        "recovered_source_record_projection_count": 1,
        "source_record_parquet_pairs_byte_identical": 1,
        "record_products": (
            [{"source_id": source_id, "row_count": 4}]
            if products is None
            else products
        ),
        "coverage_complete": False,
        "external_publication_performed": False,
        "public_release_authorized": False,
    }
    receipt_data[field] = value
    receipt = tmp_path / "quality/qualifications/us-live-bronze-records.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps(receipt_data), encoding="utf-8")
    assert receipt_backed_landing_evidence(tmp_path, {source_id}) == {}


@pytest.mark.integration
def test_repository_us_live_records_override_scope_is_exact() -> None:
    covered_ids = {
        "us-fda-nsde",
        "us-openfda-drugsfda",
        "us-openfda-faers",
        "us-openfda-nsde",
        "us-fda-orange-book",
        "us-fda-drug-shortages",
    }
    evidence = receipt_backed_landing_evidence(ROOT, covered_ids)
    assert set(evidence) == {
        "us-fda-drug-shortages",
        "us-fda-nsde",
        "us-fda-orange-book",
        "us-openfda-drugsfda",
        "us-openfda-faers",
        "us-openfda-nsde",
    }
    assert set(evidence.values()) == {
        "quality/qualifications/fda-shortages-live-corpus-20260821.json",
        "quality/qualifications/us-live-bronze-records-20260820.json",
    }


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
