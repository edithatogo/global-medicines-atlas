"""Measured adapter-cohort migration and rollback qualification."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol, cast

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from global_medicines_atlas import canonical_v2_cohorts as cohorts_module
from global_medicines_atlas.canonical_v2 import migrate_record_v1_to_v2
from global_medicines_atlas.canonical_v2_cohorts import (
    AdapterCohort,
    CohortQualification,
    ContentBoundCohortReceipt,
    MigrationCase,
    RecordQualification,
    build_representative_adapter_cohorts,
    qualify_adapter_cohort,
    qualify_representative_cohorts,
    receipt_bytes,
    write_receipt,
)
from sources.nz.nzulm_fhir import FhirResourceRecord

ROOT = Path(__file__).resolve().parents[1]
COMMITTED_RECEIPT = ROOT / "quality/qualifications/canonical-v2-cohorts.json"
CANONICAL_SCHEMA = ROOT / "schemas/canonical-medicine-v2.json"


class _SchemaValidator(Protocol):
    def validate(self, instance: object) -> None: ...


def _cohorts() -> tuple[AdapterCohort, ...]:
    return build_representative_adapter_cohorts(ROOT)


def _receipt() -> ContentBoundCohortReceipt:
    return qualify_representative_cohorts(_cohorts())


def _schema_validator() -> _SchemaValidator:
    schema = cast(
        "dict[str, Any]",
        json.loads(CANONICAL_SCHEMA.read_text(encoding="utf-8")),
    )
    Draft202012Validator.check_schema(schema)
    return cast("_SchemaValidator", Draft202012Validator(schema))


@pytest.mark.integration
def test_representative_cohorts_are_measured_without_global_overclaim() -> None:
    receipt = _receipt().receipt

    assert receipt.measured_records == 46
    assert receipt.migrated_records == 43
    assert receipt.blocked_records == 3
    assert receipt.all_migrated_round_trips_exact
    assert receipt.complete_global_coverage is False
    assert receipt.production_data_qualified is False


@pytest.mark.integration
def test_nzulm_nzmt_and_pmda_explicit_structure_migrate() -> None:
    cohorts = {item.cohort_id: item for item in _receipt().receipt.cohorts}

    nzmt = cohorts["new-zealand-nzulm-nzmt-preserved"]
    assert nzmt.measured_records == 42
    assert nzmt.migrated_records == 42
    assert nzmt.blocked_records == 0
    assert len(nzmt.fixtures) == 14
    assert nzmt.evidence_class == "preserved_upstream_fixture"

    pmda = cohorts["japan-pmda-representative"]
    assert pmda.measured_records == 1
    assert pmda.migrated_records == 1
    assert pmda.assertions.regulatory == 1


@pytest.mark.integration
def test_fda_pbs_and_ema_omit_required_substance_structure() -> None:
    cohorts = {item.cohort_id: item for item in _receipt().receipt.cohorts}

    for cohort_id in (
        "fda-drugsfda-api-representative",
        "australia-pbs-representative",
        "eu-ema-representative",
    ):
        cohort = cohorts[cohort_id]
        assert cohort.measured_records == 1
        assert cohort.migrated_records == 0
        assert cohort.blocked_records == 1
        result = cohort.records[0]
        assert result.result == "blocked_missing_explicit_structure"
        assert "explicit" in cast("str", result.block_reason)
        assert result.v2_sha256 is None
        assert result.rollback_v1_sha256 is None


@pytest.mark.integration
def test_regulatory_and_funding_counts_remain_separate() -> None:
    receipt = _receipt().receipt
    cohorts = {item.cohort_id: item for item in receipt.cohorts}

    assert receipt.assertions.regulatory == 3
    assert receipt.assertions.funding == 1
    assert receipt.assertions.formulary == 0
    assert receipt.assertions.total == 4
    assert cohorts["australia-pbs-representative"].assertions.funding == 1
    assert cohorts["australia-pbs-representative"].assertions.regulatory == 0
    assert cohorts["eu-ema-representative"].assertions.regulatory == 1
    assert cohorts["eu-ema-representative"].assertions.funding == 0


@pytest.mark.integration
def test_every_eligible_projection_validates_against_schema_v2() -> None:
    validator = _schema_validator()
    eligible = 0
    for cohort in _cohorts():
        for case in cohort.cases:
            if case.projection is None:
                continue
            eligible += 1
            migrated = migrate_record_v1_to_v2(case.record, case.projection)
            validator.validate(migrated.model_dump(mode="json"))

    assert eligible == 43


@pytest.mark.smoke
def test_committed_receipt_regenerates_byte_for_byte() -> None:
    assert COMMITTED_RECEIPT.read_bytes() == receipt_bytes(_receipt())


@pytest.mark.property
def test_cohort_order_does_not_change_receipt() -> None:
    cohorts = _cohorts()

    assert receipt_bytes(
        qualify_representative_cohorts(cohorts)
    ) == receipt_bytes(qualify_representative_cohorts(reversed(cohorts)))


@pytest.mark.edge
def test_content_bound_receipt_rejects_tampering() -> None:
    payload = _receipt().model_dump(mode="json")
    payload["receipt"]["migrated_records"] = 42

    with pytest.raises(ValidationError, match="receipt totals"):
        ContentBoundCohortReceipt.model_validate(payload)


@pytest.mark.edge
def test_content_digest_rejects_a_coherent_but_substituted_receipt() -> None:
    payload = _receipt().model_dump(mode="json")
    payload["receipt_sha256"] = "0" * 64

    with pytest.raises(ValidationError, match="digest mismatch"):
        ContentBoundCohortReceipt.model_validate(payload)


@pytest.mark.edge
def test_duplicate_cohort_identity_is_rejected() -> None:
    cohort = _cohorts()[0]

    with pytest.raises(ValueError, match="identifiers must be unique"):
        qualify_representative_cohorts((cohort, cohort))


@pytest.mark.edge
@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"v2_sha256": None}, "requires v2"),
        ({"rollback_v1_sha256": "0" * 64}, "exact v2-to-v1"),
        ({"block_reason": "unexpected"}, "cannot carry"),
    ],
)
def test_passed_record_receipt_fails_closed(
    updates: dict[str, object],
    message: str,
) -> None:
    passed = next(
        record
        for cohort in _receipt().receipt.cohorts
        for record in cohort.records
        if record.result == "passed"
    )
    payload = passed.model_dump(mode="json") | updates

    with pytest.raises(ValidationError, match=message):
        RecordQualification.model_validate(payload)


@pytest.mark.edge
def test_blocked_record_requires_only_a_reason() -> None:
    blocked = next(
        record
        for cohort in _receipt().receipt.cohorts
        for record in cohort.records
        if record.result == "blocked_missing_explicit_structure"
    )
    payload = blocked.model_dump(mode="json")
    payload["block_reason"] = None

    with pytest.raises(ValidationError, match="only a block reason"):
        RecordQualification.model_validate(payload)


@pytest.mark.edge
@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("sources", "source identifiers"),
        ("fixtures", "fixture artifacts"),
        ("records", "record results"),
        ("measured", "measured record count"),
        ("disposition", "disposition counts"),
        ("assertions", "assertion counts"),
    ],
)
def test_cohort_summary_rejects_incoherent_measurements(
    mutation: str,
    message: str,
) -> None:
    cohort = next(
        item
        for item in _receipt().receipt.cohorts
        if item.cohort_id == "new-zealand-nzulm-nzmt-preserved"
    )
    payload = cohort.model_dump(mode="json")
    if mutation == "sources":
        payload["source_ids"] = ["z-source", "a-source"]
    elif mutation == "fixtures":
        payload["fixtures"] = list(reversed(payload["fixtures"]))
    elif mutation == "records":
        payload["records"] = list(reversed(payload["records"]))
    elif mutation == "measured":
        payload["measured_records"] += 1
    elif mutation == "disposition":
        payload["migrated_records"] -= 1
    else:
        payload["assertions"]["regulatory"] += 1

    with pytest.raises(ValidationError, match=message):
        CohortQualification.model_validate(payload)


@pytest.mark.edge
@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("order", "cohorts must be sorted"),
        ("assertions", "assertion counts"),
        ("round_trip", "round-trip summary"),
    ],
)
def test_aggregate_summary_rejects_incoherent_evidence(
    mutation: str,
    message: str,
) -> None:
    payload = _receipt().receipt.model_dump(mode="json")
    if mutation == "order":
        payload["cohorts"] = list(reversed(payload["cohorts"]))
    elif mutation == "assertions":
        payload["assertions"]["funding"] += 1
    else:
        payload["all_migrated_round_trips_exact"] = False

    with pytest.raises(ValidationError, match=message):
        cohorts_module.CanonicalV2CohortReceipt.model_validate(payload)


@pytest.mark.edge
def test_migration_case_requires_exactly_one_disposition() -> None:
    case = next(
        case
        for cohort in _cohorts()
        for case in cohort.cases
        if case.projection is not None
    )

    with pytest.raises(ValueError, match="exactly one"):
        MigrationCase(record=case.record, projection=None)
    with pytest.raises(ValueError, match="exactly one"):
        MigrationCase(
            record=case.record,
            projection=case.projection,
            block_reason="both",
        )


@pytest.mark.edge
def test_duplicate_record_identity_is_rejected() -> None:
    cohort = _cohorts()[0]
    duplicate = replace(cohort, cases=(cohort.cases[0], cohort.cases[0]))

    with pytest.raises(ValueError, match="duplicate cohort record"):
        qualify_adapter_cohort(duplicate)


@pytest.mark.edge
def test_non_exact_runtime_rollback_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cohort = next(item for item in _cohorts() if item.cases[0].projection)
    original = cohort.cases[0].record
    changed = original.model_copy(
        update={
            "concept": original.concept.model_copy(
                update={"preferred_name": "substituted"}
            )
        }
    )
    monkeypatch.setattr(
        cohorts_module, "rollback_record_v2_to_v1", lambda _: changed
    )

    with pytest.raises(ValueError, match="non-exact canonical rollback"):
        qualify_adapter_cohort(replace(cohort, cases=(cohort.cases[0],)))


@pytest.mark.smoke
def test_receipt_writer_creates_parent_and_exact_bytes(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "receipt.json"
    receipt = _receipt()

    write_receipt(receipt, output)

    assert output.read_bytes() == receipt_bytes(receipt)


@pytest.mark.edge
def test_projection_helpers_reject_absent_or_malformed_native_fields() -> None:
    nz_case = next(
        cohort.cases[0]
        for cohort in _cohorts()
        if cohort.cohort_id == "new-zealand-nzulm-nzmt-preserved"
    )
    no_identifier = nz_case.record.model_copy(
        update={
            "concept": nz_case.record.concept.model_copy(
                update={"identifiers": ()}
            )
        }
    )
    with pytest.raises(ValueError, match="native identifier"):
        cohorts_module._identifier_map(no_identifier)

    assert cohorts_module._string_mapping(1) is None
    assert cohorts_module._string_mapping({1: "invalid"}) is None
    assert cohorts_module._first_coding(None) is None
    assert cohorts_module._first_coding({"coding": "invalid"}) is None
    with pytest.raises(ValueError, match="system is required"):
        cohorts_module._required_string({}, "system", "test")
    with pytest.raises(ValueError, match="malformed coded value"):
        cohorts_module._coding_display({"coding": "invalid"}, "test")
    assert (
        cohorts_module._coding_display(
            {"coding": [{"code": "explicit-code"}]}, "test"
        )
        == "explicit-code"
    )
    with pytest.raises(ValueError, match="display or code"):
        cohorts_module._coding_display({"coding": [{}]}, "test")
    with pytest.raises(ValueError, match="malformed ratio"):
        cohorts_module._ratio_text("invalid", "test")
    with pytest.raises(ValueError, match="malformed quantity"):
        cohorts_module._quantity_text("invalid", "test")
    with pytest.raises(TypeError, match="quantity value"):
        cohorts_module._quantity_text({"value": True, "unit": "mg"}, "test")
    with pytest.raises(ValueError, match="quantity unit"):
        cohorts_module._quantity_text({"value": 1, "unit": ""}, "test")


@pytest.mark.edge
@pytest.mark.parametrize(
    ("ingredient", "error"),
    [
        (None, "ingredient list"),
        ([], "exactly one"),
        (["invalid"], "malformed ingredient"),
        ([{}], "ingredient coding"),
    ],
)
def test_nzmt_projection_rejects_missing_ingredient_structure(
    ingredient: object,
    error: str,
) -> None:
    nz_case = next(
        cohort.cases[0]
        for cohort in _cohorts()
        if cohort.cohort_id == "new-zealand-nzulm-nzmt-preserved"
    )
    native = FhirResourceRecord(
        resource_type="Medication",
        resource_id="test",
        resource={"resourceType": "Medication", "ingredient": ingredient},
        source_path="fixture.json",
        source_sha256="a" * 64,
    )

    with pytest.raises((TypeError, ValueError), match=error):
        cohorts_module._nzmt_projection(nz_case.record, native)
